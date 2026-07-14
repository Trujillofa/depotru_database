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

import argparse
import json
import logging
import os
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from .analytics.category_metrics import analyze_categories as analyze_categories_core
from .analytics.customer_metrics import analyze_customers as analyze_customers_core
from .analytics.financial_metrics import (
    calculate_financial_metrics as calculate_financial_metrics_core,
)
from .analytics.inventory_metrics import analyze_inventory as analyze_inventory_core
from .analytics.product_metrics import analyze_products as analyze_products_core
from .analytics.profitability_metrics import (
    analyze_profitability as analyze_profitability_core,
)
from .analytics.risk_efficiency_metrics import (
    calculate_operational_efficiency as calculate_operational_efficiency_core,
)
from .analytics.risk_efficiency_metrics import (
    calculate_risk_metrics as calculate_risk_metrics_core,
)
from .analytics.trend_metrics import analyze_trends as analyze_trends_core

# Import configuration
from .config import Config, CustomerSegmentation, InventoryConfig, ProfitabilityConfig
from .contracts.row_contracts import extract_row_value
from .data_access import fetch_banco_datos, resolve_connection_details
from .reporting import MATPLOTLIB_AVAILABLE
from .reporting import (
    generate_visualization_report as generate_visualization_report_core,
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

if MATPLOTLIB_AVAILABLE:
    logger.info("Matplotlib available for visualizations")
else:
    logger.warning("Matplotlib not available - visualizations will be skipped")


# Custom JSON encoder for Decimal and datetime types
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return super(DecimalEncoder, self).default(o)


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

    def _extract_value(self, row: dict, keys: list, default=None) -> Any:
        """Extract value from row using multiple possible keys"""
        return extract_row_value(row, keys, default=default)

    def calculate_financial_metrics(self) -> Dict[str, Any]:
        """Calculate comprehensive financial KPIs"""
        return calculate_financial_metrics_core(self.data)

    def analyze_customers(self) -> Dict[str, Any]:
        """Comprehensive customer analytics"""
        return analyze_customers_core(
            self.data,
            self._extract_value,
            self._segment_customer,
            self._aggregate_segments,
            safe_divide,
        )

    def _segment_customer(self, revenue: float, orders: int) -> str:
        """Segment customer based on revenue and order frequency"""
        if (
            revenue > CustomerSegmentation.VIP_REVENUE_THRESHOLD
            and orders > CustomerSegmentation.VIP_ORDERS_THRESHOLD
        ):
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
        return analyze_products_core(
            self.data,
            self._extract_value,
            safe_divide,
            ProfitabilityConfig.LOW_MARGIN_THRESHOLD,
            ProfitabilityConfig.STAR_PRODUCT_MARGIN,
        )

    def analyze_categories(self) -> Dict[str, Any]:
        """Comprehensive category and subcategory analytics"""
        return analyze_categories_core(self.data, self._extract_value, safe_divide)

    def analyze_inventory(self) -> Dict[str, Any]:
        """Inventory optimization analytics"""
        return analyze_inventory_core(
            self.data,
            self._extract_value,
            InventoryConfig.FAST_MOVER_THRESHOLD,
            InventoryConfig.SLOW_MOVER_THRESHOLD,
        )

    def analyze_trends(self) -> Dict[str, Any]:
        """Trend and seasonality analysis"""
        return analyze_trends_core(self.data, self._extract_value)

    def analyze_profitability(self) -> Dict[str, Any]:
        """Deep profitability analysis"""
        return analyze_profitability_core(self.data, self._extract_value, safe_divide)

    def calculate_risk_metrics(self) -> Dict[str, Any]:
        """Calculate business risk metrics"""
        return calculate_risk_metrics_core()

    def calculate_operational_efficiency(self) -> Dict[str, Any]:
        """Calculate operational efficiency metrics"""
        return calculate_operational_efficiency_core(self.data, self._extract_value)


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
    analysis: Dict[str, Any], output_path: Optional[str] = None
) -> Optional[str]:
    return generate_visualization_report_core(analysis, output_path)


def print_detailed_statistics(analysis: Dict[str, Any]):
    """Print comprehensive business statistics"""
    metrics = analysis["calculated_metrics"]
    financial = metrics["financial_metrics"]
    customers = metrics["customer_analytics"]
    products = metrics["product_analytics"]
    categories = metrics["category_analytics"]
    recommendations = analysis.get("strategic_recommendations", [])

    print(f"\n{'=' * 80}")
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
        "--limit",
        type=int,
        default=None,
        help=f"Max rows (default: {Config.DEFAULT_LIMIT})",
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

        conn_details = resolve_connection_details(args.ncx_file)

        analysis = None

        if not args.skip_analysis:
            # Fetch data
            logger.info(f"Fetching data from {Config.DB_TABLE}...")
            data = fetch_banco_datos(
                conn_details,
                limit=args.limit,
                start_date=args.start_date,
                end_date=args.end_date,
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
                json_output_file = (
                    Config.OUTPUT_DIR
                    / f"analysis_comprehensive_{actual_start_date}_to_{actual_end_date}.json"
                )
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
        print(f"\n{'=' * 80}")
        print("COMPREHENSIVE ANALYSIS COMPLETED")
        print(f"{'=' * 80}")
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
        print(f"\n{'=' * 80}\n")

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
