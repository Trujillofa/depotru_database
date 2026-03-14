import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from ..config import Config

logger = logging.getLogger(__name__)

plt: Any = None
mpatches: Any = None
GridSpec: Any = None
np: Any = None
_matplotlib_available = False

try:
    import warnings

    import matplotlib.patches as mpatches
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.gridspec import GridSpec

    warnings.filterwarnings("ignore")
    _matplotlib_available = True
except ImportError:
    _matplotlib_available = False


MATPLOTLIB_AVAILABLE = _matplotlib_available


COLORS = ["#2E86AB", "#A23B72", "#F18F01", "#C73E1D", "#6A994E"]
if MATPLOTLIB_AVAILABLE:
    plt.style.use("seaborn-v0_8-darkgrid")


def generate_visualization_report(
    analysis: Dict[str, Any], output_path: Optional[str] = None
) -> Optional[str]:
    if not MATPLOTLIB_AVAILABLE:
        logger.warning("Matplotlib not available - skipping visualization generation")
        return None

    Config.ensure_output_dir()

    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(
            Config.OUTPUT_DIR / f"business_analysis_report_{timestamp}.png"
        )
    else:
        output_path = os.path.expanduser(output_path)

    assert (
        plt is not None
        and mpatches is not None
        and GridSpec is not None
        and np is not None
    )

    metrics = analysis["calculated_metrics"]
    financial = metrics["financial_metrics"]
    customers = metrics["customer_analytics"]
    products = metrics["product_analytics"]
    categories = metrics["category_analytics"]
    trends = metrics["trend_analytics"]

    fig = plt.figure(figsize=(20, 24))
    gs = GridSpec(6, 2, figure=fig, hspace=0.4, wspace=0.3)

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
            edgecolor=COLORS[i],
            facecolor=COLORS[i],
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
            color=COLORS[i],
        )
        ax_kpi.text(
            x_pos, 0.4, label, ha="center", va="center", fontsize=10, color="#333333"
        )

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
            y_pos, product_sales, color=COLORS[:3], alpha=0.8, edgecolor="black"
        )
        ax1.set_yticks(y_pos)
        ax1.set_yticklabels(product_names, fontsize=10)
        ax1.set_xlabel("Total Sales ($)", fontsize=12, fontweight="bold")
        ax1.set_title("Top 3 Selling Products", fontsize=14, fontweight="bold", pad=15)
        ax1.grid(axis="x", alpha=0.3)

        for bar, value in zip(bars, product_sales):
            ax1.text(
                value + 20000,
                bar.get_y() + bar.get_height() / 2,
                f"${value:,.2f}",
                va="center",
                fontsize=10,
                fontweight="bold",
            )

    ax2 = fig.add_subplot(gs[2, 0])
    category_dist = trends.get("category_distribution", {})
    positive_categories = {k: v for k, v in category_dist.items() if v > 0}
    cat_names = list(positive_categories.keys())
    cat_values = list(positive_categories.values())

    if cat_values:
        cat_names_short = [
            name[:30] + "..." if len(name) > 30 else name for name in cat_names
        ]

        wedges, texts, autotexts = ax2.pie(
            cat_values,
            labels=cat_names_short,
            autopct="%1.1f%%",
            startangle=90,
            colors=COLORS[: len(cat_values)],
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
        ax2.text(
            0.5,
            0.5,
            "No positive\ncategory data\navailable",
            ha="center",
            va="center",
            transform=ax2.transAxes,
            fontsize=12,
        )
        ax2.set_title(
            "Sales Distribution by Category", fontsize=14, fontweight="bold", pad=15
        )

    ax3 = fig.add_subplot(gs[2, 1])
    top_customers_list = customers.get("top_customers", [])[:3]
    customer_names = [c["customer_name"] for c in top_customers_list]
    customer_revenue = [c["total_revenue"] for c in top_customers_list]

    if customer_names:
        x_pos = np.arange(len(customer_names))
        bars = ax3.bar(
            x_pos, customer_revenue, color=COLORS[1], alpha=0.8, edgecolor="black"
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

    ax4 = fig.add_subplot(gs[3, :])
    category_performance = categories.get("category_performance", [])[:5]
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

        ax4.bar(
            x - width,
            cat_revenues,
            width,
            label="Revenue",
            color=COLORS[0],
            alpha=0.8,
            edgecolor="black",
        )
        ax4.bar(
            x,
            cat_costs,
            width,
            label="Cost",
            color=COLORS[3],
            alpha=0.8,
            edgecolor="black",
        )
        bars3 = ax4.bar(
            x + width,
            [m * 5000 for m in cat_margins],
            width,
            label="Margin (scaled)",
            color=COLORS[4],
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

        for bar, margin in zip(bars3, cat_margins):
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

    ax6 = fig.add_subplot(gs[4, 1])
    revenue_breakdown = {
        "Sales Revenue": revenue_without_iva,
        "IVA (Tax)": revenue_with_iva - revenue_without_iva,
    }

    bars = ax6.bar(
        list(revenue_breakdown.keys()),
        list(revenue_breakdown.values()),
        color=[COLORS[0], COLORS[2]],
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
            f"${value:,.2f}\n({value / revenue_with_iva * 100:.1f}%)",
            ha="center",
            va="center",
            fontsize=10,
            fontweight="bold",
            color="white",
        )

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
• Total Customers: {customers.get("total_customers", 0)}
• Total Products: {products.get("total_products", 0)}

⚠️ CRITICAL ISSUES:
"""

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

    plt.savefig(
        str(output_path), dpi=Config.REPORT_DPI, bbox_inches="tight", facecolor="white"
    )
    plt.close(fig)

    logger.info(f"✅ Visualization report saved to {output_path}")
    return str(output_path)
