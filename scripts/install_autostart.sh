#!/bin/bash
# 设置登录后自动启动浮窗，并立即启动一次
#   ./scripts/install_autostart.sh               使用 config.json
#   ./scripts/install_autostart.sh soxl-soxs     使用 presets/soxl-soxs.json
set -e
DIR="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-$(command -v python3)}"
PRESET="$1"
LABEL="com.github.moomoo-stock-float${PRESET:+.$PRESET}"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
EXTRA=""
if [ -n "$PRESET" ]; then
  [ -f "$DIR/presets/$PRESET.json" ] || { echo "找不到预设：presets/$PRESET.json"; exit 1; }
  EXTRA="<string>--preset</string><string>$PRESET</string>"
fi

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>$LABEL</string>
<key>ProgramArguments</key><array><string>$PY</string><string>$DIR/stock_float.py</string>$EXTRA</array>
<key>RunAtLoad</key><true/>
</dict></plist>
PL
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "已设置开机自动启动：$PLIST"
