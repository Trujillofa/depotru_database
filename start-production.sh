#!/bin/bash
# Quick Production Server Start
# Run this after deploy-production.sh has been executed

set -e

echo "🚀 Business Data Analyzer - Quick Start"
echo "=========================================="
echo ""

# Check if virtual environment exists
if [ ! -d ".venv-production" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run: ./deploy-production.sh"
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ Configuration file (.env) not found!"
    echo "Please run: ./deploy-production.sh"
    exit 1
fi

# Activate virtual environment
echo "📦 Activating virtual environment..."
source .venv-production/bin/activate

# Check if required packages are installed
echo "🔍 Checking dependencies..."
python3 -c "import vanna, flask, pandas, pyodbc" 2>/dev/null || {
    echo "❌ Missing dependencies. Installing..."
    pip install -q vanna flask pandas pyodbc
}

echo "✓ All dependencies ready"
echo ""

# Get server configuration from .env
HOST=$(grep "^HOST=" .env | cut -d= -f2 || echo "0.0.0.0")
PORT=$(grep "^PORT=" .env | cut -d= -f2 || echo "8084")

echo "🌐 Server Configuration:"
echo "   Host: $HOST"
echo "   Port: $PORT"
echo ""

# Display access URLs
IP_ADDRESS=$(hostname -I | awk '{print $1}' || echo "localhost")
echo "📱 Access URLs:"
echo "   Local: http://localhost:$PORT"
echo "   Network: http://$IP_ADDRESS:$PORT"
echo ""

echo "🚀 Starting production server..."
echo "   (Press Ctrl+C to stop)"
echo "=========================================="
echo ""

# Start the server
export PRODUCTION_MODE=true
python3 src/vanna_grok.py
