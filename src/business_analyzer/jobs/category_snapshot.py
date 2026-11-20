"""Additive individual-invoice/public-price snapshot for the affinity job."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from business_analyzer.core.database import Database
from business_analyzer.core.j3system_sales_warehouse import qualified_j3_table
from business_analyzer.core.quote_search_iva import build_product
from depotru_integrations.affinity.category_snapshot import STOCK_FIELDS, WINDOW_MONTHS
from depotru_kernel.documents import excluded_document_sql_in_list

# Existing branch invoice contract (sql_routing / manager reports):
# FED = Almacen, FEF = Florencia/Sika Center, FET = Calle 5.
# Positive quantity alone is NOT a document-type filter: use a sale allowlist.
SALE_DOCUMENT_CODES = ("FED", "FEF", "FET")


def invoice_counts_sql(*, table: str = "SmartBusiness.dbo.banco_datos", p="%s") -> str:
    """Count distinct (document code, invoice number) tuples, including solos."""
    if table not in {"SmartBusiness.dbo.banco_datos", "banco_datos"}:
        raise ValueError("invalid source")
    if p not in {"%s", "?"}:
        raise ValueError("invalid placeholder")
    sales = ", ".join(f"'{code}'" for code in SALE_DOCUMENT_CODES)
    return f"""
WITH invoices AS (
    SELECT DISTINCT LTRIM(RTRIM(ArticulosCodigo)) AS sku,
                    DocumentosCodigo, NumeroDocumento
    FROM {table}
    WHERE Fecha >= {p} AND Fecha < {p}
      AND Cantidad > 0
      AND NumeroDocumento IS NOT NULL
      AND DocumentosCodigo IN ({sales})
      AND DocumentosCodigo NOT IN ({excluded_document_sql_in_list()})
)
SELECT sku, COUNT(*) AS invoice_count FROM invoices GROUP BY sku
"""


def compute_category_snapshot(
    *, as_of: date | None = None
) -> dict[str, dict[str, Any]]:
    """Two SELECTs only; never query stock/cost or mutate J3."""
    from business_analyzer.jobs.cross_sell_affinity import _cutoff

    day = as_of or date.today()
    start = _cutoff(day, WINDOW_MONTHS)
    end = datetime.combine(day + timedelta(days=1), time.min)
    articles = qualified_j3_table("AdmArticulos")
    lines = qualified_j3_table("AdmLineas")
    prices_sql = f"""
SELECT a.ArticulosCodigo AS sku, a.ArticulosNombre AS name,
       a.ArticulosVenta AS price, l.LineasPorcentaje AS iva_rate,
       l.LineasID AS line_id
FROM {articles} a
LEFT JOIN {lines} l ON l.LineasID = a.LineasID
"""
    with Database(suppress_error_details=True) as db:
        counts = db.execute_query(invoice_counts_sql(), (start, end))
        prices = db.execute_query(prices_sql)
    if not isinstance(counts, list) or not isinstance(prices, list) or not prices:
        raise RuntimeError("category_snapshot_unavailable")
    totals = {str(row["sku"]).strip(): int(row["invoice_count"]) for row in counts}
    products = {}
    for row in prices:
        sku = str(row["sku"] or "").strip()
        product = build_product(j3_row={**row, "sku": sku})
        for key in STOCK_FIELDS:
            product.pop(key, None)
        if not sku or sku in products:
            raise ValueError("category_snapshot_invalid_sku")
        product["invoice_count"] = totals.get(sku, 0)
        products[sku] = product
    return products
