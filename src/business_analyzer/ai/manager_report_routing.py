"""Manager-report routing extracted from AIVanna.

Builds the monthly gerencial report when the question asks for it.
``AIVanna`` is late-bound by ``business_analyzer.ai.vanna``.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from business_analyzer.core.config import Config

# Late-bound by business_analyzer.ai.vanna after AIVanna is composed.
AIVanna = None


class ManagerReportMixin:
    """Detect, parse, and build the monthly manager sales report."""

    @staticmethod
    def _normalize_question_text(question: str) -> str:
        text = (question or "").lower()
        for src, dst in (
            ("á", "a"),
            ("é", "e"),
            ("í", "i"),
            ("ó", "o"),
            ("ú", "u"),
            ("ü", "u"),
        ):
            text = text.replace(src, dst)
        return text

    @staticmethod
    def _is_manager_report_question(question: str) -> bool:
        """Detect requests for the full monthly manager report (not ad-hoc SQL)."""
        lower = AIVanna._normalize_question_text(question)
        if not lower:
            return False

        has_report_noun = any(
            token in lower
            for token in ("informe", "reporte", "depotru-report", "depotru report")
        )
        if not has_report_noun:
            return False

        has_manager_context = any(
            token in lower
            for token in (
                "gerencial",
                "gerencia",
                "mensual",
                "manager",
                "de ventas",
                "ventas mensual",
                "depotru-report",
                "depotru report",
            )
        )
        has_generate_action = any(
            token in lower
            for token in (
                "genera",
                "generar",
                "crear",
                "exportar",
                "descarga",
                "descargar",
                "quiero el",
                "dame el",
                "necesito el",
            )
        )
        has_period_hint = AIVanna._parse_report_period(question) is not None

        return has_manager_context or has_generate_action or has_period_hint

    @staticmethod
    def _parse_report_period(question: str) -> Optional[Tuple[int, int]]:
        """Parse (year, month) from natural-language report requests."""
        lower = AIVanna._normalize_question_text(question)
        if not lower:
            return None

        now = datetime.now()

        if any(
            phrase in lower for phrase in ("mes pasado", "ultimo mes", "last month")
        ):
            if now.month == 1:
                return now.year - 1, 12
            return now.year, now.month - 1

        if any(
            phrase in lower
            for phrase in ("este mes", "mes actual", "mes en curso", "current month")
        ):
            return now.year, now.month

        year: Optional[int] = None
        year_match = re.search(r"\b(20\d{2})\b", lower)
        if year_match:
            year = int(year_match.group(1))

        month = AIVanna._month_number_from_question(question)
        if not month:
            patterns = (
                r"(?:mes\s+)?(\d{1,2})\s*(?:de|del|/|-)\s*(20\d{2})",
                r"(20\d{2})\s*[-/]\s*(\d{1,2})",
                r"(\d{1,2})\s*[-/]\s*(20\d{2})",
            )
            for pattern in patterns:
                match = re.search(pattern, lower)
                if not match:
                    continue
                if pattern.startswith(r"(20"):
                    year = int(match.group(1))
                    month = int(match.group(2))
                else:
                    month = int(match.group(1))
                    year = int(match.group(2))
                break

        if month and year and 1 <= month <= 12:
            return year, month
        if month and 1 <= month <= 12:
            return now.year, month
        return None

    @staticmethod
    def _parse_report_format(question: str) -> str:
        lower = AIVanna._normalize_question_text(question)
        if "pdf" in lower:
            return "pdf"
        if "json" in lower:
            return "json"
        if "texto" in lower or re.search(r"\btext\b", lower):
            return "text"
        return "html"

    @staticmethod
    def _format_manager_report_message(
        year: int,
        month: int,
        summary: Dict[str, Any],
        metadata: Dict[str, Any],
        output_path: Optional[str],
        fmt: str,
    ) -> str:
        month_name = metadata.get("month_name", str(month))
        lines = [
            "",
            "=" * 70,
            f"📊 INFORME GERENCIAL — {month_name} {year}",
            "=" * 70,
            f"Registros analizados: {metadata.get('record_count', 0):,}".replace(
                ",", "."
            ),
            "",
            f"  Facturación (IVA):     {summary.get('total_revenue_with_iva', 'N/D')}",
            f"  Facturación (sin IVA): {summary.get('total_revenue_without_iva', 'N/D')}",
            f"  Ganancia bruta:        {summary.get('gross_profit', 'N/D')}",
            f"  Margen bruto:          {summary.get('gross_margin_pct', 'N/D')}",
            f"  Transacciones:         {summary.get('order_count', 'N/D')}",
            f"  Ticket promedio:       {summary.get('average_order_value', 'N/D')}",
        ]
        if output_path:
            lines.extend(
                [
                    "",
                    f"✓ Informe {fmt.upper()} guardado en:",
                    f"  {output_path}",
                ]
            )
        lines.append("")
        return "\n".join(lines)

    def route_manager_report_question(self, question: str) -> Optional[Dict[str, Any]]:
        """
        Build the monthly manager report when the question requests it.

        Returns a result dict (also stored on ``_manager_report_result``) or None
        when the question is not a manager-report request.
        """
        if not self._is_manager_report_question(question):
            return None

        period = self._parse_report_period(question)
        if period is None:
            return {
                "status": "needs_period",
                "message": (
                    "Para generar el informe gerencial necesito el mes y el año. "
                    "Ejemplo: «Genera el informe de mayo 2024 en PDF»."
                ),
            }

        year, month = period
        fmt = self._parse_report_format(question)
        branch = self._branch_document_code(question)
        try:
            result = self._build_manager_report(
                year, month, fmt, branch_document_code=branch
            )
            self._manager_report_result = result
            return result
        except Exception as exc:
            result = {
                "status": "error",
                "message": f"Error generando el informe gerencial: {exc}",
            }
            self._manager_report_result = result
            return result

    def pop_manager_report_result(self) -> Optional[Dict[str, Any]]:
        """Return and clear the last manager-report routing result."""
        result = self._manager_report_result
        self._manager_report_result = None
        return result

    def _build_manager_report(
        self,
        year: int,
        month: int,
        fmt: str,
        *,
        branch_document_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        from business_analyzer.analysis.manager_report import ManagerSalesReport
        from business_analyzer.analysis.manager_report.helpers import (
            branch_slug,
            report_output_basename,
        )
        from business_analyzer.core.database import ConnectionType
        from business_analyzer.reports.ai_insights import ReportAIInsights
        from business_analyzer.reports.html_generator import HTMLReportGenerator
        from business_analyzer.reports.matplotlib_charts import ReportChartGenerator
        from business_analyzer.reports.pdf_generator import PDFReportGenerator

        report = ManagerSalesReport(
            year=year,
            month=month,
            db_connection_type=ConnectionType.DIRECT,
            branch_document_code=branch_document_code,
        )
        data = report.generate()
        metadata = data.get("metadata", {})
        summary = data.get("formatted", {}).get("summary", {})

        ai_data: Dict[str, Any] = {}
        if Config.ENABLE_AI_INSIGHTS:
            try:
                ai_data = ReportAIInsights(data, provider=self.provider).generate()
            except Exception as exc:
                ai_data = {
                    "ai_analysis_text": (
                        f"⚠️ No se pudo generar el análisis con IA: {exc}"
                    )
                }

        output_path: Optional[str] = None
        chart_paths: Dict[str, str] = {}

        if fmt in ("html", "pdf"):
            output_dir = Config.ensure_output_dir()
            slug = branch_slug(branch_document_code)
            chart_subdir = (
                f"{slug}_{year}_{month:02d}" if slug else f"{year}_{month:02d}"
            )
            chart_dir = output_dir / "charts" / chart_subdir
            chart_dir.mkdir(parents=True, exist_ok=True)
            chart_paths = ReportChartGenerator(
                data, output_dir=str(chart_dir)
            ).generate_all()
            filename = report_output_basename(
                year, month, fmt, branch_document_code=branch_document_code
            )
            target = output_dir / filename
            if fmt == "html":
                output_path = HTMLReportGenerator(data, chart_paths, ai_data).generate(
                    str(target)
                )
            else:
                output_path = PDFReportGenerator(data, chart_paths, ai_data).generate(
                    str(target)
                )
        elif fmt == "json":
            import json

            output_dir = Config.ensure_output_dir()
            target = output_dir / report_output_basename(
                year, month, "json", branch_document_code=branch_document_code
            )
            payload = {"report": data, "ai_insights": ai_data}
            with open(target, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=False, default=str)
            output_path = str(target.resolve())

        message = self._format_manager_report_message(
            year, month, summary, metadata, output_path, fmt
        )
        if ai_data.get("ai_analysis_text"):
            message = f"{message}\n🤖 Análisis IA:\n{ai_data['ai_analysis_text']}\n"

        result: Dict[str, Any] = {
            "status": "success",
            "year": year,
            "month": month,
            "format": fmt,
            "path": output_path,
            "record_count": metadata.get("record_count", 0),
            "summary": summary,
            "message": message,
        }
        if branch_document_code:
            result["branch_document_code"] = branch_document_code
            result["branch_name"] = metadata.get("branch_name")
        return result
