# Business Data Analyzer 📊

> **AI-powered business intelligence for hardware store operations.** Ask questions in plain English, get SQL queries and visualizations automatically.

[![CI](https://github.com/Trujillofa/depotru_database/actions/workflows/ci.yml/badge.svg)](https://github.com/Trujillofa/depotru_database/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

---

## ✨ Features

### 🤖 AI-Powered Natural Language Queries
- **Ask in plain English** — "What are my top 10 selling products?"
- **Vanna AI** with support for OpenAI GPT-4, Grok (xAI), Anthropic Claude, Ollama (local)
- **Auto-generated SQL** from natural language
- **Web chat interface** at http://localhost:8084
- **Spanish-optimized** for Colombian business context

### 📈 Business Analytics
- Financial metrics (revenue, profit, margins)
- Customer segmentation (VIP, High Value, Frequent, Regular)
- Product performance and category profitability
- Inventory velocity tracking
- Trend analysis

### 🎨 Visualizations
- Professional PNG reports
- Interactive Streamlit dashboards
- Colombian number formatting ($1.234.567, 45,6%)

### 🔒 Security
- Environment-based configuration (.env files)
- No hardcoded credentials
- Secure credential management

---

## 🚀 Quick Start

### Option 1: AI Natural Language (Recommended)

```bash
# Clone the repository
git clone https://github.com/Trujillofa/depotru_database.git
cd depotru_database

# Install in development mode (recommended)
pip install -e ".[dev]"

# Or install minimal dependencies
pip install vanna chromadb pyodbc openai python-dotenv pandas

# Configure environment
cp .env.example .env
# Edit .env with your credentials:
#   GROK_API_KEY=xai-your-key
#   DB_SERVER=your-server
#   DB_NAME=SmartBusiness
#   DB_USER=your-username
#   DB_PASSWORD=your-password

# Run the AI chat interface
python src/vanna_grok.py
# → Open http://localhost:8084
```

**Example questions to ask:**
- "Top 10 productos más vendidos este mes"
- "Ganancias por categoría"
- "Clientes con mayor facturación"
- "Margen de ganancia promedio"

### Option 2: Traditional Script Analysis

```bash
# Install dependencies
pip install pymssql python-dotenv matplotlib numpy pandas

# Configure environment
cp .env.example .env
# Edit .env with your database credentials

# Run analysis
python src/business_analyzer_combined.py

# Analyze more records
python src/business_analyzer_combined.py --limit 5000

# Analyze date range
python src/business_analyzer_combined.py --start-date 2025-01-01 --end-date 2025-12-31
```

### Option 3: Interactive Web Dashboard

```bash
# Install Streamlit
pip install streamlit pandas plotly

# Run dashboard
streamlit run examples/streamlit_dashboard.py
# → Opens automatically in browser
```

---

## 📁 Project Structure

```
depotru_database/
├── src/                                    # Source code
│   ├── business_analyzer/                  # Modular business analyzer package
│   │   ├── core/                           # Foundation modules
│   │   │   ├── config.py                   # Configuration management
│   │   │   ├── database.py                 # Database connectivity
│   │   │   └── validation.py               # Input validation
│   │   ├── analysis/                       # Business logic analyzers
│   │   │   ├── customer.py                 # Customer segmentation
│   │   │   ├── financial.py                # Financial metrics
│   │   │   ├── product.py                  # Product performance
│   │   │   ├── inventory.py                # Inventory velocity
│   │   │   └── unified.py                    # Combined analyzer
│   │   ├── ai/                             # AI integration
│   │   │   ├── base.py                     # AIVanna base class
│   │   │   ├── formatting.py               # Colombian number formatting
│   │   │   ├── insights.py                 # AI insights generation
│   │   │   ├── training.py                 # Schema training
│   │   │   └── providers/                  # AI provider implementations
│   │   │       ├── grok.py                 # xAI Grok
│   │   │       ├── openai.py               # OpenAI GPT
│   │   │       ├── anthropic.py            # Anthropic Claude
│   │   │       └── ollama.py               # Local Ollama
│   │   └── __init__.py                     # Package exports
│   ├── vanna_grok.py                       # AI chat CLI (thin wrapper)
│   ├── business_analyzer_combined.py       # Legacy analyzer (deprecated)
│   └── config.py                           # Legacy config (deprecated)
│
├── tests/                                  # Test suite
│   ├── test_basic.py                       # Repository structure tests
│   ├── test_business_metrics.py            # Business logic tests
│   ├── test_formatting.py                  # Number formatting tests
│   ├── test_config.py                      # Configuration tests
│   ├── analysis/                           # Analyzer module tests
│   │   ├── test_customer.py
│   │   ├── test_financial.py
│   │   ├── test_product.py
│   │   └── test_inventory.py
│   └── ai/                                 # AI module tests
│       └── test_base.py
│
├── docs/                                   # Documentation
│   ├── ARCHITECTURE.md                     # Technical design
│   ├── CONTRIBUTING.md                     # Developer guide
│   ├── SECURITY.md                         # Security guidelines
│   ├── TESTING.md                          # Testing guide
│   ├── PERFORMANCE.md                      # Performance characteristics
│   ├── ROADMAP.md                          # Future plans
│   └── AI_AGENT_INSTRUCTIONS.md            # AI development guide
│
├── examples/                               # Example implementations
│   ├── improvements_p0.py                # Critical fixes demo
│   ├── pandas_approach.py                  # Modern pandas implementation
│   └── streamlit_dashboard.py            # Web dashboard
│
├── benchmarks/                             # Performance benchmarks
│   └── performance_benchmark.py
│
├── .github/workflows/                      # CI/CD pipelines
│   └── ci.yml                              # Unified CI workflow
│
├── .env.example                            # Environment template
├── requirements.txt                        # Python dependencies
├── pyproject.toml                          # Modern Python packaging
├── pytest.ini                              # Test configuration
└── README.md                               # This file
```

---

## ⚙️ Configuration

Create a `.env` file in the project root:

```bash
# Database Connection (Required)
DB_HOST=your-server-host
DB_PORT=1433
DB_USER=your-username
DB_PASSWORD=your-password
DB_NAME=SmartBusiness

# AI Provider (Choose one)
GROK_API_KEY=xai-your-grok-key          # Recommended
# OPENAI_API_KEY=sk-your-openai-key
# ANTHROPIC_API_KEY=sk-ant-your-key

# Optional Settings
OUTPUT_DIR=~/business_reports
REPORT_DPI=300
DEFAULT_LIMIT=1000
HOST=0.0.0.0
PORT=8084
```

**Security note:** Never commit `.env` files to version control. The repository includes `.env.example` as a template.

---

## 🤖 AI Providers Comparison

| Provider | Cost | Speed | Quality | Best For |
|----------|------|-------|---------|----------|
| **Grok (xAI)** | $$ | Fast | ⭐⭐⭐⭐ | Production, Spanish queries |
| **OpenAI GPT-4** | $$ | Fast | ⭐⭐⭐⭐⭐ | Best accuracy |
| **Anthropic Claude** | $$ | Fast | ⭐⭐⭐⭐⭐ | Complex reasoning |
| **Ollama (Local)** | Free | Medium | ⭐⭐⭐ | Privacy, no API costs |

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run quick tests (no dependencies required)
pytest tests/test_basic.py -v

# Run with coverage
pytest tests/ -v --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/analysis/test_financial.py -v
```

See [docs/TESTING.md](docs/TESTING.md) for detailed testing guide.

---

## 🛠️ Development

```bash
# Format code
black src/ tests/ examples/

# Lint
flake8 src/ tests/

# Type checking
mypy src/

# Sort imports
isort src/ tests/ examples/
```

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for full development guide.

---

## 🔒 Security

- **Never commit credentials** to version control
- Use `.env` files for local development (already in `.gitignore`)
- Use environment variables in production
- Rotate credentials regularly
- Use least-privilege database accounts

See [docs/SECURITY.md](docs/SECURITY.md) for detailed security guidelines.

---

## 📊 What It Analyzes

| Category | Metrics |
|----------|---------|
| **Financial** | Revenue (with/without IVA), profit margins, gross profit, average order value |
| **Customers** | Segmentation (VIP, High Value, Frequent, Regular), top customers, concentration |
| **Products** | Top sellers, profitability, star products, underperformers |
| **Categories** | Category revenue/margins, subcategories, risk assessment |
| **Inventory** | Fast movers, slow movers, velocity analysis |
| **Trends** | Monthly trends, seasonal patterns, category distribution |

---

## 🐛 Troubleshooting

### "No valid database configuration found"
→ Check `.env` file exists and has correct credentials

### "Matplotlib not available"
→ `pip install matplotlib numpy`

### Vanna AI not connecting
→ Check API key is set: `echo $GROK_API_KEY` or `echo $OPENAI_API_KEY`

### Database connection failed
→ Verify ODBC driver is installed:
```bash
# Ubuntu/Debian
sudo apt install unixodbc-dev msodbcsql17

# macOS
brew install unixodbc msodbcsql17
```

---

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, data flow, tech stack |
| [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) | Development workflow, code style |
| [docs/SECURITY.md](docs/SECURITY.md) | Security best practices |
| [docs/TESTING.md](docs/TESTING.md) | Testing guide |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Future development plans |
| [docs/AI_AGENT_INSTRUCTIONS.md](docs/AI_AGENT_INSTRUCTIONS.md) | AI agent development guide |

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests: `pytest tests/`
5. Format code: `black src/ tests/`
6. Submit a pull request

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for detailed guidelines.

---

## 📄 License

MIT License — see LICENSE file for details.

---

## 🙏 Acknowledgments

- Built for hardware store business intelligence
- Designed for SmartBusiness ERP integration
- **Vanna AI** for natural language SQL
- **Grok (xAI)** for AI-powered insights

---

**⭐ Star this repo if you find it useful!**

**🚀 Ready to get started?** Configure your `.env` file and run `python src/vanna_grok.py`
