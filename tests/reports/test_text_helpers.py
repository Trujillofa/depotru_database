"""Shared report text helpers."""

from business_analyzer.reports.ai_insights import ReportAIInsights
from business_analyzer.reports.text import (
    decimal_es,
    markdown_to_reportlab,
    percent_es,
    shorten,
    strip_html,
)


def test_colombian_number_helpers():
    assert decimal_es(1234567.89, 0) == "1.234.568"
    assert decimal_es(1234567.89, 2) == "1.234.567,89"
    assert percent_es(45.6, 1) == "45,6%"
    assert percent_es(None) == "—"


def test_shorten_breaks_at_word_boundary():
    assert shorten("SIKA MULTI-SEAL 10CM X ROLLO ALUMINIO", 24) == (
        "SIKA MULTI-SEAL 10CM X…"
    )


def test_markdown_to_reportlab_keeps_bold_and_escapes_html():
    out = markdown_to_reportlab("**Análisis** & <script>\n\n- Uno")
    assert "<b>Análisis</b>" in out
    assert "&amp;" in out
    assert "<script>" not in out
    assert "• Uno" in out


def test_strip_html_flattens_fragments():
    assert strip_html("<p>Hola <strong>mundo</strong></p><br/>Fin") == "Hola mundo Fin"


def test_backend_chain_defaults_to_groq_fallback(monkeypatch):
    monkeypatch.setenv("REPORT_AI_FALLBACK_PROVIDERS", "groq, openrouter")
    assert ReportAIInsights._resolve_backends("commandcode") == [
        "commandcode",
        "groq",
        "openrouter",
    ]


def test_narrative_validator():
    assert not ReportAIInsights._narrative_is_valid("corto")
    long_text = "Análisis y recomendaciones. " * 100
    assert ReportAIInsights._narrative_is_valid(long_text)
