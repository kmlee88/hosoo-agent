#!/bin/zsh
set -u

ROOT_DIR="/Users/sabri/Documents/New project"
LOG_DIR="$ROOT_DIR/logs"
LOCK_DIR="/tmp/hosoo-reservation-collector.lock"
CDP_URL="http://127.0.0.1:9222/json/version"

mkdir -p "$LOG_DIR"
exec >> "$LOG_DIR/reservation-collector.log" 2>&1

echo ""
echo "===== $(date '+%Y-%m-%d %H:%M:%S %Z') reservation collection start ====="

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "Another reservation collection is already running. Skipping."
  exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

cd "$ROOT_DIR" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export RESERVATION_BROWSER_MODE="cdp"
export RESERVATION_CDP_URL="http://127.0.0.1:9222"

if ! curl -fsS --max-time 2 "$CDP_URL" >/dev/null; then
  echo "Chrome CDP is not ready. Trying to open reservation Chrome."
  .venv/bin/python scripts/start_reservation_chrome.py || true
  sleep 5
fi

if ! curl -fsS --max-time 2 "$CDP_URL" >/dev/null; then
  echo "Chrome CDP is still unavailable. Check Chrome window, Naver login, and macOS privacy/security permissions."
  exit 2
fi

if ! .venv/bin/python scripts/collect_reservations.py --browser-mode cdp --backfill-previous; then
  echo "Reservation collection failed."
  exit 3
fi

git add snapshots/reservations-*.json web/reservation-latest.json web/reservation-previous.json 2>/dev/null || true

if git diff --cached --quiet; then
  echo "No reservation snapshot changes to commit."
else
  git commit -m "Auto update reservation snapshot $(date '+%Y-%m-%d %H:%M')" || exit 4
  git push origin main || exit 5
fi

echo "===== $(date '+%Y-%m-%d %H:%M:%S %Z') reservation collection done ====="
