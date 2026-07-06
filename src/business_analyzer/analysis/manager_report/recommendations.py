"""Recommendation and enrichment calculations for manager reports."""

import statistics
from collections import Counter, defaultdict
from typing import Any, Dict, List

from .aggregations import (
    abc_buckets_from_sql,
    customer_vendor_mix_from_sql,
    marca_sales_from_sql,
    sku_monthly_sales_from_sql,
    vendor_sales_from_sql,
    ytd_customer_products_from_sql,
)
from .helpers import (
    extract_row_value,
    is_likely_supplier_name,
    is_recommendable_product,
    safe_divide,
    to_float,
)


class ReportRecommendationsMixin:
    def _sku_monthly_sales(self) -> Dict[str, Dict[str, Any]]:
        sql_rows = self._sql_aggregations.get("sku_monthly_sales") or []
        if sql_rows and "sku" in sql_rows[0]:
            return sku_monthly_sales_from_sql(sql_rows)
        product_sales: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"quantity": 0, "revenue": 0.0, "product_name": "Unknown"}
        )
        for row in self._sales_data:
            sku = row.get("ArticulosCodigo")
            if not sku:
                continue
            qty = extract_row_value(row, ["Cantidad"]) or 0
            rev = extract_row_value(row, ["TotalSinIva"]) or 0.0
            product_sales[sku]["quantity"] += int(qty)
            product_sales[sku]["revenue"] += rev
            product_sales[sku]["product_name"] = (
                row.get("ArticulosNombre") or product_sales[sku]["product_name"]
            )
        return dict(product_sales)

    def _calculate_inventory_insights(self) -> Dict[str, Any]:
        if not self.use_j3system or not self._j3system_inventory:
            return {
                "low_stock_alert": [],
                "fast_movers_in_month": [],
                "note": "J3System enrichment disabled or unavailable",
            }
        product_sales = self._sku_monthly_sales()
        fast_movers = []
        for sku, sd in product_sales.items():
            inv = self._j3system_inventory.get(sku)
            if not inv:
                continue
            fast_movers.append(
                {
                    "sku": sku,
                    "product_name": inv.get("name")
                    or sd.get("product_name", "Unknown"),
                    "quantity_sold": sd["quantity"],
                    "revenue": round(sd["revenue"], 2),
                    "current_stock": inv.get("stock_quantity"),
                }
            )
        fast_movers.sort(key=lambda x: x["quantity_sold"], reverse=True)
        low_stock = [
            {
                "sku": i["sku"],
                "product_name": i["product_name"],
                "quantity_sold": i["quantity_sold"],
                "current_stock": i["current_stock"],
            }
            for i in fast_movers
            if i["current_stock"] is not None and i["current_stock"] <= 10
        ][:15]
        return {"low_stock_alert": low_stock, "fast_movers_in_month": fast_movers[:15]}

    def _normalize_vendor(self, vendor: str) -> str:
        """Normalize vendor name by stripping clean and matching against J3System."""
        if not vendor:
            return ""
        v = vendor.strip().upper()
        if v in self._vendor_names:
            return self._vendor_names[v]
        return vendor.strip()

    def _calculate_vendor_sales(self) -> List[Dict[str, Any]]:
        """Revenue breakdown by vendor (proveedor) from banco_datos."""
        sql_rows = self._sql_aggregations.get("vendor_sales") or []
        if sql_rows and "vendor_name" in sql_rows[0]:
            return vendor_sales_from_sql(sql_rows, self._normalize_vendor)

        vendors = defaultdict(
            lambda: {"revenue": 0.0, "cost": 0.0, "quantity": 0, "transactions": 0}
        )
        for row in self._sales_data:
            v = row.get("proveedor")
            if not v:
                continue
            vname = self._normalize_vendor(v)
            if not vname:
                continue
            rev = extract_row_value(row, ["TotalSinIva"]) or 0.0
            cost = extract_row_value(row, ["ValorCosto"]) or 0.0
            qty = extract_row_value(row, ["Cantidad"]) or 0
            vendors[vname]["revenue"] += rev
            vendors[vname]["cost"] += cost
            vendors[vname]["quantity"] += int(qty)
            vendors[vname]["transactions"] += 1
        result = []
        for vname, d in vendors.items():
            profit = d["revenue"] - d["cost"]
            result.append(
                {
                    "vendor_name": vname,
                    "total_revenue": round(d["revenue"], 2),
                    "total_cost": round(d["cost"], 2),
                    "profit": round(profit, 2),
                    "profit_margin_pct": round(
                        safe_divide(profit, d["revenue"], 0.0) * 100, 2
                    ),
                    "total_quantity": d["quantity"],
                    "transactions": d["transactions"],
                    "revenue_pct": round(
                        safe_divide(
                            d["revenue"],
                            sum(v["revenue"] for v in vendors.values()),
                            0.0,
                        )
                        * 100,
                        1,
                    ),
                }
            )
        result.sort(key=lambda x: x["total_revenue"], reverse=True)
        return result[:20]

    def _calculate_marca_sales(self) -> List[Dict[str, Any]]:
        """Revenue breakdown by marca (brand / product line / group) from banco_datos."""
        sql_rows = self._sql_aggregations.get("marca_sales") or []
        if sql_rows and "marca_name" in sql_rows[0]:
            return marca_sales_from_sql(sql_rows)

        marcas = defaultdict(
            lambda: {"revenue": 0.0, "cost": 0.0, "quantity": 0, "transactions": 0}
        )
        for row in self._sales_data:
            m = row.get("marca")
            if not m:
                continue
            mname = m.strip()
            if not mname:
                continue
            rev = extract_row_value(row, ["TotalSinIva"]) or 0.0
            cost = extract_row_value(row, ["ValorCosto"]) or 0.0
            qty = extract_row_value(row, ["Cantidad"]) or 0
            marcas[mname]["revenue"] += rev
            marcas[mname]["cost"] += cost
            marcas[mname]["quantity"] += int(qty)
            marcas[mname]["transactions"] += 1
        result = []
        total_rev = sum(d["revenue"] for d in marcas.values())
        for mname, d in marcas.items():
            profit = d["revenue"] - d["cost"]
            result.append(
                {
                    "marca_name": mname,
                    "total_revenue": round(d["revenue"], 2),
                    "total_cost": round(d["cost"], 2),
                    "profit": round(profit, 2),
                    "profit_margin_pct": round(
                        safe_divide(profit, d["revenue"], 0.0) * 100, 2
                    ),
                    "total_quantity": d["quantity"],
                    "transactions": d["transactions"],
                    "revenue_pct": round(
                        safe_divide(d["revenue"], total_rev, 0.0) * 100, 1
                    ),
                }
            )
        result.sort(key=lambda x: x["total_revenue"], reverse=True)
        return result[:20]

    def _calculate_customer_vendor_mix(self) -> List[Dict[str, Any]]:
        """Cross-reference which customers buy from which vendors."""
        sql_rows = self._sql_aggregations.get("customer_vendor_pairs") or []
        if sql_rows and "customer_name" in sql_rows[0]:
            return customer_vendor_mix_from_sql(sql_rows, self._normalize_vendor)

        mix = defaultdict(
            lambda: defaultdict(lambda: {"revenue": 0.0, "transactions": 0})
        )
        for row in self._sales_data:
            customer = row.get("TercerosNombres") or "Unknown"
            v = row.get("proveedor")
            if not v:
                continue
            vname = self._normalize_vendor(v)
            rev = extract_row_value(row, ["TotalSinIva"]) or 0.0
            mix[customer][vname]["revenue"] += rev
            mix[customer][vname]["transactions"] += 1

        result = []
        for customer, vendors_dict in mix.items():
            total_cust = sum(d["revenue"] for d in vendors_dict.values())
            top_vendors = sorted(
                vendors_dict.items(), key=lambda x: x[1]["revenue"], reverse=True
            )[:5]
            result.append(
                {
                    "customer_name": customer,
                    "total_revenue": round(total_cust, 2),
                    "vendor_count": len(vendors_dict),
                    "top_vendors": [
                        {
                            "vendor_name": vn,
                            "revenue": round(vd["revenue"], 2),
                            "pct": round(
                                safe_divide(vd["revenue"], total_cust, 0.0) * 100, 1
                            ),
                        }
                        for vn, vd in top_vendors
                    ],
                }
            )
        result.sort(key=lambda x: x["total_revenue"], reverse=True)
        return result[:15]

    def _calculate_suggested_orders(self) -> List[Dict[str, Any]]:
        """
        Generate suggested reorder quantities per customer based on YTD purchase patterns.
        For each top customer, figures out which products they buy regularly and suggests
        restocking quantities based on average monthly consumption and current inventory.
        """
        ytd_sql = self._ytd_sql_aggregations or {}
        product_rows = ytd_sql.get("customer_products") or []
        vendor_rows = ytd_sql.get("primary_vendors") or []
        if product_rows and "customer_name" in product_rows[0]:
            ytd = ytd_customer_products_from_sql(product_rows, vendor_rows)
        elif not self._ytd_sales_data:
            return []
        else:
            ytd = defaultdict(
                lambda: defaultdict(
                    lambda: {
                        "quantity": 0,
                        "revenue": 0.0,
                        "last_purchase": None,
                        "vendors": defaultdict(int),
                    }
                )
            )
            for row in self._ytd_sales_data:
                customer = row.get("TercerosNombres") or "Unknown"
                sku = row.get("ArticulosCodigo") or ""
                pname = row.get("ArticulosNombre") or "Unknown"
                qty = extract_row_value(row, ["Cantidad"]) or 0
                rev = extract_row_value(row, ["TotalSinIva"]) or 0.0
                fecha = row.get("Fecha")
                date_str = (
                    fecha.strftime("%Y-%m-%d")
                    if hasattr(fecha, "strftime")
                    else str(fecha)[:10]
                )
                ytd[customer][sku]["quantity"] += int(qty)
                ytd[customer][sku]["revenue"] += rev
                ytd[customer][sku]["product_name"] = pname
                m = row.get("marca")
                if m:
                    ytd[customer][sku]["marca"] = m.strip()
                if (
                    ytd[customer][sku]["last_purchase"] is None
                    or date_str > ytd[customer][sku]["last_purchase"]
                ):
                    ytd[customer][sku]["last_purchase"] = date_str
                v = row.get("proveedor")
                if v:
                    vnorm = self._normalize_vendor(v)
                    ytd[customer][sku]["vendors"][vnorm] += int(qty)

        months_elapsed = max(self.month, 1)
        top_customers = self._calculate_top_customers()
        suggestions = []
        for tc in top_customers[:10]:
            cname = tc["customer_name"]
            customer_products = ytd.get(cname, {})
            if not customer_products:
                continue
            items = []
            for sku, pd in customer_products.items():
                avg_monthly = pd["quantity"] / months_elapsed
                stock = None
                if self.use_j3system:
                    inv = self._j3system_inventory.get(sku)
                    if inv:
                        stock = inv.get("stock_quantity")
                suggested = max(0, int(avg_monthly * 1.5 - (stock or 0)))
                if suggested > 0 and is_recommendable_product(pd["product_name"]):
                    # Mix vendor: prefer J3 authoritative vendor, fall back to sales data primary
                    j3_vendor = None
                    if sku and self._j3system_products:
                        j3_vendor = self._j3system_products.get(sku, {}).get(
                            "vendor_name"
                        )
                    primary_from_sales = pd.get("primary_vendor") or ""
                    if not primary_from_sales and pd.get("vendors"):
                        primary_from_sales = max(
                            pd["vendors"].items(), key=lambda x: x[1]
                        )[0]
                    vendor_for_item = j3_vendor or primary_from_sales
                    if vendor_for_item:
                        vp = str(vendor_for_item).strip()
                        if (
                            vp.upper()
                            in (
                                "",
                                "S/I",
                                "S.I",
                                "SIN PROVEEDOR",
                                "N/A",
                                ".",
                                "SIN IVA",
                                "NA",
                            )
                            or len(vp) <= 2
                        ):
                            vendor_for_item = ""
                    m = pd.get("marca", "") or ""
                    if m:
                        mp = str(m).strip()
                        if (
                            mp.upper()
                            in (
                                "",
                                "S/I",
                                "S.I",
                                "SIN PROVEEDOR",
                                "N/A",
                                ".",
                                "SIN IVA",
                                "NA",
                            )
                            or len(mp) <= 2
                        ):
                            m = ""
                    items.append(
                        {
                            "product_name": pd["product_name"],
                            "sku": sku,
                            "ytd_quantity": pd["quantity"],
                            "avg_monthly": round(avg_monthly, 1),
                            "current_stock": stock,
                            "suggested_order": suggested,
                            "last_purchase": pd["last_purchase"],
                            "ytd_revenue": round(pd["revenue"], 2),
                            "primary_vendor": vendor_for_item,
                            "marca": m,
                        }
                    )
            items.sort(key=lambda x: x["suggested_order"], reverse=True)
            suggestions.append(
                {
                    "customer_name": cname,
                    "monthly_revenue": round(tc["total_revenue"], 2),
                    "suggested_items": items[:10],
                    "total_suggested": sum(i["suggested_order"] for i in items),
                }
            )
        return suggestions

    def _calculate_procurement_plan(
        self, order_suggestions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Build a consolidated procurement / shopping plan by vendor.

        Uses the per-customer YTD-based suggested orders (which include primary_vendor)
        and aggregates into actionable purchase suggestions per vendor:
        - Total units the store may need to acquire from that vendor
        - Which top customers drive the demand (mix vendors with customers)
        - Key products and quantities to buy

        This provides the "plan for shopping recommendations or suggestions".
        """
        if not order_suggestions:
            return []

        vendor_agg: Dict[str, Dict] = defaultdict(
            lambda: {
                "total_units": 0,
                "customers": set(),
                "products": defaultdict(
                    lambda: {
                        "suggested": 0,
                        "customers": set(),
                        "ytd_rev": 0.0,
                        "name": "",
                        "sku": "",
                    }
                ),
            }
        )

        bad_vendors = {"", "SIN PROVEEDOR", "S/I", "S.I", "N/A", ".", "SIN IVA", "NA"}
        for sug in order_suggestions:
            cname = sug.get("customer_name", "Unknown")
            for item in sug.get("suggested_items", []):
                v = (item.get("primary_vendor") or "").strip()
                if not v or v.upper() in bad_vendors or len(v) < 3:
                    continue
                if not is_likely_supplier_name(v):
                    continue  # product name leaked as "vendor" (e.g. 'BARRA CORRUGADA 1/2'); skip
                units = int(item.get("suggested_order", 0) or 0)
                if units <= 0:
                    continue
                sku = item.get("sku", "") or ""
                pname = item.get("product_name", "Unknown")
                yrev = float(item.get("ytd_revenue", 0.0) or 0.0)

                va = vendor_agg[v]
                va["total_units"] += units
                va["customers"].add(cname)
                pa = va["products"][sku or pname]
                pa["suggested"] += units
                pa["customers"].add(cname)
                pa["ytd_rev"] += yrev
                pa["name"] = pname
                pa["sku"] = sku

        result: List[Dict[str, Any]] = []
        for vname, va in vendor_agg.items():
            key_prods: List[Dict[str, Any]] = []
            for _k, pa in va["products"].items():
                key_prods.append(
                    {
                        "product_name": pa["name"],
                        "sku": pa["sku"],
                        "suggested_order": pa["suggested"],
                        "affected_customers": len(pa["customers"]),
                        "ytd_revenue": round(pa["ytd_rev"], 2),
                    }
                )
            key_prods.sort(key=lambda x: x["suggested_order"], reverse=True)
            result.append(
                {
                    "vendor_name": vname,
                    "total_suggested_units": va["total_units"],
                    "affected_customers": len(va["customers"]),
                    "key_products": key_prods[:8],
                }
            )
        result.sort(key=lambda x: x["total_suggested_units"], reverse=True)
        return result[:15]

    def _calculate_abc_analysis(self) -> Dict[str, Any]:
        """ABC analysis (80/15/5 rule) for products, customers, and vendors."""
        sql = self._sql_aggregations or {}
        abc_p = sql.get("abc_products") or []
        abc_c = sql.get("abc_customers") or []
        abc_v = sql.get("abc_vendors") or []
        if (
            abc_p
            and "entity_name" in abc_p[0]
            and abc_c
            and "entity_name" in abc_c[0]
            and abc_v
            and "entity_name" in abc_v[0]
        ):
            return {
                "products": abc_buckets_from_sql(abc_p),
                "customers": abc_buckets_from_sql(abc_c),
                "vendors": abc_buckets_from_sql(abc_v),
            }

        prod_rev = defaultdict(float)
        for row in self._sales_data:
            name = row.get("ArticulosNombre") or "Unknown"
            rev = extract_row_value(row, ["TotalSinIva"]) or 0.0
            prod_rev[name] += rev
        sorted_prods = sorted(prod_rev.items(), key=lambda x: x[1], reverse=True)
        total_p = sum(prod_rev.values()) or 1.0
        cum = 0.0
        a_p = b_p = c_p = a_rev_p = b_rev_p = c_rev_p = 0
        for i, (n, r) in enumerate(sorted_prods):
            cum += r
            if cum / total_p * 100 <= 80:
                a_p += 1
                a_rev_p += r
            elif cum / total_p * 100 <= 95:
                b_p += 1
                b_rev_p += r
            else:
                c_p += 1
                c_rev_p += r
        # Customers (exclude internal)
        excluded_c = {
            "DEPOSITO TRUJILLO SAS",
            "DEPOSITO TRUJILLO S.A.S",
            "DEPOSITO TRUJILLO",
        }
        cust_rev = defaultdict(float)
        for row in self._sales_data:
            name = row.get("TercerosNombres") or "Unknown"
            if name.upper() in excluded_c:
                continue
            rev = extract_row_value(row, ["TotalMasIva"]) or 0.0
            cust_rev[name] += rev
        sorted_c = sorted(cust_rev.items(), key=lambda x: x[1], reverse=True)
        total_c = sum(cust_rev.values()) or 1.0
        cum = 0.0
        a_c = b_c = c_c = a_rev_c = b_rev_c = c_rev_c = 0
        for n, r in sorted_c:
            cum += r
            if cum / total_c * 100 <= 80:
                a_c += 1
                a_rev_c += r
            elif cum / total_c * 100 <= 95:
                b_c += 1
                b_rev_c += r
            else:
                c_c += 1
                c_rev_c += r
        # Vendors (proveedor)
        vend_rev = defaultdict(float)
        for row in self._sales_data:
            v = row.get("proveedor")
            if not v:
                continue
            vname = self._normalize_vendor(v) or v
            rev = extract_row_value(row, ["TotalSinIva"]) or 0.0
            vend_rev[vname] += rev
        sorted_v = sorted(vend_rev.items(), key=lambda x: x[1], reverse=True)
        total_v = sum(vend_rev.values()) or 1.0
        cum = 0.0
        a_v = b_v = c_v = a_rev_v = b_rev_v = c_rev_v = 0
        for n, r in sorted_v:
            cum += r
            if cum / total_v * 100 <= 80:
                a_v += 1
                a_rev_v += r
            elif cum / total_v * 100 <= 95:
                b_v += 1
                b_rev_v += r
            else:
                c_v += 1
                c_rev_v += r
        return {
            "products": {
                "a": {
                    "count": a_p,
                    "revenue": round(a_rev_p, 2),
                    "revenue_pct": round(a_rev_p / total_p * 100, 1),
                },
                "b": {
                    "count": b_p,
                    "revenue": round(b_rev_p, 2),
                    "revenue_pct": round(b_rev_p / total_p * 100, 1),
                },
                "c": {
                    "count": c_p,
                    "revenue": round(c_rev_p, 2),
                    "revenue_pct": round(c_rev_p / total_p * 100, 1),
                },
                "total": len(sorted_prods),
            },
            "customers": {
                "a": {
                    "count": a_c,
                    "revenue": round(a_rev_c, 2),
                    "revenue_pct": round(a_rev_c / total_c * 100, 1),
                },
                "b": {
                    "count": b_c,
                    "revenue": round(b_rev_c, 2),
                    "revenue_pct": round(b_rev_c / total_c * 100, 1),
                },
                "c": {
                    "count": c_c,
                    "revenue": round(c_rev_c, 2),
                    "revenue_pct": round(c_rev_c / total_c * 100, 1),
                },
                "total": len(sorted_c),
            },
            "vendors": {
                "a": {
                    "count": a_v,
                    "revenue": round(a_rev_v, 2),
                    "revenue_pct": round(a_rev_v / total_v * 100, 1),
                },
                "b": {
                    "count": b_v,
                    "revenue": round(b_rev_v, 2),
                    "revenue_pct": round(b_rev_v / total_v * 100, 1),
                },
                "c": {
                    "count": c_v,
                    "revenue": round(c_rev_v, 2),
                    "revenue_pct": round(c_rev_v / total_v * 100, 1),
                },
                "total": len(sorted_v),
            },
        }

    def _calculate_stock_replenishment_suggestions(self) -> List[Dict[str, Any]]:
        """Suggested items to shop (replenish) based on low stock + sales velocity (using J3 stock data).
        Addresses 'suggested shopping with missing stock'. Computed from inventory + sales.
        Enriched with marca/proveedor from master.
        If no strict low-stock (<=10) items, falls back to top fast-movers so the section is always useful.
        """
        if not self.use_j3system or not self._j3system_inventory:
            return []
        insights = self._calculate_inventory_insights()
        low_stock = (
            insights.get("low_stock_alert", []) if isinstance(insights, dict) else []
        )
        fast = (
            insights.get("fast_movers_in_month", [])
            if isinstance(insights, dict)
            else []
        )

        source = low_stock if low_stock else fast[:8]
        reason = (
            "stock bajo + movimiento rápido (J3 + ventas SmartBusiness)"
            if low_stock
            else "alto movimiento reciente - revisar stock actual en J3"
        )

        result = []
        for item in source[:8]:
            sku = item.get("sku")
            master = (
                self._j3system_products.get(sku, {}) if self._j3system_products else {}
            )
            result.append(
                {
                    "sku": sku,
                    "product_name": item.get("product_name"),
                    "marca": master.get("marca", ""),
                    "proveedor": master.get("vendor_name", ""),
                    "current_stock": item.get("current_stock"),
                    "recent_sold": item.get("quantity_sold"),
                    "reason": reason,
                    "priority": "alta"
                    if (item.get("current_stock") or 99) <= 10
                    else "monitorear",
                }
            )
        return result

    def _calculate_shopping_recommendations(self) -> List[Dict[str, Any]]:
        """
        Generate cross-sell / shopping recommendations:
        - Products frequently bought together (co-occurrence within same customer)
        - Products with high margins that should be pushed
        - Under-exploited vendor products
        """
        basket_rows = self._sql_aggregations.get("customer_baskets") or []
        margin_rows = self._sql_aggregations.get("product_margins") or []

        customer_baskets: Dict[str, set] = defaultdict(set)
        vendor_products: Dict[str, set] = defaultdict(set)
        product_info: Dict[str, Dict] = {}
        product_revenue: Dict[str, float] = defaultdict(float)

        if basket_rows and "customer_name" in basket_rows[0]:
            for row in basket_rows:
                customer = row.get("customer_name") or "Unknown"
                pname = row.get("product_name") or "Unknown"
                sku = row.get("sku") or ""
                v = row.get("proveedor") or ""
                vname = self._normalize_vendor(v) if v else ""
                customer_baskets[customer].add(pname)
                if vname:
                    vendor_products[vname].add(pname)
                if pname not in product_info:
                    product_info[pname] = {"product_name": pname, "sku": sku}
            for row in margin_rows:
                pname = row.get("product_name") or "Unknown"
                product_revenue[pname] = to_float(row.get("revenue")) or 0.0
        elif not self._sales_data:
            return []
        else:
            for row in self._sales_data:
                customer = row.get("TercerosNombres") or "Unknown"
                pname = row.get("ArticulosNombre") or "Unknown"
                sku = row.get("ArticulosCodigo") or ""
                v = row.get("proveedor") or ""
                vname = self._normalize_vendor(v)
                rev = extract_row_value(row, ["TotalSinIva"]) or 0.0

                customer_baskets[customer].add(pname)
                if vname:
                    vendor_products[vname].add(pname)
                if pname not in product_info:
                    product_info[pname] = {"product_name": pname, "sku": sku}
                product_revenue[pname] += rev

        # Product affinity: products bought by the same customers
        product_customers: Dict[str, set] = defaultdict(set)
        for customer, products in customer_baskets.items():
            for p in products:
                product_customers[p].add(customer)

        # Cross-sell pairs
        cross_sell: List[Dict] = []
        viewed_products = set()
        product_list = sorted(product_revenue.items(), key=lambda x: x[1], reverse=True)

        for pname, rev in product_list[:20]:
            if pname in viewed_products:
                continue
            buyers = product_customers.get(pname, set())
            if len(buyers) < 2:
                continue
            co_products = []
            for other_p, other_customers in product_customers.items():
                if other_p == pname or other_p in viewed_products:
                    continue
                overlap = len(buyers & other_customers)
                if overlap >= 2:
                    co_products.append(
                        {"product_name": other_p, "common_customers": overlap}
                    )
            if co_products:
                co_products.sort(key=lambda x: x["common_customers"], reverse=True)
                cross_sell.append(
                    {
                        "product_name": pname,
                        "buyers": len(buyers),
                        "revenue": round(rev, 2),
                        "recommended_with": co_products[:3],
                    }
                )
                viewed_products.add(pname)

        margin_promote = []
        products_with_margin: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"revenue": 0.0, "cost": 0.0, "quantity": 0}
        )
        if margin_rows and "product_name" in margin_rows[0]:
            for row in margin_rows:
                pname = row.get("product_name") or "Unknown"
                products_with_margin[pname]["revenue"] = (
                    to_float(row.get("revenue")) or 0.0
                )
                products_with_margin[pname]["cost"] = to_float(row.get("cost")) or 0.0
                products_with_margin[pname]["quantity"] = int(
                    to_float(row.get("quantity")) or 0
                )
        else:
            for row in self._sales_data:
                pname = row.get("ArticulosNombre") or "Unknown"
                rev = extract_row_value(row, ["TotalSinIva"]) or 0.0
                cost = extract_row_value(row, ["ValorCosto"]) or 0.0
                qty = extract_row_value(row, ["Cantidad"]) or 0
                products_with_margin[pname]["revenue"] += rev
                products_with_margin[pname]["cost"] += cost
                products_with_margin[pname]["quantity"] += int(qty)
        for pname, d in products_with_margin.items():
            margin = safe_divide(d["revenue"] - d["cost"], d["revenue"], 0.0) * 100
            if margin >= 20 and d["quantity"] >= 5 and is_recommendable_product(pname):
                margin_promote.append(
                    {
                        "product_name": pname,
                        "margin_pct": round(margin, 1),
                        "revenue": round(d["revenue"], 2),
                        "quantity_sold": d["quantity"],
                    }
                )
        margin_promote.sort(key=lambda x: x["margin_pct"], reverse=True)

        return {
            "cross_sell": cross_sell[:10],
            "high_margin_promote": margin_promote[:10],
        }
