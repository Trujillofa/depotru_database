#!/usr/bin/env python3
"""Generate comprehensive PRODUCTOS SIKA markdown report with insights"""
import json

with open("reports/data/sika_analysis_report.json", "r") as f:
    data = json.load(f)

report = []

# HEADER
report.append("# PRODUCTOS SIKA - Comprehensive Business Analysis")
report.append(f"**Period:** 2024-2025 (Full Year)")
report.append(f"**Generated:** {data['generated_at']}")
report.append(f"**Filter:** `{data['filter']}`")
report.append("")
report.append("---")
report.append("")

# EXECUTIVE SUMMARY
report.append("## Executive Summary")
report.append("")

s24 = data["summary"].get("2024", {})
s25 = data["summary"].get("2025", {})

if s24 and s25:
    rev_growth = (s25["net_revenue"] - s24["net_revenue"]) / s24["net_revenue"] * 100
    profit_growth = (s25["net_profit"] - s24["net_profit"]) / s24["net_profit"] * 100
    cust_growth = (
        (s25["unique_customers"] - s24["unique_customers"])
        / s24["unique_customers"]
        * 100
    )

    report.append("### Key Highlights")
    report.append("")
    report.append(
        f"- **Revenue Growth:** {rev_growth:+.1f}% YoY (${s24['net_revenue']:,.0f} → ${s25['net_revenue']:,.0f})"
    )
    report.append(
        f"- **Profit Growth:** {profit_growth:+.1f}% YoY (${s24['net_profit']:,.0f} → ${s25['net_profit']:,.0f})"
    )
    report.append(
        f"- **Customer Growth:** {cust_growth:+.1f}% YoY ({int(s24['unique_customers']):,} → {int(s25['unique_customers']):,} customers)"
    )
    report.append(
        f"- **Margin Improvement:** {(s24['net_profit']/s24['net_revenue']*100):.1f}% → {(s25['net_profit']/s25['net_revenue']*100):.1f}%"
    )
    report.append("")

# YEARLY COMPARISON TABLE
report.append("## Yearly Performance Comparison")
report.append("")
report.append("| Metric | 2024 | 2025 | Change | % Change |")
report.append("|--------|------|------|--------|----------|")

if s24 and s25:
    metrics = [
        ("Revenue", "net_revenue", True),
        ("Profit", "net_profit", True),
        ("Profit Margin %", None, False),
        ("Customers", "unique_customers", False),
        ("Transactions", "transactions", False),
        ("Avg Transaction", "avg_transaction_value", True),
        ("Products Sold", "net_units", False),
        ("Returns", "returns", False),
    ]

    for label, key, is_currency in metrics:
        if key is None:  # Profit margin
            v24 = s24["net_profit"] / s24["net_revenue"] * 100
            v25 = s25["net_profit"] / s25["net_revenue"] * 100
            change = v25 - v24
            pct = (change / v24 * 100) if v24 else 0
            report.append(
                f"| {label} | {v24:.1f}% | {v25:.1f}% | {change:+.1f}pp | {pct:+.1f}% |"
            )
        else:
            v24 = s24[key]
            v25 = s25[key]
            change = v25 - v24
            pct = (change / v24 * 100) if v24 else 0

            if is_currency:
                report.append(
                    f"| {label} | ${v24:,.0f} | ${v25:,.0f} | ${change:,.0f} | {pct:+.1f}% |"
                )
            else:
                report.append(
                    f"| {label} | {v24:,.0f} | {v25:,.0f} | {change:,.0f} | {pct:+.1f}% |"
                )

report.append("")

# MONTHLY TRENDS
report.append("## Monthly Sales Trends")
report.append("")
report.append("### 2024 vs 2025 Monthly Comparison")
report.append("")
report.append(
    "| Month | 2024 Revenue | 2024 Customers | 2025 Revenue | 2025 Customers | Revenue Growth % |"
)
report.append(
    "|-------|--------------|----------------|--------------|----------------|------------------|"
)

month_names = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}

# Group by month
monthly_2024 = {int(m["month"]): m for m in data["monthly_sales"] if m["year"] == 2024}
monthly_2025 = {int(m["month"]): m for m in data["monthly_sales"] if m["year"] == 2025}

for month_num in range(1, 13):
    m24 = monthly_2024.get(month_num, {})
    m25 = monthly_2025.get(month_num, {})

    if m24 or m25:
        month = month_names[month_num]
        rev24 = m24.get("revenue", 0)
        cust24 = int(m24.get("customers", 0))
        rev25 = m25.get("revenue", 0)
        cust25 = int(m25.get("customers", 0))

        growth = ((rev25 - rev24) / rev24 * 100) if rev24 else 0

        r24_str = f"${rev24:,.0f}" if rev24 else "-"
        c24_str = f"{cust24:,}" if cust24 else "-"
        r25_str = f"${rev25:,.0f}" if rev25 else "-"
        c25_str = f"{cust25:,}" if cust25 else "-"
        g_str = f"{growth:+.1f}%" if rev24 and rev25 else "-"

        report.append(
            f"| {month} | {r24_str} | {c24_str} | {r25_str} | {c25_str} | {g_str} |"
        )

report.append("")

# CUSTOMER ANALYSIS
report.append("## Customer Analysis")
report.append("")

# Customer Segments
report.append("### Customer Segmentation")
report.append("")
report.append(
    "| Segment | Year | Customers | Revenue | Avg Revenue/Customer | % of Total Revenue |"
)
report.append(
    "|---------|------|-----------|---------|---------------------|-------------------|"
)

# Calculate total revenue by year for percentages
total_2024 = sum(
    s["segment_revenue"] for s in data["customer_segments"] if s["ano"] == 2024
)
total_2025 = sum(
    s["segment_revenue"] for s in data["customer_segments"] if s["ano"] == 2025
)

for seg in data["customer_segments"]:
    year = int(seg["ano"])
    total = total_2024 if year == 2024 else total_2025
    pct = (seg["segment_revenue"] / total * 100) if total else 0

    report.append(
        f"| {seg['segment']} | {year} | {int(seg['num_customers']):,} | "
        f"${seg['segment_revenue']:,.0f} | ${seg['avg_revenue_per_customer']:,.0f} | {pct:.1f}% |"
    )

report.append("")

# Top Customers
report.append("### Top 20 Customers by Revenue")
report.append("")
report.append("#### 2024 Top Customers")
report.append("")
report.append("| Rank | Customer | Orders | Revenue | Profit | Avg Order | Margin % |")
report.append("|------|----------|--------|---------|--------|-----------|----------|")

top_2024 = sorted(
    [c for c in data["top_customers"] if c["year"] == 2024],
    key=lambda x: x["total_revenue"],
    reverse=True,
)[:20]
for i, cust in enumerate(top_2024, 1):
    margin = (
        (cust["total_profit"] / cust["total_revenue"] * 100)
        if cust["total_revenue"]
        else 0
    )
    cust_name = (cust["customer_name"] or "Unknown")[:30]
    report.append(
        f"| {i} | {cust_name} | {int(cust['num_orders']):,} | "
        f"${cust['total_revenue']:,.0f} | ${cust['total_profit']:,.0f} | "
        f"${cust['avg_order_value']:,.0f} | {margin:.1f}% |"
    )

report.append("")
report.append("#### 2025 Top Customers")
report.append("")
report.append("| Rank | Customer | Orders | Revenue | Profit | Avg Order | Margin % |")
report.append("|------|----------|--------|---------|--------|-----------|----------|")

top_2025 = sorted(
    [c for c in data["top_customers"] if c["year"] == 2025],
    key=lambda x: x["total_revenue"],
    reverse=True,
)[:20]
for i, cust in enumerate(top_2025, 1):
    margin = (
        (cust["total_profit"] / cust["total_revenue"] * 100)
        if cust["total_revenue"]
        else 0
    )
    cust_name = (cust["customer_name"] or "Unknown")[:30]
    report.append(
        f"| {i} | {cust_name} | {int(cust['num_orders']):,} | "
        f"${cust['total_revenue']:,.0f} | ${cust['total_profit']:,.0f} | "
        f"${cust['avg_order_value']:,.0f} | {margin:.1f}% |"
    )

report.append("")

# VENDOR ANALYSIS - REMOVED (SIKA is implicit provider for PRODUCTOS SIKA)

# PRODUCT ANALYSIS
report.append("## Product Performance Analysis")
report.append("")

# Subcategory Performance
report.append("### Subcategory Performance")
report.append("")
report.append(
    "| Subcategory | Year | Products | Customers | Revenue | Profit | Margin % | Transactions |"
)
report.append(
    "|-------------|------|----------|-----------|---------|--------|----------|--------------|"
)

for subcat in data["subcategory_performance"]:
    subcat_name = (subcat["subcategoria"] or "N/A")[:20]
    report.append(
        f"| {subcat_name} | {int(subcat['year'])} | {int(subcat['num_products']):,} | "
        f"{int(subcat['num_customers']):,} | ${subcat['revenue']:,.0f} | "
        f"${subcat['profit']:,.0f} | {subcat['margin_pct']:.1f}% | {int(subcat['transactions']):,} |"
    )

report.append("")

# Top 15 Most Profitable Products
report.append("### Top 15 Most Profitable Products")
report.append("")
report.append("#### 2024")
report.append("")
report.append("| Rank | Product | SKU | Revenue | Profit | Margin % | Customers |")
report.append("|------|---------|-----|---------|--------|----------|-----------|")

prof_2024 = sorted(
    [p for p in data["most_profitable"] if p["year"] == 2024],
    key=lambda x: x["profit"],
    reverse=True,
)[:15]
for i, prod in enumerate(prof_2024, 1):
    prod_name = (prod["product_name"] or "Unknown")[:40]
    report.append(
        f"| {i} | {prod_name} | {prod['sku']} | ${prod['revenue']:,.0f} | "
        f"${prod['profit']:,.0f} | {prod['margin_pct']:.1f}% | {int(prod['unique_customers']):,} |"
    )

report.append("")
report.append("#### 2025")
report.append("")
report.append("| Rank | Product | SKU | Revenue | Profit | Margin % | Customers |")
report.append("|------|---------|-----|---------|--------|----------|-----------|")

prof_2025 = sorted(
    [p for p in data["most_profitable"] if p["year"] == 2025],
    key=lambda x: x["profit"],
    reverse=True,
)[:15]
for i, prod in enumerate(prof_2025, 1):
    prod_name = (prod["product_name"] or "Unknown")[:40]
    report.append(
        f"| {i} | {prod_name} | {prod['sku']} | ${prod['revenue']:,.0f} | "
        f"${prod['profit']:,.0f} | {prod['margin_pct']:.1f}% | {int(prod['unique_customers']):,} |"
    )

report.append("")

# INSIGHTS & RECOMMENDATIONS
report.append("## Key Insights & Strategic Recommendations")
report.append("")

if s24 and s25:
    report.append("### 📈 Growth Performance")
    report.append("")

    rev_growth = (s25["net_revenue"] - s24["net_revenue"]) / s24["net_revenue"] * 100
    profit_growth = (s25["net_profit"] - s24["net_profit"]) / s24["net_profit"] * 100

    if rev_growth > 15:
        report.append(
            f"- **Strong Revenue Growth:** {rev_growth:.1f}% YoY indicates robust market demand for PRODUCTOS SIKA"
        )
    else:
        report.append(
            f"- **Moderate Revenue Growth:** {rev_growth:.1f}% YoY - consider expansion strategies"
        )

    if profit_growth > rev_growth:
        report.append(
            f"- **Margin Expansion:** Profit growing faster than revenue ({profit_growth:.1f}% vs {rev_growth:.1f}%) shows improving operational efficiency"
        )

    report.append("")

    # Monthly insights
    report.append("### 📅 Seasonal Patterns")
    report.append("")

    # Find best/worst months
    monthly_sorted_24 = sorted(
        monthly_2024.items(), key=lambda x: x[1].get("revenue", 0), reverse=True
    )
    monthly_sorted_25 = sorted(
        monthly_2025.items(), key=lambda x: x[1].get("revenue", 0), reverse=True
    )

    if monthly_sorted_24:
        best_month_24 = month_names[monthly_sorted_24[0][0]]
        best_rev_24 = monthly_sorted_24[0][1]["revenue"]
        worst_month_24 = month_names[monthly_sorted_24[-1][0]]

        report.append(f"**2024 Analysis:**")
        report.append(
            f"- Best performing month: **{best_month_24}** (${best_rev_24:,.0f})"
        )
        report.append(f"- Weakest month: **{worst_month_24}**")
        report.append("")

    if monthly_sorted_25 and len(monthly_2025) > 0:
        best_month_25 = month_names[monthly_sorted_25[0][0]]
        best_rev_25 = monthly_sorted_25[0][1]["revenue"]
        report.append(f"**2025 Analysis:**")
        report.append(
            f"- Best performing month: **{best_month_25}** (${best_rev_25:,.0f})"
        )
        report.append("")

    # Customer insights
    report.append("### 👥 Customer Insights")
    report.append("")

    cust_growth = (
        (s25["unique_customers"] - s24["unique_customers"])
        / s24["unique_customers"]
        * 100
    )
    report.append(
        f"- **Customer Base Growth:** {cust_growth:+.1f}% ({int(s24['unique_customers']):,} → {int(s25['unique_customers']):,})"
    )

    # Customer concentration
    if top_2024:
        top5_revenue = sum(c["total_revenue"] for c in top_2024[:5])
        top5_pct = (
            (top5_revenue / s24["net_revenue"] * 100) if s24["net_revenue"] else 0
        )
        report.append(
            f"- **Customer Concentration (2024):** Top 5 customers represent {top5_pct:.1f}% of revenue"
        )

    if top_2025:
        top5_revenue_25 = sum(c["total_revenue"] for c in top_2025[:5])
        top5_pct_25 = (
            (top5_revenue_25 / s25["net_revenue"] * 100) if s25["net_revenue"] else 0
        )
        report.append(
            f"- **Customer Concentration (2025):** Top 5 customers represent {top5_pct_25:.1f}% of revenue"
        )

        if top5_pct_25 < top5_pct:
            report.append(
                "  - ✅ Reduced concentration indicates healthier customer diversification"
            )
        else:
            report.append(
                "  - ⚠️ Increasing concentration - consider customer acquisition initiatives"
            )

    report.append("")

    # Vendor insights - REMOVED (SIKA is implicit provider)

    # Product insights
    report.append("### 🛍️ Product Portfolio")
    report.append("")

    sku_count = int(s24["unique_products"])
    report.append(f"- **Active SKUs:** {sku_count} products")

    if prof_2024:
        top_product = prof_2024[0]
        top_prod_contrib = (
            (top_product["revenue"] / s24["net_revenue"] * 100)
            if s24["net_revenue"]
            else 0
        )
        report.append(
            f"- **Star Product (2024):** {top_product['product_name'][:50]} (${top_product['revenue']:,.0f}, {top_prod_contrib:.1f}% of total)"
        )

    if prof_2025:
        top_product_25 = prof_2025[0]
        report.append(
            f"- **Star Product (2025):** {top_product_25['product_name'][:50]} (${top_product_25['revenue']:,.0f})"
        )

    report.append("")

    # Recommendations
    report.append("### 💡 Strategic Recommendations")
    report.append("")

    if rev_growth > 15 and profit_growth > 20:
        report.append(
            "1. **Scale Operations:** Strong growth trajectory suggests opportunity for capacity expansion"
        )

    if cust_growth < 10:
        report.append(
            "1. **Customer Acquisition:** Focus on new customer acquisition to drive growth"
        )

    if top5_pct > 50:
        report.append(
            "2. **Reduce Concentration Risk:** Develop strategies to diversify customer base"
        )

    report.append(
        "3. **Inventory Optimization:** Align stock levels with monthly demand patterns"
    )
    report.append(
        "4. **Customer Retention:** Implement loyalty programs for high-value customers"
    )
    report.append(
        "5. **Product Mix Analysis:** Focus on high-margin products while maintaining volume leaders"
    )

report.append("")
report.append("---")
report.append("")
report.append("*Report generated from SmartBusiness database*")

# Write report
with open("reports/SIKA_ANALYSIS_REPORT.md", "w") as f:
    f.write("\n".join(report))

print("✅ Report generated: reports/SIKA_ANALYSIS_REPORT.md")
