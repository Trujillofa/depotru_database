"""
Business Analysis Modules
=========================

This package contains specialized analysis modules for business metrics:

- customer: Customer segmentation and analytics
- product: Product performance and profitability
- financial: Financial metrics and KPIs
- inventory: Inventory velocity and optimization

Usage:
    from src.business_analyzer.analysis import CustomerAnalyzer, ProductAnalyzer
    from src.business_analyzer.analysis import FinancialAnalyzer, InventoryAnalyzer
"""

from .alerts import InventoryAlerts
from .anomaly import check_sales_anomaly
from .customer import CustomerAnalyzer
from .financial import FinancialAnalyzer
from .inventory import InventoryAnalyzer
from .manager_report import ManagerSalesReport, generate_monthly_report
from .predictive import forecast_demand, get_top_products
from .product import ProductAnalyzer
from .unified import UnifiedAnalyzer

__all__ = [
    "CustomerAnalyzer",
    "ProductAnalyzer",
    "FinancialAnalyzer",
    "InventoryAnalyzer",
    "UnifiedAnalyzer",
    "InventoryAlerts",
    "ManagerSalesReport",
    "generate_monthly_report",
    "forecast_demand",
    "get_top_products",
    "check_sales_anomaly",
]
