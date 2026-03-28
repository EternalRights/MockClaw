#!/bin/bash

echo "============================================================"
echo "                   MockClaw Startup"
echo "============================================================"
echo ""

cd "$(dirname "$0")"

echo "[1/2] Starting Backend (Brain API)..."
osascript -e 'tell application "Terminal" to do script "cd '$(pwd)' && python src/brain.py"'
sleep 2

echo "[2/2] Starting Frontend (Next.js)..."
osascript -e 'tell application "Terminal" to do script "cd '$(pwd)'/web && npm run dev"'
sleep 3

echo ""
echo "============================================================"
echo " Services Started!"
echo " Backend:  http://localhost:8000"
echo " Frontend: http://localhost:3000"
echo "============================================================"
echo ""

# Open browser
open http://localhost:3000
