"""Unit tests for the AkzoNobel Core Lines report. Synthetic data only."""

from __future__ import annotations

import csv
import re
import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest

from business_analyzer.jobs import akzonobel_core_lines as acl


def _config(**overrides: object) -> acl.CoreLinesConfig:
    base = {
        "placeholder": True,
        "territory": acl.TerritoryMapping(
            key_field="vendedor_codigo",
            label_field="VendedorFactura",
        ),
        "skus": (
            acl.CoreSku(sku="AKZO-DEMO-001", name="Pintura demo línea núcleo 1"),
            acl.CoreSku(sku="AKZO-DEMO-002", name="Pintura demo línea núcleo 2"),
            acl.CoreSku(sku="AKZO-DEMO-003", name="Pintura demo línea núcleo 3"),
        ),
    }
    base.update(overrides)
    return acl.CoreLinesConfig(**base)  # type: ignore[arg-type]


def _sales_rows() -> list[dict]:
    return [
        {
            "territory_key": "01",
            "territory_label": "Ana Demo",
            "sku": "AKZO-DEMO-001",
            "product_name": "Pintura demo línea núcleo 1",
            "revenue": 800_000,
            "quantity": 8,
            "proveedor": "AKZO-DEMO-VENDOR",
            "marca": "AKZO-DEMO-MARCA",
        },
        {
            "territory_key": "01",
            "territory_label": "Ana Demo",
            "sku": "SKU-OTRO-001",
            "product_name": "Cemento demo",
            "revenue": 4_200_000,
            "quantity": 40,
            "proveedor": "OTRO-DEMO",
            "marca": "OTRO",
        },
        {
            "territory_key": "02",
            "territory_label": "Luis Demo",
            "sku": "SKU-OTRO-002",
            "product_name": "Broca demo",
            "revenue": 1_200_000,
            "quantity": 12,
            "proveedor": "OTRO-DEMO",
            "marca": "OTRO",
        },
    ]


def _live_yaml(path: Path, placeholder: bool = False) -> Path:
    flag = "true" if placeholder else "false"
    path.write_text(
        "\n".join(
            [
                f"placeholder: {flag}",
                "territory:",
                "  key_field: vendedor_codigo",
                "  label_field: VendedorFactura",
                "skus:",
                "  - sku: AKZO-DEMO-001",
                "    name: Pintura demo línea núcleo 1",
                "  - sku: AKZO-DEMO-002",
                "    name: Pintura demo línea núcleo 2",
                "  - sku: AKZO-DEMO-003",
                "    name: Pintura demo línea núcleo 3",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _mssql_to_sqlite(sql: str) -> str:
    sql = re.sub(r"\[([^\]]+)\]\.\[dbo\]\.\[([^\]]+)\]", r"\2", sql)
    sql = sql.replace(" COLLATE DATABASE_DEFAULT", "")
    sql = re.sub(r"\bLEN\(", "LENGTH(", sql)
    return sql.replace("%s", "?")


def _sqlite_sales_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE banco_datos (
            Fecha TEXT,
            TotalSinIva REAL,
            Cantidad REAL,
            ArticulosCodigo TEXT,
            ArticulosNombre TEXT,
            DocumentosCodigo TEXT,
            vendedor_codigo TEXT,
            VendedorFactura TEXT,
            ciudad TEXT,
            departamento TEXT,
            proveedor TEXT,
            marca TEXT
        );
        CREATE TABLE productos_adicional (
            producto_codigo TEXT,
            proveedor_descripcion TEXT,
            producto_marca TEXT
        );
        """
    )


def _insert_sale(conn: sqlite3.Connection, **row: object) -> None:
    defaults = {
        "Fecha": "2026-08-15",
        "TotalSinIva": 1000,
        "Cantidad": 1,
        "ArticulosCodigo": "SKU-OTRO-001",
        "ArticulosNombre": "Cemento demo",
        "DocumentosCodigo": "FED",
        "vendedor_codigo": "01",
        "VendedorFactura": "Ana Demo",
        "ciudad": "Neiva Demo",
        "departamento": "Huila Demo",
        "proveedor": "OTRO-DEMO",
        "marca": "OTRO",
    }
    defaults.update(row)
    conn.execute(
        """
        INSERT INTO banco_datos (
            Fecha, TotalSinIva, Cantidad, ArticulosCodigo, ArticulosNombre,
            DocumentosCodigo, vendedor_codigo, VendedorFactura, ciudad,
            departamento, proveedor, marca
        ) VALUES (
            :Fecha, :TotalSinIva, :Cantidad, :ArticulosCodigo, :ArticulosNombre,
            :DocumentosCodigo, :vendedor_codigo, :VendedorFactura, :ciudad,
            :departamento, :proveedor, :marca
        )
        """,
        defaults,
    )


def _sale(**overrides: object) -> dict:
    row = {
        "territory_key": "01",
        "territory_label": "Ana Demo",
        "sku": "SKU-OTRO-001",
        "product_name": "Cemento demo",
        "revenue": 1_000,
        "quantity": 1,
        "proveedor": "OTRO-DEMO",
        "marca": "OTRO",
    }
    row.update(overrides)
    return row


def _query_sqlite_sales(conn: sqlite3.Connection) -> list[dict]:
    conn.row_factory = sqlite3.Row
    mapping = acl.TerritoryMapping(
        key_field="vendedor_codigo",
        label_field="VendedorFactura",
    )
    sql, params = acl.build_territory_sku_sql(
        mapping, start_date="2026-08-01", end_date="2026-08-31"
    )
    return [dict(row) for row in conn.execute(_mssql_to_sqlite(sql), params).fetchall()]


def _run_sqlite_report(conn: sqlite3.Connection) -> list[acl.GapRow]:
    return acl.find_zero_penetration(_query_sqlite_sales(conn), _config())


@pytest.mark.unit
def test_last_complete_month_from_mid_month():
    start, end = acl.last_complete_month(date(2026, 9, 30))
    assert start == date(2026, 8, 1)
    assert end == date(2026, 8, 31)


@pytest.mark.unit
def test_last_complete_month_from_january():
    start, end = acl.last_complete_month(date(2026, 1, 5))
    assert start == date(2025, 12, 1)
    assert end == date(2025, 12, 31)


@pytest.mark.unit
def test_shipped_yaml_is_labelled_synthetic_placeholder():
    path = acl.packaged_config_path()
    assert path.is_file()
    cfg = acl.load_core_lines_config(path)
    assert cfg.placeholder is True
    assert cfg.territory.key_field == "vendedor_codigo"
    assert cfg.territory.label_field == "VendedorFactura"
    skus = [item.sku for item in cfg.skus]
    assert skus == ["AKZO-DEMO-001", "AKZO-DEMO-002", "AKZO-DEMO-003"]
    text = path.read_text(encoding="utf-8")
    assert "SYNTHETIC PLACEHOLDER" in text
    assert "placeholder: true" in text
    assert "vendor_match" not in text
    assert "Pintuco" not in text
    assert "Coral" not in text


@pytest.mark.unit
def test_load_json_and_csv_configs(tmp_path: Path):
    json_path = tmp_path / "core.json"
    json_path.write_text(
        """
        {
          "placeholder": true,
          "territory": {"key_field": "ciudad", "label_field": "ciudad"},
          "skus": [{"sku": "AKZO-DEMO-009", "name": "SKU demo ciudad"}]
        }
        """,
        encoding="utf-8",
    )
    cfg = acl.load_core_lines_config(json_path)
    assert cfg.territory.key_field == "ciudad"
    assert cfg.skus[0].sku == "AKZO-DEMO-009"

    csv_path = tmp_path / "skus.csv"
    csv_path.write_text(
        "sku,name\nAKZO-DEMO-010,Pintura demo csv\n",
        encoding="utf-8",
    )
    csv_cfg = acl.load_core_lines_config(csv_path)
    assert csv_cfg.territory.key_field == "vendedor_codigo"
    assert csv_cfg.skus[0].sku == "AKZO-DEMO-010"
    assert csv_cfg.placeholder is True


@pytest.mark.unit
def test_reject_unknown_territory_field():
    with pytest.raises(ValueError, match="territorio"):
        acl.TerritoryMapping(key_field="zona_inventada", label_field="ciudad")


@pytest.mark.unit
def test_zero_penetration_ranks_by_territory_potential():
    gaps = acl.find_zero_penetration(_sales_rows(), _config())
    assert [row.territory_key for row in gaps] == ["01", "01", "02", "02", "02"]
    assert [row.sku for row in gaps if row.territory_key == "01"] == [
        "AKZO-DEMO-002",
        "AKZO-DEMO-003",
    ]
    assert {row.sku for row in gaps if row.territory_key == "02"} == {
        "AKZO-DEMO-001",
        "AKZO-DEMO-002",
        "AKZO-DEMO-003",
    }
    assert gaps[0].territory_revenue == 5_000_000
    assert gaps[0].territory_rank == 1
    assert gaps[-1].territory_rank == 2
    sold_elsewhere = next(
        row for row in gaps if row.territory_key == "02" and row.sku == "AKZO-DEMO-001"
    )
    assert sold_elsewhere.company_sku_revenue == 800_000


@pytest.mark.unit
def test_zero_penetration_skips_idle_and_complete_territories():
    rows = _sales_rows() + [
        {
            "territory_key": "",
            "territory_label": "Sin código",
            "sku": "SKU-OTRO-003",
            "product_name": "Ignorado",
            "revenue": 9_000_000,
            "quantity": 1,
            "proveedor": "OTRO-DEMO",
            "marca": "OTRO",
        },
        {
            "territory_key": "03",
            "territory_label": "Carla Demo",
            "sku": "AKZO-DEMO-001",
            "product_name": "Pintura demo línea núcleo 1",
            "revenue": 10_000,
            "quantity": 1,
            "proveedor": "AKZO-DEMO-VENDOR",
            "marca": "AKZO-DEMO-MARCA",
        },
        {
            "territory_key": "03",
            "territory_label": "Carla Demo",
            "sku": "AKZO-DEMO-002",
            "product_name": "Pintura demo línea núcleo 2",
            "revenue": 10_000,
            "quantity": 1,
            "proveedor": "AKZO-DEMO-VENDOR",
            "marca": "AKZO-DEMO-MARCA",
        },
        {
            "territory_key": "03",
            "territory_label": "Carla Demo",
            "sku": "AKZO-DEMO-003",
            "product_name": "Pintura demo línea núcleo 3",
            "revenue": 10_000,
            "quantity": 1,
            "proveedor": "AKZO-DEMO-VENDOR",
            "marca": "AKZO-DEMO-MARCA",
        },
    ]
    gaps = acl.find_zero_penetration(rows, _config())
    assert all(row.territory_key in {"01", "02"} for row in gaps)
    assert "03" not in {row.territory_key for row in gaps}


@pytest.mark.unit
def test_empty_sales_yield_no_gaps():
    assert acl.find_zero_penetration([], _config()) == []


@pytest.mark.unit
def test_format_number_colombian_currency_and_percent():
    assert acl.format_number(5_000_000, "TotalSinIva") == "$5.000.000"
    assert acl.format_number(45.6, "Margen") == "45,6%"


@pytest.mark.unit
def test_html_spanish_placeholder_and_exclusions():
    report = acl.build_report(
        sales_rows=_sales_rows(),
        config=_config(),
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 31),
    )
    html = acl.render_html(report)
    assert "Líneas núcleo" in html
    assert "sin penetración" in html.lower()
    assert "Ana Demo" in html
    assert "AKZO-DEMO-002" in html
    assert "$5.000.000" in html
    assert "marcador sintético" in html.lower() or "placeholder" in html.lower()
    assert "vendedor_codigo" in html
    assert "XY" in html and "ISC" in html
    assert "solo lectura" in html.lower()
    assert "<script" not in html
    assert 'lang="es-CO"' in html


@pytest.mark.unit
def test_html_escapes_special_characters_across_all_fields():
    cfg = _config(
        skus=(
            acl.CoreSku(
                sku="AKZO<&\">'",
                name='Pintura <demo> & "y" \'',
            ),
        )
    )
    rows = [
        _sale(
            territory_key="99&<>\"'",
            territory_label='<Vendedor Script> & "x" \'',
            sku="SKU-OTRO-X",
            product_name='Otro <demo> & "z"',
            revenue=1000,
            quantity=2,
        )
    ]
    report = acl.build_report(
        sales_rows=rows,
        config=cfg,
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 31),
    )
    html = acl.render_html(report)
    raw_values = (
        "<Vendedor Script>",
        "AKZO<&\">'",
        "Pintura <demo>",
        "99&<>\"'",
        'Otro <demo> & "z"',
        "<script>",
    )
    for raw in raw_values:
        assert raw not in html
    assert "&lt;Vendedor Script&gt;" in html
    assert "&amp;" in html
    assert "&quot;" in html
    assert "&#x27;" in html
    assert "&lt;demo&gt;" in html
    assert report.gaps
    gap = report.gaps[0]
    assert acl._html(gap.territory_key) in html
    assert acl._html(gap.territory_label) in html
    assert acl._html(gap.sku) in html
    assert acl._html(gap.sku_name) in html
    assert acl._html(gap.territory_rank) in html
    assert acl._html(acl.format_number(gap.territory_revenue, "TotalSinIva")) in html
    assert acl._html(acl.format_number(gap.company_sku_revenue, "TotalSinIva")) in html


@pytest.mark.unit
def test_csv_spanish_headers_and_rows():
    report = acl.build_report(
        sales_rows=_sales_rows(),
        config=_config(),
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 31),
    )
    text = acl.render_csv(report)
    assert "Territorio" in text
    assert "VentasTerritorio" in text
    assert "AKZO-DEMO-002" in text
    reader = csv.DictReader(text.splitlines())
    rows = list(reader)
    assert rows
    assert rows[0]["CodigoTerritorio"] == "01"


@pytest.mark.unit
def test_write_report_html_and_csv(tmp_path: Path):
    report = acl.build_synthetic_report(
        run_date=date(2026, 9, 30),
        config=_config(),
    )
    result = acl.write_report(report, tmp_path)
    assert result.html_path.is_file()
    assert result.csv_path.is_file()
    assert result.html_path.name.startswith("akzonobel_core_lines_")
    assert "Ana Demo" in result.html_path.read_text(encoding="utf-8")
    assert "Luis Demo" in result.csv_path.read_text(encoding="utf-8")


@pytest.mark.unit
def test_sql_is_readonly_and_excludes_test_docs():
    mapping = acl.TerritoryMapping(
        key_field="vendedor_codigo",
        label_field="VendedorFactura",
    )
    sql, params = acl.build_territory_sku_sql(
        mapping,
        start_date="2026-08-01",
        end_date="2026-08-31",
    )
    lowered = sql.lower()
    assert sql.lstrip().upper().startswith("SELECT")
    for banned in ("insert ", "update ", "delete ", "merge ", "drop ", "alter "):
        assert banned not in lowered
    assert "documentoscodigo not in" in lowered
    for code in ("XY", "AS", "TS", "YX", "ISC"):
        assert code in params
    assert "vendedor_codigo" in sql
    assert "VendedorFactura" in sql
    assert "productos_adicional" not in lowered
    assert "totalsiniva" in lowered
    assert "between %s and %s" in lowered
    assert "cantidad > 0" in lowered
    assert "totalsiniva > 0" in lowered
    assert "articulosnombre" in lowered
    assert params[0] == "2026-08-01"
    assert params[1] == "2026-08-31"
    assert "SERVICIO DE CORTE" in params
    assert "BOLSA BIODEGRADABLE PARA ENTREGA" in params
    assert "ALLOW_WRITE" not in sql


@pytest.mark.unit
def test_sql_ciudad_dimension_uses_documented_field():
    mapping = acl.TerritoryMapping(key_field="ciudad", label_field="ciudad")
    sql, _params = acl.build_territory_sku_sql(
        mapping,
        start_date="2026-08-01",
        end_date="2026-08-31",
    )
    assert "bd.ciudad" in sql
    assert "zona_unica" not in sql.lower()


@pytest.mark.unit
def test_parse_args_defaults_and_flags():
    args = acl.parse_args([])
    assert args.synthetic is False
    args = acl.parse_args(
        [
            "--synthetic",
            "--start-date",
            "2026-08-01",
            "--end-date",
            "2026-08-31",
            "--dimension",
            "ciudad",
        ]
    )
    assert args.synthetic is True
    assert args.start_date == "2026-08-01"
    assert args.dimension == "ciudad"


@pytest.mark.unit
def test_main_synthetic_writes_outputs(tmp_path: Path):
    code = acl.main(
        [
            "--synthetic",
            "--output-dir",
            str(tmp_path),
            "--run-date",
            "2026-09-30",
        ]
    )
    assert code == 0
    assert list(tmp_path.glob("*.html"))
    assert list(tmp_path.glob("*.csv"))
    html = next(tmp_path.glob("*.html")).read_text(encoding="utf-8")
    assert "Ana Demo" in html
    assert "AKZO-DEMO-002" in html


@pytest.mark.unit
def test_main_accepts_config_and_dates(tmp_path: Path):
    cfg = tmp_path / "custom.yaml"
    cfg.write_text(
        "\n".join(
            [
                "placeholder: true",
                "territory:",
                "  key_field: vendedor_codigo",
                "  label_field: VendedorFactura",
                "skus:",
                "  - sku: AKZO-DEMO-001",
                "    name: Pintura demo línea núcleo 1",
                "  - sku: AKZO-DEMO-002",
                "    name: Pintura demo línea núcleo 2",
            ]
        ),
        encoding="utf-8",
    )
    code = acl.main(
        [
            "--synthetic",
            "--config",
            str(cfg),
            "--output-dir",
            str(tmp_path),
            "--start-date",
            "2026-08-01",
            "--end-date",
            "2026-08-31",
        ]
    )
    assert code == 0
    html = next(tmp_path.glob("*.html")).read_text(encoding="utf-8")
    assert "2026-08-01" in html
    assert "AKZO-DEMO-003" not in html


@pytest.mark.unit
def test_build_live_report_uses_injected_loader():
    report = acl.build_live_report(
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 31),
        config=_config(),
        sales_loader=lambda _start, _end, _mapping: _sales_rows(),
    )
    assert report.gaps
    assert report.gaps[0].territory_label == "Ana Demo"


@pytest.mark.unit
def test_fetch_territory_sku_sales_uses_database(monkeypatch):
    captured: dict[str, object] = {}

    class _FakeDB:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute_query(self, query, params=None):
            captured["query"] = query
            captured["params"] = params
            return _sales_rows()

    monkeypatch.setattr(acl, "_open_database", lambda: _FakeDB())
    mapping = acl.TerritoryMapping(
        key_field="vendedor_codigo",
        label_field="VendedorFactura",
    )
    rows = acl.fetch_territory_sku_sales("2026-08-01", "2026-08-31", mapping)
    assert rows == _sales_rows()
    assert "DocumentosCodigo NOT IN" in str(captured["query"])
    assert captured["params"][0] == "2026-08-01"


@pytest.mark.unit
def test_main_live_uses_loader_patch(tmp_path: Path):
    cfg = _live_yaml(tmp_path / "live.yaml", placeholder=False)
    with patch.object(acl, "fetch_territory_sku_sales", return_value=_sales_rows()):
        code = acl.main(
            [
                "--config",
                str(cfg),
                "--output-dir",
                str(tmp_path),
                "--start-date",
                "2026-08-01",
                "--end-date",
                "2026-08-31",
            ]
        )
    assert code == 0
    assert list(tmp_path.glob("*.html"))


@pytest.mark.unit
def test_main_missing_config_returns_error(tmp_path: Path, capsys):
    missing = tmp_path / "nope.yaml"
    code = acl.main(
        [
            "--synthetic",
            "--config",
            str(missing),
            "--output-dir",
            str(tmp_path),
        ]
    )
    assert code == 1
    assert "config" in capsys.readouterr().err.lower()


@pytest.mark.unit
def test_settings_config_path_override(tmp_path: Path, monkeypatch):
    custom = tmp_path / "from-settings.yaml"
    custom.write_text(
        "placeholder: true\n"
        "territory:\n"
        "  key_field: ciudad\n"
        "  label_field: ciudad\n"
        "skus:\n"
        "  - sku: AKZO-DEMO-011\n"
        "    name: Demo settings\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AKZONOBEL_CORE_LINES_CONFIG", str(custom))
    from business_analyzer.core.config import Settings

    settings = Settings()
    assert settings.AKZONOBEL_CORE_LINES_CONFIG == str(custom)
    path = acl.resolve_config_path(settings=settings)
    assert path == custom
    cfg = acl.load_core_lines_config(path)
    assert cfg.territory.key_field == "ciudad"


@pytest.mark.unit
def test_default_output_dir_uses_config(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        acl.Config,
        "ensure_output_dir",
        classmethod(lambda cls: tmp_path),
    )
    args = acl.parse_args(["--synthetic", "--run-date", "2026-09-30"])
    with patch.object(acl, "parse_args", return_value=args):
        code = acl.main(["--synthetic", "--run-date", "2026-09-30"])
    assert code == 0
    assert list((tmp_path / "akzonobel_core_lines").glob("*.html"))


@pytest.mark.unit
def test_load_config_rejects_empty_skus(tmp_path: Path):
    path = tmp_path / "empty.json"
    path.write_text(
        '{"placeholder": true, "skus": [], "territory": '
        '{"key_field": "ciudad", "label_field": "ciudad"}}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="SKU"):
        acl.load_core_lines_config(path)


@pytest.mark.unit
def test_empty_gaps_html_message():
    rows = [
        {
            "territory_key": "01",
            "territory_label": "Ana Demo",
            "sku": "AKZO-DEMO-001",
            "product_name": "Pintura demo línea núcleo 1",
            "revenue": 10,
            "quantity": 1,
            "proveedor": "AKZO-DEMO-VENDOR",
            "marca": "AKZO-DEMO-MARCA",
        },
        {
            "territory_key": "01",
            "territory_label": "Ana Demo",
            "sku": "AKZO-DEMO-002",
            "product_name": "Pintura demo línea núcleo 2",
            "revenue": 10,
            "quantity": 1,
            "proveedor": "AKZO-DEMO-VENDOR",
            "marca": "AKZO-DEMO-MARCA",
        },
        {
            "territory_key": "01",
            "territory_label": "Ana Demo",
            "sku": "AKZO-DEMO-003",
            "product_name": "Pintura demo línea núcleo 3",
            "revenue": 10,
            "quantity": 1,
            "proveedor": "AKZO-DEMO-VENDOR",
            "marca": "AKZO-DEMO-MARCA",
        },
    ]
    report = acl.build_report(
        sales_rows=rows,
        config=_config(),
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 31),
    )
    html = acl.render_html(report)
    assert "Sin SKUs de líneas núcleo sin penetración" in html


@pytest.mark.unit
def test_json_string_skus(tmp_path: Path):
    path = tmp_path / "core.json"
    path.write_text(
        '{"placeholder": true, "skus": ["AKZO-DEMO-020"]}',
        encoding="utf-8",
    )
    cfg = acl.load_core_lines_config(path)
    assert cfg.skus[0].sku == "AKZO-DEMO-020"


@pytest.mark.unit
def test_yaml_must_be_mapping(tmp_path: Path):
    path = tmp_path / "list.yaml"
    path.write_text("- just-a-list\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapeo"):
        acl.load_core_lines_config(path)


@pytest.mark.unit
def test_apply_dimension_rejects_unknown():
    with pytest.raises(ValueError, match="Dimensión"):
        acl.apply_dimension(_config(), "zona_unica")


@pytest.mark.unit
def test_assert_readonly_sql_rejects_writes():
    with pytest.raises(ValueError, match="lectura"):
        acl._assert_readonly_sql("DELETE FROM banco_datos")
    with pytest.raises(ValueError, match="SELECT"):
        acl._assert_readonly_sql("WITH x AS (SELECT 1) SELECT 1")


@pytest.mark.unit
def test_sql_falls_back_to_canonical_exclusions(monkeypatch):
    monkeypatch.setattr(acl.Config, "EXCLUDED_DOCUMENT_CODES", ["XY"])
    mapping = acl.TerritoryMapping(
        key_field="vendedor_codigo",
        label_field="VendedorFactura",
    )
    _sql, params = acl.build_territory_sku_sql(
        mapping,
        start_date="2026-08-01",
        end_date="2026-08-31",
    )
    assert params[2:7] == ("XY", "AS", "TS", "YX", "ISC")
    assert "SERVICIO DE CORTE" in params


@pytest.mark.unit
def test_dimension_cli_overrides_mapping(tmp_path: Path):
    rows = [
        {
            "territory_key": "Neiva Demo",
            "territory_label": "Neiva Demo",
            "sku": "SKU-OTRO-001",
            "product_name": "Cemento demo",
            "revenue": 2_000_000,
            "quantity": 5,
            "proveedor": "OTRO-DEMO",
            "marca": "OTRO",
        }
    ]
    with patch.object(acl, "synthetic_sales_rows", return_value=rows):
        code = acl.main(
            [
                "--synthetic",
                "--dimension",
                "ciudad",
                "--output-dir",
                str(tmp_path),
                "--run-date",
                "2026-09-30",
            ]
        )
    assert code == 0
    html = next(tmp_path.glob("*.html")).read_text(encoding="utf-8")
    assert "ciudad" in html
    assert "Neiva Demo" in html


@pytest.mark.unit
def test_core_only_territory_is_not_ranked():
    rows = [
        _sale(
            territory_key="10",
            territory_label="Solo Núcleo",
            sku="AKZO-DEMO-001",
            product_name="Pintura demo línea núcleo 1",
            revenue=900_000,
            quantity=9,
            proveedor="AKZO-DEMO-VENDOR",
            marca="AKZO-DEMO-MARCA",
        ),
        _sale(
            territory_key="01",
            territory_label="Ana Demo",
            sku="SKU-OTRO-001",
            product_name="Cemento demo",
            revenue=2_000_000,
            quantity=4,
        ),
    ]
    gaps = acl.find_zero_penetration(rows, _config())
    keys = {row.territory_key for row in gaps}
    assert "10" not in keys
    assert "01" in keys
    assert {row.sku for row in gaps if row.territory_key == "01"} == {
        "AKZO-DEMO-001",
        "AKZO-DEMO-002",
        "AKZO-DEMO-003",
    }


@pytest.mark.unit
def test_credit_notes_and_zero_totals_do_not_count_as_sold():
    rows = [
        _sale(sku="SKU-OTRO-001", revenue=2_000_000, quantity=4),
        _sale(
            sku="AKZO-DEMO-001",
            product_name="Pintura demo línea núcleo 1",
            revenue=-400_000,
            quantity=-2,
            proveedor="AKZO-DEMO-VENDOR",
            marca="AKZO-DEMO-MARCA",
        ),
        _sale(
            sku="AKZO-DEMO-002",
            product_name="Pintura demo línea núcleo 2",
            revenue=0,
            quantity=3,
            proveedor="AKZO-DEMO-VENDOR",
            marca="AKZO-DEMO-MARCA",
        ),
        _sale(
            sku="AKZO-DEMO-003",
            product_name="Pintura demo línea núcleo 3",
            revenue=80_000,
            quantity=0,
            proveedor="AKZO-DEMO-VENDOR",
            marca="AKZO-DEMO-MARCA",
        ),
    ]
    gaps = acl.find_zero_penetration(rows, _config())
    assert {row.sku for row in gaps if row.territory_key == "01"} == {
        "AKZO-DEMO-001",
        "AKZO-DEMO-002",
        "AKZO-DEMO-003",
    }


@pytest.mark.unit
def test_excluded_product_names_do_not_make_territory_active():
    rows = [
        _sale(
            territory_key="20",
            territory_label="Solo Corte",
            sku="SKU-SERV-001",
            product_name="SERVICIO DE CORTE",
            revenue=50_000,
            quantity=1,
        ),
        _sale(
            territory_key="21",
            territory_label="Bolsa y núcleo",
            sku="SKU-BOLSA-001",
            product_name="BOLSA BIODEGRADABLE PARA ENTREGA",
            revenue=1_200,
            quantity=10,
        ),
        _sale(
            territory_key="21",
            territory_label="Bolsa y núcleo",
            sku="AKZO-DEMO-001",
            product_name="Pintura demo línea núcleo 1",
            revenue=80_000,
            quantity=1,
            proveedor="AKZO-DEMO-VENDOR",
            marca="AKZO-DEMO-MARCA",
        ),
        _sale(
            territory_key="01",
            territory_label="Ana Demo",
            sku="SKU-OTRO-001",
            product_name="Cemento demo",
            revenue=1_500_000,
            quantity=3,
        ),
        _sale(
            territory_key="01",
            territory_label="Ana Demo",
            sku="SKU-BOLSA-002",
            product_name="BOLSA BIODEGRADABLE PARA ENTREGA",
            revenue=800,
            quantity=8,
        ),
    ]
    gaps = acl.find_zero_penetration(rows, _config())
    keys = {row.territory_key for row in gaps}
    assert "20" not in keys
    assert "21" not in keys
    assert "01" in keys


@pytest.mark.unit
def test_sqlite_sql_core_only_territory_is_not_ranked():
    conn = sqlite3.connect(":memory:")
    _sqlite_sales_schema(conn)
    _insert_sale(
        conn,
        vendedor_codigo="01",
        VendedorFactura="Ana Demo",
        ArticulosCodigo="SKU-OTRO-001",
        ArticulosNombre="Cemento demo",
        Cantidad=4,
        TotalSinIva=2_000_000,
    )
    _insert_sale(
        conn,
        vendedor_codigo="10",
        VendedorFactura="Solo Nucleo",
        ArticulosCodigo="AKZO-DEMO-001",
        ArticulosNombre="Pintura demo línea núcleo 1",
        Cantidad=9,
        TotalSinIva=900_000,
    )
    queried = _query_sqlite_sales(conn)
    assert {row["territory_key"] for row in queried} == {"01", "10"}
    gaps = acl.find_zero_penetration(queried, _config())
    keys = {row.territory_key for row in gaps}
    assert "10" not in keys
    assert "01" in keys


@pytest.mark.unit
def test_sqlite_sql_credit_and_zero_total_are_not_sold():
    conn = sqlite3.connect(":memory:")
    _sqlite_sales_schema(conn)
    _insert_sale(
        conn,
        ArticulosCodigo="SKU-OTRO-001",
        ArticulosNombre="Cemento demo",
        Cantidad=4,
        TotalSinIva=2_000_000,
    )
    _insert_sale(
        conn,
        ArticulosCodigo="AKZO-DEMO-001",
        ArticulosNombre="Pintura demo línea núcleo 1",
        Cantidad=-2,
        TotalSinIva=-400_000,
    )
    _insert_sale(
        conn,
        ArticulosCodigo="AKZO-DEMO-002",
        ArticulosNombre="Pintura demo línea núcleo 2",
        Cantidad=3,
        TotalSinIva=0,
    )
    _insert_sale(
        conn,
        ArticulosCodigo="AKZO-DEMO-003",
        ArticulosNombre="Pintura demo línea núcleo 3",
        Cantidad=0,
        TotalSinIva=80_000,
    )
    queried = _query_sqlite_sales(conn)
    assert {row["sku"] for row in queried} == {"SKU-OTRO-001"}
    gaps = acl.find_zero_penetration(queried, _config())
    assert {row.sku for row in gaps if row.territory_key == "01"} == {
        "AKZO-DEMO-001",
        "AKZO-DEMO-002",
        "AKZO-DEMO-003",
    }


@pytest.mark.unit
def test_sqlite_sql_excluded_product_names_are_not_active():
    conn = sqlite3.connect(":memory:")
    _sqlite_sales_schema(conn)
    _insert_sale(
        conn,
        vendedor_codigo="20",
        VendedorFactura="Solo Corte",
        ArticulosCodigo="SKU-SERV-001",
        ArticulosNombre="SERVICIO DE CORTE",
        Cantidad=1,
        TotalSinIva=50_000,
    )
    _insert_sale(
        conn,
        vendedor_codigo="21",
        VendedorFactura="Bolsa y nucleo",
        ArticulosCodigo="SKU-BOLSA-001",
        ArticulosNombre="BOLSA BIODEGRADABLE PARA ENTREGA",
        Cantidad=10,
        TotalSinIva=1_200,
    )
    _insert_sale(
        conn,
        vendedor_codigo="21",
        VendedorFactura="Bolsa y nucleo",
        ArticulosCodigo="AKZO-DEMO-001",
        ArticulosNombre="Pintura demo línea núcleo 1",
        Cantidad=1,
        TotalSinIva=80_000,
    )
    _insert_sale(
        conn,
        vendedor_codigo="01",
        VendedorFactura="Ana Demo",
        ArticulosCodigo="SKU-OTRO-001",
        ArticulosNombre="Cemento demo",
        Cantidad=3,
        TotalSinIva=1_500_000,
    )
    queried = _query_sqlite_sales(conn)
    assert {row["territory_key"] for row in queried} == {"01", "21"}
    assert all(
        str(row["product_name"]).upper()
        not in {"SERVICIO DE CORTE", "BOLSA BIODEGRADABLE PARA ENTREGA"}
        for row in queried
    )
    gaps = acl.find_zero_penetration(queried, _config())
    keys = {row.territory_key for row in gaps}
    assert "20" not in keys
    assert "21" not in keys
    assert "01" in keys


@pytest.mark.unit
def test_yaml_ignores_legacy_vendor_match(tmp_path: Path):
    path = tmp_path / "legacy.yaml"
    path.write_text(
        "\n".join(
            [
                "placeholder: true",
                "vendor_match:",
                "  proveedor_contains:",
                "    - AKZO-DEMO-VENDOR",
                "  marca_contains:",
                "    - AKZO-DEMO-MARCA",
                "skus:",
                "  - sku: AKZO-DEMO-001",
                "    name: Pintura demo línea núcleo 1",
            ]
        ),
        encoding="utf-8",
    )
    cfg = acl.load_core_lines_config(path)
    assert not hasattr(cfg, "vendor_match")
    assert cfg.skus[0].sku == "AKZO-DEMO-001"
    assert not hasattr(acl, "matches_vendor_tokens")


@pytest.mark.unit
def test_main_refuses_placeholder_live_run(tmp_path: Path, capsys):
    cfg = _live_yaml(tmp_path / "placeholder.yaml", placeholder=True)
    code = acl.main(
        [
            "--config",
            str(cfg),
            "--output-dir",
            str(tmp_path),
            "--run-date",
            "2026-09-30",
        ]
    )
    assert code == 1
    err = capsys.readouterr().err
    assert "marcador sintético" in err.lower()
    assert "placeholder" in err.lower()
    assert "base de datos" in err.lower()
    assert not list(tmp_path.glob("*.html"))


@pytest.mark.unit
def test_build_live_report_refuses_placeholder_without_loader():
    with pytest.raises(ValueError, match="placeholder"):
        acl.build_live_report(
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31),
            config=_config(placeholder=True),
        )


@pytest.mark.unit
def test_csv_guard_cell_prefixes_formula_injection():
    assert acl.csv_guard_cell("=1+1") == "'=1+1"
    assert acl.csv_guard_cell("+CMD") == "'+CMD"
    assert acl.csv_guard_cell("-2+2") == "'-2+2"
    assert acl.csv_guard_cell("@SUM(A1)") == "'@SUM(A1)"
    assert acl.csv_guard_cell("\t=1+1") == "'\t=1+1"
    assert acl.csv_guard_cell("\r=1+1") == "'\r=1+1"
    assert acl.csv_guard_cell("Ana Demo") == "Ana Demo"
    assert acl.csv_guard_cell(12) == "12"
    assert acl.csv_guard_cell(None) == ""


@pytest.mark.unit
def test_render_csv_guards_formula_cells():
    cfg = _config(skus=(acl.CoreSku(sku="=HYPERLINK(A1)", name="+cmd|cmd"),))
    rows = [
        _sale(
            territory_key="@01",
            territory_label="-Luis Demo",
            sku="SKU-OTRO-001",
            revenue=1_000,
            quantity=1,
        )
    ]
    report = acl.build_report(
        sales_rows=rows,
        config=cfg,
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 31),
    )
    text = acl.render_csv(report)
    reader = csv.DictReader(text.splitlines())
    exported = list(reader)
    assert exported
    assert exported[0]["SKU"].startswith("'=")
    assert exported[0]["Producto"].startswith("'+")
    assert exported[0]["CodigoTerritorio"].startswith("'@")
    assert exported[0]["Territorio"].startswith("'-")


@pytest.mark.unit
def test_main_invalid_run_date_is_spanish(tmp_path: Path, capsys):
    code = acl.main(
        [
            "--synthetic",
            "--output-dir",
            str(tmp_path),
            "--run-date",
            "31/09/2026",
        ]
    )
    assert code == 1
    err = capsys.readouterr().err
    assert "Fecha no válida" in err
    assert "--run-date" in err
    assert "AAAA-MM-DD" in err


@pytest.mark.unit
def test_argparse_help_is_spanish(capsys):
    with pytest.raises(SystemExit) as exc:
        acl.parse_args(["--help"])
    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    assert "Informe de líneas núcleo" in help_text
    assert "Prueba con datos sintéticos" in help_text
    assert "Fecha de referencia" in help_text
    assert "base de datos" in help_text.lower()


@pytest.mark.unit
def test_fetch_database_error_is_spanish(monkeypatch):
    class _Boom:
        def __enter__(self):
            raise ConnectionError("timeout")

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(acl, "_open_database", lambda: _Boom())
    mapping = acl.TerritoryMapping(
        key_field="vendedor_codigo",
        label_field="VendedorFactura",
    )
    with pytest.raises(RuntimeError, match="base de datos"):
        acl.fetch_territory_sku_sales("2026-08-01", "2026-08-31", mapping)


@pytest.mark.unit
def test_main_live_database_error_is_spanish(tmp_path: Path, capsys):
    cfg = _live_yaml(tmp_path / "live.yaml", placeholder=False)
    with patch.object(
        acl,
        "fetch_territory_sku_sales",
        side_effect=RuntimeError(
            "No se pudo leer la base de datos (consulta de solo lectura). "
            "Detalle: timeout"
        ),
    ):
        code = acl.main(
            [
                "--config",
                str(cfg),
                "--output-dir",
                str(tmp_path),
                "--start-date",
                "2026-08-01",
                "--end-date",
                "2026-08-31",
            ]
        )
    assert code == 1
    err = capsys.readouterr().err
    assert "No se pudo leer la base de datos" in err


@pytest.mark.unit
def test_live_sql_has_no_unused_vendor_join():
    mapping = acl.TerritoryMapping(
        key_field="vendedor_codigo",
        label_field="VendedorFactura",
    )
    sql, _params = acl.build_territory_sku_sql(
        mapping,
        start_date="2026-08-01",
        end_date="2026-08-31",
    )
    lowered = sql.lower()
    assert "productos_adicional" not in lowered
    assert "proveedor" not in lowered
    assert "marca" not in lowered
    assert "left join" not in lowered
    assert "articuloscodigo" in lowered.replace(" ", "")


@pytest.mark.unit
def test_fetch_database_error_hides_driver_text(monkeypatch):
    class _Boom:
        def __enter__(self):
            raise ConnectionError("Login failed for user sa on host prod-db.internal")

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(acl, "_open_database", lambda: _Boom())
    mapping = acl.TerritoryMapping(
        key_field="vendedor_codigo",
        label_field="VendedorFactura",
    )
    with pytest.raises(RuntimeError, match="base de datos") as caught:
        acl.fetch_territory_sku_sales("2026-08-01", "2026-08-31", mapping)
    message = str(caught.value)
    assert "prod-db" not in message
    assert "Login failed" not in message
    assert " sa " not in f" {message} "
    assert "Detalle:" not in message


@pytest.mark.unit
def test_invalid_yaml_raises_clear_value_error(tmp_path: Path):
    path = tmp_path / "broken.yaml"
    path.write_text("placeholder: [unterminated\n  skus:\n", encoding="utf-8")
    with pytest.raises(ValueError, match="YAML") as caught:
        acl.load_core_lines_config(path)
    assert "traceback" not in str(caught.value).lower()


@pytest.mark.unit
def test_main_invalid_yaml_is_spanish(tmp_path: Path, capsys):
    path = tmp_path / "broken.yaml"
    path.write_text("placeholder: [unterminated\n", encoding="utf-8")
    code = acl.main(
        [
            "--synthetic",
            "--config",
            str(path),
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )
    assert code == 1
    err = capsys.readouterr().err
    assert "YAML" in err or "yaml" in err.lower()
    assert (
        "líneas núcleo" in err.lower()
        or "lineas nucleo" in err.lower()
        or "config" in err.lower()
    )
    assert not (tmp_path / "out").exists()


@pytest.mark.unit
def test_html_does_not_call_positive_sum_net_billing():
    report = acl.build_report(
        sales_rows=_sales_rows(),
        config=_config(),
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 31),
    )
    html = acl.render_html(report)
    assert "facturación neta" not in html.lower()
    assert "facturacion neta" not in html.lower()
    assert "líneas positivas" in html.lower() or "lineas positivas" in html.lower()
    assert "no se netean" in html.lower() or "no se netea" in html.lower()


@pytest.mark.unit
def test_csv_guard_cell_skips_numeric_values():
    assert acl.csv_guard_cell(-400_000) == "-400000"
    assert acl.csv_guard_cell(-12.5) == "-12.5"
    assert acl.csv_guard_cell(5_000_000) == "5000000"
    assert acl.csv_guard_cell("-400000") == "'-400000"
    assert acl.csv_guard_cell("+12") == "'+12"
    assert acl.csv_guard_cell(Decimal("-12.50")) == "-12.50"
    assert acl.csv_guard_cell(Decimal("12.50")) == "12.50"


@pytest.mark.unit
def test_write_report_csv_has_utf8_bom(tmp_path: Path):
    report = acl.build_synthetic_report(
        run_date=date(2026, 9, 30),
        config=_config(),
    )
    result = acl.write_report(report, tmp_path)
    raw = result.csv_path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    text = result.csv_path.read_text(encoding="utf-8-sig")
    assert "Territorio" in text
    assert "Ana Demo" in text


@pytest.mark.unit
def test_main_placeholder_does_not_create_output_dir(tmp_path: Path, capsys):
    cfg = _live_yaml(tmp_path / "placeholder.yaml", placeholder=True)
    output = tmp_path / "fresh_out"
    code = acl.main(
        [
            "--config",
            str(cfg),
            "--output-dir",
            str(output),
            "--run-date",
            "2026-09-30",
        ]
    )
    assert code == 1
    err = capsys.readouterr().err
    assert "marcador sintético" in err.lower()
    assert not output.exists()
