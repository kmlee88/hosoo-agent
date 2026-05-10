#!/bin/zsh
set -euo pipefail

ROOT_DIR="/Users/sabri/Documents/New project"
LABEL="com.hosoo.reservation-collector"
PLIST_SRC="$ROOT_DIR/launchd/$LABEL.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
SUPPORT_DIR="$HOME/Library/Application Support/HosooAgent"
RUNNER_DEST="$SUPPORT_DIR/auto_collect_reservations.sh"

mkdir -p "$HOME/Library/LaunchAgents" "$SUPPORT_DIR" "$ROOT_DIR/logs"
chmod +x "$ROOT_DIR/scripts/auto_collect_reservations.sh"
cp "$ROOT_DIR/scripts/auto_collect_reservations.sh" "$RUNNER_DEST"
chmod +x "$RUNNER_DEST"
cp "$PLIST_SRC" "$PLIST_DEST"

launchctl bootout "gui/$(id -u)" "$PLIST_DEST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_DEST"
launchctl enable "gui/$(id -u)/$LABEL"

echo "예약 자동 수집을 등록했습니다."
echo "- 매시 정각 실행"
echo "- 23:50 최종 수집 실행"
echo "- 로그: $ROOT_DIR/logs/reservation-collector.log"
echo ""
echo "바로 테스트하려면:"
echo "launchctl kickstart -k gui/$(id -u)/$LABEL"
