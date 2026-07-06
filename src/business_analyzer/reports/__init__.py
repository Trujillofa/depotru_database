"""
Reports Package
=============

CLI and report generation utilities for the business analyzer.

Modules:
    monthly: CLI for monthly manager sales reports
    matplotlib_charts: Matplotlib chart generator for manager reports
    ai_insights: AI-powered insights and recommendations
    html_generator: Self-contained HTML report with embedded charts
    pdf_generator: Professional PDF report with ReportLab

Usage:
    python -m business_analyzer.reports.monthly --year 2024 --month 5 --format html
"""

from .ai_insights import ReportAIInsights
from .html_generator import HTMLReportGenerator
from .matplotlib_charts import ReportChartGenerator
from .pdf_generator import PDFReportGenerator

__all__ = [
    "ReportChartGenerator",
    "ReportAIInsights",
    "HTMLReportGenerator",
    "PDFReportGenerator",
]
