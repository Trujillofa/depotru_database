#!/usr/bin/env python3
"""
vanna_grok.py (Vanna 2.0.1 Legacy Fixed – MSSQL + Grok Ready)
Bullet-proof setup: Natural language → SQL → Charts for SmartBusiness.
Run: python src/vanna_grok.py → http://localhost:8084
"""

import os
import sys
from dotenv import load_dotenv

# Vanna 2.0.1 legacy imports (stable for custom Grok/ChromaDB/MSSQL)
from vanna.legacy.chromadb.chromadb_vector import ChromaDB_VectorStore
from vanna.legacy.openai import OpenAI_Chat
from vanna.legacy.flask import VannaFlaskApp
from openai import OpenAI

load_dotenv()

# =============================================================================
# CONFIGURATION (from .env – keep secrets safe!)
# =============================================================================

class Config:
    GROK_API_KEY = os.getenv("GROK_API_KEY")
    if not GROK_API_KEY or not GROK_API_KEY.startswith("xai-"):
        print("❌ ERROR: Set GROK_API_KEY in .env (must start with 'xai-...')")
        sys.exit(1)

    DB_SERVER = os.getenv("DB_SERVER", "190.60.235.209")
    DB_NAME = os.getenv("DB_NAME", "SmartBusiness")
    DB_USER = os.getenv("DB_USER", "Consulta")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "Control*01")

    PORT = int(os.getenv("PORT", "8084"))
    HOST = os.getenv("HOST", "0.0.0.0")

# =============================================================================
# CUSTOM VANNA CLASS – Grok + ChromaDB + MSSQL (ODBC via pyodbc)
# =============================================================================

class GrokVanna(ChromaDB_VectorStore, OpenAI_Chat):
    def __init__(self):
        # 1. ChromaDB for RAG (local, private, fast)
        ChromaDB_VectorStore.__init__(self, config={})

        # 2. Grok LLM via OpenAI-compatible client
        client = OpenAI(
            api_key=Config.GROK_API_KEY,
            base_url="https://api.x.ai/v1"
        )
        OpenAI_Chat.__init__(
            self,
            client=client,
            config={"model": "grok-beta"}  # Stable as of Dec 2025
        )

    def connect_to_mssql_odbc(self):
        """Connect & test via ODBC (Vanna's go-to for MSSQL)"""
        # Build ODBC string (handles special chars like * in password)
        odbc_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={Config.DB_SERVER};"
            f"DATABASE={Config.DB_NAME};"
            f"UID={Config.DB_USER};"
            f"PWD={Config.DB_PASSWORD};"
            f"TrustServerCertificate=yes;"  # For remote/trusted connections
            f"Encrypt=yes;"  # Security best practice
        )
        try:
            self.connect_to_mssql(odbc_conn_str=odbc_str)
            # Ping test (safe, no data leak)
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
            print("   - Or reply 'pymssql fallback' for pure Python DB connect")
            sys.exit(1)

# =============================================================================
# TRAINING – Schema, Rules, & Golden Examples (Your Accuracy Secret Sauce)
# =============================================================================

def train_vanna(vn: GrokVanna):
    print("\nTraining on SmartBusiness schema & rules...")

    # 1. DDL (Table Structure)
    vn.train(ddl="""
        CREATE TABLE banco_datos (
            Fecha DATE,
            TotalMasIva DECIMAL(18,2),
            TotalSinIva DECIMAL(18,2),
            ValorCosto DECIMAL(18,2),
            Cantidad INT,
            TercerosNombres NVARCHAR(200),
            ArticulosNombre NVARCHAR(200),
            ArticulosCodigo NVARCHAR(50),
            DocumentosCodigo NVARCHAR(10),
            categoria NVARCHAR(100),
            subcategoria NVARCHAR(100)
        );
    """)

    # 2. Business Rules/Docs (Forces smart filtering)
    vn.train(documentation="""
        SmartBusiness – Ferretería Sales Database
        CRITICAL RULE: ALWAYS add WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS') to exclude test/cancelled docs.
        Key Metrics:
        - Revenue: SUM(TotalMasIva)
        - Net Revenue: SUM(TotalSinIva)
        - Profit: SUM(TotalSinIva - ValorCosto)
        - Margin %: (TotalSinIva - ValorCosto) / TotalSinIva * 100
        - Tax (IVA): TotalMasIva - TotalSinIva
        Queries in Spanish work best (e.g., 'productos vendidos').
    """)

    # 3. Golden Examples (Few-shot prompts = Grok's SQL superpowers)
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
        ("Ganancias por categoría en el último mes", """
            SELECT
                categoria,
                SUM(TotalSinIva - ValorCosto) AS Ganancia_Neta
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
              AND Fecha >= DATEADD(MONTH, -1, GETDATE())
            GROUP BY categoria
            ORDER BY Ganancia_Neta DESC
        """),
        ("Top 10 clientes por facturación total", """
            SELECT TOP 10
                TercerosNombres AS Cliente,
                SUM(TotalMasIva) AS Facturacion_Total
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
            GROUP BY TercerosNombres
            ORDER BY Facturacion_Total DESC
        """),
        ("Margen de ganancia promedio por subcategoría", """
            SELECT
                subcategoria,
                AVG((TotalSinIva - ValorCosto) * 100.0 / NULLIF(TotalSinIva, 0)) AS Margen_Promedio_Pct
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS') AND TotalSinIva > 0
            GROUP BY subcategoria
            ORDER BY Margen_Promedio_Pct DESC
        """)
    ]

    for question, sql in examples:
        try:
            vn.train(question=question, sql=sql)
        except Exception as e:
            print(f"⚠️ Skipped example '{question[:30]}...': {e}")

    print("✓ Training complete – Vanna's ready to query like a pro!")

# =============================================================================
# MAIN – Connect, Train, Serve (One-Command Magic)
# =============================================================================

def main():
    print("=" * 70)
    print("🚀 VANNA 2.0.1 + GROK – SMARTBUSINESS BI DASHBOARD")
    print("   (Legacy Imports Fixed – Ask Away in Español!)")
    print("=" * 70)

    # 1. Instantiate Vanna
    vn = GrokVanna()

    # 2. Connect to DB
    vn.connect_to_mssql_odbc()

    # 3. Train (Schema + Rules + Examples)
    train_vanna(vn)

    # 4. Launch Web UI (Flask – Stable & Chart-Friendly)
    print(f"\n🌐 Server firing up → http://{Config.HOST}:{Config.PORT}")
    print("   Pro Tips: Ask 'Top productos rentables' or 'Ventas mensuales por categoría'")
    print("   Auto-generates SQL, tables, & charts. Ctrl+C to stop.\n")

    app = VannaFlaskApp(
        vn,
        allow_llm_to_see_data=True,  # Grok peeks at results for smarter viz
        title="SmartBusiness + Grok AI",
        subtitle="¡Chatea con tu base de datos en español natural!"
    )

    # Prod-Ready Server (Waitress > Flask Dev)
    try:
        from waitress import serve
        print("Using Waitress (production mode)")
        serve(app, host=Config.HOST, port=Config.PORT, threads=8)
    except ImportError:
        print("Waitress missing → Flask dev server (install: pip install waitress)")
        app.run(host=Config.HOST, port=Config.PORT, threaded=True, debug=False)

if __name__ == "__main__":
    main()
