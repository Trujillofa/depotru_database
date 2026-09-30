"""Unit tests for the AkzoNobel Core Lines report. Synthetic data only."""

from __future__ import annotations

import csv
from datetime import date
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
        "proveedor_contains": ("AKZO-DEMO-VENDOR",),
        "marca_contains": ("AKZO-DEMO-MARCA",),
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
            "proveedor": "AKZO-DEMO-VENDOR",
            "marca": "AKZO-DEMO-MARCA",
        },
        {
            "territory_key": "01",
            "territory_label": "Ana Demo",
            "sku": "SKU-OTRO-001",
            "product_name": "Cemento demo",
            "revenue": 4_200_000,
            "proveedor": "OTRO-DEMO",
            "marca": "OTRO",
        },
        {
            "territory_key": "02",
            "territory_label": "Luis Demo",
            "sku": "SKU-OTRO-002",
            "product_name": "Broca demo",
            "revenue": 1_200_000,
            "proveedor": "OTRO-DEMO",
            "marca": "OTRO",
        },
    ]


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
    assert "AKZO-DEMO-VENDOR" in text
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
          "vendor_match": {
            "proveedor_contains": ["AKZO-DEMO-VENDOR"],
            "marca_contains": ["AKZO-DEMO-MARCA"]
          },
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
            "proveedor": "OTRO-DEMO",
            "marca": "OTRO",
        },
        {
            "territory_key": "03",
            "territory_label": "Carla Demo",
            "sku": "AKZO-DEMO-001",
            "product_name": "Pintura demo línea núcleo 1",
            "revenue": 10_000,
            "proveedor": "AKZO-DEMO-VENDOR",
            "marca": "AKZO-DEMO-MARCA",
        },
        {
            "territory_key": "03",
            "territory_label": "Carla Demo",
            "sku": "AKZO-DEMO-002",
            "product_name": "Pintura demo línea núcleo 2",
            "revenue": 10_000,
            "proveedor": "AKZO-DEMO-VENDOR",
            "marca": "AKZO-DEMO-MARCA",
        },
        {
            "territory_key": "03",
            "territory_label": "Carla Demo",
            "sku": "AKZO-DEMO-003",
            "product_name": "Pintura demo línea núcleo 3",
            "revenue": 10_000,
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
def test_matches_vendor_tokens_are_synthetic_only():
    assert acl.matches_vendor_tokens(
        {"proveedor": "AKZO-DEMO-VENDOR", "marca": "x"},
        _config(),
    )
    assert acl.matches_vendor_tokens(
        {"proveedor": "otro", "marca": "AKZO-DEMO-MARCA"},
        _config(),
    )
    assert not acl.matches_vendor_tokens(
        {"proveedor": "SIKA COLOMBIA", "marca": "SIKA"},
        _config(),
    )


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
def test_html_escapes_injected_names():
    rows = [
        {
            "territory_key": "99",
            "territory_label": "<Vendedor Script>",
            "sku": "SKU-OTRO-X",
            "product_name": "Otro <demo>",
            "revenue": 1000,
            "proveedor": "OTRO",
            "marca": "OTRO",
        }
    ]
    report = acl.build_report(
        sales_rows=rows,
        config=_config(),
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 31),
    )
    html = acl.render_html(report)
    assert "<Vendedor Script>" not in html
    assert "&lt;Vendedor Script&gt;" in html


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
    assert "productos_adicional" in lowered
    assert "totalsiniva" in lowered
    assert "between %s and %s" in lowered
    assert params[0] == "2026-08-01"
    assert params[1] == "2026-08-31"
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
                "vendor_match:",
                "  proveedor_contains:",
                "    - AKZO-DEMO-VENDOR",
                "  marca_contains:",
                "    - AKZO-DEMO-MARCA",
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
    with patch.object(acl, "fetch_territory_sku_sales", return_value=_sales_rows()):
        code = acl.main(
            [
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
            "proveedor": "AKZO-DEMO-VENDOR",
            "marca": "AKZO-DEMO-MARCA",
        },
        {
            "territory_key": "01",
            "territory_label": "Ana Demo",
            "sku": "AKZO-DEMO-002",
            "product_name": "Pintura demo línea núcleo 2",
            "revenue": 10,
            "proveedor": "AKZO-DEMO-VENDOR",
            "marca": "AKZO-DEMO-MARCA",
        },
        {
            "territory_key": "01",
            "territory_label": "Ana Demo",
            "sku": "AKZO-DEMO-003",
            "product_name": "Pintura demo línea núcleo 3",
            "revenue": 10,
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
def test_json_string_skus_and_vendor_token(tmp_path: Path):
    path = tmp_path / "core.json"
    path.write_text(
        '{"placeholder": true, "vendor_match": {"proveedor_contains": '
        '"AKZO-DEMO-VENDOR"}, "skus": ["AKZO-DEMO-020"]}',
        encoding="utf-8",
    )
    cfg = acl.load_core_lines_config(path)
    assert cfg.skus[0].sku == "AKZO-DEMO-020"
    assert cfg.proveedor_contains == ("AKZO-DEMO-VENDOR",)


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
    assert params[2:] == ("XY", "AS", "TS", "YX", "ISC")


@pytest.mark.unit
def test_dimension_cli_overrides_mapping(tmp_path: Path):
    rows = [
        {
            "territory_key": "Neiva Demo",
            "territory_label": "Neiva Demo",
            "sku": "SKU-OTRO-001",
            "product_name": "Cemento demo",
            "revenue": 2_000_000,
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
