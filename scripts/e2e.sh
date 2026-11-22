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
# Retries (added 2026-11-22). GitHub Pages now and then answers a single request with a 5xx; one 503
# failed LifeClock's self-test on 2026-11-17. On a live site, a page that hasn't passed is loaded
# again after 10, 20 and 30 seconds before it counts as failed, with at most four retries per run,
# so a site that is really down still fails within minutes. Local runs (no URL given) keep one try:
# a failure there is a real bug. The Chrome command is the loop's own.
retries_left=0
if [ -n "${1:-}" ]; then retries_left=4; fi
retry_unless_passed() {  # retry_unless_passed <url>: reload <url> into $out until it passes
  local pause
  for pause in 10 20 30; do
    case "$(printf '%s' "$out" | grep -o 'data-selftest="[^"]*"' | head -1 || true)" in *'"pass"'*) return 0 ;; esac
    [ "$retries_left" -gt 0 ] || return 0
    retries_left=$((retries_left - 1))
    echo "::warning::${1%%#*} didn't pass; loading it again in ${pause}s"
    sleep "$pause"
    out="$("$CHROME" --headless=new --disable-gpu --no-sandbox --no-first-run --no-default-browser-check \
      --user-data-dir="$profile" --virtual-time-budget=30000 --dump-dom "$1" 2>/dev/null || true)"
  done
}
for path in "" "scams/toll-text/" "scams/jury-duty/" "embed/"; do
  out="$("$CHROME" --headless=new --disable-gpu --no-sandbox --no-first-run --no-default-browser-check \
    --user-data-dir="$profile" --virtual-time-budget=30000 --dump-dom "${base}${path}?selftest=1" 2>/dev/null || true)"
  retry_unless_passed "${base}${path}?selftest=1"
  status="$(printf '%s' "$out" | grep -o 'data-selftest="[^"]*"' | head -1 || true)"
  echo "/${path}: ${status:-no result}"
  printf '%s\n' "$out" | sed -n '/<pre id="selftest">/,/<\/pre>/p' | sed 's/<[^>]*>//g' | sed 's/^/    /' | head -16
  case "$status" in *'"pass"'*) ;; *) fail=1 ;; esac
done
rm -rf "$profile"
exit "$fail"
