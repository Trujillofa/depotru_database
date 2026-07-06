"""Manager sales report package."""

from business_analyzer.core.database import ConnectionType, Database

from .helpers import (
    MONTH_NAMES_ES,
    extract_row_value,
    extract_value,
    is_likely_supplier_name,
    is_recommendable_product,
    safe_divide,
    to_float,
)
from .report import ManagerSalesReport, generate_monthly_report

# Backward-compatible private aliases
_to_float = to_float
_extract_row_value = extract_row_value
_is_recommendable_product = is_recommendable_product
_is_likely_supplier_name = is_likely_supplier_name

__all__ = [
    "ManagerSalesReport",
    "generate_monthly_report",
    "Database",
    "ConnectionType",
    "MONTH_NAMES_ES",
    "safe_divide",
    "to_float",
    "extract_row_value",
    "extract_value",
    "is_recommendable_product",
    "is_likely_supplier_name",
]
