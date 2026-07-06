"""Tests for SQL aggregation row mappers."""

from business_analyzer.analysis.manager_report.aggregations import (
    abc_buckets_from_sql,
    category_breakdown_from_sql,
    customer_vendor_mix_from_sql,
    daily_trend_from_sql,
    marca_sales_from_sql,
    sku_monthly_sales_from_sql,
    summary_from_sql,
    top_customers_from_sql,
    top_products_from_sql,
    vendor_sales_from_sql,
    ytd_customer_products_from_sql,
)


def test_summary_from_sql_maps_totals():
    result = summary_from_sql(
        {
            "total_with_iva": 121000.0,
            "total_without_iva": 100000.0,
            "total_cost": 70000.0,
            "total_quantity": 10,
            "order_count": 2,
        }
    )
    assert result["total_revenue_with_iva"] == 121000.0
    assert result["gross_profit"] == 30000.0
    assert result["order_count"] == 2


def test_top_products_from_sql():
    rows = [
        {
            "product_name": "Producto B",
            "sku": "SKU002",
            "total_revenue": 250000.0,
            "total_cost": 150000.0,
            "total_quantity": 20,
            "transactions": 2,
        }
    ]
    result = top_products_from_sql(rows)
    assert result[0]["product_name"] == "Producto B"
    assert result[0]["profit_margin_pct"] == 40.0


def test_top_customers_from_sql():
    rows = [
        {
            "customer_name": "Cliente A",
            "total_revenue": 200000.0,
            "total_cost": 120000.0,
            "total_quantity": 15,
            "total_orders": 3,
        }
    ]
    result = top_customers_from_sql(rows)
    assert result[0]["customer_name"] == "Cliente A"
    assert result[0]["average_order_value"] > 0


def test_category_breakdown_from_sql():
    rows = [
        {
            "categoria": "Herramientas",
            "subcategoria": "Manuales",
            "total_revenue": 100000.0,
            "total_cost": 60000.0,
            "total_quantity": 10,
            "transactions": 4,
        }
    ]
    result = category_breakdown_from_sql(rows)
    assert result[0]["category_path"] == "Herramientas > Manuales"


def test_daily_trend_from_sql():
    rows = [
        {
            "sale_date": "2024-05-01",
            "revenue_with_iva": 121000.0,
            "revenue_without_iva": 100000.0,
            "cost": 70000.0,
            "quantity": 10,
            "orders": 2,
        }
    ]
    result = daily_trend_from_sql(rows)
    assert result[0]["date"] == "2024-05-01"
    assert result[0]["profit"] == 30000.0


def test_vendor_sales_from_sql():
    rows = [
        {
            "vendor_name": "PROV1",
            "total_revenue": 100000.0,
            "total_cost": 60000.0,
            "total_quantity": 10,
            "transactions": 2,
        },
        {
            "vendor_name": "PROV2",
            "total_revenue": 50000.0,
            "total_cost": 30000.0,
            "total_quantity": 5,
            "transactions": 1,
        },
    ]
    result = vendor_sales_from_sql(rows)
    assert result[0]["vendor_name"] == "PROV1"
    assert result[0]["revenue_pct"] == 66.7


def test_marca_sales_from_sql():
    rows = [
        {
            "marca_name": "SIKA",
            "total_revenue": 80000.0,
            "total_cost": 50000.0,
            "total_quantity": 8,
            "transactions": 3,
        }
    ]
    result = marca_sales_from_sql(rows)
    assert result[0]["marca_name"] == "SIKA"
    assert result[0]["profit"] == 30000.0


def test_customer_vendor_mix_from_sql():
    rows = [
        {
            "customer_name": "Cliente A",
            "vendor_name": "PROV1",
            "revenue": 100000.0,
            "transactions": 2,
        },
        {
            "customer_name": "Cliente A",
            "vendor_name": "PROV2",
            "revenue": 50000.0,
            "transactions": 1,
        },
    ]
    result = customer_vendor_mix_from_sql(rows)
    assert result[0]["customer_name"] == "Cliente A"
    assert result[0]["vendor_count"] == 2
    assert len(result[0]["top_vendors"]) == 2


def test_abc_buckets_from_sql():
    rows = [
        {"entity_name": "A", "total_revenue": 800.0},
        {"entity_name": "B", "total_revenue": 150.0},
        {"entity_name": "C", "total_revenue": 50.0},
    ]
    result = abc_buckets_from_sql(rows)
    assert result["a"]["count"] >= 1
    assert result["total"] == 3


def test_ytd_customer_products_from_sql():
    products = [
        {
            "customer_name": "Cliente A",
            "sku": "SKU001",
            "product_name": "Prod A",
            "quantity": 12,
            "revenue": 1200.0,
            "last_purchase": "2024-05-02",
            "marca": "SIKA",
        }
    ]
    vendors = [
        {
            "customer_name": "Cliente A",
            "sku": "SKU001",
            "primary_vendor": "PROV1",
        }
    ]
    ytd = ytd_customer_products_from_sql(products, vendors)
    assert ytd["Cliente A"]["SKU001"]["quantity"] == 12
    assert ytd["Cliente A"]["SKU001"]["primary_vendor"] == "PROV1"


def test_sku_monthly_sales_from_sql():
    rows = [
        {"sku": "SKU001", "product_name": "Prod A", "quantity": 10, "revenue": 1000.0}
    ]
    result = sku_monthly_sales_from_sql(rows)
    assert result["SKU001"]["quantity"] == 10
