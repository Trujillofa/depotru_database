"""Tests for authoritative product attribute resolution."""

from business_analyzer.core.product_attrs import (
    effective_marca_sql,
    resolve_effective_marca,
)


def test_resolve_effective_marca_prefers_producto_marca():
    assert resolve_effective_marca("HERRAMIENTAS SIKA", "SIKA") == "SIKA"
    assert resolve_effective_marca("HERRAMIENTAS", "PINTUCO") == "PINTUCO"


def test_resolve_effective_marca_falls_back_to_banco_datos():
    assert resolve_effective_marca("GRIVAL", None) == "GRIVAL"
    assert resolve_effective_marca("GRIVAL", "") == "GRIVAL"


def test_resolve_effective_marca_rejects_bad_values():
    assert resolve_effective_marca("S/I", "PINTUCO") == "PINTUCO"
    assert resolve_effective_marca("N/A", "NA") is None


def test_effective_marca_sql_prefers_master_column():
    sql = effective_marca_sql().upper()
    assert "PRODUCTO_MARCA" in sql
    assert "COALESCE" in sql
    assert "DATABASE_DEFAULT" in sql
    first_coalesce = sql.index("COALESCE")
    assert sql.find("PRODUCTO_MARCA", first_coalesce) < sql.find(
        ".MARCA", first_coalesce
    )
