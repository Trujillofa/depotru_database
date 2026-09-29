"""SQL question classifiers and deterministic SQL templates.

Extracted from AIVanna without behavior changes. The composed AIVanna
class is injected as ``AIVanna`` after import so historical
``AIVanna._foo()`` lookups keep working.
"""

from __future__ import annotations

import re
from typing import List, Optional

from business_analyzer.core.j3system_sales_warehouse import (
    build_sales_warehouse_sql_for_question,
    extract_warehouse_code,
    is_j3system_warehouse_question,
    qualified_j3_table,
    warehouse_display_name_sql,
)

# Late-bound by business_analyzer.ai.vanna after AIVanna is composed.
AIVanna = None


class SqlRoutingMixin:
    """Deterministic NL→SQL classifiers, templates, and SQL repairs."""

    @staticmethod
    def _is_brand_profit_question(question: str) -> bool:
        lower = (question or "").lower()
        has_brand = "marca" in lower or "marcas" in lower
        has_profit = any(
            token in lower for token in ("rentable", "rentables", "ganancia", "margen")
        )
        return has_brand and has_profit

    BRAND_ALIASES = {
        "ska": "SIKA",
        "sra": "SIKA",
        "cermex": "CEMEX",
    }

    @staticmethod
    def _extract_vendor_brands(question: str) -> List[str]:
        """Pull known vendor/brand tokens from a natural-language question."""
        lower = (question or "").lower()
        branch_blocks_sika_brand = "sika center" in lower
        catalog = (
            "pavco",
            "euroceramica",
            "alfa",
            "cemex",
            "sika",
            "acesco",
            "hylsa",
            "corona",
            "pintuco",
            "gricol",
            "holcim",
        )
        found = [
            name.upper()
            for name in catalog
            if name in lower and not (name == "sika" and branch_blocks_sika_brand)
        ]
        marca_brand = re.search(r"\bmarcas?\s+([a-záéíóúñ][\wáéíóúñ]{2,})", lower)
        if marca_brand:
            token = marca_brand.group(1).upper()
            if token not in {"MAS", "MÁS", "POR", "DE", "LA", "EL", "LOS", "LAS"}:
                if token not in found:
                    found.append(token)
        ventas_brand = re.search(
            r"ventas(?:\s+de|\s+del)?\s+(?:productos?\s+)?([a-záéíóúñ][\wáéíóúñ]{3,})",
            lower,
        )
        if ventas_brand:
            token = ventas_brand.group(1).upper()
            if token not in {"VENTAS", "PRODUCTOS", "MARCA", "PROVEEDOR", "TOTAL"}:
                if token not in found:
                    found.append(token)
        for alias, canonical in AIVanna.BRAND_ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", lower):
                found.append(canonical)
        for match in re.finditer(
            r"\b([a-záéíóúñ]{4,})\b",
            lower,
        ):
            token = match.group(1).upper()
            if token in {"VENTAS", "PRODUCTOS", "MARCA", "PROVEEDOR", "TOTAL"}:
                continue
            if " O " in f" {lower} " and token not in found:
                found.append(token)
        # de-duplicate preserving order (apply typo aliases: cermex → CEMEX)
        seen = set()
        ordered: List[str] = []
        for brand in found:
            canonical = AIVanna.BRAND_ALIASES.get(brand.lower(), brand)
            if canonical not in seen:
                seen.add(canonical)
                ordered.append(canonical)
        return ordered

    @staticmethod
    def _branch_document_code(question: str) -> str | None:
        lower = (question or "").lower()
        if "sika center" in lower:
            return "FEF"
        if "calle 5" in lower or "distribuciones" in lower:
            return "FET"
        if re.search(r"\b(?:sede|tienda|sucursal)\s+almac[eé]n\b", lower):
            return "FED"
        if re.search(r"\balmac[eé]n\s+(?:principal|depotru|trujillo)\b", lower):
            return "FED"
        return None

    @staticmethod
    def _is_j3system_warehouse_question(question: str) -> bool:
        return is_j3system_warehouse_question(question)

    @staticmethod
    def _j3system_warehouse_sql_template(question: str = "") -> str:
        return build_sales_warehouse_sql_for_question(question)

    @staticmethod
    def _is_branch_store_sales_question(question: str) -> bool:
        if AIVanna._is_j3system_warehouse_question(question):
            return False
        lower = (question or "").lower()
        if AIVanna._branch_document_code(question):
            has_sales = any(
                token in lower
                for token in ("venta", "ventas", "factur", "ingreso", "sede")
            )
            return has_sales
        return "sede" in lower and any(
            token in lower for token in ("venta", "ventas", "factur")
        )

    @staticmethod
    def _is_product_ranking_question(question: str) -> bool:
        lower = (question or "").lower()
        if "baja rotación" in lower or "baja rotacion" in lower:
            return False
        has_product = "producto" in lower
        has_ranking = any(
            token in lower
            for token in (
                "más vendid",
                "mas vendid",
                "menos vendid",
                "menor vendid",
                "peor vendid",
                "principales producto",
                "inventario vendido",
            )
        ) or bool(re.search(r"top\s*\d+\s+productos?", lower))
        return has_product and has_ranking

    @staticmethod
    def _is_branch_product_ranking_question(question: str) -> bool:
        return AIVanna._branch_document_code(
            question
        ) is not None and AIVanna._is_product_ranking_question(question)

    @staticmethod
    def _extract_product_category(question: str) -> str | None:
        lower = (question or "").lower()
        match = re.search(
            r"\bde\s+([a-záéíóúñ0-9][a-záéíóúñ0-9\s]*?)"
            r"(?:\s+(?:más|mas|este|por)|$)",
            lower,
        )
        if not match:
            match = re.search(
                r"categor[ií]a\s+([a-záéíóúñ0-9][a-záéíóúñ0-9\s]*)",
                lower,
            )
        if not match:
            return None
        category = re.sub(r"\s+", " ", match.group(1).strip()).upper()
        category_tokens = category.split()
        if "MARCA" in category_tokens or "PROVEEDOR" in category_tokens:
            return None
        skip = {
            "SIKA",
            "ACESCO",
            "PAVCO",
            "CEMEX",
            "EUROCERAMICA",
            "ALFA",
            "HOLCIM",
        }
        if category in skip:
            return None
        return category or None

    @staticmethod
    def _is_brand_top_products_question(question: str) -> bool:
        if not AIVanna._is_product_ranking_question(question):
            return False
        brands = AIVanna._extract_vendor_brands(question)
        category = AIVanna._extract_product_category(question)
        return len(brands) >= 1 or category is not None

    @staticmethod
    def _is_generic_top_products_question(question: str) -> bool:
        return AIVanna._is_product_ranking_question(
            question
        ) and not AIVanna._is_brand_top_products_question(question)

    @staticmethod
    def _has_brand_sales_context(question: str) -> bool:
        lower = (question or "").lower()
        brands = AIVanna._extract_vendor_brands(question)
        if not brands:
            return False
        return any(token in lower for token in ("venta", "ventas", "factur", "ingreso"))

    @staticmethod
    def _is_brand_by_warehouse_question(question: str) -> bool:
        """Brand sales by physical warehouse (banco_datos.AlmacenCodigo, e.g. FLO)."""
        if AIVanna._is_j3system_warehouse_question(question):
            return False
        lower = (question or "").lower()
        if not AIVanna._has_brand_sales_context(question):
            return False
        return any(
            phrase in lower for phrase in ("por almacén", "por almacen", "por bodega")
        )

    @staticmethod
    def _is_brand_at_warehouse_question(question: str) -> bool:
        """Brand sales scoped to one warehouse code (e.g. ventas de sika en flo)."""
        if AIVanna._is_brand_by_warehouse_question(question):
            return False
        if AIVanna._is_brand_by_branch_question(question):
            return False
        if not AIVanna._has_brand_sales_context(question):
            return False
        return extract_warehouse_code(question) is not None

    @staticmethod
    def _is_brand_by_branch_question(question: str) -> bool:
        """Brand sales broken down by invoice branch/sede (FED/FEF/FET)."""
        if AIVanna._is_j3system_warehouse_question(question):
            return False
        lower = (question or "").lower()
        if not AIVanna._has_brand_sales_context(question):
            return False
        return any(
            phrase in lower
            for phrase in (
                "por sede",
                "por sucursal",
                "por tienda",
                "por documento",
                "por facturación",
                "por facturacion",
            )
        )

    @staticmethod
    def _brand_sales_by_warehouse_sql_template(question: str = "") -> str:
        brands = AIVanna._extract_vendor_brands(question)
        if not brands:
            return ""
        brand_filter = AIVanna._multi_vendor_brand_filter_sql(brands)
        year_filter = AIVanna._year_filter_from_question(question).replace(
            "YEAR(Fecha)", "YEAR(bd.Fecha)"
        )
        adm_almacen = qualified_j3_table("AdmAlmacen")
        nombre_almacen = warehouse_display_name_sql()
        return f"""
SELECT
    bd.AlmacenCodigo AS Codigo_Almacen,
    {nombre_almacen} AS Nombre_Almacen,
    COUNT(*) AS Numero_Transacciones,
    SUM(bd.TotalMasIva) AS Ventas_Totales,
    SUM(bd.TotalSinIva - bd.ValorCosto) AS Ganancia
FROM banco_datos bd
LEFT JOIN productos_adicional pa
    ON bd.ArticulosCodigo COLLATE DATABASE_DEFAULT
     = pa.producto_codigo COLLATE DATABASE_DEFAULT
LEFT JOIN {adm_almacen} a
    ON a.AlmacenCodigo COLLATE DATABASE_DEFAULT
     = bd.AlmacenCodigo COLLATE DATABASE_DEFAULT
WHERE bd.DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
  AND bd.AlmacenCodigo IS NOT NULL AND LTRIM(RTRIM(bd.AlmacenCodigo)) <> ''
  AND {brand_filter}{year_filter}
GROUP BY bd.AlmacenCodigo, a.AlmacenNombre
ORDER BY Ventas_Totales DESC
        """.strip()

    @staticmethod
    def _brand_sales_at_warehouse_sql_template(question: str = "") -> str:
        brands = AIVanna._extract_vendor_brands(question)
        code = extract_warehouse_code(question)
        if not brands or not code:
            return ""
        brand_filter = AIVanna._multi_vendor_brand_filter_sql(brands)
        year_filter = AIVanna._year_filter_from_question(question).replace(
            "YEAR(Fecha)", "YEAR(bd.Fecha)"
        )
        adm_almacen = qualified_j3_table("AdmAlmacen")
        nombre_almacen = warehouse_display_name_sql()
        return f"""
SELECT
    bd.AlmacenCodigo AS Codigo_Almacen,
    {nombre_almacen} AS Nombre_Almacen,
    COUNT(*) AS Numero_Transacciones,
    SUM(bd.TotalMasIva) AS Ventas_Totales,
    SUM(bd.TotalSinIva - bd.ValorCosto) AS Ganancia
FROM banco_datos bd
LEFT JOIN productos_adicional pa
    ON bd.ArticulosCodigo COLLATE DATABASE_DEFAULT
     = pa.producto_codigo COLLATE DATABASE_DEFAULT
LEFT JOIN {adm_almacen} a
    ON a.AlmacenCodigo COLLATE DATABASE_DEFAULT
     = bd.AlmacenCodigo COLLATE DATABASE_DEFAULT
WHERE bd.DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
  AND bd.AlmacenCodigo = '{code}'
  AND {brand_filter}{year_filter}
GROUP BY bd.AlmacenCodigo, a.AlmacenNombre
        """.strip()

    @staticmethod
    def _brand_sales_by_branch_sql_template(question: str = "") -> str:
        brands = AIVanna._extract_vendor_brands(question)
        if not brands:
            return ""
        brand_filter = AIVanna._multi_vendor_brand_filter_sql(brands)
        descripcion = AIVanna._document_type_description_sql()
        year_filter = AIVanna._year_filter_from_question(question).replace(
            "YEAR(Fecha)", "YEAR(bd.Fecha)"
        )
        return f"""
SELECT
    bd.DocumentosCodigo AS Codigo_Sede,
    {descripcion} AS Sede,
    COUNT(*) AS Numero_Transacciones,
    SUM(bd.TotalMasIva) AS Ventas_Totales,
    SUM(bd.TotalSinIva - bd.ValorCosto) AS Ganancia
FROM banco_datos bd
LEFT JOIN productos_adicional pa
    ON bd.ArticulosCodigo COLLATE DATABASE_DEFAULT
     = pa.producto_codigo COLLATE DATABASE_DEFAULT
WHERE bd.DocumentosCodigo IN ('FED', 'FEF', 'FET')
  AND {brand_filter}{year_filter}
GROUP BY bd.DocumentosCodigo
ORDER BY Ventas_Totales DESC
        """.strip()

    @staticmethod
    def _is_multi_vendor_sales_question(question: str) -> bool:
        if AIVanna._is_brand_by_warehouse_question(question):
            return False
        if AIVanna._is_brand_at_warehouse_question(question):
            return False
        if AIVanna._is_brand_by_branch_question(question):
            return False
        if AIVanna._is_branch_store_sales_question(question):
            return False
        if AIVanna._is_product_ranking_question(question):
            return False
        lower = (question or "").lower()
        has_sales = any(
            token in lower
            for token in ("venta", "ventas", "factur", "ingreso", "vendido")
        )
        brands = AIVanna._extract_vendor_brands(question)
        return has_sales and len(brands) >= 1

    @staticmethod
    def _norm_proveedor_sql() -> str:
        """Collation-safe proveedor from banco_datos + productos_adicional."""
        return (
            "UPPER(LTRIM(RTRIM(COALESCE("
            "bd.proveedor COLLATE DATABASE_DEFAULT, "
            "pa.proveedor_descripcion COLLATE DATABASE_DEFAULT, "
            "''"
            "))))"
        )

    @staticmethod
    def _norm_marca_sql() -> str:
        """Collation-safe marca from banco_datos + productos_adicional."""
        return (
            "UPPER(LTRIM(RTRIM(COALESCE("
            "bd.marca COLLATE DATABASE_DEFAULT, "
            "pa.producto_marca COLLATE DATABASE_DEFAULT, "
            "''"
            "))))"
        )

    @staticmethod
    def _safe_brand_tokens(brands: List[str]) -> List[str]:
        return [
            re.sub(r"[^A-Z0-9]", "", brand.upper())
            for brand in brands
            if brand and re.sub(r"[^A-Z0-9]", "", brand.upper())
        ]

    @staticmethod
    def _articulos_name_match_sql(brand: str) -> str:
        expr = "UPPER(bd.ArticulosNombre COLLATE DATABASE_DEFAULT)"
        clause = f"{expr} LIKE '%{brand}%'"
        for blocker in AIVanna.BRAND_SUBSTRING_BLOCKERS.get(brand, ()):
            clause = f"({clause} AND {expr} NOT LIKE '%{blocker}%')"
        return clause

    @staticmethod
    def _multi_vendor_brand_filter_sql(brands: List[str]) -> str:
        safe_brands = AIVanna._safe_brand_tokens(brands)
        if not safe_brands:
            return ""
        in_list = ", ".join(f"'{brand}'" for brand in safe_brands)
        proveedor_norm = AIVanna._norm_proveedor_sql()
        marca_norm = AIVanna._norm_marca_sql()
        name_filters = " OR ".join(
            AIVanna._articulos_name_match_sql(brand) for brand in safe_brands
        )
        return f"""(
            {proveedor_norm} IN ({in_list})
            OR {marca_norm} IN ({in_list})
            OR {name_filters}
        )"""

    @staticmethod
    def _multi_vendor_inner_subquery(sql: str) -> Optional[str]:
        lower = (sql or "").lower()
        marker = ") as ventas_marca"
        if marker not in lower:
            return None
        return sql[: lower.index(marker)]

    @staticmethod
    def _multi_vendor_sql_has_where_prefilter(sql: str, brands: List[str]) -> bool:
        """True when brand prefilter lives in the inner WHERE (not only in CASE)."""
        inner = AIVanna._multi_vendor_inner_subquery(sql)
        safe_brands = AIVanna._safe_brand_tokens(brands)
        if not inner or not safe_brands:
            return False
        where_idx = inner.lower().rfind("where ")
        if where_idx == -1:
            return False
        where_clause = inner[where_idx:].lower()
        return all(
            (
                f"'{brand.lower()}'" in where_clause
                or f"like '%{brand.lower()}%'" in where_clause
            )
            for brand in safe_brands
        )

    @staticmethod
    def _brands_referenced_in_multi_vendor_sql(sql: str) -> List[str]:
        """Infer brand tokens from a ventas_marca aggregate query."""
        brands: List[str] = []
        seen: set[str] = set()
        for match in re.finditer(r"THEN\s+'([A-Z0-9]{4,})'", sql, re.IGNORECASE):
            token = match.group(1).upper()
            if token not in seen:
                seen.add(token)
                brands.append(token)
        for match in re.finditer(
            r"IN\s*\(\s*'([A-Z0-9]{4,})'\s*\)", sql, re.IGNORECASE
        ):
            token = match.group(1).upper()
            if token not in seen:
                seen.add(token)
                brands.append(token)
        return brands

    _DOC_EXCLUSION_INNER = "bd.DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')"
    _DOC_EXCLUSION_PATTERN = re.compile(
        r"(?:bd\.)?DocumentosCodigo\s+NOT\s+IN\s*\([^\)]*\)",
        flags=re.IGNORECASE,
    )
    _INNER_DOC_WHERE_PATTERN = re.compile(
        r"WHERE\s+(?:bd\.)?DocumentosCodigo\s+NOT\s+IN\s*\([^\)]+\)",
        flags=re.IGNORECASE,
    )
    _BANCO_DATOS_JOIN_PATTERN = re.compile(
        r"ON\s+bd\.ArticulosCodigo\s+COLLATE\s+DATABASE_DEFAULT\s*\n\s*=\s*"
        r"pa\.producto_codigo\s+COLLATE\s+DATABASE_DEFAULT",
        flags=re.IGNORECASE,
    )

    @staticmethod
    def _normalize_inner_document_exclusion(inner: str) -> str:
        return AIVanna._DOC_EXCLUSION_PATTERN.sub(AIVanna._DOC_EXCLUSION_INNER, inner)

    @staticmethod
    def _find_inner_document_where_end(inner: str) -> Optional[int]:
        match = AIVanna._INNER_DOC_WHERE_PATTERN.search(inner)
        return match.end() if match else None

    @staticmethod
    def _append_inner_where_clause(inner: str, clause: str) -> str:
        """Insert a WHERE clause after the productos_adicional JOIN."""
        stripped = clause.strip()
        if re.search(r"\bwhere\b", inner, flags=re.IGNORECASE):
            addition = stripped
            if addition.upper().startswith("WHERE "):
                addition = f"AND {addition[6:].strip()}"
            return inner.rstrip() + f"\n      {addition}"

        join_match = AIVanna._BANCO_DATOS_JOIN_PATTERN.search(inner)
        if join_match:
            return (
                inner[: join_match.end()]
                + f"\n    {stripped}"
                + inner[join_match.end() :]
            )
        return inner.rstrip() + f"\n    {stripped}"

    @staticmethod
    def _ensure_multi_vendor_inner_filters(sql: str) -> str:
        """Ensure document exclusion and brand prefilter live in the inner subquery."""
        inner = AIVanna._multi_vendor_inner_subquery(sql)
        if inner is None or "from banco_datos" not in inner.lower():
            return sql

        suffix = sql[len(inner) :]
        working = AIVanna._normalize_inner_document_exclusion(inner)
        brands = AIVanna._brands_referenced_in_multi_vendor_sql(sql)

        if "documentoscodigo" not in working.lower():
            working = AIVanna._append_inner_where_clause(
                working, f"WHERE {AIVanna._DOC_EXCLUSION_INNER}"
            )

        full_check = working + suffix
        if brands and not AIVanna._multi_vendor_sql_has_where_prefilter(
            full_check, brands
        ):
            brand_filter = AIVanna._multi_vendor_brand_filter_sql(brands)
            if brand_filter:
                anchor = AIVanna._find_inner_document_where_end(working)
                if anchor is not None:
                    working = (
                        working[:anchor]
                        + f"\n      AND {brand_filter}"
                        + working[anchor:]
                    )
                else:
                    working = AIVanna._append_inner_where_clause(
                        working,
                        f"WHERE {AIVanna._DOC_EXCLUSION_INNER}\n      AND {brand_filter}",
                    )

        return working + suffix

    @staticmethod
    def _repair_multi_vendor_brand_prefilter(sql: str) -> str:
        """Backward-compatible alias for inner brand prefilter repair."""
        return AIVanna._ensure_multi_vendor_inner_filters(sql)

    @staticmethod
    def _prepare_sql_for_execution(sql: str) -> str:
        """Normalize LLM/cached SQL immediately before execution."""
        if not sql:
            return sql
        sql = AIVanna._repair_sika_center_customer_sql(sql)
        sql = AIVanna._repair_common_sql_hallucinations(sql)
        if AIVanna._multi_vendor_inner_subquery(sql) is not None:
            return AIVanna._ensure_multi_vendor_inner_filters(sql)
        return AIVanna._ensure_document_exclusion(sql)

    @staticmethod
    def _multi_vendor_sales_sql_template(brands: List[str]) -> str:
        """Aggregate sales by vendor/brand with master-data enrichment."""
        safe_brands = AIVanna._safe_brand_tokens(brands)
        if not safe_brands:
            return ""
        proveedor_norm = AIVanna._norm_proveedor_sql()
        marca_norm = AIVanna._norm_marca_sql()
        in_list = ", ".join(f"'{brand}'" for brand in safe_brands)
        name_cases = "\n".join(
            f"            WHEN {AIVanna._articulos_name_match_sql(brand)} THEN '{brand}'"
            for brand in safe_brands
        )
        brand_filter = AIVanna._multi_vendor_brand_filter_sql(safe_brands)
        return f"""
SELECT
    Marca_Proveedor,
    SUM(TotalMasIva) AS Ventas_Totales,
    COUNT(*) AS Numero_Transacciones,
    SUM(TotalSinIva - ValorCosto) AS Ganancia
FROM (
    SELECT
        bd.TotalMasIva,
        bd.TotalSinIva,
        bd.ValorCosto,
        CASE
            WHEN {proveedor_norm} IN ({in_list})
                THEN {proveedor_norm}
            WHEN {marca_norm} IN ({in_list})
                THEN {marca_norm}
{name_cases}
            ELSE NULL
        END AS Marca_Proveedor
    FROM banco_datos bd
    LEFT JOIN productos_adicional pa
        ON bd.ArticulosCodigo COLLATE DATABASE_DEFAULT
         = pa.producto_codigo COLLATE DATABASE_DEFAULT
    WHERE bd.DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
      AND {brand_filter}
) AS ventas_marca
WHERE Marca_Proveedor IS NOT NULL
GROUP BY Marca_Proveedor
ORDER BY Ventas_Totales DESC
        """.strip()

    @staticmethod
    def _insert_before_tail(sql: str, fragment: str) -> str:
        """Insert SQL fragment before GROUP/ORDER/HAVING/LIMIT clauses."""
        lower = sql.lower()
        positions = [
            pos
            for pos in (
                lower.find(" group by "),
                lower.find(" order by "),
                lower.find(" having "),
                lower.find(" limit "),
            )
            if pos != -1
        ]

        insert_at = min(positions) if positions else len(sql)
        head = sql[:insert_at].rstrip()
        tail = sql[insert_at:]

        if head.endswith(";"):
            head = head[:-1].rstrip()

        return f"{head} {fragment}{tail}"

    @staticmethod
    def _ensure_document_exclusion(sql: str) -> str:
        """Guarantee exclusion filter for banco_datos queries."""
        if not sql:
            return sql

        canonical_filter = "DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')"
        normalized_sql = re.sub(
            r"DocumentosCodigo\s+NOT\s+IN\s*\([^\)]*\)",
            canonical_filter,
            sql,
            flags=re.IGNORECASE,
        )

        lower = sql.lower()
        normalized_lower = normalized_sql.lower()
        if "from banco_datos" not in lower:
            return normalized_sql

        if "documentoscodigo" in normalized_lower:
            return normalized_sql

        if " where " in lower:
            return AIVanna._insert_before_tail(
                normalized_sql, f"AND {canonical_filter}"
            )

        return AIVanna._insert_before_tail(normalized_sql, f"WHERE {canonical_filter}")

    @staticmethod
    def _repair_j3system_impresion_factura_sql(sql: str) -> str:
        """Replace incomplete InvImpresionFactura joins with InvVentasDetalle coverage."""
        if not sql or "invimpresionfactura" not in sql.lower():
            return sql
        from business_analyzer.core.j3system_sales_warehouse import (
            build_sales_by_warehouse_sql,
        )

        lower = sql.lower()
        if "group by" in lower and "count(distinct" in lower:
            return build_sales_by_warehouse_sql()
        return sql

    @staticmethod
    def _repair_common_sql_hallucinations(sql: str) -> str:
        """Fix frequent LLM column/table typos before execution."""
        if not sql:
            return sql

        repaired = sql
        replacements = (
            (r"\bTotalActiva\b", "TotalMasIva"),
            (r"\bTotalVentas\b", "TotalMasIva"),
            (r"\bVentaTotal\b", "TotalMasIva"),
            (r"\bDocumentoCodigo\b", "DocumentosCodigo"),
            (r"'YY'", "'YX'"),
        )
        for pattern, replacement in replacements:
            repaired = re.sub(pattern, replacement, repaired, flags=re.IGNORECASE)

        lower = repaired.lower()
        if "from banco_datos" in lower:
            repaired = re.sub(
                r"SUM\s*\(\s*TotalMasIva\s*-\s*ValorCosto\s*\)",
                "SUM(TotalSinIva - ValorCosto)",
                repaired,
                flags=re.IGNORECASE,
            )
        repaired = AIVanna._repair_j3system_impresion_factura_sql(repaired)
        return repaired

    @staticmethod
    def _is_year_month_comparison_question(question: str) -> bool:
        lower = (question or "").lower()
        has_month = "mes" in lower or "mensual" in lower
        has_sales = any(
            token in lower for token in ("venta", "ventas", "factur", "ingreso")
        )
        has_compare = any(
            token in lower
            for token in ("comparando", "comparar", "comparación", "comparacion")
        )
        has_years = any(
            token in lower for token in ("año", "años", "anos", "ano", "year")
        )
        return has_month and has_sales and has_compare and has_years

    @staticmethod
    def _year_month_comparison_sql_template(question: str = "") -> str:
        lower = (question or "").lower()
        year_span = 2
        if re.search(r"\b(3|tres)\s+años?\b", lower) or "últimos 3" in lower:
            year_span = 3
        return f"""
SELECT
    MONTH(Fecha) AS Mes,
    DATENAME(MONTH, Fecha) AS Nombre_Mes,
    SUM(CASE WHEN YEAR(Fecha) = YEAR(GETDATE()) THEN TotalMasIva ELSE 0 END)
        AS Ventas_Anio_Actual,
    SUM(CASE WHEN YEAR(Fecha) = YEAR(GETDATE()) - 1 THEN TotalMasIva ELSE 0 END)
        AS Ventas_Anio_Anterior,
    SUM(CASE WHEN YEAR(Fecha) = YEAR(GETDATE()) THEN TotalSinIva - ValorCosto ELSE 0 END)
        AS Ganancia_Actual
FROM banco_datos
WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
  AND YEAR(Fecha) >= YEAR(GETDATE()) - {year_span - 1}
GROUP BY MONTH(Fecha), DATENAME(MONTH, Fecha)
ORDER BY Mes
        """.strip()

    @staticmethod
    def _is_brand_monthly_sales_question(question: str) -> bool:
        if AIVanna._is_product_ranking_question(question):
            return False
        if AIVanna._is_branch_store_sales_question(question):
            return False
        if AIVanna._is_year_month_comparison_question(question):
            return False
        lower = (question or "").lower()
        brands = AIVanna._extract_vendor_brands(question)
        has_month = any(
            token in lower
            for token in ("mes", "mensual", "al mes", "por mes", "mensuales")
        )
        has_sales = any(
            token in lower for token in ("venta", "ventas", "factur", "ingreso")
        )
        return len(brands) >= 1 and has_month and has_sales

    @staticmethod
    def _brand_monthly_sales_sql_template(question: str = "") -> str:
        brands = AIVanna._extract_vendor_brands(question)
        if not brands:
            return ""
        brand_clauses = [AIVanna._brand_match_filter(brand) for brand in brands[:3]]
        scope_filter = "\n  AND (" + " OR ".join(brand_clauses) + ")"
        year_filter = AIVanna._year_filter_from_question(question)
        if not year_filter and "comparando" not in (question or "").lower():
            year_filter = "\n  AND YEAR(Fecha) >= YEAR(GETDATE()) - 2"
        return f"""
SELECT
    YEAR(Fecha) AS Año,
    MONTH(Fecha) AS Mes,
    DATENAME(MONTH, Fecha) AS Nombre_Mes,
    SUM(TotalMasIva) AS Ventas_Totales,
    SUM(TotalSinIva - ValorCosto) AS Ganancia,
    COUNT(*) AS Numero_Transacciones
FROM banco_datos
WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC'){year_filter}{scope_filter}
GROUP BY YEAR(Fecha), MONTH(Fecha), DATENAME(MONTH, Fecha)
ORDER BY Año DESC, Mes DESC
        """.strip()

    @staticmethod
    def _norm_cliente_sql() -> str:
        """Collapse duplicate spaces in customer names for consistent grouping."""
        return "REPLACE(REPLACE(LTRIM(RTRIM(TercerosNombres)), '  ', ' '), '  ', ' ')"

    @staticmethod
    def _is_top_customers_question(question: str) -> bool:
        lower = (question or "").lower()
        has_customer = "cliente" in lower
        has_metric = any(
            token in lower
            for token in ("factur", "venta", "ganancia", "rentable", "ingreso")
        )
        has_ranking = any(
            token in lower
            for token in (
                "top",
                "mayor",
                "mejor",
                "principales",
                "ranking",
                "más",
                "mas",
            )
        )
        has_top_n = bool(re.search(r"top\s*\d+", lower)) or bool(
            re.search(r"\d+\s+clientes?", lower)
        )
        return has_customer and has_metric and (has_ranking or has_top_n)

    @staticmethod
    def _extract_top_n(question: str, default: int = 10) -> int:
        lower = (question or "").lower()
        for pattern in (
            r"top\s*(\d+)",
            r"(\d+)\s+clientes?",
            r"(\d+)\s+vendedores?",
            r"(\d+)\s+productos?",
        ):
            match = re.search(pattern, lower)
            if match:
                return max(1, min(int(match.group(1)), 100))
        return default

    @staticmethod
    def _is_bare_top_n_followup(question: str) -> bool:
        return bool(re.fullmatch(r"top\s*\d+\s*", (question or "").lower().strip()))

    @staticmethod
    def resolve_question_with_context(
        question: Optional[str], prior: Optional[str] = None
    ) -> str:
        """Expand chat follow-ups like ``top 100`` using the prior question."""
        q = (question or "").strip()
        if not q or not AIVanna._is_bare_top_n_followup(q):
            return q
        prior_q = (prior or "").strip()
        n = AIVanna._extract_top_n(q)
        if prior_q and prior_q.lower() != q.lower():
            return f"{prior_q} top {n}"
        return f"top {n} productos más vendidos por facturación"

    @staticmethod
    def _year_filter_from_question(question: str) -> str:
        lower = (question or "").lower()
        year_match = re.search(r"\b(20\d{2})\b", lower)
        if year_match:
            return f"\n  AND YEAR(Fecha) = {year_match.group(1)}"
        if any(
            phrase in lower
            for phrase in (
                "este año",
                "este ano",
                "año actual",
                "ano actual",
                "ytd",
            )
        ):
            return "\n  AND YEAR(Fecha) = YEAR(GETDATE())"
        return ""

    @staticmethod
    def _top_customers_sql_template(question: str = "") -> str:
        n = AIVanna._extract_top_n(question)
        year_filter = AIVanna._year_filter_from_question(question)
        cliente_norm = AIVanna._norm_cliente_sql()
        return f"""
SELECT TOP {n}
    {cliente_norm} AS Cliente,
    SUM(TotalMasIva) AS Facturacion_Total,
    SUM(TotalSinIva - ValorCosto) AS Ganancia_Neta,
    COUNT(*) AS Numero_Compras,
    AVG((TotalSinIva - ValorCosto) * 100.0 / NULLIF(TotalSinIva, 0)) AS Margen_Promedio
FROM banco_datos
WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
  AND NULLIF(LTRIM(RTRIM(TercerosNombres)), '') IS NOT NULL{year_filter}
GROUP BY {cliente_norm}
ORDER BY Facturacion_Total DESC
        """.strip()

    BRAND_SUBSTRING_BLOCKERS = {
        "GRICOL": ("AGRICOL",),
    }

    @staticmethod
    def _brand_text_like_sql(field: str, brand: str) -> str:
        """Substring match that avoids false positives (e.g. GRICOL inside AGRICOL)."""
        safe = re.sub(r"[^A-Z0-9]", "", brand.upper())
        if not safe:
            return "1 = 0"
        expr = f"UPPER(LTRIM(RTRIM(COALESCE({field}, ''))))"
        clause = f"{expr} LIKE '%{safe}%'"
        for blocker in AIVanna.BRAND_SUBSTRING_BLOCKERS.get(safe, ()):
            clause = f"({clause} AND {expr} NOT LIKE '%{blocker}%')"
        return clause

    @staticmethod
    def _brand_match_filter(brand: str) -> str:
        safe = re.sub(r"[^A-Z0-9]", "", brand.upper())
        if not safe:
            return "1 = 0"
        exact_fields = ("proveedor", "marca")
        text_fields = ("ArticulosNombre", "categoria", "subcategoria")
        clauses = [
            f"UPPER(LTRIM(RTRIM(COALESCE({field}, '')))) = '{safe}'"
            for field in exact_fields
        ]
        clauses.extend(
            AIVanna._brand_text_like_sql(field, safe) for field in text_fields
        )
        return "(\n        " + "\n        OR ".join(clauses) + "\n    )"

    @staticmethod
    def _product_ranking_order(question: str) -> str:
        lower = (question or "").lower()
        ascending = any(
            token in lower for token in ("menos vendid", "menor vendid", "peor vendid")
        )
        direction = "ASC" if ascending else "DESC"
        if "por cantidad" in lower or "cantidad" in lower and "factur" not in lower:
            return f"Cantidad_Vendida {direction}"
        if "factur" in lower:
            return f"Facturacion_Total {direction}"
        return f"Ventas {direction}"

    @staticmethod
    def _brand_top_products_sql_template(question: str = "") -> str:
        n = AIVanna._extract_top_n(question, default=15)
        year_filter = AIVanna._year_filter_from_question(question)
        order_clause = AIVanna._product_ranking_order(question)
        brands = AIVanna._extract_vendor_brands(question)
        category = AIVanna._extract_product_category(question)

        revenue_col = (
            "Facturacion_Total" if "factur" in (question or "").lower() else "Ventas"
        )

        if brands:
            safe_brands = AIVanna._safe_brand_tokens(brands[:3])
            brand_filter = AIVanna._multi_vendor_brand_filter_sql(safe_brands)
            year_on_bd = year_filter.replace("YEAR(Fecha)", "YEAR(bd.Fecha)")
            return f"""
SELECT TOP {n}
    bd.ArticulosNombre AS Producto,
    SUM(bd.TotalMasIva) AS {revenue_col},
    SUM(bd.Cantidad) AS Cantidad_Vendida,
    SUM(bd.TotalSinIva - bd.ValorCosto) AS Ganancia
FROM banco_datos bd
LEFT JOIN productos_adicional pa
    ON bd.ArticulosCodigo COLLATE DATABASE_DEFAULT
     = pa.producto_codigo COLLATE DATABASE_DEFAULT
WHERE bd.DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC'){year_on_bd}
  AND ({brand_filter})
GROUP BY bd.ArticulosNombre
ORDER BY {order_clause}
            """.strip()

        scope_filter = ""
        if category:
            safe_category = re.sub(r"[^A-Z0-9 ]", "", category.upper()).strip()
            scope_filter = (
                f"\n  AND UPPER(LTRIM(RTRIM(COALESCE(categoria, '')))) = "
                f"'{safe_category}'"
            )

        return f"""
SELECT TOP {n}
    ArticulosNombre AS Producto,
    SUM(TotalMasIva) AS {revenue_col},
    SUM(Cantidad) AS Cantidad_Vendida,
    SUM(TotalSinIva - ValorCosto) AS Ganancia
FROM banco_datos
WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC'){year_filter}{scope_filter}
GROUP BY ArticulosNombre
ORDER BY {order_clause}
        """.strip()

    @staticmethod
    def _branch_product_ranking_sql_template(question: str = "") -> str:
        doc_code = AIVanna._branch_document_code(question) or "FEF"
        n = AIVanna._extract_top_n(question)
        year_filter = AIVanna._year_filter_from_question(question)
        order_clause = AIVanna._product_ranking_order(question)
        revenue_col = (
            "Facturacion_Total" if "factur" in (question or "").lower() else "Ventas"
        )
        return f"""
SELECT TOP {n}
    ArticulosNombre AS Producto,
    SUM(TotalMasIva) AS {revenue_col},
    SUM(Cantidad) AS Cantidad_Vendida,
    SUM(TotalSinIva - ValorCosto) AS Ganancia
FROM banco_datos
WHERE DocumentosCodigo = '{doc_code}'{year_filter}
GROUP BY ArticulosNombre
ORDER BY {order_clause}
        """.strip()

    @staticmethod
    def _generic_top_products_sql_template(question: str = "") -> str:
        n = AIVanna._extract_top_n(question)
        year_filter = AIVanna._year_filter_from_question(question)
        order_clause = AIVanna._product_ranking_order(question)
        lower = (question or "").lower()
        if "factur" in lower:
            return f"""
SELECT TOP {n}
    ArticulosNombre AS Producto,
    SUM(Cantidad) AS Unidades_Vendidas,
    SUM(TotalMasIva) AS Facturacion_Total,
    SUM(TotalSinIva - ValorCosto) AS Ganancia_Neta
FROM banco_datos
WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC'){year_filter}
GROUP BY ArticulosNombre
ORDER BY {order_clause}
            """.strip()
        return f"""
SELECT TOP {n}
    ArticulosNombre AS Producto,
    SUM(Cantidad) AS Cantidad_Vendida,
    COUNT(*) AS Numero_Transacciones
FROM banco_datos
WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC'){year_filter}
GROUP BY ArticulosNombre
ORDER BY {order_clause}
        """.strip()

    @staticmethod
    def _norm_vendedor_sql() -> str:
        """Single vendor identity across factura/código/asignado fields."""
        return (
            "COALESCE("
            "NULLIF(LTRIM(RTRIM(VendedorFactura)), ''), "
            "'Código: ' + vendedor_codigo, "
            "VendedorAsignado"
            ")"
        )

    @staticmethod
    def _is_vendedor_performance_question(question: str) -> bool:
        lower = (question or "").lower()
        if "proveedor" in lower and "vendedor" not in lower:
            return False
        if " del vendedor " in f" {lower} ":
            return False
        has_vendedor = "vendedor" in lower
        has_performance = any(
            token in lower
            for token in (
                "desempeño",
                "desempeno",
                "mejor",
                "top",
                "mayor",
                "ranking",
                "ventas",
                "factur",
                "ganancia",
                "transacciones",
                "comision",
                "comisión",
            )
        )
        return has_vendedor and has_performance

    @staticmethod
    def _month_filter_from_question(question: str) -> str:
        """Calendar month filter for 'este mes', named months, or mes pasado."""
        lower = (question or "").lower()
        month_names = {
            "enero": 1,
            "febrero": 2,
            "marzo": 3,
            "abril": 4,
            "mayo": 5,
            "junio": 6,
            "julio": 7,
            "agosto": 8,
            "septiembre": 9,
            "setiembre": 9,
            "octubre": 10,
            "noviembre": 11,
            "diciembre": 12,
        }
        for month_name, month_number in month_names.items():
            if month_name in lower:
                year_match = re.search(r"\b(20\d{2})\b", lower)
                if year_match:
                    return (
                        f"\n  AND YEAR(Fecha) = {year_match.group(1)}"
                        f" AND MONTH(Fecha) = {month_number}"
                    )
                return (
                    f"\n  AND YEAR(Fecha) = YEAR(GETDATE())"
                    f" AND MONTH(Fecha) = {month_number}"
                )

        if any(
            phrase in lower
            for phrase in ("mes pasado", "último mes", "ultimo mes", "mes anterior")
        ):
            return (
                "\n  AND YEAR(Fecha) = YEAR(DATEADD(MONTH, -1, GETDATE()))"
                " AND MONTH(Fecha) = MONTH(DATEADD(MONTH, -1, GETDATE()))"
            )

        if any(
            phrase in lower for phrase in ("este mes", "este período", "este periodo")
        ):
            return (
                "\n  AND YEAR(Fecha) = YEAR(GETDATE())"
                " AND MONTH(Fecha) = MONTH(GETDATE())"
            )

        return AIVanna._year_filter_from_question(question)

    @staticmethod
    def _vendedor_performance_sql_template(question: str = "") -> str:
        n = AIVanna._extract_top_n(question)
        month_filter = AIVanna._month_filter_from_question(question)
        vendedor_norm = AIVanna._norm_vendedor_sql()
        return f"""
SELECT TOP {n}
    {vendedor_norm} AS Vendedor,
    COUNT(*) AS Ventas_Este_Mes,
    SUM(TotalMasIva) AS Total_Vendido,
    SUM(TotalSinIva - ValorCosto) AS Ganancia_Generada
FROM banco_datos
WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
  AND (VendedorFactura IS NOT NULL OR vendedor_codigo IS NOT NULL
       OR VendedorAsignado IS NOT NULL){month_filter}
GROUP BY {vendedor_norm}
ORDER BY Total_Vendido DESC
        """.strip()

    @staticmethod
    def _document_type_description_sql() -> str:
        return """
        CASE
            WHEN DocumentosCodigo = 'FED' THEN 'Factura Almacén'
            WHEN DocumentosCodigo = 'FEF' THEN 'Factura Florencia (Sika Center)'
            WHEN DocumentosCodigo = 'FET' THEN 'Factura Calle 5'
            WHEN DocumentosCodigo = 'DVD' THEN 'Devolución DVD'
            WHEN DocumentosCodigo = 'DVE' THEN 'Devolución DVE'
            WHEN DocumentosCodigo = 'DVF' THEN 'Devolución DVF'
            ELSE DocumentosCodigo
        END""".strip()

    @staticmethod
    def _is_document_type_sales_question(question: str) -> bool:
        if AIVanna._is_brand_by_branch_question(question):
            return False
        lower = (question or "").lower()
        has_document = any(
            token in lower
            for token in (
                "tipo de documento",
                "tipos de documento",
                "documentos codigo",
                "documentoscodigo",
                "por documento",
            )
        )
        has_sales = any(
            token in lower
            for token in ("venta", "ventas", "factur", "comparación", "comparacion")
        )
        return has_document and has_sales

    @staticmethod
    def _document_type_sales_sql_template(question: str = "") -> str:
        year_filter = AIVanna._year_filter_from_question(question)
        if not year_filter and "este año" not in (question or "").lower():
            year_filter = "\n  AND YEAR(Fecha) = YEAR(GETDATE())"
        descripcion = AIVanna._document_type_description_sql()
        return f"""
SELECT
    DocumentosCodigo AS Tipo_Documento,
    {descripcion} AS Descripcion,
    COUNT(*) AS Numero_Documentos,
    SUM(TotalMasIva) AS Ventas_Total,
    SUM(TotalSinIva - ValorCosto) AS Ganancia_Total,
    AVG(TotalMasIva) AS Promedio_Por_Documento
FROM banco_datos
WHERE DocumentosCodigo IN ('FED', 'FEF', 'FET'){year_filter}
GROUP BY DocumentosCodigo
ORDER BY Ventas_Total DESC
        """.strip()

    @staticmethod
    def _is_daily_average_by_month_question(question: str) -> bool:
        lower = (question or "").lower()
        has_daily = "diari" in lower
        has_average = any(token in lower for token in ("promedio", "media", "average"))
        has_month = "mes" in lower or "mensual" in lower
        has_sales = any(token in lower for token in ("venta", "ventas", "factur"))
        return has_daily and has_average and has_month and has_sales

    @staticmethod
    def _daily_average_by_month_sql_template() -> str:
        return """
SELECT
    YEAR(Fecha) AS Año,
    MONTH(Fecha) AS Mes,
    DATENAME(MONTH, Fecha) AS Nombre_Mes,
    AVG(Ventas_Diarias) AS Promedio_Ventas_Diarias,
    AVG(Num_Transacciones) AS Promedio_Transacciones_Diarias
FROM (
    SELECT
        Fecha,
        SUM(TotalMasIva) AS Ventas_Diarias,
        COUNT(*) AS Num_Transacciones
    FROM banco_datos
    WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
    GROUP BY Fecha
) AS Ventas_Diarias
GROUP BY YEAR(Fecha), MONTH(Fecha), DATENAME(MONTH, Fecha)
ORDER BY Año DESC, Mes DESC
        """.strip()

    @staticmethod
    def _brand_profit_sql_template() -> str:
        return """
SELECT TOP 10
    Marca,
    SUM(TotalSinIva - ValorCosto) AS Ganancia,
    SUM(TotalMasIva) AS Ventas,
    COUNT(*) AS Transacciones
FROM (
    SELECT
        UPPER(LTRIM(RTRIM(NULLIF(proveedor, '')))) AS Marca,
        TotalSinIva,
        ValorCosto,
        TotalMasIva
    FROM banco_datos
    WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
      AND NULLIF(LTRIM(RTRIM(proveedor)), '') IS NOT NULL
) AS marcas_norm
WHERE Marca NOT LIKE '%MATERIALES%'
  AND Marca NOT LIKE '%SERVICIO%'
  AND Marca NOT LIKE '%HERRAMIENAS%'
  AND Marca NOT LIKE '%REVESTIMIENTO%'
  AND Marca NOT LIKE '%PRODUCTOS EXCLUIDOS%'
  AND LEN(Marca) > 2
GROUP BY Marca
ORDER BY Ganancia DESC
        """.strip()

    @staticmethod
    def _is_credit_vs_cash_question(question: str) -> bool:
        lower = (question or "").lower()
        has_credit = any(token in lower for token in ("crédito", "credito", "contado"))
        has_compare = any(
            token in lower for token in ("vs", "versus", "frente a", "compar")
        )
        has_sales = any(token in lower for token in ("venta", "ventas", "factur"))
        return has_credit and has_compare and has_sales

    @staticmethod
    def _credit_vs_cash_sql_template(question: str = "") -> str:
        year_filter = AIVanna._year_filter_from_question(question)
        if not year_filter:
            year_filter = "\n  AND YEAR(Fecha) = YEAR(GETDATE())"
        return f"""
SELECT
    CASE
        WHEN DiasCredito = 0 THEN 'Contado'
        ELSE 'Credito'
    END AS Tipo_Venta,
    COUNT(*) AS Numero_Ventas,
    SUM(TotalMasIva) AS Ventas_Total,
    AVG(DiasCredito) AS Promedio_Dias_Credito,
    SUM(TotalSinIva - ValorCosto) AS Ganancia
FROM banco_datos
WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC'){year_filter}
GROUP BY CASE WHEN DiasCredito = 0 THEN 'Contado' ELSE 'Credito' END
ORDER BY Ventas_Total DESC
        """.strip()

    @staticmethod
    def _is_weekday_sales_question(question: str) -> bool:
        lower = (question or "").lower()
        return (
            "día de la semana" in lower
            or "dias de la semana" in lower
            or "días de la semana" in lower
        )

    @staticmethod
    def _is_sika_center_branch_question(question: str) -> bool:
        return AIVanna._is_branch_store_sales_question(question)

    @staticmethod
    def _is_last_n_days_sales_question(question: str) -> bool:
        lower = (question or "").lower()
        has_sales = any(token in lower for token in ("venta", "ventas", "factur"))
        has_window = any(
            token in lower
            for token in ("últimos", "ultimos", "último", "ultimo", "last")
        )
        has_days = bool(re.search(r"\d+\s*d[ií]as", lower))
        return has_sales and has_window and has_days

    @staticmethod
    def _extract_days_window(question: str, default: int = 30) -> int:
        lower = (question or "").lower()
        match = re.search(r"(\d+)\s*d[ií]as", lower)
        if match:
            return max(1, min(int(match.group(1)), 365))
        return default

    @staticmethod
    def _last_n_days_sales_sql_template(question: str = "") -> str:
        days = AIVanna._extract_days_window(question)
        return f"""
SELECT
    Fecha,
    SUM(TotalMasIva) AS Ventas_Diarias,
    COUNT(*) AS Numero_Transacciones
FROM banco_datos
WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
  AND Fecha >= DATEADD(DAY, -{days}, GETDATE())
GROUP BY Fecha
ORDER BY Fecha DESC
        """.strip()

    @staticmethod
    def _month_number_from_question(question: str) -> int:
        lower = (question or "").lower()
        numeric_month = re.search(
            r"month\s*\(\s*fecha\s*\)\s*=\s*(1[0-2]|[1-9])", lower
        )
        if numeric_month:
            return int(numeric_month.group(1))

        month_names = {
            "enero": 1,
            "febrero": 2,
            "marzo": 3,
            "abril": 4,
            "mayo": 5,
            "junio": 6,
            "julio": 7,
            "agosto": 8,
            "septiembre": 9,
            "setiembre": 9,
            "octubre": 10,
            "noviembre": 11,
            "diciembre": 12,
        }
        for month_name, month_number in month_names.items():
            if month_name in lower:
                return month_number
        return 0

    @staticmethod
    def _branch_store_sql_template(question: str = "") -> str:
        doc_code = AIVanna._branch_document_code(question) or "FEF"
        lower = (question or "").lower()
        year_filter = ""
        year_match = re.search(r"\b(20\d{2})\b", lower)
        if year_match:
            year_filter = f"\n  AND YEAR(Fecha) = {year_match.group(1)}"
        elif any(
            phrase in lower
            for phrase in ("este año", "este ano", "año actual", "ano actual")
        ):
            year_filter = "\n  AND YEAR(Fecha) = YEAR(GETDATE())"
        elif "por mes" not in lower and "mensual" not in lower:
            year_filter = "\n  AND YEAR(Fecha) = YEAR(GETDATE())"

        month_number = AIVanna._month_number_from_question(question)
        month_filter = f"\n  AND MONTH(Fecha) = {month_number}" if month_number else ""
        order_clause = (
            "Año DESC, Mes DESC" if "por mes" in lower or "mensual" in lower else "Mes"
        )

        return f"""
SELECT
    YEAR(Fecha) AS Año,
    MONTH(Fecha) AS Mes,
    DATENAME(MONTH, Fecha) AS Nombre_Mes,
    SUM(TotalMasIva) AS Ventas_Totales,
    SUM(TotalSinIva - ValorCosto) AS Ganancia,
    COUNT(*) AS Numero_Transacciones
FROM banco_datos
WHERE DocumentosCodigo = '{doc_code}'{year_filter}{month_filter}
GROUP BY YEAR(Fecha), MONTH(Fecha), DATENAME(MONTH, Fecha)
ORDER BY {order_clause}
        """.strip()

    @staticmethod
    def _sika_center_branch_sql_template(question: str = "") -> str:
        return AIVanna._branch_store_sql_template(question)

    @staticmethod
    def _repair_sika_center_customer_sql(sql: str) -> str:
        if not sql:
            return sql

        lower = sql.lower()
        references_sika_customer = (
            "tercerosnombres" in lower
            and "sika" in lower
            and "from banco_datos" in lower
        )
        if not references_sika_customer:
            return sql

        return AIVanna._branch_store_sql_template(sql)

    @staticmethod
    def _weekday_sales_sql_template() -> str:
        return """
WITH ventas_por_dia AS (
    SELECT
        ((DATEPART(WEEKDAY, Fecha) + @@DATEFIRST + 5) % 7) + 1 AS Dia_Orden,
        TotalMasIva,
        TotalSinIva,
        ValorCosto
    FROM banco_datos
    WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
      AND Fecha >= DATEADD(MONTH, -3, GETDATE())
)
SELECT
    CASE Dia_Orden
        WHEN 1 THEN 'Lunes'
        WHEN 2 THEN 'Martes'
        WHEN 3 THEN 'Miércoles'
        WHEN 4 THEN 'Jueves'
        WHEN 5 THEN 'Viernes'
        WHEN 6 THEN 'Sábado'
        WHEN 7 THEN 'Domingo'
    END AS Dia_Semana,
    Dia_Orden,
    SUM(TotalMasIva) AS Ventas_Totales,
    SUM(TotalSinIva - ValorCosto) AS Ganancia,
    COUNT(*) AS Numero_Transacciones
FROM ventas_por_dia
GROUP BY Dia_Orden
ORDER BY Dia_Orden
        """.strip()
