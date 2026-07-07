"""Tests for branch-scoped manager sales reports."""

import pytest

from business_analyzer.ai.base import AIVanna
from business_analyzer.analysis.manager_report.helpers import (
    BRANCH_SLUGS,
    branch_display_name,
    branch_slug,
    report_output_basename,
)
from business_analyzer.analysis.manager_report.queries import SalesQueryRunner


@pytest.mark.parametrize(
    "code,expected",
    [
        ("FEF", "sika_center"),
        ("FET", "calle_5"),
        ("FED", "almacen_principal"),
        (None, None),
    ],
)
def test_branch_slug(code, expected):
    assert branch_slug(code) == expected


def test_branch_display_name():
    assert branch_display_name("FEF") == "Sika Center"


def test_report_output_basename_for_branch():
    assert (
        report_output_basename(2024, 5, "html", branch_document_code="FEF")
        == "report_sika_center_2024_05.html"
    )
    assert report_output_basename(2024, 5, "html") == "report_2024_05.html"


def test_sales_query_runner_product_exclusion_in_sql():
    runner = SalesQueryRunner("2024-05-01", "2024-05-31", 2024)
    clause = runner._sales_from_clause()
    assert "ArticulosNombre" in clause
    assert "SERVICIO DE CORTE" not in clause  # parameterized
    assert runner._period_params()[-2:] == (
        "SERVICIO DE CORTE",
        "BOLSA BIODEGRADABLE PARA ENTREGA",
    )


def test_sales_query_runner_branch_filter_in_sql():
    runner = SalesQueryRunner(
        "2024-05-01",
        "2024-05-31",
        2024,
        branch_document_code="FEF",
    )
    clause = runner._sales_from_clause()
    assert "DocumentosCodigo = %s" in clause
    params = runner._period_params()
    assert "FEF" in params
    assert params.index("FEF") < params.index("SERVICIO DE CORTE")


@pytest.mark.parametrize(
    "question,expected",
    [
        ("Genera el informe gerencial de Sika Center para mayo 2024", "FEF"),
        ("reporte mensual calle 5 junio 2024", "FET"),
        ("informe de mayo 2024", None),
    ],
)
def test_branch_document_code_from_report_question(question, expected):
    assert AIVanna._branch_document_code(question) == expected


def test_branch_slugs_cover_known_stores():
    assert BRANCH_SLUGS["FEF"] == "sika_center"
