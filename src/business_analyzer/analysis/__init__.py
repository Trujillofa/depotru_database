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
from .customer import CustomerAnalyzer
from .financial import FinancialAnalyzer
from .inventory import InventoryAnalyzer
from .product import ProductAnalyzer
from .unified import UnifiedAnalyzer

__all__ = [
    "CustomerAnalyzer",
    "ProductAnalyzer",
    "FinancialAnalyzer",
    "InventoryAnalyzer",
    "UnifiedAnalyzer",
    "InventoryAlerts",
]
