#!/usr/bin/env python3
"""
vanna_grok.py (Vanna 2.0.1 Multi-Provider – MSSQL + AI Ready)
Production-ready: Natural language → SQL → Charts for SmartBusiness.

This is now a thin wrapper/CLI entry point that uses the modular ai package.
All core functionality has been moved to src/business_analyzer/ai/

Run: python src/vanna_grok.py → http://localhost:8084

Supported AI Providers (set via AI_PROVIDER env var):
- grok (default): xAI Grok via OpenAI-compatible API
- openai: OpenAI GPT-4
- anthropic: Anthropic Claude
- ollama: Local Ollama (free, private)
"""

import os
import re
import socket
import subprocess
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Import from the new modular ai package
from business_analyzer.ai import (  # noqa: E402
    AIVanna,
    Config,
    format_dataframe,
    full_training,
    generate_insights,
)
from business_analyzer.ai.charts import (  # noqa: E402
    _normalize_chart_dtypes,
    build_plotly_code,
    build_smart_figure,
    get_chart_query_context,
    set_chart_query_context,
)
from business_analyzer.ai.flask_app import SmartVannaFlaskApp  # noqa: E402
from business_analyzer.ai.formatting import coerce_chart_dataframe  # noqa: E402


def clean_sql(sql: str) -> str:
    """
    Clean SQL by removing LLM artifacts like 'intermediate_sql:' prefixes,
    comments, and other non-SQL content that causes execution errors.

    Known issue: Vanna LLMs sometimes prefix SQL with labels like:
    - 'intermediate_sql:'
    - 'sql:'
    - '```sql'
    This causes SQL Server to interpret the label as a stored procedure name.
    """
    if not sql:
        return sql

    cleaned = sql

    # Remove common LLM SQL prefixes (case-insensitive)
    prefixes = [
        r"^intermediate_sql:\s*",
        r"^sql:\s*",
        r"^final_sql:\s*",
        r"^query:\s*",
    ]
    for prefix in prefixes:
        cleaned = re.sub(
            prefix, "", cleaned, flags=re.IGNORECASE | re.MULTILINE
        ).strip()

    # Remove leading SQL comment lines (-- comment)
    lines = cleaned.split("\n")
    code_lines = [line for line in lines if not line.strip().startswith("--")]
    cleaned = "\n".join(code_lines).strip()

    # Remove markdown code blocks if present
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```\w*", "", cleaned).strip()
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()

    return cleaned


def train_vanna(vn: AIVanna):
    """Train Vanna on SmartBusiness schema and examples."""
    full_training(vn, schema_name="SmartBusiness")


def _port_is_available(host: str, port: int) -> bool:
    bind_host = "127.0.0.1" if host in ("0.0.0.0", "") else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((bind_host, port))
        except OSError:
            return False
    return True


def _pids_on_port(port: int) -> list[str]:
    try:
        output = subprocess.check_output(
            ["ss", "-tlnp"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []
    pids: list[str] = []
    needle = f":{port}"
    for line in output.splitlines():
        if needle not in line or "users:" not in line:
            continue
        for token in line.split("pid=")[1:]:
            pids.append(token.split(",")[0])
    return pids


def _exit_if_port_busy(host: str, port: int) -> None:
    if _port_is_available(host, port):
        return
    pids = _pids_on_port(port)
    pid_hint = f"kill {' '.join(pids)}" if pids else f"fuser -k {port}/tcp"
    print(f"\n❌ Puerto {port} ya está en uso — Vanna ya está corriendo.")
    print(f"   → Abre http://localhost:{port} (no necesitas iniciar otro)")
    print(f"   → Para reiniciar: {pid_hint}")
    print(f"   → O usa otro puerto: PORT=8085 uv run python src/vanna_grok.py")
    print("   → O: scripts/utils/vanna_serve.sh restart\n")
    sys.exit(1)


class EnhancedAIVanna(AIVanna):
    """
    Enhanced AIVanna with additional functionality for the web interface.
    Extends the base AIVanna with insights generation and formatting.
    """

    def generate_sql(
        self,
        question: Optional[str] = None,
        allow_llm_to_see_data: bool = True,
        **kwargs,
    ):
        self._last_question = question
        set_chart_query_context(question=question)
        return super().generate_sql(
            question=question, allow_llm_to_see_data=allow_llm_to_see_data, **kwargs
        )

    def run_sql(self, sql: str, **kwargs):
        self._ensure_project_run_sql()
        df = super().run_sql(sql, **kwargs)
        if df is not None and not df.empty:
            normalized_df = _normalize_chart_dtypes(df.copy())
            self._last_result_df = normalized_df
            set_chart_query_context(
                raw_df=normalized_df,
                question=getattr(self, "_last_question", None),
            )
            return format_dataframe(df)
        self._last_result_df = None
        set_chart_query_context(raw_df=None)
        return df

    def should_generate_chart(self, df: pd.DataFrame) -> bool:
        raw = getattr(self, "_last_result_df", None)
        if raw is not None and not raw.empty:
            return super().should_generate_chart(raw)
        return super().should_generate_chart(df)

    def generate_plotly_code(
        self,
        question: Optional[str] = None,
        sql: Optional[str] = None,
        df_metadata: Optional[str] = None,
        **kwargs,
    ) -> str:
        tls_df, tls_question = get_chart_query_context()
        df = tls_df
        if df is None or df.empty:
            df = getattr(self, "_last_result_df", None)
        chart_question = (
            question or tls_question or getattr(self, "_last_question", None)
        )
        if df is not None and not df.empty:
            code = build_plotly_code(df, question=chart_question)
            if code:
                return code
        if not getattr(self, "provider", None):
            return ""
        return super().generate_plotly_code(
            question=question, sql=sql, df_metadata=df_metadata, **kwargs
        )

    def get_plotly_figure(
        self, plotly_code: str, df: pd.DataFrame, dark_mode: bool = True, **kwargs
    ):
        tls_df, tls_question = get_chart_query_context()
        chart_df = tls_df
        if chart_df is None or chart_df.empty:
            chart_df = getattr(self, "_last_result_df", None)
        if chart_df is None or chart_df.empty:
            chart_df = coerce_chart_dataframe(df)
        question = (
            kwargs.get("question")
            or tls_question
            or getattr(self, "_last_question", None)
        )
        fig = build_smart_figure(
            chart_df,
            question=question,
            dark_mode=dark_mode,
        )
        if fig is not None:
            return fig
        raise ValueError(
            "Smart chart heuristics could not build a figure for this data"
        )

    def ask(
        self,
        question: Optional[str] = None,
        print_results: bool = True,
        auto_train: bool = True,
    ) -> tuple:
        """
        Enhanced ask() method with:
        - Beautiful number formatting (Colombian pesos, percentages)
        - AI-generated insights and recommendations
        - Spanish-optimized output
        """
        try:
            # Generate SQL
            sql = self.generate_sql(question=question, allow_llm_to_see_data=True)

            if sql is None:
                print("\n⚠️ No se pudo generar SQL válido para la pregunta.\n")
                return None, pd.DataFrame(), None

            # Clean LLM artifacts from SQL (intermediate_sql prefix bug - GitHub #588)
            sql = clean_sql(sql)

            # Execute query (run_sql returns formatted display; raw kept in _last_result_df)
            df_display = self.run_sql(sql)
            raw_df = getattr(self, "_last_result_df", df_display)

            if df_display is None or df_display.empty:
                print("\n⚠️ La consulta no devolvió resultados.\n")
                return sql, pd.DataFrame(), None

            # ========== ENHANCEMENT 1: Format Numbers ==========
            print("\n" + "=" * 70)
            print("📊 RESULTADOS (con formato colombiano)")
            print("=" * 70)
            print(f"\n📝 SQL Ejecutado:\n{sql}\n")
            print(f"✅ {len(raw_df)} filas encontradas\n")

            print(df_display.to_string(index=False))
            print()

            # ========== ENHANCEMENT 2: AI Insights (Optional) ==========
            insights = ""
            if Config.ENABLE_AI_INSIGHTS:
                # Get appropriate AI client for insights
                ai_client = self.get_ai_client()
                if ai_client:
                    insights = generate_insights(
                        question=question,
                        sql=sql,
                        df=raw_df,
                        ai_client=ai_client,
                        provider=self.provider,
                    )
                    print(insights)
                else:
                    print(
                        f"\n💡 Insights no disponibles para proveedor: {self.provider}\n"
                    )
            else:
                print("\n💡 Insights desactivados (ENABLE_AI_INSIGHTS=false)\n")

            # Auto-train on successful queries (optional)
            if auto_train and raw_df is not None:
                try:
                    self.train(question=question, sql=sql)
                except Exception:  # nosec B110
                    # Training failures shouldn't break the user experience
                    pass

            return sql, raw_df, insights

        except Exception as e:
            print(f"\n❌ Error ejecutando consulta: {e}\n")
            return None, None, None


def main():
    print("=" * 70)
    print("🚀 VANNA 2.0.1 MULTI-PROVIDER – SMARTBUSINESS BI DASHBOARD")
    print(f"   Proveedor AI: {Config.AI_PROVIDER.upper()}")
    print("=" * 70)

    _exit_if_port_busy(Config.HOST, Config.PORT)

    # 1. Instantiate Vanna with selected provider
    vn = EnhancedAIVanna()

    # 2. Connect to DB
    vn.connect_to_mssql_odbc()

    # 3. Train (Schema + Rules + Examples)
    train_vanna(vn)

    # 4. Launch Web UI
    print(f"\n🌐 Server firing up → http://{Config.HOST}:{Config.PORT}")
    print(
        "   Pro Tips: Ask 'Top productos rentables' or 'Ventas mensuales por categoría'"
    )
    print("   Auto-generates SQL, tables, & charts. Ctrl+C to stop.\n")

    app = SmartVannaFlaskApp(
        vn,
        allow_llm_to_see_data=True,
        title=f"SmartBusiness + {Config.AI_PROVIDER.upper()} AI",
        subtitle="¡Chatea con tu base de datos en español natural!",
        chart=True,  # Enable chart generation
    )

    production = os.getenv("PRODUCTION_MODE", "false").lower() in (
        "1",
        "true",
        "yes",
    )
    threads = int(os.getenv("WAITRESS_THREADS", "8"))

    try:
        if production:
            from waitress import serve

            print(f"✓ Starting Waitress production server ({threads} threads)")
            serve(
                app.flask_app,
                host=Config.HOST,
                port=Config.PORT,
                threads=threads,
            )
        else:
            print("✓ Starting Flask development server")
            app.flask_app.run(
                host=Config.HOST,
                port=Config.PORT,
                debug=False,
                use_reloader=False,
                threaded=True,
            )
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped gracefully! (Gracias por chatear con tus datos)")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
