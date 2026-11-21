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

_LAZY_EXPORTS = {
    "InventoryAlerts": ".alerts",
    "check_sales_anomaly": ".anomaly",
    "CustomerAnalyzer": ".customer",
    "FinancialAnalyzer": ".financial",
    "InventoryAnalyzer": ".inventory",
    "ManagerSalesReport": ".manager_report",
    "generate_monthly_report": ".manager_report",
    "forecast_demand": ".predictive",
    "get_top_products": ".predictive",
    "ProductAnalyzer": ".product",
    "UnifiedAnalyzer": ".unified",
}

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


def __getattr__(name):
    # Lazy imports: eagerly importing the analyzers here drags the whole
    # ``business_analyzer.ai`` package (and its required API keys) into every
    # CLI, even DB-only tools that never use AI.
    module_path = _LAZY_EXPORTS.get(name)
    if module_path:
        import importlib

        module = importlib.import_module(module_path, __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(list(globals()) + __all__)
