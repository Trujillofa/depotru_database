# Production Readiness Analysis: depotru_database

**Analysis Date:** 2026-01-19
**Repository:** Trujillofa/depotru_database
**Branch:** claude/production-readiness-analysis-sEsBT
**Analyst:** Claude (Opus 4.5)

---

## Executive Summary

This repository is a **Business Intelligence platform for Colombian hardware store operations** that provides:
- Natural language to SQL queries via multiple AI providers (Grok, OpenAI, Claude, Ollama)
- Business analytics with financial metrics, customer segmentation, and product performance
- Web-based dashboards (Streamlit) and CLI-based reporting
- Integration with MSSQL Server (SmartBusiness ERP)

**Current State: 70% Production Ready**

The codebase demonstrates good security awareness (SQL injection prevention, credential management) and has comprehensive documentation. However, critical gaps exist in API architecture, database schema management, testing depth, and infrastructure automation that must be addressed before production deployment.

---

## 1. Repository Overview

### What Problem This Repository Solves

This platform enables non-technical business users at a Colombian hardware store (ferreteria) to:
1. Query sales data using natural language in Spanish/English
2. Generate automated business reports with visualizations
3. Analyze customer segments, product performance, and profitability
4. Make data-driven decisions through AI-powered insights

### How It Fits Into a Full Stack Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CURRENT ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│   ┌──────────────┐    ┌─────────────────┐    ┌─────────────────┐    │
│   │  Streamlit   │    │  Flask/Vanna    │    │   CLI Scripts   │    │
│   │  Dashboard   │    │   Web Chat      │    │  (Reports/      │    │
│   │  (Port 8501) │    │  (Port 8084)    │    │   Analysis)     │    │
│   └──────┬───────┘    └────────┬────────┘    └────────┬────────┘    │
│          │                     │                      │              │
│          └─────────────────────┼──────────────────────┘              │
│                                │                                      │
│                    ┌───────────▼───────────┐                         │
│                    │  Business Logic Layer  │                         │
│                    │  (business_analyzer_   │                         │
│                    │   combined.py)         │                         │
│                    └───────────┬───────────┘                         │
│                                │                                      │
│          ┌─────────────────────┼─────────────────────┐               │
│          │                     │                     │               │
│   ┌──────▼──────┐    ┌────────▼────────┐    ┌───────▼───────┐       │
│   │  ChromaDB   │    │    pymssql/     │    │  AI Providers │       │
│   │  (Vectors)  │    │    pyodbc       │    │  (Grok/GPT-4/ │       │
│   │             │    │                 │    │   Claude)     │       │
│   └─────────────┘    └────────┬────────┘    └───────────────┘       │
│                               │                                      │
│                    ┌──────────▼──────────┐                          │
│                    │   MSSQL Server      │                          │
│                    │   (SmartBusiness)   │                          │
│                    │   [External - Not   │                          │
│                    │    Part of Repo]    │                          │
│                    └────────────────────┘                           │
└─────────────────────────────────────────────────────────────────────┘
```

### Technologies, Languages, and Patterns Used

| Category | Technologies |
|----------|-------------|
| **Language** | Python 3.8+ (primary) |
| **Database** | MSSQL Server (SmartBusiness ERP), ChromaDB (vectors) |
| **AI/ML** | Vanna.ai, OpenAI GPT-4, Grok (xAI), Anthropic Claude, Ollama |
| **Web Frameworks** | Flask + Waitress (WSGI), Streamlit |
| **Data Processing** | Pandas, NumPy |
| **Visualization** | Matplotlib, Plotly, Seaborn |
| **ORM** | SQLAlchemy (partial), raw pymssql/pyodbc |
| **Testing** | pytest, pytest-cov |
| **CI/CD** | GitHub Actions |
| **Security** | CodeQL, dependency review |

### Intended Data Flow and Responsibilities

```
User Query (Spanish/English)
         │
         ▼
┌────────────────────┐
│ Vanna AI Layer     │──► ChromaDB (retrieve similar queries)
│ (vanna_grok.py)    │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│ AI Provider        │──► Generate SQL from natural language
│ (Grok/GPT-4/etc)   │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│ SQL Validation     │──► Prevent SQL injection
│ (validate_sql_     │
│  identifier)       │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│ MSSQL Database     │──► Execute query with parameterization
│ (banco_datos)      │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│ Business Metrics   │──► Calculate KPIs, segmentation
│ Calculator         │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│ Visualization &    │──► Format in Colombian pesos, generate
│ Reporting          │    charts, produce insights
└────────────────────┘
```

---

## 2. Production Readiness Assessment

### Code Quality and Structure

| Aspect | Score | Assessment |
|--------|-------|------------|
| **Code Organization** | B+ | Clear separation of concerns, but some monolithic files (1,689 LOC in `business_analyzer_combined.py`) |
| **Documentation** | A | Excellent inline docs, comprehensive README, architecture docs |
| **Type Hints** | B- | Present in key functions, but inconsistent across codebase |
| **Error Handling** | B | Good try/catch patterns, but missing custom exception classes |
| **Naming Conventions** | A- | Consistent snake_case for Python, clear variable names |
| **DRY Principle** | C+ | Duplicate code exists (see Critical Issues) |

**Code Organization Issues:**

```
src/
├── business_analyzer_combined.py  # 1,689 lines - TOO LARGE
├── vanna_grok.py                  # 713 lines - acceptable
├── vanna_chat.py                  # 395 lines - good
└── config.py                      # 141 lines - good
```

Recommendation: Break down `business_analyzer_combined.py` into:
- `src/database/connection.py`
- `src/metrics/calculator.py`
- `src/visualization/charts.py`
- `src/reports/generator.py`

### Database Schema Design and Normalization

**Critical Finding: No Database Schema Management**

This repository **does not manage the database schema**. It connects to an external SmartBusiness ERP database (`banco_datos` table). This is both a strength (doesn't modify production data) and a weakness (no schema versioning, no migrations).

**Current Schema Understanding** (from `data/database_explained.json`):

```sql
-- Reconstructed schema based on code analysis
CREATE TABLE banco_datos (
    VentaID INT PRIMARY KEY,              -- Sales transaction ID
    VendedorID INT,                        -- Vendor foreign key
    VendedorFactura NVARCHAR(200),         -- Vendor name
    DocumentosCodigo NVARCHAR(10),         -- Document type code
    DocumentosNombre NVARCHAR(100),        -- Document name
    NumeroDocumento INT,                   -- Document number
    Fecha DATE,                            -- Transaction date
    ano INT,                               -- Year
    mes INT,                               -- Month
    dia INT,                               -- Day
    periodo INT,                           -- Period (YYYYM format)
    DiasCredito INT,                       -- Credit days
    TercerosID INT,                        -- Customer foreign key
    TercerosIdentificacion NVARCHAR(50),   -- Customer ID number
    TercerosNombres NVARCHAR(200),         -- Customer name
    ArticulosID INT,                       -- Product foreign key
    ArticulosCodigo NVARCHAR(50),          -- Product code/SKU
    ArticulosNombre NVARCHAR(200),         -- Product name
    AlmacenCodigo NVARCHAR(10),            -- Warehouse code
    Cantidad DECIMAL(18,2),                -- Quantity
    VentaSinIva DECIMAL(18,4),             -- Unit price without IVA
    VentaMasIva DECIMAL(18,4),             -- Unit price with IVA
    TotalSinIva DECIMAL(18,2),             -- Total without IVA
    TotalMasIva DECIMAL(18,2),             -- Total with IVA
    ValorCosto DECIMAL(18,2),              -- Cost value
    PorDescuento DECIMAL(5,2),             -- Discount percentage
    ValorDescuento DECIMAL(18,4),          -- Discount value
    Iva DECIMAL(5,2),                      -- Tax rate
    marca NVARCHAR(100),                   -- Brand/Category
    proveedor NVARCHAR(100),               -- Supplier
    categoria NVARCHAR(100),               -- Category
    subcategoria NVARCHAR(100),            -- Subcategory
    departamento NVARCHAR(100),            -- State/Department
    ciudad NVARCHAR(100)                   -- City
);
```

**Normalization Issues Identified:**

1. **Denormalized Data**: Customer, vendor, product, and location data are embedded directly in the sales table rather than normalized into separate tables with foreign keys.

2. **Redundant Date Fields**: `Fecha`, `ano`, `mes`, `dia`, `periodo` store the same date information multiple times.

3. **Missing Indexes**: No evidence of indexing strategy for common queries.

**Recommendation**: Since this is an external database, document expected schema and create a schema validation check on startup.

### Naming Conventions and Consistency

| Entity | Convention | Consistency |
|--------|-----------|-------------|
| Python files | snake_case | Consistent |
| Python classes | PascalCase | Consistent |
| Python functions | snake_case | Consistent |
| Python variables | snake_case | Consistent |
| Database columns | PascalCase | Consistent (matches SmartBusiness) |
| Config constants | UPPER_SNAKE_CASE | Consistent |

**Issue**: Mixed language (Spanish/English) in database fields and comments:
- `TercerosNombres` (Spanish) vs `revenue` (English)
- Comments in Spanish and English

**Recommendation**: Standardize on English for code, use Spanish only for user-facing strings and documentation targeting Spanish speakers.

### Security Risks Assessment

| Risk Category | Status | Details |
|---------------|--------|---------|
| **SQL Injection** | MITIGATED | `validate_sql_identifier()` function blocks injection attempts |
| **Hardcoded Credentials** | MITIGATED | All credentials moved to environment variables |
| **API Keys Exposure** | LOW | API keys validated on load, not logged |
| **XSS (Streamlit)** | LOW | Streamlit sanitizes by default |
| **Authentication** | MISSING | No user authentication layer |
| **Authorization** | MISSING | No role-based access control |
| **Data Encryption** | PARTIAL | TLS for MSSQL possible, but not enforced |
| **Audit Logging** | MISSING | No audit trail for queries |
| **Rate Limiting** | MISSING | No protection against API abuse |

**Critical Security Finding - vanna_grok.py:527-539:**

```python
# DUPLICATE CODE - generate_insights called TWICE
if Config.ENABLE_AI_INSIGHTS:
    insights = generate_insights(
        question=question,
        sql=sql,
        df=df,
        grok_client=self.grok_client  # First call
    )
    print(insights)
else:
    print("\n💡 Insights desactivados (ENABLE_AI_INSIGHTS=false)\n")

# This code is ALWAYS executed (no condition) - DUPLICATE!
grok_client = OpenAI(
    api_key=Config.GROK_API_KEY, base_url="https://api.x.ai/v1"
)
insights = generate_insights(  # Second call - WASTES API TOKENS
    question=question,
    sql=sql,
    df=df,
    grok_client=grok_client,
)
print(insights)
```

### Performance and Scalability Concerns

| Concern | Severity | Details |
|---------|----------|---------|
| **No Connection Pooling** | HIGH | Each request creates new DB connection |
| **In-Memory Data Processing** | MEDIUM | Large datasets loaded entirely into memory |
| **No Caching Layer** | MEDIUM | Repeated queries hit database every time |
| **Single-Threaded Flask** | MEDIUM | Limited concurrent user capacity |
| **No Query Optimization** | MEDIUM | Missing indexes, no query plan analysis |
| **ChromaDB Scaling** | LOW | Local ChromaDB may not scale horizontally |

**Memory Concern** (`business_analyzer_combined.py:860`):

```python
data = list(cursor)  # Loads ALL results into memory
```

For queries returning 100,000+ rows, this could exhaust system memory.

### Error Handling and Data Integrity

**Good Practices Found:**
- `safe_divide()` function prevents division by zero
- Input validation for dates, limits, and SQL identifiers
- Proper `finally` blocks for database cleanup
- Retry logic with exponential backoff for API calls

**Missing:**
- Custom exception classes for domain-specific errors
- Transaction management for write operations
- Data integrity constraints (handled by external DB)
- Circuit breaker pattern for external API failures

### Environment Separation (Dev/Staging/Prod)

| Environment | Implementation | Status |
|-------------|---------------|--------|
| **Development** | `.env` file | Implemented |
| **Testing** | `_is_testing_env()` detection | Implemented |
| **Staging** | Not defined | Missing |
| **Production** | Environment variables | Partial |

**Issue**: No formal environment configuration management. All environments use the same `Config` class.

---

## 3. Critical Issues to Fix (Must-Fix Before Production)

### CRITICAL-01: Duplicate API Calls Wasting Tokens

**File:** `src/vanna_grok.py:513-539`
**Severity:** HIGH (Financial Impact)
**Impact:** Every query calls `generate_insights()` twice, doubling AI API costs.

**Current Code:**
```python
# Lines 513-525: First call (conditional)
if Config.ENABLE_AI_INSIGHTS:
    insights = generate_insights(question=question, sql=sql, df=df,
                                  grok_client=self.grok_client)
    print(insights)

# Lines 527-539: Second call (unconditional) - BUG!
grok_client = OpenAI(api_key=Config.GROK_API_KEY, base_url="https://api.x.ai/v1")
insights = generate_insights(question=question, sql=sql, df=df,
                              grok_client=grok_client)
print(insights)
```

**Fix:** Remove lines 527-539 entirely.

---

### CRITICAL-02: No Database Connection Pooling

**File:** `src/business_analyzer_combined.py:811-820`
**Severity:** HIGH (Performance/Stability)
**Impact:** Each request creates a new database connection, causing:
- Connection exhaustion under load
- Increased latency (connection setup ~100-500ms)
- Resource leaks if connections aren't closed properly

**Fix:**
```python
# Install: pip install sqlalchemy[pymssql]
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

# Create engine once at module level
engine = create_engine(
    f"mssql+pymssql://{user}:{password}@{host}:{port}/{database}",
    poolclass=QueuePool,
    pool_size=5,           # Base connections
    max_overflow=10,       # Additional connections under load
    pool_recycle=3600,     # Recycle connections after 1 hour
    pool_pre_ping=True     # Verify connections before use
)
```

---

### CRITICAL-03: No Authentication/Authorization

**Files:** All web endpoints
**Severity:** HIGH (Security)
**Impact:** Anyone with network access can query your database.

**Minimal Fix:**
```python
# For Streamlit: Use streamlit-authenticator
import streamlit_authenticator as stauth

# For Flask/Vanna: Use Flask-Login or JWT
from flask_login import LoginManager, login_required

@app.route('/api/query')
@login_required
def query():
    ...
```

---

### CRITICAL-04: Potential SQL Injection in Streamlit Dashboard

**File:** `examples/streamlit_dashboard.py:59-73`
**Severity:** HIGH (Security)
**Impact:** The `limit` parameter is inserted directly into SQL via f-string.

**Vulnerable Code:**
```python
query = f"""
SELECT TOP {limit}  -- VULNERABLE: limit comes from user slider
    Fecha, ...
FROM banco_datos
...
"""
```

**Fix:** Use parameterized queries:
```python
query = """
SELECT TOP :limit
    Fecha, ...
FROM banco_datos
...
"""
df = pd.read_sql(query, engine, params={"limit": limit, ...})
```

---

### CRITICAL-05: No Rate Limiting

**File:** `src/vanna_grok.py` (Flask app)
**Severity:** MEDIUM-HIGH (Cost/Availability)
**Impact:** Malicious users can exhaust AI API quotas and run up costs.

**Fix:**
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["100 per hour", "10 per minute"]
)

@app.route('/api/ask')
@limiter.limit("5 per minute")
def ask():
    ...
```

---

### CRITICAL-06: Missing Logging/Audit Trail

**Files:** All
**Severity:** MEDIUM (Compliance/Security)
**Impact:** No record of who queried what, making security incidents undetectable.

**Fix:**
```python
import logging
from datetime import datetime

# Configure structured logging
logging.basicConfig(
    format='{"time": "%(asctime)s", "level": "%(levelname)s", '
           '"user": "%(user)s", "action": "%(action)s", "details": "%(message)s"}',
    level=logging.INFO
)

# Log all queries
def log_query(user: str, question: str, sql: str, success: bool):
    logging.info(
        f"Query executed",
        extra={
            "user": user,
            "action": "query",
            "question": question[:100],  # Truncate for logs
            "success": success
        }
    )
```

---

### CRITICAL-07: Secrets in CI/CD Logs

**File:** `.github/workflows/tests.yml:87-91`
**Severity:** MEDIUM (Security)
**Impact:** Database credentials passed as environment variables could leak into logs.

**Current:**
```yaml
env:
  GROK_API_KEY: ${{ secrets.GROK_API_KEY }}
  DB_SERVER: ${{ secrets.DB_SERVER }}
  DB_PASSWORD: ${{ secrets.DB_PASSWORD }}  # Could leak in error messages
```

**Fix:** Add masking and use OIDC where possible:
```yaml
- name: Mask secrets
  run: |
    echo "::add-mask::${{ secrets.DB_PASSWORD }}"

- name: Run tests
  env:
    # Use GitHub OIDC for cloud providers instead of static credentials
```

---

## 4. Improvements and Refactors

### 4.1 Code Modularization

**Current Problem:** `business_analyzer_combined.py` is 1,689 lines doing too much.

**Proposed Structure:**
```
src/
├── __init__.py
├── config.py                    # Configuration (keep as-is)
├── database/
│   ├── __init__.py
│   ├── connection.py            # Connection pooling, management
│   ├── queries.py               # SQL query builders
│   └── validation.py            # SQL injection prevention
├── metrics/
│   ├── __init__.py
│   ├── calculator.py            # BusinessMetricsCalculator
│   ├── financial.py             # Financial calculations
│   ├── customer.py              # Customer segmentation
│   └── product.py               # Product analytics
├── visualization/
│   ├── __init__.py
│   ├── charts.py                # Matplotlib/Plotly charts
│   └── formatting.py            # Number formatting (Colombian pesos)
├── reports/
│   ├── __init__.py
│   ├── generator.py             # Report generation
│   └── templates/               # Jinja2 templates
├── ai/
│   ├── __init__.py
│   ├── vanna_grok.py            # Grok integration
│   ├── vanna_chat.py            # Multi-provider chat
│   └── insights.py              # AI insights generation
└── api/
    ├── __init__.py
    ├── routes.py                # API endpoints
    └── middleware.py            # Auth, rate limiting, logging
```

### 4.2 Schema and Query Optimizations

**Add Schema Validation on Startup:**
```python
# src/database/validation.py
REQUIRED_COLUMNS = [
    'VentaID', 'Fecha', 'TotalMasIva', 'TotalSinIva',
    'ValorCosto', 'TercerosNombres', 'ArticulosNombre'
]

def validate_schema(connection) -> bool:
    """Validate that required columns exist in banco_datos."""
    cursor = connection.cursor()
    cursor.execute("""
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'banco_datos'
    """)
    existing = {row[0] for row in cursor.fetchall()}

    missing = set(REQUIRED_COLUMNS) - existing
    if missing:
        raise SchemaValidationError(
            f"Missing required columns: {missing}"
        )
    return True
```

**Add Query Performance Hints:**
```python
# Suggest indexes to DBA
RECOMMENDED_INDEXES = """
-- Recommended indexes for banco_datos (run on MSSQL Server)
CREATE INDEX IX_banco_datos_Fecha ON banco_datos(Fecha);
CREATE INDEX IX_banco_datos_DocumentosCodigo ON banco_datos(DocumentosCodigo);
CREATE INDEX IX_banco_datos_TercerosID ON banco_datos(TercerosID);
CREATE INDEX IX_banco_datos_ArticulosID ON banco_datos(ArticulosID);
CREATE INDEX IX_banco_datos_categoria ON banco_datos(categoria);
"""
```

### 4.3 Recommended Standards

**Linting/Formatting Configuration (`pyproject.toml`):**
```toml
[tool.black]
line-length = 100
target-version = ['py38', 'py39', 'py310', 'py311', 'py312']
exclude = '''
/(
    \.eggs
  | \.git
  | \.venv
  | build
  | dist
)/
'''

[tool.isort]
profile = "black"
line_length = 100
known_first_party = ["src"]

[tool.mypy]
python_version = "3.10"
strict = true
ignore_missing_imports = true

[tool.pylint]
max-line-length = 100
disable = ["C0114", "C0115", "C0116"]  # Disable missing docstring warnings

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short --cov=src --cov-report=term-missing"
```

**Pre-commit Hooks (`.pre-commit-config.yaml`):**
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.3.0
    hooks:
      - id: black

  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort

  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: detect-private-key
```

---

## 5. Full Stack Integration Plan

### 5.1 Recommended Architecture for Production

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     RECOMMENDED PRODUCTION ARCHITECTURE                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────┐    ┌────────────────┐    ┌────────────────┐         │
│  │  React/Vue     │    │  Mobile App    │    │  BI Tools      │         │
│  │  Frontend      │    │  (Optional)    │    │  (Metabase)    │         │
│  └───────┬────────┘    └───────┬────────┘    └───────┬────────┘         │
│          │                     │                     │                   │
│          └─────────────────────┼─────────────────────┘                   │
│                                │                                          │
│                     ┌──────────▼──────────┐                              │
│                     │   API Gateway       │◄── Auth (JWT/OAuth2)         │
│                     │   (Kong/AWS API GW) │◄── Rate Limiting             │
│                     └──────────┬──────────┘◄── Request Logging           │
│                                │                                          │
│                     ┌──────────▼──────────┐                              │
│                     │   FastAPI Backend   │                              │
│                     │   (Replaces Flask)  │                              │
│                     └──────────┬──────────┘                              │
│                                │                                          │
│       ┌────────────────────────┼────────────────────────┐                │
│       │                        │                        │                │
│ ┌─────▼─────┐           ┌──────▼──────┐          ┌──────▼──────┐        │
│ │  Redis    │           │  Business   │          │  AI Service │        │
│ │  Cache    │           │  Logic      │          │  (Vanna)    │        │
│ └───────────┘           └──────┬──────┘          └─────────────┘        │
│                                │                                          │
│                     ┌──────────▼──────────┐                              │
│                     │  SQLAlchemy ORM     │                              │
│                     │  (Connection Pool)  │                              │
│                     └──────────┬──────────┘                              │
│                                │                                          │
│                     ┌──────────▼──────────┐                              │
│                     │  MSSQL Server       │                              │
│                     │  (SmartBusiness)    │                              │
│                     └────────────────────┘                               │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Backend API Design (REST)

**Recommended API Endpoints:**

```yaml
openapi: 3.0.3
info:
  title: Business Data Analyzer API
  version: 1.0.0

paths:
  /api/v1/auth/login:
    post:
      summary: Authenticate user
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                username: { type: string }
                password: { type: string }
      responses:
        200:
          description: JWT token returned

  /api/v1/query/natural-language:
    post:
      summary: Execute natural language query
      security: [bearerAuth: []]
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                question: { type: string, example: "Top 10 productos vendidos" }
                include_insights: { type: boolean, default: true }
      responses:
        200:
          description: Query results with optional AI insights
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/QueryResult'

  /api/v1/metrics/financial:
    get:
      summary: Get financial KPIs
      parameters:
        - name: start_date
          in: query
          schema: { type: string, format: date }
        - name: end_date
          in: query
          schema: { type: string, format: date }
      responses:
        200:
          description: Financial metrics

  /api/v1/metrics/customers:
    get:
      summary: Get customer analytics
      responses:
        200:
          description: Customer segmentation and metrics

  /api/v1/metrics/products:
    get:
      summary: Get product performance
      responses:
        200:
          description: Product analytics

  /api/v1/reports/generate:
    post:
      summary: Generate PDF/Excel report
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                report_type: { type: string, enum: [financial, customer, product] }
                format: { type: string, enum: [pdf, excel, json] }
                date_range:
                  type: object
                  properties:
                    start: { type: string, format: date }
                    end: { type: string, format: date }
      responses:
        202:
          description: Report generation started
          content:
            application/json:
              schema:
                type: object
                properties:
                  task_id: { type: string }

components:
  schemas:
    QueryResult:
      type: object
      properties:
        sql: { type: string }
        data:
          type: array
          items: { type: object }
        row_count: { type: integer }
        insights: { type: string }
        execution_time_ms: { type: integer }

  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
```

### 5.3 FastAPI Implementation Example

```python
# src/api/main.py
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from pydantic import BaseModel
from typing import Optional
import jwt

app = FastAPI(
    title="Business Data Analyzer API",
    version="1.0.0",
    docs_url="/api/docs"
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# Auth
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload["sub"]
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

# Models
class NaturalLanguageQuery(BaseModel):
    question: str
    include_insights: bool = True

class QueryResult(BaseModel):
    sql: str
    data: list
    row_count: int
    insights: Optional[str]
    execution_time_ms: int

# Endpoints
@app.post("/api/v1/query/natural-language", response_model=QueryResult)
@limiter.limit("10/minute")
async def execute_natural_language_query(
    query: NaturalLanguageQuery,
    user: str = Depends(get_current_user)
):
    """Execute natural language query and return formatted results."""
    start_time = time.time()

    # Use existing Vanna integration
    vn = get_vanna_instance()
    sql, df, insights = vn.ask(query.question, print_results=False)

    execution_time = int((time.time() - start_time) * 1000)

    # Log for audit
    log_query(user=user, question=query.question, sql=sql, success=True)

    return QueryResult(
        sql=sql,
        data=df.to_dict(orient="records") if df is not None else [],
        row_count=len(df) if df is not None else 0,
        insights=insights if query.include_insights else None,
        execution_time_ms=execution_time
    )
```

### 5.4 Authentication/Authorization Model

**Recommended: JWT + Role-Based Access Control (RBAC)**

```python
# src/auth/models.py
from enum import Enum
from pydantic import BaseModel

class Role(str, Enum):
    ADMIN = "admin"           # Full access + user management
    ANALYST = "analyst"       # Full query access + reports
    VIEWER = "viewer"         # Read-only dashboards
    API_CLIENT = "api_client" # Programmatic access only

class Permission(str, Enum):
    QUERY_EXECUTE = "query:execute"
    QUERY_HISTORY = "query:history"
    REPORTS_GENERATE = "reports:generate"
    REPORTS_DOWNLOAD = "reports:download"
    USERS_MANAGE = "users:manage"
    ADMIN_ACCESS = "admin:access"

ROLE_PERMISSIONS = {
    Role.ADMIN: [Permission.QUERY_EXECUTE, Permission.QUERY_HISTORY,
                 Permission.REPORTS_GENERATE, Permission.REPORTS_DOWNLOAD,
                 Permission.USERS_MANAGE, Permission.ADMIN_ACCESS],
    Role.ANALYST: [Permission.QUERY_EXECUTE, Permission.QUERY_HISTORY,
                   Permission.REPORTS_GENERATE, Permission.REPORTS_DOWNLOAD],
    Role.VIEWER: [Permission.QUERY_HISTORY, Permission.REPORTS_DOWNLOAD],
    Role.API_CLIENT: [Permission.QUERY_EXECUTE]
}

class User(BaseModel):
    id: str
    username: str
    email: str
    role: Role

    def has_permission(self, permission: Permission) -> bool:
        return permission in ROLE_PERMISSIONS[self.role]
```

### 5.5 ORM Recommendation: SQLAlchemy 2.0

```python
# src/database/models.py
from sqlalchemy import Column, Integer, String, Numeric, Date, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool

Base = declarative_base()

class BancoDatos(Base):
    """SQLAlchemy model for banco_datos table (read-only mapping)."""
    __tablename__ = 'banco_datos'
    __table_args__ = {'schema': 'dbo'}

    VentaID = Column(Integer, primary_key=True)
    Fecha = Column(Date, index=True)
    TotalMasIva = Column(Numeric(18, 2))
    TotalSinIva = Column(Numeric(18, 2))
    ValorCosto = Column(Numeric(18, 2))
    Cantidad = Column(Numeric(18, 2))
    TercerosNombres = Column(String(200))
    ArticulosNombre = Column(String(200))
    ArticulosCodigo = Column(String(50))
    DocumentosCodigo = Column(String(10), index=True)
    categoria = Column(String(100), index=True)
    subcategoria = Column(String(100))

# Connection with pooling
def get_engine(config):
    return create_engine(
        f"mssql+pymssql://{config.DB_USER}:{config.DB_PASSWORD}"
        f"@{config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}",
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_recycle=3600,
        pool_pre_ping=True
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine(Config))
```

---

## 6. Production Infrastructure & DevOps Readiness

### 6.1 Environment Variables and Secrets Management

**Recommended: Migrate to Secret Management Service**

| Environment | Current | Recommended |
|-------------|---------|-------------|
| **Development** | `.env` file | Keep as-is |
| **CI/CD** | GitHub Secrets | GitHub OIDC + AWS/Azure secrets |
| **Staging** | Not defined | AWS Secrets Manager / Azure Key Vault |
| **Production** | Environment vars | AWS Secrets Manager / Azure Key Vault |

**Implementation:**
```python
# src/config/secrets.py
import os
from functools import lru_cache

def get_secret(name: str) -> str:
    """Get secret from appropriate source based on environment."""
    env = os.getenv("ENVIRONMENT", "development")

    if env == "development":
        # Use .env file
        from dotenv import load_dotenv
        load_dotenv()
        return os.getenv(name)

    elif env in ("staging", "production"):
        # Use AWS Secrets Manager
        import boto3
        from botocore.exceptions import ClientError

        client = boto3.client('secretsmanager')
        try:
            response = client.get_secret_value(SecretId=f"depotru/{env}/{name}")
            return response['SecretString']
        except ClientError as e:
            raise RuntimeError(f"Failed to get secret {name}: {e}")

    raise ValueError(f"Unknown environment: {env}")

@lru_cache(maxsize=1)
def get_db_credentials():
    """Get database credentials (cached)."""
    return {
        "host": get_secret("DB_HOST"),
        "port": int(get_secret("DB_PORT")),
        "user": get_secret("DB_USER"),
        "password": get_secret("DB_PASSWORD"),
        "database": get_secret("DB_NAME")
    }
```

### 6.2 Migration Strategy

Since this repo connects to an external SmartBusiness database, traditional migrations (Alembic/Django) don't apply. Instead:

**Schema Documentation & Validation:**
```python
# src/database/schema_validator.py
SCHEMA_VERSION = "1.0.0"

EXPECTED_SCHEMA = {
    "banco_datos": {
        "columns": [
            {"name": "VentaID", "type": "INT", "nullable": False},
            {"name": "Fecha", "type": "DATE", "nullable": True},
            {"name": "TotalMasIva", "type": "DECIMAL", "nullable": True},
            # ... other columns
        ],
        "indexes": [
            {"name": "IX_Fecha", "columns": ["Fecha"]},
            {"name": "IX_DocumentosCodigo", "columns": ["DocumentosCodigo"]}
        ]
    }
}

def validate_schema(connection) -> dict:
    """Validate external database schema matches expectations."""
    issues = []

    # Check columns exist
    cursor = connection.cursor()
    cursor.execute("""
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'banco_datos'
    """)

    existing_columns = {row[0]: row for row in cursor.fetchall()}

    for expected in EXPECTED_SCHEMA["banco_datos"]["columns"]:
        if expected["name"] not in existing_columns:
            issues.append(f"Missing column: {expected['name']}")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "schema_version": SCHEMA_VERSION
    }
```

### 6.3 Backup and Rollback Strategy

Since this is a read-only analytics platform connecting to an external database:

**What Needs Backup:**
1. ChromaDB vector store (trained queries)
2. Configuration files
3. Generated reports
4. User preferences/saved queries (if implemented)

**Backup Script:**
```bash
#!/bin/bash
# scripts/backup.sh

BACKUP_DIR="/backups/depotru/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

# Backup ChromaDB
cp -r ~/.chroma "$BACKUP_DIR/chromadb"

# Backup configuration (without secrets)
cp src/config.py "$BACKUP_DIR/"
cp .env.example "$BACKUP_DIR/"

# Backup generated reports
cp -r ~/business_reports "$BACKUP_DIR/reports"

# Compress
tar -czf "$BACKUP_DIR.tar.gz" "$BACKUP_DIR"
rm -rf "$BACKUP_DIR"

# Upload to S3/Azure (optional)
# aws s3 cp "$BACKUP_DIR.tar.gz" s3://depotru-backups/
```

**Rollback Procedure:**
```bash
#!/bin/bash
# scripts/rollback.sh

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: ./rollback.sh <backup_file.tar.gz>"
    exit 1
fi

# Extract
tar -xzf "$BACKUP_FILE" -C /tmp

# Restore ChromaDB
rm -rf ~/.chroma
cp -r /tmp/*/chromadb ~/.chroma

echo "Rollback complete. Restart services."
```

### 6.4 CI/CD Pipeline Recommendations

**Proposed Pipeline:**

```yaml
# .github/workflows/production.yml
name: Production Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  # Stage 1: Quality Checks
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install black flake8 mypy isort bandit

      - name: Code formatting check
        run: black --check src/ tests/

      - name: Import sorting check
        run: isort --check src/ tests/

      - name: Linting
        run: flake8 src/ tests/

      - name: Type checking
        run: mypy src/ --ignore-missing-imports

      - name: Security scan
        run: bandit -r src/ -ll

  # Stage 2: Tests
  test:
    needs: quality
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y freetds-dev unixodbc-dev
          pip install -r requirements.txt

      - name: Run tests
        run: pytest tests/ -v --cov=src --cov-report=xml
        env:
          TESTING: "true"

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        if: matrix.python-version == '3.12'

  # Stage 3: Build
  build:
    needs: test
    runs-on: ubuntu-latest
    outputs:
      image_tag: ${{ steps.meta.outputs.tags }}

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Docker meta
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository }}
          tags: |
            type=sha,prefix=
            type=ref,event=branch
            type=semver,pattern={{version}}

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: ${{ github.event_name != 'pull_request' }}
          tags: ${{ steps.meta.outputs.tags }}

  # Stage 4: Deploy to Staging
  deploy-staging:
    needs: build
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: staging

    steps:
      - name: Deploy to staging
        run: |
          # Add deployment commands (kubectl, docker, etc.)
          echo "Deploying to staging..."

  # Stage 5: Deploy to Production (Manual Approval)
  deploy-production:
    needs: deploy-staging
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: production

    steps:
      - name: Deploy to production
        run: |
          echo "Deploying to production..."
```

### 6.5 Logging, Monitoring, and Observability

**Recommended Stack:**
- **Logs**: ELK Stack (Elasticsearch, Logstash, Kibana) or CloudWatch Logs
- **Metrics**: Prometheus + Grafana
- **Tracing**: OpenTelemetry + Jaeger
- **Alerting**: PagerDuty/Opsgenie

**Implementation:**

```python
# src/observability/logging.py
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }

        # Add extra fields
        if hasattr(record, "user"):
            log_entry["user"] = record.user
        if hasattr(record, "query"):
            log_entry["query"] = record.query
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms

        return json.dumps(log_entry)

def setup_logging():
    """Configure structured logging."""
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

    logger = logging.getLogger("depotru")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    return logger
```

```python
# src/observability/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Metrics
QUERY_COUNT = Counter(
    "depotru_queries_total",
    "Total queries executed",
    ["status", "query_type"]
)

QUERY_DURATION = Histogram(
    "depotru_query_duration_seconds",
    "Query execution duration",
    ["query_type"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

ACTIVE_USERS = Gauge(
    "depotru_active_users",
    "Number of active users"
)

AI_API_CALLS = Counter(
    "depotru_ai_api_calls_total",
    "AI API calls",
    ["provider", "status"]
)
```

### 6.6 Containerization (Docker)

**Dockerfile:**
```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    freetds-dev \
    unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ src/
COPY data/ data/

# Non-root user for security
RUN useradd -m appuser
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8084/health || exit 1

EXPOSE 8084

CMD ["python", "-m", "src.api.main"]
```

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8084:8084"
    environment:
      - ENVIRONMENT=production
    env_file:
      - .env.production
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8084/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
    restart: unless-stopped

volumes:
  redis_data:
  grafana_data:
```

---

## 7. Testing Strategy

### 7.1 Current Test Coverage Assessment

| Test Category | Files | Coverage | Assessment |
|---------------|-------|----------|------------|
| **Unit Tests** | 6 files | ~40% | Needs improvement |
| **Integration Tests** | 2 files | ~10% | Severely lacking |
| **Security Tests** | 1 file | ~5% | Good foundation |
| **End-to-End Tests** | 0 files | 0% | Missing |
| **Performance Tests** | 0 files | 0% | Missing |

### 7.2 What Types of Tests Are Missing

**Missing Test Categories:**

1. **Integration Tests with Real Database**
   ```python
   # tests/integration/test_database.py
   @pytest.mark.integration
   @pytest.mark.requires_db
   def test_database_connection():
       """Test actual database connectivity."""
       ...

   def test_query_execution():
       """Test query execution against real database."""
       ...
   ```

2. **API Endpoint Tests**
   ```python
   # tests/api/test_endpoints.py
   def test_natural_language_query_endpoint(client):
       """Test /api/v1/query/natural-language."""
       response = client.post("/api/v1/query/natural-language", json={
           "question": "Top 10 productos"
       })
       assert response.status_code == 200
       assert "data" in response.json()
   ```

3. **Performance/Load Tests**
   ```python
   # tests/performance/test_load.py
   import locust

   class QueryUser(locust.HttpUser):
       @locust.task
       def query_products(self):
           self.client.post("/api/v1/query/natural-language", json={
               "question": "Top productos vendidos"
           })
   ```

4. **End-to-End Tests**
   ```python
   # tests/e2e/test_workflow.py
   def test_full_analysis_workflow():
       """Test complete user workflow: login -> query -> report."""
       ...
   ```

### 7.3 How to Test Database Integrity and Migrations

Since this connects to an external database:

```python
# tests/database/test_schema_integrity.py
import pytest
from src.database.schema_validator import validate_schema

class TestSchemaIntegrity:
    """Test external database schema matches expectations."""

    @pytest.mark.requires_db
    def test_required_columns_exist(self, db_connection):
        """Verify all required columns exist in banco_datos."""
        result = validate_schema(db_connection)
        assert result["valid"], f"Schema issues: {result['issues']}"

    @pytest.mark.requires_db
    def test_data_types_correct(self, db_connection):
        """Verify column data types match expectations."""
        ...

    @pytest.mark.requires_db
    def test_no_orphaned_records(self, db_connection):
        """Check referential integrity (soft check)."""
        ...
```

### 7.4 Suggested Tools and Test Structure

```
tests/
├── conftest.py                    # Shared fixtures
├── unit/
│   ├── test_config.py
│   ├── test_formatting.py
│   ├── test_sql_validation.py
│   └── test_metrics_calculator.py
├── integration/
│   ├── test_database_connection.py
│   ├── test_vanna_integration.py
│   └── test_ai_providers.py
├── api/
│   ├── test_auth.py
│   ├── test_query_endpoints.py
│   └── test_report_endpoints.py
├── security/
│   ├── test_sql_injection.py
│   ├── test_auth_bypass.py
│   └── test_rate_limiting.py
├── performance/
│   ├── test_load.py
│   └── test_memory.py
└── e2e/
    ├── test_user_workflow.py
    └── test_dashboard.py
```

**Recommended Test Tools:**
- `pytest` - Test runner
- `pytest-cov` - Coverage reporting
- `pytest-asyncio` - Async test support
- `httpx` - Async HTTP client for API tests
- `locust` - Load testing
- `hypothesis` - Property-based testing
- `faker` - Test data generation
- `pytest-mock` - Mocking
- `pytest-snapshot` - Snapshot testing for reports

---

## 8. Roadmap & Next Steps

### Phase 1: Stabilization & Fixes (Immediate - 1-2 weeks)

**Priority: CRITICAL**

| Task | File | Effort | Impact |
|------|------|--------|--------|
| Fix duplicate API calls | `vanna_grok.py:527-539` | 5 min | HIGH - Cost savings |
| Fix SQL injection in Streamlit | `streamlit_dashboard.py:59` | 30 min | HIGH - Security |
| Add connection pooling | `business_analyzer_combined.py` | 2 hrs | HIGH - Performance |
| Add rate limiting | `vanna_grok.py` | 2 hrs | MEDIUM - Cost/Security |
| Add basic authentication | All web endpoints | 4 hrs | HIGH - Security |
| Add structured logging | All files | 3 hrs | MEDIUM - Observability |

**Deliverables:**
- [ ] All critical security vulnerabilities fixed
- [ ] Connection pooling implemented
- [ ] Basic auth protecting all endpoints
- [ ] Structured JSON logging enabled

### Phase 2: Hardening for Production (1-2 weeks)

**Priority: HIGH**

| Task | Description | Effort |
|------|-------------|--------|
| Modularize codebase | Split `business_analyzer_combined.py` into modules | 1 day |
| Add comprehensive tests | Unit, integration, API tests | 3 days |
| Docker containerization | Dockerfile + docker-compose | 1 day |
| CI/CD pipeline enhancement | Add staging/production deployment | 1 day |
| Secrets management | Integrate AWS Secrets Manager/Azure Key Vault | 1 day |
| Schema validation | Add startup validation for external DB | 2 hrs |
| API documentation | OpenAPI spec + Swagger UI | 4 hrs |

**Deliverables:**
- [ ] Test coverage > 70%
- [ ] Docker images published to container registry
- [ ] Automated deployment pipeline to staging
- [ ] Secrets externalized to secret manager
- [ ] API documentation live at `/api/docs`

### Phase 3: Scalability & Future Growth (2-4 weeks)

**Priority: MEDIUM**

| Task | Description | Effort |
|------|-------------|--------|
| Migrate to FastAPI | Replace Flask for better performance | 2 days |
| Add Redis caching | Cache frequent queries | 1 day |
| Implement query queue | Async query processing with Celery | 2 days |
| Add monitoring stack | Prometheus + Grafana | 1 day |
| Multi-tenancy support | Separate data by organization | 3 days |
| Horizontal scaling | Kubernetes deployment | 2 days |
| GraphQL API (optional) | For complex frontend needs | 3 days |

**Deliverables:**
- [ ] API response times < 200ms (p95)
- [ ] Support 100+ concurrent users
- [ ] Real-time monitoring dashboards
- [ ] Auto-scaling based on load
- [ ] Multi-tenant architecture ready

---

## Appendix A: Quick Fixes (Copy-Paste Ready)

### Fix CRITICAL-01: Remove Duplicate API Calls

```python
# In src/vanna_grok.py, REMOVE lines 527-539:
# DELETE THIS BLOCK:
# ========== ENHANCEMENT 2: AI Insights ==========
# Get Grok client for insights
grok_client = OpenAI(
    api_key=Config.GROK_API_KEY, base_url="https://api.x.ai/v1"
)

insights = generate_insights(
    question=question,
    sql=sql,
    df=df,  # Use original unformatted data for analysis
    grok_client=grok_client,
)

print(insights)
```

### Fix CRITICAL-04: Parameterize Streamlit Query

```python
# In examples/streamlit_dashboard.py, replace lines 55-74 with:
@st.cache_data(ttl=3600)
def load_data(connection_string: str, start_date: str, end_date: str, limit: int = 50000):
    """Load data from database with caching and parameterized queries."""
    engine = create_engine(connection_string)

    query = """
    SELECT TOP (:limit)
        Fecha,
        TotalMasIva,
        TotalSinIva,
        ValorCosto,
        Cantidad,
        TercerosNombres as customer_name,
        ArticulosNombre as product_name,
        ArticulosCodigo as product_code,
        categoria as category,
        subcategoria as subcategory
    FROM banco_datos
    WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
        AND Fecha BETWEEN :start_date AND :end_date
    """

    df = pd.read_sql(
        query,
        engine,
        params={"limit": limit, "start_date": start_date, "end_date": end_date}
    )
    return df
```

---

## Appendix B: Recommended Reading

1. **FastAPI Best Practices**: https://fastapi.tiangolo.com/deployment/
2. **SQLAlchemy 2.0 Tutorial**: https://docs.sqlalchemy.org/en/20/tutorial/
3. **12-Factor App Methodology**: https://12factor.net/
4. **OWASP API Security Top 10**: https://owasp.org/API-Security/
5. **Prometheus Python Client**: https://github.com/prometheus/client_python

---

## Conclusion

This repository demonstrates strong foundations in security awareness, documentation, and AI integration. The critical issues identified are common in rapidly developed analytics platforms and are addressable within a few weeks.

**Top 3 Priorities:**
1. **Fix the duplicate API calls** - Immediate cost savings
2. **Add authentication** - Security requirement
3. **Implement connection pooling** - Performance/stability

Following this roadmap will transform this codebase from a solid prototype into a production-ready business intelligence platform suitable for enterprise deployment.

---

*Analysis performed by Claude (Opus 4.5) on 2026-01-19*
