"""
Vanna AI Integration for SmartBusiness Database
================================================
Chat with your database using natural language!

Instead of writing SQL or running complex scripts, just ask questions like:
- "What are my top 10 selling products?"
- "Show me revenue by category this month"
- "Which customers have the highest order values?"
- "What's my profit margin by product?"

This uses Vanna AI to convert your questions into SQL queries automatically.

Setup Options:
1. Cloud (Easy): Use OpenAI/Anthropic/Grok API with Vanna or ChromaDB
2. Local (Private): Use Ollama + ChromaDB (runs entirely on your machine)

Requirements:
- pip install vanna
- pip install pyodbc (for SQL Server)
- Optional: pip install chromadb ollama (for local setup)

Usage:
    python vanna_chat.py

Then open http://localhost:8084 in your browser and start asking questions!
"""

import os
from typing import Optional

# ============================================================================
# CONFIGURATION - CHOOSE YOUR SETUP
# ============================================================================

# Option 1: Use OpenAI (Recommended for best results)
USE_OPENAI = True
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your-openai-api-key")

# Option 2: Use local Ollama (Free, runs on your machine)
USE_OLLAMA = False
OLLAMA_MODEL = "mistral"  # or "llama2", "codellama"

# Option 3: Use Anthropic Claude
USE_ANTHROPIC = False
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "your-anthropic-api-key")

# Option 4: Use Grok (xAI)
USE_GROK = False
GROK_API_KEY = os.getenv("GROK_API_KEY", "your-grok-api-key")

# Database connection (your SmartBusiness SQL Server)
DB_SERVER = os.getenv("DB_SERVER", "your-server")
DB_NAME = os.getenv("DB_NAME", "SmartBusiness")
DB_USER = os.getenv("DB_USER", "your-username")
DB_PASSWORD = os.getenv("DB_PASSWORD", "your-password")

# ============================================================================
# SETUP VANNA
# ============================================================================

def create_vanna_instance():
    """Create Vanna instance based on configuration"""

    # Option 1: OpenAI + Vanna hosted vector DB (easiest setup)
    if USE_OPENAI:
        from vanna.openai import OpenAI_Chat
        from vanna.vannadb import VannaDB_VectorStore

        class MyVanna(VannaDB_VectorStore, OpenAI_Chat):
            def __init__(self, config=None):
                VannaDB_VectorStore.__init__(self, vanna_model='smartbusiness-model', vanna_api_key=os.getenv('VANNA_API_KEY', ''), config=config)
                OpenAI_Chat.__init__(self, config=config)

        vn = MyVanna(config={'api_key': OPENAI_API_KEY, 'model': 'gpt-4'})

    # Option 2: Local Ollama + ChromaDB (completely free, runs locally)
    elif USE_OLLAMA:
        from vanna.ollama import Ollama
        from vanna.chromadb import ChromaDB_VectorStore

        class MyVanna(ChromaDB_VectorStore, Ollama):
            def __init__(self, config=None):
                ChromaDB_VectorStore.__init__(self, config=config)
                Ollama.__init__(self, config=config)

        vn = MyVanna(config={
            'model': OLLAMA_MODEL,
            'ollama_host': 'http://localhost:11434'
        })

    # Option 3: Anthropic Claude
    elif USE_ANTHROPIC:
        from vanna.anthropic import Anthropic_Chat
        from vanna.chromadb import ChromaDB_VectorStore

        class MyVanna(ChromaDB_VectorStore, Anthropic_Chat):
            def __init__(self, config=None):
                ChromaDB_VectorStore.__init__(self, config=config)
                Anthropic_Chat.__init__(self, config=config)

        vn = MyVanna(config={
            'api_key': ANTHROPIC_API_KEY,
            'model': 'claude-3-sonnet-20240229'
        })

    # Option 4: Grok (xAI) - Uses OpenAI-compatible API
    elif USE_GROK:
        from vanna.openai import OpenAI_Chat
        from vanna.chromadb import ChromaDB_VectorStore

        class MyVanna(ChromaDB_VectorStore, OpenAI_Chat):
            def __init__(self, config=None):
                ChromaDB_VectorStore.__init__(self, config=config)
                # Override base_url and api_key for Grok
                config_with_grok = config or {}
                config_with_grok['base_url'] = 'https://api.x.ai/v1'
                config_with_grok['api_key'] = GROK_API_KEY
                OpenAI_Chat.__init__(self, config=config_with_grok)

        vn = MyVanna(config={
            'api_key': GROK_API_KEY,
            'model': 'grok-beta',  # or 'grok-vision-beta'
            'base_url': 'https://api.x.ai/v1'
        })

    else:
        raise ValueError("Please enable one of: USE_OPENAI, USE_OLLAMA, USE_ANTHROPIC, or USE_GROK")

    return vn


def connect_to_database(vn):
    """Connect Vanna to your SQL Server database"""

    # Build ODBC connection string
    odbc_conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={DB_NAME};"
        f"UID={DB_USER};"
        f"PWD={DB_PASSWORD}"
    )

    print(f"Connecting to SQL Server: {DB_SERVER}/{DB_NAME}")
    vn.connect_to_mssql(odbc_conn_str=odbc_conn_str)
    print("✓ Connected to database!")

    return vn


def train_vanna_on_schema(vn):
    """Train Vanna on your database schema"""

    print("\nTraining Vanna on your database schema...")

    # 1. Train on database schema (DDL)
    print("  - Loading table information...")
    df_ddl = vn.run_sql("""
        SELECT
            TABLE_SCHEMA,
            TABLE_NAME,
            COLUMN_NAME,
            DATA_TYPE,
            IS_NULLABLE,
            COLUMN_DEFAULT
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME IN ('banco_datos')
        ORDER BY TABLE_NAME, ORDINAL_POSITION
    """)

    # Add DDL information
    vn.train(ddl="""
        -- Main business data table
        -- Contains all sales transactions for hardware store
        CREATE TABLE banco_datos (
            Fecha DATE,                    -- Transaction date
            TotalMasIva DECIMAL(18,2),     -- Total amount WITH tax (IVA)
            TotalSinIva DECIMAL(18,2),     -- Total amount WITHOUT tax
            ValorCosto DECIMAL(18,2),      -- Product cost
            Cantidad INT,                  -- Quantity sold
            TercerosNombres NVARCHAR(200), -- Customer name
            ArticulosNombre NVARCHAR(200), -- Product name
            ArticulosCodigo NVARCHAR(50),  -- Product SKU/code
            DocumentosCodigo NVARCHAR(10), -- Document type (exclude XY, AS, TS)
            categoria NVARCHAR(100),       -- Product category
            subcategoria NVARCHAR(100)     -- Product subcategory
        );

        -- Note: Always filter out DocumentosCodigo IN ('XY', 'AS', 'TS') in queries
    """)

    # 2. Add documentation about the data
    print("  - Adding business context...")
    vn.train(documentation="""
        # SmartBusiness Database - Hardware Store Sales Data

        ## Key Tables
        - **banco_datos**: Main sales transactions table with all business data

        ## Important Fields
        - **TotalMasIva**: Revenue WITH tax (IVA) - use for total revenue calculations
        - **TotalSinIva**: Revenue WITHOUT tax - use for profit margin calculations
        - **ValorCosto**: Product cost - use to calculate profit
        - **TercerosNombres**: Customer name
        - **ArticulosNombre**: Product name
        - **categoria/subcategoria**: Product categorization

        ## Business Rules
        1. ALWAYS exclude documents with DocumentosCodigo IN ('XY', 'AS', 'TS')
        2. Profit = TotalSinIva - ValorCosto
        3. Profit Margin = (TotalSinIva - ValorCosto) / TotalSinIva * 100
        4. IVA (tax) = TotalMasIva - TotalSinIva

        ## Common Queries
        - Top customers by revenue: GROUP BY TercerosNombres, SUM(TotalMasIva)
        - Top products: GROUP BY ArticulosNombre, SUM(TotalMasIva)
        - Category performance: GROUP BY categoria, calculate profit margins
        - Monthly trends: GROUP BY YEAR(Fecha), MONTH(Fecha)
    """)

    # 3. Add example SQL queries (Vanna learns from these!)
    print("  - Adding example queries...")

    # Example: Top customers
    vn.train(sql="""
        -- Question: Who are my top 10 customers by revenue?
        SELECT TOP 10
            TercerosNombres as customer_name,
            SUM(TotalMasIva) as total_revenue,
            COUNT(*) as order_count,
            AVG(TotalMasIva) as avg_order_value
        FROM banco_datos
        WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
        GROUP BY TercerosNombres
        ORDER BY total_revenue DESC
    """)

    # Example: Top products
    vn.train(sql="""
        -- Question: What are my best selling products?
        SELECT TOP 10
            ArticulosNombre as product_name,
            SUM(TotalMasIva) as total_revenue,
            SUM(Cantidad) as units_sold,
            SUM(TotalSinIva) - SUM(ValorCosto) as profit,
            CASE
                WHEN SUM(TotalSinIva) > 0
                THEN (SUM(TotalSinIva) - SUM(ValorCosto)) / SUM(TotalSinIva) * 100
                ELSE 0
            END as profit_margin_pct
        FROM banco_datos
        WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
        GROUP BY ArticulosNombre
        ORDER BY total_revenue DESC
    """)

    # Example: Category performance
    vn.train(sql="""
        -- Question: How are my product categories performing?
        SELECT
            categoria as category,
            SUM(TotalMasIva) as total_revenue,
            SUM(TotalSinIva) - SUM(ValorCosto) as profit,
            CASE
                WHEN SUM(TotalSinIva) > 0
                THEN (SUM(TotalSinIva) - SUM(ValorCosto)) / SUM(TotalSinIva) * 100
                ELSE 0
            END as profit_margin_pct,
            COUNT(*) as transaction_count
        FROM banco_datos
        WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
        GROUP BY categoria
        ORDER BY total_revenue DESC
    """)

    # Example: Monthly revenue trend
    vn.train(sql="""
        -- Question: Show me monthly revenue trends
        SELECT
            YEAR(Fecha) as year,
            MONTH(Fecha) as month,
            SUM(TotalMasIva) as total_revenue,
            SUM(TotalSinIva) - SUM(ValorCosto) as profit,
            COUNT(*) as transaction_count
        FROM banco_datos
        WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
        GROUP BY YEAR(Fecha), MONTH(Fecha)
        ORDER BY year DESC, month DESC
    """)

    # Example: Revenue this month
    vn.train(sql="""
        -- Question: What's my revenue this month?
        SELECT
            SUM(TotalMasIva) as total_revenue,
            SUM(TotalSinIva) as revenue_without_tax,
            SUM(TotalMasIva) - SUM(TotalSinIva) as tax_collected,
            SUM(TotalSinIva) - SUM(ValorCosto) as gross_profit,
            COUNT(*) as total_orders
        FROM banco_datos
        WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
            AND Fecha >= DATEADD(MONTH, DATEDIFF(MONTH, 0, GETDATE()), 0)
            AND Fecha < DATEADD(MONTH, DATEDIFF(MONTH, 0, GETDATE()) + 1, 0)
    """)

    # Example: Products with low margin
    vn.train(sql="""
        -- Question: Which products have low profit margins?
        SELECT TOP 20
            ArticulosNombre as product_name,
            SUM(TotalSinIva) as revenue,
            SUM(ValorCosto) as cost,
            SUM(TotalSinIva) - SUM(ValorCosto) as profit,
            CASE
                WHEN SUM(TotalSinIva) > 0
                THEN (SUM(TotalSinIva) - SUM(ValorCosto)) / SUM(TotalSinIva) * 100
                ELSE 0
            END as profit_margin_pct
        FROM banco_datos
        WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
        GROUP BY ArticulosNombre
        HAVING SUM(TotalSinIva) > 0
        ORDER BY profit_margin_pct ASC
    """)

    print("✓ Training complete!")
    return vn


def run_chat_interface(vn):
    """Launch the web-based chat interface"""

    from vanna.flask import VannaFlaskApp

    print("\n" + "="*60)
    print("🚀 STARTING VANNA CHAT INTERFACE")
    print("="*60)
    print()
    print("Open your browser and go to: http://localhost:8084")
    print()
    print("Try asking questions like:")
    print("  • What are my top 10 selling products?")
    print("  • Show me revenue by category")
    print("  • Which customers have the highest order values?")
    print("  • What's my profit margin by product category?")
    print("  • Show me monthly revenue trends")
    print("  • Which products have low profit margins?")
    print()
    print("Press Ctrl+C to stop the server")
    print("="*60)

    # Create and run Flask app
    app = VannaFlaskApp(vn, allow_llm_to_see_data=True)
    app.run(port=8084)


def main():
    """Main entry point"""
    print("="*60)
    print("VANNA AI - Chat with Your SmartBusiness Database")
    print("="*60)
    print()

    # Check for required environment variables
    if USE_OPENAI and OPENAI_API_KEY == "your-openai-api-key":
        print("⚠️  WARNING: Set your OPENAI_API_KEY environment variable")
        print("   export OPENAI_API_KEY='sk-...'")
        print()

    if USE_GROK and GROK_API_KEY == "your-grok-api-key":
        print("⚠️  WARNING: Set your GROK_API_KEY environment variable")
        print("   export GROK_API_KEY='xai-...'")
        print()

    # Create Vanna instance
    print("[1/4] Creating Vanna instance...")
    vn = create_vanna_instance()
    print("✓ Vanna instance created!")

    # Connect to database
    print("\n[2/4] Connecting to database...")
    vn = connect_to_database(vn)

    # Train on schema
    print("\n[3/4] Training on database schema...")
    vn = train_vanna_on_schema(vn)

    # Run chat interface
    print("\n[4/4] Starting chat interface...")
    run_chat_interface(vn)


if __name__ == "__main__":
    main()
