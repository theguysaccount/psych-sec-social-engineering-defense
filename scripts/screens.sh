#!/usr/bin/env bash
# Screenshots of the key screens at desktop (1280px) and phone (390px) widths -> docs/screens/.
# Phone shots load the page in a 390px iframe, because desktop Chrome won't shrink a window that far.
#   scripts/screens.sh               # from dist/, served locally
#   scripts/screens.sh https://host/x/
set -euo pipefail
CHROME="${CHROME:-$(command -v google-chrome || command -v chromium || echo "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")}"
base="${1:-}"
port="${PORT:-8767}"
work="$(mktemp -d)"
python3 -m http.server "$port" --bind 127.0.0.1 --directory "$work" >/dev/null 2>&1 &
wrapsrv=$!
trap 'kill $wrapsrv ${srv:-} 2>/dev/null || true; rm -rf "$work"' EXIT
if [ -z "$base" ]; then
  python3 -m http.server $((port + 1)) --bind 127.0.0.1 --directory dist >/dev/null 2>&1 &
  srv=$!
  base="http://127.0.0.1:$((port + 1))/"
fi
sleep 1
mkdir -p docs/screens
shot() { # name page width height
  local name="$1" page="$2" width="$3" height="$4" url="${base}$2"
  if [ "$width" -lt 600 ]; then
    printf '<!doctype html><body style="margin:0"><iframe src="%s" style="border:0;width:%spx;height:%spx"></iframe>' "$url" "$width" "$height" > "$work/$name.html"
    url="http://127.0.0.1:$port/$name.html"
  fi
  "$CHROME" --headless=new --disable-gpu --no-first-run --no-default-browser-check --hide-scrollbars \
    --user-data-dir="$work/profile" --window-size="$width,$height" --virtual-time-budget=8000 \
    --screenshot="docs/screens/$name.png" "$url" >/dev/null 2>&1
  echo "docs/screens/$name.png"
}
shot home-desktop "" 1280 1500
shot home-phone "" 390 1700
shot question-desktop "?demo=0" 1280 1400
shot question-phone "?demo=0" 390 1500
shot feedback-phone "?demo=1" 390 2100
shot results-phone "?demo=end" 390 2400
shot lesson-desktop "scams/toll-text/" 1280 2600
shot lesson-phone "scams/toll-text/" 390 3000
