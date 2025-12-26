#!/usr/bin/env python3
"""Generate markdown report from analysis JSON"""
import json

with open('reports/data/analysis_report.json', 'r') as f:
    data = json.load(f)

report = []
report.append("# Business Analysis Report")
report.append(f"**Periodo:** {data['periodo']} (Jan 2024 - Dec 2025)")
report.append(f"**Generated:** {data['generated_at']}")
report.append("")

# YEARLY TOTALS
report.append("## Yearly Totals")
report.append("")
report.append("| Year | Net Revenue | Net Profit | Margin % | Net Units | Returns | Avg Ticket | Transactions |")
report.append("|------|-------------|------------|----------|-----------|---------|------------|--------------|")
for y in data['yearly_totals']:
    margin = (y['net_profit'] / y['net_revenue'] * 100) if y['net_revenue'] else 0
    report.append(f"| {int(y['year'])} | ${y['net_revenue']:,.0f} | ${y['net_profit']:,.0f} | {margin:.1f}% | {y['net_units_sold']:,.0f} | {y['units_returned']:,.0f} | ${y['avg_ticket']:,.0f} | {y['total_transactions']:,} |")

# Calculate YoY change
if len(data['yearly_totals']) == 2:
    y24, y25 = data['yearly_totals'][0], data['yearly_totals'][1]
    rev_change = ((y25['net_revenue'] - y24['net_revenue']) / y24['net_revenue'] * 100)
    profit_change = ((y25['net_profit'] - y24['net_profit']) / y24['net_profit'] * 100)
    report.append("")
    report.append(f"**YoY Change 2024→2025:** Revenue: {rev_change:+.1f}% | Profit: {profit_change:+.1f}%")
    report.append("")
    report.append("*Note: 2025 data is partial (Jan-Nov 2025)*")

report.append("")

# CATEGORY TOTALS
report.append("## Category Performance by Year")
report.append("")

# Group by category
cat_data = {}
for c in data['category_totals']:
    cat = c['marca'] or 'Sin Categoria'
    if cat not in cat_data:
        cat_data[cat] = {}
    cat_data[cat][int(c['year'])] = c

report.append("| Category | Year | Revenue | Profit | Margin % | Avg Ticket | Units |")
report.append("|----------|------|---------|--------|----------|------------|-------|")

# Sort categories by 2024 revenue (or 2025 if no 2024)
sorted_cats = sorted(cat_data.keys(), key=lambda x: cat_data[x].get(2024, cat_data[x].get(2025, {})).get('net_revenue', 0), reverse=True)

for cat in sorted_cats[:20]:  # Top 20 categories
    for year in [2024, 2025]:
        if year in cat_data[cat]:
            c = cat_data[cat][year]
            margin = (c['net_profit'] / c['net_revenue'] * 100) if c['net_revenue'] else 0
            cat_display = cat[:30] if len(cat) > 30 else cat
            report.append(f"| {cat_display} | {year} | ${c['net_revenue']:,.0f} | ${c['net_profit']:,.0f} | {margin:.1f}% | ${c['avg_ticket']:,.0f} | {c['net_units']:,.0f} |")

report.append("")
report.append("*(Top 20 categories by 2024 revenue shown)*")
report.append("")

# BESTSELLERS
report.append("## Top Bestsellers by Category/Subcategory")
report.append("")
report.append("### 2024 Top Bestsellers")
report.append("")
report.append("| Category | Subcategory | SKU | Product | Net Units | Revenue | Profit |")
report.append("|----------|-------------|-----|---------|-----------|---------|--------|")

bestsellers_2024 = sorted([b for b in data['bestsellers'] if b['year'] == 2024], key=lambda x: x['net_units_sold'], reverse=True)[:20]
for b in bestsellers_2024:
    cat = (b['marca'] or 'N/A')[:20]
    sub = (b['subcategoria'] or 'N/A')[:20]
    prod = (b['product_name'] or 'N/A')[:35]
    report.append(f"| {cat} | {sub} | {b['sku']} | {prod} | {b['net_units_sold']:,.0f} | ${b['revenue']:,.0f} | ${b['profit']:,.0f} |")

report.append("")
report.append("### 2025 Top Bestsellers")
report.append("")
report.append("| Category | Subcategory | SKU | Product | Net Units | Revenue | Profit |")
report.append("|----------|-------------|-----|---------|-----------|---------|--------|")

bestsellers_2025 = sorted([b for b in data['bestsellers'] if b['year'] == 2025], key=lambda x: x['net_units_sold'], reverse=True)[:20]
for b in bestsellers_2025:
    cat = (b['marca'] or 'N/A')[:20]
    sub = (b['subcategoria'] or 'N/A')[:20]
    prod = (b['product_name'] or 'N/A')[:35]
    report.append(f"| {cat} | {sub} | {b['sku']} | {prod} | {b['net_units_sold']:,.0f} | ${b['revenue']:,.0f} | ${b['profit']:,.0f} |")

report.append("")

# MOST PROFITABLE
report.append("## Most Profitable Products by Category/Subcategory")
report.append("")
report.append("### 2024 Most Profitable")
report.append("")
report.append("| Category | Subcategory | SKU | Product | Profit | Margin % | Revenue |")
report.append("|----------|-------------|-----|---------|--------|----------|---------|")

profitable_2024 = sorted([p for p in data['most_profitable'] if p['year'] == 2024], key=lambda x: x['total_profit'], reverse=True)[:20]
for p in profitable_2024:
    cat = (p['marca'] or 'N/A')[:20]
    sub = (p['subcategoria'] or 'N/A')[:20]
    prod = (p['product_name'] or 'N/A')[:35]
    report.append(f"| {cat} | {sub} | {p['sku']} | {prod} | ${p['total_profit']:,.0f} | {p['margin_percentage']:.1f}% | ${p['revenue']:,.0f} |")

report.append("")
report.append("### 2025 Most Profitable")
report.append("")
report.append("| Category | Subcategory | SKU | Product | Profit | Margin % | Revenue |")
report.append("|----------|-------------|-----|---------|--------|----------|---------|")

profitable_2025 = sorted([p for p in data['most_profitable'] if p['year'] == 2025], key=lambda x: x['total_profit'], reverse=True)[:20]
for p in profitable_2025:
    cat = (p['marca'] or 'N/A')[:20]
    sub = (p['subcategoria'] or 'N/A')[:20]
    prod = (p['product_name'] or 'N/A')[:35]
    report.append(f"| {cat} | {sub} | {p['sku']} | {prod} | ${p['total_profit']:,.0f} | {p['margin_percentage']:.1f}% | ${p['revenue']:,.0f} |")

report.append("")

# AVERAGE TICKET
report.append("## Average Ticket by Category/Subcategory")
report.append("")
report.append("### 2024 Highest Average Tickets")
report.append("")
report.append("| Category | Subcategory | Avg Ticket | Transactions | Revenue | Profit |")
report.append("|----------|-------------|------------|--------------|---------|--------|")

ticket_2024 = sorted([t for t in data['avg_ticket_by_category'] if t['year'] == 2024 and t['avg_ticket']], key=lambda x: x['avg_ticket'], reverse=True)[:20]
for t in ticket_2024:
    cat = (t['marca'] or 'N/A')[:20]
    sub = (t['subcategoria'] or 'N/A')[:20]
    report.append(f"| {cat} | {sub} | ${t['avg_ticket']:,.0f} | {t['num_transactions']:,} | ${t['net_revenue']:,.0f} | ${t['net_profit']:,.0f} |")

report.append("")
report.append("### 2025 Highest Average Tickets")
report.append("")
report.append("| Category | Subcategory | Avg Ticket | Transactions | Revenue | Profit |")
report.append("|----------|-------------|------------|--------------|---------|--------|")

ticket_2025 = sorted([t for t in data['avg_ticket_by_category'] if t['year'] == 2025 and t['avg_ticket']], key=lambda x: x['avg_ticket'], reverse=True)[:20]
for t in ticket_2025:
    cat = (t['marca'] or 'N/A')[:20]
    sub = (t['subcategoria'] or 'N/A')[:20]
    report.append(f"| {cat} | {sub} | ${t['avg_ticket']:,.0f} | {t['num_transactions']:,} | ${t['net_revenue']:,.0f} | ${t['net_profit']:,.0f} |")

report.append("")

# Summary stats
report.append("## Summary Statistics")
report.append("")
total_revenue = sum(y['net_revenue'] for y in data['yearly_totals'])
total_profit = sum(y['net_profit'] for y in data['yearly_totals'])
total_units = sum(y['net_units_sold'] for y in data['yearly_totals'])
total_returns = sum(y['units_returned'] for y in data['yearly_totals'])
report.append(f"- **Total Revenue (2024-2025):** ${total_revenue:,.0f}")
report.append(f"- **Total Profit (2024-2025):** ${total_profit:,.0f}")
report.append(f"- **Overall Margin:** {(total_profit/total_revenue*100):.1f}%")
report.append(f"- **Total Units Sold (Net):** {total_units:,.0f}")
report.append(f"- **Total Returns:** {total_returns:,.0f}")
report.append(f"- **Return Rate:** {(total_returns/(total_units+total_returns)*100):.2f}%")
report.append(f"- **Categories:** {len(set(c['marca'] for c in data['category_totals']))}")
report.append(f"- **Subcategories:** {len(data['avg_ticket_by_category'])//2}")

# Write report
with open('reports/ANALYSIS_REPORT.md', 'w') as f:
    f.write('\n'.join(report))

print("Report generated: reports/ANALYSIS_REPORT.md")
