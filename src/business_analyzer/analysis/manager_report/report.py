"""
Manager Sales Report Module
===========================

Generate comprehensive monthly sales reports for management review.
"""

import calendar
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from business_analyzer.core.database import ConnectionType
from business_analyzer.core.product_attrs import (
    is_bad_attr_value,
    resolve_effective_marca,
)

from .aggregations import (
    budget_vs_actual_from_sql,
    category_breakdown_from_rows,
    category_breakdown_from_sql,
    daily_trend_from_rows,
    daily_trend_from_sql,
    summary_from_rows,
    summary_from_sql,
    top_customers_from_rows,
    top_customers_from_sql,
    top_products_from_rows,
    top_products_from_sql,
)
from .formatting import format_for_display
from .helpers import MONTH_NAMES_ES, branch_display_name, month_date_range
from .queries import SalesQueryRunner
from .recommendations import ReportRecommendationsMixin


class ManagerSalesReport(ReportRecommendationsMixin):
    """Monthly manager sales report generator."""

    def __init__(
        self,
        year: int,
        month: int,
        use_j3system: bool = True,
        db_connection_type: ConnectionType = ConnectionType.DIRECT,
        conn_details: Optional[Dict[str, Any]] = None,
        branch_document_code: Optional[str] = None,
    ):
        if not (1 <= month <= 12):
            raise ValueError(f"Month must be between 1 and 12, got {month}")
        if year < 2000 or year > 2100:
            raise ValueError(f"Year must be realistic, got {year}")

        self.year = year
        self.month = month
        self.use_j3system = use_j3system
        self.db_connection_type = db_connection_type
        self.conn_details = conn_details or {}
        self.branch_document_code = (
            branch_document_code.upper() if branch_document_code else None
        )
        self.branch_name = branch_display_name(self.branch_document_code)

        self.start_date, self.end_date = month_date_range(year, month)
        self._queries = SalesQueryRunner(
            self.start_date,
            self.end_date,
            year,
            db_connection_type,
            conn_details,
            branch_document_code=self.branch_document_code,
        )

        self._sales_data: List[Dict[str, Any]] = []
        self._ytd_sales_data: List[Dict[str, Any]] = []
        self._sql_aggregations: Dict[str, Any] = {}
        self._ytd_sql_aggregations: Dict[str, Any] = {}
        self._j3system_inventory: Dict[str, Dict[str, Any]] = {}
        self._j3system_products: Dict[str, Dict[str, Any]] = {}
        self._j3system_warehouse: Dict[str, List[Dict[str, Any]]] = {}
        self._sb_product_map: Dict[str, Dict[str, Any]] = {}
        self._vendor_names: Dict[str, str] = {}
        self._sku_historical_prov: Dict[str, str] = {}
        self._sku_historical_marca: Dict[str, str] = {}
        self._processed = False

    def _build_sku_historical_map(self) -> None:
        sku_provs: Dict[str, Counter] = defaultdict(Counter)
        sku_marcas: Dict[str, Counter] = defaultdict(Counter)
        bads = {"", "S/I", "S.I", "SIN PROVEEDOR", "N/A", "."}
        all_rows = (self._sales_data or []) + (self._ytd_sales_data or [])
        for row in all_rows:
            sku = row.get("ArticulosCodigo")
            if not sku:
                continue
            p = str(row.get("proveedor") or "").strip()
            if p and p.upper() not in bads and len(p) > 2:
                sku_provs[sku][p] += 1
            m = str(row.get("marca") or "").strip()
            if m and m.upper() not in bads and len(m) > 2:
                sku_marcas[sku][m] += 1
        self._sku_historical_prov = {
            s: c.most_common(1)[0][0] for s, c in sku_provs.items() if c
        }
        self._sku_historical_marca = {
            s: c.most_common(1)[0][0] for s, c in sku_marcas.items() if c
        }

    def _enrich_proveedor_marca_from_master(self, rows: list) -> None:
        if not rows:
            return
        for row in rows:
            sku = row.get("ArticulosCodigo")
            if not sku:
                continue
            master = self._sb_product_map.get(sku) if self._sb_product_map else None
            if master:
                prov = row.get("proveedor")
                bad = (
                    not prov
                    or str(prov).strip().upper()
                    in ("", "S/I", "S.I", "SIN PROVEEDOR", "N/A", ".", "SIN IVA", "NA")
                    or len(str(prov).strip()) <= 2
                )
                if bad:
                    p = master.get("proveedor")
                    if p and p not in ("NA", ""):
                        row["proveedor"] = p
                master_marca = master.get("marca")
                if master_marca and not is_bad_attr_value(master_marca):
                    row["marca"] = master_marca
                else:
                    resolved = resolve_effective_marca(row.get("marca"), master_marca)
                    if resolved:
                        row["marca"] = resolved
                continue

            if self._j3system_products:
                j3 = self._j3system_products.get(sku)
                if j3:
                    prov = row.get("proveedor")
                    if not prov or str(prov).strip().upper() in (
                        "",
                        "S/I",
                        "S.I",
                        "SIN PROVEEDOR",
                        "N/A",
                        ".",
                        "SIN IVA",
                        "NA",
                    ):
                        if j3.get("vendor_name"):
                            row["proveedor"] = j3["vendor_name"]
                    m = row.get("marca")
                    if not m or str(m).strip() == "":
                        if j3.get("marca"):
                            row["marca"] = j3["marca"]

            if not row.get("proveedor") or str(
                row.get("proveedor")
            ).strip().upper() in (
                "",
                "S/I",
                "S.I",
                "SIN PROVEEDOR",
                "N/A",
                ".",
                "SIN IVA",
                "NA",
            ):
                hist_p = self._sku_historical_prov.get(sku)
                if hist_p:
                    row["proveedor"] = hist_p
            if not row.get("marca") or str(row.get("marca")).strip() == "":
                hist_m = self._sku_historical_marca.get(sku)
                if hist_m:
                    row["marca"] = hist_m

    def _enrich_sales_proveedor_marca_from_master(self) -> None:
        self._enrich_proveedor_marca_from_master(self._sales_data)

    def _report_metadata(self, *, record_count: int) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            "year": self.year,
            "month": self.month,
            "month_name": MONTH_NAMES_ES.get(
                self.month, calendar.month_name[self.month]
            ),
            "start_date": self.start_date,
            "end_date": self.end_date,
            "record_count": record_count,
        }
        if self.branch_document_code:
            metadata["branch_document_code"] = self.branch_document_code
            metadata["branch_name"] = self.branch_name
        return metadata

    def _process_data(self) -> None:
        if self._processed:
            return
        self._sales_data = self._queries.fetch_sales_data()
        if self._sales_data:
            try:
                self._sql_aggregations = self._queries.fetch_sql_aggregations()
            except Exception:
                self._sql_aggregations = {}
            try:
                self._ytd_sql_aggregations = self._queries.fetch_ytd_sql_aggregations()
                self._ytd_sales_data = []
            except Exception:
                self._ytd_sql_aggregations = {}
                self._ytd_sales_data = self._queries.fetch_year_to_date_data()
            self._sb_product_map = self._queries.fetch_sb_product_map()
            self._build_sku_historical_map()
            self._enrich_sales_proveedor_marca_from_master()
            if self._ytd_sales_data:
                self._enrich_proveedor_marca_from_master(self._ytd_sales_data)
        if self.use_j3system:
            self._j3system_inventory = self._queries.fetch_j3system_inventory()
            products, vendor_map = self._queries.fetch_j3system_product_details()
            self._j3system_products = products
            self._vendor_names = vendor_map
            self._j3system_warehouse = self._queries.fetch_j3system_warehouse_sales()
            self._enrich_sales_proveedor_marca_from_master()
            if self._ytd_sales_data:
                self._enrich_proveedor_marca_from_master(self._ytd_sales_data)
        self._processed = True

    def _calculate_summary(self) -> Dict[str, Any]:
        sql_row = self._sql_aggregations.get("summary") or {}
        if sql_row.get("total_with_iva") is not None:
            return summary_from_sql(sql_row)
        return summary_from_rows(self._sales_data)

    def _calculate_top_products(self) -> List[Dict[str, Any]]:
        sql_rows = self._sql_aggregations.get("top_products") or []
        if sql_rows and "product_name" in sql_rows[0]:
            return top_products_from_sql(sql_rows)
        return top_products_from_rows(self._sales_data)

    def _calculate_top_customers(self) -> List[Dict[str, Any]]:
        sql_rows = self._sql_aggregations.get("top_customers") or []
        if sql_rows and "customer_name" in sql_rows[0]:
            return top_customers_from_sql(sql_rows)
        return top_customers_from_rows(self._sales_data)

    def _calculate_category_breakdown(self) -> List[Dict[str, Any]]:
        sql_rows = self._sql_aggregations.get("category_breakdown") or []
        if sql_rows and "categoria" in sql_rows[0]:
            return category_breakdown_from_sql(sql_rows)
        return category_breakdown_from_rows(self._sales_data)

    def _calculate_daily_trend(self) -> List[Dict[str, Any]]:
        sql_rows = self._sql_aggregations.get("daily_trend") or []
        if sql_rows and "sale_date" in sql_rows[0]:
            return daily_trend_from_sql(sql_rows)
        return daily_trend_from_rows(self._sales_data)

    def _calculate_budget_vs_actual(self) -> Dict[str, Any]:
        try:
            payload = self._queries.fetch_budget_vs_actual()
        except Exception:
            return {
                "available": False,
                "note": "No fue posible consultar presupuesto vs real.",
                "periodo": None,
                "summary": {},
                "sellers": [],
                "underperformers": [],
            }
        return budget_vs_actual_from_sql(payload)

    def generate(self) -> Dict[str, Any]:
        """Generate the complete manager sales report with all sections."""
        self._process_data()

        if not self._sales_data:
            from business_analyzer.ai.formatting import (
                format_currency,
                format_integer,
                format_percentage,
            )

            empty_formatted = {
                "summary": {
                    "total_revenue_with_iva": format_currency(0, 0),
                    "total_revenue_without_iva": format_currency(0, 0),
                    "total_cost": format_currency(0, 0),
                    "gross_profit": format_currency(0, 0),
                    "gross_margin_pct": format_percentage(0, 1),
                    "total_quantity_sold": format_integer(0),
                    "order_count": format_integer(0),
                    "average_order_value": format_currency(0, 0),
                    "average_order_profit": format_currency(0, 0),
                },
                "top_products": [],
                "top_customers": [],
                "category_breakdown": [],
                "daily_trend": [],
                "vendor_sales": [],
                "marca_sales": [],
                "customer_vendor_mix": [],
                "customer_order_suggestions": [],
                "shopping_recommendations": {
                    "cross_sell": [],
                    "high_margin_promote": [],
                },
                "procurement_plan": [],
                "warehouse_sales": {"breakdown": [], "sales_detail": [], "note": None},
                "budget_vs_actual": {
                    "available": False,
                    "summary": {},
                    "sellers": [],
                    "underperformers": [],
                },
            }
            return {
                "metadata": self._report_metadata(record_count=0),
                "summary": {
                    "total_revenue_with_iva": 0.0,
                    "total_revenue_without_iva": 0.0,
                    "total_cost": 0.0,
                    "gross_profit": 0.0,
                    "gross_margin_pct": 0.0,
                    "total_quantity_sold": 0,
                    "order_count": 0,
                    "average_order_value": 0.0,
                    "average_order_profit": 0.0,
                },
                "top_products": [],
                "top_customers": [],
                "category_breakdown": [],
                "daily_trend": [],
                "inventory_insights": {
                    "low_stock_alert": [],
                    "fast_movers_in_month": [],
                },
                "vendor_sales": [],
                "marca_sales": [],
                "customer_order_suggestions": [],
                "shopping_recommendations": [],
                "customer_vendor_mix": [],
                "procurement_plan": [],
                "warehouse_sales": {
                    "breakdown": [],
                    "sales_detail": [],
                    "note": "Sin datos de ventas",
                },
                "budget_vs_actual": {
                    "available": False,
                    "note": "Sin datos de ventas",
                    "summary": {},
                    "sellers": [],
                    "underperformers": [],
                },
                "abc_analysis": {"products": {}, "customers": {}, "vendors": {}},
                "stock_replenishment_suggestions": [],
                "formatted": empty_formatted,
            }

        summary = self._calculate_summary()
        top_products = self._calculate_top_products()
        top_customers = self._calculate_top_customers()
        category_breakdown = self._calculate_category_breakdown()
        daily_trend = self._calculate_daily_trend()
        inventory_insights = self._calculate_inventory_insights()
        warehouse_sales = self._calculate_warehouse_sales()
        vendor_sales = self._calculate_vendor_sales()
        marca_sales = self._calculate_marca_sales()
        customer_vendor_mix = self._calculate_customer_vendor_mix()
        order_suggestions = self._calculate_suggested_orders()
        recommendations = self._calculate_shopping_recommendations()
        procurement_plan = self._calculate_procurement_plan(order_suggestions)
        abc_analysis = self._calculate_abc_analysis()
        stock_replenish = self._calculate_stock_replenishment_suggestions()
        budget_vs_actual = self._calculate_budget_vs_actual()

        formatted = format_for_display(
            summary,
            top_products,
            top_customers,
            category_breakdown,
            daily_trend,
            vendor_sales,
            marca_sales,
            customer_vendor_mix,
            order_suggestions,
            recommendations,
            procurement_plan,
            abc_analysis,
            stock_replenish,
            warehouse_sales,
            budget_vs_actual,
        )

        return {
            "metadata": self._report_metadata(record_count=len(self._sales_data)),
            "summary": summary,
            "top_products": top_products,
            "top_customers": top_customers,
            "category_breakdown": category_breakdown,
            "daily_trend": daily_trend,
            "inventory_insights": inventory_insights,
            "warehouse_sales": warehouse_sales,
            "vendor_sales": vendor_sales,
            "marca_sales": marca_sales,
            "customer_vendor_mix": customer_vendor_mix,
            "customer_order_suggestions": order_suggestions,
            "shopping_recommendations": recommendations,
            "procurement_plan": procurement_plan,
            "abc_analysis": abc_analysis,
            "stock_replenishment_suggestions": stock_replenish,
            "budget_vs_actual": budget_vs_actual,
            "formatted": formatted,
        }


def generate_monthly_report(
    year: int,
    month: int,
    use_j3system: bool = True,
    db_connection_type: str = "direct",
    conn_details: Optional[Dict[str, Any]] = None,
    branch_document_code: Optional[str] = None,
) -> Dict[str, Any]:
    """Convenience function to generate a monthly manager sales report."""
    report = ManagerSalesReport(
        year=year,
        month=month,
        use_j3system=use_j3system,
        db_connection_type=ConnectionType(db_connection_type),
        conn_details=conn_details,
        branch_document_code=branch_document_code,
    )
    return report.generate()
