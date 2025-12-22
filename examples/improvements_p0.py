"""
Priority 0 (Critical) Improvements
==================================
These fixes should be applied immediately to prevent production failures.

Issues addressed:
1. Database connection leak
2. Division by zero crashes
3. Missing input validation
"""

import pymssql
from datetime import datetime
from typing import Dict, Any, List, Tuple


# ============================================================================
# Fix #1: Safe Database Connection with proper cleanup
# ============================================================================

def fetch_banco_datos_safe(
    conn_details: Dict[str, Any],
    limit: int = 1000,
    start_date: str = None,
    end_date: str = None
) -> List[Dict[str, Any]]:
    """
    Fetch data with proper connection handling.

    CRITICAL FIX: Ensures connection is always closed, even on error.
    """
    conn = None
    try:
        conn = pymssql.connect(
            server=conn_details["Host"],
            port=conn_details["Port"],
            user=conn_details["UserName"],
            password=conn_details["Password"],
            database="SmartBusiness",
            login_timeout=10,
            timeout=10,
        )

        cursor = conn.cursor(as_dict=True)

        # Build query
        query = "SELECT TOP %s * FROM banco_datos WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')"
        params = [limit]

        if start_date and end_date:
            query += " AND Fecha BETWEEN %s AND %s"
            params.extend([start_date, end_date])

        cursor.execute(query, tuple(params))
        data = list(cursor)

        return data

    except pymssql.OperationalError as e:
        if "timeout" in str(e).lower():
            print(f"❌ Database connection timeout. Check network connectivity.")
        raise
    except pymssql.Error as e:
        print(f"❌ Database error: {e}")
        raise
    finally:
        # CRITICAL: Always close connection
        if conn:
            conn.close()
            print("✓ Database connection closed safely")


# ============================================================================
# Fix #2: Safe Division Helper
# ============================================================================

def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Perform division with zero-check.

    CRITICAL FIX: Prevents division by zero crashes.

    Examples:
        >>> safe_divide(100, 50)
        2.0
        >>> safe_divide(100, 0)
        0.0
        >>> safe_divide(100, 0, default=-1)
        -1.0
    """
    return numerator / denominator if denominator != 0 else default


def calculate_profit_margin_safe(revenue: float, cost: float) -> Dict[str, float]:
    """
    Calculate profit and margin with safe division.

    CRITICAL FIX: Handles zero revenue without crashing.
    """
    profit = revenue - cost
    margin = safe_divide(profit, revenue, default=0.0) * 100

    return {
        "profit": round(profit, 2),
        "margin": round(margin, 2)
    }


# Example usage in financial metrics
def calculate_financial_metrics_safe(data: List[Dict]) -> Dict[str, Any]:
    """Fixed version of financial metrics calculation"""
    revenues_with_iva = []
    revenues_without_iva = []
    costs = []

    for row in data:
        if "TotalMasIva" in row and row["TotalMasIva"]:
            revenues_with_iva.append(float(row["TotalMasIva"]))
        if "TotalSinIva" in row and row["TotalSinIva"]:
            revenues_without_iva.append(float(row["TotalSinIva"]))
        if "ValorCosto" in row and row["ValorCosto"]:
            costs.append(float(row["ValorCosto"]))

    total_revenue = sum(revenues_without_iva)
    total_cost = sum(costs)

    # CRITICAL FIX: Use safe division
    metrics = calculate_profit_margin_safe(total_revenue, total_cost)

    # CRITICAL FIX: Safe average calculation
    avg_order = safe_divide(
        sum(revenues_with_iva),
        len(revenues_with_iva),
        default=0.0
    )

    return {
        "revenue": {
            "total_with_iva": round(sum(revenues_with_iva), 2),
            "total_without_iva": round(total_revenue, 2),
            "average_order_value": round(avg_order, 2),
        },
        "costs": {
            "total_cost": round(total_cost, 2),
        },
        "profit": metrics
    }


# ============================================================================
# Fix #3: Input Validation
# ============================================================================

def validate_date_range(start_date: str, end_date: str) -> Tuple[datetime, datetime]:
    """
    Validate and parse date inputs.

    CRITICAL FIX: Prevents cryptic errors from invalid dates.

    Args:
        start_date: Date string in YYYY-MM-DD format
        end_date: Date string in YYYY-MM-DD format

    Returns:
        Tuple of (start_datetime, end_datetime)

    Raises:
        ValueError: If dates are invalid or in wrong order
    """
    if not start_date or not end_date:
        raise ValueError("Both start_date and end_date are required")

    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(
            f"Invalid start_date format: '{start_date}'. "
            f"Use YYYY-MM-DD format (e.g., 2025-01-15)"
        ) from e

    try:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(
            f"Invalid end_date format: '{end_date}'. "
            f"Use YYYY-MM-DD format (e.g., 2025-01-15)"
        ) from e

    if start_dt > end_dt:
        raise ValueError(
            f"start_date ({start_date}) must be before or equal to "
            f"end_date ({end_date})"
        )

    # Check if dates are reasonable (not too far in past/future)
    current_year = datetime.now().year
    if start_dt.year < 2000 or start_dt.year > current_year + 1:
        raise ValueError(
            f"start_date year ({start_dt.year}) seems unreasonable. "
            f"Expected between 2000 and {current_year + 1}"
        )

    return start_dt, end_dt


def validate_limit(limit: int) -> int:
    """
    Validate record limit parameter.

    CRITICAL FIX: Prevents memory issues from excessive limits.
    """
    if limit is None:
        return 1000  # Default

    if not isinstance(limit, int):
        raise ValueError(f"limit must be an integer, got {type(limit).__name__}")

    if limit < 1:
        raise ValueError(f"limit must be at least 1, got {limit}")

    if limit > 1_000_000:
        raise ValueError(
            f"limit ({limit:,}) exceeds maximum (1,000,000). "
            f"Use smaller limit to prevent memory issues."
        )

    return limit


def validate_cli_arguments(args) -> None:
    """
    Validate all CLI arguments.

    CRITICAL FIX: Comprehensive validation before processing.
    """
    errors = []

    # Validate dates
    if args.start_date or args.end_date:
        if not (args.start_date and args.end_date):
            errors.append(
                "Both --start-date and --end-date must be provided together"
            )
        else:
            try:
                validate_date_range(args.start_date, args.end_date)
            except ValueError as e:
                errors.append(str(e))

    # Validate limit
    if args.limit is not None:
        try:
            validate_limit(args.limit)
        except ValueError as e:
            errors.append(str(e))

    # Report all errors at once
    if errors:
        error_msg = "Validation errors:\n" + "\n".join(f"  • {err}" for err in errors)
        raise ValueError(error_msg)


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    print("=== Priority 0 Fixes Demonstration ===\n")

    # Test 1: Safe division
    print("Test 1: Safe Division")
    print(f"  100 / 50 = {safe_divide(100, 50)}")
    print(f"  100 / 0 = {safe_divide(100, 0)} (no crash!)")
    print()

    # Test 2: Profit margin calculation
    print("Test 2: Profit Margin with Zero Revenue")
    result = calculate_profit_margin_safe(revenue=0, cost=100)
    print(f"  Revenue: $0, Cost: $100")
    print(f"  Result: {result} (no crash!)")
    print()

    # Test 3: Date validation
    print("Test 3: Date Validation")
    try:
        start, end = validate_date_range("2025-01-01", "2025-12-31")
        print(f"  ✓ Valid dates: {start.date()} to {end.date()}")
    except ValueError as e:
        print(f"  ✗ Error: {e}")

    try:
        validate_date_range("2025-12-31", "2025-01-01")
    except ValueError as e:
        print(f"  ✓ Caught invalid order: {e}")

    try:
        validate_date_range("invalid", "2025-12-31")
    except ValueError as e:
        print(f"  ✓ Caught invalid format: {e}")
    print()

    # Test 4: Limit validation
    print("Test 4: Limit Validation")
    try:
        print(f"  ✓ Valid limit: {validate_limit(5000)}")
    except ValueError as e:
        print(f"  ✗ Error: {e}")

    try:
        validate_limit(-1)
    except ValueError as e:
        print(f"  ✓ Caught negative limit: {e}")

    try:
        validate_limit(2_000_000)
    except ValueError as e:
        print(f"  ✓ Caught excessive limit: {e}")

    print("\n=== All P0 Fixes Demonstrated ===")
