"""Fixture/mock tests for manager_report/queries.py. No live DB."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from business_analyzer.analysis.manager_report.helpers import EXCLUDED_PRODUCT_NAMES
from business_analyzer.analysis.manager_report.queries import SalesQueryRunner
from business_analyzer.core.database import ConnectionError, QueryError
from depotru_kernel.documents import CANONICAL_EXCLUDED_DOCUMENT_CODES


class FakeDatabase:
    """Context-manager stand-in for Database."""

    def __init__(self, execute_side_effect=None, j3_conn=None):
        self.execute_side_effect = execute_side_effect
        self.j3_conn = j3_conn
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute_query(self, query, params=None):
        self.calls.append((query, params))
        if callable(self.execute_side_effect):
            return self.execute_side_effect(query, params)
        if self.execute_side_effect is not None:
            return self.execute_side_effect
        return []

    def get_j3system_connection(self):
        if isinstance(self.j3_conn, Exception):
            raise self.j3_conn
        if self.j3_conn is None:
            raise ConnectionError("J3 unavailable")
        return self.j3_conn


@pytest.fixture
def canonical_codes(monkeypatch):
    codes = list(CANONICAL_EXCLUDED_DOCUMENT_CODES)
    monkeypatch.setattr(
        "business_analyzer.analysis.manager_report.queries.Config.EXCLUDED_DOCUMENT_CODES",
        codes,
    )
    return codes


def _runner(**kwargs) -> SalesQueryRunner:
    defaults = {
        "start_date": "2024-05-01",
        "end_date": "2024-05-31",
        "year": 2024,
        "month": 5,
    }
    defaults.update(kwargs)
    return SalesQueryRunner(**defaults)


@pytest.mark.unit
def test_period_params_include_canonical_excluded_docs(canonical_codes):
    runner = _runner()
    params = runner._period_params()
    assert params[0] == "2024-05-01"
    assert params[1] == "2024-05-31"
    for code in ("XY", "AS", "TS"):
        assert code in params
    for code in canonical_codes:
        assert code in params
    assert params[-2:] == tuple(name.upper() for name in EXCLUDED_PRODUCT_NAMES)


@pytest.mark.unit
def test_sales_from_clause_parameterizes_exclusions(canonical_codes):
    runner = _runner()
    clause = runner._sales_from_clause()
    assert "Fecha BETWEEN %s AND %s" in clause
    assert "DocumentosCodigo NOT IN" in clause
    assert "XY" not in clause  # codes are bound params, not literals
    assert "SERVICIO DE CORTE" not in clause
    placeholders = ", ".join(["%s"] * len(canonical_codes))
    assert placeholders in clause


@pytest.mark.unit
def test_branch_filter_and_invalid_identifier(canonical_codes):
    runner = _runner(branch_document_code="fef")
    assert runner.branch_document_code == "FEF"
    assert "DocumentosCodigo = %s" in runner._sales_from_clause()
    assert "FEF" in runner._period_params()

    with pytest.raises(ValueError, match="Invalid"):
        _runner(branch_document_code="FEF'; DROP")


@pytest.mark.unit
def test_month_derived_from_start_date():
    runner = SalesQueryRunner("2024-11-01", "2024-11-30", 2024)
    assert runner.month == 11


@pytest.mark.unit
def test_effective_sql_helpers_exclude_bad_vendor_tokens():
    sql = SalesQueryRunner._effective_proveedor_sql()
    assert "SIN PROVEEDOR" in sql
    assert "pa.proveedor_descripcion" in sql
    marca = SalesQueryRunner._effective_marca_sql()
    assert "pa" in marca or "marca" in marca.lower()


@pytest.mark.unit
def test_fetch_sales_data_uses_period_sql(canonical_codes):
    fake = FakeDatabase(execute_side_effect=[{"Fecha": "2024-05-01"}])
    runner = _runner()
    with patch.object(SalesQueryRunner, "_open_db", return_value=fake):
        rows = runner.fetch_sales_data()
    assert rows == [{"Fecha": "2024-05-01"}]
    query, params = fake.calls[0]
    assert "TotalMasIva" in query
    assert "DocumentosCodigo NOT IN" in query
    assert "TS" in params


@pytest.mark.unit
def test_fetch_sql_aggregations_dispatches_all_result_sets():
    def dispatch(query, params):
        if "AS order_count" in query:
            return [
                {
                    "total_with_iva": 121000,
                    "total_without_iva": 100000,
                    "total_cost": 70000,
                    "total_quantity": 10,
                    "order_count": 2,
                }
            ]
        if "AS product_name" in query and "TOP 15" in query:
            return [{"product_name": "P", "sku": "S", "total_revenue": 100}]
        if "AS customer_name" in query and "TOP 15" in query:
            return [{"customer_name": "C", "total_revenue": 200}]
        if "AS categoria" in query:
            return [{"categoria": "Herramientas", "total_revenue": 50}]
        if "AS sale_date" in query:
            return [{"sale_date": "2024-05-01", "revenue_with_iva": 10}]
        if "AS vendor_name" in query and "TOP 20" in query:
            return [{"vendor_name": "SIKA", "total_revenue": 80}]
        if "AS marca_name" in query:
            return [{"marca_name": "SIKA", "total_revenue": 80}]
        if "AS customer_name" in query and "AS vendor_name" in query:
            return [{"customer_name": "C", "vendor_name": "SIKA", "revenue": 10}]
        if "AS sku" in query and "sku_monthly" not in query.lower():
            return [{"sku": "S", "product_name": "P", "quantity": 2}]
        if "AS entity_name" in query:
            return [{"entity_name": "P", "total_revenue": 10}]
        if "AS product_name" in query and "HAVING" in query:
            return [{"product_name": "P", "revenue": 10, "cost": 4, "quantity": 5}]
        if "AS sku" in query or "SELECT DISTINCT" in query:
            return [{"customer_name": "C", "product_name": "P", "sku": "S"}]
        return []

    fake = FakeDatabase(execute_side_effect=dispatch)
    runner = _runner()
    with patch.object(SalesQueryRunner, "_open_db", return_value=fake):
        data = runner.fetch_sql_aggregations()

    assert data["summary"]["total_with_iva"] == 121000
    assert data["top_products"][0]["product_name"] == "P"
    assert data["top_customers"][0]["customer_name"] == "C"
    assert data["vendor_sales"][0]["vendor_name"] == "SIKA"
    assert data["marca_sales"][0]["marca_name"] == "SIKA"
    assert len(fake.calls) >= 10
    margin_sql = next(q for q, _ in fake.calls if "HAVING SUM(bd.Cantidad)" in q)
    assert "AS proveedor" in margin_sql


@pytest.mark.unit
def test_fetch_ytd_and_year_to_date(canonical_codes):
    def dispatch(query, params):
        assert params[0] == "2024-01-01"
        assert params[1] == "2024-12-31"
        assert "TS" in params
        if "AS last_purchase" in query:
            return [{"customer_name": "C", "sku": "S", "quantity": 2}]
        if "AS primary_vendor" in query:
            return [{"customer_name": "C", "sku": "S", "primary_vendor": "SIKA"}]
        return [{"Fecha": "2024-02-01"}]

    fake = FakeDatabase(execute_side_effect=dispatch)
    runner = _runner()
    with patch.object(SalesQueryRunner, "_open_db", return_value=fake):
        ytd = runner.fetch_ytd_sql_aggregations()
        rows = runner.fetch_year_to_date_data()
    assert ytd["customer_products"][0]["sku"] == "S"
    assert ytd["primary_vendors"][0]["primary_vendor"] == "SIKA"
    assert rows[0]["Fecha"] == "2024-02-01"


@pytest.mark.unit
def test_fetch_sb_product_map_normalizes_bad_vendor():
    fake = FakeDatabase(
        execute_side_effect=[
            {
                "producto_codigo": "SKU1",
                "proveedor_descripcion": "NA",
                "producto_marca": "SIKA",
                "producto_rubro": "Químicos",
                "producto_subrubro": "Impermeabilizantes",
            },
            {
                "producto_codigo": "SKU2",
                "proveedor_descripcion": "SIKA COLOMBIA",
                "producto_marca": "",
                "producto_rubro": None,
                "producto_subrubro": None,
            },
        ]
    )
    runner = _runner()
    with patch.object(SalesQueryRunner, "_open_db", return_value=fake):
        pmap = runner.fetch_sb_product_map()
    assert pmap["SKU1"]["proveedor"] is None
    assert pmap["SKU1"]["marca"] == "SIKA"
    assert pmap["SKU2"]["proveedor"] == "SIKA COLOMBIA"
    assert pmap["SKU2"]["marca"] is None


@pytest.mark.unit
def test_budget_skip_for_branch_does_not_open_db():
    runner = _runner(branch_document_code="FEF")
    with patch.object(SalesQueryRunner, "_open_db") as open_db:
        payload = runner.fetch_budget_vs_actual()
    open_db.assert_not_called()
    assert payload["available"] is False
    assert "sede" in payload["note"].lower()


@pytest.mark.unit
def test_budget_no_meta_and_success_paths():
    runner = _runner()
    empty_meta = FakeDatabase(execute_side_effect=lambda q, p: [])
    with patch.object(SalesQueryRunner, "_open_db", return_value=empty_meta):
        missing = runner.fetch_budget_vs_actual()
    assert missing["available"] is False
    assert missing["meta_origen"] == "sin_meta"

    seq = [
        [{"periodo": 20235}],
        [
            {
                "vendedor_codigo": "01",
                "vendedor_nombre": "Ana",
                "presupuesto": 100,
                "ventas_reales": 80,
            }
        ],
        [
            {
                "presupuesto_total": 100,
                "ventas_reales_total": 80,
                "cumplimiento_pct": 80,
                "brecha_total": 20,
            }
        ],
    ]

    def next_row(query, params):
        return seq.pop(0)

    fake = FakeDatabase(execute_side_effect=next_row)
    with patch.object(SalesQueryRunner, "_open_db", return_value=fake):
        found = runner.fetch_budget_vs_actual()
    assert found["available"] is True
    assert found["meta_origen"] == "mismo_mes_historico"
    assert found["sellers"][0]["vendedor_nombre"] == "Ana"
    assert "histórica" in (found["note"] or "")


@pytest.mark.unit
def test_j3_connection_error_returns_empty_not_fake_zeros():
    runner = _runner()
    fake = FakeDatabase(j3_conn=ConnectionError("down"))
    with patch.object(SalesQueryRunner, "_open_db", return_value=fake):
        assert runner.fetch_j3system_inventory() == {}
        assert runner.fetch_j3system_warehouse_sales() == {
            "breakdown": [],
            "sales": [],
        }
        products, vendors = runner.fetch_j3system_product_details()
        assert products == {}
        assert vendors == {}


@pytest.mark.unit
def test_j3_attribute_error_is_not_swallowed_as_empty_stock():
    runner = _runner()
    fake = FakeDatabase()
    fake.get_j3system_connection = MagicMock(
        side_effect=AttributeError("typo in helper")
    )
    with patch.object(SalesQueryRunner, "_open_db", return_value=fake):
        with pytest.raises(AttributeError, match="typo"):
            runner.fetch_j3system_inventory()
        with pytest.raises(AttributeError, match="typo"):
            runner.fetch_j3system_product_details()
        with pytest.raises(AttributeError, match="typo"):
            runner.fetch_j3system_warehouse_sales()


@pytest.mark.unit
def test_j3_inventory_maps_rows():
    cursor = MagicMock()
    cursor.__iter__ = lambda self: iter(
        [
            {
                "ArticulosCodigo": "SKU1",
                "ArticulosNombre": "Taladro",
                "ArticulosPeso": 1.5,
                "stock_quantity": 4,
            }
        ]
    )
    conn = MagicMock()
    conn.cursor.return_value = cursor
    fake = FakeDatabase(j3_conn=conn)
    runner = _runner()
    with patch.object(SalesQueryRunner, "_open_db", return_value=fake):
        inv = runner.fetch_j3system_inventory()
    assert inv["SKU1"]["name"] == "Taladro"
    assert inv["SKU1"]["stock_quantity"] == 4.0


@pytest.mark.unit
def test_query_error_still_degrades_j3_optional_sections():
    runner = _runner()
    fake = FakeDatabase(j3_conn=QueryError("timeout"))
    with patch.object(SalesQueryRunner, "_open_db", return_value=fake):
        assert runner.fetch_j3system_inventory() == {}


class _Cursor:
    def __init__(self, batches):
        self.batches = list(batches)
        self.current = []

    def execute(self, *_args, **_kwargs):
        self.current = self.batches.pop(0) if self.batches else []

    def __iter__(self):
        return iter(self.current)

    def close(self):
        return None


@pytest.mark.unit
def test_j3_warehouse_and_product_details_map_rows():
    cursor = _Cursor(
        [
            [{"Almacen": "ALM", "qty": 1}],
            [{"Documento": "1", "Almacen": "ALM"}],
        ]
    )
    conn = MagicMock()
    conn.cursor.return_value = cursor
    runner = _runner()
    with patch.object(
        SalesQueryRunner, "_open_db", return_value=FakeDatabase(j3_conn=conn)
    ):
        data = runner.fetch_j3system_warehouse_sales(detail_limit=10)
    assert data["breakdown"][0]["Almacen"] == "ALM"
    assert data["sales"][0]["Documento"] == "1"

    prod_cursor = _Cursor(
        [
            [
                {
                    "ArticulosCodigo": "SKU1",
                    "ArticulosNombre": "Taladro",
                    "ArticulosPeso": 1.2,
                    "GruposCodigo": "G",
                    "marca": "BOSCH",
                    "vendor_terceros_id": 9,
                    "vendor_name": "Bosch SAS",
                }
            ]
        ]
    )
    prod_conn = MagicMock()
    prod_conn.cursor.return_value = prod_cursor
    with patch.object(
        SalesQueryRunner, "_open_db", return_value=FakeDatabase(j3_conn=prod_conn)
    ):
        products, vendors = runner.fetch_j3system_product_details()
    assert products["SKU1"]["marca"] == "BOSCH"
    assert vendors["BOSCH SAS"] == "Bosch SAS"


@pytest.mark.unit
def test_year_to_date_includes_branch_param(canonical_codes):
    fake = FakeDatabase(execute_side_effect=[{"Fecha": "2024-01-02"}])
    runner = _runner(branch_document_code="FET")
    with patch.object(SalesQueryRunner, "_open_db", return_value=fake):
        runner.fetch_year_to_date_data()
        runner.fetch_ytd_sql_aggregations()
    for _query, params in fake.calls:
        assert "FET" in params
        assert "TS" in params
