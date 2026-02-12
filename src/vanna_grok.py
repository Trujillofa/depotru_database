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

import sys

# Add src to path for imports
sys.path.insert(0, "/home/yderf/depotru_database/src")

# Import from the new modular ai package
from business_analyzer.ai import (
    AIVanna,
    Config,
    format_dataframe,
    generate_insights,
    full_training,
)
from vanna.legacy.flask import VannaFlaskApp
import pandas as pd


def train_vanna(vn: AIVanna):
    """Train Vanna on SmartBusiness schema and examples."""
    full_training(vn, schema_name="SmartBusiness")


class EnhancedAIVanna(AIVanna):
    """
    Enhanced AIVanna with additional functionality for the web interface.
    Extends the base AIVanna with insights generation and formatting.
    """

    def ask(
        self, question: str = None, print_results: bool = True, auto_train: bool = True
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
                # Get appropriate AI client for insights
                ai_client = self.get_ai_client()
                if ai_client:
                    insights = generate_insights(
                        question=question,
                        sql=sql,
                        df=df,
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
            if auto_train and df is not None:
                try:
                    self.train(question=question, sql=sql)
                except:
                    pass  # Silent fail on training

            return sql, df, insights

        except Exception as e:
            print(f"\n❌ Error ejecutando consulta: {e}\n")
            return None, None, None


def main():
    print("=" * 70)
    print("🚀 VANNA 2.0.1 MULTI-PROVIDER – SMARTBUSINESS BI DASHBOARD")
    print(f"   Proveedor AI: {Config.AI_PROVIDER.upper()}")
    print("=" * 70)

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

    app = VannaFlaskApp(
        vn,
        allow_llm_to_see_data=True,
        title=f"SmartBusiness + {Config.AI_PROVIDER.upper()} AI",
        subtitle="¡Chatea con tu base de datos en español natural!",
    )

    # Vanna's Official Magic: .run()
    print("✓ Using Vanna's built-in Flask runner (threaded for multiple users)")
    try:
        app.run(
            host=Config.HOST,
            port=Config.PORT,
            debug=False,
            use_reloader=False,
            threaded=True,
        )
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped gracefully! (Gracias por chatear con tus datos)")
    except Exception as e:
        print(f"\n❌ Launch hiccup: {e}")
        print("💡 Fixes: Check port (lsof -i :8084), or try PORT=8085 in .env")


if __name__ == "__main__":
    main()
