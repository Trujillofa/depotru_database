"""Unit tests for the Monday cash pack orchestrator. Synthetic data only."""

from __future__ import annotations

import logging
from datetime import date
from email import message_from_bytes
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from business_analyzer.core.cartera_aging import build_report_from_rows
from business_analyzer.jobs import monday_cash_pack as mcp


def _cartera_snapshot_rows() -> list[dict]:
    return [
        {
            "cliente_uid": 1,
            "cliente_nit": "9001",
            "cliente_razon_social": "Cliente Alfa",
            "cliente_ciudad": "Neiva",
            "cliente_departamento": "Huila",
            "vendedor_nombre": "Ana Demo",
            "corriente": 0,
            "vencido": 2_500_000,
            "vencido_30": 0,
            "vencido_60": 0,
            "vencido_90": 0,
            "vencido_120": 2_500_000,
            "vencido_360": 0,
            "vencido_superior": 0,
            "total": 2_500_000,
            "dias_vencidos": 110,
            "cliente_cupo": 3_000_000,
            "fecha_carga": "2026-09-27 08:00:00",
        },
        {
            "cliente_uid": 2,
            "cliente_nit": "9002",
            "cliente_razon_social": "Cliente Beta",
            "cliente_ciudad": "Florencia",
            "cliente_departamento": "Caquetá",
            "vendedor_nombre": "Luis Demo",
            "corriente": 100_000,
            "vencido": 80_000,
            "vencido_30": 80_000,
            "vencido_60": 0,
            "vencido_90": 0,
            "vencido_120": 0,
            "vencido_360": 0,
            "vencido_superior": 0,
            "total": 180_000,
            "dias_vencidos": 18,
            "cliente_cupo": 400_000,
            "fecha_carga": "2026-09-27 08:00:00",
        },
    ]


def _product_margin_rows() -> list[dict]:
    return [
        {
            "product_name": "Impermeabilizante Demo SIKA",
            "sku": "SKU-DEMO-SIKA-1",
            "revenue": 1_000_000,
            "cost": 1_250_000,
            "quantity": 10,
            "proveedor": "SIKA COLOMBIA",
        },
        {
            "product_name": "Broca HSS 8mm Demo",
            "sku": "SKU-DEMO-002",
            "revenue": 400_000,
            "cost": 480_000,
            "quantity": 8,
        },
        {
            "product_name": "Cemento gris Demo",
            "sku": "SKU-DEMO-003",
            "revenue": 800_000,
            "cost": 500_000,
            "quantity": 20,
        },
    ]


@pytest.mark.unit
def test_last_completed_week_from_monday():
    start, end = mcp.last_completed_week(date(2026, 9, 28))
    assert start == date(2026, 9, 21)
    assert end == date(2026, 9, 27)


@pytest.mark.unit
def test_last_completed_week_from_wednesday():
    start, end = mcp.last_completed_week(date(2026, 9, 30))
    assert start == date(2026, 9, 21)
    assert end == date(2026, 9, 27)


@pytest.mark.unit
def test_rank_overdue_uses_cartera_helper_order():
    report = build_report_from_rows(
        _cartera_snapshot_rows(),
        as_of_date="2026-09-27",
        top_n=10,
        include_dso=False,
    )
    ranked = mcp.rank_overdue_receivables(report, top_n=10)
    assert [row.customer_name for row in ranked] == ["Cliente Alfa", "Cliente Beta"]
    assert ranked[0].overdue_amount == 2_500_000
    assert ranked[0].days_overdue == 110


@pytest.mark.unit
def test_select_negative_margin_skus_ranks_loss_and_flags_sika():
    rows = mcp.select_negative_margin_skus(_product_margin_rows(), top_n=10)
    assert [row.sku for row in rows] == ["SKU-DEMO-SIKA-1", "SKU-DEMO-002"]
    assert rows[0].is_sika is True
    assert rows[1].is_sika is False
    assert rows[0].profit == -250_000
    assert rows[0].margin_pct < 0


@pytest.mark.unit
def test_select_negative_margin_skus_ignores_positive_and_honors_top_n():
    rows = mcp.select_negative_margin_skus(_product_margin_rows(), top_n=1)
    assert len(rows) == 1
    assert rows[0].sku == "SKU-DEMO-SIKA-1"


@pytest.mark.unit
def test_kpi_highlights_use_manager_summary_helper():
    from business_analyzer.analysis.manager_report.aggregations import summary_from_sql

    summary = summary_from_sql(
        {
            "total_with_iva": 12_345_678,
            "total_without_iva": 10_000_000,
            "total_cost": 7_000_000,
            "total_quantity": 100,
            "order_count": 40,
        }
    )
    kpi = mcp.kpi_highlights_from_summary(
        summary,
        week_start=date(2026, 9, 21),
        week_end=date(2026, 9, 27),
    )
    assert kpi.revenue_with_iva == 12_345_678
    assert kpi.gross_profit == 3_000_000
    assert kpi.gross_margin_pct == 30.0


@pytest.mark.unit
def test_format_pack_numbers_colombian():
    overdue = mcp.rank_overdue_receivables(
        build_report_from_rows(
            _cartera_snapshot_rows(),
            as_of_date="2026-09-27",
            include_dso=False,
        ),
        top_n=5,
    )
    skus = mcp.select_negative_margin_skus(_product_margin_rows(), top_n=5)
    formatted = mcp.format_pack_numbers(overdue, skus)
    assert formatted["overdue"][0]["amount"] == "$2.500.000"
    assert formatted["overdue"][0]["days"] == "110"
    assert formatted["skus"][0]["profit"] == "-$250.000"
    assert mcp.format_number(-250_000, "Ganancia") == "-$250.000"
    assert "," in formatted["skus"][0]["margin"]
    assert formatted["skus"][0]["margin"].endswith("%")


@pytest.mark.unit
def test_render_email_html_spanish_and_format_number():
    pack = mcp.build_synthetic_pack(run_date=date(2026, 9, 29), top_n=5)
    html = mcp.render_email_html(pack)
    assert "Paquete de caja" in html
    assert "2026-09-29" in html
    assert "Cuentas por cobrar" in html
    assert "margen negativo" in html.lower()
    assert "SIKA" in html
    assert "$2.500.000" in html
    assert "45,6%" not in html  # fixture margin is not 45.6
    assert "no se envía" in html.lower() or "no se envio" in html.lower()
    assert "XY" in html and "ISC" in html
    assert "<script" not in html


@pytest.mark.unit
def test_html_escapes_injected_names():
    report = {
        "summary": {"Cartera_Total": 1, "Cartera_Vencida": 1},
        "top_overdue": [
            {
                "cliente_razon_social": "<Cliente Script>",
                "vendedor_nombre": "Ana",
                "vencido": 1000,
                "dias_vencidos": 5,
                "total": 1000,
            }
        ],
    }
    pack = mcp.build_pack(
        run_date=date(2026, 9, 29),
        as_of_date="2026-09-27",
        cartera_report=report,
        product_rows=[
            {
                "product_name": "SKU <demo>",
                "sku": "SKU-X",
                "revenue": 10,
                "cost": 20,
            }
        ],
        kpi_summary={
            "total_revenue_with_iva": 100,
            "total_revenue_without_iva": 80,
            "total_cost": 50,
            "gross_profit": 30,
            "gross_margin_pct": 37.5,
            "order_count": 2,
        },
        week_start=date(2026, 9, 21),
        week_end=date(2026, 9, 27),
    )
    html = mcp.render_email_html(pack)
    assert "<Cliente Script>" not in html
    assert "&lt;Cliente Script&gt;" in html
    assert "SKU &lt;demo&gt;" in html


@pytest.mark.unit
def test_write_draft_html_and_eml_does_not_send(tmp_path: Path):
    pack = mcp.build_synthetic_pack(run_date=date(2026, 9, 29), top_n=5)
    extra = tmp_path / "KPI_CONTROL_BOARD_2026_W39.md"
    extra.write_text("# KPI sintético\n", encoding="utf-8")
    pack.attachments.append(extra)

    with patch.object(mcp, "send_draft") as send_mock:
        result = mcp.write_draft(pack, tmp_path)
        send_mock.assert_not_called()

    assert result.html_path.is_file()
    assert result.eml_path.is_file()
    assert result.html_path.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")
    parsed = message_from_bytes(result.eml_path.read_bytes())
    assert "Paquete de caja" in parsed["Subject"]
    payload = result.eml_path.read_text(encoding="utf-8", errors="replace")
    assert "KPI_CONTROL_BOARD_2026_W39.md" in payload
    assert "Cliente Alfa" in payload


@pytest.mark.unit
def test_parse_args_send_defaults_off():
    args = mcp.parse_args([])
    assert args.send is False
    assert args.synthetic is False


@pytest.mark.unit
def test_parse_args_synthetic_and_send_flags():
    args = mcp.parse_args(["--synthetic", "--send", "--top-n", "3"])
    assert args.synthetic is True
    assert args.send is True
    assert args.top_n == 3


@pytest.mark.unit
def test_main_synthetic_writes_draft_without_sending(tmp_path: Path):
    with patch.object(mcp, "send_draft") as send_mock:
        code = mcp.main(
            [
                "--synthetic",
                "--output-dir",
                str(tmp_path),
                "--run-date",
                "2026-09-29",
            ]
        )
        send_mock.assert_not_called()
    assert code == 0
    htmls = list(tmp_path.glob("*.html"))
    emls = list(tmp_path.glob("*.eml"))
    assert len(htmls) == 1
    assert len(emls) == 1
    text = htmls[0].read_text(encoding="utf-8")
    assert "Cliente Alfa" in text
    assert "Impermeabilizante Demo SIKA" in text


@pytest.mark.unit
def test_main_send_without_smtp_does_not_send(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("MAIL_TO", raising=False)
    with patch("smtplib.SMTP") as smtp_cls:
        code = mcp.main(
            [
                "--synthetic",
                "--send",
                "--output-dir",
                str(tmp_path),
                "--run-date",
                "2026-09-29",
            ]
        )
        smtp_cls.assert_not_called()
    assert code == 1


@pytest.mark.unit
def test_send_draft_uses_settings_not_raw_env(tmp_path: Path):
    eml = tmp_path / "draft.eml"
    eml.write_bytes(b"From: a@example.test\nTo: b@example.test\n\nbody\n")
    settings = MagicMock()
    settings.SMTP_HOST = "smtp.example.test"
    settings.SMTP_PORT = 587
    settings.SMTP_USER = "placeholder_user"
    settings.SMTP_PASSWORD = "placeholder_password"
    settings.SMTP_USE_TLS = True
    settings.MAIL_FROM = "from@example.test"
    settings.MAIL_TO = "to@example.test"

    smtp = MagicMock()
    with patch("smtplib.SMTP") as smtp_cls:
        smtp_cls.return_value.__enter__.return_value = smtp
        mcp.send_draft(eml, settings)

    smtp_cls.assert_called_once_with("smtp.example.test", 587, timeout=30)
    smtp.starttls.assert_called_once()
    tls_kwargs = smtp.starttls.call_args.kwargs
    assert tls_kwargs["context"] is not None
    smtp.login.assert_called_once_with("placeholder_user", "placeholder_password")
    smtp.sendmail.assert_called_once()
    args = smtp.sendmail.call_args[0]
    assert args[0] == "from@example.test"
    assert args[1] == ["to@example.test"]


@pytest.mark.unit
def test_build_pack_composes_three_sections():
    pack = mcp.build_synthetic_pack(run_date=date(2026, 9, 29), top_n=5)
    assert pack.overdue
    assert pack.negative_skus
    assert pack.kpi.week_start == date(2026, 9, 21)
    assert any(row.is_sika for row in pack.negative_skus)


@pytest.mark.unit
def test_live_loaders_use_injected_callables(tmp_path: Path):
    report = build_report_from_rows(
        _cartera_snapshot_rows(),
        as_of_date="2026-09-27",
        include_dso=False,
    )
    sales = {
        "summary": {
            "total_with_iva": 5_000_000,
            "total_without_iva": 4_000_000,
            "total_cost": 3_000_000,
            "total_quantity": 50,
            "order_count": 12,
        },
        "product_margins": _product_margin_rows(),
    }
    kpi_md = tmp_path / "KPI_CONTROL_BOARD_2026_W39.md"

    def _kpi_writer(start: str, end: str, output: str) -> Path:
        path = Path(output)
        path.write_text(f"# KPI {start} {end}\n", encoding="utf-8")
        return path

    pack = mcp.build_live_pack(
        run_date=date(2026, 9, 29),
        as_of_date="2026-09-27",
        top_n=5,
        output_dir=tmp_path,
        cartera_loader=lambda _as_of, _top_n: report,
        sales_loader=lambda _start, _end: sales,
        kpi_writer=_kpi_writer,
        attachment_writer=lambda _report, _out: [kpi_md],
    )
    assert pack.overdue[0].customer_name == "Cliente Alfa"
    assert pack.negative_skus[0].is_sika is True
    assert pack.kpi.revenue_with_iva == 5_000_000
    assert any(path.name.startswith("KPI_") for path in pack.attachments)


@pytest.mark.unit
def test_optional_sika_json_uses_existing_generator(tmp_path: Path):
    json_path = tmp_path / "sika_analysis_report.json"
    json_path.write_text(
        '{"generated_at":"2026-09-29","filter":"SIKA",'
        '"summary":{"2024":{"net_revenue":100},"2025":{"net_revenue":120}}}',
        encoding="utf-8",
    )
    out = tmp_path / "REPORTE_SIKA_ESPANOL.md"
    path = mcp.render_sika_markdown(json_path, out)
    assert path == out
    text = out.read_text(encoding="utf-8")
    assert "PRODUCTOS SIKA" in text
    assert "20.0%" in text or "+20" in text


@pytest.mark.unit
def test_print_schedule_mentions_bogota_and_no_send():
    line = mcp.schedule_line()
    jobs = [
        raw
        for raw in line.splitlines()
        if raw.strip() and not raw.lstrip().startswith("#")
    ]
    command = jobs[-1]
    assert "CRON_TZ=America/Bogota" in line
    assert " TZ=" not in command
    assert not command.startswith("TZ=")
    assert "08:45" in line or " 8 " in command
    assert "America/Bogota" in line
    assert "--send" not in command


@pytest.mark.unit
def test_main_print_schedule_exits_zero(capsys):
    assert mcp.main(["--print-schedule"]) == 0
    command = capsys.readouterr().out.splitlines()[-1]
    assert "--send" not in command


@pytest.mark.unit
def test_main_synthetic_sika_json_attaches_markdown(tmp_path: Path):
    json_path = tmp_path / "sika_analysis_report.json"
    json_path.write_text(
        '{"generated_at":"2026-09-29","filter":"SIKA",'
        '"summary":{"2024":{"net_revenue":50},"2025":{"net_revenue":50}}}',
        encoding="utf-8",
    )
    code = mcp.main(
        [
            "--synthetic",
            "--output-dir",
            str(tmp_path),
            "--run-date",
            "2026-09-29",
            "--sika-json",
            str(json_path),
        ]
    )
    assert code == 0
    assert (tmp_path / "REPORTE_SIKA_ESPANOL.md").is_file()


@pytest.mark.unit
def test_rank_overdue_falls_back_to_cartera_helper():
    from business_analyzer.core.cartera_aging import aggregate_clients

    clients = aggregate_clients(_cartera_snapshot_rows())
    ranked = mcp.rank_overdue_receivables({"clients": clients}, top_n=1)
    assert ranked[0].customer_name == "Cliente Alfa"


@pytest.mark.unit
def test_empty_sections_render_spanish_placeholders(tmp_path: Path):
    pack = mcp.build_pack(
        run_date=date(2026, 9, 29),
        as_of_date="2026-09-27",
        cartera_report={"summary": {}, "top_overdue": []},
        product_rows=[],
        kpi_summary={
            "total_revenue_with_iva": 0,
            "total_revenue_without_iva": 0,
            "total_cost": 0,
            "gross_profit": 0,
            "gross_margin_pct": 0,
            "order_count": 0,
        },
        week_start=date(2026, 9, 21),
        week_end=date(2026, 9, 27),
        attachments=[tmp_path / "missing-attachment.bin"],
    )
    html = mcp.render_email_html(pack)
    assert "Sin cuentas vencidas" in html
    assert "Sin SKUs con margen negativo" in html
    result = mcp.write_draft(pack, tmp_path)
    payload = result.eml_path.read_text(encoding="utf-8", errors="replace")
    assert 'filename="missing-attachment.bin"' not in payload
    assert "Sin adjuntos adicionales" in payload


@pytest.mark.unit
def test_send_draft_requires_mail_to(tmp_path: Path):
    eml = tmp_path / "draft.eml"
    eml.write_bytes(b"From: a@example.test\n\nbody\n")
    settings = MagicMock()
    settings.SMTP_HOST = "smtp.example.test"
    settings.SMTP_PORT = 587
    settings.MAIL_TO = ""
    settings.MAIL_FROM = None
    settings.SMTP_USER = None
    with patch("smtplib.SMTP") as smtp_cls:
        with pytest.raises(RuntimeError, match="MAIL_TO"):
            mcp.send_draft(eml, settings)
        smtp_cls.assert_not_called()


@pytest.mark.unit
def test_default_loaders_are_delegates():
    fake_report = {"top_overdue": []}
    with patch("business_analyzer.core.cartera_aging.CarteraAgingRunner") as runner_cls:
        runner_cls.return_value.build_report.return_value = fake_report
        assert mcp.default_cartera_loader("2026-09-27", 5) == fake_report

    with patch(
        "business_analyzer.analysis.manager_report.queries.SalesQueryRunner"
    ) as sales_cls:
        sales_cls.return_value.fetch_sql_aggregations.return_value = {"summary": {}}
        assert mcp.default_sales_loader("2026-09-21", "2026-09-27")["summary"] == {}

    with patch.object(mcp, "_load_script_attr", return_value=lambda **_k: Path("x.md")):
        assert mcp.default_kpi_writer("2026-09-21", "2026-09-27", "x.md") == Path(
            "x.md"
        )


@pytest.mark.unit
def test_default_attachment_writer_writes_html(tmp_path: Path):
    report = build_report_from_rows(
        _cartera_snapshot_rows(),
        as_of_date="2026-09-27",
        include_dso=False,
    )
    paths = mcp.default_attachment_writer(report, tmp_path)
    assert paths
    assert paths[0].suffix == ".html"
    assert paths[0].is_file()


@pytest.mark.unit
def test_build_live_pack_skips_failed_kpi_writer(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    report = build_report_from_rows(
        _cartera_snapshot_rows(),
        as_of_date="2026-09-27",
        include_dso=False,
    )

    def _boom(_start: str, _end: str, _output: str) -> Path:
        raise RuntimeError("kpi unavailable")

    with caplog.at_level(logging.WARNING):
        pack = mcp.build_live_pack(
            run_date=date(2026, 9, 29),
            as_of_date="2026-09-27",
            top_n=5,
            output_dir=tmp_path,
            cartera_loader=lambda _as_of, _top_n: report,
            sales_loader=lambda _start, _end: {
                "summary": {
                    "total_with_iva": 1,
                    "total_without_iva": 1,
                    "total_cost": 1,
                    "total_quantity": 1,
                    "order_count": 1,
                },
                "product_margins": [],
            },
            kpi_writer=_boom,
            attachment_writer=lambda _report, _out: [],
        )
    assert pack.kpi.order_count == 1
    assert pack.attachments == []
    assert "KPI" in caplog.text
    assert "kpi unavailable" in caplog.text


@pytest.mark.unit
def test_load_script_attr_and_repo_root():
    root = mcp._repo_root()
    assert (root / "scripts/analysis/generate_sika_report.py").is_file()
    generate = mcp._load_script_attr(
        "scripts/analysis/generate_sika_report.py", "generate_report"
    )
    assert callable(generate)


@pytest.mark.unit
def test_systemd_unit_never_sends():
    repo = Path(__file__).resolve().parents[2]
    service = (repo / "deploy/systemd/depotru-monday-cash-pack.service").read_text(
        encoding="utf-8"
    )
    timer = (repo / "deploy/systemd/depotru-monday-cash-pack.timer").read_text(
        encoding="utf-8"
    )
    exec_line = next(
        raw for raw in service.splitlines() if raw.startswith("ExecStart=")
    )
    assert "--send" not in exec_line
    assert "OnCalendar=Mon *-*-* 08:45:00 America/Bogota" in timer
    cron = (repo / "deploy/depotru-schedule.cron.example").read_text(encoding="utf-8")
    assert "CRON_TZ=America/Bogota" in cron
    assert "TZ=America/Bogota cd" not in cron


@pytest.mark.unit
def test_send_draft_without_tls_or_user(tmp_path: Path):
    eml = tmp_path / "draft.eml"
    eml.write_bytes(b"From: a@example.test\nTo: b@example.test\n\nbody\n")
    settings = MagicMock()
    settings.SMTP_HOST = "smtp.example.test"
    settings.SMTP_PORT = 25
    settings.SMTP_USER = None
    settings.SMTP_PASSWORD = None
    settings.SMTP_USE_TLS = False
    settings.MAIL_FROM = "from@example.test"
    settings.MAIL_TO = "one@example.test, two@example.test"
    smtp = MagicMock()
    with patch("smtplib.SMTP") as smtp_cls:
        smtp_cls.return_value.__enter__.return_value = smtp
        mcp.send_draft(eml, settings)
    smtp.starttls.assert_not_called()
    smtp.login.assert_not_called()
    assert smtp.sendmail.call_args[0][1] == ["one@example.test", "two@example.test"]


@pytest.mark.unit
def test_default_attachment_writer_skips_failed_pdf(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    report = build_report_from_rows(
        _cartera_snapshot_rows(),
        as_of_date="2026-09-27",
        include_dso=False,
    )
    with patch(
        "business_analyzer.reports.cartera_pdf.write_cartera_pdf",
        side_effect=RuntimeError("pdf fail"),
    ):
        with caplog.at_level(logging.WARNING):
            paths = mcp.default_attachment_writer(report, tmp_path)
    assert len(paths) == 1
    assert paths[0].suffix == ".html"
    assert "PDF" in caplog.text
    assert "pdf fail" in caplog.text


@pytest.mark.unit
def test_main_default_output_dir_uses_settings(tmp_path: Path):
    pack = mcp.build_synthetic_pack(run_date=date(2026, 9, 29), top_n=2)
    with patch(
        "business_analyzer.core.config.Config.ensure_output_dir",
        return_value=tmp_path,
    ):
        with patch.object(mcp, "build_synthetic_pack", return_value=pack):
            code = mcp.main(["--synthetic", "--run-date", "2026-09-29"])
    assert code == 0
    out = tmp_path / "monday_cash_pack"
    assert list(out.glob("*.eml"))


@pytest.mark.unit
def test_send_draft_reads_settings_when_omitted(tmp_path: Path):
    eml = tmp_path / "draft.eml"
    eml.write_bytes(b"From: a@example.test\nTo: b@example.test\n\nbody\n")
    settings = MagicMock()
    settings.SMTP_HOST = "smtp.example.test"
    settings.SMTP_PORT = 587
    settings.SMTP_USER = None
    settings.SMTP_PASSWORD = None
    settings.SMTP_USE_TLS = False
    settings.MAIL_FROM = "from@example.test"
    settings.MAIL_TO = "to@example.test"
    smtp = MagicMock()
    with patch.object(mcp, "get_settings", return_value=settings):
        with patch("smtplib.SMTP") as smtp_cls:
            smtp_cls.return_value.__enter__.return_value = smtp
            mcp.send_draft(eml)
    smtp.sendmail.assert_called_once()


@pytest.mark.unit
def test_main_send_success(tmp_path: Path):
    with patch.object(mcp, "send_draft") as send_mock:
        code = mcp.main(
            [
                "--synthetic",
                "--send",
                "--output-dir",
                str(tmp_path),
                "--run-date",
                "2026-09-29",
            ]
        )
        send_mock.assert_called_once()
    assert code == 0


@pytest.mark.unit
def test_is_sika_from_sku_or_marca():
    assert mcp.is_sika_product({"sku": "SIKA-1", "product_name": "Sellador"})
    assert mcp.is_sika_product({"marca": "Sika", "product_name": "Sellador"})
    assert not mcp.is_sika_product({"product_name": "Cemento gris Demo", "sku": "X"})


@pytest.mark.unit
def test_is_sika_from_proveedor_when_name_and_sku_have_no_sika():
    """Live product_margins now selects proveedor; vendor-only match must work."""
    row = {
        "product_name": "Impermeabilizante Demo",
        "sku": "SKU-DEMO-004",
        "revenue": 100_000,
        "cost": 150_000,
        "proveedor": "SIKA COLOMBIA",
    }
    assert mcp.is_sika_product(row) is True
    selected = mcp.select_negative_margin_skus([row], top_n=5)
    assert selected[0].is_sika is True
    assert selected[0].sku == "SKU-DEMO-004"


@pytest.mark.unit
def test_normalize_kpi_summary_accepts_raw_and_normalized():
    raw = mcp.normalize_kpi_summary(
        {
            "total_with_iva": 100.0,
            "total_without_iva": 80.0,
            "total_cost": 50.0,
            "order_count": 2,
        }
    )
    assert raw["gross_profit"] == 30.0
    assert raw["gross_margin_pct"] == 37.5
    already = {
        "total_revenue_with_iva": 9,
        "total_revenue_without_iva": 8,
        "gross_profit": 3,
    }
    assert mcp.normalize_kpi_summary(already)["total_revenue_with_iva"] == 9


@pytest.mark.unit
def test_synthetic_pack_has_demo_totals_without_cartera_import():
    pack = mcp.build_synthetic_pack(run_date=date(2026, 9, 29), top_n=5)
    assert pack.cartera_summary["Cartera_Total"] == 2_680_000
    assert pack.overdue[0].customer_name == "Cliente Alfa"
    assert pack.kpi.gross_margin_pct == 30.0


@pytest.mark.unit
def test_format_number_raises_if_loader_missing():
    previous = mcp._FORMAT_NUMBER
    mcp._FORMAT_NUMBER = None
    try:
        with patch("importlib.util.spec_from_file_location", return_value=None):
            with pytest.raises(ImportError, match="No se pudo cargar"):
                mcp.format_number(1, "TotalMasIva")
        fake = MagicMock()
        fake.loader = None
        mcp._FORMAT_NUMBER = None
        with patch("importlib.util.spec_from_file_location", return_value=fake):
            with pytest.raises(ImportError, match="No se pudo cargar"):
                mcp.format_number(1, "TotalMasIva")
    finally:
        mcp._FORMAT_NUMBER = previous


@pytest.mark.unit
def test_load_script_attr_raises_if_loader_missing():
    with patch("importlib.util.spec_from_file_location", return_value=None):
        with pytest.raises(ImportError, match="No se pudo cargar"):
            mcp._load_script_attr(
                "scripts/analysis/generate_sika_report.py", "generate_report"
            )


@pytest.mark.unit
def test_repo_root_fallback_when_script_missing(monkeypatch):
    here = Path(mcp.__file__).resolve()
    monkeypatch.setattr(Path, "is_file", lambda _self: False)
    assert mcp._repo_root() == here.parents[3]


@pytest.mark.unit
def test_write_draft_uses_settings_from_to(tmp_path: Path):
    pack = mcp.build_synthetic_pack(run_date=date(2026, 9, 29), top_n=2)
    settings = MagicMock()
    settings.MAIL_FROM = "from@example.test"
    settings.MAIL_TO = "to@example.test"
    result = mcp.write_draft(pack, tmp_path, settings=settings)
    parsed = message_from_bytes(result.eml_path.read_bytes())
    assert parsed["From"] == "from@example.test"
    assert parsed["To"] == "to@example.test"


@pytest.mark.unit
def test_main_live_uses_build_live_pack(tmp_path: Path):
    pack = mcp.build_synthetic_pack(run_date=date(2026, 9, 29), top_n=3)
    with patch.object(mcp, "build_live_pack", return_value=pack) as live:
        code = mcp.main(
            [
                "--output-dir",
                str(tmp_path),
                "--run-date",
                "2026-09-29",
                "--as-of-date",
                "2026-09-27",
            ]
        )
        live.assert_called_once()
    assert code == 0
    assert list(tmp_path.glob("*.eml"))
