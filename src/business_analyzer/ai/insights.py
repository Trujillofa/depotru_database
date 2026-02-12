"""
Insights module for AI package.

Contains AI-powered insights generation for query results.
"""

import pandas as pd
from typing import Optional, Any

from .base import Config, retry_on_failure


@retry_on_failure(max_attempts=3, delay=2)
def generate_insights(
    question: str,
    sql: str,
    df: pd.DataFrame,
    ai_client: Any,
    provider: str = "grok",
) -> str:
    """
    Use AI to analyze query results and generate business insights.
    Includes automatic retry on failure.

    Returns Spanish business recommendations based on the data.

    Args:
        question: Original user question
        sql: SQL query that was executed
        df: DataFrame with query results
        ai_client: AI client for generating insights
        provider: AI provider name (grok, openai, anthropic)

    Returns:
        Formatted insights string in Spanish
    """
    if df is None or df.empty:
        return "⚠️ No hay datos para analizar."

    # Limit data sent to AI (privacy + token cost)
    df_preview = df.head(Config.INSIGHTS_MAX_ROWS)

    # Prepare data summary
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

    # Create prompt
    prompt = f"""Eres un analista de negocios experto para una ferretería colombiana.

Pregunta del usuario: {question}

SQL ejecutado: {sql}

Resultados (primeras {len(df_preview)} de {len(df)} filas):
{df_preview.to_string()}

Estadísticas: {summary["stats"]}

Por favor proporciona:
1. 📊 Resumen ejecutivo (1-2 oraciones sobre qué muestran los datos)
2. 💡 Insights clave (2-3 hallazgos importantes)
3. 🎯 Recomendaciones (2-3 acciones concretas que el negocio debería tomar)

Formato en español, conciso, enfocado en acción.
Usa emojis para hacer el análisis más visual."""

    try:
        if provider in ["grok", "openai"]:
            return _generate_openai_insights(ai_client, prompt, provider)
        elif provider == "anthropic":
            return _generate_anthropic_insights(ai_client, prompt)
        else:
            return f"⚠️ Insights no disponibles para proveedor: {provider}"
    except Exception as e:
        return f"⚠️ No se pudieron generar insights: {e}"


def _generate_openai_insights(ai_client, prompt: str, provider: str) -> str:
    """Generate insights using OpenAI-compatible API (Grok, OpenAI)."""
    model = "grok-4-1-fast-non-reasoning" if provider == "grok" else "gpt-4"

    response = ai_client.chat.completions.create(
        model=model,
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
    provider_name = "Grok" if provider == "grok" else "OpenAI"
    return f"\n{'=' * 70}\n🤖 ANÁLISIS INTELIGENTE (Powered by {provider_name})\n{'=' * 70}\n\n{insights}\n{'=' * 70}\n"


def _generate_anthropic_insights(ai_client, prompt: str) -> str:
    """Generate insights using Anthropic Claude API."""
    response = ai_client.messages.create(
        model="claude-3-sonnet-20240229",
        max_tokens=500,
        temperature=0.7,
        system="Eres un consultor de negocios experto en retail y ferreterías. Siempre respondes en español colombiano con recomendaciones accionables.",
        messages=[{"role": "user", "content": prompt}],
    )

    insights = response.content[0].text.strip()
    return f"\n{'=' * 70}\n🤖 ANÁLISIS INTELIGENTE (Powered by Claude)\n{'=' * 70}\n\n{insights}\n{'=' * 70}\n"
