"""Smoke tests for matplotlib report chart generation."""

from pathlib import Path

import pytest

from business_analyzer.reports.matplotlib_charts import ReportChartGenerator


@pytest.fixture
def sample_report_data():
    return {
        "metadata": {"month": 5, "year": 2024, "month_name": "Mayo"},
        "summary": {
            "total_revenue_with_iva": 1_000_000,
            "total_revenue_without_iva": 840_000,
            "gross_profit": 200_000,
            "gross_margin_pct": 23.8,
            "total_quantity_sold": 120,
            "order_count": 40,
            "average_order_value": 25_000,
            "average_order_profit": 5_000,
        },
        "daily_trend": [
            {"date": "2024-05-01", "revenue_with_iva": 100_000, "profit": 20_000},
            {"date": "2024-05-02", "revenue_with_iva": 120_000, "profit": 25_000},
            {"date": "2024-05-03", "revenue_with_iva": 90_000, "profit": 18_000},
        ],
        "top_products": [
            {
                "product_name": "Cemento",
                "sku": "CEM001",
                "total_revenue": 300_000,
                "quantity_sold": 50,
                "profit_margin_pct": 20.0,
            }
        ],
        "top_customers": [
            {
                "customer_name": "Cliente A",
                "total_revenue": 200_000,
                "total_orders": 5,
                "profit_margin_pct": 22.0,
            }
        ],
        "category_breakdown": [
            {
                "category_path": "Materiales > Cemento",
                "total_revenue": 500_000,
                "profit_margin_pct": 21.0,
            },
            {
                "category_path": "Herramientas > Manuales",
                "total_revenue": 300_000,
                "profit_margin_pct": 25.0,
            },
        ],
        "vendor_sales": [
            {
                "vendor_name": "SIKA",
                "total_revenue": 150_000,
                "profit_margin_pct": 24.0,
            },
        ],
    }


def test_generate_all_creates_chart_files(tmp_path, sample_report_data):
    gen = ReportChartGenerator(sample_report_data, output_dir=str(tmp_path))
    paths = gen.generate_all()
    assert paths
    for path in paths.values():
        assert Path(path).exists()
        assert Path(path).stat().st_size > 0
