"""Invoice-number customer summary: parser, assembler, renderers."""

from __future__ import annotations

import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from business_analyzer.core.invoice_summary import (
    MAX_INVOICES,
    assemble_invoice_summary,
    parse_invoice_numbers,
    public_sede_name,
)
from business_analyzer.reports.invoice_summary import (
    build_invoice_summary_result,
    invoice_summary_output_basename,
    render_markdown,
)


def test_parse_invoice_numbers_from_mixed_text():
    text = "447748\n447777, 448060 448129; 449437 449438"
    assert parse_invoice_numbers(text) == [
        447748,
        447777,
        448060,
        448129,
        449437,
        449438,
    ]


def test_parse_invoice_numbers_dedupes_and_drops_junk():
    assert parse_invoice_numbers("abc 12 447748 447748 FED-447777") == [
        447748,
        447777,
    ]


def test_parse_invoice_numbers_empty():
    assert parse_invoice_numbers("  , ; \n") == []


def test_parse_invoice_numbers_caps_list():
    blob = " ".join(str(100000 + i) for i in range(MAX_INVOICES + 20))
    parsed = parse_invoice_numbers(blob)
    assert len(parsed) == MAX_INVOICES


def test_public_sede_name_does_not_expose_erp_code():
    assert public_sede_name("FED") == "Almacén Principal"
    assert "FED" not in public_sede_name("FED")


def _line(
    numero,
    *,
    fecha="2026-08-05",
    cliente="FREDI TRUJILLO CULMA",
    nit="12124183",
    codigo="0020390074",
    nombre="CODO SANITARIO 45 CC 4 T/PESADO",
    categoria="TUBERIA Y ACCE PVC",
    cantidad=4,
    sin=31200,
    mas=37128,
    iva=19,
    detalle=" CLUB CAMPESTRE LOTE 76",
    credito=30,
    vendedor="LUIS ESTEBAN MEDINA",
    doc="FED",
    terceros_id=7710,
):
    return {
        "DocumentosCodigo": doc,
        "DocumentosNombre": "FACTURA ELECTRONICA DE VENTA",
        "NumeroDocumento": Decimal(str(numero)),
        "Fecha": date.fromisoformat(fecha),
        "TercerosID": terceros_id,
        "TercerosIdentificacion": nit,
        "TercerosNombres": cliente,
        "DiasCredito": Decimal(str(credito)),
        "VendedorFactura": vendedor,
        "ArticulosCodigo": codigo,
        "ArticulosNombre": nombre,
        "categoria": categoria,
        "Cantidad": Decimal(str(cantidad)),
        "TotalSinIva": Decimal(str(sin)),
        "TotalMasIva": Decimal(str(mas)),
        "Iva": Decimal(str(iva)),
        "Detalle": detalle,
    }


def test_assemble_groups_invoices_and_totals():
    lines = [
        _line(447748, cantidad=4, sin=31200, mas=37128),
        _line(
            447748,
            codigo="0030050010",
            nombre="LADRILLO TOLETE",
            categoria="ART Y HERRAM AGRICOLAS",
            cantidad=600,
            sin=900000,
            mas=900000,
            iva=0,
        ),
        _line(
            447777,
            codigo="0020090002",
            nombre="CEMENTO GRIS CEMEX 50KG",
            categoria="CEMENTO GRIS",
            cantidad=70,
            sin=1952930,
            mas=2323986.70,
        ),
    ]
    cartera = [
        {
            "documento_tipo": "FED ",
            "documento_numero": 447748,
            "documento_fecha_vencimiento": date(2026, 9, 4),
            "documento_fecha_cancela": None,
            "debitos": Decimal("937128"),
            "creditos": Decimal("0"),
            "total": Decimal("937128"),
            "corriente": Decimal("937128"),
            "vencido": Decimal("0"),
            "dias_vencidos": -17,
        }
    ]
    report = assemble_invoice_summary(
        requested=[447748, 447777, 440136],
        line_rows=lines,
        cartera_rows=cartera,
    )
    assert report["missing"] == [440136]
    assert report["customer"]["name"] == "FREDI TRUJILLO CULMA"
    assert report["customer"]["nit"] == "12124183"
    assert report["summary"]["invoice_count"] == 2
    assert abs(report["summary"]["total_sin_iva"] - 2884130) < 0.01
    assert abs(report["summary"]["total_mas_iva"] - 3261114.70) < 0.01
    assert report["invoices"][0]["numero"] == 447748
    assert report["invoices"][0]["vence"] == "2026-09-04"
    assert report["obra"] == "CLUB CAMPESTRE LOTE 76"
    skus = {item["codigo"] for inv in report["invoices"] for item in inv["lines"]}
    assert "0030050010" in skus


def test_assemble_mixed_customers_sets_multiple_flag():
    lines = [
        _line(447748),
        _line(
            440136,
            fecha="2026-07-09",
            cliente="OTRO CLIENTE SAS",
            nit="901078509",
            terceros_id=99,
            codigo="0020030020",
            nombre="MALLA",
            cantidad=1,
            sin=148492,
            mas=176705.48,
            detalle="",
            credito=0,
        ),
    ]
    report = assemble_invoice_summary(
        requested=[447748, 440136],
        line_rows=lines,
        cartera_rows=[],
    )
    assert report["multiple_customers"] is True
    assert len(report["customers"]) == 2


def test_render_markdown_is_spanish_and_omits_costs():
    report = assemble_invoice_summary(
        requested=[447748],
        line_rows=[_line(447748)],
        cartera_rows=[],
    )
    md = render_markdown(report)
    assert "Fredi" in md or "FREDI" in md
    assert "447748" in md
    assert "Costo" not in md
    assert "FED" not in md
    assert "$37.128" in md or "$37.128,00" in md


def test_basename():
    assert invoice_summary_output_basename("html") == "RESUMEN_FACTURAS.html"
    assert invoice_summary_output_basename("pdf", slug="fredi") == (
        "RESUMEN_FACTURAS_fredi.pdf"
    )


def test_build_result_requires_invoices():
    result = build_invoice_summary_result(invoices="")
    assert result["status"] == "error"
    assert "factura" in result["message"].lower()


def test_build_writes_html_without_erp_code(tmp_path):
    report = assemble_invoice_summary(
        requested=[447748],
        line_rows=[_line(447748)],
        cartera_rows=[],
    )
    result = build_invoice_summary_result(
        invoices=[447748],
        report=report,
        output_dir=tmp_path,
        fmt="html",
    )
    assert result["status"] == "success"
    html = Path(result["path"]).read_text(encoding="utf-8")
    assert "447748" in html
    assert "FED" not in html
    assert "FREDI" in html


def test_flask_generate_invoice_summary(tmp_path, monkeypatch):
    from unittest.mock import patch

    from business_analyzer.ai.flask_app import SmartVannaFlaskApp

    class _Stub:
        run_sql_is_set = True

        def generate_sql(self, question, allow_llm_to_see_data=True, **kwargs):
            return None

    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    html_out = tmp_path / "RESUMEN_FACTURAS_fredi.html"
    html_out.write_text("<html>ok</html>", encoding="utf-8")
    app = SmartVannaFlaskApp(_Stub(), chart=False)
    app.flask_app.config["TESTING"] = True
    with app.flask_app.test_client() as client:
        with patch(
            "business_analyzer.reports.invoice_summary.build_invoice_summary_result",
            return_value={
                "status": "success",
                "format": "html",
                "path": str(html_out),
                "message": "ok",
                "invoice_count": 6,
                "customer_name": "FREDI TRUJILLO CULMA",
                "missing": [],
            },
        ):
            response = client.post(
                "/api/v0/generate_invoice_summary",
                json={"invoices": "447748 447777", "format": "html"},
            )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["type"] == "invoice_summary"
    assert payload["download_url"] == "/reports/RESUMEN_FACTURAS_fredi.html"
    assert payload["invoice_count"] == 6


def test_flask_generate_invoice_summary_requires_numbers(tmp_path, monkeypatch):
    from business_analyzer.ai.flask_app import SmartVannaFlaskApp

    class _Stub:
        run_sql_is_set = True

        def generate_sql(self, question, allow_llm_to_see_data=True, **kwargs):
            return None

    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    app = SmartVannaFlaskApp(_Stub(), chart=False)
    app.flask_app.config["TESTING"] = True
    with app.flask_app.test_client() as client:
        response = client.post("/api/v0/generate_invoice_summary", json={})
    assert response.status_code == 200
    assert response.get_json()["type"] == "error"


def test_build_writes_pdf(tmp_path):
    report = assemble_invoice_summary(
        requested=[447748],
        line_rows=[_line(447748)],
        cartera_rows=[],
    )
    result = build_invoice_summary_result(
        invoices=[447748],
        report=report,
        output_dir=tmp_path,
        fmt="pdf",
    )
    assert result["status"] == "success"
    assert Path(result["path"]).is_file()
    assert Path(result["path"]).stat().st_size > 500
