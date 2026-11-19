# moomoo 美股置顶行情浮窗（macOS）

一个始终显示在屏幕最上层的小浮窗，实时显示**任意几只美股 / ETF** 的价格、涨跌幅、盘前/盘后/夜盘价格和 **1 分钟 K 线**。数据来自 **moomoo OpenD**，包括美股 24 小时交易（含夜盘）。

要看哪些股票，改一下 `config.json` 就行。项目还自带一个 **SOXL / SOXS 预设**（半导体 3 倍多空 ETF），一条命令就能用。

<!-- 在这里放一张截图：![screenshot](docs/screenshot.png) -->

## 项目结构：通用版与 SOXL / SOXS 版的关系

这个项目最早是一个只看 SOXL / SOXS 的浮窗（**SOXL / SOXS Float**），后来改成了能看任意美股的通用版（**moomoo Stock Float**）。两者现在是同一套代码：

> **SOXL / SOXS Float = moomoo Stock Float + `soxl-soxs` 预设**

```
moomoo-stock-float/
├── stock_float.py           ← 通用程序（唯一的代码，两种用法共用）
├── config.json              ← 通用版的默认配置：自己想看的股票（示例 SPY / QQQ / NVDA）
├── presets/
│   ├── README.md            ← 预设说明
│   └── soxl-soxs.json       ← SOXL / SOXS 版 = 这一份配置
├── scripts/
│   ├── start.sh             ← 启动：不带参数 = 通用版；带 soxl-soxs = SOXL / SOXS 版
│   ├── install_autostart.sh ← 开机自动启动（同样可带预设名）
│   └── uninstall_autostart.sh
├── requirements.txt
├── LICENSE
└── README.md
```

| | 通用版 moomoo Stock Float | SOXL / SOXS 版（预设） |
|---|---|---|
| 代码 | `stock_float.py` | 同一个 `stock_float.py` |
| 读哪份配置 | `config.json` | `presets/soxl-soxs.json` |
| 显示的股票 | 你在 `config.json` 里写的 | 固定为 SOXL、SOXS |
| 启动 | `./scripts/start.sh` | `./scripts/start.sh soxl-soxs` |
| 开机自启 | `./scripts/install_autostart.sh` | `./scripts/install_autostart.sh soxl-soxs` |
| 适合谁 | 想自定义盯盘列表的人 | 专门做半导体 3 倍多空的人，开箱即用 |

- 两者可以同时运行，各自是一个独立的浮窗。
- 修 bug 或加功能只需要改 `stock_float.py`，两种用法同时生效。
- 想做第三个版本（比如 AI 股），不用复制代码，只要在 `presets/` 里加一个 json。

## 为什么做这个：解决的痛点

在 Mac 上用 moomoo 自带的桌面小组件盯盘，有三个不方便的地方：

| 痛点 | moomoo 桌面小组件 | 本浮窗 |
|---|---|---|
| **看不到走势图** | 只显示价格和涨跌幅，看不出这一段是在拉升、下跌还是横盘 | 直接显示 1 / 5 / 15 分钟 K 线，或 24 小时分时线（含夜盘） |
| **点击跳错地方** | 点击小组件常常跳到 iPhone 镜像（手机投屏）界面，而不是 Mac 上的 moomoo | 单击哪一行，就在 Mac 版 moomoo 打开哪只股票 |
| **被窗口挡住** | 小组件固定在桌面层，一打开别的窗口就被盖住，只能回到桌面才看得到 | 始终显示在所有窗口最上层，可以拖到任意位置，透明度可调，干别的事时也能顺便盯盘 |

## 功能

- **自选股票**：在 `config.json` 里写要看的代码，浮窗按数量自动调整高度。
- **置顶显示**：无边框、半透明的浅蓝色卡片，可以拖到屏幕任意位置。
- **实时行情**：通过 moomoo OpenD 每 2 秒刷新一次。
- **图表**：右键可切换四种图表：
  - 1 分钟 K 线（默认，显示最近约 70 根）
  - 5 分钟 K 线
  - 15 分钟 K 线
  - 24 小时分时线：横轴是美东 20:00 → 次日 20:00，依次是夜盘、盘前、盘中、盘后
- **盘前 / 盘后 / 夜盘价格**：在对应时段会单独显示。
- **点击跳转**：单击某一行，会在 moomoo 桌面版打开这只股票的页面。
- **自动备用数据源**：没检测到 OpenD 时，自动改用 Yahoo 1 分钟数据（没有夜盘）。OpenD 一启动就自动切回来。
- **只用一个依赖**：除了 moomoo-api，其余都是 Python 标准库（界面用 Tkinter）。

## 环境要求

- macOS
- Python 3.9 及以上，需要带 Tkinter（推荐 Anaconda / Miniconda 或 python.org 的安装包）
- [moomoo OpenD](https://www.moomoo.com/download/OpenAPI)：安装并用你的 moomoo 账号登录，默认端口 `11111`
- 你的 moomoo 账号需要有美股行情权限。要实时数据，需要 LV1 或以上的实时权限。

## 安装与运行

```bash
git clone https://github.com/cindyonly12/moomoo-stock-float.git
cd moomoo-stock-float
python3 -m pip install -r requirements.txt

# 前台运行（关闭终端，浮窗也会关闭）
python3 stock_float.py

# 或者在后台运行（启动后可以关闭终端）
./scripts/start.sh

# 使用 SOXL / SOXS 预设
./scripts/start.sh soxl-soxs
```

### 开机自动启动

```bash
./scripts/install_autostart.sh               # 设置登录后自动启动（使用 config.json），并立即启动一次
./scripts/uninstall_autostart.sh             # 取消自动启动，并关闭浮窗

./scripts/install_autostart.sh soxl-soxs     # 用 SOXL / SOXS 预设开机自动启动
./scripts/uninstall_autostart.sh soxl-soxs   # 取消该预设的自动启动
```

默认配置和各个预设可以同时开机启动，各自显示一个浮窗。

建议同时把 moomoo OpenD 加入「系统设置 → 通用 → 登录项」，并在 OpenD 里勾选自动登录。

## 操作

| 操作 | 效果 |
|---|---|
| 单击某只股票那一行 | 在 moomoo 打开该股票 |
| 左键拖动 | 移动浮窗 |
| 右键（或 Control + 点击） | 菜单：切换图表、调透明度、立即刷新、退出 |
| Esc 或右上角 × | 关闭浮窗 |

### 「点击跳转」需要辅助功能权限

moomoo 桌面版没有公开打开个股页的链接，所以这里的做法是：把 moomoo 切到前台，模拟键盘输入股票代码，再按回车。

第一次点击时，macOS 会请求权限。请到「系统设置 → 隐私与安全性 → 辅助功能」，打开**终端**（或 **python3**）的开关。

如果点击时开着中文输入法，代码可能会被当成拼音输入。切到英文输入法就好。

## 切换股票 / 自定义：`config.json`

默认设置在项目根目录的 `config.json` 里（示例是 SPY / QQQ / NVDA）。改完保存，重启浮窗生效（运行 `./scripts/start.sh` 会自动关掉旧的再打开新的）。

```json
{
  "symbols": ["SOXL", "SOXS", "NVDA", "TQQQ"],
  "refresh_ms": 2000,
  "default_mode": "1",
  "red_up": false,
  "alpha": 0.86,
  "candle_width": 5,
  "opend_host": "127.0.0.1",
  "opend_port": 11111
}
```

| 字段 | 说明 | 默认值 |
|---|---|---|
| `symbols` | 要显示的美股 / ETF 代码，按顺序从上到下排列。写 `"NVDA"` 或 `"US.NVDA"` 都可以，大小写不限，重复的会自动去掉 | `["SOXL", "SOXS"]` |
| `refresh_ms` | 刷新间隔（毫秒） | `2000` |
| `default_mode` | 默认图表：`"1"` / `"5"` / `"15"` = 对应分钟 K 线，`"line"` = 24 小时分时线 | `"1"` |
| `red_up` | `true` = 红涨绿跌，`false` = 绿涨红跌 | `false` |
| `alpha` | 不透明度（0.3–1.0） | `0.86` |
| `candle_width` | 每根 K 线的宽度（像素），越小显示的根数越多 | `5` |
| `opend_host` / `opend_port` | OpenD 地址 | `127.0.0.1` / `11111` |

- 每个字段都可以省略，省略的用默认值。没有 `config.json` 时，全部用默认值。
- 代码写错时，那一行会显示"代码无效，请检查 config.json"，其他股票照常显示。
- 每只股票占一行，大约 90 像素高。建议不超过 5–6 只，否则浮窗会超出屏幕。
- 目前只支持美股 / 美股 ETF：盘前、盘后、夜盘和 24 小时分时都是按美东时间设计的。

### 预设（presets）

预设就是放在 `presets/` 目录里的另一份配置文件，格式和 `config.json` 完全一样。用 `--preset 名称` 启动时，读取 `presets/名称.json`。

| 预设 | 内容 | 启动命令 |
|---|---|---|
| `soxl-soxs` | SOXL / SOXS 半导体 3 倍多空 ETF，适合同时盯多空两边 | `./scripts/start.sh soxl-soxs` |

自己做一个预设：复制 `presets/soxl-soxs.json`，改个文件名（比如 `presets/ai.json`），把 `symbols` 改成你要的代码，再运行 `./scripts/start.sh ai`。

也可以直接指定任意配置文件：`python3 stock_float.py --config ~/my-watch.json`

## 工作原理

1. 程序启动时读取配置（`config.json`，或 `--preset` / `--config` 指定的文件），再检测本机 `127.0.0.1:11111` 是否有 OpenD 在运行。
2. 有 OpenD 时，订阅报价和 1 分钟 K 线，包含夜盘在内的全部时段：
   - 每 5 分钟用 `request_history_kline` 补一次最近几天的分钟线；
   - 每次刷新用 `get_cur_kline` 取最新数据。
3. 5 分钟、15 分钟 K 线都由 1 分钟 K 线在本地合成。
4. 没有 OpenD 时，改用 Yahoo Finance 的公开 1 分钟数据，每 15 秒刷新一次。

## 免责声明

本项目只用于个人学习和看盘辅助，**不构成任何投资建议**。行情数据来自 moomoo OpenAPI 和 Yahoo Finance，可能有延迟或错误，请以券商官方数据为准。使用 moomoo OpenAPI 时，请遵守 moomoo 的相关条款。默认示例中的 SOXL / SOXS 是 3 倍杠杆 ETF，风险很高。

本项目与 moomoo、Futu、Direxion 和 Yahoo 均无关联。

## License

[MIT](LICENSE)
