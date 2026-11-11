"""TSOL-GENERAL export mapping and workbook shape."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from business_analyzer.core.tsol_export import (
    INVENTARIO_HEADERS,
    VENTAS_HEADERS,
    assemble_inventario_row,
    assemble_venta_row,
    brand_match_sql,
    build_inventory_sql,
    build_sales_sql,
    format_divipola,
    format_nit,
    format_tsol_date,
    month_bounds,
    previous_calendar_month,
    quality_issues,
    quality_summary,
)
from business_analyzer.reports.tsol_export import (
    build_tsol_result,
    tsol_output_basename,
    write_tsol_xlsx,
)


def test_format_tsol_date_ddmmyyyy():
    assert format_tsol_date(date(2015, 10, 2)) == "02102015"
    assert format_tsol_date("2026-07-31") == "31072026"
    assert format_tsol_date(None) == ""


def test_format_nit_appends_dv():
    assert format_nit("890300300", "8") == "890300300-8"
    assert format_nit("12124183", " ") == "12124183"
    assert format_nit(" 90.198.6969 ", "  ") == "901986969"


def test_format_divipola_pads_department_and_city():
    assert format_divipola("41", "1") == "41001"
    assert format_divipola("18", "001") == "18001"
    assert format_divipola("", "001") == ""


def test_month_bounds_and_previous_month():
    start, end = month_bounds(2026, 7)
    assert start == date(2026, 7, 1)
    assert end == date(2026, 8, 1)
    assert previous_calendar_month(today=date(2026, 8, 24)) == (2026, 7)


def test_sales_sql_keeps_invoice_filter_and_exclusions():
    sql = build_sales_sql("sika")
    assert "DocumentosCodigo NOT IN ('XY'" in sql
    assert "'FED'" in sql
    assert "'DVE'" in sql
    assert "LIKE 'SIKA%'" in sql
    assert "AlmacenCodigo IN ('ALM')" not in sql
    assert sql.count("%s") == 2
    inv = build_inventory_sql("sika", inventory_year=2026)
    assert "d.Ano = 2026" in inv
    assert "ALM" in inv


def test_pintuco_sql_uses_sku_009_all_bodegas_and_returns():
    sql = build_sales_sql("pintuco")
    assert "ArticulosCodigo LIKE '009%'" in sql
    assert "AlmacenCodigo IN ('ALM')" not in sql
    assert "DVE" in sql
    assert "NOT LIKE '%DEVOLUC%'" not in sql
    inv = build_inventory_sql("pintuco", inventory_year=2026)
    assert "ArticulosCodigo LIKE '009%'" in inv
    assert "AlmacenCodigo IN ('ALM')" not in inv
    assert "HAVING" not in inv


def test_brand_match_sql_whitelist_and_sika_exclude():
    sql = brand_match_sql("bd.proveedor", "sika")
    assert "LIKE 'SIKA%'" in sql
    assert "S.IVA" in sql
    assert brand_match_sql("a.ArticulosMarca", "all") == "1 = 1"


def test_assemble_venta_row_matches_template_headers():
    row = assemble_venta_row(
        {
            "NumeroDocumento": 447748,
            "Fecha": date(2026, 7, 5),
            "VendedorCodigo": "140",
            "VendedorNombre": "LUIS ESTEBAN MEDINA",
            "Cedula": "1083864123",
            "DepartamentoCodigo": "41",
            "CiudadCodigo": "001",
            "CiudadNombre": "NEIVA",
            "TercerosID": 7710,
            "TercerosRazonSocial": "",
            "TercerosNombres": "FREDI TRUJILLO CULMA",
            "TercerosIdentificacion": "12124183",
            "TercerosDv": " ",
            "TercerosDireccion": "CLUB CAMPESTRE LOTE 76",
            "ArticulosCodigo": "0020280070",
            "ArticulosNombre": "SIKA MONOTOP 107 25KG",
            "BarrasCodigo": "",
            "TipoNegocioCodigo": "003",
            "TipoNegocioNombre": "CLIENTE FINAL",
            "Cantidad": 4,
            "ValorCosto": 4000.4,
            "TotalSinIva": 10000.1,
        }
    )
    assert list(row.keys()) == list(VENTAS_HEADERS)
    assert row["NUMERO\nFACTURAS"] == "447748"
    assert row["FECHA VENTA"] == "05072026"
    assert row["CODIGO DE MUNICIPIO"] == "41001"
    assert row["NIT CLIENTE"] == "12124183"
    assert row["VALOR TOTAL VENTA"] == 10000.1
    assert row["COSTO"] == 4000.4


def test_assemble_inventario_row_uses_as_of_and_unit_fallback():
    row = assemble_inventario_row(
        {
            "ArticulosCodigo": "0020280070",
            "ArticulosNombre": "SIKA MONOTOP 107 25KG",
            "Cantidad": 12.5,
            "MedidasCodigo": "",
        },
        as_of=date(2026, 7, 31),
    )
    assert list(row.keys()) == list(INVENTARIO_HEADERS)
    assert row["FECHA"] == "31072026"
    assert row["UN MEDIDA"] == "UN"
    assert row["CANTIDAD"] == 12.5


def test_quality_summary_counts_gaps():
    ventas = [
        assemble_venta_row(
            {
                "NumeroDocumento": 1,
                "Fecha": date(2026, 7, 1),
                "TercerosIdentificacion": "",
                "TercerosDireccion": "",
                "TotalSinIva": 100,
                "ValorCosto": 40,
            }
        )
    ]
    q = quality_summary(ventas, [])
    assert q["venta_rows"] == 1
    assert q["missing_nit"] == 1
    assert q["missing_direccion"] == 1
    assert q["venta_total"] == 100


def test_write_tsol_xlsx_keeps_sheet_names_and_headers(tmp_path):
    ventas = [
        assemble_venta_row(
            {
                "NumeroDocumento": "1234567",
                "Fecha": date(2015, 10, 2),
                "VendedorCodigo": "08",
                "VendedorNombre": "JOHN BERMUDEZ",
                "Cedula": "94100000",
                "DepartamentoCodigo": "41",
                "CiudadCodigo": "006",
                "CiudadNombre": "MUNICIPIO 1",
                "TercerosID": 1234,
                "TercerosNombres": "STEPHANIA GOMEZ",
                "TercerosIdentificacion": "890300300",
                "TercerosDv": "8",
                "TercerosDireccion": "CALLE 1 # 23 - 45",
                "ArticulosCodigo": "500034",
                "ArticulosNombre": "PRODUCTO 1",
                "BarrasCodigo": "770123456",
                "TipoNegocioCodigo": "01",
                "TipoNegocioNombre": "TIENDA",
                "Cantidad": 4,
                "ValorCosto": 4000,
                "TotalSinIva": 10000,
            }
        )
    ]
    inventario = [
        assemble_inventario_row(
            {
                "ArticulosCodigo": "500034",
                "ArticulosNombre": "PRODUCTO 1",
                "Cantidad": 213,
                "MedidasCodigo": "UN",
            },
            as_of=date(2017, 12, 1),
        )
    ]
    path = tmp_path / "tsol.xlsx"
    write_tsol_xlsx(path, ventas, inventario)
    from openpyxl import load_workbook

    wb = load_workbook(path)
    assert wb.sheetnames == ["Ventas", "Inventario"]
    assert [c.value for c in wb["Ventas"][1]] == list(VENTAS_HEADERS)
    assert wb["Ventas"]["A2"].value == "1234567"
    assert wb["Ventas"]["B2"].value == "02102015"
    assert wb["Ventas"]["J2"].value == "890300300-8"
    assert wb["Ventas"]["S2"].value == 10000
    assert [c.value for c in wb["Inventario"][1]] == list(INVENTARIO_HEADERS)
    assert wb["Inventario"]["A2"].value == "01122017"


def test_basename_and_build_from_payload(tmp_path):
    assert tsol_output_basename("sika", 2026, 7) == "TSOL_SIKA_2026-07.xlsx"
    assert (
        tsol_output_basename("sika", start="2026-01-01", end="2026-08-24")
        == "TSOL_SIKA_2026-01-01_2026-08-24.xlsx"
    )
    payload = {
        "brand": "sika",
        "year": 2026,
        "month": 7,
        "period_start": "2026-07-01",
        "period_end": "2026-07-31",
        "ventas": [
            assemble_venta_row(
                {
                    "NumeroDocumento": 1,
                    "Fecha": date(2026, 7, 1),
                    "TercerosIdentificacion": "1",
                    "TotalSinIva": 10,
                    "ValorCosto": 5,
                    "Cantidad": 1,
                    "ArticulosCodigo": "X",
                    "ArticulosNombre": "SIKA",
                }
            )
        ],
        "inventario": [],
    }
    result = build_tsol_result(
        brand="sika",
        year=2026,
        month=7,
        output_dir=tmp_path,
        payload=payload,
    )
    assert result["status"] == "success"
    assert Path(result["path"]).exists()
    assert result["quality"]["venta_rows"] == 1


def test_quality_issues_flags_blockers():
    quality = {
        "venta_rows": 10,
        "missing_barcode": 10,
        "placeholder_nit": 2,
        "missing_tipo_negocio": 0,
        "missing_cedula_vendedor": 0,
        "inventory_negative": 1,
    }
    ids = {i["id"] for i in quality_issues(quality)}
    assert {"barcode_empty_all", "placeholder_nit", "inventory_negative"} <= ids


def test_build_tsol_result_strict_blocks_and_writes_quality(tmp_path: Path):
    from business_analyzer.reports.tsol_export import build_tsol_result

    payload = {
        "brand": "sika",
        "year": 2026,
        "month": 10,
        "period_start": "2026-10-01",
        "period_end": "2026-10-31",
        "ventas": [
            {
                "NUMERO\nFACTURAS": "1",
                "FECHA VENTA": "01102026",
                "CODIGO DE BARRA": "",
                "NIT CLIENTE": "222222222222",
                "NOM.CLIENTE": "CONSUMIDOR FINAL",
                "CODIGO TIPO NEGOCIO": "",
                "CEDULA VENDEDOR": "",
            }
        ],
        "inventario": [],
        "quality": {
            "venta_rows": 1,
            "inventario_rows": 0,
            "missing_nit": 0,
            "missing_direccion": 0,
            "missing_municipio": 0,
            "missing_tipo_negocio": 1,
            "missing_cedula_vendedor": 1,
            "missing_barcode": 1,
            "placeholder_nit": 1,
            "generic_customer": 1,
            "inventory_negative": 0,
        },
    }
    out = tmp_path / "TSOL_TEST.xlsx"
    result = build_tsol_result(payload=payload, output_path=out, strict=True)
    assert result["status"] == "error"
    assert "BLOQUEADO" in result["message"]
    assert (tmp_path / "TSOL_TEST.calidad.json").exists()
