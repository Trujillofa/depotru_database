"""Command Code CLI narrative cleanup."""

from business_analyzer.reports.ai_insights import ReportAIInsights


def test_strip_trailing_offer_question():
    text = (
        "Cierre\n\nTexto final del informe.\n\n¿Quieres que lo deje guardado como X.md?"
    )
    assert ReportAIInsights._strip_cli_trailing_offer(text) == (
        "Cierre\n\nTexto final del informe."
    )


def test_strip_trailing_offer_english_style():
    text = "Fin.\n\nSi deseas, puedo exportarlo a PDF."
    assert ReportAIInsights._strip_cli_trailing_offer(text) == "Fin."


def test_strip_keeps_report_questions():
    text = "¿Cuánto creceríamos con mejor mix?\n\nCierre del informe."
    assert ReportAIInsights._strip_cli_trailing_offer(text) == text
