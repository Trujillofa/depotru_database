"""SQL queries and data fetching for manager sales reports."""

from typing import Any, Dict, List, Optional, Tuple

try:
    from config import Config
except ImportError:
    import sys
    from pathlib import Path

    src_path = Path(__file__).parent.parent.parent.parent
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    from config import Config

from business_analyzer.core.database import ConnectionType, Database
from business_analyzer.core.j3system_sales_warehouse import (
    build_one_warehouse_per_sale_for_period_sql,
    build_warehouse_breakdown_for_period_sql,
)
from business_analyzer.core.product_attrs import effective_marca_sql

from .helpers import EXCLUDED_CUSTOMERS, EXCLUDED_PRODUCT_NAMES, year_month_to_periodo


class SalesQueryRunner:
    """Execute SmartBusiness and J3System queries for a report period."""

    def __init__(
        self,
        start_date: str,
        end_date: str,
        year: int,
        db_connection_type: ConnectionType = ConnectionType.DIRECT,
        conn_details: Optional[Dict[str, Any]] = None,
        branch_document_code: Optional[str] = None,
        month: Optional[int] = None,
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.year = year
        # Prefer explicit month; else derive from start_date (YYYY-MM-DD).
        if month is not None:
            self.month = int(month)
        else:
            self.month = int(str(start_date).split("-")[1])
        self.db_connection_type = db_connection_type
        self.conn_details = conn_details or {}
        self.branch_document_code = (
            branch_document_code.upper() if branch_document_code else None
        )
        if self.branch_document_code:
            Database.validate_sql_identifier(
                self.branch_document_code, "branch document code"
            )

    def _open_db(self) -> Database:
        return Database(
            connection_type=self.db_connection_type,
            conn_details=self.conn_details,
        )

    def _period_params(self) -> Tuple[str, ...]:
        excluded = Config.EXCLUDED_DOCUMENT_CODES
        for code in excluded:
            Database.validate_sql_identifier(code, "excluded code")
        params: Tuple[str, ...] = (self.start_date, self.end_date, *excluded)
        if self.branch_document_code:
            params = params + (self.branch_document_code,)
        params = params + tuple(name.upper() for name in EXCLUDED_PRODUCT_NAMES)
        return params

    def _product_exclusion_sql(self, alias: str = "") -> str:
        col = (
            f"UPPER(LTRIM(RTRIM({alias}ArticulosNombre)))"
            if alias
            else "UPPER(LTRIM(RTRIM(ArticulosNombre)))"
        )
        clauses = [f"{col} <> %s" for _ in EXCLUDED_PRODUCT_NAMES]
        return f" AND {' AND '.join(clauses)}"

    def _branch_filter_sql(self, alias: str = "") -> str:
        if not self.branch_document_code:
            return ""
        col = f"{alias}DocumentosCodigo" if alias else "DocumentosCodigo"
        return f" AND {col} = %s"

    def _sales_from_clause(self) -> str:
        db_name = Database.validate_sql_identifier(Config.DB_NAME, "database")
        table_name = Database.validate_sql_identifier(Config.DB_TABLE, "table")
        excluded = Config.EXCLUDED_DOCUMENT_CODES
        placeholders = ", ".join(["%s"] * len(excluded))
        return (
            f"FROM [{db_name}].[dbo].[{table_name}] "
            f"WHERE Fecha BETWEEN %s AND %s "
            f"AND DocumentosCodigo NOT IN ({placeholders})"
            f"{self._branch_filter_sql()}"
            f"{self._product_exclusion_sql()}"
        )

    def _sales_enriched_from_clause(self, alias: str = "bd") -> str:
        """Period filter with LEFT JOIN to productos_adicional for proveedor/marca."""
        db_name = Database.validate_sql_identifier(Config.DB_NAME, "database")
        table_name = Database.validate_sql_identifier(Config.DB_TABLE, "table")
        excluded = Config.EXCLUDED_DOCUMENT_CODES
        placeholders = ", ".join(["%s"] * len(excluded))
        return (
            f"FROM [{db_name}].[dbo].[{table_name}] {alias} "
            f"LEFT JOIN [{db_name}].[dbo].[productos_adicional] pa "
            f"ON {alias}.ArticulosCodigo = pa.producto_codigo "
            f"WHERE {alias}.Fecha BETWEEN %s AND %s "
            f"AND {alias}.DocumentosCodigo NOT IN ({placeholders})"
            f"{self._branch_filter_sql(alias)}"
            f"{self._product_exclusion_sql(alias)}"
        )

    @staticmethod
    def _effective_proveedor_sql(alias: str = "bd") -> str:
        raw = (
            f"COALESCE({alias}.proveedor COLLATE DATABASE_DEFAULT, "
            f"pa.proveedor_descripcion COLLATE DATABASE_DEFAULT, '')"
        )
        return f"""
        CASE
          WHEN UPPER(LTRIM(RTRIM({raw}))) IN (
              '', 'S/I', 'S.I', 'SIN PROVEEDOR', 'N/A', '.', 'SIN IVA', 'NA'
          ) OR LEN(LTRIM(RTRIM({raw}))) <= 2
          THEN NULL
          ELSE LTRIM(RTRIM(COALESCE(
              NULLIF(LTRIM(RTRIM({alias}.proveedor COLLATE DATABASE_DEFAULT)), ''),
              NULLIF(LTRIM(RTRIM(pa.proveedor_descripcion COLLATE DATABASE_DEFAULT)), '')
          )))
        END
        """  # nosec B608

    @staticmethod
    def _effective_marca_sql(alias: str = "bd") -> str:
        return effective_marca_sql(alias=alias, pa_alias="pa")

    def fetch_sales_data(self) -> List[Dict[str, Any]]:
        db = self._open_db()
        with db:
            query = f"""
                SELECT
                    Fecha, TotalMasIva, TotalSinIva, ValorCosto,
                    Cantidad, TercerosNombres, ArticulosNombre,
                    ArticulosCodigo, categoria, subcategoria, marca,
                    DocumentosCodigo, proveedor
                {self._sales_from_clause()}
                ORDER BY Fecha
            """  # nosec B608
            return db.execute_query(query, self._period_params())

    def fetch_year_to_date_data(self) -> List[Dict[str, Any]]:
        ytd_start = f"{self.year:04d}-01-01"
        ytd_end = f"{self.year:04d}-12-31"
        db = self._open_db()
        with db:
            db_name = Database.validate_sql_identifier(Config.DB_NAME, "database")
            table_name = Database.validate_sql_identifier(Config.DB_TABLE, "table")
            excluded = Config.EXCLUDED_DOCUMENT_CODES
            placeholders = ", ".join(["%s"] * len(excluded))
            query = f"""
                SELECT
                    Fecha, TotalMasIva, TotalSinIva, Cantidad,
                    TercerosNombres, ArticulosCodigo, ArticulosNombre,
                    categoria, marca, proveedor
                FROM [{db_name}].[dbo].[{table_name}]
                WHERE Fecha BETWEEN %s AND %s
                  AND DocumentosCodigo NOT IN ({placeholders})
                  {self._branch_filter_sql()}
                  {self._product_exclusion_sql()}
                ORDER BY TercerosNombres, Fecha
            """  # nosec B608
            params = (ytd_start, ytd_end, *excluded)
            if self.branch_document_code:
                params = params + (self.branch_document_code,)
            params = params + tuple(name.upper() for name in EXCLUDED_PRODUCT_NAMES)
            return db.execute_query(query, params)

    def fetch_sql_aggregations(self) -> Dict[str, Any]:
        """Push-down summary, rankings, category, and daily trend to SQL."""
        db = self._open_db()
        with db:
            from_clause = self._sales_from_clause()
            params = self._period_params()
            excluded_cust = tuple(EXCLUDED_CUSTOMERS)
            cust_placeholders = ", ".join(["%s"] * len(excluded_cust))

            summary = db.execute_query(
                f"""
                SELECT
                    SUM(TotalMasIva) AS total_with_iva,
                    SUM(TotalSinIva) AS total_without_iva,
                    SUM(ValorCosto) AS total_cost,
                    SUM(Cantidad) AS total_quantity,
                    COUNT(*) AS order_count
                {from_clause}
                """,  # nosec B608
                params,
            )

            top_products = db.execute_query(
                f"""
                SELECT TOP 15
                    ArticulosNombre AS product_name,
                    MAX(ArticulosCodigo) AS sku,
                    SUM(TotalSinIva) AS total_revenue,
                    SUM(ValorCosto) AS total_cost,
                    SUM(Cantidad) AS total_quantity,
                    COUNT(*) AS transactions
                {from_clause}
                GROUP BY ArticulosNombre
                ORDER BY SUM(TotalSinIva) DESC
                """,  # nosec B608
                params,
            )

            top_customers = db.execute_query(
                f"""
                SELECT TOP 15
                    TercerosNombres AS customer_name,
                    SUM(TotalMasIva) AS total_revenue,
                    SUM(ValorCosto) AS total_cost,
                    SUM(Cantidad) AS total_quantity,
                    COUNT(*) AS total_orders
                {from_clause}
                  AND UPPER(LTRIM(RTRIM(TercerosNombres))) NOT IN ({cust_placeholders})
                GROUP BY TercerosNombres
                ORDER BY SUM(TotalMasIva) DESC
                """,  # nosec B608
                params + excluded_cust,
            )

            category_breakdown = db.execute_query(
                f"""
                SELECT
                    ISNULL(categoria, 'Sin Categoría') AS categoria,
                    ISNULL(subcategoria, 'Sin Subcategoría') AS subcategoria,
                    SUM(TotalSinIva) AS total_revenue,
                    SUM(ValorCosto) AS total_cost,
                    SUM(Cantidad) AS total_quantity,
                    COUNT(*) AS transactions
                {from_clause}
                GROUP BY categoria, subcategoria
                ORDER BY SUM(TotalSinIva) DESC
                """,  # nosec B608
                params,
            )

            daily_trend = db.execute_query(
                f"""
                SELECT
                    CONVERT(date, Fecha) AS sale_date,
                    SUM(TotalMasIva) AS revenue_with_iva,
                    SUM(TotalSinIva) AS revenue_without_iva,
                    SUM(ValorCosto) AS cost,
                    SUM(Cantidad) AS quantity,
                    COUNT(*) AS orders
                {from_clause}
                GROUP BY CONVERT(date, Fecha)
                ORDER BY sale_date
                """,  # nosec B608
                params,
            )

            enriched_from = self._sales_enriched_from_clause()
            prov_expr = self._effective_proveedor_sql()
            marca_expr = self._effective_marca_sql()

            vendor_sales = db.execute_query(
                f"""
                SELECT TOP 20
                    {prov_expr} AS vendor_name,
                    SUM(bd.TotalSinIva) AS total_revenue,
                    SUM(bd.ValorCosto) AS total_cost,
                    SUM(bd.Cantidad) AS total_quantity,
                    COUNT(*) AS transactions
                {enriched_from}
                  AND {prov_expr} IS NOT NULL
                GROUP BY {prov_expr}
                ORDER BY SUM(bd.TotalSinIva) DESC
                """,  # nosec B608
                params,
            )

            marca_sales = db.execute_query(
                f"""
                SELECT TOP 20
                    {marca_expr} AS marca_name,
                    SUM(bd.TotalSinIva) AS total_revenue,
                    SUM(bd.ValorCosto) AS total_cost,
                    SUM(bd.Cantidad) AS total_quantity,
                    COUNT(*) AS transactions
                {enriched_from}
                  AND {marca_expr} IS NOT NULL
                GROUP BY {marca_expr}
                ORDER BY SUM(bd.TotalSinIva) DESC
                """,  # nosec B608
                params,
            )

            customer_vendor_pairs = db.execute_query(
                f"""
                SELECT
                    bd.TercerosNombres AS customer_name,
                    {prov_expr} AS vendor_name,
                    SUM(bd.TotalSinIva) AS revenue,
                    COUNT(*) AS transactions
                {enriched_from}
                  AND {prov_expr} IS NOT NULL
                  AND UPPER(LTRIM(RTRIM(bd.TercerosNombres))) NOT IN ({cust_placeholders})
                GROUP BY bd.TercerosNombres, {prov_expr}
                """,  # nosec B608
                params + excluded_cust,
            )

            sku_monthly_sales = db.execute_query(
                f"""
                SELECT
                    bd.ArticulosCodigo AS sku,
                    MAX(bd.ArticulosNombre) AS product_name,
                    SUM(bd.Cantidad) AS quantity,
                    SUM(bd.TotalSinIva) AS revenue
                {enriched_from}
                  AND bd.ArticulosCodigo IS NOT NULL
                  AND bd.ArticulosCodigo <> ''
                GROUP BY bd.ArticulosCodigo
                ORDER BY SUM(bd.Cantidad) DESC
                """,  # nosec B608
                params,
            )

            abc_products = db.execute_query(
                f"""
                SELECT
                    bd.ArticulosNombre AS entity_name,
                    SUM(bd.TotalSinIva) AS total_revenue
                {enriched_from}
                GROUP BY bd.ArticulosNombre
                ORDER BY SUM(bd.TotalSinIva) DESC
                """,  # nosec B608
                params,
            )

            abc_customers = db.execute_query(
                f"""
                SELECT
                    bd.TercerosNombres AS entity_name,
                    SUM(bd.TotalMasIva) AS total_revenue
                {enriched_from}
                  AND UPPER(LTRIM(RTRIM(bd.TercerosNombres))) NOT IN ({cust_placeholders})
                GROUP BY bd.TercerosNombres
                ORDER BY SUM(bd.TotalMasIva) DESC
                """,  # nosec B608
                params + excluded_cust,
            )

            abc_vendors = db.execute_query(
                f"""
                SELECT
                    {prov_expr} AS entity_name,
                    SUM(bd.TotalSinIva) AS total_revenue
                {enriched_from}
                  AND {prov_expr} IS NOT NULL
                GROUP BY {prov_expr}
                ORDER BY SUM(bd.TotalSinIva) DESC
                """,  # nosec B608
                params,
            )

            product_margins = db.execute_query(
                f"""
                SELECT
                    bd.ArticulosNombre AS product_name,
                    MAX(bd.ArticulosCodigo) AS sku,
                    SUM(bd.TotalSinIva) AS revenue,
                    SUM(bd.ValorCosto) AS cost,
                    SUM(bd.Cantidad) AS quantity
                {enriched_from}
                GROUP BY bd.ArticulosNombre
                HAVING SUM(bd.Cantidad) >= 5
                ORDER BY SUM(bd.TotalSinIva) DESC
                """,  # nosec B608
                params,
            )

            customer_baskets = db.execute_query(
                f"""
                SELECT DISTINCT
                    bd.TercerosNombres AS customer_name,
                    bd.ArticulosNombre AS product_name,
                    bd.ArticulosCodigo AS sku,
                    {prov_expr} AS proveedor
                {enriched_from}
                """,  # nosec B608
                params,
            )

        return {
            "summary": summary[0] if summary else {},
            "top_products": top_products,
            "top_customers": top_customers,
            "category_breakdown": category_breakdown,
            "daily_trend": daily_trend,
            "vendor_sales": vendor_sales,
            "marca_sales": marca_sales,
            "customer_vendor_pairs": customer_vendor_pairs,
            "sku_monthly_sales": sku_monthly_sales,
            "abc_products": abc_products,
            "abc_customers": abc_customers,
            "abc_vendors": abc_vendors,
            "product_margins": product_margins,
            "customer_baskets": customer_baskets,
        }

    def fetch_ytd_sql_aggregations(self) -> Dict[str, Any]:
        """YTD customer×SKU aggregates for order suggestions (replaces full YTD scan)."""
        ytd_start = f"{self.year:04d}-01-01"
        ytd_end = f"{self.year:04d}-12-31"
        db = self._open_db()
        with db:
            db_name = Database.validate_sql_identifier(Config.DB_NAME, "database")
            table_name = Database.validate_sql_identifier(Config.DB_TABLE, "table")
            excluded = Config.EXCLUDED_DOCUMENT_CODES
            placeholders = ", ".join(["%s"] * len(excluded))
            params = (ytd_start, ytd_end, *excluded)
            if self.branch_document_code:
                params = params + (self.branch_document_code,)
            params = params + tuple(name.upper() for name in EXCLUDED_PRODUCT_NAMES)
            prov_expr = self._effective_proveedor_sql()
            marca_expr = self._effective_marca_sql()

            customer_products = db.execute_query(
                f"""
                SELECT
                    bd.TercerosNombres AS customer_name,
                    bd.ArticulosCodigo AS sku,
                    MAX(bd.ArticulosNombre) AS product_name,
                    SUM(bd.Cantidad) AS quantity,
                    SUM(bd.TotalSinIva) AS revenue,
                    MAX(CONVERT(date, bd.Fecha)) AS last_purchase,
                    MAX({marca_expr}) AS marca
                FROM [{db_name}].[dbo].[{table_name}] bd
                LEFT JOIN [{db_name}].[dbo].[productos_adicional] pa
                    ON bd.ArticulosCodigo = pa.producto_codigo
                WHERE bd.Fecha BETWEEN %s AND %s
                  AND bd.DocumentosCodigo NOT IN ({placeholders})
                  {self._branch_filter_sql("bd.")}
                  {self._product_exclusion_sql("bd.")}
                  AND bd.ArticulosCodigo IS NOT NULL
                  AND bd.ArticulosCodigo <> ''
                GROUP BY bd.TercerosNombres, bd.ArticulosCodigo
                """,  # nosec B608
                params,
            )

            primary_vendors = db.execute_query(
                f"""
                WITH vendor_qty AS (
                    SELECT
                        bd.TercerosNombres AS customer_name,
                        bd.ArticulosCodigo AS sku,
                        {prov_expr} AS vendor_name,
                        SUM(bd.Cantidad) AS qty
                    FROM [{db_name}].[dbo].[{table_name}] bd
                    LEFT JOIN [{db_name}].[dbo].[productos_adicional] pa
                        ON bd.ArticulosCodigo = pa.producto_codigo
                    WHERE bd.Fecha BETWEEN %s AND %s
                      AND bd.DocumentosCodigo NOT IN ({placeholders})
                      {self._branch_filter_sql("bd.")}
                      {self._product_exclusion_sql("bd.")}
                      AND {prov_expr} IS NOT NULL
                    GROUP BY bd.TercerosNombres, bd.ArticulosCodigo, {prov_expr}
                ),
                ranked AS (
                    SELECT
                        customer_name,
                        sku,
                        vendor_name,
                        qty,
                        ROW_NUMBER() OVER (
                            PARTITION BY customer_name, sku
                            ORDER BY qty DESC
                        ) AS rn
                    FROM vendor_qty
                )
                SELECT customer_name, sku, vendor_name AS primary_vendor
                FROM ranked
                WHERE rn = 1
                """,  # nosec B608
                params,
            )

        return {
            "customer_products": customer_products,
            "primary_vendors": primary_vendors,
        }

    def fetch_j3system_warehouse_sales(
        self,
        *,
        detail_limit: int = 50,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """J3System sales-to-warehouse aggregates and per-sale detail for the period."""
        db = self._open_db()
        j3_conn = None
        try:
            j3_conn = db.get_j3system_connection()
            cursor = j3_conn.cursor(as_dict=True)
            breakdown_sql = build_warehouse_breakdown_for_period_sql(
                self.start_date, self.end_date
            )
            cursor.execute(breakdown_sql)
            breakdown = list(cursor)

            detail_sql = build_one_warehouse_per_sale_for_period_sql(
                self.start_date,
                self.end_date,
                top_n=detail_limit,
            )
            cursor.execute(detail_sql)
            sales = list(cursor)
            cursor.close()
        except Exception:
            return {"breakdown": [], "sales": []}
        finally:
            if j3_conn:
                try:
                    j3_conn.close()
                except Exception:
                    pass
        return {"breakdown": breakdown, "sales": sales}

    def fetch_j3system_inventory(self) -> Dict[str, Dict[str, Any]]:
        db = self._open_db()
        j3_conn = None
        try:
            j3_conn = db.get_j3system_connection()
            cursor = j3_conn.cursor(as_dict=True)
            cursor.execute(
                """
                SELECT a.ArticulosCodigo, a.ArticulosNombre, a.ArticulosPeso,
                       e.ExistenciasCantidad AS stock_quantity
                FROM J3System.dbo.AdmArticulos a
                LEFT JOIN J3System.dbo.InvExistencias e ON a.ArticulosCodigo = e.ArticulosCodigo
                WHERE a.ArticulosEstado = 'A'
            """
            )
            rows = list(cursor)
            cursor.close()
        except Exception:
            return {}
        finally:
            if j3_conn:
                try:
                    j3_conn.close()
                except Exception:
                    pass
        inventory: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            code = row.get("ArticulosCodigo")
            if code:
                from .helpers import to_float

                inventory[code] = {
                    "name": row.get("ArticulosNombre"),
                    "weight_kg": to_float(row.get("ArticulosPeso")),
                    "stock_quantity": to_float(row.get("stock_quantity")),
                }
        return inventory

    def fetch_j3system_product_details(
        self,
    ) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str]]:
        db = self._open_db()
        j3_conn = None
        try:
            j3_conn = db.get_j3system_connection()
            cursor = j3_conn.cursor(as_dict=True)
            cursor.execute(
                """
                SELECT a.ArticulosCodigo, a.ArticulosNombre, a.ArticulosPeso, a.GruposCodigo,
                       a.ArticulosMarca AS marca,
                       p.TercerosID AS vendor_terceros_id,
                       t.TercerosNombres AS vendor_name
                FROM J3System.dbo.AdmArticulos a
                LEFT JOIN J3System.dbo.AdmProveedorArt p ON a.ArticulosID = p.ArticulosID
                LEFT JOIN J3System.dbo.AdmTerceros t ON p.TercerosID = t.TercerosID
                WHERE a.ArticulosEstado = 'A'
            """
            )
            rows = list(cursor)
            cursor.close()
        except Exception:
            return {}, {}
        finally:
            if j3_conn:
                try:
                    j3_conn.close()
                except Exception:
                    pass

        from .helpers import to_float

        products: Dict[str, Dict[str, Any]] = {}
        vendor_map: Dict[str, str] = {}
        for row in rows:
            code = row.get("ArticulosCodigo")
            if code and code not in products:
                products[code] = {
                    "name": row.get("ArticulosNombre"),
                    "weight_kg": to_float(row.get("ArticulosPeso")),
                    "group_code": row.get("GruposCodigo"),
                    "vendor_name": row.get("vendor_name"),
                    "marca": row.get("marca"),
                }
            vname = row.get("vendor_name")
            if vname:
                vendor_map[vname.strip().upper()] = vname.strip()
        return products, vendor_map

    def fetch_sb_product_map(self) -> Dict[str, Dict[str, Any]]:
        db = self._open_db()
        with db:
            rows = db.execute_query(
                """
                SELECT
                    producto_codigo,
                    proveedor_descripcion,
                    producto_marca,
                    producto_rubro,
                    producto_subrubro
                FROM productos_adicional
                WHERE producto_codigo IS NOT NULL
            """
            )
        pmap: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            code = row.get("producto_codigo")
            if code:
                prov = row.get("proveedor_descripcion")
                if prov:
                    prov = prov.strip()
                    if prov.upper() in ("NA", "N/A", "") or len(prov) < 2:
                        prov = None
                pmap[code] = {
                    "proveedor": prov,
                    "marca": (row.get("producto_marca") or "").strip() or None,
                    "rubro": (row.get("producto_rubro") or "").strip() or None,
                    "subrubro": (row.get("producto_subrubro") or "").strip() or None,
                }
        return pmap

    def fetch_budget_vs_actual(self) -> Dict[str, Any]:
        """Compare presupuesto_vendedores targets to banco_datos sales for the month."""
        if self.branch_document_code:
            return {
                "available": False,
                "note": (
                    "Presupuesto es consolidado por vendedor; no aplica a reportes por sede."
                ),
                "periodo": year_month_to_periodo(self.year, self.month),
                "sellers": [],
                "summary": {},
            }

        periodo = year_month_to_periodo(self.year, self.month)
        db = self._open_db()
        db_name = Database.validate_sql_identifier(Config.DB_NAME, "database")
        table_name = Database.validate_sql_identifier(Config.DB_TABLE, "table")
        excluded = Config.EXCLUDED_DOCUMENT_CODES
        placeholders = ", ".join(["%s"] * len(excluded))

        with db:
            # Prefer exact sales period; else latest prior year with same calendar month.
            meta_period_rows = db.execute_query(
                f"""
                SELECT TOP 1 p.periodo
                FROM (
                    SELECT pv.periodo, 0 AS preferencia
                    FROM [{db_name}].[dbo].[presupuesto_vendedores] pv
                    WHERE pv.periodo = %s
                    UNION ALL
                    SELECT pv.periodo, 1 AS preferencia
                    FROM [{db_name}].[dbo].[presupuesto_vendedores] pv
                    WHERE pv.periodo <> %s
                      AND (
                            CASE
                                WHEN pv.periodo >= 100000 THEN pv.periodo %% 100
                                ELSE pv.periodo %% 10
                            END
                          ) = %s
                      AND (
                            CASE
                                WHEN pv.periodo >= 100000 THEN pv.periodo / 100
                                ELSE pv.periodo / 10
                            END
                          ) < %s
                ) p
                ORDER BY p.preferencia ASC, p.periodo DESC
                """,  # nosec B608
                (periodo, periodo, self.month, self.year),
            )
            periodo_meta = (
                int(meta_period_rows[0]["periodo"]) if meta_period_rows else None
            )
            if periodo_meta is None:
                return {
                    "available": False,
                    "note": (
                        f"Sin metas en presupuesto_vendedores para periodo {periodo} "
                        f"ni el mismo mes en años anteriores."
                    ),
                    "periodo": periodo,
                    "periodo_meta": None,
                    "meta_origen": "sin_meta",
                    "sellers": [],
                    "summary": {},
                }

            meta_origen = (
                "periodo_actual" if periodo_meta == periodo else "mismo_mes_historico"
            )
            params: Tuple[Any, ...] = (
                periodo,
                self.start_date,
                self.end_date,
                *excluded,
                periodo_meta,
            )
            params = params + tuple(name.upper() for name in EXCLUDED_PRODUCT_NAMES)

            sellers = db.execute_query(
                f"""
                WITH actual_sales AS (
                    SELECT
                        LTRIM(RTRIM(bd.vendedor_codigo)) AS vendedor_codigo,
                        MAX(bd.VendedorFactura) AS vendedor_nombre,
                        SUM(bd.TotalSinIva) AS ventas_reales,
                        SUM(bd.TotalMasIva) AS facturacion_con_iva,
                        COUNT(*) AS transacciones
                    FROM [{db_name}].[dbo].[{table_name}] bd
                    WHERE bd.periodo = %s
                      AND bd.Fecha BETWEEN %s AND %s
                      AND bd.DocumentosCodigo NOT IN ({placeholders})
                      {self._product_exclusion_sql("bd.")}
                      AND bd.vendedor_codigo IS NOT NULL
                      AND LTRIM(RTRIM(bd.vendedor_codigo)) <> ''
                    GROUP BY LTRIM(RTRIM(bd.vendedor_codigo))
                ),
                budget AS (
                    SELECT
                        LTRIM(RTRIM(pv.vendedor_codigo)) AS vendedor_codigo,
                        MAX(pv.vendedor_nombre) AS vendedor_nombre_presupuesto,
                        SUM(pv.valor) AS meta_presupuesto
                    FROM [{db_name}].[dbo].[presupuesto_vendedores] pv
                    WHERE pv.periodo = %s
                    GROUP BY LTRIM(RTRIM(pv.vendedor_codigo))
                )
                SELECT
                    COALESCE(b.vendedor_codigo, a.vendedor_codigo) AS vendedor_codigo,
                    COALESCE(
                        NULLIF(LTRIM(RTRIM(b.vendedor_nombre_presupuesto)), ''),
                        NULLIF(LTRIM(RTRIM(a.vendedor_nombre)), ''),
                        COALESCE(b.vendedor_codigo, a.vendedor_codigo)
                    ) AS vendedor_nombre,
                    ISNULL(b.meta_presupuesto, 0) AS presupuesto,
                    ISNULL(a.ventas_reales, 0) AS ventas_reales,
                    ISNULL(a.facturacion_con_iva, 0) AS facturacion_con_iva,
                    ISNULL(a.transacciones, 0) AS transacciones,
                    CASE
                        WHEN ISNULL(b.meta_presupuesto, 0) = 0 THEN NULL
                        ELSE ISNULL(a.ventas_reales, 0) * 100.0 / b.meta_presupuesto
                    END AS cumplimiento_pct,
                    CASE
                        WHEN ISNULL(b.meta_presupuesto, 0) = 0 THEN NULL
                        ELSE ISNULL(b.meta_presupuesto, 0) - ISNULL(a.ventas_reales, 0)
                    END AS brecha
                FROM budget b
                FULL OUTER JOIN actual_sales a
                    ON a.vendedor_codigo = b.vendedor_codigo
                ORDER BY ISNULL(b.meta_presupuesto, 0) DESC
                """,  # nosec B608
                params,
            )

            summary_rows = db.execute_query(
                f"""
                WITH actual_sales AS (
                    SELECT SUM(bd.TotalSinIva) AS ventas_reales
                    FROM [{db_name}].[dbo].[{table_name}] bd
                    WHERE bd.periodo = %s
                      AND bd.Fecha BETWEEN %s AND %s
                      AND bd.DocumentosCodigo NOT IN ({placeholders})
                      {self._product_exclusion_sql("bd.")}
                ),
                budget AS (
                    SELECT SUM(pv.valor) AS meta_presupuesto
                    FROM [{db_name}].[dbo].[presupuesto_vendedores] pv
                    WHERE pv.periodo = %s
                )
                SELECT
                    b.meta_presupuesto AS presupuesto_total,
                    a.ventas_reales AS ventas_reales_total,
                    CASE
                        WHEN ISNULL(b.meta_presupuesto, 0) = 0 THEN NULL
                        ELSE ISNULL(a.ventas_reales, 0) * 100.0 / b.meta_presupuesto
                    END AS cumplimiento_pct,
                    CASE
                        WHEN ISNULL(b.meta_presupuesto, 0) = 0 THEN NULL
                        ELSE ISNULL(b.meta_presupuesto, 0) - ISNULL(a.ventas_reales, 0)
                    END AS brecha_total
                FROM budget b
                CROSS JOIN actual_sales a
                """,  # nosec B608
                params,
            )

        summary = summary_rows[0] if summary_rows else {}
        if not sellers and not summary.get("presupuesto_total"):
            return {
                "available": False,
                "note": f"Sin metas en presupuesto_vendedores para periodo {periodo}.",
                "periodo": periodo,
                "periodo_meta": periodo_meta,
                "meta_origen": meta_origen,
                "sellers": [],
                "summary": {},
            }

        note = None
        if meta_origen == "mismo_mes_historico":
            note = (
                f"Sin meta para periodo {periodo}; se usa meta histórica del mismo mes "
                f"(periodo {periodo_meta})."
            )

        return {
            "available": True,
            "note": note,
            "periodo": periodo,
            "periodo_meta": periodo_meta,
            "meta_origen": meta_origen,
            "sellers": sellers,
            "summary": summary,
        }
