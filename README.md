# Business Data Analyzer 📊

> **Comprehensive business intelligence platform for hardware store operations** with AI-powered natural language SQL queries, automated reporting, and interactive visualizations.

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

---

## ✨ Features

### 🤖 AI-Powered Natural Language Queries
- **Ask questions in plain English** - "What are my top 10 selling products?"
- **Vanna AI integration** with support for:
  - OpenAI GPT-4
  - **Grok (xAI)** 🆕
  - Anthropic Claude
  - Ollama (local, private, free)
- **Auto-generated SQL** from natural language
- **Web-based chat interface** at http://localhost:8084

### 📈 Comprehensive Business Analytics
- Financial metrics (revenue, profit, margins)
- Customer segmentation (VIP, High Value, Frequent, Regular)
- Product performance analytics
- Category-level profitability
- Inventory velocity tracking
- Trend analysis and forecasting

### 🎨 Automated Visualizations
- Professional PNG reports
- Interactive dashboards (Streamlit)
- Category distribution charts
- Profit margin analysis
- Revenue breakdowns

### 🔒 Enterprise-Grade Security
- Environment-based configuration
- Secure credential management
- No hardcoded passwords
- .env file support

---

## 🚀 Quick Start

### Option 1: Traditional Business Analyzer

```bash
# Install dependencies
pip install pymssql python-dotenv matplotlib numpy

# Configure environment
cp .env.example .env
# Edit .env with your database credentials

# Run analysis
python src/business_analyzer_combined.py
```

### Option 2: AI-Powered Natural Language Queries 🌟

**Two implementations available** ([see comparison](docs/VANNA_COMPARISON.md)):

**A) Production-Ready Grok (Recommended) 🌟:**
```bash
# Install
pip install vanna chromadb pyodbc openai waitress python-dotenv pandas

# Configure .env
echo "GROK_API_KEY=xai-your-key" >> .env

# Run
python src/vanna_grok.py
# → http://localhost:8084
# Ask in Spanish: "Top 10 productos más vendidos"
```

**✨ Features:**
- 💰 **Beautiful number formatting** (Colombian pesos: `$123.456.789`)
- 🤖 **AI-powered insights** (Grok analyzes results and gives recommendations)
- 🇪🇸 **Spanish-optimized** (Colombian business context)
- 📊 **Executive summaries** with each query

**B) Multi-Provider (Testing):**
```bash
# Install
pip install vanna chromadb pyodbc openai

# Choose provider
export GROK_API_KEY='xai-your-key'        # Grok (xAI)
# OR export OPENAI_API_KEY='sk-...'       # OpenAI
# OR export ANTHROPIC_API_KEY='sk-ant-'   # Anthropic

# Run
python src/vanna_chat.py
# → http://localhost:8084
```

### Option 3: Interactive Web Dashboard

```bash
# Install Streamlit
pip install streamlit pandas plotly

# Run dashboard
streamlit run examples/streamlit_dashboard.py
```

---

## 📁 Project Structure

```
coding_omarchy/
├── README.md                          # ⭐ You are here
├── .env.example                       # Environment configuration template
├── .gitignore                         # Git exclusions
├── .gitattributes                     # Git attributes
├── requirements.txt                   # Python dependencies
│
├── src/                              # 💻 Source Code
│   ├── __init__.py
│   ├── business_analyzer_combined.py # Main analyzer (traditional)
│   ├── vanna_grok.py                 # 🆕 AI chat (Grok-optimized, Spanish)
│   ├── vanna_chat.py                 # AI chat (multi-provider support)
│   ├── config.py                     # Configuration management
│   └── utils/                        # Utility functions
│       └── __init__.py
│
├── tests/                            # 🧪 Tests
│   ├── __init__.py
│   ├── test_business_metrics.py      # Business logic tests
│   └── test_metabase_connection.py   # Database connection tests
│
├── docs/                             # 📚 Documentation
│   ├── START_HERE.md                 # ⭐ Start here!
│   ├── ROADMAP.md                    # 🗺️ Strategic roadmap & what's next
│   ├── VANNA_COMPARISON.md           # 🆕 Vanna implementations comparison
│   ├── VANNA_BEAUTIFUL_OUTPUT.md     # 🎨 Beautiful output examples
│   ├── VANNA_SETUP.md                # Vanna AI setup guide
│   ├── ARCHITECTURE.md               # Technical architecture
│   ├── ANALYSIS_SUMMARY.md           # Executive summary
│   ├── IMPROVEMENT_ANALYSIS.md       # Detailed analysis
│   ├── QUICK_START_IMPROVEMENTS.md   # Fast-track guide
│   ├── P0_FIXES_APPLIED.md           # Critical fixes
│   ├── METABASE_TROUBLESHOOTING.md   # Metabase guide
│   ├── SECURITY.md                   # Security guidelines
│   ├── CONTRIBUTING.md               # Development guide
│   └── setup_instructions.md         # Setup instructions
│
├── examples/                         # 💡 Examples
│   ├── improvements_p0.py            # Critical bug fixes
│   ├── pandas_approach.py            # Modern Pandas implementation
│   └── streamlit_dashboard.py        # Web dashboard
│
└── data/                            # 📊 Data Files
    └── database_explained.json       # Database schema documentation
```

---

## 🎯 Choose Your Workflow

### For Business Users (No Coding Required)
```bash
# Option A: Ask questions in plain English
python src/vanna_chat.py
# "What are my top customers this month?"

# Option B: Use Metabase (Docker)
docker run -d -p 3000:3000 metabase/metabase
# Point & click dashboards
```

### For Data Analysts
```bash
# Interactive Streamlit dashboard
streamlit run examples/streamlit_dashboard.py
# Real-time filtering, interactive charts
```

### For Developers
```bash
# Traditional script-based analysis
python src/business_analyzer_combined.py --limit 5000
# Or use Pandas approach (10-100x faster)
python examples/pandas_approach.py
```

---

## 🤖 Vanna AI - Natural Language SQL

### Supported AI Providers

| Provider | Cost | Speed | Quality | Setup Difficulty |
|----------|------|-------|---------|------------------|
| **OpenAI GPT-4** | $$ | Fast | ⭐⭐⭐⭐⭐ | Easy |
| **Grok (xAI)** 🆕 | $$ | Fast | ⭐⭐⭐⭐ | Easy |
| **Anthropic Claude** | $$ | Fast | ⭐⭐⭐⭐⭐ | Easy |
| **Ollama (Local)** | Free | Medium | ⭐⭐⭐ | Medium |

### Example Questions You Can Ask

```
💬 "What are my top 10 selling products?"
💬 "Show me revenue by category this month"
💬 "Which customers have the highest order values?"
💬 "What's my profit margin by product?"
💬 "Show me monthly revenue trends"
💬 "Which products have low profit margins?"
💬 "Compare this month's revenue to last month"
💬 "Show me my best customers in the last 90 days"
```

### Setup Vanna with Grok (New!)

```bash
# Install dependencies
pip install vanna chromadb pyodbc

# Set your Grok API key
export GROK_API_KEY='xai-your-grok-api-key'

# Edit src/vanna_chat.py
USE_GROK = True
USE_OPENAI = False
USE_OLLAMA = False
USE_ANTHROPIC = False

# Run
python src/vanna_chat.py
```

---

## 📊 Traditional Business Analyzer

### Command Line Options

```bash
# Basic analysis (default 1000 records)
python src/business_analyzer_combined.py

# Analyze more records
python src/business_analyzer_combined.py --limit 5000

# Analyze specific date range
python src/business_analyzer_combined.py \
  --start-date 2025-01-01 \
  --end-date 2025-10-31

# Skip re-analysis, just regenerate visualizations
python src/business_analyzer_combined.py --skip-analysis
```

### Output Files

All reports saved to `~/business_reports/` (configurable):
- `analysis_comprehensive_YYYY-MM-DD_to_YYYY-MM-DD.json`
- `business_analysis_report_YYYYMMDD_HHMMSS.png`

---

## ⚙️ Configuration

### Environment Variables (.env file)

```bash
# Database Connection
DB_HOST=your-server-host
DB_PORT=1433
DB_USER=your-username
DB_PASSWORD=your-password
DB_NAME=SmartBusiness

# AI Providers (choose one)
OPENAI_API_KEY=sk-your-openai-key
GROK_API_KEY=xai-your-grok-key         # 🆕 Grok support
ANTHROPIC_API_KEY=sk-ant-your-key

# Output Configuration
OUTPUT_DIR=~/business_reports
REPORT_DPI=300
DEFAULT_LIMIT=1000
```

See `.env.example` for all options.

---

## 🔒 Security

**IMPORTANT**: Never commit credentials to version control!

✅ **Best Practices:**
- Use `.env` files (already in `.gitignore`)
- Use environment variables in production
- Rotate credentials regularly
- Use least-privilege database accounts

📖 See [`docs/SECURITY.md`](docs/SECURITY.md) for detailed guidelines.

---

## 📚 Documentation

**New to this project?** Start here:
1. **[docs/START_HERE.md](docs/START_HERE.md)** - Quick overview and path selection
2. **[docs/VANNA_SETUP.md](docs/VANNA_SETUP.md)** - AI natural language setup (includes Grok!)
3. **[docs/ANALYSIS_SUMMARY.md](docs/ANALYSIS_SUMMARY.md)** - Executive summary

**Detailed guides:**
- [docs/IMPROVEMENT_ANALYSIS.md](docs/IMPROVEMENT_ANALYSIS.md) - 500+ line deep dive
- [docs/QUICK_START_IMPROVEMENTS.md](docs/QUICK_START_IMPROVEMENTS.md) - Fast-track guide
- [docs/P0_FIXES_APPLIED.md](docs/P0_FIXES_APPLIED.md) - Critical fixes applied
- [docs/ANACONDA_TESTING.md](docs/ANACONDA_TESTING.md) - Multi-version Python testing 🆕
- [docs/METABASE_TROUBLESHOOTING.md](docs/METABASE_TROUBLESHOOTING.md) - Metabase guide
- [docs/SECURITY.md](docs/SECURITY.md) - Security best practices
- [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) - Development workflow

---

## 🧪 Testing

### Quick Testing

```bash
# Quick start - Run basic tests (no dependencies required)
python run_tests.py --quick

# Run all available tests
python run_tests.py

# Run with coverage report
python run_tests.py --cov

# Using pytest directly
pytest tests/ -v

# Run specific test file
pytest tests/test_basic.py -v
```

### Multi-Version Testing with Anaconda 🆕

Test on Python 3.8, 3.9, 3.10, and 3.11:

```bash
# Create Conda environment
conda env create -f environment.yml
conda activate business-analyzer

# Run tests
pytest tests/ -v --cov=src

# Test on specific Python version
conda create -n test-py310 python=3.10 -y
conda activate test-py310
pip install -r requirements.txt
pytest tests/ -v
```

**📖 Full guide:** [docs/ANACONDA_TESTING.md](docs/ANACONDA_TESTING.md)

---

## 🛠️ Development

### Code Style

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

### Running Examples

```bash
# Critical P0 fixes
python examples/improvements_p0.py

# Modern Pandas approach (10-100x faster)
python examples/pandas_approach.py

# Interactive Streamlit dashboard
streamlit run examples/streamlit_dashboard.py
```

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
→ Check API key is set: `echo $OPENAI_API_KEY` or `echo $GROK_API_KEY`

### Metabase showing wrong data
→ See [docs/METABASE_TROUBLESHOOTING.md](docs/METABASE_TROUBLESHOOTING.md)

---

## 🚀 Performance

| Approach | Lines of Code | Performance | Use Case |
|----------|---------------|-------------|----------|
| Current Script | 1,492 | Baseline | Works today |
| Pandas Approach | 200 | **10-100x faster** | Best for developers |
| Streamlit | 300 | **10x faster** | Best for teams |
| Metabase | 0 (GUI) | Fast | Best for business users |
| **Vanna AI** 🆕 | 0 (Natural Language) | **Real-time** | **Best for everyone** |

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

[Specify your license here]

---

## 🙏 Acknowledgments

- Built for hardware store business intelligence
- Designed for SmartBusiness ERP integration
- Compatible with Magento e-commerce
- **Vanna AI integration** for natural language SQL
- **Grok (xAI) support** 🆕

---

## 📞 Support

- 📖 **Documentation**: See `docs/` directory
- 🐛 **Issues**: Open a GitHub issue
- 💡 **Questions**: See [docs/START_HERE.md](docs/START_HERE.md)

---

## 🎯 Quick Links

| I want to... | Go here... |
|-------------|-----------|
| **See what's next / roadmap** 🗺️ | [docs/ROADMAP.md](docs/ROADMAP.md) 🆕 |
| **Run tests** 🧪 | `python run_tests.py --quick` + [docs/TESTING.md](docs/TESTING.md) |
| **Use Grok AI in Spanish** 🆕 | [src/vanna_grok.py](src/vanna_grok.py) + [docs/VANNA_COMPARISON.md](docs/VANNA_COMPARISON.md) |
| **See beautiful output examples** 🎨 | [docs/VANNA_BEAUTIFUL_OUTPUT.md](docs/VANNA_BEAUTIFUL_OUTPUT.md) |
| Ask questions in plain English | [src/vanna_chat.py](src/vanna_chat.py) + [docs/VANNA_SETUP.md](docs/VANNA_SETUP.md) |
| Get started quickly | [docs/START_HERE.md](docs/START_HERE.md) |
| Compare Vanna implementations | [docs/VANNA_COMPARISON.md](docs/VANNA_COMPARISON.md) |
| Run traditional analyzer | `python src/business_analyzer_combined.py` |
| Build web dashboard | `streamlit run examples/streamlit_dashboard.py` |
| Fix critical bugs | [examples/improvements_p0.py](examples/improvements_p0.py) |
| Understand the code | [docs/IMPROVEMENT_ANALYSIS.md](docs/IMPROVEMENT_ANALYSIS.md) |
| Secure my deployment | [docs/SECURITY.md](docs/SECURITY.md) |

---

**⭐ Star this repo if you find it useful!**

**🚀 Ready to get started?** → [docs/START_HERE.md](docs/START_HERE.md)

---

**Note**: This tool processes business data. Ensure compliance with data privacy regulations (GDPR, CCPA, etc.) when handling customer information.
