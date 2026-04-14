#!/bin/bash
# Production Deployment Script for Business Data Analyzer
# Option 1: Production Server Deployment
# ===========================================

set -e  # Exit on any error

echo "=========================================="
echo "🚀 Business Data Analyzer - Production Deployment"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
VENV_DIR=".venv-production"
PYTHON_VERSION="3.9"
REQUIRED_SPACE_GB=2

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}❌ Error: Must run from repository root directory${NC}"
    exit 1
fi

echo "📁 Repository root detected"
echo ""

# Step 1: Check system requirements
echo "🔍 Step 1: Checking system requirements..."

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    exit 1
fi

PYTHON_VER=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $PYTHON_VER"

# Check available disk space
AVAILABLE_SPACE=$(df . | tail -1 | awk '{print $4}')
AVAILABLE_GB=$((AVAILABLE_SPACE / 1024 / 1024))

if [ $AVAILABLE_GB -lt $REQUIRED_SPACE_GB ]; then
    echo -e "${YELLOW}⚠️  Warning: Only ${AVAILABLE_GB}GB available. Recommended: ${REQUIRED_SPACE_GB}GB+${NC}"
else
    echo "✓ Disk space: ${AVAILABLE_GB}GB available"
fi

# Check for required system packages
echo ""
echo "🔍 Checking system dependencies..."

# Check for ODBC drivers
if command -v odbcinst &> /dev/null; then
    echo "✓ ODBC drivers found"
else
    echo -e "${YELLOW}⚠️  ODBC drivers not detected. You may need to install:${NC}"
    echo "   Ubuntu/Debian: sudo apt-get install unixodbc-dev msodbcsql17"
    echo "   macOS: brew install unixodbc msodbcsql17"
fi

echo ""

# Step 2: Create virtual environment
echo "📦 Step 2: Setting up Python virtual environment..."

if [ -d "$VENV_DIR" ]; then
    echo "✓ Virtual environment exists: $VENV_DIR"
else
    echo "Creating virtual environment: $VENV_DIR"
    python3 -m venv $VENV_DIR
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
source $VENV_DIR/bin/activate

echo "✓ Virtual environment activated"
echo ""

# Step 3: Install dependencies
echo "📦 Step 3: Installing production dependencies..."

echo "Upgrading pip..."
pip install --quiet --upgrade pip

echo "Installing core dependencies (this may take a few minutes)..."
pip install --quiet \
    vanna>=0.3.0 \
    chromadb>=0.4.0 \
    pyodbc>=4.0.0 \
    pandas>=1.5.0 \
    numpy>=1.21.0 \
    matplotlib>=3.5.0 \
    plotly>=5.0.0 \
    flask>=2.0.0 \
    waitress>=2.1.0 \
    python-dotenv>=0.19.0 \
    openai>=1.0.0 \
    anthropic>=0.7.0 \
    requests>=2.28.0 \
    rich>=13.0.0 \
    pymssql>=2.2.8

echo "✓ Dependencies installed"
echo ""

# Step 4: Create .env file if it doesn't exist
echo "⚙️  Step 4: Configuration setup..."

if [ -f ".env" ]; then
    echo -e "${GREEN}✓ .env file already exists${NC}"
    echo ""
    read -p "Do you want to reconfigure? (y/N): " RECONFIGURE
    if [[ $RECONFIGURE =~ ^[Yy]$ ]]; then
        CONFIGURE=true
    else
        CONFIGURE=false
    fi
else
    echo "Creating .env configuration file..."
    CONFIGURE=true
fi

if [ "$CONFIGURE" = true ]; then
    echo ""
    echo "=========================================="
    echo "🔧 Database Configuration"
    echo "=========================================="
    echo ""

    read -p "Database Host (e.g., sql.yourcompany.com): " DB_HOST
    read -p "Database Port [1433]: " DB_PORT
    DB_PORT=${DB_PORT:-1433}
    read -p "Database Username: " DB_USER
    read -s -p "Database Password: " DB_PASSWORD
    echo ""
    read -p "Database Name [SmartBusiness]: " DB_NAME
    DB_NAME=${DB_NAME:-SmartBusiness}

    echo ""
    echo "=========================================="
    echo "🤖 AI Provider Configuration (Choose ONE)"
    echo "=========================================="
    echo ""
    echo "1. Grok (xAI) - Recommended for Spanish"
    echo "2. OpenAI GPT-4 - Best accuracy"
    echo "3. Anthropic Claude - Complex reasoning"
    echo "4. Ollama (Local) - Free, no API key"
    echo ""
    read -p "Select AI provider (1-4): " AI_CHOICE

    case $AI_CHOICE in
        1)
            read -s -p "Enter Grok API Key (xai-...): " API_KEY
            echo ""
            AI_PROVIDER="grok"
            ;;
        2)
            read -s -p "Enter OpenAI API Key (sk-...): " API_KEY
            echo ""
            AI_PROVIDER="openai"
            ;;
        3)
            read -s -p "Enter Anthropic API Key (sk-ant-...): " API_KEY
            echo ""
            AI_PROVIDER="anthropic"
            ;;
        4)
            API_KEY=""
            AI_PROVIDER="ollama"
            echo "Ollama selected. Make sure Ollama is installed locally."
            ;;
        *)
            echo -e "${YELLOW}⚠️  Invalid choice. Using Grok as default.${NC}"
            read -s -p "Enter Grok API Key (xai-...): " API_KEY
            echo ""
            AI_PROVIDER="grok"
            ;;
    esac

    echo ""
    echo "=========================================="
    echo "🌐 Server Configuration"
    echo "=========================================="
    echo ""
    read -p "Server Host [0.0.0.0]: " HOST
    HOST=${HOST:-0.0.0.0}
    read -p "Server Port [8084]: " PORT
    PORT=${PORT:-8084}

    # Create .env file
    cat > .env << EOF
# Business Data Analyzer - Production Configuration
# Generated on $(date)
# ============================================

# Database Configuration
DB_HOST=$DB_HOST
DB_PORT=$DB_PORT
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD
DB_NAME=$DB_NAME

# AI Provider Configuration
AI_PROVIDER=$AI_PROVIDER
EOF

    # Add API key based on provider
    case $AI_PROVIDER in
        grok)
            echo "GROK_API_KEY=$API_KEY" >> .env
            ;;
        openai)
            echo "OPENAI_API_KEY=$API_KEY" >> .env
            ;;
        anthropic)
            echo "ANTHROPIC_API_KEY=$API_KEY" >> .env
            ;;
    esac

    # Add server configuration
    cat >> .env << EOF

# Server Configuration
HOST=$HOST
PORT=$PORT
PRODUCTION_MODE=true

# Output Configuration
OUTPUT_DIR=~/business_reports
REPORT_DPI=300
DEFAULT_LIMIT=1000
LOG_LEVEL=INFO

# Features
ENABLE_AI_INSIGHTS=true
EOF

    echo ""
    echo -e "${GREEN}✓ .env file created successfully${NC}"
fi

echo ""

# Step 5: Test database connectivity
echo "🔌 Step 5: Testing database connectivity..."

python3 << 'PYTHON_SCRIPT'
import sys
import os
from dotenv import load_dotenv

load_dotenv()

required_vars = ['DB_HOST', 'DB_USER', 'DB_PASSWORD', 'DB_NAME']
missing = [var for var in required_vars if not os.getenv(var)]

if missing:
    print(f"❌ Missing environment variables: {', '.join(missing)}")
    sys.exit(1)

try:
    import pyodbc
    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={os.getenv('DB_HOST')};"
        f"DATABASE={os.getenv('DB_NAME')};"
        f"UID={os.getenv('DB_USER')};"
        f"PWD={os.getenv('DB_PASSWORD')};"
        f"Timeout=10;"
    )

    print(f"Connecting to {os.getenv('DB_HOST')}...")
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    cursor.execute("SELECT @@VERSION")
    version = cursor.fetchone()[0]
    conn.close()

    print(f"✓ Database connection successful!")
    print(f"  SQL Server version: {version[:50]}...")
    sys.exit(0)

except Exception as e:
    print(f"❌ Database connection failed: {e}")
    sys.exit(1)
PYTHON_SCRIPT

if [ $? -ne 0 ]; then
    echo ""
    echo -e "${RED}❌ Database connection test failed!${NC}"
    echo "Please check your database credentials and network connectivity."
    exit 1
fi

echo ""

# Step 6: Create systemd service file (optional)
echo "⚙️  Step 6: Creating systemd service file..."

cat > business-analyzer.service << EOF
[Unit]
Description=Business Data Analyzer - AI-Powered BI Platform
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/$VENV_DIR/bin
ExecStart=$(pwd)/$VENV_DIR/bin/python $(pwd)/src/vanna_grok.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo "✓ Created business-analyzer.service"
echo ""
echo "To install as system service (requires sudo):"
echo "  sudo cp business-analyzer.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable business-analyzer"
echo "  sudo systemctl start business-analyzer"
echo ""

# Step 7: Start production server
echo "🚀 Step 7: Starting production server..."
echo ""
echo "=========================================="
echo "🎉 Deployment Complete!"
echo "=========================================="
echo ""
echo -e "${GREEN}Server is ready to start!${NC}"
echo ""
echo "To start the server manually:"
echo "  source $VENV_DIR/bin/activate"
echo "  python src/vanna_grok.py"
echo ""
echo "Or use the systemd service (recommended for production):"
echo "  sudo systemctl start business-analyzer"
echo ""
echo "Access the web interface at:"
echo "  http://$(hostname -I | awk '{print $1}'):${PORT:-8084}"
echo ""
echo "Test the AI chat with questions like:"
echo "  • 'Top 10 productos más vendidos este mes'"
echo "  • 'Ganancias por categoría'"
echo "  • 'Clientes con mayor facturación'"
echo ""
echo "Logs are available via:"
echo "  journalctl -u business-analyzer -f"
echo ""
echo "=========================================="

# Ask if user wants to start now
read -p "Start the server now? (y/N): " START_NOW

if [[ $START_NOW =~ ^[Yy]$ ]]; then
    echo ""
    echo "🚀 Starting production server..."
    echo "Press Ctrl+C to stop"
    echo "=========================================="
    echo ""
    python src/vanna_grok.py
fi
