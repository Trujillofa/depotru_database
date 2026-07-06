"""Static verification for J3System sales-to-warehouse reference documentation."""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
DOC_PATH = REPO_ROOT / "docs/reference/j3system-sales-warehouse-query.md"

EXPECTED_WAREHOUSE_CODES = (
    "ALM",
    "SUR",
    "BD6",
    "DIS",
    "BOD",
    "BDT",
    "FLO",
    "CEN",
    "MDL",
    "EXH",
    "TRA",
    "CON",
    "B.ROT",
    "EXD",
)

REQUIRED_SECTIONS = (
    "InvVentas",
    "InvImpresionFactura",
    "VentaID",
    "Almancen",
    "AdmAlmacen",
    "CAST(iif.VentaID AS int)",
    "## Caveats",
)


@pytest.fixture
def doc_text() -> str:
    assert DOC_PATH.exists(), f"Missing reference doc: {DOC_PATH}"
    return DOC_PATH.read_text(encoding="utf-8")


@pytest.mark.unit
def test_j3system_doc_exists(doc_text: str) -> None:
    assert len(doc_text) > 0


@pytest.mark.unit
@pytest.mark.parametrize("section", REQUIRED_SECTIONS)
def test_j3system_doc_required_sections(doc_text: str, section: str) -> None:
    assert section in doc_text, f"Missing required content: {section}"


@pytest.mark.unit
def test_j3system_doc_has_working_sql_block(doc_text: str) -> None:
    assert "```sql" in doc_text
    assert "FROM InvVentas v" in doc_text
    assert "JOIN InvImpresionFactura iif" in doc_text


@pytest.mark.unit
def test_j3system_doc_warehouse_codes_table_has_14_codes(doc_text: str) -> None:
    table_start = doc_text.index("## Warehouse Codes")
    table_section = doc_text[table_start:]
    codes_found = []
    for code in EXPECTED_WAREHOUSE_CODES:
        assert f"`{code}`" in table_section, f"Missing warehouse code: {code}"
        codes_found.append(code)
    assert len(codes_found) == 14


@pytest.mark.unit
def test_j3system_doc_caveats_mention_multi_row_and_empty_almancen(
    doc_text: str,
) -> None:
    caveats = doc_text.split("## Caveats", 1)[1]
    assert "multiple rows" in caveats.lower()
    assert "Almancen = ''" in caveats


@pytest.mark.unit
def test_j3system_doc_cross_linked_from_ai_context_readme() -> None:
    readme = (REPO_ROOT / "docs/ai-context/README.md").read_text(encoding="utf-8")
    assert "j3system-sales-warehouse-query" in readme


@pytest.mark.unit
def test_j3system_doc_cross_linked_from_mcp_readme() -> None:
    readme = (REPO_ROOT / "mcp/README.md").read_text(encoding="utf-8")
    assert "j3system-sales-warehouse-query" in readme
