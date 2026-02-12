# Architecture Documentation

> **Technical design, system organization, and implementation details for the Business Data Analyzer.**

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
9. [AI Integration](#ai-integration)
10. [Performance Considerations](#performance-considerations)

---

## Overview

The Business Data Analyzer is a Python-based business intelligence platform for hardware store operations. It provides three primary interfaces:

1. **AI Natural Language Queries** — Ask questions in plain English/Spanish via web chat
2. **Traditional Script Analysis** — Command-line Python for automated reports
3. **Interactive Web Dashboard** — Streamlit-based UI for teams

### Design Goals

- **Modular**: Separate concerns (config, analytics, visualization, AI)
- **Extensible**: Easy to add new metrics or AI providers
- **Secure**: Environment-based configuration, no hardcoded credentials
- **Flexible**: Multiple interfaces for different user types
- **Maintainable**: Clear structure, comprehensive documentation

---

## Repository Structure

```
depotru_database/
├── src/                              # Source code
│   ├── vanna_grok.py                 # AI chat (Grok-optimized, Spanish)
│   ├── vanna_chat.py                 # AI chat (multi-provider support)
│   ├── business_analyzer_combined.py # Traditional analyzer (1,500+ lines)
│   ├── config.py                     # Configuration management
│   └── utils/                        # Utility functions
│
├── tests/                            # Test suite
│   ├── test_basic.py                 # Repository structure tests
│   ├── test_business_metrics.py      # Business logic tests
│   ├── test_formatting.py            # Number formatting tests
│   └── test_metabase_connection.py   # Database connection tests
│
├── docs/                             # Documentation
│   ├── ARCHITECTURE.md               # This file
│   ├── CONTRIBUTING.md               # Developer guide
│   ├── SECURITY.md                   # Security guidelines
│   ├── TESTING.md                    # Testing guide
│   ├── ROADMAP.md                    # Future plans
│   └── AI_AGENT_INSTRUCTIONS.md      # AI development guide
│
├── examples/                         # Example implementations
│   ├── improvements_p0.py           # Critical bug fixes demo
│   ├── pandas_approach.py            # Modern pandas implementation
│   └── streamlit_dashboard.py        # Web dashboard
│
├── data/                            # Data files
│   └── database_explained.json      # Schema documentation
│
├── .env.example                      # Environment template
├── requirements.txt                  # Python dependencies
├── pyproject.toml                    # Modern Python packaging
└── README.md                         # Main documentation
```

---

## Core Components

### 1. Configuration Management (`src/config.py`)

Centralized configuration with environment variable support:

```python
class Config:
    """Application configuration"""
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    GROK_API_KEY = os.getenv('GROK_API_KEY')
    # ... more config
```

**Features:**
- Environment variable support (`.env` files via `python-dotenv`)
- Fallback defaults for optional settings
- Validation logic for required credentials
- Security warnings for missing credentials

### 2. AI Chat Interface (`src/vanna_grok.py`)

Production-ready natural language to SQL conversion:

**Key Features:**
- **Grok (xAI) optimized** — Best for Spanish queries
- **Colombian formatting** — $1.234.567, 45,6%
- **AI insights** — Automatic business recommendations
- **Production server** — Waitress for concurrent users
- **Connection validation** — Ping test on startup

**Architecture:**
```
User Question → Vanna AI → SQL Query → SQL Server → Results → Format → Display
                ↓
            Grok API (xAI)
```

**Usage:**
```bash
python src/vanna_grok.py
# → http://localhost:8084
```

### 3. Traditional Analyzer (`src/business_analyzer_combined.py`)

Core analytics engine for business metrics:

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `fetch_banco_datos()` | Database connection & query |
| `analyze_financial_metrics()` | Revenue, profit, margins |
| `analyze_customer_segments()` | Customer categorization |
| `analyze_product_performance()` | Top products, margins |
| `analyze_categories()` | Category-level analytics |
| `analyze_inventory()` | Inventory velocity |
| `generate_visualizations()` | PNG report generation |

**Usage:**
```bash
python src/business_analyzer_combined.py --limit 5000
```

### 4. Multi-Provider AI (`src/vanna_chat.py`)

Alternative AI interface supporting multiple providers:

**Supported Providers:**
- OpenAI GPT-4
- Grok (xAI)
- Anthropic Claude
- Ollama (local)

**Use case:** Testing different AI providers or when Grok is unavailable.

---

## Data Flow

### AI Chat Flow

```
┌─────────────┐
│   User      │
│ (Natural    │
│  Language)  │
└──────┬──────┘
       │
       ▼
┌─────────────────────────┐
│ vanna_grok.py           │
│ (Flask Web UI)          │
└──────┬──────────────────┘
       │
       ├──► Grok API ───────────► Generate SQL
       │
       ├──► SQL Server ──────────► Execute Query
       │
       ├──► Format Results ─────► Colombian formatting
       │
       └──► AI Insights ────────► Business recommendations
```

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
       ├──► Config (.env) ────► Database credentials
       │
       ├──► SQL Server ───────► banco_datos table
       │
       ├──► Analytics Engine ──► JSON Output
       │
       └──► Visualization ─────► PNG Report
```

---

## Technology Stack

### Core Dependencies

| Technology | Purpose | Version |
|------------|---------|---------|
| **Python** | Programming language | 3.8+ |
| **pymssql/pyodbc** | SQL Server connection | 2.2.0+ |
| **python-dotenv** | Environment variables | 0.19.0+ |
| **pandas** | Data manipulation | 1.3.0+ |
| **matplotlib** | Static visualizations | 3.5.0+ |

### AI/ML Stack

| Technology | Purpose | Version |
|------------|---------|---------|
| **Vanna** | Natural language to SQL | 2.0.1 (legacy) |
| **ChromaDB** | Vector database | 0.4.0+ |
| **OpenAI** | GPT-4 API | 1.0.0+ |
| **Anthropic** | Claude API | 0.7.0+ |

### Web Framework Stack

| Technology | Purpose | Version |
|------------|---------|---------|
| **Streamlit** | Web dashboards | 1.20.0+ |
| **Flask** | Web server | 2.0.0+ |
| **Waitress** | Production WSGI | 2.1.0+ |
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

Environment-based configuration with fallbacks:

```python
# Good (Environment-based)
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PASSWORD = os.getenv('DB_PASSWORD')  # Required, no default

# Validation function
def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} is required")
    return value
```

### 2. Safe Operations Pattern

Wrapper functions for risky operations:

```python
def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Perform division with zero-check."""
    return numerator / denominator if denominator != 0 else default

# Usage
profit_margin = safe_divide(profit, revenue, 0.0)
```

### 3. Factory Pattern

Create different AI provider instances:

```python
def create_vanna_instance():
    """Factory for creating Vanna AI instance"""
    if USE_GROK:
        return create_grok_vanna()
    elif USE_OPENAI:
        return create_openai_vanna()
    # ... etc
```

### 4. Retry Pattern

Exponential backoff for API calls:

```python
from functools import wraps

def retry_on_failure(max_attempts=3, delay=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    time.sleep(delay * (attempt + 1))
        return wrapper
    return decorator
```

---

## Security Architecture

### Credential Management

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

### Input Validation

Validate all user input:

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

### Database Security

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
python src/vanna_grok.py
```

**Best for**: Development, testing

### Option 2: Production Server

```bash
# Install with production dependencies
pip install vanna chromadb pyodbc openai python-dotenv waitress

# Run with production server
PRODUCTION_MODE=true python src/vanna_grok.py
# → Uses Waitress (handles 10-50 concurrent users)
```

**Best for**: Production deployment

### Option 3: Docker Deployment

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY .env .

CMD ["python", "src/vanna_grok.py"]
```

**Best for**: Consistent deployments

### Option 4: Streamlit Cloud

```bash
# Run locally
streamlit run examples/streamlit_dashboard.py

# Deploy to Streamlit Cloud
# 1. Push to GitHub
# 2. Connect to Streamlit Cloud
# 3. Deploy!
```

**Best for**: Team dashboards

---

## AI Integration

### Vanna AI Architecture

Vanna uses **Retrieval Augmented Generation (RAG)**:

1. **Training Phase**:
   - Database schema (DDL) → ChromaDB
   - Documentation → ChromaDB
   - Example SQL queries → ChromaDB

2. **Query Phase**:
   - User question → Embedding
   - Search ChromaDB for similar examples
   - Generate SQL using context + LLM
   - Execute SQL against database
   - Return formatted results

### Training Data

The system includes pre-configured training for SmartBusiness database:

```python
# Schema training
vn.train(ddl="""
    CREATE TABLE banco_datos (
        Fecha DATE,
        TotalMasIva DECIMAL(18,2),
        TotalSinIva DECIMAL(18,2),
        ValorCosto DECIMAL(18,2),
        TercerosNombres NVARCHAR(200),
        ArticulosNombre NVARCHAR(200),
        categoria NVARCHAR(100)
    );
""")

# Documentation training
vn.train(documentation="""
    - TotalMasIva = revenue WITH tax (IVA)
    - TotalSinIva = revenue WITHOUT tax
    - Profit = TotalSinIva - ValorCosto
    - Always exclude DocumentosCodigo IN ('XY', 'AS', 'TS')
""")

# Example queries (Spanish)
examples = [
    ("Top 10 productos más vendidos", "SELECT ..."),
    ("Ganancias por categoría", "SELECT ..."),
]
```

### AI Providers

| Provider | Setup | Best For |
|----------|-------|----------|
| **Grok (xAI)** | `GROK_API_KEY=xai-...` | Production, Spanish |
| **OpenAI** | `OPENAI_API_KEY=sk-...` | Accuracy |
| **Claude** | `ANTHROPIC_API_KEY=sk-ant-...` | Complex queries |
| **Ollama** | Local installation | Privacy, free |

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

### Resource Optimization

1. **Single AI client** — Reuse Grok client across requests
2. **Limit AI context** — Send only top 15 rows for insights
3. **Connection pooling** — Reuse database connections
4. **Caching** — Cache frequent queries (future enhancement)

### Performance Targets

| Operation | Target | Current |
|-----------|--------|---------|
| SQL query generation | < 2s | ~1.5s |
| DataFrame formatting (1000 rows) | < 0.5s | ~0.3s |
| AI insights generation | < 5s | ~3s |
| Page load time | < 3s | ~2s |

---

## Future Enhancements

See [ROADMAP.md](ROADMAP.md) for detailed planning:

1. **API Layer** — RESTful API for programmatic access
2. **Query Caching** — Redis integration to reduce API costs
3. **Authentication** — User accounts and access control
4. **Scheduled Reports** — Daily/weekly automated reports
5. **Smart Alerts** — Threshold-based notifications
6. **Multi-tenancy** — Support multiple companies/stores

---

## References

- [Vanna AI Documentation](https://vanna.ai/docs/)
- [Grok API Reference](https://docs.x.ai/)
- [Pandas Documentation](https://pandas.pydata.org/docs/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [SQL Server Best Practices](https://docs.microsoft.com/sql/)

---

**Questions?** See [CONTRIBUTING.md](CONTRIBUTING.md) or open an issue.
