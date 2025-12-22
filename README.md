# Deposito Trujillo - Database Analysis Project

📊 Complete SmartBusiness database analysis and reporting system

[![Database Analysis](https://github.com/Trujillofa/depotru_database/actions/workflows/database-analysis.yml/badge.svg)](https://github.com/Trujillofa/depotru_database/actions/workflows/database-analysis.yml)

---

## 🚀 Quick Start

```bash
# Navigate to project
cd /home/yderf/depotru_database

# Install dependencies
pip install -r requirements.txt

# Run PRODUCTOS SIKA analysis
python3 sika_analysis.py

# Generate reports
python3 generate_sika_report.py        # English
python3 generate_sika_report_es.py     # Spanish

# Run general category analysis
python3 run_analysis.py

# Test database connection
python3 test_connection.py

# Test Vanna AI integration
python3 test_vanna.py
```

---

## 🔧 GitHub Actions Setup

This repository is configured to run automated analysis via GitHub Actions.

### Required Secrets

Configure these in your GitHub repository settings (Settings → Secrets and variables → Actions):

```
DB_HOST=190.60.235.209
DB_PORT=1433
DB_USER=Consulta
DB_PASSWORD=Control*01
DB_NAME=SmartBusiness
VANNA_API_KEY=your_vanna_api_key_here
```

### Workflow Triggers

- **Push to main/master**: Runs analysis on every push
- **Pull Requests**: Validates analysis on PRs
- **Daily Schedule**: Runs at 8 AM UTC daily
- **Manual**: Can be triggered via "Actions" tab

### Artifacts

Analysis results are uploaded as artifacts and retained for 30 days:
- `*.json` - Raw analysis data
- `*.md` - Generated reports

---

## 📁 Project Structure

```
depotru_database/
├── .github/workflows/
│   └── database-analysis.yml          ← GitHub Actions workflow
├── README.md                          ← This file
├── requirements.txt                   ← Python dependencies
├── .gitignore                        ← Git ignore rules
├── grok_depotru.md                   ← 📖 COMPLETE DOCUMENTATION (START HERE)
├── claude_depotru.md                 ← Comprehensive reference
│
├── Python Scripts (Analysis)
│   ├── sika_analysis.py              ← Main SIKA analysis (CURRENT)
│   ├── run_analysis.py               ← General category analysis
│   ├── investigate_deposito.py       ← DEPOSITO TRUJILLO investigation
│   ├── check_document_codes.py       ← Document code validation
│   ├── test_connection.py            ← Database connection test
│   └── test_vanna.py                 ← Vanna AI integration test
│
├── Python Scripts (Report Generators)
│   ├── generate_sika_report.py       ← English SIKA report
│   ├── generate_sika_report_es.py    ← Spanish SIKA report (CURRENT)
│   └── generate_report.py            ← General report
│
├── Reports (Markdown)
│   ├── REPORTE_SIKA_ESPANOL.md      ← 📄 SIKA Report (Spanish) ⭐
│   ├── SIKA_ANALYSIS_REPORT.md      ← SIKA Report (English)
│   ├── ANALYSIS_REPORT.md           ← General category report
│   ├── DEPOSITO_TRUJILLO_INVESTIGATION.md ← Internal operations report
│   └── SIKA_PROVIDER_VERIFICATION.md     ← Provider analysis
│
└── Data Files (JSON)
    ├── sika_analysis_report.json    ← SIKA raw data
    └── analysis_report.json         ← General raw data
```

---

## 🔌 Database Connection

```
Server:   190.60.235.209:1433
Database: SmartBusiness
User:     Consulta
Password: Control*01
Table:    [dbo].[banco_datos]
```

**Environment Variables** (for GitHub Actions):
```bash
export DB_HOST=190.60.235.209
export DB_PORT=1433
export DB_USER=Consulta
export DB_PASSWORD=Control*01
export DB_NAME=SmartBusiness
```

---

## 📊 Latest Results (2024-2025)

### PRODUCTOS SIKA Performance

| Metric | 2024 | 2025 | Growth |
|--------|------|------|--------|
| Revenue | $4,626M | $5,549M | +20.0% |
| Profit | $730M | $921M | +26.2% |
| Margin | 15.8% | 16.6% | +0.8pp |
| Customers | 4,335 | 5,017 | +15.7% |

---

## 🤖 Vanna AI Integration

This project includes integration with Vanna AI for natural language to SQL conversion, powered by Grok.

### Testing Vanna

```bash
# Set your Vanna API key (if using Vanna cloud)
export VANNA_API_KEY=your_key_here

# Run Vanna tests
python3 test_vanna.py
```

### Features

- Natural language to SQL conversion
- Grok-powered query generation
- Database schema understanding
- Automated query validation

---

## ⚠️ Important Notes

1. **Use `marca` field for category** (NOT `categoria`)
2. **Use `TotalSinIva` for revenue** (NOT `TotalMasIva`)
3. **Use `ano IN (2024, 2025)` filter** (NOT `periodo BETWEEN`)
4. **Exclude DEPOSITO TRUJILLO SAS** (internal operations)
5. **Exclude document codes:** XY, AS, TS, YX, ISC

---

## 📖 Full Documentation

👉 **See `grok_depotru.md` for complete reference:**
- Database schema
- Field mappings
- SQL query patterns
- Common issues & solutions
- Future development roadmap

👉 **See `claude_depotru.md` for original comprehensive documentation**

---

## 🔄 Workflow

1. **Modify analysis:** Edit `sika_analysis.py`
2. **Run analysis:** `python3 sika_analysis.py`
3. **Generate reports:** `python3 generate_sika_report_es.py`
4. **Review output:** Check `REPORTE_SIKA_ESPANOL.md`

---

## 🧪 Testing

```bash
# Test database connection
python3 test_connection.py

# Test Vanna AI integration
python3 test_vanna.py

# Run full analysis
python3 sika_analysis.py
```

---

## 📞 Support

For detailed information, troubleshooting, and SQL patterns:
📖 Read: `grok_depotru.md` or `claude_depotru.md`

---

**Last Updated:** 2025-12-22  
**Status:** Production Ready ✅  
**CI/CD:** GitHub Actions Enabled ✅
