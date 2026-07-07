"""Aggregate sales metrics from SQL results or in-memory rows."""

from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional

from .helpers import (
    EXCLUDED_CUSTOMERS,
    extract_row_value,
    is_excluded_product,
    safe_divide,
    to_float,
)


def summary_from_sql(row: Dict[str, Any]) -> Dict[str, Any]:
    total_with_iva = to_float(row.get("total_with_iva")) or 0.0
    total_without_iva = to_float(row.get("total_without_iva")) or 0.0
    total_cost = to_float(row.get("total_cost")) or 0.0
    total_quantity = int(to_float(row.get("total_quantity")) or 0)
    order_count = int(to_float(row.get("order_count")) or 0)
    gross_profit = total_without_iva - total_cost
    return {
        "total_revenue_with_iva": round(total_with_iva, 2),
        "total_revenue_without_iva": round(total_without_iva, 2),
        "total_cost": round(total_cost, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_margin_pct": round(
            safe_divide(gross_profit, total_without_iva, 0.0) * 100, 2
        ),
        "total_quantity_sold": total_quantity,
        "order_count": order_count,
        "average_order_value": round(safe_divide(total_with_iva, order_count, 0.0), 2),
        "average_order_profit": round(safe_divide(gross_profit, order_count, 0.0), 2),
    }


def summary_from_rows(sales_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_with_iva = total_without_iva = total_cost = 0.0
    total_quantity = order_count = 0
    for row in sales_data:
        riva = extract_row_value(row, ["TotalMasIva", "PrecioTotal"])
        rniva = extract_row_value(row, ["TotalSinIva", "PrecioUnitario"])
        cost = extract_row_value(row, ["ValorCosto", "CostoUnitario"])
        qty = extract_row_value(row, ["Cantidad", "quantity"])
        if riva is not None:
            total_with_iva += riva
        if rniva is not None:
            total_without_iva += rniva
        if cost is not None:
            total_cost += cost
        if qty is not None:
            total_quantity += int(qty)
        order_count += 1
    gross_profit = total_without_iva - total_cost
    return {
        "total_revenue_with_iva": round(total_with_iva, 2),
        "total_revenue_without_iva": round(total_without_iva, 2),
        "total_cost": round(total_cost, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_margin_pct": round(
            safe_divide(gross_profit, total_without_iva, 0.0) * 100, 2
        ),
        "total_quantity_sold": total_quantity,
        "order_count": order_count,
        "average_order_value": round(safe_divide(total_with_iva, order_count, 0.0), 2),
        "average_order_profit": round(safe_divide(gross_profit, order_count, 0.0), 2),
    }


def top_products_from_sql(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result = []
    for row in rows:
        pname = row.get("product_name") or "Unknown"
        if is_excluded_product(pname):
            continue
        revenue = to_float(row.get("total_revenue")) or 0.0
        cost = to_float(row.get("total_cost")) or 0.0
        profit = revenue - cost
        result.append(
            {
                "product_name": pname,
                "sku": row.get("sku") or "",
                "total_revenue": round(revenue, 2),
                "total_quantity": int(to_float(row.get("total_quantity")) or 0),
                "profit": round(profit, 2),
                "profit_margin_pct": round(safe_divide(profit, revenue, 0.0) * 100, 2),
                "transactions": int(to_float(row.get("transactions")) or 0),
            }
        )
    return result


def top_products_from_rows(sales_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    products = defaultdict(
        lambda: {
            "sku": "",
            "total_revenue": 0.0,
            "total_cost": 0.0,
            "total_quantity": 0,
            "transactions": 0,
        }
    )
    for row in sales_data:
        name = row.get("ArticulosNombre") or "Unknown"
        if is_excluded_product(name):
            continue
        sku = row.get("ArticulosCodigo") or ""
        revenue = extract_row_value(row, ["TotalSinIva", "TotalMasIva"]) or 0.0
        cost = extract_row_value(row, ["ValorCosto"]) or 0.0
        qty = extract_row_value(row, ["Cantidad"]) or 0
        products[name]["sku"] = sku or products[name]["sku"]
        products[name]["total_revenue"] += revenue
        products[name]["total_cost"] += cost
        products[name]["total_quantity"] += int(qty)
        products[name]["transactions"] += 1
    plist = []
    for name, d in products.items():
        profit = d["total_revenue"] - d["total_cost"]
        plist.append(
            {
                "product_name": name,
                "sku": d["sku"],
                "total_revenue": round(d["total_revenue"], 2),
                "total_quantity": d["total_quantity"],
                "profit": round(profit, 2),
                "profit_margin_pct": round(
                    safe_divide(profit, d["total_revenue"], 0.0) * 100, 2
                ),
                "transactions": d["transactions"],
            }
        )
    plist.sort(key=lambda x: x["total_revenue"], reverse=True)
    return plist[:15]


def top_customers_from_sql(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result = []
    for row in rows:
        revenue = to_float(row.get("total_revenue")) or 0.0
        cost = to_float(row.get("total_cost")) or 0.0
        orders = int(to_float(row.get("total_orders")) or 0)
        profit = revenue - cost
        result.append(
            {
                "customer_name": row.get("customer_name") or "Unknown",
                "total_revenue": round(revenue, 2),
                "total_cost": round(cost, 2),
                "profit": round(profit, 2),
                "profit_margin_pct": round(safe_divide(profit, revenue, 0.0) * 100, 2),
                "total_orders": orders,
                "average_order_value": round(safe_divide(revenue, orders, 0.0), 2),
                "total_quantity": int(to_float(row.get("total_quantity")) or 0),
            }
        )
    return result


def top_customers_from_rows(sales_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    customers = defaultdict(
        lambda: {
            "total_revenue": 0.0,
            "total_orders": 0,
            "total_quantity": 0,
            "total_cost": 0.0,
        }
    )
    for row in sales_data:
        name = row.get("TercerosNombres") or "Unknown"
        if name.upper() in EXCLUDED_CUSTOMERS:
            continue
        revenue = extract_row_value(row, ["TotalMasIva"]) or 0.0
        cost = extract_row_value(row, ["ValorCosto"]) or 0.0
        qty = extract_row_value(row, ["Cantidad"]) or 0
        customers[name]["total_revenue"] += revenue
        customers[name]["total_orders"] += 1
        customers[name]["total_quantity"] += int(qty)
        customers[name]["total_cost"] += cost
    clist = []
    for name, d in customers.items():
        profit = d["total_revenue"] - d["total_cost"]
        clist.append(
            {
                "customer_name": name,
                "total_revenue": round(d["total_revenue"], 2),
                "total_cost": round(d["total_cost"], 2),
                "profit": round(profit, 2),
                "profit_margin_pct": round(
                    safe_divide(profit, d["total_revenue"], 0.0) * 100, 2
                ),
                "total_orders": d["total_orders"],
                "average_order_value": round(
                    safe_divide(d["total_revenue"], d["total_orders"], 0.0), 2
                ),
                "total_quantity": d["total_quantity"],
            }
        )
    clist.sort(key=lambda x: x["total_revenue"], reverse=True)
    return clist[:15]


def category_breakdown_from_sql(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result = []
    for row in rows:
        key = f"{row.get('categoria', 'Sin Categoría')} > {row.get('subcategoria', 'Sin Subcategoría')}"
        revenue = to_float(row.get("total_revenue")) or 0.0
        cost = to_float(row.get("total_cost")) or 0.0
        profit = revenue - cost
        result.append(
            {
                "category_path": key,
                "total_revenue": round(revenue, 2),
                "total_cost": round(cost, 2),
                "profit": round(profit, 2),
                "profit_margin_pct": round(safe_divide(profit, revenue, 0.0) * 100, 2),
                "total_quantity": int(to_float(row.get("total_quantity")) or 0),
                "transactions": int(to_float(row.get("transactions")) or 0),
            }
        )
    return result


def category_breakdown_from_rows(
    sales_data: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    cats = defaultdict(
        lambda: {
            "total_revenue": 0.0,
            "total_cost": 0.0,
            "total_quantity": 0,
            "transactions": 0,
        }
    )
    for row in sales_data:
        key = f"{row.get('categoria', 'Sin Categoría')} > {row.get('subcategoria', 'Sin Subcategoría')}"
        rev = extract_row_value(row, ["TotalSinIva"]) or 0.0
        cost = extract_row_value(row, ["ValorCosto"]) or 0.0
        qty = extract_row_value(row, ["Cantidad"]) or 0
        cats[key]["total_revenue"] += rev
        cats[key]["total_cost"] += cost
        cats[key]["total_quantity"] += int(qty)
        cats[key]["transactions"] += 1
    result = []
    for key, d in cats.items():
        profit = d["total_revenue"] - d["total_cost"]
        result.append(
            {
                "category_path": key,
                "total_revenue": round(d["total_revenue"], 2),
                "total_cost": round(d["total_cost"], 2),
                "profit": round(profit, 2),
                "profit_margin_pct": round(
                    safe_divide(profit, d["total_revenue"], 0.0) * 100, 2
                ),
                "total_quantity": d["total_quantity"],
                "transactions": d["transactions"],
            }
        )
    result.sort(key=lambda x: x["total_revenue"], reverse=True)
    return result


def daily_trend_from_sql(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    trend = []
    for row in rows:
        sale_date = row.get("sale_date")
        if sale_date is None:
            continue
        date_key = (
            sale_date.strftime("%Y-%m-%d")
            if hasattr(sale_date, "strftime")
            else str(sale_date)[:10]
        )
        riva = to_float(row.get("revenue_with_iva")) or 0.0
        rniva = to_float(row.get("revenue_without_iva")) or 0.0
        cost = to_float(row.get("cost")) or 0.0
        profit = rniva - cost
        trend.append(
            {
                "date": date_key,
                "revenue_with_iva": round(riva, 2),
                "revenue_without_iva": round(rniva, 2),
                "cost": round(cost, 2),
                "profit": round(profit, 2),
                "profit_margin_pct": round(safe_divide(profit, rniva, 0.0) * 100, 2),
                "quantity": int(to_float(row.get("quantity")) or 0),
                "orders": int(to_float(row.get("orders")) or 0),
            }
        )
    return trend


def daily_trend_from_rows(sales_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    daily = defaultdict(
        lambda: {
            "revenue_with_iva": 0.0,
            "revenue_without_iva": 0.0,
            "cost": 0.0,
            "quantity": 0,
            "orders": 0,
        }
    )
    for row in sales_data:
        fecha = row.get("Fecha")
        if fecha is None:
            continue
        date_key = (
            fecha.strftime("%Y-%m-%d")
            if hasattr(fecha, "strftime")
            else str(fecha)[:10]
        )
        riva = extract_row_value(row, ["TotalMasIva"]) or 0.0
        rniva = extract_row_value(row, ["TotalSinIva"]) or 0.0
        cost = extract_row_value(row, ["ValorCosto"]) or 0.0
        qty = extract_row_value(row, ["Cantidad"]) or 0
        daily[date_key]["revenue_with_iva"] += riva
        daily[date_key]["revenue_without_iva"] += rniva
        daily[date_key]["cost"] += cost
        daily[date_key]["quantity"] += int(qty)
        daily[date_key]["orders"] += 1
    trend = []
    for dk in sorted(daily.keys()):
        d = daily[dk]
        profit = d["revenue_without_iva"] - d["cost"]
        trend.append(
            {
                "date": dk,
                "revenue_with_iva": round(d["revenue_with_iva"], 2),
                "revenue_without_iva": round(d["revenue_without_iva"], 2),
                "cost": round(d["cost"], 2),
                "profit": round(profit, 2),
                "profit_margin_pct": round(
                    safe_divide(profit, d["revenue_without_iva"], 0.0) * 100, 2
                ),
                "quantity": d["quantity"],
                "orders": d["orders"],
            }
        )
    return trend


def warehouse_breakdown_from_sql(
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Normalize J3System warehouse breakdown rows for manager reports."""
    result = []
    total_rev = sum(to_float(r.get("revenue_without_iva")) or 0.0 for r in rows)
    for row in rows:
        code = (row.get("warehouse_code") or "").strip()
        if not code:
            continue
        revenue = to_float(row.get("revenue_without_iva")) or 0.0
        revenue_iva = to_float(row.get("revenue_with_iva")) or 0.0
        result.append(
            {
                "warehouse_code": code,
                "warehouse_name": (row.get("warehouse_name") or code).strip(),
                "sale_count": int(to_float(row.get("sale_count")) or 0),
                "revenue_without_iva": round(revenue, 2),
                "revenue_with_iva": round(revenue_iva, 2),
                "quantity": round(to_float(row.get("quantity")) or 0.0, 2),
                "revenue_pct": round(safe_divide(revenue, total_rev, 0.0) * 100, 1),
            }
        )
    result.sort(key=lambda x: x["revenue_without_iva"], reverse=True)
    return result


def warehouse_sales_detail_from_sql(
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Normalize one-warehouse-per-sale detail rows."""
    result = []
    for row in rows:
        code = (row.get("warehouse_code") or "").strip()
        if not code:
            continue
        fecha = row.get("Fecha")
        result.append(
            {
                "venta_id": int(to_float(row.get("VentaID")) or 0),
                "numero_documento": to_float(row.get("NumeroDocumento")),
                "fecha": str(fecha)[:10] if fecha is not None else None,
                "nro_factura": (row.get("NroFactura") or "").strip() or None,
                "warehouse_code": code,
                "warehouse_name": (row.get("warehouse_name") or code).strip(),
            }
        )
    return result


def vendor_sales_from_sql(
    rows: List[Dict[str, Any]],
    normalize_vendor: Optional[Callable[[str], str]] = None,
) -> List[Dict[str, Any]]:
    result = []
    total_rev = sum(to_float(r.get("total_revenue")) or 0.0 for r in rows)
    for row in rows:
        vname = str(row.get("vendor_name") or "")
        if normalize_vendor:
            vname = normalize_vendor(vname) or vname
        if not vname:
            continue
        revenue = to_float(row.get("total_revenue")) or 0.0
        cost = to_float(row.get("total_cost")) or 0.0
        profit = revenue - cost
        result.append(
            {
                "vendor_name": vname,
                "total_revenue": round(revenue, 2),
                "total_cost": round(cost, 2),
                "profit": round(profit, 2),
                "profit_margin_pct": round(safe_divide(profit, revenue, 0.0) * 100, 2),
                "total_quantity": int(to_float(row.get("total_quantity")) or 0),
                "transactions": int(to_float(row.get("transactions")) or 0),
                "revenue_pct": round(safe_divide(revenue, total_rev, 0.0) * 100, 1),
            }
        )
    result.sort(key=lambda x: x["total_revenue"], reverse=True)
    return result[:20]


def marca_sales_from_sql(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result = []
    total_rev = sum(to_float(r.get("total_revenue")) or 0.0 for r in rows)
    for row in rows:
        mname = (row.get("marca_name") or "").strip()
        if not mname:
            continue
        revenue = to_float(row.get("total_revenue")) or 0.0
        cost = to_float(row.get("total_cost")) or 0.0
        profit = revenue - cost
        result.append(
            {
                "marca_name": mname,
                "total_revenue": round(revenue, 2),
                "total_cost": round(cost, 2),
                "profit": round(profit, 2),
                "profit_margin_pct": round(safe_divide(profit, revenue, 0.0) * 100, 2),
                "total_quantity": int(to_float(row.get("total_quantity")) or 0),
                "transactions": int(to_float(row.get("transactions")) or 0),
                "revenue_pct": round(safe_divide(revenue, total_rev, 0.0) * 100, 1),
            }
        )
    result.sort(key=lambda x: x["total_revenue"], reverse=True)
    return result[:20]


def customer_vendor_mix_from_sql(
    rows: List[Dict[str, Any]],
    normalize_vendor: Optional[Callable[[str], str]] = None,
) -> List[Dict[str, Any]]:
    mix: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(
        lambda: defaultdict(lambda: {"revenue": 0.0, "transactions": 0})
    )
    for row in rows:
        customer = row.get("customer_name") or "Unknown"
        vname = row.get("vendor_name") or ""
        if normalize_vendor:
            vname = normalize_vendor(vname) or vname
        if not vname:
            continue
        rev = to_float(row.get("revenue")) or 0.0
        tx = int(to_float(row.get("transactions")) or 0)
        mix[customer][vname]["revenue"] += rev
        mix[customer][vname]["transactions"] += tx

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


def sku_monthly_sales_from_sql(
    rows: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        sku = row.get("sku")
        if not sku:
            continue
        out[str(sku)] = {
            "product_name": row.get("product_name") or "Unknown",
            "quantity": int(to_float(row.get("quantity")) or 0),
            "revenue": to_float(row.get("revenue")) or 0.0,
        }
    return out


def abc_buckets_from_sql(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build ABC summary from pre-aggregated revenue rows."""
    sorted_rows = sorted(
        rows,
        key=lambda r: to_float(r.get("total_revenue")) or 0.0,
        reverse=True,
    )
    total = sum(to_float(r.get("total_revenue")) or 0.0 for r in sorted_rows) or 1.0
    cum = 0.0
    a_count = b_count = c_count = 0
    a_rev = b_rev = c_rev = 0.0
    for row in sorted_rows:
        rev = to_float(row.get("total_revenue")) or 0.0
        cum += rev
        pct = cum / total * 100
        if pct <= 80:
            a_count += 1
            a_rev += rev
        elif pct <= 95:
            b_count += 1
            b_rev += rev
        else:
            c_count += 1
            c_rev += rev
    return {
        "a": {
            "count": a_count,
            "revenue": round(a_rev, 2),
            "revenue_pct": round(a_rev / total * 100, 1),
        },
        "b": {
            "count": b_count,
            "revenue": round(b_rev, 2),
            "revenue_pct": round(b_rev / total * 100, 1),
        },
        "c": {
            "count": c_count,
            "revenue": round(c_rev, 2),
            "revenue_pct": round(c_rev / total * 100, 1),
        },
        "total": len(sorted_rows),
    }


def ytd_customer_products_from_sql(
    product_rows: List[Dict[str, Any]],
    vendor_rows: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Rebuild nested YTD structure used by order suggestions."""
    vendor_lookup: Dict[tuple, str] = {}
    for row in vendor_rows:
        key = (row.get("customer_name"), row.get("sku"))
        pv = row.get("primary_vendor")
        if key[0] and key[1] and pv:
            vendor_lookup[key] = str(pv)

    ytd: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
    for row in product_rows:
        customer = row.get("customer_name") or "Unknown"
        sku = row.get("sku") or ""
        if not sku:
            continue
        last_purchase = row.get("last_purchase")
        if hasattr(last_purchase, "strftime"):
            last_purchase = last_purchase.strftime("%Y-%m-%d")
        elif last_purchase is not None:
            last_purchase = str(last_purchase)[:10]
        ytd[customer][sku] = {
            "quantity": int(to_float(row.get("quantity")) or 0),
            "revenue": to_float(row.get("revenue")) or 0.0,
            "product_name": row.get("product_name") or "Unknown",
            "last_purchase": last_purchase,
            "marca": (row.get("marca") or "").strip() if row.get("marca") else "",
            "primary_vendor": vendor_lookup.get((customer, sku), ""),
        }
    return ytd


def budget_vs_actual_from_sql(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Shape presupuesto vs real SQL payload for report consumption."""
    if not payload.get("available"):
        return {
            "available": False,
            "note": payload.get("note"),
            "periodo": payload.get("periodo"),
            "summary": {},
            "sellers": [],
            "underperformers": [],
        }

    summary_row = payload.get("summary") or {}
    presupuesto_total = to_float(summary_row.get("presupuesto_total")) or 0.0
    ventas_total = to_float(summary_row.get("ventas_reales_total")) or 0.0
    cumplimiento = to_float(summary_row.get("cumplimiento_pct")) or 0.0
    brecha = to_float(summary_row.get("brecha_total")) or 0.0

    sellers: List[Dict[str, Any]] = []
    for row in payload.get("sellers") or []:
        presupuesto = to_float(row.get("presupuesto")) or 0.0
        ventas = to_float(row.get("ventas_reales")) or 0.0
        sellers.append(
            {
                "vendedor_codigo": row.get("vendedor_codigo") or "",
                "vendedor_nombre": row.get("vendedor_nombre") or "",
                "presupuesto": round(presupuesto, 2),
                "ventas_reales": round(ventas, 2),
                "facturacion_con_iva": round(
                    to_float(row.get("facturacion_con_iva")) or 0.0, 2
                ),
                "transacciones": int(to_float(row.get("transacciones")) or 0),
                "cumplimiento_pct": round(
                    to_float(row.get("cumplimiento_pct")) or 0.0, 2
                ),
                "brecha": round(to_float(row.get("brecha")) or 0.0, 2),
                "presupuesto_share_pct": round(
                    safe_divide(presupuesto, presupuesto_total, 0.0) * 100, 2
                ),
            }
        )

    underperformers = [
        s for s in sellers if s["presupuesto"] > 0 and s["cumplimiento_pct"] < 90.0
    ]
    underperformers.sort(key=lambda s: s["cumplimiento_pct"])

    return {
        "available": True,
        "note": None,
        "periodo": payload.get("periodo"),
        "summary": {
            "presupuesto_total": round(presupuesto_total, 2),
            "ventas_reales_total": round(ventas_total, 2),
            "cumplimiento_pct": round(cumplimiento, 2),
            "brecha_total": round(brecha, 2),
            "vendedores_con_meta": sum(1 for s in sellers if s["presupuesto"] > 0),
            "vendedores_bajo_90pct": len(underperformers),
        },
        "sellers": sellers,
        "underperformers": underperformers[:10],
    }
