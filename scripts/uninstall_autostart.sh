#!/bin/bash
# 取消开机自动启动，并关闭对应的浮窗
#   ./scripts/uninstall_autostart.sh               对应 config.json
#   ./scripts/uninstall_autostart.sh soxl-soxs     对应 presets/soxl-soxs.json
PRESET="$1"
LABEL="com.github.moomoo-stock-float${PRESET:+.$PRESET}"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
launchctl unload "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
if [ -n "$PRESET" ]; then
  pkill -f "stock_float.py --preset $PRESET" 2>/dev/null
else
  pkill -f "stock_float.py$" 2>/dev/null
fi
echo "已取消开机自动启动${PRESET:+（预设：$PRESET）}"
