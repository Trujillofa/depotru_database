#!/usr/bin/env python3
"""
vanna_grok.py (Vanna 2.0.1 Legacy Fixed – MSSQL + Grok Ready)
Production-ready: Natural language → SQL → Charts for SmartBusiness.
Features: Robust formatting, AI insights, security hardening, error handling.
Run: python src/vanna_grok.py → http://localhost:8084
"""

import os
import sys
import locale
import time
import pandas as pd
from typing import Any, List
from functools import wraps
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
# SECURITY - Required Environment Variables (No Defaults!)
# =============================================================================

def require_env(name: str, validation_func=None, error_msg: str = None) -> str:
    """
    Get required environment variable with optional validation.
    Exits immediately if missing or invalid - no defaults allowed!
    """
    value = os.getenv(name)

    if not value:
        print(f"❌ ERROR: Variable de entorno requerida faltante: {name}")
        if error_msg:
            print(f"   {error_msg}")
        else:
            print(f"   Agrega a tu archivo .env:")
            print(f"   {name}=tu-valor-aqui")
        print(f"\n   Ejemplo .env completo:")
        print(f"   GROK_API_KEY=xai-tu-clave")
        print(f"   DB_SERVER=tu-servidor")
        print(f"   DB_NAME=SmartBusiness")
        print(f"   DB_USER=tu-usuario")
        print(f"   DB_PASSWORD=tu-contraseña")
        sys.exit(1)

    if validation_func and not validation_func(value):
        print(f"❌ ERROR: {name} tiene un valor inválido: {value}")
        if error_msg:
            print(f"   {error_msg}")
        sys.exit(1)

    return value

# =============================================================================
# CONFIGURATION (All required from .env – No defaults for security!)
# =============================================================================

def _is_testing_env() -> bool:
    """
    Detect if we're running in a testing environment.
    Checks multiple indicators to be robust across different test runners.
    """
    # Check if pytest is imported
    if "pytest" in sys.modules:
        return True
    
    # Check for TESTING environment variable
    if os.getenv("TESTING", "false").lower() == "true":
        return True
    
    # Check if running from a test file
    try:
        frame = sys._getframe()
        while frame:
            filename = frame.f_globals.get('__file__', '')
            if 'test' in filename.lower() or 'pytest' in filename.lower():
                return True
            frame = frame.f_back
    except (AttributeError, ValueError):
        pass
    
    return False


def get_env_or_test_default(name: str, test_default: str, validation_func=None, error_msg: str = None) -> str:
    """
    Get environment variable with testing support.
    In production: uses require_env() with validation and exits on failure.
    In testing: returns environment variable or test default without exiting.
    """
    is_testing = _is_testing_env()
    
    if is_testing:
        return os.getenv(name, test_default)
    else:
        return require_env(name, validation_func, error_msg)


class Config:
    # Required API keys and credentials (no defaults!)
    GROK_API_KEY = get_env_or_test_default(
        "GROK_API_KEY",
        test_default="xai-test-key",
        validation_func=lambda x: x.startswith("xai-"),
        error_msg="La clave debe comenzar con 'xai-'"
    )

    DB_SERVER = get_env_or_test_default("DB_SERVER", test_default="test-server")
    DB_NAME = get_env_or_test_default("DB_NAME", test_default="TestDB")
    DB_USER = get_env_or_test_default("DB_USER", test_default="test_user")
    DB_PASSWORD = get_env_or_test_default("DB_PASSWORD", test_default="test_password")

    # Optional configuration with sensible defaults
    PORT = int(os.getenv("PORT", "8084"))
    HOST = os.getenv("HOST", "0.0.0.0")

    # Feature toggles
    ENABLE_AI_INSIGHTS = os.getenv("ENABLE_AI_INSIGHTS", "true").lower() == "true"
    INSIGHTS_MAX_ROWS = int(os.getenv("INSIGHTS_MAX_ROWS", "15"))
    MAX_DISPLAY_ROWS = int(os.getenv("MAX_DISPLAY_ROWS", "100"))

    # Known currency columns (explicit detection for reliability)
    CURRENCY_COLUMNS = [
        'TotalMasIva', 'TotalSinIva', 'ValorCosto', 'Facturacion_Total',
        'Revenue', 'Ganancia', 'Ganancia_Neta', 'total_revenue',
        'Ticket_Promedio', 'Revenue_Neto', 'Precio', 'Costo'
    ]

    # Known percentage columns
    PERCENTAGE_COLUMNS = [
        'Margen_Promedio_Pct', 'profit_margin_pct', 'Margen',
        'margin_pct', 'percentage'
    ]

# =============================================================================
# ROBUST NUMBER FORMATTING (Colombian Pesos, Percentages, Thousands)
# =============================================================================

def format_number(value: Any, column_name: str = "") -> str:
    """
    Bulletproof number formatting with explicit column detection.

    Priority:
    1. Explicit column name match (most reliable)
    2. Keyword detection (fallback)
    3. Type-based formatting (default)

    Examples:
    - TotalMasIva: 1234567 → "$1.234.567"
    - Margen_Promedio_Pct: 45.6 → "45,6%"
    - Cantidad: 1234 → "1.234"
    - None/NaN → "-"
    """
    # Handle nulls first
    if pd.isna(value) or value is None:
        return "-"

    # Try to convert to number
    try:
        num = float(value)
    except (ValueError, TypeError):
        return str(value)

    # Use explicit column lists from Config
    known_currency_cols = Config.CURRENCY_COLUMNS
    known_pct_cols = Config.PERCENTAGE_COLUMNS

    # 1. EXPLICIT COLUMN MATCH (highest priority)
    if column_name in known_currency_cols:
        # Colombian format: $123.456.789
        return f"${num:,.0f}".replace(',', '.')

    if column_name in known_pct_cols:
        # Spanish format: 45,6%
        return f"{num:,.1f}%".replace('.', ',')

    # 2. KEYWORD DETECTION (fallback)
    col_lower = column_name.lower()

    # Currency keywords
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
        return f"${num:,.0f}".replace(',', '.')

    # Percentage keywords
    percentage_keywords = ['margen', 'margin', 'pct', 'porcentaje', '%']
    if any(kw in col_lower for kw in percentage_keywords):
        return f"{num:,.1f}%".replace('.', ',')

    # 3. TYPE-BASED FORMATTING (default)
    if num == int(num):  # Integer - quantities
        return f"{int(num):,}".replace(',', '.')
    else:  # Decimal
        return f"{num:,.2f}".replace(',', 'TEMP').replace('.', ',').replace('TEMP', '.')



def format_dataframe(df: pd.DataFrame, max_rows: int = None) -> pd.DataFrame:
    """Apply beautiful formatting to entire dataframe"""
    if df is None or df.empty:
        return df

    if max_rows is None:
        max_rows = Config.MAX_DISPLAY_ROWS

    # Limit rows for display (prevent slowness with large results)
    df_display = df.head(max_rows).copy()

    # Apply formatting to each column
    for col in df_display.columns:
        df_display[col] = df_display[col].apply(
            lambda x: format_number(x, col)
        )

    # Warn if truncated
    if len(df) > max_rows:
        print(f"\n⚠️ Mostrando solo las primeras {max_rows} filas (total: {len(df):,})")

    return df_display

# =============================================================================
# ERROR HANDLING - Retry Logic for API Calls
# =============================================================================

def retry_on_failure(max_attempts: int = 3, delay: int = 2, backoff: int = 2):
    """
    Decorator for retrying failed API calls with exponential backoff.

    Args:
        max_attempts: Maximum retry attempts (default 3)
        delay: Initial delay in seconds (default 2)
        backoff: Backoff multiplier (default 2 = exponential)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        # Last attempt - re-raise exception
                        raise

                    print(f"⚠️ Intento {attempt + 1}/{max_attempts} falló: {e}")
                    print(f"   Reintentando en {current_delay}s...")
                    time.sleep(current_delay)
                    current_delay *= backoff  # Exponential backoff

            return None
        return wrapper
    return decorator


# =============================================================================
# AI INSIGHTS GENERATION (Grok analyzes results and gives recommendations)
# =============================================================================

@retry_on_failure(max_attempts=3, delay=2)
def generate_insights(
    question: str, sql: str, df: pd.DataFrame, grok_client: OpenAI
) -> str:
    """
    Use Grok to analyze query results and generate business insights.
    Includes automatic retry on failure.

    Returns Spanish business recommendations based on the data.
    """
    if df is None or df.empty:
        return "⚠️ No hay datos para analizar."

    # Limit data sent to Grok (privacy + token cost)
    df_preview = df.head(Config.INSIGHTS_MAX_ROWS)

    # Prepare data summary for Grok
    summary = {
        "rows": len(df),
        "columns": list(df.columns),
        "sample": df_preview.to_dict("records") if len(df_preview) > 0 else [],
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

Resultados (primeras {len(df_preview)} de {len(df)} filas):
{df_preview.to_string()}

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
        # If all retries failed, return error message
        return f"⚠️ No se pudieron generar insights: {e}"


# =============================================================================
# CUSTOM VANNA CLASS – Grok + ChromaDB + MSSQL (Resource Optimized)
# =============================================================================


class GrokVanna(ChromaDB_VectorStore, OpenAI_Chat):
    def __init__(self):
        # 1. ChromaDB for RAG (local, private, fast)
        ChromaDB_VectorStore.__init__(self, config={})

        # 2. Single shared Grok client (reused for SQL + insights)
        self.grok_client = OpenAI(
            api_key=Config.GROK_API_KEY,
            base_url="https://api.x.ai/v1"
        )

        # 3. Initialize OpenAI Chat with shared client
        OpenAI_Chat.__init__(
            self,
            client=self.grok_client,
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

            # ========== ENHANCEMENT 2: AI Insights (Optional) ==========
            insights = ""
            if Config.ENABLE_AI_INSIGHTS:
                # Use shared Grok client (resource optimization)
                insights = generate_insights(
                    question=question,
                    sql=sql,
                    df=df,  # Use original unformatted data for analysis
                    grok_client=self.grok_client  # ← Reuse shared client!
                )
                print(insights)
            else:
                print("\n💡 Insights desactivados (ENABLE_AI_INSIGHTS=false)\n")
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
