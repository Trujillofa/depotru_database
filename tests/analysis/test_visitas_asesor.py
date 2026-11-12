"""Tests for the asesor visit planner helpers (post-audit)."""

import datetime as dt

from business_analyzer.analysis.sika_impact import (
    SEGMENT_ACTIVO,
    SEGMENT_INACTIVO,
    SEGMENT_RIESGO,
)
from business_analyzer.analysis.visitas_asesor import (
    AGENDA_LLAMADA,
    AGENDA_VISITA,
    CAP_DIAS_PRESENCIAL,
    CATEGORIA_CRONOGRAMA,
    VisitScheduler,
    build_client_base,
    build_visita_id,
    export_xlsx,
    filter_prospectos_existentes,
    holiday_shortfall,
    month_label,
    normalize_name,
    parse_barrios,
    parse_cronograma_clients,
    parse_prospectos,
    schedule_programs,
    spillover_working_dates,
    weekday_dates,
)
from business_analyzer.analysis.visitas_asesor_cli import resolve_months

TODAY = dt.date(2026, 9, 3)
# Ventana multi-anual como el histórico real de banco_datos.
INICIO = dt.date(2020, 1, 23)


class TestFechas:
    def test_month_label(self):
        assert month_label(2026, 9) == "SEP"

    def test_weekday_dates_start_from(self):
        dates = weekday_dates(2026, 9, start_from=TODAY)
        assert dates[0] == dt.date(2026, 9, 3)
        assert all(date.weekday() < 5 for date in dates)

    def test_weekday_dates_skips_colombian_holidays(self):
        october = weekday_dates(2026, 10)
        assert dt.date(2026, 10, 12) not in october  # Día de la Raza
        assert dt.date(2026, 10, 13) in october
        skipped = weekday_dates(2026, 10, skip_holidays=False)
        assert dt.date(2026, 10, 12) in skipped

    def test_holiday_shortfall_rolls_into_next_month(self):
        assert holiday_shortfall(2026, 10) == 1
        assert spillover_working_dates(2026, 10, 1) == [dt.date(2026, 11, 3)]

    def test_resolve_months_default_and_explicit(self):
        assert resolve_months(None, TODAY) == [(2026, 9), (2026, 10)]
        assert resolve_months("2026-10,2026-11", TODAY) == [(2026, 10), (2026, 11)]


class TestParsing:
    def test_normalize_name(self):
        assert normalize_name("  ferretería   la   paz ") == "FERRETERÍA LA PAZ"

    def test_parse_prospectos_ignores_header_cells(self):
        rows_by_category = {
            "VIDRIERIA": [
                ("NOMBRE COMERCIAL", "CELULAR"),
                ("VIDRIOS FERMARR", 3134311290),
                ("CELULAR", "X"),
            ],
            "ACEROS": [("NOMBRE COMERCIAL", "CELULAR")],
        }
        prospectos = parse_prospectos(rows_by_category)
        assert prospectos["VIDRIERIA"] == [
            {"nombre": "VIDRIOS FERMARR", "celular": "3134311290"}
        ]
        assert prospectos["ACEROS"] == []

    def test_parse_cronograma_all_layouts(self):
        rows = [
            ("FECHA", "NOMBRE DEL CLIENTE", "FERRETERIA", "NIT - CC"),
            (dt.datetime(2026, 3, 1), "GRUPO CORPEZ", None, None),
            (None, "MARIA JOSE ALMARIO", 1137674107, "FERRETODO FLORENCIA"),
            (None, 7718944, "HERNANDO PEREZ MONTES", None),
            (None, "MARIA JOSE ALMARIO", 1137674107, None),
        ]
        clients = parse_cronograma_clients(rows)
        assert len(clients) == 3
        by_name = {normalize_name(c["cliente"]): c for c in clients}
        assert by_name["HERNANDO PEREZ MONTES"]["nit"] == "7718944"

    def test_parse_barrios(self):
        rows = [
            ("PROGRAMACION MENSUAL DE VISITAS",),
            ("No.", "NOMBRE CLIENTE", "FERRETERIA", "FECHA DE VISITA"),
            (1, "ZONA NORTE", "LA PAZ", "x"),
            (1, "ENTREGAS", "ZONA NORTE FLORENCIA", "x"),
            (2, "ZONA NORTE", "LA PAZ", "x"),
        ]
        assert parse_barrios(rows) == ["LA PAZ"]


def _history_row(
    nit,
    cliente,
    facturacion,
    fact_12m,
    dias_sin_compra,
    ganancia=None,
):
    ultima = TODAY - dt.timedelta(days=dias_sin_compra)
    return {
        "terceros_id": 1,
        "nit": nit,
        "cliente": cliente,
        "primera_compra": INICIO,
        "ultima_compra": ultima,
        "cantidad": 10,
        "facturacion": facturacion,
        "facturacion_12m": fact_12m,
        "ganancia": ganancia if ganancia is not None else facturacion * 0.25,
        "dias_compra": 4,
    }


def _contact(celular="3001112233", ciudad="FLORENCIA CAQ", email="a@b.co"):
    return {
        "cliente": "",
        "celular": celular,
        "telefono": "6084645976",
        "direccion": "CRA 7 #2-80",
        "ciudad": ciudad,
        "email": email,
    }


def _contacts_for(history):
    return {row["nit"]: _contact(email=f"{row['nit']}@mail.co") for row in history}


class TestClientBase:
    def test_base_has_score_agenda_and_validated_movil(self):
        history = [
            _history_row("111", "ACTIVO", 12000000, 12000000, 10),
            _history_row("222", "RIESGO", 9000000, 3000000, 120),
            _history_row("333", "INACTIVO LEJANO", 8000000, 0, 700),
        ]
        contacts = {
            "111": _contact(email="a@b.co"),
            "222": _contact(email="b@b.co"),
            "333": _contact(email="c@b.co"),
        }
        base = build_client_base(history, contacts, hoy=TODAY)
        assert len(base) == 3
        by_nit = {row["nit"]: row for row in base}
        assert by_nit["111"]["agenda"] == AGENDA_VISITA
        assert by_nit["333"]["agenda"] == AGENDA_LLAMADA  # > CAP_DIAS_PRESENCIAL
        assert by_nit["111"]["movil"] == "3001112233"
        assert by_nit["111"]["canal_preferido"] == "WhatsApp"
        assert by_nit["111"]["email"] == "a@b.co"
        assert by_nit["111"]["facturacion_12m"] == 12000000
        # Orden por score (valor × recencia), no por un solo campo monetario.
        assert base[0]["nit"] == "111"

    def test_score_combina_valor_y_recencia(self):
        # Un inactivo de alto valor histórico no supera a un activo que
        # factura lo mismo cada mes (recencia penaliza).
        history = [
            _history_row("111", "ACTIVO", 6000000, 6000000, 5),
            _history_row("222", "INACTIVO", 90000000, 0, 700),
        ]
        contacts = {"111": _contact(), "222": _contact()}
        base = build_client_base(history, contacts, hoy=TODAY)
        by_nit = {row["nit"]: row for row in base}
        assert by_nit["111"]["score"] > by_nit["222"]["score"]

    def test_contactos_sin_florencia_quedan_fuera(self):
        history = [_history_row("444", "OTRA CIUDAD", 8000000, 0, 10)]
        base = build_client_base(history, {}, hoy=TODAY)
        assert base == []

    def test_movil_recuperado_de_telefono(self):
        history = [_history_row("555", "CELULAR VACIO", 1000000, 0, 20)]
        contacts = {"555": _contact(celular="", ciudad="FLORENCIA CAQ")}
        contacts["555"]["telefono"] = "3124789022"
        base = build_client_base(history, contacts, hoy=TODAY)
        assert base[0]["movil"] == "3124789022"

    def test_ciudad_cau_se_corrige_y_queda_en_calidad(self):
        history = [_history_row("666", "CAU", 1000000, 0, 20)]
        contacts = {"666": _contact(ciudad="FLORENCIA CAU")}
        issues = []
        base = build_client_base(history, contacts, hoy=TODAY, issues=issues)
        assert base[0]["ciudad"] == "FLORENCIA CAQ"
        assert any(issue["campo"] == "Ciudad" for issue in issues)


class TestProspectosCruce:
    def test_filter_quita_clientes_de_base_y_deduplica(self):
        prospectos = {
            CATEGORIA_CRONOGRAMA: [
                {"nombre": "MILLER MUÑOZ SILVA", "celular": ""},
                {"nombre": "VIDRIO NUEVO SAS", "celular": "3001112233"},
                {"nombre": "OTRO PROSPECTO", "celular": "3183607163"},
            ],
            "CONSTRUCTORA": [
                {"nombre": "SINERGIA CONSTRUCTORA ZOMAC S.A.S", "celular": "311"},
                {"nombre": "SINERGIA CONSTRUCTORA ZOMAC S.A.S", "celular": "311"},
                {"nombre": "FERRETERIA NUEVA", "celular": "3183607163"},
            ],
        }
        known = ["MILLER MUNOZ SILVA", "SINERGIA CONSTRUCTORA ZOMAC S.A.S"]
        filtered, excluidos = filter_prospectos_existentes(prospectos, known)
        names = [entry["nombre"] for rows in filtered.values() for entry in rows]
        assert "VIDRIO NUEVO SAS" in names
        assert "MILLER MUÑOZ SILVA" not in names
        assert all("SINERGIA" not in name for name in names)
        # Same cellphone kept once (first remaining prospect).
        assert sum(1 for name in names if name == "FERRETERIA NUEVA") == 0
        motivos = {entry["nombre"]: entry["motivo"] for entry in excluidos}
        assert "MILLER" in next(n for n in motivos if "MILLER" in n)
        assert any("BASE DE CLIENTES" in m for m in motivos.values())
        assert motivos["FERRETERIA NUEVA"].startswith("Prospecto duplicado")
        assert motivos["SINERGIA CONSTRUCTORA ZOMAC S.A.S"].startswith(
            "Ya está en BASE"
        )


class TestScheduler:
    def _clients(self):
        history = (
            [
                _history_row(f"R{i}", f"RIESGO {i}", 500000, 400000, 100 + i)
                for i in range(3)
            ]
            + [
                _history_row(f"I{i}", f"INACTIVO {i}", 900000, 0, 200 + i)
                for i in range(2)
            ]
            + [
                _history_row(f"A{i}", f"ACTIVO {i}", 800000, 700000, 10 + i)
                for i in range(5)
            ]
        )
        contacts = _contacts_for(history)
        return build_client_base(history, contacts, hoy=TODAY)

    def test_mezcla_diaria_por_segmento(self):
        scheduler = VisitScheduler(self._clients())
        days = [dt.date(2026, 9, 7)]
        program = scheduler.schedule_month(days, visitas_por_dia=4)
        segments = [
            (
                SEGMENT_RIESGO
                if row["nit"].startswith("R")
                else SEGMENT_INACTIVO if row["nit"].startswith("I") else SEGMENT_ACTIVO
            )
            for row in program
        ]
        # 2 en riesgo + 1 inactivo + 1 activo (auditoría V-2).
        assert segments.count(SEGMENT_RIESGO) == 2
        assert segments.count(SEGMENT_INACTIVO) == 1
        assert segments.count(SEGMENT_ACTIVO) == 1

    def test_cursor_continua_entre_meses_sin_repetir(self):
        scheduler = VisitScheduler(self._clients())
        sept = scheduler.schedule_month(
            [dt.date(2026, 9, day) for day in (7, 8)], visitas_por_dia=4
        )
        october = scheduler.schedule_month(
            [dt.date(2026, 10, day) for day in (1, 2)], visitas_por_dia=4
        )
        nits_sept = [row["nit"] for row in sept]
        nits_oct = [row["nit"] for row in october]
        # V-1: octubre NO repite a septiembre; el cursor avanzó.
        assert nits_oct, "octubre quedó vacío: cursor no avanzó"
        assert not set(nits_sept) & set(nits_oct)
        total_programados = len(set(nits_sept) | set(nits_oct))
        assert total_programados == len(sept) + len(october)

    def test_agenda_llamada_no_recibe_visita(self):
        history = [_history_row("L1", "LEJANO", 9000000, 0, CAP_DIAS_PRESENCIAL + 10)]
        contacts = {"L1": _contact()}
        base = build_client_base(history, contacts, hoy=TODAY)
        scheduler = VisitScheduler(base)
        program = scheduler.schedule_month([dt.date(2026, 9, 7)], visitas_por_dia=4)
        assert program == []

    def test_build_visita_id_estable(self):
        visita_id = build_visita_id("Armando Jose", dt.date(2026, 9, 7), "123", 1)
        assert visita_id == "ARMANDOJ-20260907-123"
        assert (
            build_visita_id("Armando Jose", dt.date(2026, 9, 7), "", 3)
            == "ARMANDOJ-20260907-IDX3"
        )

    def test_holiday_rollover_keeps_cursor_head(self):
        history = (
            [
                _history_row(f"R{i}", f"RIESGO {i}", 500000, 400000, 100 + i)
                for i in range(40)
            ]
            + [
                _history_row(f"I{i}", f"INACTIVO {i}", 900000, 0, 200 + i)
                for i in range(30)
            ]
            + [
                _history_row(f"A{i}", f"ACTIVO {i}", 800000, 700000, 10 + i)
                for i in range(40)
            ]
        )
        contacts = _contacts_for(history)
        clients = build_client_base(history, contacts, hoy=TODAY)
        programs = schedule_programs(
            clients,
            [(2026, 10)],
            today=dt.date(2026, 9, 3),
            visitas_por_dia=4,
        )
        labels = [label for label, _ in programs]
        assert "OCT-2026" in labels
        assert "NOV-2026" in labels
        october = dict(programs)["OCT-2026"]
        november = dict(programs)["NOV-2026"]
        assert dt.date(2026, 10, 12) not in [row["fecha"] for row in october]
        assert len(november) == 4
        assert november[0]["fecha"] == dt.date(2026, 11, 3)
        assert not {row["nit"] for row in october} & {row["nit"] for row in november}

    def test_consumidor_final_fuera_de_base(self):
        history = [
            _history_row("222222222222", "CONSUMIDOR FINAL", 9999999, 0, 2),
            _history_row("111", "ACTIVO", 1000000, 500000, 10),
        ]
        contacts = _contacts_for(history)
        base = build_client_base(history, contacts, hoy=TODAY)
        assert [row["nit"] for row in base] == ["111"]


class TestExport:
    def test_export_full_workbook(self, tmp_path):
        history = (
            [
                _history_row(f"R{i}", f"RIESGO {i}", 500000, 400000, 100 + i)
                for i in range(3)
            ]
            + [
                _history_row(f"I{i}", f"INACTIVO {i}", 900000, 0, 200 + i)
                for i in range(2)
            ]
            + [
                _history_row(f"A{i}", f"ACTIVO {i}", 800000, 700000, 10 + i)
                for i in range(5)
            ]
            + [_history_row("L1", "LEJANO", 9000000, 0, 700)]
        )
        contacts = _contacts_for(history)
        base = build_client_base(history, contacts, hoy=TODAY)

        scheduler = VisitScheduler(base)
        sep = scheduler.schedule_month(
            [dt.date(2026, 9, day) for day in (7, 8)], visitas_por_dia=4
        )
        october = scheduler.schedule_month(
            [dt.date(2026, 10, day) for day in (1, 2)], visitas_por_dia=4
        )

        output = tmp_path / "visitas.xlsx"
        export_xlsx(
            str(output),
            asesor="ARMANDO JOSE",
            client_base=base,
            programs=[("SEP-2026", sep), ("OCT-2026", october)],
            prospectos={
                "VIDRIERIA": [{"nombre": "VIDRIOS X", "celular": "311"}],
                CATEGORIA_CRONOGRAMA: [{"nombre": "PROSPECTO MANUAL", "celular": ""}],
            },
            barrios=["LA PAZ", "CUNDUY"],
            ciudad="FLORENCIA",
            hoy=TODAY,
        )
        assert output.exists()

        import openpyxl

        workbook = openpyxl.load_workbook(output)
        assert workbook.sheetnames == [
            "BASE DE CLIENTES",
            "PROGRAMACION SEP-2026",
            "PROGRAMACION OCT-2026",
            "CONTROL DE VISITAS",
            "RUTERO",
            "PROSPECTOS",
            "ZONAS",
            "Calidad de datos",
        ]

        # V-5: la fecha es una fecha real, no texto.
        sep_sheet = workbook["PROGRAMACION SEP-2026"]
        fecha_cell = sep_sheet.cell(4, 1).value
        assert isinstance(fecha_cell, dt.datetime)
        assert fecha_cell.date() == dt.date(2026, 9, 7)
        # V-3: el programa lleva móvil validado.
        movil_col = 7
        assert sep_sheet.cell(4, movil_col).value == "3001112233"

        # V-1: octubre no repite los NIT de septiembre.
        oct_sheet = workbook["PROGRAMACION OCT-2026"]
        nits = lambda sheet, col, n: [  # noqa: E731
            sheet.cell(row, col).value for row in range(4, 4 + n)
        ]
        sep_nits = set(nits(sep_sheet, 4, len(sep)))
        oct_nits = set(nits(oct_sheet, 4, len(october)))
        assert not sep_nits & oct_nits

        # V-11: control con ID estable y validaciones.
        control = workbook["CONTROL DE VISITAS"]
        headers = [cell.value for cell in control[3]]
        assert headers[0] == "ID visita"
        assert control.cell(4, 1).value.startswith("ARMANDOJ-")
        validations = {
            str(dv.sqref): dv for dv in control.data_validations.dataValidation
        }
        assert any("Efectiva" in dv.formula1 for dv in validations.values())
        assert any(dv.type == "decimal" for dv in validations.values())

        # V-10: prospectos planos por categoría + barrios en ZONAS.
        prospect_sheet = workbook["PROSPECTOS"]
        prospect_rows = list(prospect_sheet.iter_rows(values_only=True))
        categorias = {
            row[0]
            for row in prospect_rows
            if row[0] in ("VIDRIERIA", CATEGORIA_CRONOGRAMA)
        }
        assert categorias == {"VIDRIERIA", CATEGORIA_CRONOGRAMA}
        assert any(
            dv.type == "list" and "Sí" in dv.formula1
            for dv in prospect_sheet.data_validations.dataValidation
        )
        zonas = list(workbook["ZONAS"].iter_rows(values_only=True))
        assert any(row and row[0] == "LA PAZ" for row in zonas)

        # BASE: columnas nuevas.
        base_sheet = workbook["BASE DE CLIENTES"]
        base_headers = [cell.value for cell in base_sheet[3]]
        assert "Agenda" in base_headers
        assert "Score prioridad" in base_headers
        assert "Score prioridad ($/mes)" not in base_headers
        assert "Móvil (validado)" in base_headers
        assert any(
            row and row[0] == "(sin incidencias detectadas)"
            for row in workbook["Calidad de datos"].iter_rows(values_only=True)
        )
