"""Tests for the brand business report and its Vanna integration."""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from business_analyzer.ai.flask_app import SmartVannaFlaskApp
from business_analyzer.ai.recommended_reports import get_recommended_reports
from business_analyzer.reports import brand_report
from business_analyzer.reports.brand_html import render_html
from business_analyzer.reports.brand_report import (
    BrandReportBuilder,
    brand_report_basename,
    build_brand_report_result,
    list_brands,
    normalize_brand,
    resolve_brand_period,
    resolve_brand_period_range,
)


class _StubVanna:
    run_sql_is_set = True
    provider = "grok"
    _last_result_df = None

    def generate_sql(self, *args, **kwargs):
        return None

    def pop_manager_report_result(self):
        return None

    def is_sql_valid(self, sql):
        return bool(sql)

    def should_generate_chart(self, dataframe):
        return False


def _kpi(rev: float = 100.0) -> dict:
    cost = rev * 0.8
    return {
        "lines": 1,
        "skus": 1,
        "customers": 1,
        "invoices": 1,
        "rev": rev,
        "rev_iva": rev * 1.19,
        "cost": cost,
        "qty": 10.0,
        "gross_rev": rev,
        "return_rev": 0.0,
        "return_lines": 0,
        "profit": rev - cost,
        "margin_pct": 20.0,
        "avg_ticket": rev,
        "price_unit": 10.0,
        "return_pct": 0.0,
    }


def _minimal_report() -> dict:
    return {
        "status": "ok",
        "brand": "SIKA",
        "brand_label": "Sika",
        "year": 2026,
        "as_of": "2026-11-10",
        "period": {
            "start": "2026-01-01",
            "end": "2026-11-10",
            "requested_start": "2026-01-01",
            "requested_end": "2026-12-31",
            "prior_start": "2025-01-01",
            "prior_end": "2025-11-10",
            "days": 314,
            "partial": True,
            "clamped": True,
            "full_year": True,
        },
        "kpis": {
            "current": _kpi(100.0),
            "prior": _kpi(90.0),
            "company_current": _kpi(1000.0),
            "company_prior": _kpi(900.0),
        },
        "annual": [
            {
                "year": 2025,
                "rev": 90.0,
                "profit": 18.0,
                "margin_pct": 20.0,
                "qty": 10.0,
                "customers": 1,
                "invoices": 1,
                "partial": False,
            }
        ],
        "monthly": [
            {
                "month": 1,
                "current_rev": 10.0,
                "prior_rev": 9.0,
                "current_margin_pct": 20.0,
                "prior_margin_pct": 19.0,
                "current_qty": 1.0,
                "partial": False,
            }
        ],
        "warehouses": {
            "current": [
                {"code": "ALM", "rev": 100.0, "margin_pct": 20.0, "share_pct": 100.0}
            ],
            "prior": [{"code": "ALM", "rev": 90.0}],
        },
        "branches": {
            "current": [
                {
                    "code": "FED",
                    "doc_name": "FACTURA",
                    "rev": 100.0,
                    "share_pct": 100.0,
                    "margin_pct": 20.0,
                    "invoices": 1,
                    "customers": 1,
                }
            ],
            "prior": [],
        },
        "rubros": {
            "current": [
                {"rubro": "R", "subrubro": "S", "rev": 100.0, "margin_pct": 20.0}
            ],
            "prior": [],
        },
        "products": {
            "top": [
                {
                    "sku": "1",
                    "name": "Producto",
                    "rev": 100.0,
                    "qty": 10.0,
                    "margin_pct": 20.0,
                    "share_pct": 100.0,
                    "prior_rev": 90.0,
                }
            ],
            "items": [],
            "gains": [],
            "losses": [],
            "promo": {
                "current": {"rev": 10.0, "margin_pct": 15.0, "skus": 1},
                "prior": {"rev": 5.0, "margin_pct": 20.0, "skus": 1},
                "base_current": {"rev": 90.0, "margin_pct": 20.0, "skus": 1},
                "base_prior": {"rev": 85.0, "margin_pct": 20.0, "skus": 1},
                "share_pct": 10.0,
                "prior_share_pct": 5.0,
            },
            "master_gap": {
                "current": {"skus": 0, "rev": 0.0},
                "prior": {"skus": 0, "rev": 0.0},
                "share_pct": 0.0,
                "prior_share_pct": 0.0,
            },
        },
        "customers": {
            "top": [],
            "stats": {
                "customers": 1,
                "prior_customers": 1,
                "top10_share_pct": 100.0,
                "recurring": {
                    "customers": 1,
                    "current_rev": 100.0,
                    "prior_rev": 90.0,
                },
                "new": {"customers": 0, "rev": 0.0, "top": []},
                "lost": {"customers": 0, "rev": 0.0, "top": []},
                "buckets": {
                    "one": {"customers": 1, "rev": 100.0, "share_pct": 100.0},
                    "two_three": {"customers": 0, "rev": 0.0, "share_pct": 0.0},
                    "four_nine": {"customers": 0, "rev": 0.0, "share_pct": 0.0},
                    "ten_plus": {"customers": 0, "rev": 0.0, "share_pct": 0.0},
                },
            },
        },
        "vendors": [],
        "returns": {
            "current": _kpi(100.0),
            "prior": _kpi(90.0),
            "by_doc": {"current": [], "prior": []},
            "top_customers": [],
            "top_products": [],
        },
        "inventory": {"available": False, "message": "Inventario no disponible."},
        "findings": [
            {
                "title": "Hallazgo",
                "evidence": "Evidencia",
                "risk": "Riesgo",
                "priority": "Alta",
            }
        ],
        "projection": {"run_rate": 110.0, "prior_full": 90.0, "growth_pct": 22.2},
        "excluded_document_codes": ["XY"],
    }


class _FakeDB:
    """Minimal DB stub that answers KPI/max-date queries and records SQL."""

    def __init__(self, max_date=None):
        self.max_date = max_date or date(2026, 11, 17)
        self.queries = []

    def execute_query(self, sql, params=None):
        self.queries.append((sql, tuple(params or ())))
        if "MAX(bd.Fecha)" in sql:
            return [{"max_date": self.max_date}]
        if (
            "COUNT(*) AS lines" in sql
            and "SUM(bd.TotalSinIva) AS rev" in sql
            and "SUM(bd.TotalMasIva) AS rev_iva" in sql
        ):
            return [
                {
                    "lines": 1,
                    "skus": 1,
                    "customers": 1,
                    "invoices": 1,
                    "rev": 100.0,
                    "rev_iva": 119.0,
                    "cost": 80.0,
                    "qty": 10.0,
                    "gross_rev": 100.0,
                    "return_rev": 0.0,
                    "return_lines": 0,
                }
            ]
        return []

    def get_j3system_connection(self):
        raise RuntimeError("J3 unavailable in test")


class _FakeCursor:
    def __init__(self):
        self.sql = ""
        self.params = ()
        self.closed = False

    def execute(self, sql, params=None):
        self.sql = sql
        self.params = tuple(params or ())

    def fetchone(self):
        return {"max_year": 2026}

    def __iter__(self):
        return iter([])

    def close(self):
        self.closed = True


class _FakeJ3Connection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self, as_dict=True):
        return self._cursor

    def close(self):
        pass


class _FakeJ3DB:
    def __init__(self, cursor):
        self.cursor_obj = cursor

    def get_j3system_connection(self):
        return _FakeJ3Connection(self.cursor_obj)


class TestBrandPeriods:
    def test_current_year_partial(self):
        period = resolve_brand_period(2026, max_date=date(2026, 11, 10))
        assert period["start"] == date(2026, 1, 1)
        assert period["end"] == date(2026, 11, 10)
        assert period["prior_end"] == date(2025, 11, 10)
        assert period["partial"] is True
        assert period["days"] == 314

    def test_past_year_closes_december(self):
        period = resolve_brand_period(2025, max_date=date(2026, 11, 10))
        assert period["end"] == date(2025, 12, 31)
        assert period["prior_end"] == date(2024, 12, 31)
        assert period["partial"] is False

    def test_future_year_rejected(self):
        with pytest.raises(ValueError):
            resolve_brand_period(2027, max_date=date(2026, 11, 10))

    def test_basename_and_brand_normalization(self):
        assert normalize_brand("  sika  ") == "sika"
        name = brand_report_basename("SIKA", "2026-01-01", "2026-12-31", "json")
        assert name.endswith(".json")
        assert "SIKA" in name
        assert "2026-01-01_2026-12-31" in name

    def test_explicit_range_clamps_to_available_data(self):
        period = resolve_brand_period_range(
            date(2026, 1, 1),
            date(2026, 12, 31),
            max_date=date(2026, 11, 17),
        )
        assert period["end"] == date(2026, 11, 17)
        assert period["requested_end"] == date(2026, 12, 31)
        assert period["prior_end"] == date(2025, 11, 17)
        assert period["clamped"] is True
        assert period["full_year"] is True

    def test_explicit_range_keeps_complete_prior_year(self):
        period = resolve_brand_period_range(
            date(2025, 1, 1),
            date(2025, 12, 31),
            max_date=date(2026, 11, 17),
        )
        assert period["end"] == date(2025, 12, 31)
        assert period["prior_start"] == date(2024, 1, 1)
        assert period["prior_end"] == date(2024, 12, 31)
        assert period["clamped"] is False
        assert period["full_year"] is True

    def test_explicit_range_rejects_reversed_dates(self):
        with pytest.raises(ValueError):
            resolve_brand_period_range(
                date(2026, 12, 31),
                date(2026, 1, 1),
                max_date=date(2026, 11, 17),
            )


class TestBrandCondition:
    def test_sika_includes_name_fallback(self):
        builder = object.__new__(BrandReportBuilder)
        builder.brand_upper = "SIKA"
        sql, params = builder._brand_condition()
        assert "LIKE %s" in sql
        assert "%SIKA%" in params

    def test_short_brand_skips_name_fallback(self):
        builder = object.__new__(BrandReportBuilder)
        builder.brand_upper = "ICO"
        sql, params = builder._brand_condition()
        assert "LIKE %s" not in sql
        assert "%ICO%" not in params


class TestBrandReportBuild:
    def test_render_html_contains_sections(self):
        html = render_html(_minimal_report())
        assert "Informe de marca — Sika" in html
        assert "Resumen ejecutivo" in html
        assert "Tablero de resultados" in html
        assert "Clientes" in html
        assert "Plan de acción" in html
        assert "Metodología y limitaciones" in html
        assert "Hallazgo" in html

    def test_build_result_writes_html(self, tmp_path, monkeypatch):
        class FakeBuilder:
            def __init__(self, *args, **kwargs):
                pass

            def build(self):
                return _minimal_report()

        monkeypatch.setattr(brand_report, "BrandReportBuilder", FakeBuilder)
        result = build_brand_report_result(
            brand="SIKA",
            year=2026,
            as_of="2026-11-10",
            fmt="html",
            output_dir=tmp_path,
        )
        assert result["status"] == "success"
        path = Path(result["path"])
        assert path.is_file()
        assert "Informe de marca" in path.read_text(encoding="utf-8")

    def test_build_result_rejects_bad_format(self, tmp_path):
        result = build_brand_report_result(
            brand="SIKA", year=2026, fmt="pdf", output_dir=tmp_path
        )
        assert result["status"] == "error"

    def test_list_brands_shape(self, monkeypatch):
        class FakeDB:
            def execute_query(self, sql, params=None):
                if "MAX(" in sql:
                    return [{"max_date": date(2026, 11, 10)}]
                return [
                    {"brand": "SIKA", "skus": 10, "rev": 100.0},
                    {"brand": "PINTUCO", "skus": 5, "rev": 50.0},
                ]

        payload = list_brands(db=FakeDB())
        assert payload["default_brand"] == "SIKA"
        assert [brand["value"] for brand in payload["brands"]] == ["SIKA", "PINTUCO"]

    def test_build_smoke_uses_fake_db_and_parameter_counts(self):
        db = _FakeDB()
        builder = BrandReportBuilder(
            "SIKA",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            db=db,
        )
        report = builder.build()
        assert report["status"] == "ok"
        assert builder.period["end"] == date(2026, 11, 17)
        assert builder.period["requested_end"] == date(2026, 12, 31)
        assert db.queries
        for sql, params in db.queries:
            assert sql.count("%s") == len(params), (sql, params)
        assert report["inventory"]["available"] is False

    def test_finish_products_classifies_new_and_dropped(self):
        builder = object.__new__(BrandReportBuilder)
        builder.top_n = 15
        current = [
            {
                "sku": "A",
                "name": "A",
                "rev": 100.0,
                "cost": 80.0,
                "qty": 1.0,
                "missing_master": 0,
            },
        ]
        prior = [
            {
                "sku": "A",
                "name": "A",
                "rev": 80.0,
                "cost": 60.0,
                "qty": 1.0,
                "missing_master": 0,
            },
            {
                "sku": "C",
                "name": "C",
                "rev": 40.0,
                "cost": 30.0,
                "qty": 1.0,
                "missing_master": 0,
            },
        ]
        result = builder._finish_products(current, prior)
        assert result["top"][0]["prior_rev"] == 80.0
        assert result["gains"][0]["sku"] == "A"
        assert result["losses"][0]["sku"] == "C"
        assert result["losses"][0]["current"] == 0.0

    def test_finish_customers_classifies_new_lost_and_recurring(self):
        builder = object.__new__(BrandReportBuilder)
        builder.top_n = 15
        current = [
            {
                "cid": 1,
                "name": "Uno",
                "rev": 100.0,
                "cost": 80.0,
                "qty": 1.0,
                "invoices": 2,
                "skus": 1,
            },
            {
                "cid": 2,
                "name": "Dos",
                "rev": 50.0,
                "cost": 40.0,
                "qty": 1.0,
                "invoices": 1,
                "skus": 1,
            },
        ]
        prior = [
            {
                "cid": 1,
                "name": "Uno",
                "rev": 80.0,
                "cost": 60.0,
                "qty": 1.0,
                "invoices": 2,
                "skus": 1,
            },
            {
                "cid": 3,
                "name": "Tres",
                "rev": 40.0,
                "cost": 30.0,
                "qty": 1.0,
                "invoices": 1,
                "skus": 1,
            },
        ]
        result = builder._finish_customers(current, prior)
        stats = result["stats"]
        assert stats["new"]["customers"] == 1
        assert stats["lost"]["customers"] == 1
        assert stats["recurring"]["customers"] == 1
        assert stats["new"]["rev"] == 50.0
        assert stats["lost"]["rev"] == 40.0

    def test_inventory_query_uses_commercial_warehouses_and_brand_guard(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            brand_report.Config, "DB_NAME_J3SYSTEM", "J3System", raising=False
        )
        cursor = _FakeCursor()
        builder = object.__new__(BrandReportBuilder)
        builder.brand = "SIKA"
        builder.brand_upper = "SIKA"
        builder.year = 2026
        builder.include_inventory = True
        builder.period = {"days": 314}
        builder.db = _FakeJ3DB(cursor)
        result = builder._inventory([], 1000.0)
        assert result["available"] is False
        assert "AdmAlmacen" in cursor.sql
        for code in ("'ALM'", "'SUR'", "'BD6'", "'DIS'", "'FLO'"):
            assert code in cursor.sql
        assert "LIKE %s" in cursor.sql
        assert "NULLIF(LTRIM(RTRIM(a.ArticulosMarca)), '') IS NULL" in cursor.sql
        assert 2026 in cursor.params and 2025 in cursor.params

    def test_unknown_brand_returns_error(self, tmp_path, monkeypatch):
        zero = _minimal_report()
        zero["kpis"]["current"]["lines"] = 0
        zero["kpis"]["prior"]["lines"] = 0

        class FakeBuilder:
            def __init__(self, *args, **kwargs):
                pass

            def build(self):
                return zero

        monkeypatch.setattr(brand_report, "BrandReportBuilder", FakeBuilder)
        result = build_brand_report_result(
            brand="NOEXISTE",
            start_date="2026-01-01",
            end_date="2026-12-31",
            output_dir=tmp_path,
        )
        assert result["status"] == "error"
        assert "Sin ventas" in result["message"]

    def test_leap_year_prior_end_uses_month_end(self):
        period = resolve_brand_period_range(
            date(2025, 2, 1),
            date(2025, 2, 28),
            max_date=date(2026, 11, 17),
        )
        assert period["prior_end"] == date(2024, 2, 29)


class TestBrandReportFlask:
    @pytest.fixture
    def brand_client(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
        success = {
            "status": "success",
            "message": "Informe de marca listo",
            "brand": "SIKA",
            "year": 2026,
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "data_start": "2026-01-01",
            "data_end": "2026-11-17",
            "as_of": "2026-11-17",
            "format": "html",
            "path": str(tmp_path / "INFORME_MARCA_SIKA_2026-01-01_2026-12-31.html"),
        }
        monkeypatch.setattr(
            brand_report, "build_brand_report_result", lambda **kwargs: success
        )
        monkeypatch.setattr(
            brand_report,
            "list_brands",
            lambda **kwargs: {
                "brands": [
                    {"value": "SIKA", "label": "Sika"},
                    {"value": "PINTUCO", "label": "Pintuco"},
                ],
                "default_brand": "SIKA",
                "year": 2026,
                "max_date": "2026-11-10",
            },
        )
        app = SmartVannaFlaskApp(_StubVanna(), chart=False)
        app.flask_app.config["TESTING"] = True
        with app.flask_app.test_client() as client:
            yield client

    def test_generate_brand_report_endpoint(self, brand_client):
        response = brand_client.post(
            "/api/v0/generate_brand_report",
            json={
                "brand": "SIKA",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "format": "html",
            },
        )
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["type"] == "brand_report"
        assert payload["brand"] == "SIKA"
        assert payload["start_date"] == "2026-01-01"
        assert payload["end_date"] == "2026-12-31"
        assert payload["download_url"].endswith(
            "INFORME_MARCA_SIKA_2026-01-01_2026-12-31.html"
        )

    def test_generate_brand_report_requires_brand(self, brand_client):
        response = brand_client.post("/api/v0/generate_brand_report", json={})
        assert response.status_code == 200
        assert response.get_json()["type"] == "error"

    def test_brands_endpoint(self, brand_client):
        response = brand_client.get("/api/v0/brands")
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["default_brand"] == "SIKA"
        assert [brand["value"] for brand in payload["brands"]] == ["SIKA", "PINTUCO"]

    def test_catalog_has_brand_entry(self):
        reports = get_recommended_reports(today=date(2026, 11, 11))
        entry = next(report for report in reports if report["id"] == "brand-report")
        assert entry["period_type"] == "brand"
        assert entry["action"]["type"] == "generate_brand_report"
        assert entry["action"]["start_date"] == "2026-01-01"
        assert entry["action"]["end_date"] == "2026-12-31"
        assert entry["action"]["year"] == 2026
        assert entry["group"] == "Marcas"
