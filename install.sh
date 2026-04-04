#!/usr/bin/env bash
set -e

echo "🚀 MockClaw Quick Install"
echo "========================"
echo ""

PYTHON_CMD=""

if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "❌ Error: Python not found"
    echo "Please install Python 3.11 or higher and try again"
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
echo "✅ Found Python: $PYTHON_VERSION"

MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 11 ]); then
    echo "❌ Error: MockClaw requires Python 3.11 or higher"
    echo "Current version: $PYTHON_VERSION"
    exit 1
fi

echo ""
echo "📦 Setting up virtual environment..."

if [ -d "venv" ]; then
    echo "⚠️  Virtual environment already exists"
    read -p "Remove and recreate? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf venv
    else
        echo "Using existing virtual environment"
    fi
fi

if [ ! -d "venv" ]; then
    $PYTHON_CMD -m venv venv
    echo "✅ Virtual environment created"
fi

echo ""
echo "📥 Installing dependencies..."

source venv/bin/activate

pip install --upgrade pip -q
pip install -r src/requirements.txt -q

echo "✅ Dependencies installed"

echo ""
echo "🔧 Installing MockClaw..."

pip install -e . -q

echo "✅ MockClaw installed"

echo ""
echo "✨ Installation complete!"
echo ""
echo "Quick Start:"
echo "  1. Activate environment:  source venv/bin/activate"
echo "  2. Try quick example:     mockclaw example"
echo "  3. View documentation:    mockclaw --help"
echo ""
echo "Or run directly:"
echo "  ./venv/bin/mockclaw example"
echo ""
