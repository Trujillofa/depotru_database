from pathlib import Path

import pytest

from src import business_analyzer_combined as analyzer
from src.config import Config
from src.reporting import visualization


@pytest.fixture
def sample_analysis_payload():
    return {
        "analysis_metadata": {
            "total_records": 3,
            "data_period": {
                "start_date": "2025-01-01",
                "end_date": "2025-01-31",
            },
        },
        "calculated_metrics": {
            "financial_metrics": {
                "revenue": {
                    "total_with_iva": 1160.0,
                    "total_without_iva": 1000.0,
                    "average_order_value": 386.67,
                }
            },
            "customer_analytics": {
                "total_customers": 2,
                "top_customers": [
                    {"customer_name": "Alice Retail", "total_revenue": 600.0},
                    {"customer_name": "Bob Wholesale", "total_revenue": 400.0},
                ],
            },
            "product_analytics": {
                "total_products": 3,
                "top_products": [
                    {"product_name": "Hammer Pro", "total_revenue": 500.0},
                    {"product_name": "Screwdriver Set", "total_revenue": 350.0},
                    {"product_name": "Drill X", "total_revenue": 150.0},
                ],
            },
            "category_analytics": {
                "total_categories": 2,
                "category_performance": [
                    {
                        "category_name": "Tools",
                        "total_revenue": 700.0,
                        "total_cost": 350.0,
                        "profit_margin": 50.0,
                    },
                    {
                        "category_name": "Electrical",
                        "total_revenue": 300.0,
                        "total_cost": 200.0,
                        "profit_margin": 33.3,
                    },
                ],
            },
            "trend_analytics": {
                "category_distribution": {"Tools": 700.0, "Electrical": 300.0}
            },
        },
        "strategic_recommendations": [
            "Increase inventory for star products.",
            "Implement customer segmentation for personalized pricing.",
        ],
        "magento_integration_strategies": {
            "product_catalog_optimization": [
                {"products": ["Hammer Pro", "Screwdriver Set", "Drill X"]}
            ]
        },
    }


def test_generate_visualization_report_smoke_with_default_output(
    sample_analysis_payload, tmp_path, monkeypatch
):
    if not visualization.MATPLOTLIB_AVAILABLE:
        pytest.skip("matplotlib is not available in test environment")

    monkeypatch.setattr(Config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(Config, "REPORT_DPI", 30)

    report_path = analyzer.generate_visualization_report(sample_analysis_payload)

    assert report_path is not None
    report_file = Path(report_path)
    assert report_file.exists()
    assert report_file.parent == tmp_path
    assert report_file.name.startswith("business_analysis_report_")
    assert report_file.suffix == ".png"


def test_generate_visualization_report_graceful_when_matplotlib_unavailable(
    sample_analysis_payload, monkeypatch
):
    monkeypatch.setattr(visualization, "MATPLOTLIB_AVAILABLE", False)

    report_path = analyzer.generate_visualization_report(sample_analysis_payload)

    assert report_path is None
