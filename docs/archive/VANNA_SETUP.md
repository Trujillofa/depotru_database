# 🤖 Vanna AI Integration - Chat with Your Database

> **Ask questions in plain English, get SQL queries and results automatically!**

Instead of writing complex Python scripts or SQL queries, just ask:
- *"What are my top 10 selling products?"*
- *"Show me revenue by customer this month"*
- *"Which products have low profit margins?"*

---

## 🎯 What is Vanna AI?

Vanna is an open-source framework that converts **natural language → SQL → Results**.

**How it works:**
1. You ask a question in plain English
2. Vanna generates the SQL query
3. Executes it against your database
4. Returns results with charts and tables

**Benefits over current approach:**
- No coding needed for users
- Interactive web interface
- Learns your database schema
- Gets smarter over time
- Can generate visualizations automatically

---

## 🚀 Quick Start (15 minutes)

### Option 1: Cloud Setup (Easiest) - OpenAI + Vanna

**Requirements:**
- OpenAI API key (~$0.01 per question)
- Internet connection

```bash
# 1. Install Vanna
pip install vanna pyodbc

# 2. Set your API key
export OPENAI_API_KEY='sk-your-key-here'

# 3. Configure database connection in vanna_chat.py
nano vanna_chat.py
# Edit DB_SERVER, DB_NAME, DB_USER, DB_PASSWORD

# 4. Run
python vanna_chat.py

# 5. Open browser
open http://localhost:8084
```

---

### Option 2: Grok (xAI) - New! 🆕

**Requirements:**
- Grok API key from x.ai (~$0.01 per question)
- Internet connection

```bash
# 1. Install Vanna
pip install vanna chromadb pyodbc

# 2. Get Grok API key
# Visit: https://console.x.ai
# Create account and get API key

# 3. Set your API key
export GROK_API_KEY='xai-your-key-here'

# 4. Configure src/vanna_chat.py
# Set: USE_GROK = True
# Set: USE_OPENAI = False
# Set: USE_OLLAMA = False
# Set: USE_ANTHROPIC = False

# 5. Run
python src/vanna_chat.py

# 6. Open browser
open http://localhost:8084
```

**Why Grok?**
- ✅ Fast responses
- ✅ Good at complex queries
- ✅ OpenAI-compatible API (easy to integrate)
- ✅ Competitive pricing

---

### Option 3: Local Setup (Free & Private) - Ollama + ChromaDB

**Requirements:**
- Ollama installed (runs LLM locally)
- 8GB+ RAM recommended

```bash
# 1. Install Ollama (Mac/Linux)
curl https://ollama.ai/install.sh | sh

# 2. Download a model
ollama pull mistral
# Or for better results:
ollama pull llama2

# 3. Install Python packages
pip install vanna chromadb pyodbc

# 4. Configure vanna_chat.py
nano vanna_chat.py
# Set: USE_OPENAI = False
# Set: USE_OLLAMA = True

# 5. Run
python vanna_chat.py

# 6. Open browser
open http://localhost:8084
```

**Pros:** Completely free, data stays on your machine
**Cons:** Slower, requires good hardware

---

### Option 3: Anthropic Claude

```bash
# 1. Install
pip install vanna anthropic chromadb pyodbc

# 2. Set API key
export ANTHROPIC_API_KEY='sk-ant-...'

# 3. Configure vanna_chat.py
# Set: USE_OPENAI = False
# Set: USE_ANTHROPIC = True

# 4. Run
python vanna_chat.py
```

---

## 📋 Configuration

Edit `src/vanna_chat.py` with your settings:

```python
# Choose your LLM provider (enable only ONE)
USE_OPENAI = True      # Recommended for best results
USE_GROK = False       # 🆕 xAI Grok - Fast and capable
USE_OLLAMA = False     # Free, local, private
USE_ANTHROPIC = False  # Claude - Excellent quality

# Database connection (your SmartBusiness SQL Server)
DB_SERVER = "your-server"
DB_NAME = "SmartBusiness"
DB_USER = "your-username"
DB_PASSWORD = "your-password"
```

Or use environment variables:

```bash
# Choose ONE AI provider
export OPENAI_API_KEY='sk-...'              # OpenAI
export GROK_API_KEY='xai-...'               # 🆕 Grok (xAI)
export ANTHROPIC_API_KEY='sk-ant-...'       # Anthropic

# Database credentials
export DB_SERVER='your-server'
export DB_NAME='SmartBusiness'
export DB_USER='your-username'
export DB_PASSWORD='your-password'

python src/vanna_chat.py
```

---

## 💬 Example Questions You Can Ask

Once running, try these questions in the chat interface:

### Revenue & Sales
- *"What's my total revenue this month?"*
- *"Show me revenue by month for 2025"*
- *"What were my sales last week?"*
- *"Compare revenue this month vs last month"*

### Products
- *"What are my top 10 selling products?"*
- *"Which products have the highest profit margin?"*
- *"Show me products with low margins below 10%"*
- *"What's the best selling product in each category?"*

### Customers
- *"Who are my top 5 customers?"*
- *"Which customers buy the most frequently?"*
- *"Show me new customers this month"*
- *"What's the average order value by customer?"*

### Categories
- *"How are my product categories performing?"*
- *"Which category has the best profit margin?"*
- *"Show me sales by category and subcategory"*

### Trends
- *"Show me the sales trend over the last 6 months"*
- *"Which day of the week has the most sales?"*
- *"Compare this quarter to last quarter"*

### Advanced
- *"Which products are selling but losing money?"*
- *"Show me the 80/20 analysis - top products making 80% of revenue"*
- *"What's the customer concentration - how much do top 10 customers represent?"*

---

## 🔧 How Training Works

Vanna learns from three sources:

### 1. Database Schema (DDL)
Automatically reads your table structure:
```sql
-- Vanna learns this:
CREATE TABLE banco_datos (
    Fecha DATE,
    TotalMasIva DECIMAL,
    TercerosNombres NVARCHAR,
    ...
);
```

### 2. Documentation
Business context you provide:
```
- TotalMasIva = revenue WITH tax
- Always exclude DocumentosCodigo IN ('XY', 'AS', 'TS')
- Profit = TotalSinIva - ValorCosto
```

### 3. Example SQL Queries
The more examples you provide, the better it gets:
```sql
-- Question: Top customers
SELECT TercerosNombres, SUM(TotalMasIva) as revenue
FROM banco_datos
WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
GROUP BY TercerosNombres
ORDER BY revenue DESC
```

**The script already includes training for your SmartBusiness database!**

---

## 📊 Adding More Training Data

To make Vanna smarter, add more example queries:

```python
# In vanna_chat.py, add to train_vanna_on_schema():

# Example: Customer retention
vn.train(sql="""
    -- Question: Show me repeat customers
    SELECT
        TercerosNombres,
        COUNT(DISTINCT CONVERT(DATE, Fecha)) as days_purchased,
        MIN(Fecha) as first_purchase,
        MAX(Fecha) as last_purchase
    FROM banco_datos
    WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
    GROUP BY TercerosNombres
    HAVING COUNT(DISTINCT CONVERT(DATE, Fecha)) > 1
    ORDER BY days_purchased DESC
""")
```

---

## 🆚 Comparison: Vanna vs Current Script

| Feature | Current Script | Vanna AI |
|---------|----------------|----------|
| **Interface** | Command line | Web chat |
| **Query Method** | Predefined Python | Natural language |
| **Flexibility** | Fixed reports | Ask anything |
| **Learning** | Manual coding | Learns from examples |
| **Visualizations** | Static PNG | Interactive charts |
| **User Skill** | Needs Python | No coding needed |
| **New Questions** | Requires code changes | Just ask |
| **Speed** | Fast (direct SQL) | Slightly slower (LLM) |
| **Cost** | Free | Free (Ollama) or ~$0.01/question |

**When to use Vanna:**
- ✅ Ad-hoc questions
- ✅ Non-technical users
- ✅ Exploratory analysis
- ✅ Quick insights

**When to use current script:**
- ✅ Automated reports
- ✅ Scheduled jobs
- ✅ Complex business logic
- ✅ Batch processing

---

## 🔒 Security Considerations

### Cloud Setup (OpenAI/Anthropic)
- Your database schema is sent to the LLM
- Query results are processed by the LLM
- Consider data sensitivity

### Local Setup (Ollama)
- Everything stays on your machine
- No data sent externally
- Recommended for sensitive data

### Production Deployment
- Add authentication to the Flask app
- Use SSL/TLS
- Implement rate limiting
- Consider row-level security

---

## 🐛 Troubleshooting

### "Connection failed"
```bash
# Check ODBC driver is installed
pip install pyodbc

# For Linux, install unixODBC and MS driver:
# See: https://docs.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server
```

### "API key error"
```bash
# Make sure environment variable is set
echo $OPENAI_API_KEY

# Or set directly in script
OPENAI_API_KEY = "sk-..."
```

### "Ollama not running"
```bash
# Start Ollama
ollama serve

# Check it's running
curl http://localhost:11434/api/tags
```

### "Model not found"
```bash
# Download model first
ollama pull mistral
```

### "SQL generation not accurate"
- Add more training examples
- Be more specific in your questions
- Add documentation about your data

---

## 📚 Resources

- **Vanna GitHub:** https://github.com/vanna-ai/vanna
- **Vanna Docs:** https://vanna.ai/docs/
- **SQL Server Setup:** https://vanna.ai/docs/mssql-openai-vanna-vannadb/
- **Ollama:** https://ollama.ai/

---

## 🎯 Recommended Setup

### For Quick Testing
Use **OpenAI** (best results, ~$0.01/question):
```bash
pip install vanna pyodbc
export OPENAI_API_KEY='sk-...'
python vanna_chat.py
```

### For Production / Privacy
Use **Ollama** (free, local, private):
```bash
pip install vanna chromadb pyodbc
ollama pull mistral
python vanna_chat.py
```

### For Enterprise
Consider:
- Vanna Cloud (managed service)
- Self-hosted with authentication
- Row-level security integration

---

## ✨ Summary

**Vanna AI lets you chat with your database!**

Instead of:
```python
# Writing complex Python code
calculator = BusinessMetricsCalculator(data)
metrics = calculator.calculate_financial_metrics()
```

Just ask:
```
"What's my revenue this month?"
```

**Try it now:**
```bash
pip install vanna pyodbc
export OPENAI_API_KEY='sk-...'
python vanna_chat.py
# Open http://localhost:8084
```

---

## 🤝 Integration with Current System

You can use **both** systems together:

1. **Vanna AI** for ad-hoc questions and exploration
2. **business_analyzer_combined.py** for scheduled reports
3. **Streamlit dashboard** for team dashboards
4. **Metabase** for business user dashboards

They all connect to the same SmartBusiness database!

---

**Questions?** Check the Vanna documentation or ask in the chat interface!
