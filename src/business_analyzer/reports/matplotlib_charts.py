# mypy: ignore-errors
"""
Chart Generator for Manager Sales Reports
=========================================

Creates professional matplotlib charts for sales reports.
All charts use Colombian formatting and Spanish labels.

Usage:
    from business_analyzer.reports.matplotlib_charts import ReportChartGenerator

    gen = ReportChartGenerator(report_data, output_dir="reports/charts")
    paths = gen.generate_all()
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

# Use non-interactive backend for server environments
matplotlib.use("Agg")

# Spanish month names for labels
MONTH_NAMES_ES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}


def _format_currency_axis(value: float, _pos: int) -> str:
    """Format y-axis ticks as Colombian currency (billions/millions)."""
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}M".replace(".", ",")
    if value >= 1_000_000:
        return f"${value / 1_000_000:.0f}M".replace(".", ",")
    if value >= 1_000:
        return f"${value / 1_000:.0f}K".replace(".", ",")
    return f"${value:,.0f}".replace(",", ".")


def _format_currency_compact(value: float) -> str:
    """Compact currency for chart labels."""
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}MM".replace(".", ",")
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M".replace(".", ",")
    if value >= 1_000:
        return f"${value / 1_000:.0f}K".replace(".", ",")
    return f"${value:,.0f}".replace(",", ".")


class ReportChartGenerator:
    """
    Generate matplotlib charts for a monthly sales report.

    Attributes:
        data: Report dictionary from ManagerSalesReport.generate()
        output_dir: Directory to save chart images
        figsize: Default figure size (width, height)
        dpi: Image resolution
    """

    def __init__(
        self,
        data: Dict[str, Any],
        output_dir: str = "reports/charts",
        figsize: tuple = (12, 6),
        dpi: int = 150,
    ):
        self.data = data
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.figsize = figsize
        self.dpi = dpi
        self._chart_paths: Dict[str, str] = {}

        # Style configuration
        plt.rcParams.update(
            {
                "font.size": 10,
                "axes.titlesize": 14,
                "axes.labelsize": 11,
                "figure.facecolor": "white",
                "axes.facecolor": "#f8f9fa",
                "axes.edgecolor": "#dee2e6",
                "axes.grid": True,
                "grid.alpha": 0.3,
                "grid.color": "#adb5bd",
            }
        )

    def generate_all(self) -> Dict[str, str]:
        """Generate all charts and return paths."""
        self._chart_paths["daily_trend"] = self._daily_revenue_chart()
        self._chart_paths["top_products"] = self._top_products_chart()
        self._chart_paths["top_customers"] = self._top_customers_chart()
        self._chart_paths["category_pie"] = self._category_pie_chart()
        self._chart_paths["category_bar"] = self._category_bar_chart()
        self._chart_paths["margin_comparison"] = self._margin_comparison_chart()
        self._chart_paths["kpi_summary"] = self._kpi_summary_chart()
        self._chart_paths["vendor_sales"] = self._vendor_sales_chart()
        return {k: v for k, v in self._chart_paths.items() if v}

    def _daily_revenue_chart(self) -> Optional[str]:
        """Line chart of daily revenue trend."""
        trend = self.data.get("daily_trend", [])
        if len(trend) < 2:
            return None

        dates = [d["date"][-2:] for d in trend]  # Day only
        revenue = [d["revenue_with_iva"] for d in trend]
        profit = [d["profit"] for d in trend]

        fig, ax = plt.subplots(figsize=(14, 6))
        x = np.arange(len(dates))

        ax.plot(
            x,
            revenue,
            color="#2563eb",
            linewidth=2.5,
            label="Facturación (IVA)",
            marker="o",
            markersize=4,
        )
        ax.plot(
            x,
            profit,
            color="#16a34a",
            linewidth=2.5,
            label="Ganancia",
            marker="s",
            markersize=4,
        )
        ax.fill_between(x, profit, alpha=0.15, color="#16a34a")
        ax.fill_between(x, revenue, alpha=0.08, color="#2563eb")

        # Highlight weekends (every 6th and 7th day approx)
        for i in range(len(x)):
            if i % 7 in (5, 6):
                ax.axvspan(i - 0.4, i + 0.4, alpha=0.06, color="red")

        ax.set_xlabel("Día del Mes")
        ax.set_ylabel("Valor ($)")
        ax.yaxis.set_major_formatter(plt.FuncFormatter(_format_currency_axis))
        ax.set_title("Tendencia Diaria de Ventas", fontweight="bold", pad=15)
        ax.legend(loc="upper left", framealpha=0.9)

        # Reduce x-axis labels for readability
        step = max(1, len(dates) // 15)
        ax.set_xticks(x[::step])
        ax.set_xticklabels(dates[::step], rotation=45, ha="right")

        plt.tight_layout()
        path = str(self.output_dir / "daily_trend.png")
        fig.savefig(path, dpi=self.dpi, bbox_inches="tight")
        plt.close(fig)
        return path

    def _top_products_chart(self) -> Optional[str]:
        """Horizontal bar chart of top 10 products."""
        products = self.data.get("top_products", [])
        if not products:
            return None

        top = products[:10]
        names = [p["product_name"][:35] for p in reversed(top)]
        revenue = [p["total_revenue"] for p in reversed(top)]
        margins = [p["profit_margin_pct"] for p in reversed(top)]

        fig, ax1 = plt.subplots(figsize=(12, 7))
        y = np.arange(len(names))

        # Revenue bars
        bars = ax1.barh(
            y, revenue, color="#3b82f6", alpha=0.85, height=0.6, label="Facturación"
        )
        ax1.set_yticks(y)
        ax1.set_yticklabels(names, fontsize=9)
        ax1.set_xlabel("Facturación ($)")
        ax1.xaxis.set_major_formatter(plt.FuncFormatter(_format_currency_axis))
        ax1.set_title("Top 10 Productos por Facturación", fontweight="bold", pad=15)

        # Add value labels on bars
        for bar, val in zip(bars, revenue):
            ax1.text(
                bar.get_width() + max(revenue) * 0.01,
                bar.get_y() + bar.get_height() / 2,
                _format_currency_compact(val),
                va="center",
                fontsize=8,
                color="#1e3a5f",
            )

        # Margin line on secondary axis
        ax2 = ax1.twiny()
        ax2.plot(
            margins,
            y,
            color="#dc2626",
            marker="D",
            markersize=5,
            linewidth=2,
            label="Margen %",
        )
        ax2.set_xlabel("Margen (%)", color="#dc2626")
        ax2.tick_params(axis="x", colors="#dc2626")
        ax2.set_xlim(0, max(margins) * 1.5 if margins else 50)

        # Combined legend
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(
            lines1 + lines2, labels1 + labels2, loc="lower right", framealpha=0.9
        )

        plt.tight_layout()
        path = str(self.output_dir / "top_products.png")
        fig.savefig(path, dpi=self.dpi, bbox_inches="tight")
        plt.close(fig)
        return path

    def _top_customers_chart(self) -> Optional[str]:
        """Horizontal bar chart of top 10 customers."""
        customers = self.data.get("top_customers", [])
        if not customers:
            return None

        top = customers[:10]
        names = [c["customer_name"][:30] for c in reversed(top)]
        revenue = [c["total_revenue"] for c in reversed(top)]
        orders = [c["total_orders"] for c in reversed(top)]

        fig, ax1 = plt.subplots(figsize=(11, 6))
        y = np.arange(len(names))

        bars = ax1.barh(y, revenue, color="#8b5cf6", alpha=0.85, height=0.6)
        ax1.set_yticks(y)
        ax1.set_yticklabels(names, fontsize=9)
        ax1.set_xlabel("Facturación ($)")
        ax1.xaxis.set_major_formatter(plt.FuncFormatter(_format_currency_axis))
        ax1.set_title("Top 10 Clientes por Facturación", fontweight="bold", pad=15)

        for bar, val in zip(bars, revenue):
            ax1.text(
                bar.get_width() + max(revenue) * 0.01,
                bar.get_y() + bar.get_height() / 2,
                _format_currency_compact(val),
                va="center",
                fontsize=8,
                color="#4c1d95",
            )

        ax2 = ax1.twiny()
        ax2.plot(
            orders,
            y,
            color="#f59e0b",
            marker="o",
            markersize=5,
            linewidth=2,
            label="Pedidos",
        )
        ax2.set_xlabel("N° Pedidos", color="#f59e0b")
        ax2.tick_params(axis="x", colors="#f59e0b")

        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(
            lines1 + lines2, labels1 + labels2, loc="lower right", framealpha=0.9
        )

        plt.tight_layout()
        path = str(self.output_dir / "top_customers.png")
        fig.savefig(path, dpi=self.dpi, bbox_inches="tight")
        plt.close(fig)
        return path

    def _vendor_sales_chart(self) -> Optional[str]:
        """Horizontal bar chart for top vendors by revenue (sales per vendors)."""
        vendors = self.data.get("vendor_sales", [])
        if not vendors:
            return None
        top = vendors[:10]
        names = [v["vendor_name"][:22] for v in reversed(top)]
        revenue = [v["total_revenue"] for v in reversed(top)]
        margins = [v.get("profit_margin_pct", 0) for v in reversed(top)]

        fig, ax = plt.subplots(figsize=(11, 5.5))
        y = np.arange(len(names))
        bars = ax.barh(y, revenue, color="#0ea5e9", alpha=0.85, height=0.65)
        ax.set_yticks(y)
        ax.set_yticklabels(names, fontsize=9)
        ax.set_xlabel("Facturación ($)")
        ax.xaxis.set_major_formatter(plt.FuncFormatter(_format_currency_axis))
        ax.set_title("Top Proveedores por Facturación", fontweight="bold", pad=12)

        for bar, val in zip(bars, revenue):
            ax.text(
                bar.get_width() + max(revenue) * 0.015 if max(revenue) > 0 else 0,
                bar.get_y() + bar.get_height() / 2,
                _format_currency_compact(val),
                va="center",
                fontsize=8,
                color="#0369a1",
            )

        # annotate margin on right
        for i, (bar, m) in enumerate(zip(bars, margins)):
            ax.text(
                bar.get_width() * 0.02,
                bar.get_y() + bar.get_height() / 2,
                f"{m:.1f}%",
                va="center",
                fontsize=7,
                color="#166534",
                fontweight="bold",
            )

        ax.text(
            0.99,
            0.02,
            "etiqueta = margen %",
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=7,
            color="#166534",
            alpha=0.7,
        )

        plt.tight_layout()
        path = str(self.output_dir / "vendor_sales.png")
        fig.savefig(path, dpi=self.dpi, bbox_inches="tight")
        plt.close(fig)
        return path

    def _category_pie_chart(self) -> Optional[str]:
        """Pie chart of revenue by top categories."""
        categories = self.data.get("category_breakdown", [])
        if not categories:
            return None

        # Group by top-level category
        cat_revenue: Dict[str, float] = {}
        for c in categories:
            parts = c["category_path"].split(" > ")
            top_cat = parts[0] if parts else "Otros"
            cat_revenue[top_cat] = cat_revenue.get(top_cat, 0.0) + c["total_revenue"]

        sorted_cats = sorted(cat_revenue.items(), key=lambda x: x[1], reverse=True)
        top = sorted_cats[:8]
        others_sum = sum(v for _, v in sorted_cats[8:])
        if others_sum > 0:
            top.append(("Otros", others_sum))

        labels = [k[:20] for k, _ in top]
        values = [v for _, v in top]
        colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))

        fig, ax = plt.subplots(figsize=(9, 9))
        wedges, texts, autotexts = ax.pie(
            values,
            labels=labels,
            colors=colors,
            autopct="%1.1f%%",
            startangle=90,
            pctdistance=0.8,
            wedgeprops={"edgecolor": "white", "linewidth": 2},
        )
        for autotext in autotexts:
            autotext.set_color("white")
            autotext.set_fontweight("bold")
            autotext.set_fontsize(9)
        for text in texts:
            text.set_fontsize(10)

        ax.set_title("Distribución de Ventas por Categoría", fontweight="bold", pad=20)
        plt.tight_layout()
        path = str(self.output_dir / "category_pie.png")
        fig.savefig(path, dpi=self.dpi, bbox_inches="tight")
        plt.close(fig)
        return path

    def _category_bar_chart(self) -> Optional[str]:
        """Grouped bar chart of top categories with revenue and margin."""
        categories = self.data.get("category_breakdown", [])
        if not categories:
            return None

        top = categories[:10]
        names = [c["category_path"].replace(" > ", "\n")[:25] for c in top]
        revenue = [c["total_revenue"] for c in top]
        margins = [c["profit_margin_pct"] for c in top]

        fig, ax1 = plt.subplots(figsize=(13, 6))
        x = np.arange(len(names))
        width = 0.5

        bars = ax1.bar(
            x, revenue, width, color="#0ea5e9", alpha=0.85, label="Facturación"
        )
        ax1.set_xticks(x)
        ax1.set_xticklabels(names, rotation=35, ha="right", fontsize=8)
        ax1.set_ylabel("Facturación ($)")
        ax1.yaxis.set_major_formatter(plt.FuncFormatter(_format_currency_axis))
        ax1.set_title(
            "Top 10 Categorías — Facturación y Margen", fontweight="bold", pad=15
        )

        # Add compact labels on bars
        for bar, val in zip(bars, revenue):
            ax1.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(revenue) * 0.01,
                _format_currency_compact(val),
                ha="center",
                fontsize=7,
                color="#0369a1",
            )

        ax2 = ax1.twinx()
        ax2.plot(
            x,
            margins,
            color="#ef4444",
            marker="D",
            markersize=6,
            linewidth=2.5,
            label="Margen %",
        )
        ax2.set_ylabel("Margen (%)", color="#ef4444")
        ax2.tick_params(axis="y", colors="#ef4444")
        ax2.set_ylim(0, max(margins) * 1.4 if margins else 50)

        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(
            lines1 + lines2, labels1 + labels2, loc="upper right", framealpha=0.9
        )

        plt.tight_layout()
        path = str(self.output_dir / "category_bar.png")
        fig.savefig(path, dpi=self.dpi, bbox_inches="tight")
        plt.close(fig)
        return path

    def _margin_comparison_chart(self) -> Optional[str]:
        """Scatter plot: revenue vs margin for top products."""
        products = self.data.get("top_products", [])
        if len(products) < 3:
            return None

        revenue = [p["total_revenue"] for p in products]
        margins = [p["profit_margin_pct"] for p in products]
        quantities = [p["total_quantity"] for p in products]
        names = [p["product_name"][:20] for p in products]

        fig, ax = plt.subplots(figsize=(11, 7))

        # Bubble sizes based on quantity
        sizes = [max(50, min(800, q * 2)) for q in quantities]
        colors = plt.cm.viridis(np.linspace(0, 1, len(products)))

        scatter = ax.scatter(
            revenue,
            margins,
            s=sizes,
            c=colors,
            alpha=0.7,
            edgecolors="white",
            linewidth=1.5,
        )

        # Annotate top 5
        for i in range(min(5, len(names))):
            ax.annotate(
                names[i],
                (revenue[i], margins[i]),
                fontsize=8,
                xytext=(8, 5),
                textcoords="offset points",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.3),
                arrowprops=dict(arrowstyle="->", color="gray", lw=0.5),
            )

        ax.set_xlabel("Facturación ($)")
        ax.xaxis.set_major_formatter(plt.FuncFormatter(_format_currency_axis))
        ax.set_ylabel("Margen de Ganancia (%)")
        ax.set_title(
            "Productos: Facturación vs Margen (tamaño = cantidad vendida)",
            fontweight="bold",
            pad=15,
        )
        ax.axhline(
            y=np.mean(margins),
            color="red",
            linestyle="--",
            alpha=0.5,
            label=f"Margen Promedio: {np.mean(margins):.1f}%",
        )
        ax.legend(loc="lower left", framealpha=0.9)

        plt.tight_layout()
        path = str(self.output_dir / "margin_comparison.png")
        fig.savefig(path, dpi=self.dpi, bbox_inches="tight")
        plt.close(fig)
        return path

    def _kpi_summary_chart(self) -> Optional[str]:
        """Visual KPI summary card-style chart."""
        summary = self.data.get("summary", {})
        if not summary:
            return None

        fig, axes = plt.subplots(2, 3, figsize=(14, 8))
        fig.suptitle(
            "Resumen de Indicadores Clave", fontsize=16, fontweight="bold", y=0.98
        )

        kpis = [
            (
                "Facturación\n(con IVA)",
                summary.get("total_revenue_with_iva", 0),
                "#2563eb",
            ),
            (
                "Facturación\n(sin IVA)",
                summary.get("total_revenue_without_iva", 0),
                "#3b82f6",
            ),
            ("Costo Total", summary.get("total_cost", 0), "#dc2626"),
            ("Ganancia Bruta", summary.get("gross_profit", 0), "#16a34a"),
            ("Ticket Promedio", summary.get("average_order_value", 0), "#8b5cf6"),
            ("Unidades\nVendidas", summary.get("total_quantity_sold", 0), "#f59e0b"),
        ]

        for ax, (label, value, color) in zip(axes.flat, kpis):
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis("off")
            from matplotlib.patches import FancyBboxPatch

            fancy = FancyBboxPatch(
                (0.05, 0.1),
                0.9,
                0.8,
                boxstyle="round,pad=0.02",
                facecolor=color,
                alpha=0.15,
                edgecolor=color,
                linewidth=2,
            )
            ax.add_patch(fancy)
            ax.text(
                0.5,
                0.65,
                label,
                ha="center",
                va="center",
                fontsize=11,
                fontweight="bold",
                color="#374151",
            )
            if value >= 1_000_000:
                text = _format_currency_compact(value)
            else:
                text = f"{value:,.0f}".replace(",", ".")
            ax.text(
                0.5,
                0.35,
                text,
                ha="center",
                va="center",
                fontsize=18,
                fontweight="bold",
                color=color,
            )

        plt.tight_layout(rect=[0, 0, 1, 0.95])
        path = str(self.output_dir / "kpi_summary.png")
        fig.savefig(path, dpi=self.dpi, bbox_inches="tight")
        plt.close(fig)
        return path
