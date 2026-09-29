# Monday cash pack

**Issue:** [Phase 3 / #65](https://github.com/Trujillofa/depotru_database/issues/65) (part A)
**CLI:** `depotru-monday-cash`
**Code:** `business_analyzer.jobs.monday_cash_pack`

Weekly ops pack for Monday morning. It **reuses existing reports** (no new sales SQL):

1. Overdue receivables ranked by amount and days (`CarteraAgingRunner` / `run_cartera_aging.py`).
2. Negative-margin SKU alert, with SIKA flagged from manager-report `product_margins` (`SalesQueryRunner.fetch_sql_aggregations`). Optional attachment via the existing `scripts/analysis/generate_sika_report.py` converter (`--sika-json`).
3. Weekly KPI board (`scripts/utils/generate_kpi_control_board.py` / last completed Mon–Sun week).

Output is a Spanish (Colombian) HTML body plus an `.eml` draft. Existing cartera HTML/PDF and the KPI markdown are attached when the live path generates them.

## Never sends by default

The job writes a **draft/preview** only. `--send` is off unless you pass it. The systemd unit and the documented cron line **do not** include `--send`.

Sending uses optional SMTP fields on the existing pydantic `Settings` (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_USE_TLS`, `MAIL_FROM`, `MAIL_TO`). There are no new raw `os.getenv` reads. If SMTP is missing, `--send` fails and nothing is mailed.

## How to run locally (synthetic, no DB)

```bash
PYTHONPATH=src python scripts/reports/run_monday_cash_pack.py \
  --synthetic --output-dir /tmp/monday_cash_pack --run-date 2026-09-29

# or
depotru-monday-cash --synthetic --output-dir /tmp/monday_cash_pack
```

Fixtures use names like `Cliente Alfa` / `SKU-DEMO-SIKA-1` only. Inspect `/tmp/monday_cash_pack/*.html` and `*.eml`.

Print the opt-in cron line:

```bash
PYTHONPATH=src python scripts/reports/run_monday_cash_pack.py --print-schedule
```

## Live run (read-only SQL)

Needs the usual DB Settings (`DB_HOST` / NCX, etc.). Sales queries keep the canonical exclusion:

`DocumentosCodigo NOT IN ('XY','AS','TS','YX','ISC')`.

```bash
PYTHONPATH=src python scripts/reports/run_monday_cash_pack.py \
  --output-dir ~/business_reports/monday_cash_pack
```

Optional SIKA markdown from an existing analysis JSON (no DB write):

```bash
PYTHONPATH=src python scripts/reports/run_monday_cash_pack.py \
  --sika-json path/to/sika_analysis_report.json
```

## Schedule (disabled / opt-in)

Mondays **08:45 America/Bogota**. Units ship disabled.

```bash
# Copy units only (does not enable)
./scripts/ops/install_monday_cash_pack_timer.sh

# Opt in
./scripts/ops/install_monday_cash_pack_timer.sh --enable
systemctl --user status depotru-monday-cash-pack.timer
```

Cron fallback (commented in `deploy/depotru-schedule.cron.example`):

```
45 8 * * 1 TZ=America/Bogota cd /path/to/depotru_database && \
  PYTHONPATH=src python scripts/reports/run_monday_cash_pack.py \
  >> ~/business_reports/monday_cash_pack.log 2>&1
```

Set the host timezone to America/Bogota or adjust `OnCalendar`.

## Regenerating

Re-run the same command; files are named `monday_cash_pack_YYYY-MM-DD.html` / `.eml`. Live mode also refreshes `CARTERA_AGING_*.html` (and PDF when ReportLab works) plus `KPI_CONTROL_BOARD_<year>_W<week>.md` using the existing generators.

## Out of scope here

AkzoNobel Core Lines zero-penetration report and mining `chat_log.jsonl` for new assistant guides are later PRs of Phase 3.
