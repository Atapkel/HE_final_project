#!/usr/bin/env bash
# Starts Lesson Ready with a free public link, so phones on ANY network can join (mobile data, uni Wi-Fi).
# Usage: ./share.sh        (Ctrl+C stops both the app and the link)
set -u
cd "$(dirname "$0")"
PORT="${PORT:-5000}"

if ! grep -qE '^CLAUDE_API=.+' .env 2>/dev/null && [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "Please put your Claude API key in the .env file:  CLAUDE_API=sk-ant-..." ; exit 1
fi
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
[ -f lessons.db ] || .venv/bin/python seed.py

# cloudflared: free "quick tunnel", no account needed
CF="$(command -v cloudflared || true)"
if [ -z "$CF" ]; then
  CF="bin/cloudflared"
  if [ ! -x "$CF" ]; then
    case "$(uname -s)-$(uname -m)" in
      Linux-x86_64)  ASSET=cloudflared-linux-amd64 ;;
      Linux-aarch64|Linux-arm64) ASSET=cloudflared-linux-arm64 ;;
      Darwin-*) echo "On macOS run:  brew install cloudflared   then run ./share.sh again"; exit 1 ;;
      *) echo "Please install cloudflared: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"; exit 1 ;;
    esac
    echo "Downloading cloudflared (one time)…"
    mkdir -p bin
    curl -fsSL -o "$CF" "https://github.com/cloudflare/cloudflared/releases/latest/download/$ASSET" || { echo "Download failed."; exit 1; }
    chmod +x "$CF"
  fi
fi

rm -f .public_url
PORT="$PORT" .venv/bin/python app.py > .app.log 2>&1 &
APP=$!
"$CF" tunnel --no-autoupdate --url "http://localhost:$PORT" > .tunnel.log 2>&1 &
TUN=$!
cleanup() { kill "$APP" "$TUN" 2>/dev/null; rm -f .public_url; echo; echo "Stopped."; }
trap cleanup EXIT INT TERM

URL=""
for _ in $(seq 1 45); do
  URL="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' .tunnel.log | head -1)"
  [ -n "$URL" ] && break
  sleep 1
done
if [ -z "$URL" ]; then
  echo "Could not create a public link (see .tunnel.log). The app still runs at http://localhost:$PORT"
  wait "$APP"; exit 1
fi
echo "$URL" > .public_url

echo
echo "  Lesson Ready is online"
echo "  Teacher (this laptop):  $URL/teacher      (or http://localhost:$PORT)"
echo "  Students (any phone):   $URL/join"
echo "  The QR code on each lesson page already uses this link. Wait ~10 s before the first scan."
echo
.venv/bin/python -c "import segno,sys; segno.make(sys.argv[1] + '/join').terminal(compact=True)" "$URL" 2>/dev/null
echo "  Press Ctrl+C to stop."
wait "$APP"
