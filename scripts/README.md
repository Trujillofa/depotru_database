# Scripts Directory

This directory contains all Python scripts organized by function.

## Structure

### `/analysis/` - Data Analysis Scripts
Scripts for analyzing business data and generating insights.

- `sika_analysis.py` - Main PRODUCTOS SIKA analysis script
- `run_analysis.py` - General category analysis (all products)
- `investigate_deposito.py` - DEPOSITO TRUJILLO investigation
- `check_document_codes.py` - Document code validation
- `kpi_sql_pack.sql.template` - Weekly SQL KPI pack (profitability, ticket, concentration, returns)

### `/reports/` - Report Generation Scripts
Scripts for generating reports from analysis data.

- `generate_report.py` - General category report generator
- `generate_sika_report.py` - English SIKA report generator
- `generate_sika_report_es.py` - Spanish SIKA report generator

### `/utils/` - Utility Scripts
Helper scripts for testing, diagnostics, and maintenance.

- `test_connection.py` - Database connection testing
- `test_vanna.py` - Vanna AI testing
- `run_tests.py` - Test runner
- `autoresearch_to_vanna.py` - Convert AutoResearch outputs to Vanna JSONL training pairs
- `run_autoresearch_pipeline.py` - Convert AutoResearch data and launch Vanna with external training file
- `run_vanna_regression_checks.py` - Run repeatable NL→SQL quality checks (filter + non-empty results)
- `generate_kpi_control_board.py` - Execute KPI SQL pack and generate weekly KPI markdown board
- `run_weekly_kpi_board.py` - One-command weekly wrapper (last completed Mon-Sun week)
- `diagnose_and_fix_css.py` - CSS diagnostics
- `upload_and_fix.py` - Upload and fix utility

## Usage

Run scripts from the repository root:

```bash
# One-command weekly KPI board automation (Makefile target)
make kpi-weekly

# Analysis
python scripts/analysis/sika_analysis.py
python scripts/analysis/run_analysis.py
# Execute KPI pack in MSSQL client:
# scripts/analysis/kpi_sql_pack.sql.template

# Reports
python scripts/reports/generate_sika_report.py
python scripts/reports/generate_sika_report_es.py

# Utilities
python scripts/utils/test_connection.py
python scripts/utils/run_tests.py
python scripts/utils/autoresearch_to_vanna.py --input data/raw.tsv --output data/vanna_examples.jsonl
python scripts/utils/run_autoresearch_pipeline.py --input data/raw.tsv
python scripts/utils/run_vanna_regression_checks.py --training-file data/autoresearch_vanna_examples.jsonl
python scripts/utils/generate_kpi_control_board.py --start-date 2026-01-01 --end-date 2026-03-31
python scripts/utils/run_weekly_kpi_board.py

# Optional: print cron line for Monday automation
python scripts/utils/run_weekly_kpi_board.py --print-cron
```

Notes:
- `make kpi-weekly` uses `venv/bin/python`, so run `make install` first if your venv is not created yet.
- KPI scripts load database credentials from `.env` (or environment), requiring at minimum: `DB_SERVER`, `DB_USER`, `DB_PASSWORD`.
