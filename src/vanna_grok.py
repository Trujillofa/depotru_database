#!/usr/bin/env python3
"""
vanna_grok.py (Vanna 2.0.1 Legacy Fixed – MSSQL + Grok Ready)
Bullet-proof setup: Natural language → SQL → Charts for SmartBusiness.
Features: Beautiful number formatting, AI insights, Spanish optimization.
Run: python src/vanna_grok.py → http://localhost:8084
"""

import os
import sys
import locale
import pandas as pd
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Vanna 2.0.1 legacy imports (stable for custom Grok/ChromaDB/MSSQL)
from vanna.legacy.chromadb.chromadb_vector import ChromaDB_VectorStore
from vanna.legacy.openai import OpenAI_Chat
from vanna.legacy.flask import VannaFlaskApp
from openai import OpenAI

load_dotenv()

# Set Colombian locale for number formatting (fallback to Spanish/default)
try:
    locale.setlocale(locale.LC_ALL, "es_CO.UTF-8")  # Colombian Spanish
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, "es_ES.UTF-8")  # Spanish
    except locale.Error:
        try:
            locale.setlocale(locale.LC_ALL, "en_US.UTF-8")  # Fallback
        except locale.Error:
            pass  # Use system default

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
# NUMBER FORMATTING (Colombian Pesos, Percentages, Thousands)
# =============================================================================


def format_number(value: Any, column_name: str = "") -> str:
    """
    Format numbers beautifully based on column name and value type.

    Examples:
    - Revenue, Ganancia, Total → $123.456.789 (Colombian pesos)
    - Margen, Percentage → 45,6%
    - Cantidad, Unidades → 1.234 (thousands separator)
    """
    if pd.isna(value) or value is None:
        return "-"

    # Detect column type from name (Spanish business terms)
    col_lower = column_name.lower()

    # Currency columns (Colombian Pesos)
    currency_keywords = [
        "revenue",
        "ganancia",
        "facturacion",
        "total",
        "costo",
        "precio",
        "valor",
        "ingreso",
        "profit",
        "cost",
        "iva",
    ]
    if any(kw in col_lower for kw in currency_keywords):
        try:
            num = float(value)
            # Colombian format: $123.456.789 (period as thousands separator)
            formatted = f"${num:,.0f}".replace(",", ".")
            return formatted
        except (ValueError, TypeError):
            return str(value)

    # Percentage columns
    percentage_keywords = ["margen", "margin", "pct", "porcentaje", "percentage", "%"]
    if any(kw in col_lower for kw in percentage_keywords):
        try:
            num = float(value)
            # Spanish format: 45,6% (comma as decimal separator)
            formatted = (
                f"{num:,.1f}%".replace(",", "TEMP")
                .replace(".", ",")
                .replace("TEMP", ".")
            )
            return formatted
        except (ValueError, TypeError):
            return str(value)

    # Regular numbers (quantities, counts)
    try:
        num = float(value)
        if num == int(num):  # Integer
            formatted = f"{int(num):,}".replace(",", ".")
            return formatted
        else:  # Decimal
            formatted = (
                f"{num:,.2f}".replace(",", "TEMP")
                .replace(".", ",")
                .replace("TEMP", ".")
            )
            return formatted
    except (ValueError, TypeError):
        return str(value)


def format_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Apply beautiful formatting to entire dataframe"""
    if df is None or df.empty:
        return df

    # Create formatted copy
    df_formatted = df.copy()

    for col in df_formatted.columns:
        df_formatted[col] = df_formatted[col].apply(lambda x: format_number(x, col))

    return df_formatted


# =============================================================================
# AI INSIGHTS GENERATION (Grok analyzes results and gives recommendations)
# =============================================================================


def generate_insights(
    question: str, sql: str, df: pd.DataFrame, grok_client: OpenAI
) -> str:
    """
    Use Grok to analyze query results and generate business insights.

    Returns Spanish business recommendations based on the data.
    """
    if df is None or df.empty:
        return "⚠️ No hay datos para analizar."

    # Prepare data summary for Grok
    summary = {
        "rows": len(df),
        "columns": list(df.columns),
        "sample": df.head(10).to_dict("records") if len(df) > 0 else [],
        "stats": {},
    }

    # Add statistics for numeric columns
    for col in df.columns:
        try:
            if pd.api.types.is_numeric_dtype(df[col]):
                summary["stats"][col] = {
                    "min": float(df[col].min()),
                    "max": float(df[col].max()),
                    "mean": float(df[col].mean()),
                    "total": float(df[col].sum()) if "sum" in dir(df[col]) else None,
                }
        except:
            pass

    # Create prompt for Grok
    prompt = f"""Eres un analista de negocios experto para una ferretería colombiana.

Pregunta del usuario: {question}

SQL ejecutado: {sql}

Resultados (primeras filas):
{df.head(10).to_string()}

Estadísticas: {summary['stats']}

Por favor proporciona:
1. 📊 Resumen ejecutivo (1-2 oraciones sobre qué muestran los datos)
2. 💡 Insights clave (2-3 hallazgos importantes)
3. 🎯 Recomendaciones (2-3 acciones concretas que el negocio debería tomar)

Formato en español, conciso, enfocado en acción.
Usa emojis para hacer el análisis más visual."""

    try:
        response = grok_client.chat.completions.create(
            model="grok-4-1-fast-non-reasoning",
            messages=[
                {
                    "role": "system",
                    "content": "Eres un consultor de negocios experto en retail y ferreterías. Siempre respondes en español colombiano con recomendaciones accionables.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=500,
        )

        insights = response.choices[0].message.content.strip()
        return f"\n{'='*70}\n🤖 ANÁLISIS INTELIGENTE (Powered by Grok)\n{'='*70}\n\n{insights}\n{'='*70}\n"

    except Exception as e:
        return f"⚠️ No se pudieron generar insights: {e}"


# =============================================================================
# CUSTOM VANNA CLASS – Grok + ChromaDB + MSSQL (ODBC via pyodbc)
# =============================================================================


class GrokVanna(ChromaDB_VectorStore, OpenAI_Chat):
    def __init__(self):
        # 1. ChromaDB for RAG (local, private, fast)
        ChromaDB_VectorStore.__init__(self, config={})

        # 2. Grok LLM via OpenAI-compatible client
        client = OpenAI(api_key=Config.GROK_API_KEY, base_url="https://api.x.ai/v1")
        OpenAI_Chat.__init__(
            self,
            client=client,
            config={"model": "grok-4-1-fast-non-reasoning"},  # Stable as of Dec 2025
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

    def ask(
        self, question: str = None, print_results: bool = True, auto_train: bool = True
    ) -> tuple:
        """
        Enhanced ask() method with:
        - Beautiful number formatting (Colombian pesos, percentages)
        - AI-generated insights and recommendations
        - Spanish-optimized output
        """
        # Get SQL and run query (using parent class methods)
        try:
            # Generate SQL
            sql = self.generate_sql(question=question, allow_llm_to_see_data=True)

            if sql is None:
                return None, None, None

            # Execute query
            df = self.run_sql(sql)

            if df is None or df.empty:
                print("\n⚠️ La consulta no devolvió resultados.\n")
                return sql, df, None

            # ========== ENHANCEMENT 1: Format Numbers ==========
            print("\n" + "=" * 70)
            print("📊 RESULTADOS (con formato colombiano)")
            print("=" * 70)
            print(f"\n📝 SQL Ejecutado:\n{sql}\n")
            print(f"✅ {len(df)} filas encontradas\n")

            # Show formatted dataframe
            df_formatted = format_dataframe(df)
            print(df_formatted.to_string(index=False))
            print()

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

            # Auto-train on successful queries (optional)
            if auto_train and df is not None:
                try:
                    self.train(question=question, sql=sql)
                except:
                    pass  # Silent fail on training

            return sql, df, insights

        except Exception as e:
            print(f"\n❌ Error ejecutando consulta: {e}\n")
            return None, None, None


# =============================================================================
# TRAINING – Schema, Rules, & Golden Examples (Your Accuracy Secret Sauce)
# =============================================================================


def train_vanna(vn: GrokVanna):
    print("\nTraining on SmartBusiness schema & rules...")

    # 1. DDL (Table Structure)
    vn.train(
        ddl="""
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
    """
    )

    # 2. Business Rules/Docs (Forces smart filtering)
    vn.train(
        documentation="""
        SmartBusiness – Ferretería Sales Database
        CRITICAL RULE: ALWAYS add WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS') to exclude test/cancelled docs.
        Key Metrics:
        - Revenue: SUM(TotalMasIva)
        - Net Revenue: SUM(TotalSinIva)
        - Profit: SUM(TotalSinIva - ValorCosto)
        - Margin %: (TotalSinIva - ValorCosto) / TotalSinIva * 100
        - Tax (IVA): TotalMasIva - TotalSinIva
        Queries in Spanish work best (e.g., 'productos vendidos').
    """
    )

    # 3. Golden Examples (Few-shot prompts = Grok's SQL superpowers)
    examples = [
        (
            "Top 10 productos más vendidos este año",
            """
            SELECT TOP 10
                ArticulosNombre AS Producto,
                SUM(Cantidad) AS Unidades_Vendidas,
                SUM(TotalMasIva) AS Revenue
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
              AND YEAR(Fecha) = YEAR(GETDATE())
            GROUP BY ArticulosNombre
            ORDER BY Revenue DESC
        """,
        ),
        (
            "Ganancias por categoría en el último mes",
            """
            SELECT
                categoria,
                SUM(TotalSinIva - ValorCosto) AS Ganancia_Neta
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
              AND Fecha >= DATEADD(MONTH, -1, GETDATE())
            GROUP BY categoria
            ORDER BY Ganancia_Neta DESC
        """,
        ),
        (
            "Top 10 clientes por facturación total",
            """
            SELECT TOP 10
                TercerosNombres AS Cliente,
                SUM(TotalMasIva) AS Facturacion_Total
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
            GROUP BY TercerosNombres
            ORDER BY Facturacion_Total DESC
        """,
        ),
        (
            "Margen de ganancia promedio por subcategoría",
            """
            SELECT
                subcategoria,
                AVG((TotalSinIva - ValorCosto) * 100.0 / NULLIF(TotalSinIva, 0)) AS Margen_Promedio_Pct
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS') AND TotalSinIva > 0
            GROUP BY subcategoria
            ORDER BY Margen_Promedio_Pct DESC
        """,
        ),
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

    # 4. Launch Web UI (Vanna's Native Runner – Handles Everything)
    print(f"\n🌐 Server firing up → http://{Config.HOST}:{Config.PORT}")
    print(
        "   Pro Tips: Ask 'Top productos rentables' or 'Ventas mensuales por categoría'"
    )
    print("   Auto-generates SQL, tables, & charts. Ctrl+C to stop.\n")

    app = VannaFlaskApp(
        vn,
        allow_llm_to_see_data=True,  # Grok peeks at results for smarter viz
        title="SmartBusiness + Grok AI",
        subtitle="¡Chatea con tu base de datos en español natural!",
    )

    # 🚀 Vanna's Official Magic: .run() – Works in Dev/Prod, No Hacks Needed
    print("✓ Using Vanna's built-in Flask runner (threaded for multiple users)")
    try:
        app.run(
            host=Config.HOST,
            port=Config.PORT,
            debug=False,  # False for prod-like stability
            use_reloader=False,  # No double-spawns in scripts
            threaded=True,  # Handles 10-20 concurrent chats
        )
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped gracefully! (Gracias por chatear con tus datos)")
    except Exception as e:
        print(f"\n❌ Launch hiccup: {e}")
        print("💡 Fixes: Check port (lsof -i :8084), or try PORT=8085 in .env")


if __name__ == "__main__":
    main()
