#!/bin/bash
# 在后台启动浮窗（启动后可以关闭终端）
#   ./scripts/start.sh               使用 config.json
#   ./scripts/start.sh soxl-soxs     使用 presets/soxl-soxs.json
DIR="$(cd "$(dirname "$0")/.." && pwd)"
PRESET="$1"
if [ -n "$PRESET" ]; then
  [ -f "$DIR/presets/$PRESET.json" ] || { echo "找不到预设：presets/$PRESET.json"; exit 1; }
  ARGS=(--preset "$PRESET")
  pkill -f "stock_float.py --preset $PRESET" 2>/dev/null
else
  ARGS=()
  pkill -f "stock_float.py$" 2>/dev/null
fi
nohup "${PYTHON:-python3}" "$DIR/stock_float.py" "${ARGS[@]}" >/dev/null 2>&1 & disown
echo "浮窗已启动${PRESET:+（预设：$PRESET）}"
