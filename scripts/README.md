# Scripts Directory

This directory contains all Python scripts organized by function.

## Structure

### `/analysis/` - Data Analysis Scripts
Scripts for analyzing business data and generating insights.

- `sika_analysis.py` - Main PRODUCTOS SIKA analysis script
- `run_analysis.py` - General category analysis (all products)
- `investigate_deposito.py` - DEPOSITO TRUJILLO investigation
- `check_document_codes.py` - Document code validation

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
- `diagnose_and_fix_css.py` - CSS diagnostics
- `upload_and_fix.py` - Upload and fix utility

## Usage

Run scripts from the repository root:

```bash
# Analysis
python scripts/analysis/sika_analysis.py
python scripts/analysis/run_analysis.py

# Reports
python scripts/reports/generate_sika_report.py
python scripts/reports/generate_sika_report_es.py

# Utilities
python scripts/utils/test_connection.py
python scripts/utils/run_tests.py
```
