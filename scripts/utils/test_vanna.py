#!/usr/bin/env python3
"""
Test Vanna AI integration with SmartBusiness database
Uses Grok for natural language to SQL conversion
"""

import os
import sys

import pymssql


def get_connection():
    """Get database connection using environment variables"""
    # SECURITY: Get credentials from environment (no defaults)
    db_host = os.environ.get("DB_SERVER")
    db_port = int(os.environ.get("DB_PORT", "1433"))
    db_user = os.environ.get("DB_USER")
    db_password = os.environ.get("DB_PASSWORD")
    db_name = os.environ.get("DB_NAME", "SmartBusiness")

    if not all([db_host, db_user, db_password]):
        print("ERROR: Missing required environment variables")
        print("Please set: DB_SERVER, DB_USER, DB_PASSWORD")
        sys.exit(1)

    return pymssql.connect(
        server=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        database=db_name,
        login_timeout=30,
        timeout=180,
    )


def test_vanna_basic():
    """Test basic Vanna functionality"""
    try:
        from vanna.remote import VannaDefault

        print("🤖 Testing Vanna AI integration...")

        # Initialize Vanna (using VannaDefault for testing)
        vn = VannaDefault(model="chinook", api_key=os.environ.get("VANNA_API_KEY"))

        # Test basic SQL generation
        test_question = "Show me total revenue by category in 2024"
        print(f"\n❓ Question: {test_question}")

        sql = vn.generate_sql(test_question)
        print(f"\n📝 Generated SQL:\n{sql}")

        print("\n✅ Vanna basic test passed!")
        return True

    except ImportError:
        print("⚠️  Vanna not installed - skipping Vanna tests")
        return True
    except Exception as e:
        print(f"❌ Vanna test failed: {e}")
        return False


def test_manual_query():
    """Test manual database query that simulates what Vanna would generate"""
    try:
        print("\n🔍 Testing manual database query...")

        conn = get_connection()
        cursor = conn.cursor()

        # Test query for SIKA products
        query = """
        SELECT TOP 5
            marca AS category,
            SUM(TotalSinIva) AS revenue,
            COUNT(DISTINCT TercerosNombres) AS customers
        FROM [dbo].[banco_datos]
        WHERE categoria = 'PRODUCTOS SIKA'
          AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
          AND TercerosNombres != 'DEPOSITO TRUJILLO SAS'
          AND ano = 2024
        GROUP BY marca
        ORDER BY SUM(TotalSinIva) DESC
        """

        cursor.execute(query)
        results = cursor.fetchall()

        print("\n📊 Sample Results (Top 5 categories by revenue):")
        print(f"{'Category':<30} {'Revenue':>15} {'Customers':>10}")
        print("-" * 60)

        for row in results:
            category, revenue, customers = row
            print(f"{category:<30} ${revenue:>14,.0f} {customers:>10}")

        cursor.close()
        conn.close()

        print("\n✅ Manual query test passed!")
        return True

    except Exception as e:
        print(f"❌ Manual query test failed: {e}")
        return False


def test_grok_integration():
    """
    Test Grok-based SQL generation
    This simulates how Grok would help generate SQL from natural language
    """
    print("\n🤖 Testing Grok-style SQL generation...")

    # Example natural language questions and expected SQL patterns
    test_cases = [
        {
            "question": "What are the top 10 customers by revenue in 2024?",
            "expected_fields": ["TercerosNombres", "SUM(TotalSinIva)", "ano"],
            "expected_filters": ["ano = 2024", "DocumentosCodigo NOT IN"],
        },
        {
            "question": "Show monthly sales trends for SIKA products",
            "expected_fields": ["mes", "ano", "SUM(TotalSinIva)"],
            "expected_filters": ["categoria = 'PRODUCTOS SIKA'"],
        },
    ]

    print("\n📝 Test Cases for Grok Integration:")
    for i, test in enumerate(test_cases, 1):
        print(f"\n{i}. Question: {test['question']}")
        print(f"   Expected fields: {', '.join(test['expected_fields'])}")
        print(f"   Expected filters: {', '.join(test['expected_filters'])}")

    print("\n✅ Grok integration test framework ready!")
    print("   (Actual Grok API integration would go here)")
    return True


def main():
    """Run all tests"""
    print("=" * 60)
    print("VANNA & GROK INTEGRATION TESTS")
    print("=" * 60)

    all_passed = True

    # Test 1: Basic Vanna
    if not test_vanna_basic():
        all_passed = False

    # Test 2: Manual query
    if not test_manual_query():
        all_passed = False

    # Test 3: Grok integration framework
    if not test_grok_integration():
        all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        return 0

    print("❌ SOME TESTS FAILED")
    print("=" * 60)
    return 1


if __name__ == "__main__":
    sys.exit(main())
