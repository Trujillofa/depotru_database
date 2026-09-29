"""Spanish / Colombian result summaries and currency normalization.

Chart figures stay in ``charts.py``; this module is the text-summary
half of visualization. ``AIVanna`` is late-bound by
``business_analyzer.ai.vanna``.
"""

from __future__ import annotations

import math
import re
from typing import List

from business_analyzer.core.config import Config

# Late-bound by business_analyzer.ai.vanna after AIVanna is composed.
AIVanna = None


class SummaryMixin:
    """Deterministic and LLM fallback summaries for query results."""

    @staticmethod
    def _normalize_currency_symbols(text: str) -> str:
        if not text:
            return text
        normalized = text.replace("₡", "$").replace("CRC ", "$").replace("COP ", "$")
        return AIVanna._normalize_scientific_notation(normalized)

    @staticmethod
    def _normalize_scientific_notation(text: str) -> str:
        scientific_number_pattern = re.compile(
            r"(?P<prefix>\$\s*)?(?P<number>[+-]?\d+(?:\.\d+)?[eE][+-]?\d+)"
        )

        def _replace(match: re.Match[str]) -> str:
            number_text = match.group("number")
            prefix = match.group("prefix") or ""
            try:
                value = float(number_text)
            except ValueError:
                return match.group(0)

            if not math.isfinite(value):
                return match.group(0)

            if value.is_integer():
                formatted = f"{int(value):,}".replace(",", ".")
            else:
                formatted = (
                    f"{value:,.2f}".replace(",", "TEMP")
                    .replace(".", ",")
                    .replace("TEMP", ".")
                )

            return f"{prefix}{formatted}"

        return scientific_number_pattern.sub(_replace, text)

    @staticmethod
    def _deterministic_summary(question: str, df) -> str | None:
        """Build a Spanish summary with Colombian formatting (no LLM guesswork)."""
        from .formatting import format_number

        if df is None or not hasattr(df, "empty") or df.empty:
            return None

        colmap = {str(c).lower(): c for c in df.columns}

        def _pick(*names: str) -> str | None:
            for name in names:
                if name in colmap:
                    return colmap[name]
            return None

        ventas_col = _pick(
            "ventas_anio_actual",
            "ventas_anio_anterior",
            "ventas_total",
            "total_vendido",
            "promedio_ventas_diarias",
            "ventas_totales",
            "facturacion_total",
            "facturacion",
            "ventas",
            "totalmasiva",
        )
        ganancia_col = _pick(
            "ganancia_generada",
            "ganancia_neta",
            "ganancia_total",
            "ganancia",
        )
        count_col = _pick(
            "numero_documentos",
            "ventas_este_mes",
            "numero_ventas",
            "numero_transacciones",
            "numero_compras",
            "promedio_transacciones_diarias",
        )
        label_col = _pick(
            "periodo",
            "producto",
            "tipo_venta",
            "descripcion",
            "vendedor",
            "cliente",
            "nombre_mes",
        )
        clientes_col = _pick("clientes_unicos", "numero_clientes", "clientes")
        dept_col = _pick("departamento")
        city_col = _pick("ciudad")
        product_col = label_col or _pick(
            "vendedor",
            "producto",
            "articulosnombre",
            "articulonombre",
            "cliente",
            "tercerosnombres",
            "tipo_documento",
        )

        if not ventas_col and not ganancia_col:
            return None

        def _label(row) -> str:
            if dept_col and city_col:
                return f"{row[dept_col]} — {row[city_col]}"
            if product_col:
                return str(row[product_col])
            if dept_col:
                return str(row[dept_col])
            if city_col:
                return str(row[city_col])
            return "Registro"

        lines: List[str] = []
        if question:
            lines.append(question.strip())

        for _, row in df.head(5).iterrows():
            metrics: List[str] = []
            if ventas_col:
                metrics.append(
                    f"facturación {format_number(row[ventas_col], ventas_col)}"
                )
            if ganancia_col:
                metrics.append(
                    f"ganancia {format_number(row[ganancia_col], ganancia_col)}"
                )
            if count_col:
                count_lower = str(count_col).lower()
                unit = "documentos" if "documento" in count_lower else "transacciones"
                metrics.append(f"{format_number(row[count_col], count_col)} {unit}")
            if clientes_col:
                metrics.append(
                    f"clientes {format_number(row[clientes_col], clientes_col)}"
                )
            if metrics:
                lines.append(f"{_label(row)}: {', '.join(metrics)}")
            else:
                lines.append(_label(row))

        return "\n".join(lines) if lines else None

    def generate_summary(self, question: str, df, **kwargs) -> str:
        if df is None:
            return (
                "⚠️ No se pudo generar el resumen porque la consulta no devolvió "
                "resultados válidos."
            )

        if hasattr(df, "empty") and df.empty:
            return "ℹ️ La consulta no devolvió registros para resumir."

        raw_df = getattr(self, "_last_result_df", None)
        summary_source = (
            raw_df
            if raw_df is not None and hasattr(raw_df, "empty") and not raw_df.empty
            else df
        )
        deterministic = self._deterministic_summary(question, summary_source)
        if deterministic:
            return deterministic

        try:
            from .formatting import format_dataframe

            preview = format_dataframe(df.head(Config.INSIGHTS_MAX_ROWS))
            message_log = [
                self.system_message(
                    "Eres un asistente de datos para una ferretería colombiana. "
                    "Resume en español colombiano usando formato de moneda COP "
                    "con separador de miles con punto (ej. $25.766.450.551). "
                    "Los valores ya vienen formateados: repítelos tal cual, sin "
                    "convertir a miles/millones ni abreviar (nada de 25.88 ni 9.6K)."
                ),
                self.system_message(
                    f"Pregunta del usuario: '{question}'\n\n"
                    f"Resultados:\n{preview.to_markdown(index=False)}\n"
                ),
                self.user_message(
                    "Resume brevemente los datos según la pregunta. "
                    "No agregues explicación extra." + self._response_language()
                ),
            ]
            summary = self.submit_prompt(message_log, **kwargs)
        except Exception as exc:
            return (
                "⚠️ No se pudo generar el resumen automático para esta consulta "
                f"({exc})."
            )

        return self._normalize_currency_symbols(summary)
