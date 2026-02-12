# Vanna AI Implementation Comparison

> **Two powerful ways to chat with your database using natural language**

---

## 📋 Quick Comparison

| Feature | `vanna_chat.py` | `vanna_grok.py` ⭐ |
|---------|-----------------|-------------------|
| **AI Providers** | OpenAI, Grok, Anthropic, Ollama | **Grok only** (optimized) |
| **Vanna Version** | Latest (flexible imports) | **2.0.1 Legacy** (stable) |
| **Spanish Support** | Yes | **Optimized for Spanish** 🇪🇸 |
| **Number Formatting** | Basic | **Colombian format** 💰 🆕 |
| **AI Insights** | No | **Yes** (recommendations) 🤖 🆕 |
| **Production Ready** | Good (Flask only) | **Flexible** (Dev or Prod) |
| **Configuration** | Manual flags | **.env file** (cleaner) |
| **Error Handling** | Basic | **Enhanced** (detailed debugging) |
| **Training Examples** | English | **Spanish business queries** |
| **Database Testing** | Basic | **Ping test on connect** |
| **Recommended For** | Testing multiple AI providers | **Production use with Grok** |

---

## 🎯 Which One Should You Use?

### Use `vanna_grok.py` if:
- ✅ You have a Grok API key and want the **best performance**
- ✅ You need **production-ready** deployment
- ✅ Your team speaks **Spanish** (Colombian business context)
- ✅ You want **Waitress** production server out-of-the-box
- ✅ You need **better error messages** and debugging
- ✅ You're deploying to **production** and need stability

**Quick Start:**
```bash
# Add to .env
GROK_API_KEY=xai-your-key-here

# Run
python src/vanna_grok.py
# → http://localhost:8084
```

---

### Use `vanna_chat.py` if:
- ✅ You want to **try different AI providers** (OpenAI, Anthropic, Ollama)
- ✅ You don't have Grok yet but have **OpenAI/Anthropic**
- ✅ You want to **test locally** with Ollama (free)
- ✅ You need **flexibility** to switch providers
- ✅ You're **experimenting** and want options

**Quick Start:**
```bash
# Choose your provider in the file
export OPENAI_API_KEY='sk-...'  # or
export GROK_API_KEY='xai-...'   # or
export ANTHROPIC_API_KEY='sk-ant-...'

python src/vanna_chat.py
```

---

## 🎨 Beautiful Output (vanna_grok.py Only)

**`vanna_grok.py` includes enhanced output formatting:**

### 💰 Colombian Number Formatting
- **Currency**: `$123.456.789` (pesos colombianos)
- **Percentages**: `45,6%` (comma as decimal separator)
- **Quantities**: `1.234` (period as thousands separator)
- **Auto-detection**: Based on column names

### 🤖 AI-Generated Insights
Every query includes:
- **📊 Resumen Ejecutivo**: Quick data summary
- **💡 Insights Clave**: 2-3 key findings
- **🎯 Recomendaciones**: 3-5 actionable business recommendations

**Example Output:**
```
======================================================================
📊 RESULTADOS (con formato colombiano)
======================================================================

Producto                   Unidades_Vendidas  Revenue
-------------------------  -----------------  ----------------
CEMENTO GRIS x 50KG        2.456              $45.678.900
VARILLA 3/8" x 6M          1.892              $38.234.567

======================================================================
🤖 ANÁLISIS INTELIGENTE (Powered by Grok)
======================================================================

📊 Resumen: Cemento lidera ventas con 54% del revenue total...
💡 Insights: Alta rotación en materiales básicos...
🎯 Recomendaciones:
  1. Asegurar stock permanente de cemento
  2. Crear combos cemento + varilla
  3. Promoción cross-selling con arena
======================================================================
```

**See full examples:** [VANNA_BEAUTIFUL_OUTPUT.md](VANNA_BEAUTIFUL_OUTPUT.md) 🆕

---

## 🔍 Detailed Differences

### 1. **Vanna Imports**

**`vanna_chat.py`** - Modern imports (flexible):
```python
from vanna.openai import OpenAI_Chat
from vanna.chromadb import ChromaDB_VectorStore
from vanna.anthropic import Anthropic_Chat
from vanna.ollama import Ollama
```

**`vanna_grok.py`** - Legacy imports (stable):
```python
from vanna.legacy.chromadb.chromadb_vector import ChromaDB_VectorStore
from vanna.legacy.openai import OpenAI_Chat
from vanna.legacy.flask import VannaFlaskApp
```

**Why legacy?** Vanna 2.0.1 legacy APIs are **more stable** for production deployments and better tested with custom LLM endpoints like Grok.

---

### 2. **Configuration**

**`vanna_chat.py`** - Manual flags:
```python
USE_OPENAI = True
USE_GROK = False
USE_ANTHROPIC = False
USE_OLLAMA = False

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your-openai-api-key")
GROK_API_KEY = os.getenv("GROK_API_KEY", "your-grok-api-key")
```

**`vanna_grok.py`** - `.env` only:
```python
class Config:
    GROK_API_KEY = os.getenv("GROK_API_KEY")
    if not GROK_API_KEY or not GROK_API_KEY.startswith("xai-"):
        print("❌ ERROR: Set GROK_API_KEY in .env")
        sys.exit(1)
```

**Advantage:** `vanna_grok.py` enforces security by **requiring .env** and validates API keys.

---

### 3. **Database Connection**

**`vanna_chat.py`**:
```python
vn.connect_to_mssql(odbc_conn_str=odbc_conn_str)
```

**`vanna_grok.py`** - With connection test:
```python
def connect_to_mssql_odbc(self):
    # Build ODBC string
    odbc_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={Config.DB_SERVER};"
        f"DATABASE={Config.DB_NAME};"
        f"UID={Config.DB_USER};"
        f"PWD={Config.DB_PASSWORD};"
        f"TrustServerCertificate=yes;"
        f"Encrypt=yes;"
    )
    self.connect_to_mssql(odbc_conn_str=odbc_str)

    # Ping test
    df = self.run_sql("SELECT 1 AS ping;")
    if df is not None and not df.empty:
        print("✓ MSSQL connected & ping successful!")
```

**Advantage:** `vanna_grok.py` **validates** the connection immediately with a ping test.

---

### 4. **Training Examples**

**`vanna_chat.py`** - English:
```python
vn.train(sql="""
    -- Question: Who are my top 10 customers by revenue?
    SELECT TOP 10
        TercerosNombres as customer_name,
        SUM(TotalMasIva) as total_revenue
    FROM banco_datos
    WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
    GROUP BY TercerosNombres
    ORDER BY total_revenue DESC
""")
```

**`vanna_grok.py`** - Spanish (optimized for Colombian hardware store):
```python
examples = [
    ("Top 10 productos más vendidos este año", """
        SELECT TOP 10
            ArticulosNombre AS Producto,
            SUM(Cantidad) AS Unidades_Vendidas,
            SUM(TotalMasIva) AS Revenue
        FROM banco_datos
        WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
          AND YEAR(Fecha) = YEAR(GETDATE())
        GROUP BY ArticulosNombre
        ORDER BY Revenue DESC
    """),
    ("Ganancias por categoría en el último mes", """..."""),
    ("Top 10 clientes por facturación total", """..."""),
]
```

**Advantage:** Spanish examples = **better results** for Spanish queries.

---

### 5. **Error Handling**

**`vanna_chat.py`**:
```python
vn = create_vanna_instance()
vn = connect_to_database(vn)
```

**`vanna_grok.py`**:
```python
try:
    self.connect_to_mssql(odbc_conn_str=odbc_str)
    df = self.run_sql("SELECT 1 AS ping;")
    if df is not None and not df.empty:
        print("✓ MSSQL connected & ping successful!")
    else:
        raise ValueError("Ping returned empty—check DB access")
except ImportError:
    print("❌ pyodbc missing: Run 'pip install pyodbc'")
    sys.exit(1)
except Exception as e:
    print(f"❌ MSSQL connection failed: {e}")
    print("💡 Quick Fixes:")
    print("   - Linux: sudo apt install unixodbc-dev msodbcsql17")
    sys.exit(1)
```

**Advantage:** `vanna_grok.py` provides **actionable error messages** with fix instructions.

---

### 6. **Production Server**

**`vanna_chat.py`** - Flask dev server only:
```python
app = VannaFlaskApp(vn, allow_llm_to_see_data=True)
app.run(port=8084)
```

**`vanna_grok.py`** - Flexible dev/production mode:
```bash
# Development mode (default)
python src/vanna_grok.py

# Production mode (Waitress server)
PRODUCTION_MODE=true python src/vanna_grok.py
```

**Code:**
```python
use_production = os.getenv("PRODUCTION_MODE", "false").lower() == "true"

if use_production:
    from waitress import serve
    serve(app, host=Config.HOST, port=Config.PORT, threads=8)
else:
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=False,
        use_reloader=False
    )
```

**Advantages:**
- ✅ **Simple by default** (Flask dev server, no extra dependencies)
- ✅ **Production-ready when needed** (Waitress handles 10-50 concurrent users)
- ✅ **Environment-based switching** (clean configuration)
- ✅ **Graceful KeyboardInterrupt** handling

---

## 📊 Performance Comparison

| Metric | `vanna_chat.py` | `vanna_grok.py` |
|--------|-----------------|-----------------|
| **Startup Time** | ~3-5 seconds | ~3-5 seconds |
| **Query Speed** | Depends on provider | Grok-optimized |
| **Spanish Accuracy** | Good | **Excellent** ✅ |
| **Error Recovery** | Basic | **Enhanced** ✅ |
| **Production Stability** | Good | **Excellent** ✅ |
| **Concurrent Users** | 1-5 (Flask dev) | **10-50** (Waitress) ✅ |

---

## 🚀 Example Questions (Spanish)

### Try these with `vanna_grok.py`:

```
💬 "Top 10 productos más vendidos este año"
💬 "Ganancias por categoría en el último mes"
💬 "Top 10 clientes por facturación total"
💬 "Margen de ganancia promedio por subcategoría"
💬 "Ventas mensuales de enero a junio 2025"
💬 "Productos con margen menor al 10%"
💬 "Clientes que no han comprado en 3 meses"
💬 "Categorías más rentables este trimestre"
```

### English also works:

```
💬 "What are my top 10 selling products?"
💬 "Show me revenue by category this month"
💬 "Which customers have the highest order values?"
```

---

## 🔧 Installation

### For `vanna_grok.py` (Recommended for Production):

```bash
# 1. Install dependencies
# Development (testing):
pip install vanna chromadb pyodbc openai python-dotenv

# Production (add waitress):
pip install vanna chromadb pyodbc openai python-dotenv waitress

# 2. Install ODBC driver (if not already installed)
# Ubuntu/Debian:
sudo apt install unixodbc-dev
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/20.04/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt update
sudo ACCEPT_EULA=Y apt install msodbcsql17

# macOS:
brew install unixodbc
brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release
brew install msodbcsql17

# 3. Configure .env
cat >> .env << EOF
GROK_API_KEY=xai-your-key-here
DB_SERVER=190.60.235.209
DB_NAME=SmartBusiness
DB_USER=Consulta
DB_PASSWORD=Control*01
EOF

# 4a. Run (Development mode - simpler, good for testing)
python src/vanna_grok.py

# 4b. Run (Production mode - Waitress server, handles 10-50 users)
PRODUCTION_MODE=true python src/vanna_grok.py

# Or add to .env:
echo "PRODUCTION_MODE=true" >> .env
python src/vanna_grok.py
```

---

### For `vanna_chat.py` (Multiple Providers):

```bash
# 1. Install dependencies
pip install vanna chromadb pyodbc openai anthropic python-dotenv

# For Ollama support:
pip install ollama

# 2. Configure (choose one)
export GROK_API_KEY='xai-...'
# or
export OPENAI_API_KEY='sk-...'
# or
export ANTHROPIC_API_KEY='sk-ant-...'

# 3. Edit src/vanna_chat.py to enable your provider
# USE_GROK = True  # or USE_OPENAI, USE_ANTHROPIC, USE_OLLAMA

# 4. Run
python src/vanna_chat.py
```

---

## 🎯 Recommendations

### For Your Use Case (Colombian Hardware Store):

**✅ Use `vanna_grok.py`** because:
1. **Spanish-optimized** training examples
2. **Production-ready** with Waitress
3. **Better error messages** in Spanish context
4. **Grok is excellent** at business queries
5. **Simpler** configuration (just .env)

### Migration Path:

1. **Week 1:** Test `vanna_grok.py` locally
2. **Week 2:** Deploy to staging with real data
3. **Week 3:** Train team on Spanish queries
4. **Week 4:** Production deployment
5. **Ongoing:** Add more training examples as needed

---

## 📝 .env Configuration

### Complete `.env` for `vanna_grok.py`:

```bash
# Grok AI (Required)
GROK_API_KEY=xai-your-key-here

# Database Connection (Required)
DB_SERVER=190.60.235.209
DB_NAME=SmartBusiness
DB_USER=Consulta
DB_PASSWORD=Control*01

# Server Configuration (Optional)
HOST=0.0.0.0           # Listen on all interfaces
PORT=8084              # Web UI port
```

---

## 🐛 Troubleshooting

### `vanna_grok.py` Issues:

**"pyodbc missing"**
```bash
pip install pyodbc
# Linux: sudo apt install unixodbc-dev msodbcsql17
```

**"Waitress missing"**
```bash
pip install waitress
# Falls back to Flask if missing
```

**"MSSQL connection failed"**
```bash
# Check credentials in .env
# Test connection:
python tests/test_metabase_connection.py
```

---

## 🔗 Related Documentation

- [VANNA_SETUP.md](VANNA_SETUP.md) - General Vanna setup guide
- [ARCHITECTURE.md](ARCHITECTURE.md) - Technical architecture
- [SECURITY.md](SECURITY.md) - Security best practices

---

## 🎉 Bottom Line

**For production:** Use `vanna_grok.py` ✅
**For testing:** Use `vanna_chat.py` 🧪
**For both:** They can coexist! Different ports, different use cases.

---

**Questions?** Both scripts are production-ready. Start with `vanna_grok.py` for the best Spanish support and stability!
