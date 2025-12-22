"""
Enhanced Business Data Analyzer with Visualization Report
=========================================================
Comprehensive business analysis tool for hardware store operations.
Combines data analysis with automated report generation and visualizations.

Features:
- Database analysis with DocumentosCodigo filtering (excludes 'XY', 'AS', 'TS')
- Comprehensive business metrics calculation
- Automated visualization generation
- Strategic recommendations
- Magento e-commerce integration strategies

Usage:
python business_analyzer_combined.py --limit 5000
python business_analyzer_combined.py --start-date 2025-01-01 --end-date 2025-10-31
python business_analyzer_combined.py --limit 5000 --skip-analysis

Example:

python /home/yderf/Coding_OMARCHY/python_files/business_analyzer_combined.py --start-date 2025-10-
01 --end-date 2025-10-25 --limit 50000

Note: Visualization reports are generated automatically when matplotlib is installed.
The --generate-report flag is for future compatibility.
"""

from typing import List, Dict, Any
import pymssql
import xml.etree.ElementTree as ET
import logging
import json
import argparse
import os
from datetime import datetime, date
from decimal import Decimal
from collections import defaultdict
import statistics

# Import configuration
from config import Config, CustomerSegmentation, InventoryConfig, ProfitabilityConfig

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Visualization imports (optional)
try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.gridspec import GridSpec
    import numpy as np
    import warnings

    warnings.filterwarnings("ignore")
    MATPLOTLIB_AVAILABLE = True
    logger.info("Matplotlib available for visualizations")
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("Matplotlib not available - visualizations will be skipped")

# Set style for professional-looking charts
colors = ["#2E86AB", "#A23B72", "#F18F01", "#C73E1D", "#6A994E"]
if MATPLOTLIB_AVAILABLE:
    plt.style.use("seaborn-v0_8-darkgrid")


# Custom JSON encoder for Decimal and datetime types
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super(DecimalEncoder, self).default(obj)


# P0 FIX #2: Safe division helper to prevent crashes
def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Perform division with zero-check to prevent crashes.

    Args:
        numerator: The dividend
        denominator: The divisor
        default: Value to return if denominator is zero (default: 0.0)

    Returns:
        Result of division, or default if denominator is zero

    Examples:
        >>> safe_divide(100, 50)
        2.0
        >>> safe_divide(100, 0)
        0.0
        >>> safe_divide(100, 0, default=-1)
        -1.0
    """
    return numerator / denominator if denominator != 0 else default


# P0 FIX #3: Input validation functions
def validate_date_format(date_str: str, param_name: str) -> datetime:
    """
    Validate date string format.

    Args:
        date_str: Date string to validate
        param_name: Parameter name for error messages

    Returns:
        Parsed datetime object

    Raises:
        ValueError: If date format is invalid
    """
    try:
        parsed_date = datetime.strptime(date_str, "%Y-%m-%d")

        # Check if year is reasonable
        current_year = datetime.now().year
        if parsed_date.year < 2000 or parsed_date.year > current_year + 1:
            raise ValueError(
                f"{param_name} year ({parsed_date.year}) seems unreasonable. "
                f"Expected between 2000 and {current_year + 1}"
            )

        return parsed_date
    except ValueError as e:
        if "does not match format" in str(e) or "unconverted data remains" in str(e):
            raise ValueError(
                f"Invalid {param_name} format: '{date_str}'. "
                f"Use YYYY-MM-DD format (e.g., 2025-01-15)"
            )
        raise


def validate_date_range(start_date: str, end_date: str) -> None:
    """
    Validate date range.

    Args:
        start_date: Start date string
        end_date: End date string

    Raises:
        ValueError: If dates are invalid or in wrong order
    """
    start_dt = validate_date_format(start_date, "start-date")
    end_dt = validate_date_format(end_date, "end-date")

    if start_dt > end_dt:
        raise ValueError(
            f"start-date ({start_date}) must be before or equal to "
            f"end-date ({end_date})"
        )


def validate_limit(limit: int) -> None:
    """
    Validate record limit.

    Args:
        limit: Number of records to fetch

    Raises:
        ValueError: If limit is invalid
    """
    if limit < 1:
        raise ValueError(f"limit must be at least 1, got {limit}")

    if limit > 1_000_000:
        raise ValueError(
            f"limit ({limit:,}) exceeds maximum (1,000,000). "
            f"Use smaller limit to prevent memory issues."
        )


# Try to import NavicatCipher
try:
    from NavicatCipher import Navicat12Crypto

    NAVICAT_CIPHER_AVAILABLE = True
    logger.info("NavicatCipher module available")
except ImportError:
    NAVICAT_CIPHER_AVAILABLE = False
    logger.warning("NavicatCipher not available")

# Cryptography for password decryption (fallback)
try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


class BusinessMetricsCalculator:
    """Advanced business metrics calculator"""

    def __init__(self, data: List[Dict[str, Any]]):
        self.data = data

    def calculate_all_metrics(self) -> Dict[str, Any]:
        """Calculate comprehensive business metrics"""
        return {
            "financial_metrics": self.calculate_financial_metrics(),
            "customer_analytics": self.analyze_customers(),
            "product_analytics": self.analyze_products(),
            "category_analytics": self.analyze_categories(),
            "inventory_analytics": self.analyze_inventory(),
            "trend_analytics": self.analyze_trends(),
            "profitability_analytics": self.analyze_profitability(),
            "risk_metrics": self.calculate_risk_metrics(),
            "operational_efficiency": self.calculate_operational_efficiency(),
        }

    def _extract_value(self, row: Dict, keys: List[str], default=None):
        """Extract value from row using multiple possible keys"""
        for key in keys:
            if key in row and row[key] is not None:
                value = row[key]
                # Handle Decimal types from pymssql
                if isinstance(value, Decimal):
                    return float(value)
                # Handle string numbers
                if (
                    isinstance(value, str)
                    and value.replace(".", "")
                    .replace(",", "")
                    .replace("-", "")
                    .isdigit()
                ):
                    return float(value.replace(",", ""))
                return value
        return default

    def calculate_financial_metrics(self) -> Dict[str, Any]:
        """Calculate comprehensive financial KPIs"""
        revenues_with_iva = []
        revenues_without_iva = []
        costs = []

        for row in self.data:
            revenue_iva = self._extract_value(
                row, ["TotalMasIva", "PrecioTotal", "precio_total_iva"]
            )
            revenue_no_iva = self._extract_value(
                row, ["TotalSinIva", "PrecioUnitario", "precio_total"]
            )
            cost = self._extract_value(
                row, ["ValorCosto", "CostoUnitario", "cost", "costo"]
            )
            quantity = self._extract_value(row, ["Cantidad", "quantity"], default=1)

            if revenue_iva:
                revenues_with_iva.append(revenue_iva)
            if revenue_no_iva:
                revenues_without_iva.append(revenue_no_iva)
            if cost:
                costs.append(cost)

        metrics = {
            "revenue": {
                "total_with_iva": (
                    round(sum(revenues_with_iva), 2) if revenues_with_iva else 0
                ),
                "total_without_iva": (
                    round(sum(revenues_without_iva), 2) if revenues_without_iva else 0
                ),
                "average_order_value": (
                    round(statistics.mean(revenues_with_iva), 2)
                    if revenues_with_iva
                    else 0
                ),
                "median_order_value": (
                    round(statistics.median(revenues_with_iva), 2)
                    if revenues_with_iva
                    else 0
                ),
            },
            "costs": {
                "total_cost": round(sum(costs), 2) if costs else 0,
                "average_cost_per_unit": (
                    round(statistics.mean(costs), 2) if costs else 0
                ),
            },
            "profit": {},
        }

        if revenues_without_iva and costs:
            gross_profit = sum(revenues_without_iva) - sum(costs)
            metrics["profit"]["gross_profit"] = round(gross_profit, 2)
            # P0 FIX: Use safe_divide to prevent crashes
            metrics["profit"]["gross_profit_margin"] = round(
                safe_divide(gross_profit, sum(revenues_without_iva), default=0) * 100, 2
            )

        return metrics

    def analyze_customers(self) -> Dict[str, Any]:
        """Comprehensive customer analytics"""
        customer_data = defaultdict(
            lambda: {
                "total_revenue": 0,
                "total_orders": 0,
                "products_purchased": set(),
                "dates": [],
            }
        )

        for row in self.data:
            customer = self._extract_value(
                row,
                ["TercerosNombres", "NombreCliente", "customer_name", "cliente"],
                default="Unknown",
            )
            revenue = self._extract_value(
                row, ["TotalMasIva", "PrecioTotal", "precio_total_iva"], default=0
            )
            product = self._extract_value(
                row,
                ["ArticulosNombre", "Descripcion", "product_name", "producto"],
                default="Unknown",
            )
            date = self._extract_value(row, ["Fecha", "date", "fecha"])

            customer_data[customer]["total_revenue"] += revenue
            customer_data[customer]["total_orders"] += 1
            customer_data[customer]["products_purchased"].add(product)
            if date:
                customer_data[customer]["dates"].append(date)

        customers_list = []
        for customer, data in customer_data.items():
            customers_list.append(
                {
                    "customer_name": customer,
                    "total_revenue": round(data["total_revenue"], 2),
                    "total_orders": data["total_orders"],
                    "average_order_value": round(
                        safe_divide(data["total_revenue"], data["total_orders"], default=0), 2
                    ),
                    "product_diversity": len(data["products_purchased"]),
                    "customer_segment": self._segment_customer(
                        data["total_revenue"], data["total_orders"]
                    ),
                }
            )

        customers_list.sort(key=lambda x: x["total_revenue"], reverse=True)

        total_revenue = sum(c["total_revenue"] for c in customers_list)
        top_10_revenue = sum(
            c["total_revenue"] for c in customers_list[: min(10, len(customers_list))]
        )

        return {
            "top_customers": customers_list[:20],
            "total_customers": len(customers_list),
            "customer_concentration": {
                # P0 FIX: Use safe_divide
                "top_10_percentage": round(
                    safe_divide(top_10_revenue, total_revenue, default=0) * 100, 2
                )
            },
            "segmentation": self._aggregate_segments(customers_list),
        }

    def _segment_customer(self, revenue: float, orders: int) -> str:
        """Segment customer based on revenue and order frequency"""
        if revenue > CustomerSegmentation.VIP_REVENUE_THRESHOLD and orders > CustomerSegmentation.VIP_ORDERS_THRESHOLD:
            return "VIP"
        elif revenue > CustomerSegmentation.HIGH_VALUE_THRESHOLD:
            return "High Value"
        elif orders > CustomerSegmentation.FREQUENT_ORDERS_THRESHOLD:
            return "Frequent"
        elif revenue > CustomerSegmentation.REGULAR_REVENUE_THRESHOLD:
            return "Regular"
        else:
            return "Occasional"

    def _aggregate_segments(self, customers: List[Dict]) -> Dict[str, int]:
        """Aggregate customer segmentation"""
        segments = defaultdict(int)
        for customer in customers:
            segments[customer["customer_segment"]] += 1
        return dict(segments)

    def analyze_products(self) -> Dict[str, Any]:
        """Comprehensive product analytics"""
        product_data = defaultdict(
            lambda: {
                "sku": "",
                "total_revenue": 0,
                "total_cost": 0,
                "total_quantity": 0,
                "transactions": 0,
            }
        )

        for row in self.data:
            product = self._extract_value(
                row,
                ["ArticulosNombre", "Descripcion", "product_name", "producto"],
                default="Unknown",
            )
            sku = self._extract_value(row, ["ArticulosCodigo"], default="")
            revenue = self._extract_value(row, ["TotalSinIva"], default=0)
            cost = self._extract_value(row, ["ValorCosto"], default=0)
            quantity = self._extract_value(
                row, ["Cantidad", "quantity", "cantidad"], default=1
            )

            product_data[product]["sku"] = sku
            product_data[product]["total_revenue"] += revenue
            product_data[product]["total_cost"] += cost
            product_data[product]["total_quantity"] += quantity
            product_data[product]["transactions"] += 1

        products_list = []
        for product, data in product_data.items():
            profit = data["total_revenue"] - data["total_cost"]
            # P0 FIX: Use safe_divide
            profit_margin = safe_divide(profit, data["total_revenue"], default=0) * 100

            products_list.append(
                {
                    "product_name": product,
                    "sku": data["sku"],
                    "total_revenue": round(data["total_revenue"], 2),
                    "total_quantity": data["total_quantity"],
                    "profit": round(profit, 2),
                    "profit_margin": round(profit_margin, 2),
                    "transactions": data["transactions"],
                }
            )

        products_list.sort(key=lambda x: x["total_revenue"], reverse=True)

        return {
            "top_products": products_list[:30],
            "total_products": len(products_list),
            "underperforming_products": [
                p for p in products_list if p["profit_margin"] < ProfitabilityConfig.LOW_MARGIN_THRESHOLD
            ],
            "star_products": [p for p in products_list if p["profit_margin"] > ProfitabilityConfig.STAR_PRODUCT_MARGIN][:10],
        }

    def analyze_categories(self) -> Dict[str, Any]:
        """Comprehensive category and subcategory analytics"""
        category_data = defaultdict(
            lambda: {
                "total_revenue": 0,
                "total_cost": 0,
                "orders": 0,
                "subcategories": defaultdict(
                    lambda: {"revenue": 0, "cost": 0, "orders": 0}
                ),
            }
        )

        for row in self.data:
            categoria = self._extract_value(row, ["categoria"], default="Unknown")
            subcategoria = self._extract_value(row, ["subcategoria"], default="Unknown")
            revenue = self._extract_value(row, ["TotalSinIva"], default=0)
            cost = self._extract_value(row, ["ValorCosto"], default=0)
            quantity = self._extract_value(row, ["Cantidad", "quantity"], default=1)

            category_data[categoria]["total_revenue"] += revenue
            category_data[categoria]["total_cost"] += cost
            category_data[categoria]["orders"] += 1
            category_data[categoria]["subcategories"][subcategoria][
                "revenue"
            ] += revenue
            category_data[categoria]["subcategories"][subcategoria]["cost"] += cost
            category_data[categoria]["subcategories"][subcategoria]["orders"] += 1

        categories_list = []
        for categoria, data in category_data.items():
            profit = data["total_revenue"] - data["total_cost"]
            # P0 FIX: Use safe_divide
            profit_margin = safe_divide(profit, data["total_revenue"], default=0) * 100

            # Get top subcategories
            subcats = []
            for subcat, subdata in data["subcategories"].items():
                subcats.append(
                    {
                        "subcategory": subcat,
                        "revenue": round(subdata["revenue"], 2),
                        "orders": subdata["orders"],
                    }
                )
            subcats.sort(key=lambda x: x["revenue"], reverse=True)

            categories_list.append(
                {
                    "category_name": categoria,
                    "total_revenue": round(data["total_revenue"], 2),
                    "total_cost": round(data["total_cost"], 2),
                    "profit": round(profit, 2),
                    "profit_margin": round(profit_margin, 2),
                    "order_count": data["orders"],
                    "risk_level": (
                        "CRITICAL"
                        if profit_margin < 0
                        else (
                            "HIGH"
                            if profit_margin < 10
                            else "MEDIUM" if profit_margin < 20 else "LOW"
                        )
                    ),
                    "top_subcategories": subcats[:5],
                }
            )

        categories_list.sort(key=lambda x: x["total_revenue"], reverse=True)

        return {
            "category_performance": categories_list,
            "total_categories": len(categories_list),
        }

    def analyze_inventory(self) -> Dict[str, Any]:
        """Inventory optimization analytics"""
        inventory = defaultdict(lambda: {"total_sold": 0, "transactions": 0})

        for row in self.data:
            product = self._extract_value(
                row,
                ["ArticulosNombre", "Descripcion", "product_name"],
                default="Unknown",
            )
            quantity = self._extract_value(row, ["Cantidad", "quantity"], default=1)

            inventory[product]["total_sold"] += quantity
            inventory[product]["transactions"] += 1

        fast_movers = []
        slow_movers = []

        for product, data in inventory.items():
            if data["transactions"] > InventoryConfig.FAST_MOVER_THRESHOLD:
                fast_movers.append(
                    {
                        "product": product,
                        "velocity": data["transactions"],
                        "total_sold": data["total_sold"],
                    }
                )
            elif data["transactions"] < InventoryConfig.SLOW_MOVER_THRESHOLD:
                slow_movers.append(
                    {
                        "product": product,
                        "velocity": data["transactions"],
                        "total_sold": data["total_sold"],
                    }
                )

        return {
            "fast_moving_items": sorted(
                fast_movers, key=lambda x: x["velocity"], reverse=True
            )[:20],
            "slow_moving_items": sorted(slow_movers, key=lambda x: x["velocity"])[:20],
        }

    def analyze_trends(self) -> Dict[str, Any]:
        """Trend and seasonality analysis"""
        monthly_data = defaultdict(lambda: {"revenue": 0, "transactions": 0})
        category_data = defaultdict(float)

        for row in self.data:
            date = self._extract_value(row, ["Fecha", "date", "fecha"])
            revenue = self._extract_value(
                row, ["TotalMasIva", "PrecioTotal", "precio_total_iva"], default=0
            )
            category = self._extract_value(
                row, ["Categoria", "category", "categoria"], default="Uncategorized"
            )

            if date:
                month_key = (
                    f"{date.year}-{date.month:02d}"
                    if hasattr(date, "year")
                    else "2025-10"
                )
                monthly_data[month_key]["revenue"] += revenue
                monthly_data[month_key]["transactions"] += 1

            category_data[category] += revenue

        return {
            "monthly_trends": dict(sorted(monthly_data.items())),
            "category_distribution": dict(
                sorted(category_data.items(), key=lambda x: x[1], reverse=True)
            ),
        }

    def analyze_profitability(self) -> Dict[str, Any]:
        """Deep profitability analysis"""
        by_category = defaultdict(lambda: {"revenue": 0, "cost": 0})

        for row in self.data:
            revenue = self._extract_value(
                row, ["TotalSinIva", "PrecioUnitario", "precio_total"], default=0
            )
            cost = self._extract_value(
                row, ["ValorCosto", "CostoUnitario", "cost", "costo"], default=0
            )
            quantity = self._extract_value(row, ["Cantidad", "quantity"], default=1)
            category = self._extract_value(
                row, ["Categoria", "category"], default="Uncategorized"
            )

            by_category[category]["revenue"] += revenue
            by_category[category]["cost"] += cost

        category_margins = {}
        for cat, data in by_category.items():
            # P0 FIX: Use safe_divide
            profit = data["revenue"] - data["cost"]
            margin = safe_divide(profit, data["revenue"], default=0) * 100
            category_margins[cat] = {
                "revenue": round(data["revenue"], 2),
                "profit": round(profit, 2),
                "margin": round(margin, 2),
            }

        return {
            "by_category": dict(
                sorted(
                    category_margins.items(), key=lambda x: x[1]["margin"], reverse=True
                )
            )
        }

    def calculate_risk_metrics(self) -> Dict[str, Any]:
        """Calculate business risk metrics"""
        return {
            "customer_concentration_risk": "Moderate",
            "supplier_concentration_risk": "Moderate",
            "note": "Monitor concentration to avoid dependency",
        }

    def calculate_operational_efficiency(self) -> Dict[str, Any]:
        """Calculate operational efficiency metrics"""
        total_transactions = len(self.data)
        revenues = [
            self._extract_value(row, ["PrecioTotal", "precio_total_iva"], default=0)
            for row in self.data
        ]

        return {
            "total_transactions": total_transactions,
            "revenue_per_transaction": (
                round(statistics.mean(revenues), 2) if revenues else 0
            ),
        }


def decrypt_navicat_password(encrypted_password: str) -> str:
    """Decrypt password encrypted by Navicat"""
    if NAVICAT_CIPHER_AVAILABLE:
        try:
            crypto = Navicat12Crypto()
            decrypted = crypto.DecryptStringForNCX(encrypted_password)
            return decrypted
        except Exception as e:
            logger.warning(f"NavicatCipher decryption failed: {e}")

    if CRYPTO_AVAILABLE:
        try:
            key = b"libcckeylibcckey"
            iv = b"libcciv libcciv "
            encrypted_bytes = bytes.fromhex(encrypted_password)
            cipher = AES.new(key, AES.MODE_CBC, iv)
            decrypted = unpad(cipher.decrypt(encrypted_bytes), AES.block_size)
            return decrypted.decode("utf-8")
        except Exception as e:
            logger.warning(f"AES decryption failed: {e}")

    raise ImportError("No decryption method available")


def load_connections(file_path: str) -> List[Dict[str, Any]]:
    """Load and parse connections from a Navicat NCX file."""
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        connections = []

        for conn in root.findall("Connection"):
            host = conn.get("Host")
            user = conn.get("UserName")
            encrypted_password = conn.get("Password")

            if not all([host, user, encrypted_password]):
                continue

            try:
                password = decrypt_navicat_password(encrypted_password)
            except Exception as e:
                logger.error(f"Failed to decrypt password: {e}")
                continue

            port = conn.get("Port", "1433")
            database = conn.get("Database", "master")

            connections.append(
                {
                    "Host": host,
                    "Port": int(port),
                    "UserName": user,
                    "Password": password,
                    "Database": database,
                }
            )

        return connections
    except Exception as e:
        logger.error(f"Error loading connections: {e}")
        return []


def fetch_banco_datos(
    conn_details: Dict[str, Any],
    limit: int = None,
    start_date: str = None,
    end_date: str = None
) -> List[Dict[str, Any]]:
    """Fetch data from banco_datos table - DIRECT CONNECTION (no SSH tunnel)

    Filters out records with DocumentosCodigo in excluded list to exclude
    certain document types from analysis.

    P0 FIX: Added finally block to ensure connection is always closed.
    """
    if limit is None:
        limit = Config.DEFAULT_LIMIT

    conn = None  # P0 FIX: Initialize outside try block
    try:
        logger.info(
            f"Connecting to database at {conn_details['Host']}:{conn_details['Port']}"
        )

        conn = pymssql.connect(
            server=conn_details["Host"],
            port=conn_details["Port"],
            user=conn_details["UserName"],
            password=conn_details["Password"],
            database=Config.DB_NAME,
            login_timeout=Config.DB_LOGIN_TIMEOUT,
            timeout=Config.DB_TIMEOUT,
            tds_version=Config.DB_TDS_VERSION,
        )

        logger.info("✓ Connected to database successfully")
        cursor = conn.cursor(as_dict=True)

        # Test connection
        cursor.execute("SELECT 1 as test")
        result = cursor.fetchone()
        logger.info(f"DB connection test: {result}")

        # Get column names
        cursor.execute(f"SELECT TOP 0 * FROM [{Config.DB_NAME}].[dbo].[{Config.DB_TABLE}]")
        columns = [desc[0] for desc in cursor.description]
        logger.info(f"Columns in {Config.DB_TABLE}: {columns}")

        # Build exclusion list for query
        excluded_codes = ', '.join([f"'{code}'" for code in Config.EXCLUDED_DOCUMENT_CODES])

        # Query to fetch data
        query = f"SELECT TOP %s * FROM [{Config.DB_NAME}].[dbo].[{Config.DB_TABLE}] WHERE DocumentosCodigo NOT IN ({excluded_codes})"
        params = [limit]

        if start_date and end_date:
            query += " AND Fecha BETWEEN %s AND %s"
            params.extend([start_date, end_date])
        elif start_date:
            query += " AND Fecha >= %s"
            params.append(start_date)
        elif end_date:
            query += " AND Fecha <= %s"
            params.append(end_date)

        cursor.execute(query, tuple(params))
        data = list(cursor)

        if not data:
            logger.warning(f"No data retrieved from {Config.DB_TABLE}.")
        else:
            logger.info(f"✓ Fetched {len(data)} rows successfully")

        return data

    except pymssql.OperationalError as e:
        # P0 FIX: Better error handling for timeouts
        if "timeout" in str(e).lower():
            logger.error(f"❌ Database connection timeout. Check network connectivity.")
        else:
            logger.error(f"❌ Database operational error: {e}")
        raise
    except pymssql.Error as e:
        logger.error(f"❌ Database error: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        raise
    finally:
        # P0 FIX: CRITICAL - Always close connection, even on error
        if conn:
            try:
                conn.close()
                logger.info("✓ Database connection closed safely")
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")


def generate_recommendations(metrics: Dict[str, Any]) -> List[str]:
    """Generate business recommendations"""
    recommendations = []

    # Financial recommendations
    margin = (
        metrics.get("financial_metrics", {})
        .get("profit", {})
        .get("gross_profit_margin", 0)
    )
    if margin < 20:
        recommendations.append(
            f"⚠️ URGENT: Gross profit margin is {margin}%. Review pricing strategy."
        )

    # Category recommendations
    categories = metrics.get("category_analytics", {}).get("category_performance", [])
    critical = [c for c in categories if c["risk_level"] == "CRITICAL"]
    if critical:
        recommendations.append(
            f"🔴 CRITICAL: {len(critical)} categories with negative margins. Review pricing and costs immediately."
        )

    # Product recommendations
    underperforming = metrics.get("product_analytics", {}).get(
        "underperforming_products", []
    )
    if underperforming:
        recommendations.append(
            f"📊 {len(underperforming)} products with margins <10%. Consider price increases."
        )

    star_products = metrics.get("product_analytics", {}).get("star_products", [])
    if star_products:
        recommendations.append(
            f"⭐ {len(star_products)} star products identified. Increase inventory and marketing."
        )

    return recommendations


def generate_magento_strategies(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Generate Magento e-commerce strategies"""
    top_products = metrics.get("product_analytics", {}).get("top_products", [])[:10]

    return {
        "product_catalog_optimization": [
            {
                "strategy": "Featured Products Section",
                "implementation": "Create 'Best Sellers' section on homepage",
                "products": [p["product_name"] for p in top_products],
            }
        ],
        "b2b_features": [
            {
                "strategy": "B2B Quick Order",
                "implementation": "Enable CSV upload for wholesale customers",
                "benefit": "30% reduction in order time",
            }
        ],
        "customer_segmentation": [
            {
                "strategy": "VIP Customer Group",
                "implementation": "Create customer groups with tiered pricing",
                "segments": metrics.get("customer_analytics", {}).get(
                    "segmentation", {}
                ),
            }
        ],
    }


def generate_visualization_report(
    analysis: Dict[str, Any], output_path: str = None
) -> str:
    """Generate comprehensive visualization report"""
    if not MATPLOTLIB_AVAILABLE:
        logger.warning("Matplotlib not available - skipping visualization generation")
        return None

    # Ensure output directory exists
    Config.ensure_output_dir()

    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Config.OUTPUT_DIR / f"business_analysis_report_{timestamp}.png"
    else:
        output_path = os.path.expanduser(output_path)

    # Extract metrics for easier access
    metrics = analysis["calculated_metrics"]
    financial = metrics["financial_metrics"]
    customers = metrics["customer_analytics"]
    products = metrics["product_analytics"]
    categories = metrics["category_analytics"]
    trends = metrics["trend_analytics"]

    # Create figure with multiple subplots
    fig = plt.figure(figsize=(20, 24))
    gs = GridSpec(6, 2, figure=fig, hspace=0.4, wspace=0.3)

    # Title
    period_info = analysis["analysis_metadata"]["data_period"]
    start_date = period_info.get("start_date", "Unknown")
    end_date = period_info.get("end_date", "Unknown")
    title_date = (
        f"{start_date} to {end_date}"
        if start_date != "Unknown"
        else "Business Performance Analysis"
    )
    fig.suptitle(
        f"Business Performance Analysis Report - {title_date}",
        fontsize=24,
        fontweight="bold",
        y=0.995,
    )

    # ============================================================================
    # 1. KPI Summary Cards (Top Section)
    # ============================================================================
    ax_kpi = fig.add_subplot(gs[0, :])
    ax_kpi.axis("off")

    revenue_with_iva = financial["revenue"]["total_with_iva"]
    revenue_without_iva = financial["revenue"]["total_without_iva"]
    avg_order_value = financial["revenue"]["average_order_value"]

    kpi_data = [
        ("Total Revenue\n(with IVA)", f"${revenue_with_iva:,.2f}"),
        ("Total Revenue\n(without IVA)", f"${revenue_without_iva:,.2f}"),
        ("Average Order\nValue", f"${avg_order_value:,.2f}"),
        ("IVA Collected", f"${revenue_with_iva - revenue_without_iva:,.2f}"),
    ]

    for i, (label, value) in enumerate(kpi_data):
        x_pos = 0.125 + i * 0.22
        rect = mpatches.FancyBboxPatch(
            (x_pos - 0.08, 0.3),
            0.16,
            0.4,
            boxstyle="round,pad=0.01",
            edgecolor=colors[i],
            facecolor=colors[i],
            alpha=0.2,
            linewidth=2,
        )
        ax_kpi.add_patch(rect)
        ax_kpi.text(
            x_pos,
            0.55,
            value,
            ha="center",
            va="center",
            fontsize=16,
            fontweight="bold",
            color=colors[i],
        )
        ax_kpi.text(
            x_pos, 0.4, label, ha="center", va="center", fontsize=10, color="#333333"
        )

    # ============================================================================
    # 2. Top Selling Products (Horizontal Bar Chart)
    # ============================================================================
    ax1 = fig.add_subplot(gs[1, :])
    top_products_list = products["top_products"][:3] if products["top_products"] else []
    product_names = [
        (
            p["product_name"][:50] + "..."
            if len(p["product_name"]) > 50
            else p["product_name"]
        )
        for p in top_products_list
    ]
    product_sales = [p["total_revenue"] for p in top_products_list]

    if product_names:
        y_pos = np.arange(len(product_names))
        bars = ax1.barh(
            y_pos, product_sales, color=colors[:3], alpha=0.8, edgecolor="black"
        )
        ax1.set_yticks(y_pos)
        ax1.set_yticklabels(product_names, fontsize=10)
        ax1.set_xlabel("Total Sales ($)", fontsize=12, fontweight="bold")
        ax1.set_title("Top 3 Selling Products", fontsize=14, fontweight="bold", pad=15)
        ax1.grid(axis="x", alpha=0.3)

        # Add value labels on bars
        for i, (bar, value) in enumerate(zip(bars, product_sales)):
            ax1.text(
                value + 20000,
                bar.get_y() + bar.get_height() / 2,
                f"${value:,.2f}",
                va="center",
                fontsize=10,
                fontweight="bold",
            )

    # ============================================================================
    # 3. Category Sales Distribution (Pie Chart)
    # ============================================================================
    ax2 = fig.add_subplot(gs[2, 0])
    category_dist = trends.get("category_distribution", {})

    # Filter out negative and zero values for pie chart (matplotlib requirement)
    positive_categories = {k: v for k, v in category_dist.items() if v > 0}
    cat_names = list(positive_categories.keys())
    cat_values = list(positive_categories.values())

    if cat_values:
        # Shorten category names for display
        cat_names_short = [
            name[:30] + "..." if len(name) > 30 else name for name in cat_names
        ]

        wedges, texts, autotexts = ax2.pie(
            cat_values,
            labels=cat_names_short,
            autopct="%1.1f%%",
            startangle=90,
            colors=colors[:len(cat_values)],  # Dynamic color count
            textprops={"fontsize": 9},
        )
        for autotext in autotexts:
            autotext.set_color("white")
            autotext.set_fontweight("bold")
            autotext.set_fontsize(11)

        ax2.set_title(
            "Sales Distribution by Category", fontsize=14, fontweight="bold", pad=15
        )
    else:
        # Handle case with no positive data
        ax2.text(
            0.5, 0.5,
            "No positive\ncategory data\navailable",
            ha="center", va="center",
            transform=ax2.transAxes,
            fontsize=12
        )
        ax2.set_title(
            "Sales Distribution by Category", fontsize=14, fontweight="bold", pad=15
        )

    # ============================================================================
    # 4. Customer Concentration (Bar Chart)
    # ============================================================================
    ax3 = fig.add_subplot(gs[2, 1])
    top_customers_list = customers.get("top_customers", [])[:3]
    customer_names = [c["customer_name"] for c in top_customers_list]
    customer_revenue = [c["total_revenue"] for c in top_customers_list]

    if customer_names:
        x_pos = np.arange(len(customer_names))
        bars = ax3.bar(
            x_pos, customer_revenue, color=colors[1], alpha=0.8, edgecolor="black"
        )
        ax3.set_xticks(x_pos)
        ax3.set_xticklabels(
            [
                name.split()[0] + "\n" + " ".join(name.split()[1:])
                for name in customer_names
            ],
            fontsize=8,
            rotation=0,
        )
        ax3.set_ylabel("Total Revenue ($)", fontsize=12, fontweight="bold")
        ax3.set_title(
            "Top 3 Customers by Revenue", fontsize=14, fontweight="bold", pad=15
        )
        ax3.grid(axis="y", alpha=0.3)

        # Add value labels on bars
        for bar, value in zip(bars, customer_revenue):
            height = bar.get_height()
            ax3.text(
                bar.get_x() + bar.get_width() / 2.0,
                height + 2000,
                f"${value:,.2f}",
                ha="center",
                va="bottom",
                fontsize=9,
                fontweight="bold",
            )

    # ============================================================================
    # 5. Category Performance Analysis
    # ============================================================================
    ax4 = fig.add_subplot(gs[3, :])
    category_performance = categories.get("category_performance", [])[
        :5
    ]  # Top 5 categories
    cat_names_perf = [
        (
            c["category_name"][:20] + "..."
            if len(c["category_name"]) > 20
            else c["category_name"]
        )
        for c in category_performance
    ]
    cat_revenues = [c["total_revenue"] for c in category_performance]
    cat_costs = [c["total_cost"] for c in category_performance]
    cat_margins = [c["profit_margin"] for c in category_performance]

    if cat_names_perf:
        x = np.arange(len(cat_names_perf))
        width = 0.25

        bars1 = ax4.bar(
            x - width,
            cat_revenues,
            width,
            label="Revenue",
            color=colors[0],
            alpha=0.8,
            edgecolor="black",
        )
        bars2 = ax4.bar(
            x,
            cat_costs,
            width,
            label="Cost",
            color=colors[3],
            alpha=0.8,
            edgecolor="black",
        )
        bars3 = ax4.bar(
            x + width,
            [m * 5000 for m in cat_margins],
            width,
            label="Margin (scaled)",
            color=colors[4],
            alpha=0.8,
            edgecolor="black",
        )

        ax4.set_xlabel("Categories", fontsize=12, fontweight="bold")
        ax4.set_ylabel("Amount ($)", fontsize=12, fontweight="bold")
        ax4.set_title(
            "Category Performance: Revenue vs Cost",
            fontsize=14,
            fontweight="bold",
            pad=15,
        )
        ax4.set_xticks(x)
        ax4.set_xticklabels(cat_names_perf, fontsize=11)
        ax4.legend(fontsize=10, loc="upper left")
        ax4.grid(axis="y", alpha=0.3)

        # Add margin percentages on top
        for i, (bar, margin) in enumerate(zip(bars3, cat_margins)):
            color = "green" if margin > 0 else "red"
            ax4.text(
                bar.get_x() + bar.get_width() / 2.0,
                bar.get_height() + 10000,
                f"{margin:.1f}%",
                ha="center",
                va="bottom",
                fontsize=10,
                fontweight="bold",
                color=color,
            )

    # ============================================================================
    # 6. Profit Margin Analysis
    # ============================================================================
    ax5 = fig.add_subplot(gs[4, 0])
    margin_values = cat_margins if cat_names_perf else []
    colors_margins = ["green" if m > 0 else "red" for m in margin_values]

    if margin_values:
        y_pos = np.arange(len(cat_names_perf))
        bars = ax5.barh(
            y_pos, margin_values, color=colors_margins, alpha=0.7, edgecolor="black"
        )
        ax5.set_yticks(y_pos)
        ax5.set_yticklabels(cat_names_perf, fontsize=11)
        ax5.set_xlabel("Profit Margin (%)", fontsize=12, fontweight="bold")
        ax5.set_title("Category Profit Margins", fontsize=14, fontweight="bold", pad=15)
        ax5.axvline(x=0, color="black", linestyle="--", linewidth=1)
        ax5.grid(axis="x", alpha=0.3)

        # Add value labels
        for bar, value in zip(bars, margin_values):
            x_pos = value + (2 if value > 0 else -2)
            ha = "left" if value > 0 else "right"
            ax5.text(
                x_pos,
                bar.get_y() + bar.get_height() / 2,
                f"{value:.1f}%",
                va="center",
                ha=ha,
                fontsize=10,
                fontweight="bold",
            )

    # ============================================================================
    # 7. Revenue Breakdown Analysis
    # ============================================================================
    ax6 = fig.add_subplot(gs[4, 1])
    revenue_breakdown = {
        "Sales Revenue": revenue_without_iva,
        "IVA (Tax)": revenue_with_iva - revenue_without_iva,
    }

    bars = ax6.bar(
        revenue_breakdown.keys(),
        revenue_breakdown.values(),
        color=[colors[0], colors[2]],
        alpha=0.8,
        edgecolor="black",
    )
    ax6.set_ylabel("Amount ($)", fontsize=12, fontweight="bold")
    ax6.set_title("Revenue Breakdown", fontsize=14, fontweight="bold", pad=15)
    ax6.grid(axis="y", alpha=0.3)

    for bar, value in zip(bars, revenue_breakdown.values()):
        height = bar.get_height()
        ax6.text(
            bar.get_x() + bar.get_width() / 2.0,
            height / 2,
            f"${value:,.2f}\n({value/revenue_with_iva*100:.1f}%)",
            ha="center",
            va="center",
            fontsize=10,
            fontweight="bold",
            color="white",
        )

    # ============================================================================
    # 8. Key Insights and Recommendations
    # ============================================================================
    ax7 = fig.add_subplot(gs[5, :])
    ax7.axis("off")

    recommendations = analysis.get("strategic_recommendations", [])
    total_records = analysis["analysis_metadata"]["total_records"]

    insights_text = f"""
KEY BUSINESS INSIGHTS & RECOMMENDATIONS

📊 PERFORMANCE SUMMARY:
• Total Records Analyzed: {total_records}
• Total Revenue (with IVA): ${revenue_with_iva:,.2f}
• Total Revenue (without IVA): ${revenue_without_iva:,.2f}
• Average Order Value: ${avg_order_value:,.2f}
• Total Customers: {customers.get('total_customers', 0)}
• Total Products: {products.get('total_products', 0)}

⚠️ CRITICAL ISSUES:
"""

    # Add critical recommendations
    critical_found = False
    for rec in recommendations:
        if "CRITICAL" in rec or "URGENT" in rec:
            insights_text += f"• {rec}\n"
            critical_found = True

    if not critical_found:
        insights_text += "• No critical issues identified\n"

    insights_text += "\n✅ STRENGTHS:\n"
    strengths_found = False
    for rec in recommendations:
        if "star products" in rec.lower() or "increase inventory" in rec.lower():
            insights_text += f"• {rec}\n"
            strengths_found = True

    if not strengths_found:
        insights_text += "• Strong product portfolio identified\n"

    insights_text += "\n🎯 STRATEGIC RECOMMENDATIONS:\n"
    for i, rec in enumerate(recommendations[:5], 1):
        insights_text += f"{i}. {rec}\n"

    insights_text += "\n💻 MAGENTO ECOMMERCE ACTIONS:\n"
    magento = analysis.get("magento_integration_strategies", {})
    if magento.get("product_catalog_optimization"):
        top_products_names = magento["product_catalog_optimization"][0].get(
            "products", []
        )[:3]
        insights_text += f"• Feature top products: {', '.join(top_products_names)}\n"
    insights_text += "• Implement customer segmentation for personalized pricing\n"
    insights_text += "• Enable B2B quick order functionality\n"

    ax7.text(
        0.05,
        0.95,
        insights_text,
        transform=ax7.transAxes,
        fontsize=10,
        verticalalignment="top",
        family="monospace",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.3),
    )

    # Save the comprehensive analysis
    plt.savefig(str(output_path), dpi=Config.REPORT_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)  # Close to free memory

    logger.info(f"✅ Visualization report saved to {output_path}")
    return str(output_path)


def print_detailed_statistics(analysis: Dict[str, Any]):
    """Print comprehensive business statistics"""
    metrics = analysis["calculated_metrics"]
    financial = metrics["financial_metrics"]
    customers = metrics["customer_analytics"]
    products = metrics["product_analytics"]
    categories = metrics["category_analytics"]
    trends = metrics["trend_analytics"]
    recommendations = analysis.get("strategic_recommendations", [])

    print(f"\n{'='*80}")
    print("DETAILED BUSINESS STATISTICS")
    print("=" * 80)

    print(f"\n📈 REVENUE METRICS:")
    revenue_with_iva = financial["revenue"]["total_with_iva"]
    revenue_without_iva = financial["revenue"]["total_without_iva"]
    avg_order_value = financial["revenue"]["average_order_value"]
    print(f"   Total Revenue (with IVA):    ${revenue_with_iva:>15,.2f}")
    print(f"   Total Revenue (without IVA): ${revenue_without_iva:>15,.2f}")
    print(
        f"   IVA Collected:               ${revenue_with_iva - revenue_without_iva:>15,.2f}"
    )
    print(f"   Average Order Value:         ${avg_order_value:>15,.2f}")

    print(f"\n🏆 TOP PRODUCTS:")
    top_products_list = products.get("top_products", [])[:5]
    for i, prod in enumerate(top_products_list, 1):
        # P0 FIX: Use safe_divide
        pct = safe_divide(prod["total_revenue"], revenue_with_iva, default=0) * 100
        print(f"   {i}. {prod['product_name'][:60]}")
        print(f"      Revenue: ${prod['total_revenue']:,.2f} ({pct:.1f}% of total)")

    print(f"\n👥 TOP CUSTOMERS:")
    top_customers_list = customers.get("top_customers", [])[:5]
    total_top_customers = sum(c["total_revenue"] for c in top_customers_list)
    for i, cust in enumerate(top_customers_list, 1):
        # P0 FIX: Use safe_divide
        pct = safe_divide(cust["total_revenue"], revenue_with_iva, default=0) * 100
        print(f"   {i}. {cust['customer_name']}")
        print(f"      Revenue: ${cust['total_revenue']:,.2f} ({pct:.1f}% of total)")
    # P0 FIX: Use safe_divide
    combined_pct = safe_divide(total_top_customers, revenue_with_iva, default=0) * 100
    print(
        f"   Combined Top 5: ${total_top_customers:,.2f} ({combined_pct:.1f}% of total)"
    )

    print(f"\n🏭 CATEGORY PERFORMANCE:")
    category_performance = categories.get("category_performance", [])[:5]
    for category in category_performance:
        # P0 FIX: Use safe_divide
        pct = safe_divide(category["total_revenue"], revenue_with_iva, default=0) * 100
        print(f"   {category['category_name'][:50]}")
        print(f"      Revenue: ${category['total_revenue']:,.2f} ({pct:.1f}%)")
        print(f"      Profit Margin: {category['profit_margin']:.1f}%")
        if category["profit_margin"] < 0:
            print(f"      ⚠️  WARNING: NEGATIVE MARGIN")

    print(f"\n💡 KEY RECOMMENDATIONS:")
    for i, rec in enumerate(recommendations[:5], 1):
        print(f"   {i}. {rec}")

    print("\n" + "=" * 80)


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Enhanced business data analyzer with visualization"
    )
    parser.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--limit", type=int, default=None, help=f"Max rows (default: {Config.DEFAULT_LIMIT})"
    )
    parser.add_argument("--ncx-file", help="Path to Navicat NCX connections file")
    parser.add_argument(
        "--generate-report", action="store_true", help="Generate visualization report"
    )
    parser.add_argument("--report-output", help="Output path for visualization report")
    parser.add_argument(
        "--skip-analysis",
        action="store_true",
        help="Skip data analysis (use existing JSON)",
    )

    args = parser.parse_args()

    try:
        # P0 FIX #3: Validate CLI arguments
        logger.info("Validating input parameters...")

        # Validate dates if provided
        if args.start_date or args.end_date:
            if not (args.start_date and args.end_date):
                raise ValueError(
                    "Both --start-date and --end-date must be provided together"
                )
            validate_date_range(args.start_date, args.end_date)
            logger.info(f"✓ Date range validated: {args.start_date} to {args.end_date}")

        # Validate limit if provided
        if args.limit is not None:
            validate_limit(args.limit)
            logger.info(f"✓ Limit validated: {args.limit:,} records")

        # Validate configuration
        Config.validate()

        # Get database connection details
        if Config.has_direct_db_config():
            logger.info("Using direct database configuration from environment")
            conn_details = {
                "Host": Config.DB_HOST,
                "Port": Config.DB_PORT,
                "UserName": Config.DB_USER,
                "Password": Config.DB_PASSWORD,
                "Database": Config.DB_NAME,
            }
        else:
            # Use NCX file
            ncx_path = args.ncx_file if args.ncx_file else Config.NCX_FILE_PATH
            logger.info(f"Loading database configuration from NCX file: {ncx_path}")
            connections = load_connections(ncx_path)
            if not connections:
                raise ValueError(f"No valid connections found in {ncx_path}")
            conn_details = connections[0]

        analysis = None

        if not args.skip_analysis:
            # Fetch data
            logger.info(f"Fetching data from {Config.DB_TABLE}...")
            data = fetch_banco_datos(
                conn_details,
                limit=args.limit,
                start_date=args.start_date,
                end_date=args.end_date
            )

            if not data:
                logger.warning("No data retrieved.")
                return

            logger.info(f"✓ Fetched {len(data)} rows")

            # Calculate date range if not provided
            if not args.start_date or not args.end_date:
                dates = [row["Fecha"] for row in data if row.get("Fecha")]
                if dates:
                    min_date = min(dates)
                    max_date = max(dates)
                    actual_start_date = (
                        min_date.strftime("%Y-%m-%d")
                        if hasattr(min_date, "strftime")
                        else str(min_date)
                    )
                    actual_end_date = (
                        max_date.strftime("%Y-%m-%d")
                        if hasattr(max_date, "strftime")
                        else str(max_date)
                    )
                else:
                    actual_start_date = "No dates found"
                    actual_end_date = "No dates found"
            else:
                actual_start_date = args.start_date
                actual_end_date = args.end_date

            # Calculate metrics
            logger.info("Calculating comprehensive metrics...")
            calculator = BusinessMetricsCalculator(data)
            metrics = calculator.calculate_all_metrics()

            # Generate recommendations
            logger.info("Generating recommendations...")
            recommendations = generate_recommendations(metrics)

            # Generate Magento strategies
            logger.info("Generating Magento strategies...")
            magento_strategies = generate_magento_strategies(metrics)

            # Combine results
            analysis = {
                "analysis_metadata": {
                    "generated_date": datetime.now().isoformat(),
                    "total_records": len(data),
                    "data_period": {
                        "start_date": actual_start_date,
                        "end_date": actual_end_date,
                    },
                },
                "calculated_metrics": metrics,
                "strategic_recommendations": recommendations,
                "magento_integration_strategies": magento_strategies,
            }

            # Save analysis to JSON
            Config.ensure_output_dir()
            if (
                actual_start_date != "No dates found"
                and actual_end_date != "No dates found"
            ):
                json_output_file = Config.OUTPUT_DIR / f"analysis_comprehensive_{actual_start_date}_to_{actual_end_date}.json"
            else:
                json_output_file = Config.OUTPUT_DIR / "analysis_comprehensive.json"

            json_output_file = str(json_output_file)

            with open(json_output_file, "w", encoding="utf-8") as f:
                json.dump(analysis, f, indent=2, ensure_ascii=False, cls=DecimalEncoder)

            logger.info(f"✓ Analysis saved to {json_output_file}")

        else:
            # Load existing analysis
            output_dir = Config.ensure_output_dir()
            json_files = [
                f
                for f in os.listdir(output_dir)
                if f.startswith("analysis_comprehensive") and f.endswith(".json")
            ]
            if json_files:
                latest_file = max(
                    json_files,
                    key=lambda x: os.path.getctime(output_dir / x),
                )
                json_path = output_dir / latest_file
                logger.info(f"Loading existing analysis from {json_path}")
                with open(json_path, "r", encoding="utf-8") as f:
                    analysis = json.load(f)
            else:
                logger.error(
                    f"No existing analysis files found in {output_dir}. Run without --skip-analysis first."
                )
                return

        # Print summary
        print(f"\n{'='*80}")
        print("COMPREHENSIVE ANALYSIS COMPLETED")
        print(f"{'='*80}")
        print(f"\n📊 Results Summary:")
        print(f"   • Total Records: {analysis['analysis_metadata']['total_records']}")
        print(
            f"   • Total Customers: {analysis['calculated_metrics']['customer_analytics']['total_customers']}"
        )
        print(
            f"   • Total Products: {analysis['calculated_metrics']['product_analytics']['total_products']}"
        )
        print(
            f"   • Total Categories: {analysis['calculated_metrics']['category_analytics']['total_categories']}"
        )
        print(f"\n💡 Top Recommendations:")
        recommendations = analysis.get("strategic_recommendations", [])
        for i, rec in enumerate(recommendations[:3], 1):
            print(f"   {i}. {rec}")
        print(f"\n{'='*80}\n")

        # Generate visualization report automatically if matplotlib is available
        if MATPLOTLIB_AVAILABLE:
            logger.info("Generating visualization report...")
            report_path = generate_visualization_report(analysis, args.report_output)
            if report_path:
                print(f"✅ Visualization report saved to: {report_path}")
                # Print detailed statistics
                print_detailed_statistics(analysis)
            else:
                print("⚠️  Visualization report generation failed")
        else:
            print(
                "📊 Analysis complete! For enhanced visualization reports, install matplotlib:"
            )
            print("   pip install matplotlib numpy")
            print("   # or on Arch Linux:")
            print("   sudo pacman -S python-matplotlib python-numpy")
            print()
            # Print basic statistics even without matplotlib
            print_detailed_statistics(analysis)

        # Still allow manual generation even if matplotlib not available (for future compatibility)
        if args.generate_report and not MATPLOTLIB_AVAILABLE:
            print("❌ Cannot generate visualization report - matplotlib not installed")
            print("   Install with: pip install matplotlib numpy")

    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
