"""Tests for Sika Center impact report helpers (post-audit)."""

import datetime as dt

import pytest

from business_analyzer.analysis.customer_contact import (
    canal_preferido,
    clean_ciudad,
    clean_email,
    es_cliente_generico,
    es_festivo_colombia,
    festivos_colombia,
    find_placeholder_emails_by_frequency,
    mejor_celular,
    repair_mojibake,
)
from business_analyzer.analysis.sika_impact import (
    SEGMENT_ACTIVO,
    SEGMENT_INACTIVO,
    SEGMENT_RIESGO,
    build_sika_customers_query,
    build_summary,
    classify_segment,
    data_window,
    enrich_customer_metrics,
    export_xlsx,
    fetch_sika_customers,
    is_lapsed,
    merge_contact_lookup,
    sort_call_list,
    sugerir_umbrales,
    validar_runrate,
)

TODAY = dt.date(2026, 9, 3)
INICIO = dt.date(2026, 1, 23)


class TestContactHelpers:
    def test_mejor_celular_valid_and_coalesce(self):
        assert mejor_celular("3112322514") == "3112322514"
        assert mejor_celular("", "3152046509") == "3152046509"
        assert mejor_celular(None, "608 464 5976") is None

    def test_mejor_celular_rejects_invalid(self):
        assert mejor_celular("0") is None
        assert mejor_celular("320324864") is None  # 9 dígitos
        assert mejor_celular("31434202900") is None  # 11 dígitos
        assert mejor_celular("-*") is None

    def test_clean_email_placeholders(self):
        assert clean_email("nocorreo@gmail.com") is None
        assert clean_email("nocorreo@hotmail.com") is None
        assert clean_email("ventascontado@yahoo.com") is None
        assert clean_email("fe@gmail.com") is None
        assert clean_email("clientes@depositotrujillo.com") is None
        assert clean_email("notiene@gmail.com") is None
        assert clean_email("notieneee@gmail.com") is None
        assert clean_email("notienecorreo@gmail.com") is None
        assert clean_email("nocorreo29@gmail.com") is None
        assert clean_email("ventas@yahoo.com") is None
        assert clean_email("clientes@depositrujillo.com") is None
        assert clean_email("ventas@depositotrujillo.com") is None
        assert clean_email("x@depositrujillo.com") is None

    def test_clean_email_valid(self):
        assert clean_email(" Ferreteria.X@mail.co ") == "Ferreteria.X@mail.co"
        assert clean_email("sin arroba") is None
        assert clean_email("ventas@ferreteria.com") == "ventas@ferreteria.com"

    def test_es_cliente_generico(self):
        assert es_cliente_generico("222222222222", "CONSUMIDOR FINAL")
        assert es_cliente_generico("222.222.222.222", None)
        assert es_cliente_generico("111111111", "X")
        assert not es_cliente_generico("123", "FERRETERIA LA PAZ")

    def test_placeholder_emails_by_frequency(self):
        emails = ["districlientes@gmail.com"] * 3 + ["unico@mail.co", "unico@mail.co"]
        found = find_placeholder_emails_by_frequency(emails)
        assert "districlientes@gmail.com" in found
        assert "unico@mail.co" not in found

    def test_clean_ciudad_cau_to_caq(self):
        assert clean_ciudad("FLORENCIA CAU") == "FLORENCIA CAQ"
        assert clean_ciudad("Florencia CAQ") == "FLORENCIA CAQ"

    def test_festivos_colombia_2026(self):
        festivos = festivos_colombia(2026)
        assert dt.date(2026, 10, 12) in festivos  # Día de la Raza, lunes
        assert dt.date(2026, 5, 18) in festivos  # Ascensión
        assert dt.date(2026, 7, 20) in festivos
        assert es_festivo_colombia(dt.date(2026, 10, 12))
        assert not es_festivo_colombia(dt.date(2026, 10, 13))
        assert len(festivos) == 18

    def test_canal_preferido(self):
        assert canal_preferido("3112322514", "a@b.co") == "WhatsApp"
        assert canal_preferido(None, "a@b.co") == "Email"
        assert canal_preferido(None, None, "6084645976") == "Llamada"
        assert canal_preferido(None, None, None, "CRA 1") == "Visita"
        assert canal_preferido(None, None, None, None) == "Sin contacto"
        assert (
            canal_preferido(None, None, None, "CRA 1", allow_visita=False)
            == "Sin contacto"
        )

    def test_repair_mojibake(self):
        assert repair_mojibake("DISE?O Y FABRICACION") == "DISEÑO Y FABRICACION"


class TestSegmentation:
    def test_thresholds(self):
        assert classify_segment(30) == SEGMENT_ACTIVO
        assert classify_segment(91) == SEGMENT_RIESGO
        assert classify_segment(181) == SEGMENT_INACTIVO

    def test_sugerir_umbrales_short_window(self):
        # Sika Center lanzado en enero 2026: ventana < 365 días (S-6).
        assert sugerir_umbrales(222) == (30, 90)
        assert sugerir_umbrales(700) == (90, 180)

    def test_is_lapsed(self):
        assert is_lapsed({"dias_sin_comprar": 120}, inactivity_days=90)
        assert not is_lapsed({"dias_sin_comprar": 30}, inactivity_days=90)

    def test_data_window(self):
        rows = [
            {"primera_compra": "2026-02-01", "ultima_compra": "2026-08-01"},
            {"primera_compra": INICIO, "ultima_compra": "2026-09-02"},
        ]
        assert data_window(rows) == (INICIO, dt.date(2026, 9, 2))


def _history_row(nit, cliente, facturacion, ganancia, ultima, primera=INICIO):
    return {
        "terceros_id": 1,
        "nit": nit,
        "cliente": cliente,
        "primera_compra": primera,
        "ultima_compra": ultima,
        "cantidad": 2,
        "facturacion": facturacion,
        "ganancia": ganancia,
        "dias_compra": 1,
    }


class TestMetrics:
    def test_mensual_divides_by_window_not_active_months(self):
        # Auditoría S-1: un comprador de una sola vez no puede tener
        # promedio mensual = total histórico.
        rows = [
            _history_row("123", "COMPRA UNICA", 1000000, 200000, dt.date(2026, 3, 1))
        ]
        enriched = enrich_customer_metrics(
            rows,
            today=TODAY,
            inactivity_days=90,
            risk_days=180,
            inicio_ventana=INICIO,
        )
        meses = (TODAY - INICIO).days / 30.44
        assert enriched[0]["facturacion_mensual"] == pytest.approx(1000000 / meses)
        assert enriched[0]["facturacion_mensual"] < 200000
        # Tenure is the full window, so both rates match for an old customer.
        assert enriched[0]["run_rate_cliente"] == pytest.approx(1000000 / meses)

    def test_run_rate_cliente_uses_own_tenure(self):
        rows = [
            _history_row(
                "999",
                "NUEVO",
                3109431,
                500000,
                dt.date(2026, 8, 20),
                primera=dt.date(2026, 8, 10),
            )
        ]
        enriched = enrich_customer_metrics(
            rows, today=TODAY, inactivity_days=30, risk_days=90, inicio_ventana=INICIO
        )
        meses_ventana = (TODAY - INICIO).days / 30.44
        assert enriched[0]["facturacion_mensual"] == pytest.approx(
            3109431 / meses_ventana
        )
        # Tenure < 1 month → piso 1, so run-rate equals the historic total.
        assert enriched[0]["run_rate_cliente"] == pytest.approx(3109431)

    def test_costo_estimado_flag(self):
        rows = [
            _history_row("123", "MARGEN DEFAULT", 1000, 310, dt.date(2026, 8, 1)),
            _history_row("456", "MARGEN REAL", 1000, 257, dt.date(2026, 8, 1)),
        ]
        enriched = enrich_customer_metrics(
            rows, today=TODAY, inactivity_days=90, risk_days=180
        )
        assert enriched[0]["costo_estimado"] is True
        assert enriched[1]["costo_estimado"] is False

    def test_cliente_name_cleaned(self):
        rows = [
            _history_row(
                "123", "  DISE?O  Y   MODULARES  ", 100, 20, dt.date(2026, 8, 1)
            )
        ]
        enriched = enrich_customer_metrics(
            rows, today=TODAY, inactivity_days=90, risk_days=180
        )
        assert enriched[0]["cliente"] == "DISEÑO Y MODULARES"


class TestQueries:
    def test_query_filters_by_document_code(self):
        query = build_sika_customers_query(
            database="SmartBusiness", table="banco_datos"
        )
        assert "WHERE bd.DocumentosCodigo = %s" in query
        assert "TercerosIdentificacion NOT IN" in query
        assert "GROUP BY bd.TercerosID, bd.TercerosIdentificacion" in query

    def test_fetch_passes_document_code_param(self):
        class FakeDatabase:
            def __init__(self):
                self.calls = []

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute_query(self, query, params=None):
                self.calls.append((query, params))
                return [
                    {
                        "nit": "222222222222",
                        "cliente": "CONSUMIDOR FINAL",
                        "facturacion": 99,
                    },
                    {"nit": "123", "cliente": "FERRETERIA X", "facturacion": 1},
                ]

        fake = FakeDatabase()
        rows = fetch_sika_customers(fake, document_code="FEF")
        assert fake.calls[0][1][0] == "FEF"
        assert "222222222222" in fake.calls[0][1]
        assert all(row["nit"] != "222222222222" for row in rows)
        assert rows == [{"nit": "123", "cliente": "FERRETERIA X", "facturacion": 1}]


class TestMerge:
    def test_merge_validates_contacts_and_fills_issues(self):
        rows = [
            {
                "terceros_id": 7,
                "nit": "123",
                "cliente": "CLIENTE",
                "movil": "",
                "telefono": "",
                "direccion": "",
                "ciudad": "",
                "email": "",
                "canal_preferido": "",
            }
        ]
        by_nit = {
            "123": {
                "celular": "31434202900",  # inválido: 11 dígitos
                "telefono": "3112322514",
                "direccion": "CRA 7",
                "ciudad": "FLORENCIA CAQ",
                "email": "nocorreo@gmail.com",
            }
        }
        issues = []
        merged = merge_contact_lookup(rows, by_nit, {}, issues=issues)
        assert merged[0]["movil"] == "3112322514"  # recuperado de Teléfono
        assert merged[0]["telefono"] == ""  # el móvil no se duplica en Teléfono
        assert merged[0]["email"] == ""  # placeholder descartado
        assert merged[0]["canal_preferido"] == "WhatsApp"
        problemas = {(issue["campo"], issue["problema"]) for issue in issues}
        assert ("Email", "Correo de relleno o inválido") in problemas

    def test_merge_without_match_is_sin_contacto(self):
        rows = [{"terceros_id": 1, "nit": "999", "cliente": "A"}]
        merged = merge_contact_lookup(rows, {}, {})
        assert merged[0]["canal_preferido"] == "Sin contacto"
        assert merged[0]["movil"] == ""

    def test_merge_cleans_telefono_ciudad_and_frequent_email(self):
        rows = [
            {
                "terceros_id": 1,
                "nit": "1",
                "cliente": "A",
                "movil": "",
                "telefono": "",
                "direccion": "",
                "ciudad": "",
                "email": "",
                "canal_preferido": "",
            },
            {
                "terceros_id": 2,
                "nit": "2",
                "cliente": "B",
                "movil": "",
                "telefono": "",
                "direccion": "",
                "ciudad": "",
                "email": "",
                "canal_preferido": "",
            },
            {
                "terceros_id": 3,
                "nit": "3",
                "cliente": "C",
                "movil": "",
                "telefono": "",
                "direccion": "",
                "ciudad": "",
                "email": "",
                "canal_preferido": "",
            },
        ]
        by_nit = {
            "1": {
                "celular": "3001112233",
                "telefono": "0",
                "direccion": "CRA 1",
                "ciudad": "FLORENCIA CAU",
                "email": "districlientes@gmail.com",
            },
            "2": {
                "celular": "3001112234",
                "telefono": "6084645976",
                "direccion": "CRA 2",
                "ciudad": "FLORENCIA CAQ",
                "email": "districlientes@gmail.com",
            },
            "3": {
                "celular": "3001112235",
                "telefono": "-*",
                "direccion": "CRA 3",
                "ciudad": "FLORENCIA CAQ",
                "email": "districlientes@gmail.com",
            },
        }
        issues = []
        merged = merge_contact_lookup(rows, by_nit, {}, issues=issues)
        assert merged[0]["ciudad"] == "FLORENCIA CAQ"
        assert merged[0]["telefono"] == ""
        assert merged[1]["telefono"] == "6084645976"
        assert all(row["email"] == "" for row in merged)
        campos = {issue["campo"] for issue in issues}
        assert "Teléfono" in campos
        assert "Ciudad" in campos
        assert "Email" in campos


class TestRunrateGuard:
    def _rows(self, mensual, historica):
        return [{"facturacion_mensual": mensual, "facturacion_historica": historica}]

    def test_honest_runrate_passes(self):
        validar_runrate(self._rows(100000.0, 1000000.0))

    def test_inflated_runrate_raises(self):
        rows = self._rows(600000.0, 1000000.0) * 3 + self._rows(10.0, 1000000.0)
        with pytest.raises(ValueError):
            validar_runrate(rows)


class TestSummary:
    def test_summary_uses_validated_counts(self):
        rows = [
            {
                "segmento": SEGMENT_ACTIVO,
                "dias_sin_comprar": 5,
                "facturacion_historica": 1000000,
                "facturacion_mensual": 100000,
                "movil": "3001112233",
                "email": "",
                "costo_estimado": False,
            },
            {
                "segmento": SEGMENT_INACTIVO,
                "dias_sin_comprar": 200,
                "facturacion_historica": 4000000,
                "facturacion_mensual": 400000,
                "movil": "",
                "email": "a@b.co",
                "costo_estimado": True,
            },
        ]
        summary = build_summary(rows, inactivity_days=90, inicio_ventana=INICIO)
        assert summary["total_clientes"] == 2
        assert summary["clientes_sin_comprar"] == 1
        assert summary["con_movil"] == 1
        assert summary["con_email"] == 1
        assert summary["costo_estimado"] == 1
        assert summary["inicio_ventana"] == INICIO
        assert summary["facturacion_historica_inactivos"] == 4000000
        assert summary["facturacion_historica_en_riesgo"] == 0

    def test_summary_umbrales_short_window_are_31_90(self):
        rows = [
            {
                "segmento": SEGMENT_RIESGO,
                "dias_sin_comprar": 45,
                "facturacion_historica": 1000,
                "facturacion_mensual": 100,
                "movil": "",
                "email": "",
                "costo_estimado": False,
            }
        ]
        summary = build_summary(
            rows, inactivity_days=90, risk_days=30, inicio_ventana=INICIO
        )
        assert summary["activo_max_dias"] == 30
        assert summary["inactivo_min_dias"] == 90
        assert summary["facturacion_historica_en_riesgo"] == 1000
        assert summary["facturacion_historica_inactivos"] == 0

    def test_sort_lapsed_first_then_runrate(self):
        rows = [
            {"segmento": SEGMENT_ACTIVO, "facturacion_mensual": 1.0},
            {"segmento": SEGMENT_INACTIVO, "facturacion_mensual": 5.0},
            {"segmento": SEGMENT_RIESGO, "facturacion_mensual": 9.0},
        ]
        assert [r["segmento"] for r in sort_call_list(rows)] == [
            SEGMENT_INACTIVO,
            SEGMENT_RIESGO,
            SEGMENT_ACTIVO,
        ]


class TestExport:
    def test_export_single_data_sheet_with_quality(self, tmp_path):
        rows = [
            {
                "segmento": SEGMENT_INACTIVO,
                "cliente": "CLIENTE PRUEBA",
                "nit": "123",
                "dias_sin_comprar": 200,
                "ultima_compra": dt.date(2026, 1, 15),
                "primera_compra": INICIO,
                "dias_compra": 1,
                "facturacion_historica": 1500000.0,
                "facturacion_mensual": 205000.0,
                "run_rate_cliente": 1500000.0,
                "ganancia_historica": 300000.0,
                "ticket_promedio": 1500000.0,
                "costo_estimado": True,
                "movil": "3001112233",
                "telefono": "3001112233",
                "direccion": "CRA 1",
                "ciudad": "FLORENCIA CAQ",
                "email": "a@b.co",
                "canal_preferido": "WhatsApp",
            }
        ]
        summary = build_summary(rows, inactivity_days=90, inicio_ventana=INICIO)
        issues = [
            {
                "nit": "999",
                "cliente": "OTRO",
                "campo": "Celular",
                "valor": "0",
                "problema": "No es un móvil colombiano válido (3XXXXXXXXX)",
            }
        ]
        output = tmp_path / "sika.xlsx"
        export_xlsx(
            rows,
            str(output),
            summary=summary,
            quality_issues=issues,
            excluded_documents=("XY", "AS", "TS"),
        )
        assert output.exists()

        import openpyxl

        workbook = openpyxl.load_workbook(output)
        # S-8: una sola hoja de datos, sin copia "Contactar".
        assert workbook.sheetnames == ["Clientes", "Resumen", "Calidad de datos"]
        headers = [cell.value for cell in workbook["Clientes"][1]]
        assert headers[0] == "Segmento"
        assert "Móvil (validado)" in headers
        assert "Canal preferido" in headers
        resumen_text = "\n".join(
            str(row) for row in workbook["Resumen"].iter_rows(values_only=True)
        )
        assert "Fecha de corte" in resumen_text
        assert "DocumentosCodigo = 'FEF'" in resumen_text
        assert "No es un plan de visitas" in resumen_text
        assert "Facturación histórica de inactivos" in resumen_text
        assert "Aporte mensual a la ventana" in headers
        assert "Run-rate del cliente" in headers
        primera_width = workbook["Clientes"].column_dimensions["F"].width
        assert primera_width is not None and primera_width >= 18
        ultima_width = workbook["Clientes"].column_dimensions["E"].width
        assert ultima_width is not None and ultima_width >= 18
        calidad = [
            row for row in workbook["Calidad de datos"].iter_rows(values_only=True)
        ]
        assert calidad[1][0] == "999"
        assert calidad[1][4] == "No es un móvil colombiano válido (3XXXXXXXXX)"


class TestThresholdSemantics:
    def test_sugerir_umbrales_maps_into_classify_slots(self):
        # Cortes 30/90 en ventana corta: Activo ≤ 30, Riesgo 31–90, Inactivo > 90.
        riesgo, inactivo = sugerir_umbrales(223)
        assert riesgo == 30 and inactivo == 90
        assert classify_segment(15, inactivity_days=riesgo, risk_days=inactivo) == (
            SEGMENT_ACTIVO
        )
        assert classify_segment(45, inactivity_days=riesgo, risk_days=inactivo) == (
            SEGMENT_RIESGO
        )
        assert classify_segment(120, inactivity_days=riesgo, risk_days=inactivo) == (
            SEGMENT_INACTIVO
        )
