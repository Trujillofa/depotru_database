"""Tests for manager report intent routing in AIVanna."""

from unittest.mock import MagicMock, patch

import pytest

from business_analyzer.ai.base import AIVanna


@pytest.mark.parametrize(
    "question,expected",
    [
        ("Genera el informe mensual de mayo 2024", True),
        ("Quiero el reporte gerencial de ventas de 05/2024 en PDF", True),
        ("depotru-report mayo 2024", True),
        ("Top 10 clientes con mayor facturación", False),
        ("Ventas mensuales por categoría", False),
        ("Cuáles son las ventas de SIKA al mes?", False),
    ],
)
def test_is_manager_report_question(question, expected):
    assert AIVanna._is_manager_report_question(question) is expected


@pytest.mark.parametrize(
    "question,expected",
    [
        ("informe de mayo 2024", (2024, 5)),
        ("reporte gerencial 05/2024", (2024, 5)),
        ("informe mensual 2024-05", (2024, 5)),
        ("informe de junio", (pytest.approx(2026), 6)),
        ("informe mensual", None),
    ],
)
def test_parse_report_period(question, expected):
    result = AIVanna._parse_report_period(question)
    if expected is None:
        assert result is None
    else:
        year, month = result
        assert year == expected[0]
        assert month == expected[1]


@pytest.mark.parametrize(
    "question,expected",
    [
        ("informe en pdf de mayo 2024", "pdf"),
        ("informe json mayo 2024", "json"),
        ("informe de mayo 2024", "html"),
    ],
)
def test_parse_report_format(question, expected):
    assert AIVanna._parse_report_format(question) == expected


def _bare_vanna() -> AIVanna:
    vn = object.__new__(AIVanna)
    vn._query_cache = MagicMock()
    vn._query_cache.get.return_value = None
    vn.provider = "grok"
    vn._manager_report_result = None
    return vn


def test_generate_sql_routes_manager_report_without_llm():
    vn = _bare_vanna()
    routed = {
        "status": "success",
        "message": "informe listo",
        "path": "/tmp/report_2024_05.html",
    }
    with patch.object(AIVanna, "route_manager_report_question", return_value=routed):
        sql = AIVanna.generate_sql(vn, "Genera el informe de mayo 2024")
    assert sql is None
    assert vn._manager_report_result == routed


def test_generate_sql_needs_period_prompt():
    vn = _bare_vanna()
    routed = {
        "status": "needs_period",
        "message": "necesito mes y año",
    }
    with patch.object(AIVanna, "route_manager_report_question", return_value=routed):
        sql = AIVanna.generate_sql(vn, "Genera el informe mensual gerencial")
    assert sql is None
    assert vn.pop_manager_report_result() == routed


def test_golden_sql_questions_not_routed_to_report():
    vn = _bare_vanna()
    with patch.object(
        AIVanna,
        "_top_customers_sql_template",
        return_value="SELECT 1",
    ):
        sql = AIVanna.generate_sql(vn, "Top 10 clientes con mayor facturación")
    assert "select" in sql.lower()
    assert vn._manager_report_result is None
