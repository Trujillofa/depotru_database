# Architecture Documentation

> **Comprehensive guide to the Business Data Analyzer architecture, design decisions, and technical organization.**

---

## Table of Contents

1. [Overview](#overview)
2. [Repository Structure](#repository-structure)
3. [Core Components](#core-components)
4. [Data Flow](#data-flow)
5. [Technology Stack](#technology-stack)
6. [Design Patterns](#design-patterns)
7. [Security Architecture](#security-architecture)
8. [Deployment Options](#deployment-options)

---

## Overview

The Business Data Analyzer is a comprehensive business intelligence platform built with Python, designed for hardware store operations. It provides three primary interfaces:

1. **Traditional Script-based Analysis** - Command-line Python script
2. **AI-Powered Natural Language Queries** - Vanna AI integration with Grok support
3. **Interactive Web Dashboards** - Streamlit-based UI

### Design Goals

- **Modular**: Separate concerns (config, analytics, visualization, AI)
- **Extensible**: Easy to add new metrics or AI providers
- **Secure**: Environment-based configuration, no hardcoded credentials
- **Flexible**: Multiple interfaces for different user types
- **Maintainable**: Clear structure, comprehensive documentation

---

## Repository Structure

```
coding_omarchy/
│
├── src/                              # Source code
│   ├── __init__.py                   # Package initialization
│   ├── business_analyzer_combined.py # Main analyzer (1,500+ lines)
│   ├── vanna_chat.py                 # AI natural language interface
│   ├── config.py                     # Configuration management
│   └── utils/                        # Utility functions
│       └── __init__.py
│
├── tests/                            # Test suite
│   ├── __init__.py
│   ├── test_business_metrics.py      # Business logic tests
│   └── test_metabase_connection.py   # Database tests
│
├── docs/                             # Documentation
│   ├── START_HERE.md                 # Entry point
│   ├── ARCHITECTURE.md               # This file
│   ├── VANNA_SETUP.md                # AI setup guide
│   ├── SECURITY.md                   # Security guidelines
│   └── ...                           # Additional docs
│
├── examples/                         # Example implementations
│   ├── improvements_p0.py            # Critical fixes
│   ├── pandas_approach.py            # Modern approach
│   └── streamlit_dashboard.py        # Web dashboard
│
├── data/                            # Data files
│   └── database_explained.json       # Schema documentation
│
├── .env.example                      # Environment template
├── requirements.txt                  # Dependencies
└── README.md                         # Main documentation
```

### Why This Structure?

| Directory | Purpose | Rationale |
|-----------|---------|-----------|
| `src/` | Source code | Standard Python package structure |
| `tests/` | Test suite | Separate tests from source (pytest convention) |
| `docs/` | Documentation | Centralize all documentation |
| `examples/` | Example code | Keep examples separate from main code |
| `data/` | Data files | Separate data from code |

**Previous issues:**
- 10 documentation files scattered in root
- Main scripts mixed with config/test files
- No clear separation of concerns

**Current benefits:**
- Clear organization
- Easy to navigate
- Standard Python conventions
- Scales well as project grows

---

## Core Components

### 1. Configuration Management (`src/config.py`)

**Purpose**: Centralized configuration with environment variable support.

```python
class Config:
    """Application configuration"""
    NCX_FILE_PATH = os.getenv('NCX_FILE_PATH', '...')
    DB_HOST = os.getenv('DB_HOST', None)
    DB_PASSWORD = os.getenv('DB_PASSWORD', None)
    # ... more config
```

**Features:**
- Environment variable support (`.env` files via `python-dotenv`)
- Fallback defaults
- Validation logic
- Security warnings

**Configuration Classes:**
- `Config` - Main application settings
- `CustomerSegmentation` - Thresholds for customer categorization
- `InventoryConfig` - Inventory velocity thresholds
- `ProfitabilityConfig` - Profit margin thresholds

---

### 2. Main Business Analyzer (`src/business_analyzer_combined.py`)

**Purpose**: Core analytics engine for business metrics.

**Key Functions:**

| Function | Purpose | Lines |
|----------|---------|-------|
| `fetch_banco_datos()` | Database connection & query | ~50 |
| `analyze_financial_metrics()` | Revenue, profit, margins | ~100 |
| `analyze_customer_segments()` | Customer categorization | ~150 |
| `analyze_product_performance()` | Top products, margins | ~120 |
| `analyze_categories()` | Category-level analytics | ~80 |
| `analyze_inventory()` | Inventory velocity | ~60 |
| `generate_visualizations()` | PNG report generation | ~200 |

**P0 Fixes Applied:**
- ✅ Safe division (`safe_divide()` function)
- ✅ Connection cleanup (`finally` block)
- ✅ Input validation (`validate_date_format()`, etc.)

**Usage:**
```bash
python src/business_analyzer_combined.py --limit 5000
```

---

### 3. Vanna AI Integration (`src/vanna_chat.py`)

**Purpose**: Natural language to SQL conversion with web interface.

**Supported AI Providers:**

```python
# Option 1: OpenAI GPT-4
USE_OPENAI = True
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Option 2: Grok (xAI) 🆕
USE_GROK = True
GROK_API_KEY = os.getenv("GROK_API_KEY")

# Option 3: Anthropic Claude
USE_ANTHROPIC = True
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Option 4: Ollama (local)
USE_OLLAMA = True
OLLAMA_MODEL = "mistral"
```

**Key Functions:**
- `create_vanna_instance()` - Creates AI instance
- `connect_to_database()` - Connects to SQL Server
- `train_vanna_on_schema()` - Trains on database schema
- `run_chat_interface()` - Launches Flask web UI

**Architecture:**
```
User Question → Vanna AI → SQL Query → SQL Server → Results → User
```

**Usage:**
```bash
export GROK_API_KEY='xai-...'
python src/vanna_chat.py
# Open http://localhost:8084
```

---

## Data Flow

### Traditional Analysis Flow

```
┌─────────────┐
│   User      │
│  (CLI Args) │
└──────┬──────┘
       │
       ▼
┌─────────────────────────┐
│ business_analyzer_      │
│ combined.py             │
└──────┬──────────────────┘
       │
       ├──► Config (.env) ────► NCX File / Direct DB Config
       │
       ├──► SQL Server ───────► banco_datos table
       │
       ├──► Analytics Engine ──► JSON Output
       │
       └──► Visualization ─────► PNG Report
```

### Vanna AI Flow

```
┌─────────────┐
│   User      │
│ (Natural    │
│  Language)  │
└──────┬──────┘
       │
       ▼
┌─────────────────────────┐
│ vanna_chat.py           │
│ (Flask Web UI)          │
└──────┬──────────────────┘
       │
       ├──► Grok/OpenAI/Claude ──► Generate SQL
       │
       ├──► SQL Server ──────────► Execute Query
       │
       └──► Format Results ───────► Display to User
```

### Streamlit Dashboard Flow

```
┌─────────────┐
│   User      │
│ (Web UI)    │
└──────┬──────┘
       │
       ▼
┌─────────────────────────┐
│ streamlit_dashboard.py  │
│ (Interactive Web App)   │
└──────┬──────────────────┘
       │
       ├──► Pandas ────────────► Data Processing
       │
       ├──► Plotly ────────────► Interactive Charts
       │
       └──► SQL Server ────────► Real-time Data
```

---

## Technology Stack

### Core Dependencies

| Technology | Purpose | Version |
|------------|---------|---------|
| **Python** | Programming language | 3.8+ |
| **pymssql** | SQL Server connection | 2.2.0+ |
| **python-dotenv** | Environment variables | 0.19.0+ |
| **matplotlib** | Static visualizations | 3.5.0+ |
| **numpy** | Numerical computing | 1.21.0+ |

### AI/ML Stack

| Technology | Purpose | Version |
|------------|---------|---------|
| **Vanna** | Natural language to SQL | 0.3.0+ |
| **ChromaDB** | Vector database | 0.4.0+ |
| **OpenAI** | GPT-4 API | 1.0.0+ |
| **Anthropic** | Claude API | 0.7.0+ |
| **Grok** | xAI API (OpenAI-compatible) | - |

### Web Framework Stack

| Technology | Purpose | Version |
|------------|---------|---------|
| **Streamlit** | Web dashboards | 1.20.0+ |
| **Flask** | Lightweight web server | 2.0.0+ |
| **Plotly** | Interactive charts | 5.0.0+ |

### Development Stack

| Technology | Purpose | Version |
|------------|---------|---------|
| **pytest** | Testing framework | 7.0.0+ |
| **black** | Code formatting | 22.0.0+ |
| **flake8** | Linting | 4.0.0+ |
| **mypy** | Type checking | 0.950+ |

---

## Design Patterns

### 1. Configuration Pattern

**Pattern**: Environment-based configuration with fallbacks

```python
# Bad (Hardcoded)
DB_HOST = "192.168.1.100"
DB_PASSWORD = "secret123"

# Good (Environment-based)
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PASSWORD = os.getenv('DB_PASSWORD')
```

**Benefits:**
- Secure (no credentials in code)
- Flexible (different configs for dev/prod)
- Standard practice

---

### 2. Dependency Injection Pattern

**Pattern**: Pass dependencies as parameters

```python
# Instead of global connection
def analyze_data():
    conn = create_connection()  # Creates connection inside
    # ...

# Use dependency injection
def analyze_data(connection):
    # Use provided connection
    # ...

# Easier to test, mock, and reuse
```

---

### 3. Safe Operations Pattern

**Pattern**: Wrapper functions for risky operations

```python
def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Perform division with zero-check."""
    return numerator / denominator if denominator != 0 else default

# Usage
profit_margin = safe_divide(profit, revenue, 0.0)
```

**Applied to:**
- Division by zero (21 locations)
- Date parsing
- Database operations

---

### 4. Factory Pattern

**Pattern**: Create different AI provider instances

```python
def create_vanna_instance():
    """Factory for creating Vanna AI instance"""
    if USE_OPENAI:
        return create_openai_vanna()
    elif USE_GROK:
        return create_grok_vanna()
    elif USE_ANTHROPIC:
        return create_anthropic_vanna()
    elif USE_OLLAMA:
        return create_ollama_vanna()
```

**Benefits:**
- Easy to add new providers
- Single point of configuration
- Runtime selection

---

## Security Architecture

### 1. Credential Management

**Layers of Security:**

```
┌────────────────────────────────────┐
│  1. Never commit to version control│ (.gitignore)
├────────────────────────────────────┤
│  2. Use .env files locally         │ (python-dotenv)
├────────────────────────────────────┤
│  3. Use environment variables       │ (os.getenv)
├────────────────────────────────────┤
│  4. Use secret management in prod   │ (AWS Secrets, etc.)
└────────────────────────────────────┘
```

**Implementation:**
- ✅ `.env` in `.gitignore`
- ✅ `.env.example` (template with no real values)
- ✅ `Config` class validates credentials
- ✅ Warnings for missing credentials

---

### 2. Input Validation

**Pattern**: Validate all user input

```python
def validate_date_format(date_str: str, param_name: str) -> datetime:
    """Validate date format and range"""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        if date_obj.year < 1900 or date_obj.year > 2100:
            raise ValueError(f"Year out of range")
        return date_obj
    except ValueError as e:
        raise ValueError(f"Invalid {param_name}: {e}")
```

**Validates:**
- Date formats (YYYY-MM-DD)
- Date ranges (start <= end)
- Numeric limits (1 <= limit <= 1,000,000)

---

### 3. Database Security

**Best Practices:**
- Use parameterized queries (prevent SQL injection)
- Least-privilege database accounts
- Connection timeouts
- Proper connection cleanup (`finally` blocks)

---

## Deployment Options

### Option 1: Local Development

```bash
# Setup
git clone <repo>
pip install -r requirements.txt
cp .env.example .env
# Edit .env with credentials

# Run
python src/business_analyzer_combined.py
```

**Best for**: Development, testing

---

### Option 2: Docker Deployment

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY .env .

CMD ["python", "src/business_analyzer_combined.py"]
```

**Best for**: Production, consistency

---

### Option 3: Vanna AI Web Service

```bash
# Setup
pip install vanna chromadb pyodbc openai
export GROK_API_KEY='xai-...'

# Run
python src/vanna_chat.py

# Deploy with
gunicorn --bind 0.0.0.0:8084 src.vanna_chat:app
```

**Best for**: Business users, self-service

---

### Option 4: Streamlit Cloud

```bash
# Setup
pip install streamlit pandas plotly

# Run locally
streamlit run examples/streamlit_dashboard.py

# Deploy to Streamlit Cloud
# 1. Push to GitHub
# 2. Connect to Streamlit Cloud
# 3. Deploy!
```

**Best for**: Teams, interactive dashboards

---

## Performance Considerations

### Database Query Optimization

**Current Approach:**
```python
# Fetches all data, processes in Python
data = fetch_banco_datos(limit=100000)
# ... Python processing ...
```

**Optimized Approach (Pandas):**
```python
# Push computation to database
query = """
SELECT
    categoria,
    SUM(TotalMasIva) as revenue,
    SUM(TotalSinIva - ValorCosto) as profit
FROM banco_datos
WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
GROUP BY categoria
"""
df = pd.read_sql(query, conn)
```

**Benefits:**
- 10-100x faster
- Less memory usage
- Leverages database indexes

---

## Future Enhancements

### Planned Improvements

1. **API Layer**
   - RESTful API for programmatic access
   - JWT authentication
   - Rate limiting

2. **Real-time Analytics**
   - WebSocket connections
   - Live dashboard updates
   - Real-time alerts

3. **Advanced AI**
   - Predictive analytics
   - Anomaly detection
   - Automated insights

4. **Multi-tenant Support**
   - Multiple database support
   - User authentication
   - Role-based access control

---

## Contributing to Architecture

### Adding a New AI Provider

1. Add configuration in `src/vanna_chat.py`:
```python
USE_NEW_PROVIDER = False
NEW_PROVIDER_API_KEY = os.getenv("NEW_PROVIDER_API_KEY")
```

2. Add factory case in `create_vanna_instance()`:
```python
elif USE_NEW_PROVIDER:
    from vanna.new_provider import NewProvider_Chat
    # ... implementation
```

3. Update `.env.example`
4. Update documentation

---

### Adding a New Metric

1. Add function in `src/business_analyzer_combined.py`:
```python
def analyze_new_metric(data):
    """Analyze new metric"""
    # ... implementation
    return results
```

2. Call in main analysis flow
3. Add visualization if needed
4. Add tests in `tests/test_business_metrics.py`
5. Update documentation

---

## References

- [Python Best Practices](https://docs.python-guide.org/)
- [Vanna AI Documentation](https://vanna.ai/docs/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [SQL Server Best Practices](https://docs.microsoft.com/sql/)

---

**Questions?** See [CONTRIBUTING.md](CONTRIBUTING.md) or open an issue.
