"""Fake-only tests for ``catalog.stock`` (contract docs/contracts/catalog-stock.md).

Never touches a real DB, credential, or live connection. The query path is
mocked; the pure validation, SQL builder, and per-SKU processing logic are
exercised directly with synthetic rows.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest

from modules.catalog import stock
from modules.catalog.stock import (
    _build_stock_sql,
    _canonicalize,
    _classify_warehouse,
    _coerce_number,
    _InvalidValue,
    _normalize_warehouse_code,
    _process,
    _validate_input,
    catalog_stock,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def row(
    sku="ABC",
    articulos_id=1,
    *,
    almacen_id=None,
    codigo=None,
    saldo=None,
    num_filas_ano=1,
):
    return {
        "norm_sku": sku,
        "articulos_id": articulos_id,
        "almacen_id": almacen_id,
        "almacen_codigo": codigo,
        "saldo_actual": saldo,
        "num_filas_ano": num_filas_ano,
    }


def entrada_invalida(result):
    return result == {
        "ok": False,
        "error": {
            "type": "entrada_invalida",
            "message": "entrada inválida para catalog.stock",
        },
    }


def error_consulta(result):
    return result == {
        "ok": False,
        "error": {
            "type": "error_consulta",
            "message": "error consultando inventario J3",
        },
    }


# ---------------------------------------------------------------------------
# Input validation (§2) — tests 1, 31, 32, 34
# ---------------------------------------------------------------------------


class TestValidateInput:
    def test_empty_skus(self):
        assert entrada_invalida(catalog_stock(None, {"skus": []}))

    def test_too_many_skus(self):
        assert entrada_invalida(
            catalog_stock(None, {"skus": ["A", "B", "C", "D", "E", "F"]})
        )

    def test_invalid_chars(self):
        assert entrada_invalida(catalog_stock(None, {"skus": ["A B"]}))
        assert entrada_invalida(catalog_stock(None, {"skus": ["A*B"]}))

    def test_extra_key(self):
        assert entrada_invalida(catalog_stock(None, {"skus": ["A"], "otro": 1}))

    def test_wrong_type(self):
        assert entrada_invalida(catalog_stock(None, {"skus": "A"}))
        assert entrada_invalida(catalog_stock(None, {"skus": [1]}))
        assert entrada_invalida(catalog_stock(None, "nope"))
        assert entrada_invalida(catalog_stock(None, None))

    def test_missing_skus(self):
        assert entrada_invalida(catalog_stock(None, {"sede": "neiva"}))

    def test_non_ascii_surviving_trim(self):
        # 'é' and full-width 'Ａ' survive trim and must be rejected, never mapped.
        assert entrada_invalida(catalog_stock(None, {"skus": ["é"]}))
        assert entrada_invalida(catalog_stock(None, {"skus": ["ＡBC"]}))

    def test_duplicate_normalized(self):
        assert entrada_invalida(catalog_stock(None, {"skus": ["abc", "ABC"]}))
        assert entrada_invalida(catalog_stock(None, {"skus": [" abc ", "ABC"]}))

    def test_normalize_spaces_and_case(self):
        skus, sede = _validate_input({"skus": [" abc ", "xyz"]})
        assert skus == ["ABC", "XYZ"]
        assert sede == "ambas"

    def test_sede(self):
        assert _validate_input({"skus": ["A"], "sede": "neiva"})[1] == "neiva"
        assert _validate_input({"skus": ["A"], "sede": " NEIVA "})[1] == "neiva"
        assert _validate_input({"skus": ["A"], "sede": "florencia"})[1] == "florencia"
        assert _validate_input({"skus": ["A"]})[1] == "ambas"
        assert _validate_input({"skus": ["A"], "sede": None})[1] == "ambas"
        assert entrada_invalida(catalog_stock(None, {"skus": ["A"], "sede": "bogota"}))

    def test_validate_no_db_on_input(self):
        # validation must fail closed without ever touching the query path
        with patch.object(stock, "_query_j3_system") as q:
            assert entrada_invalida(catalog_stock(None, {"skus": ["A B"]}))
            q.assert_not_called()


# ---------------------------------------------------------------------------
# SQL builder (§11) — parameterized, read-only, sentinel, dedup, ROW_NUMBER
# ---------------------------------------------------------------------------


class TestBuildSql:
    def test_parameterized(self):
        sql, params = _build_stock_sql(["ABC", "XYZ"])
        assert params == ("ABC", "XYZ")
        assert sql.count("%s") == 2
        assert "ABC" not in sql
        assert "XYZ" not in sql

    def test_read_only_and_sentinel(self):
        sql, _ = _build_stock_sql(["ABC"])
        assert "TOP (1001)" in sql
        assert "INSERT" not in sql.upper()
        assert "UPDATE" not in sql.upper()
        assert "DELETE" not in sql.upper()

    def test_left_join_base(self):
        sql, _ = _build_stock_sql(["ABC"])
        assert "AdmArticulos" in sql
        assert "LEFT JOIN" in sql

    def test_dedup_distinct_pair(self):
        sql, _ = _build_stock_sql(["ABC"])
        assert "SELECT DISTINCT" in sql
        assert "UPPER(LTRIM(RTRIM(a.ArticulosCodigo)))" in sql
        assert "a.ArticulosID" in sql

    def test_latest_period_row_number(self):
        sql, _ = _build_stock_sql(["ABC"])
        assert "ROW_NUMBER()" in sql
        assert "ORDER BY d.Ano DESC" in sql
        assert "num_filas_ano" in sql
        assert "WHERE base.rn = 1" in sql

    def test_no_warehouse_filter_in_sql(self):
        sql, _ = _build_stock_sql(["ABC"])
        assert "AlmacenCodigo IS NOT NULL" not in sql
        assert "AlmacenCodigo <> ''" not in sql


# ---------------------------------------------------------------------------
# Decimal canonicalization / coercion (§9) — tests 22, 35
# ---------------------------------------------------------------------------


class TestDecimal:
    def test_canonicalize_exact(self):
        assert _canonicalize(Decimal("12.34")) == "12.34"
        assert _canonicalize(Decimal("7")) == "7"
        assert _canonicalize(Decimal("0.5")) == "0.5"

    def test_canonicalize_zero(self):
        assert _canonicalize(Decimal("0")) == "0"
        assert _canonicalize(Decimal("0.00")) == "0"
        assert _canonicalize(Decimal("-0")) == "0"
        assert _canonicalize(Decimal("-0.000")) == "0"

    def test_coerce_accepted(self):
        assert _coerce_number(Decimal("5.5")) == Decimal("5.5")
        assert _coerce_number(3) == Decimal("3")

    def test_coerce_rejected(self):
        for bad in (True, 3.14, "5", Decimal("NaN"), Decimal("Infinity")):
            with pytest.raises(_InvalidValue):
                _coerce_number(bad)

    def test_coerce_null(self):
        assert _coerce_number(None) is None


# ---------------------------------------------------------------------------
# Warehouse classification (§6, §7)
# ---------------------------------------------------------------------------


class TestWarehouse:
    def test_normalize(self):
        assert _normalize_warehouse_code(" alm ") == "ALM"
        assert _normalize_warehouse_code("B.ROT") == "B.ROT"
        assert _normalize_warehouse_code("") is None
        assert _normalize_warehouse_code(None) is None
        assert _normalize_warehouse_code(123) is None

    def test_classify(self):
        assert _classify_warehouse("ALM") == "neiva"
        assert _classify_warehouse("BD6") == "neiva"
        assert _classify_warehouse("SUR") == "neiva"
        assert _classify_warehouse("DIS") == "neiva"
        assert _classify_warehouse("BOD") == "neiva"
        assert _classify_warehouse("FLO") == "florencia"
        assert _classify_warehouse("B.ROT") == "baja_rotacion"
        assert _classify_warehouse("CON") == "excluded"
        assert _classify_warehouse("CEN") == "excluded"
        assert _classify_warehouse("TRA") == "excluded"
        assert _classify_warehouse("NUEVO") is None
        assert _classify_warehouse(None) is None


# ---------------------------------------------------------------------------
# Per-SKU processing (§4, §5.2) — tests 3–18, 21, 23–27, 30, 36, 37
# ---------------------------------------------------------------------------


class TestProcess:
    def test_ok_neiva(self):
        r = _process(
            [row(codigo="ALM", almacen_id=10, saldo=Decimal("12.34"))], ["ABC"], "neiva"
        )
        assert r["ok"] is True
        assert r["sede"] == "neiva"
        res = r["results"][0]
        assert res["status"] == "ok"
        assert res["sedes"] == {"neiva": "12.34"}
        assert res["baja_rotacion"] is None
        assert res["baja_rotacion_confirmation"] == "not_required"

    def test_ok_florencia(self):
        r = _process(
            [row(codigo="FLO", almacen_id=11, saldo=Decimal("5"))], ["ABC"], "florencia"
        )
        res = r["results"][0]
        assert res["sedes"] == {"florencia": "5"}

    def test_ok_ambas(self):
        rows = [
            row(codigo="ALM", almacen_id=10, saldo=Decimal("3")),
            row(codigo="FLO", almacen_id=11, saldo=Decimal("2")),
        ]
        r = _process(rows, ["ABC"], "ambas")
        res = r["results"][0]
        assert res["sedes"] == {"neiva": "3", "florencia": "2"}

    def test_absent_is_null(self):
        r = _process(
            [row(codigo="ALM", almacen_id=10, saldo=Decimal("3"))], ["ABC"], "ambas"
        )
        res = r["results"][0]
        assert res["sedes"] == {"neiva": "3", "florencia": None}

    def test_zero_with_evidence(self):
        r = _process(
            [row(codigo="ALM", almacen_id=10, saldo=Decimal("0"))], ["ABC"], "neiva"
        )
        res = r["results"][0]
        assert res["sedes"] == {"neiva": "0"}

    def test_inventario_desconocido(self):
        r = _process([row(almacen_id=None, num_filas_ano=None)], ["ABC"], "ambas")
        assert r["results"][0] == {"sku": "ABC", "status": "inventario_desconocido"}

    def test_no_encontrado(self):
        r = _process([], ["ABC"], "ambas")
        assert r["results"][0] == {"sku": "ABC", "status": "no_encontrado"}

    def test_saldo_negativo(self):
        r = _process(
            [row(codigo="ALM", almacen_id=10, saldo=Decimal("-3"))], ["ABC"], "neiva"
        )
        res = r["results"][0]
        assert res == {"sku": "ABC", "status": "bloqueado", "reason": "saldo_negativo"}

    def test_negative_florencia(self):
        r = _process(
            [row(codigo="FLO", almacen_id=11, saldo=Decimal("-1"))],
            ["ABC"],
            "florencia",
        )
        assert r["results"][0]["reason"] == "saldo_negativo"

    def test_negative_baja_rotacion(self):
        r = _process(
            [row(codigo="B.ROT", almacen_id=17, saldo=Decimal("-1"))], ["ABC"], "ambas"
        )
        assert r["results"][0]["reason"] == "saldo_negativo"

    def test_cancellation_blocked(self):
        rows = [
            row(codigo="ALM", almacen_id=10, saldo=Decimal("3")),
            row(codigo="BD6", almacen_id=12, saldo=Decimal("-3")),
        ]
        res = _process(rows, ["ABC"], "neiva")["results"][0]
        assert res["reason"] == "saldo_negativo"

    def test_negative_only_excluded_ignored(self):
        r = _process(
            [row(codigo="CON", almacen_id=13, saldo=Decimal("-99"))], ["ABC"], "ambas"
        )
        res = r["results"][0]
        assert res["status"] == "ok"
        assert res["sedes"] == {"neiva": None, "florencia": None}
        assert res["baja_rotacion"] is None

    def test_codigo_no_clasificado(self):
        r = _process(
            [row(codigo=None, almacen_id=14, saldo=Decimal("1"))], ["ABC"], "neiva"
        )
        res = r["results"][0]
        assert res == {
            "sku": "ABC",
            "status": "bloqueado",
            "reason": "codigo_no_clasificado",
        }

    def test_real_row_blank_code_not_unknown_inventory(self):
        r = _process(
            [row(codigo="", almacen_id=15, saldo=Decimal("1"))], ["ABC"], "ambas"
        )
        res = r["results"][0]
        assert res["reason"] == "codigo_no_clasificado"

    def test_null_saldo_validacion_fallida(self):
        r = _process([row(codigo="ALM", almacen_id=10, saldo=None)], ["ABC"], "neiva")
        res = r["results"][0]
        assert res == {
            "sku": "ABC",
            "status": "bloqueado",
            "reason": "validacion_fallida",
        }

    def test_float_saldo_validacion_fallida(self):
        r = _process([row(codigo="ALM", almacen_id=10, saldo=3.5)], ["ABC"], "neiva")
        assert r["results"][0]["reason"] == "validacion_fallida"

    def test_excluded_only_all_null(self):
        rows = [row(codigo="CON", almacen_id=13, saldo=Decimal("2"))]
        res = _process(rows, ["ABC"], "ambas")["results"][0]
        assert res["status"] == "ok"
        assert res["sedes"] == {"neiva": None, "florencia": None}
        assert res["baja_rotacion"] is None
        assert res["baja_rotacion_confirmation"] == "not_required"

    def test_tie_validacion_fallida(self):
        rows = [
            row(codigo="ALM", almacen_id=10, saldo=Decimal("1"), num_filas_ano=2),
            row(codigo="ALM", almacen_id=10, saldo=Decimal("1"), num_filas_ano=2),
        ]
        res = _process(rows, ["ABC"], "neiva")["results"][0]
        assert res == {
            "sku": "ABC",
            "status": "bloqueado",
            "reason": "validacion_fallida",
        }

    def test_multi_id_validacion_fallida(self):
        rows = [
            row(articulos_id=1, codigo="ALM", almacen_id=10, saldo=Decimal("1")),
            row(articulos_id=2, codigo="ALM", almacen_id=10, saldo=Decimal("1")),
        ]
        res = _process(rows, ["ABC"], "neiva")["results"][0]
        assert res == {
            "sku": "ABC",
            "status": "bloqueado",
            "reason": "validacion_fallida",
        }

    def test_multi_id_precedes_unknown_inventory(self):
        rows = [
            row(articulos_id=1, almacen_id=None, num_filas_ano=None),
            row(articulos_id=2, almacen_id=None, num_filas_ano=None),
        ]
        res = _process(rows, ["ABC"], "ambas")["results"][0]
        assert res["reason"] == "validacion_fallida"

    def test_precedence_multiple_blocks(self):
        # unknown code + negative + null → single deterministic reason (§5.2)
        rows = [
            row(codigo="NUEVO", almacen_id=16, saldo=Decimal("-1")),
            row(codigo="ALM", almacen_id=10, saldo=None),
        ]
        res = _process(rows, ["ABC"], "neiva")["results"][0]
        assert res["reason"] == "codigo_no_clasificado"

    def test_mixed_skus(self):
        rows = [row(sku="GOOD", codigo="ALM", almacen_id=10, saldo=Decimal("1"))]
        r = _process(rows, ["GOOD", "MISSING", "NEG"], "ambas")
        results = r["results"]
        assert [x["sku"] for x in results] == ["GOOD", "MISSING", "NEG"]
        assert results[0]["status"] == "ok"
        assert results[1]["status"] == "no_encontrado"


# ---------------------------------------------------------------------------
# Low-rotation signal (§8) — test 18
# ---------------------------------------------------------------------------


class TestLowRotation:
    def _rot(self, sede, rot_saldo=None, neiva_saldo=None, florencia_saldo=None):
        rows = []
        if neiva_saldo is not None:
            rows.append(row(codigo="ALM", almacen_id=10, saldo=Decimal(neiva_saldo)))
        if florencia_saldo is not None:
            rows.append(
                row(codigo="FLO", almacen_id=11, saldo=Decimal(florencia_saldo))
            )
        if rot_saldo is not None:
            rows.append(row(codigo="B.ROT", almacen_id=17, saldo=Decimal(rot_saldo)))
        return _process(rows, ["ABC"], sede)["results"][0]

    def test_rot_absent_not_required(self):
        res = self._rot("ambas", neiva_saldo="0", florencia_saldo="0")
        assert res["baja_rotacion"] is None
        assert res["baja_rotacion_confirmation"] == "not_required"

    def test_rot_positive_physical_positive(self):
        res = self._rot("ambas", rot_saldo="7.5", neiva_saldo="1", florencia_saldo="0")
        assert res["baja_rotacion"] == "7.5"
        assert res["baja_rotacion_confirmation"] == "not_required"

    def test_rot_positive_physical_zero_required(self):
        res = self._rot("ambas", rot_saldo="7.5", neiva_saldo="0", florencia_saldo="0")
        assert res["baja_rotacion_confirmation"] == "required"

    def test_rot_positive_physical_absent_unknown(self):
        res = self._rot("ambas", rot_saldo="7.5", neiva_saldo="0")
        assert res["baja_rotacion_confirmation"] == "unknown"


# ---------------------------------------------------------------------------
# Full handler + global errors (§5.1) — test 19, 29
# ---------------------------------------------------------------------------


class TestHandler:
    def test_driver_exception(self):
        with patch.object(stock, "_query_j3_system", side_effect=RuntimeError("boom")):
            assert error_consulta(catalog_stock(None, {"skus": ["ABC"]}))

    def test_rows_not_list(self):
        with patch.object(stock, "_query_j3_system", return_value="notalist"):
            assert error_consulta(catalog_stock(None, {"skus": ["ABC"]}))

    def test_missing_keys(self):
        bad = [{"norm_sku": "ABC"}]  # missing expected keys
        with patch.object(stock, "_query_j3_system", return_value=bad):
            assert error_consulta(catalog_stock(None, {"skus": ["ABC"]}))

    def test_unexpected_sku(self):
        bad = [row(sku="OTHER", codigo="ALM", almacen_id=10, saldo=Decimal("1"))]
        with patch.object(stock, "_query_j3_system", return_value=bad):
            assert error_consulta(catalog_stock(None, {"skus": ["ABC"]}))

    def test_build_sql_exception(self):
        with patch.object(stock, "_build_stock_sql", side_effect=RuntimeError("boom")):
            assert error_consulta(catalog_stock(None, {"skus": ["ABC"]}))

    def test_process_exception(self):
        with patch.object(stock, "_query_j3_system", return_value=[]):
            with patch.object(stock, "_process", side_effect=RuntimeError("boom")):
                assert error_consulta(catalog_stock(None, {"skus": ["ABC"]}))

    def test_sentinel(self):
        rows = [row(sku="ABC", codigo="ALM", almacen_id=10, saldo=Decimal("1"))] * 1001
        with patch.object(stock, "_query_j3_system", return_value=rows):
            assert error_consulta(catalog_stock(None, {"skus": ["ABC"]}))

    def test_success_flow(self):
        rows = [row(sku="ABC", codigo="ALM", almacen_id=10, saldo=Decimal("12.34"))]
        with patch.object(stock, "_query_j3_system", return_value=rows) as q:
            result = catalog_stock(None, {"skus": ["abc"]})
        assert result["ok"] is True
        # query is parameterized and normalized
        _, params = q.call_args[0]
        assert params == ("ABC",)


# ---------------------------------------------------------------------------
# Row integrity (§5.1, §5.2) — global error_consulta, fake-only
# ---------------------------------------------------------------------------


class TestRowIntegrity:
    def test_articulos_id_null_global(self):
        r = _process(
            [row(articulos_id=None, codigo="ALM", almacen_id=10, saldo=Decimal("1"))],
            ["ABC"],
            "neiva",
        )
        assert error_consulta(r)

    def test_articulos_id_unhashable_global(self):
        r = _process(
            [row(articulos_id=[1], codigo="ALM", almacen_id=10, saldo=Decimal("1"))],
            ["ABC"],
            "neiva",
        )
        assert error_consulta(r)

    def test_num_filas_ano_invalid_global(self):
        for bad in (None, 0, -1, "2", True, 1.5):
            r = _process(
                [
                    row(
                        codigo="ALM",
                        almacen_id=10,
                        saldo=Decimal("1"),
                        num_filas_ano=bad,
                    )
                ],
                ["ABC"],
                "neiva",
            )
            assert error_consulta(r)

    def test_num_filas_ano_missing_key_global(self):
        r = _process(
            [
                {
                    "norm_sku": "ABC",
                    "articulos_id": 1,
                    "almacen_id": 10,
                    "almacen_codigo": "ALM",
                    "saldo_actual": Decimal("1"),
                }
            ],
            ["ABC"],
            "neiva",
        )
        assert error_consulta(r)

    def test_positive_marker_null_id_global(self):
        # LEFT JOIN row carries a positive multiplicity but no warehouse ID.
        r = _process([row(almacen_id=None, num_filas_ano=1)], ["ABC"], "ambas")
        assert error_consulta(r)

    def test_real_id_absent_marker_global(self):
        r = _process(
            [row(codigo="ALM", almacen_id=10, saldo=Decimal("1"), num_filas_ano=None)],
            ["ABC"],
            "neiva",
        )
        assert error_consulta(r)

    def test_almacen_id_invalid_type_global(self):
        for bad in (True, 3.5, "10", [10]):
            r = _process(
                [
                    row(
                        codigo="ALM",
                        almacen_id=bad,
                        saldo=Decimal("1"),
                        num_filas_ano=1,
                    )
                ],
                ["ABC"],
                "neiva",
            )
            assert error_consulta(r)


# ---------------------------------------------------------------------------
# Registry + bounded path (§14.5, §11)
# ---------------------------------------------------------------------------


class TestRegistryAndBounds:
    def test_registry_entry(self):
        from depotru_kernel.auth import Audience, ToolScope, audience_may_use
        from depotru_tools.registry import get_default_registry

        spec = get_default_registry().get("catalog.stock")
        assert spec.scope == ToolScope.SALES_PORTFOLIO
        assert spec.public_safe is False
        assert audience_may_use(Audience.SALES, spec.scope)
        assert audience_may_use(Audience.ADMIN, spec.scope)
        assert not audience_may_use(Audience.PUBLIC, spec.scope)
        assert not audience_may_use(Audience.CUSTOMER, spec.scope)

    def test_timeout_and_retries_explicit(self):
        assert stock._QUERY_TIMEOUT_SECONDS <= 10
        assert stock._QUERY_RETRIES == 0
        assert stock.MAX_RESULT_ROWS == 1000

    def test_handler_not_public_safe(self):
        from depotru_tools.registry import get_default_registry

        assert get_default_registry().get("catalog.stock").public_safe is False
