#!/bin/bash

echo "============================================================"
echo "                   MockClaw Startup"
echo "============================================================"
echo ""

cd "$(dirname "$0")"

echo "[1/1] Starting Backend (Brain API)..."
osascript -e 'tell application "Terminal" to do script "cd '$(pwd)' && python src/brain.py"'
sleep 2

echo ""
echo "============================================================"
echo " Service Started!"
echo " Backend:  http://localhost:8000"
echo " API Docs: http://localhost:8000/docs"
echo "============================================================"
echo ""

open http://localhost:8000/docs
