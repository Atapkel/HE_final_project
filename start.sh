#!/usr/bin/env bash
# Starts Lesson Ready. Usage: ./start.sh   (put CLAUDE_API=sk-ant-... in .env first)
cd "$(dirname "$0")"
if ! grep -qE '^CLAUDE_API=.+' .env 2>/dev/null && [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "Please put your Claude API key in the .env file:  CLAUDE_API=sk-ant-..." ; exit 1
fi
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
echo "Open http://localhost:5000 (students on the same Wi-Fi: http://<this-computer-IP>:5000)"
.venv/bin/python app.py
