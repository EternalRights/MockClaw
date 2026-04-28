#!/bin/bash

echo "============================================================"
echo "                   MockClaw Startup"
echo "============================================================"
echo ""

cd "$(dirname "$0")"

echo "[1/1] Starting Backend (Brain API)..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    osascript -e 'tell application "Terminal" to do script "cd '"$(pwd)"' && python src/brain.py"'
else
    python src/brain.py &
fi
sleep 2

echo ""
echo "============================================================"
echo " Service Started!"
echo " Backend:  http://localhost:8000"
echo " API Docs: http://localhost:8000/docs"
echo "============================================================"
echo ""

if command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:8000/docs
elif [[ "$OSTYPE" == "darwin"* ]]; then
    open http://localhost:8000/docs
fi
