#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
美股置顶实时浮窗（macOS）—— 1 分钟 K 线 / 24 小时分时（夜盘 + 盘前 + 盘中 + 盘后）

要显示哪些股票：编辑同目录下的 config.json，例如 {"symbols": ["SPY", "QQQ", "NVDA"]}，重启生效
也可以用预设：presets/ 目录下的 json，例如 presets/soxl-soxs.json

运行：  python3 stock_float.py                       # 使用 config.json
       python3 stock_float.py --preset soxl-soxs    # 使用 presets/soxl-soxs.json
       python3 stock_float.py --config 路径.json      # 使用指定配置文件
后台运行（可关终端）：  nohup python3 stock_float.py >/dev/null 2>&1 & disown

数据源自动选择：
  - 检测到 moomoo OpenD（127.0.0.1:11111）且装了 moomoo-api → moomoo 实时 1 分钟 K 线（含夜盘）
  - 否则 → Yahoo 1 分钟数据（没有夜盘），OpenD 一启动就自动切换

走势图横轴 = 一个完整的美股 24 小时交易日：美东 20:00 → 次日 20:00
  夜盘 20:00–04:00 | 盘前 04:00–09:30 | 盘中 09:30–16:00 | 盘后 16:00–20:00
虚线 = 上一个常规交易时段的收盘价

图表（右键切换）：1分钟 K 线（默认）/ 5分钟 / 15分钟 / 24小时分时线
  K 线显示最近 N 根（浮窗宽度能放下的根数），右侧虚线 = 最新价

操作：单击某一行 在 moomoo 打开该股票 | 左键拖动 移动 | 右键 菜单（图表、透明度、刷新、退出） | Esc 或 × 关闭
"""
import json
import os
import sys
import socket
import ssl
import threading
import time
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import tkinter as tk

try:
    from moomoo import OpenQuoteContext, SubType, KLType, RET_OK
    HAS_MOOMOO = True
except ImportError:
    try:
        from futu import OpenQuoteContext, SubType, KLType, RET_OK
        HAS_MOOMOO = True
    except ImportError:
        HAS_MOOMOO = False
try:
    from moomoo import Session
except ImportError:
    try:
        from futu import Session
    except ImportError:
        Session = None

# ---------------- 可调参数（默认值，可在 config.json 里覆盖） ----------------
SYMBOLS = ["SOXL", "SOXS"]
OPEND_HOST, OPEND_PORT = "127.0.0.1", 11111
REFRESH_MS = 2000           # 刷新间隔（毫秒）
HISTORY_EVERY = 300         # 每隔多少秒重新补一次完整历史分钟线
RED_UP = False              # True = 红涨绿跌；False = 绿涨红跌（美股 / moomoo 默认）
ALPHA = 0.86
WIDTH = 520
ROW_H = 92
HEADER_H = 22
FOOTER_H = 14
CHART_X0 = 150
CANDLE_W = 5                # 每根蜡烛占的像素宽度（含间隔），越小显示的根数越多
DEFAULT_MODE = "1"          # 默认图表："1"/"5"/"15" = 对应分钟 K 线；"line" = 24h 分时线
# -----------------------------------------

# ---------------- 读取 config.json ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _config_path(argv):
    """--preset 名称 → presets/名称.json；--config 路径 → 指定文件；否则 config.json"""
    for i, a in enumerate(argv):
        if a in ("--preset", "-p") and i + 1 < len(argv):
            name = argv[i + 1]
            return os.path.join(BASE_DIR, "presets",
                                name if name.endswith(".json") else name + ".json")
        if a in ("--config", "-c") and i + 1 < len(argv):
            return os.path.abspath(os.path.expanduser(argv[i + 1]))
    return os.path.join(BASE_DIR, "config.json")


CONFIG_PATH = _config_path(sys.argv[1:])
_cfg = {}
try:
    with open(CONFIG_PATH, encoding="utf-8") as _f:
        _cfg = json.load(_f)
except FileNotFoundError:
    if os.path.basename(CONFIG_PATH) != "config.json":
        print(f"找不到配置文件：{CONFIG_PATH}，使用默认设置")
except Exception as _e:
    print(f"config.json 读取失败，使用默认设置：{_e}")


def _clean_symbols(lst):
    out = []
    for x in lst if isinstance(lst, list) else []:
        sym = str(x).strip().upper().split(".")[-1]  # 允许写 "US.NVDA" 或 "NVDA"
        if sym and sym not in out:
            out.append(sym)
    return out


SYMBOLS = _clean_symbols(_cfg.get("symbols", SYMBOLS)) or ["SOXL", "SOXS"]
REFRESH_MS = int(_cfg.get("refresh_ms", REFRESH_MS))
DEFAULT_MODE = str(_cfg.get("default_mode", DEFAULT_MODE))
RED_UP = bool(_cfg.get("red_up", RED_UP))
ALPHA = float(_cfg.get("alpha", ALPHA))
CANDLE_W = max(2, int(_cfg.get("candle_width", CANDLE_W)))
OPEND_HOST = str(_cfg.get("opend_host", OPEND_HOST))
OPEND_PORT = int(_cfg.get("opend_port", OPEND_PORT))
if DEFAULT_MODE not in ("1", "5", "15", "line"):
    DEFAULT_MODE = "1"

BG, FG, DIM, GRID = "#b4cfeb", "#16202b", "#4a5d72", "#94b4d6"
GREEN, RED = "#0b9a5b", "#e2434d"
UP_C, DOWN_C = (RED, GREEN) if RED_UP else (GREEN, RED)
NY = ZoneInfo("America/New_York")
CODES = [f"US.{s}" for s in SYMBOLS]
# 时段分隔：距 20:00 开盘的小时数
SEPS = [(8.0, "盘前"), (13.5, "盘中"), (20.0, "盘后")]


def session_now():
    t = datetime.now(NY)
    m = t.hour * 60 + t.minute
    if t.weekday() == 5 or (t.weekday() == 6 and m < 20 * 60) or (t.weekday() == 4 and m >= 20 * 60):
        return "休市"
    if 4 * 60 <= m < 9 * 60 + 30:
        return "盘前"
    if 9 * 60 + 30 <= m < 16 * 60:
        return "盘中"
    if 16 * 60 <= m < 20 * 60:
        return "盘后"
    return "夜盘"


def _num(row, col):
    try:
        v = float(row[col])
        return v if v == v and v != 0 else None
    except (KeyError, TypeError, ValueError):
        return None


def _ts(time_key):
    """moomoo 美股 K 线 time_key 为美东时间字符串。"""
    return datetime.strptime(str(time_key)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=NY).timestamp()


def build_day(bars):
    """从 {时间戳: 价格} 里取出最近一个 24 小时交易日（美东 20:00 → 次日 20:00）。
    返回 (点列表[(ts, price)], 起点ts, 上一常规收盘价)。"""
    if not bars:
        return [], None, None
    keys = sorted(bars)
    last = datetime.fromtimestamp(keys[-1], NY)
    start = last.replace(hour=20, minute=0, second=0, microsecond=0)
    if last <= start:  # 20:00 那根是盘后最后一分钟，属于前一个交易日
        start -= timedelta(days=1)
    s_ts = start.timestamp()
    e_ts = (start + timedelta(days=1)).timestamp()
    pts = [(t, bars[t][3]) for t in keys if s_ts < t <= e_ts]
    base = None
    for t in reversed(keys):
        if t > s_ts:
            continue
        d = datetime.fromtimestamp(t, NY)
        m = d.hour * 60 + d.minute
        if 9 * 60 + 30 < m <= 16 * 60:
            base = bars[t][3]
            break
    return pts, s_ts, base


def candles(bars, minutes, n):
    """把 1 分钟 K 线 {ts: (o,h,l,c)} 合成 minutes 分钟 K 线，返回最后 n 根 [(ts,o,h,l,c)]。"""
    out = []
    span = minutes * 60
    for t in sorted(bars):
        o, h, l, c = bars[t]
        k = (t - 1) // span
        if out and out[-1][0] == k:
            _, t0, o0, h0, l0, _ = out[-1]
            out[-1] = (k, t, o0, max(h0, h), min(l0, l), c)
        else:
            out.append((k, t, o, h, l, c))
    return [x[1:] for x in out[-n:]]


def opend_up():
    try:
        with socket.create_connection((OPEND_HOST, OPEND_PORT), timeout=0.5):
            return True
    except OSError:
        return False


# ---------------- moomoo OpenD ----------------
class Feed:
    def __init__(self):
        self.ctx = None
        self.codes = list(CODES)
        self.bad = []
        self.bars = {s: {} for s in SYMBOLS}
        self.hist_t = 0.0

    def _call(self, fn, *a, **kw):
        """带 session=ALL（含夜盘）调用；旧版接口不支持该参数时自动去掉。"""
        if Session is not None:
            try:
                return fn(*a, session=Session.ALL, **kw)
            except TypeError:
                pass
        return fn(*a, **kw)

    def connect(self):
        if self.ctx:
            return
        ctx = OpenQuoteContext(host=OPEND_HOST, port=OPEND_PORT)
        subs = [SubType.QUOTE, SubType.K_1M]
        ret, err = self._call(ctx.subscribe, CODES, subs,
                              subscribe_push=False, extended_time=True)
        self.codes = list(CODES)
        if ret != RET_OK:
            # 有代码写错时逐只订阅，跳过无效的
            self.codes = [c for c in CODES
                          if self._call(ctx.subscribe, [c], subs, subscribe_push=False,
                                        extended_time=True)[0] == RET_OK]
            self.bad = [c.split(".", 1)[1] for c in CODES if c not in self.codes]
            if not self.codes:
                ctx.close()
                raise RuntimeError(f"订阅失败：{err}")
        self.ctx = ctx
        self.hist_t = 0.0

    def close(self):
        if self.ctx:
            try:
                self.ctx.close()
            except Exception:
                pass
            self.ctx = None

    def _merge(self, sym, df):
        if df is None or not len(df):
            return
        b = self.bars[sym]
        for tk, o, h, l, c in zip(df["time_key"], df["open"], df["high"], df["low"], df["close"]):
            try:
                o, h, l, c = float(o), float(h), float(l), float(c)
                if c == c and c > 0:
                    o = o if o == o and o > 0 else c
                    b[_ts(tk)] = (o, max(h, o, c), min(l if l > 0 else c, o, c), c)
            except (TypeError, ValueError):
                pass

    def _history(self):
        now = datetime.now(NY)
        start = (now - timedelta(days=4)).strftime("%Y-%m-%d")
        end = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        for code in self.codes:
            sym = code.split(".", 1)[1]
            key = None
            for _ in range(10):
                res = self._call(self.ctx.request_history_kline, code, start=start, end=end,
                                 ktype=KLType.K_1M, max_count=1000, page_req_key=key,
                                 extended_time=True)
                ret, df, key = res[0], res[1], res[2]
                if ret != RET_OK:
                    break
                self._merge(sym, df)
                if key is None:
                    break
        cutoff = time.time() - 5 * 86400
        for s in SYMBOLS:
            self.bars[s] = {t: p for t, p in self.bars[s].items() if t >= cutoff}

    def fetch(self):
        self.connect()
        if time.time() - self.hist_t > HISTORY_EVERY:
            try:
                self._history()
            except Exception:
                pass  # 历史补数失败不影响实时
            self.hist_t = time.time()
        for code in self.codes:
            sym = code.split(".", 1)[1]
            ret, kl = self.ctx.get_cur_kline(code, 1000, KLType.K_1M)
            if ret == RET_OK:
                self._merge(sym, kl)

        ret, q = self.ctx.get_stock_quote(self.codes)
        if ret != RET_OK:
            raise RuntimeError(f"报价获取失败：{q}")
        sess = session_now()
        out = {}
        for _, row in q.iterrows():
            sym = row["code"].split(".", 1)[1]
            price, prev = _num(row, "last_price"), _num(row, "prev_close_price")
            ext = None
            key = {"盘前": "pre", "盘后": "after", "夜盘": "overnight"}.get(sess)
            if key:
                ep = _num(row, f"{key}_price")
                er = _num(row, f"{key}_change_rate")
                if ep:
                    if er is None and price:
                        er = (ep / price - 1) * 100
                    ext = (sess, ep, er or 0.0)
            pts, start, base = build_day(self.bars.get(sym, {}))
            out[sym] = {"price": price, "prev": prev,
                        "pct": (price / prev - 1) * 100 if price and prev else None,
                        "ext": ext, "pts": pts, "start": start,
                        "baseline": base or prev, "bars": dict(self.bars.get(sym, {}))}
        return out, sess


# ---------------- 备用数据源：Yahoo 1 分钟（无夜盘） ----------------
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
try:
    import certifi
    SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    SSL_CTX = ssl.create_default_context()


def yahoo_fetch():
    out = {}
    for sym in SYMBOLS:
        try:
            out[sym] = _yahoo_one(sym)
        except Exception:
            pass  # 单只失败不影响其他
    if not out:
        raise RuntimeError("Yahoo 数据获取失败")
    return out


def _yahoo_one(sym):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
           f"?range=5d&interval=1m&includePrePost=true")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as r:
        res = json.load(r)["chart"]["result"][0]
    meta = res["meta"]
    q = (res.get("indicators", {}).get("quote") or [{}])[0]
    # Yahoo 时间戳是分钟开始，+60 秒对齐成分钟结束
    bars = {}
    for t, o, h, l, c in zip(res.get("timestamp") or [], q.get("open") or [],
                             q.get("high") or [], q.get("low") or [], q.get("close") or []):
        if c is None:
            continue
        o = o or c
        bars[t + 60] = (o, max(h or c, o, c), min(l or c, o, c), c)
    price = meta.get("regularMarketPrice")
    prev = meta.get("previousClose") or meta.get("chartPreviousClose")
    ext = None
    sess = session_now()
    if bars and price and sess in ("盘前", "盘后"):
        p_last = bars[max(bars)][3]
        ext = (sess, p_last, (p_last / price - 1) * 100)
    pts, start, base = build_day(bars)
    return {"price": price, "prev": prev,
            "pct": (price / prev - 1) * 100 if price and prev else None,
            "ext": ext, "pts": pts, "start": start, "baseline": base or prev,
            "bars": bars}


# ---------------- 点击跳转 moomoo ----------------
def open_in_moomoo(sym):
    """把 moomoo 切到前台，输入代码并回车，打开个股页（需要辅助功能权限）。"""
    script = ['-e', 'tell application "moomoo" to activate',
              '-e', 'delay 0.6',
              '-e', f'tell application "System Events" to keystroke "{sym}"',
              '-e', 'delay 1',
              '-e', 'tell application "System Events" to key code 36']
    import subprocess
    subprocess.Popen(["osascript"] + script, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)


# ---------------- 窗口 ----------------
class FloatWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(" / ".join(SYMBOLS))
        self.alpha = tk.DoubleVar(value=ALPHA)
        self.mode = tk.StringVar(value=DEFAULT_MODE)
        self.feed = Feed()
        self.data, self.sess = {}, ""
        self.status = "加载行情中…"
        self.updated = None
        self.busy = False
        self.source = ""
        self._yahoo_t = 0.0

        h = HEADER_H + ROW_H * len(SYMBOLS) + FOOTER_H + 4
        sw = self.root.winfo_screenwidth()
        self.root.geometry(f"{WIDTH}x{h}+{sw - WIDTH - 20}+40")
        self.root.configure(bg=BG)
        self.root.update_idletasks()
        self.root.overrideredirect(True)
        self._topmost()
        self._set_alpha()

        self.cv = tk.Canvas(self.root, width=WIDTH, height=h, bg=BG,
                            highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        self.h = h
        self.cv.bind("<ButtonPress-1>", self._press)
        self.cv.bind("<B1-Motion>", self._drag)
        self.cv.bind("<ButtonRelease-1>", self._release)
        self.cv.configure(cursor="hand2")
        for b in ("<Button-2>", "<Button-3>", "<Control-Button-1>"):
            self.cv.bind(b, self._menu)
        self.root.bind("<Escape>", lambda e: self.quit())

        self.menu = tk.Menu(self.root, tearoff=0)
        for val, lab in (("1", "1分钟 K 线"), ("5", "5分钟 K 线"), ("15", "15分钟 K 线"),
                         ("line", "24小时分时线")):
            self.menu.add_radiobutton(label=lab, variable=self.mode, value=val,
                                      command=self.draw)
        self.menu.add_separator()
        am = tk.Menu(self.menu, tearoff=0)
        for a in (1.0, 0.9, 0.8, 0.7, 0.6, 0.5):
            am.add_radiobutton(label=f"{int(a * 100)}%", variable=self.alpha, value=a,
                               command=self._set_alpha)
        self.menu.add_cascade(label="透明度", menu=am)
        self.menu.add_command(label="立即刷新", command=self.refresh)
        self.menu.add_separator()
        self.menu.add_command(label="退出", command=self.quit)

        self.draw()
        self._tick()
        self._keep_top()

    def _topmost(self):
        self.root.attributes("-topmost", True)
        self.root.lift()

    def _keep_top(self):
        self._topmost()
        self.root.geometry(f"{WIDTH}x{self.h}")
        self.root.after(3000, self._keep_top)

    def _set_alpha(self):
        try:
            self.root.attributes("-alpha", self.alpha.get())
        except tk.TclError:
            pass

    def _press(self, e):
        if e.x > WIDTH - 22 and e.y < HEADER_H:
            self.quit()
            return
        self._dx, self._dy = e.x, e.y
        self._moved = False

    def _drag(self, e):
        if abs(e.x - self._dx) > 3 or abs(e.y - self._dy) > 3:
            self._moved = True
        self.root.geometry(f"+{self.root.winfo_x() + e.x - self._dx}"
                           f"+{self.root.winfo_y() + e.y - self._dy}")

    def _release(self, e):
        """没拖动 = 点击：点哪一行就在 moomoo 打开哪只。"""
        if getattr(self, "_moved", True):
            return
        i = int((e.y - HEADER_H) // ROW_H)
        if e.y > HEADER_H and 0 <= i < len(SYMBOLS):
            open_in_moomoo(SYMBOLS[i])

    def _menu(self, e):
        try:
            self.menu.tk_popup(e.x_root, e.y_root)
        finally:
            self.menu.grab_release()

    def quit(self):
        threading.Thread(target=self.feed.close, daemon=True).start()
        self.root.destroy()

    # ---------- 数据 ----------
    def _tick(self):
        self.refresh()
        self.root.after(REFRESH_MS, self._tick)

    def refresh(self):
        if self.busy:
            return
        self.busy = True
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        out, sess, err = {}, session_now(), None
        if HAS_MOOMOO and opend_up():
            try:
                out, sess = self.feed.fetch()
                self.source = "moomoo 实时"
            except Exception as ex:
                self.feed.close()
                err = f"OpenD 取数失败：{str(ex)[:40]}"
        if not out:
            self.feed.close()
            if time.time() - self._yahoo_t < 15 and self.data:
                out = None
            else:
                try:
                    out = yahoo_fetch()
                    self._yahoo_t = time.time()
                    self.source = "Yahoo 1分钟（未连 OpenD，无夜盘）"
                    err = None
                except Exception as ex:
                    err = f"行情获取失败：{type(ex).__name__}"
                    out = {}
        try:
            self.root.after(0, self._done, out, sess, err)
        except RuntimeError:
            pass

    def _done(self, out, sess, err):
        self.busy = False
        if out is None:
            return
        if out:
            self.data.update(out)
            self.sess = sess
            self.updated = datetime.now()
        self.status = err or ""
        self.draw()

    # ---------- 绘制 ----------
    def draw(self):
        cv = self.cv
        cv.delete("all")
        cv.create_rectangle(0, 0, WIDTH, self.h, fill=BG, outline="")
        t = self.updated.strftime("%H:%M:%S") if self.updated else "--:--:--"
        mode = self.mode.get()
        mlabel = "24h分时" if mode == "line" else f"{mode}分K"
        header = self.status or f"{self.source} · {mlabel} · {self.sess} · {t}"
        cv.create_text(8, HEADER_H / 2, text=header, anchor="w",
                       fill=RED if self.status and self.updated is None else DIM,
                       font=("Helvetica", 10))
        cv.create_text(WIDTH - 11, HEADER_H / 2, text="×", fill=DIM,
                       font=("Helvetica", 13))

        x0, x1 = CHART_X0, WIDTH - 10
        for i, s in enumerate(SYMBOLS):
            y0 = HEADER_H + i * ROW_H
            if i:
                cv.create_line(12, y0, WIDTH - 12, y0, fill=GRID)
            d = self.data.get(s)
            cv.create_text(10, y0 + 15, text=s, anchor="w", fill=FG,
                           font=("Helvetica", 13, "bold"))
            if not d or d["price"] is None:
                bad = s in getattr(self.feed, "bad", [])
                cv.create_text(10, y0 + 38, text="代码无效，请检查 config.json" if bad else "—",
                               anchor="w", fill=RED if bad else DIM,
                               font=("Helvetica", 11 if bad else 12))
                continue
            pct = d["pct"] or 0.0
            col = UP_C if pct >= 0 else DOWN_C
            cv.create_text(10, y0 + 37, text=f"{d['price']:.2f}", anchor="w",
                           fill=col, font=("Helvetica", 17, "bold"))
            cv.create_text(70, y0 + 15, text=f"{pct:+.2f}%", anchor="w",
                           fill=col, font=("Helvetica", 11, "bold"))
            if d["ext"]:
                lab, p, ep = d["ext"]
                cv.create_text(10, y0 + 58, text=f"{lab} {p:.2f} {ep:+.2f}%",
                               anchor="w", fill=UP_C if ep >= 0 else DOWN_C,
                               font=("Helvetica", 9))
            if mode == "line":
                self._spark(d, x0, y0 + 6, x1, y0 + ROW_H - 6)
            else:
                self._candles(d, int(mode), x0, y0 + 6, x1, y0 + ROW_H - 6)

        fy = HEADER_H + ROW_H * len(SYMBOLS) + FOOTER_H / 2
        if mode != "line":
            span = getattr(self, "_span", None)
            if span:
                cv.create_text(x0, fy, text=span[0], anchor="w", fill=DIM, font=("Helvetica", 8))
                cv.create_text(x1 - 34, fy, text=span[1], anchor="e", fill=DIM,
                               font=("Helvetica", 8))
            return
        # 时段标签
        edges = [0.0] + [h for h, _ in SEPS] + [24.0]
        names = ["夜盘"] + [n for _, n in SEPS]
        for a, b, n in zip(edges, edges[1:], names):
            xm = x0 + (x1 - x0) * (a + b) / 2 / 24
            cv.create_text(xm, fy, text=n, fill=DIM, font=("Helvetica", 8))

    def _candles(self, d, minutes, x0, y0, x1, y1):
        cv = self.cv
        x1 -= 34  # 右侧留给价格刻度
        n = max(10, int((x1 - x0) // CANDLE_W))
        ks = candles(d.get("bars") or {}, minutes, n)
        if len(ks) < 2:
            cv.create_text((x0 + x1) / 2, (y0 + y1) / 2, text="暂无K线数据",
                           fill=DIM, font=("Helvetica", 9))
            return
        lo = min(k[3] for k in ks)
        hi = max(k[2] for k in ks)
        if hi == lo:
            hi, lo = hi + 0.01, lo - 0.01
        fy = lambda v: y1 - (y1 - y0) * (v - lo) / (hi - lo)
        step = (x1 - x0) / n
        bw = max(1.0, step * 0.7)
        off = (n - len(ks)) * step  # 根数不够时靠右对齐
        for i, (t, o, h, l, c) in enumerate(ks):
            xc = x0 + off + step * (i + 0.5)
            col = UP_C if c >= o else DOWN_C
            cv.create_line(xc, fy(h), xc, fy(l), fill=col)
            yt, yb = fy(max(o, c)), fy(min(o, c))
            if yb - yt < 1:
                yb = yt + 1
            cv.create_rectangle(xc - bw / 2, yt, xc + bw / 2, yb, fill=col, outline=col)
        last = ks[-1][4]
        yl = fy(last)
        lcol = UP_C if last >= ks[-1][1] else DOWN_C
        cv.create_line(x0, yl, x1, yl, fill=lcol, dash=(1, 3))
        cv.create_text(x1 + 34, yl, text=f"{last:.2f}", anchor="e", fill=lcol,
                       font=("Helvetica", 8, "bold"))
        cv.create_text(x1 + 34, y0, text=f"{hi:.2f}", anchor="ne", fill=DIM,
                       font=("Helvetica", 8))
        cv.create_text(x1 + 34, y1, text=f"{lo:.2f}", anchor="se", fill=DIM,
                       font=("Helvetica", 8))
        f = lambda ts: datetime.fromtimestamp(ts - minutes * 60, NY).strftime("%m-%d %H:%M")
        self._span = (f"美东 {f(ks[0][0])}", f(ks[-1][0]))

    def _spark(self, d, x0, y0, x1, y1):
        pts, base, start = d["pts"], d["baseline"], d.get("start")
        for h, _ in SEPS:
            xs = x0 + (x1 - x0) * h / 24
            self.cv.create_line(xs, y0, xs, y1, fill=GRID)
        if len(pts) < 2 or start is None:
            self.cv.create_text((x0 + x1) / 2, (y0 + y1) / 2, text="暂无分时数据",
                                fill=DIM, font=("Helvetica", 9))
            return
        vals = [p for _, p in pts]
        lo, hi = min(vals), max(vals)
        if base:
            lo, hi = min(lo, base), max(hi, base)
        if hi == lo:
            hi, lo = hi + 0.01, lo - 0.01
        span = 86400.0
        fx = lambda t: x0 + (x1 - x0) * min(max((t - start) / span, 0), 1)
        fy = lambda v: y1 - (y1 - y0) * (v - lo) / (hi - lo)
        col = UP_C if vals[-1] >= (base or vals[0]) else DOWN_C
        if base:
            self.cv.create_line(x0, fy(base), x1, fy(base), fill=DIM, dash=(2, 3))
        coords = []
        for t, v in pts:
            coords += [fx(t), fy(v)]
        self.cv.create_polygon([coords[0], y1] + coords + [coords[-2], y1], fill=col,
                               outline="", stipple="gray25")
        self.cv.create_line(coords, fill=col, width=1.2)
        self.cv.create_oval(coords[-2] - 2, coords[-1] - 2, coords[-2] + 2,
                            coords[-1] + 2, fill=col, outline="")
        self.cv.create_text(x1, y0, text=f"{hi:.2f}", anchor="ne", fill=DIM,
                            font=("Helvetica", 8))
        self.cv.create_text(x1, y1, text=f"{lo:.2f}", anchor="se", fill=DIM,
                            font=("Helvetica", 8))

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    FloatWindow().run()
