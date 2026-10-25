#!/usr/bin/env bash
# Play the test end to end in headless Chrome (site/assets/selftest.js drives the real UI).
#   scripts/e2e.sh                 # serve dist/ locally and test it
#   scripts/e2e.sh https://host/x/ # test a live site
set -euo pipefail
CHROME="${CHROME:-$(command -v google-chrome || command -v chromium || command -v chromium-browser || echo "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")}"
base="${1:-}"
if [ -z "$base" ]; then
  port="${PORT:-8765}"
  # Find a free port, so a leftover server from another run can't answer for this one.
  while (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; do port=$((port + 1)); done
  python3 -m http.server "$port" --bind 127.0.0.1 --directory dist >/dev/null 2>&1 &
  srv=$!
  trap 'kill $srv 2>/dev/null || true' EXIT
  for _ in $(seq 1 50); do curl -s -o /dev/null "http://127.0.0.1:$port/" && break; sleep 0.1; done
  base="http://127.0.0.1:$port/"
fi
profile="$(mktemp -d)"
fail=0
for path in "" "scams/toll-text/" "scams/jury-duty/" "embed/"; do
  out="$("$CHROME" --headless=new --disable-gpu --no-sandbox --no-first-run --no-default-browser-check \
    --user-data-dir="$profile" --virtual-time-budget=30000 --dump-dom "${base}${path}?selftest=1" 2>/dev/null || true)"
  status="$(printf '%s' "$out" | grep -o 'data-selftest="[^"]*"' | head -1 || true)"
  echo "/${path}: ${status:-no result}"
  printf '%s\n' "$out" | sed -n '/<pre id="selftest">/,/<\/pre>/p' | sed 's/<[^>]*>//g' | sed 's/^/    /' | head -16
  case "$status" in *'"pass"'*) ;; *) fail=1 ;; esac
done
rm -rf "$profile"
exit "$fail"
