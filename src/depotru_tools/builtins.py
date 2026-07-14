"""Built-in tools for Phase 0 (no Magento live calls required)."""

from __future__ import annotations

from typing import Any, Mapping

from depotru_kernel.attribution import resolve_seller
from depotru_kernel.auth import ToolScope
from depotru_kernel.documents import CANONICAL_EXCLUDED_DOCUMENT_CODES
from depotru_tools.registry import ToolContext, ToolRegistry, ToolSpec

# Public store info (static; Magento theme can override later via config).
BRANCHES = [
    {
        "code": "FED",
        "name": "Sede Principal",
        "city": "Neiva",
        "note": "Sucursal comercial (DocumentosCodigo FED)",
    },
    {
        "code": "FEF",
        "name": "Sede Ferias / alterna",
        "city": "Neiva",
        "note": "Sucursal comercial",
    },
    {
        "code": "FET",
        "name": "Calle 5",
        "city": "Neiva",
        "note": "Sucursal comercial",
    },
]


def _tool_platform_health(ctx: ToolContext, params: Mapping[str, Any]) -> dict:
    return {
        "status": "ok",
        "audience": ctx.audience.value,
        "excluded_document_codes": list(CANONICAL_EXCLUDED_DOCUMENT_CODES),
        "platform": "depotru",
        "kernel_version": "0.1.0",
    }


def _tool_branches_info(ctx: ToolContext, params: Mapping[str, Any]) -> dict:
    return {"branches": BRANCHES, "locale": "es_CO"}


def _tool_resolve_seller(ctx: ToolContext, params: Mapping[str, Any]) -> dict:
    result = resolve_seller(
        code=params.get("code"),
        name=params.get("name"),
        asignado=params.get("asignado"),
        name_to_code=params.get("name_to_code"),
    )
    return dict(result)


def _tool_related_from_candidates(ctx: ToolContext, params: Mapping[str, Any]) -> dict:
    """Return related SKUs from an in-memory candidate map (export-backed later).

    params:
      sku: str
      candidates: {sku: [related_sku, ...]}  optional; empty → no hits
      limit: int
    """
    sku = str(params.get("sku") or "").strip()
    if not sku:
        return {"sku": sku, "related": [], "error": "sku_required"}
    candidates = params.get("candidates") or {}
    if not isinstance(candidates, Mapping):
        candidates = {}
    related = list(candidates.get(sku) or candidates.get(sku.upper()) or [])
    limit = int(params.get("limit") or 10)
    related = [str(s).strip() for s in related if str(s).strip() and str(s) != sku][
        :limit
    ]
    return {
        "sku": sku,
        "related": related,
        "source": "candidates",
        "policy": "fill_empty_only_or_merge_at_export",
    }


def _storefront_base_url() -> str:
    return (
        __import__("os").getenv("MAGENTO_STOREFRONT_URL")
        or __import__("os").getenv("MAGENTO_BASE_URL")
        or "https://www.depositotrujillo.co"
    ).rstrip("/")


def _storefront_search_url(query: str) -> str:
    from urllib.parse import quote_plus

    return f"{_storefront_base_url()}/catalogsearch/result/?q={quote_plus(query)}"


def storefront_product_url(url_key: str) -> str:
    """Build a PDP URL from Magento url_key (customer-facing, no SKU)."""
    key = (url_key or "").strip().strip("/")
    if not key:
        return ""
    suffix = __import__("os").getenv("MAGENTO_PRODUCT_URL_SUFFIX", ".html")
    if suffix and not suffix.startswith("."):
        suffix = f".{suffix}"
    base = _storefront_base_url()
    if key.endswith(suffix) or key.endswith(".html"):
        return f"{base}/{key}"
    return f"{base}/{key}{suffix}" if suffix else f"{base}/{key}"


def _search_products_db(query: str, limit: int = 5) -> list[dict]:
    """Best-effort product search on SmartBusiness sales history."""
    q = (query or "").strip()
    if not q or len(q) < 2:
        return []
    try:
        from business_analyzer.core.database import Database
        from depotru_kernel.documents import excluded_document_sql_in_list

        excl = excluded_document_sql_in_list()
        sql = f"""
            SELECT TOP {int(limit)}
                ArticulosCodigo AS sku,
                MAX(ArticulosNombre) AS name,
                SUM(Cantidad) AS qty_sold
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ({excl})
              AND ArticulosNombre LIKE %s
            GROUP BY ArticulosCodigo
            ORDER BY SUM(Cantidad) DESC
        """  # nosec B608 — excl from constants; limit cast int
        pattern = f"%{q}%"
        with Database() as db:
            rows = db.execute_query(sql, (pattern,))
        if not isinstance(rows, list):
            return []
        out = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            out.append(
                {
                    "sku": str(row.get("sku") or ""),
                    "name": str(row.get("name") or ""),
                    "qty_sold": row.get("qty_sold"),
                    "source": "banco_datos",
                }
            )
        return out
    except Exception:  # noqa: BLE001 — tool must never crash chat
        return []


def _tool_search_products(ctx: ToolContext, params: Mapping[str, Any]) -> dict:
    """Search catalog by free-text name (Magento REST and/or sales history)."""
    query = str(params.get("query") or params.get("q") or "").strip()
    limit = int(params.get("limit") or 5)
    limit = max(1, min(limit, 10))
    if not query:
        return {
            "query": "",
            "products": [],
            "status": "error",
            "reason": "query_required",
        }

    products: list[dict] = []
    source = "none"

    try:
        from depotru_integrations.magento.client import MagentoConfig, MagentoRestClient

        config = MagentoConfig.from_env()
        if config is not None:
            products = MagentoRestClient(config).search_products(query, page_size=limit)
            if products:
                source = "magento"
    except Exception:  # noqa: BLE001
        products = []

    if not products:
        products = _search_products_db(query, limit=limit)
        if products:
            source = "banco_datos"

    return {
        "query": query,
        "products": products,
        "count": len(products),
        "source": source,
        "search_url": _storefront_search_url(query),
        "status": "ok" if products else "empty",
    }


def _tool_sellable_qty_stub(ctx: ToolContext, params: Mapping[str, Any]) -> dict:
    """Customer-facing sellable qty via Magento MSI when configured.

    Never invents quantities — returns structured unavailable without credentials.
    """
    sku = str(params.get("sku") or "").strip()
    if not sku:
        return {
            "sku": "",
            "sellable_qty": None,
            "status": "error",
            "reason": "sku_required",
        }

    try:
        from depotru_integrations.magento.client import MagentoConfig, MagentoRestClient

        config = MagentoConfig.from_env()
        if config is not None:
            safety = float(params.get("safety_stock") or 10.0)
            payload = MagentoRestClient(config).sellable_qty(sku, safety_stock=safety)
            return dict(payload)
    except Exception as exc:  # noqa: BLE001 — surface adapter errors cleanly
        return {
            "sku": sku,
            "sellable_qty": None,
            "status": "error",
            "reason": "magento_request_failed",
            "detail": str(exc)[:300],
            "policy": "never invent stock; SafetyStock may reduce sellable below ERP",
        }

    return {
        "sku": sku,
        "sellable_qty": None,
        "status": "unavailable",
        "reason": "magento_adapter_not_configured",
        "hint": "Set MAGENTO_BASE_URL + MAGENTO_ACCESS_TOKEN for live MSI reads",
        "policy": "never invent stock; SafetyStock may reduce sellable below ERP",
    }


def register_builtin_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="platform.health",
            description="Platform health and canonical document exclusions",
            scope=ToolScope.PUBLIC_INFO,
            handler=_tool_platform_health,
            public_safe=True,
            parameters_schema={},
        )
    )
    registry.register(
        ToolSpec(
            name="info.branches",
            description="List commercial branch / sede codes",
            scope=ToolScope.PUBLIC_INFO,
            handler=_tool_branches_info,
            public_safe=True,
            parameters_schema={},
        )
    )
    registry.register(
        ToolSpec(
            name="attribution.resolve_seller",
            description=(
                "Resolve seller code using Asignado > Factura > codigo > POOL"
            ),
            scope=ToolScope.ATTRIBUTION,
            handler=_tool_resolve_seller,
            public_safe=False,
            parameters_schema={
                "code": "optional vendedor_codigo",
                "name": "optional VendedorFactura name",
                "asignado": "optional VendedorAsignado string",
            },
        )
    )
    registry.register(
        ToolSpec(
            name="catalog.related_for_sku",
            description="Related SKUs from candidate map (affinity export)",
            scope=ToolScope.PUBLIC_CATALOG,
            handler=_tool_related_from_candidates,
            public_safe=True,
            parameters_schema={
                "sku": "source SKU",
                "candidates": "optional map sku→list",
                "limit": "max links (default 10)",
            },
        )
    )
    registry.register(
        ToolSpec(
            name="inventory.sellable_qty",
            description="Customer-facing sellable qty (Magento MSI − SafetyStock)",
            scope=ToolScope.PUBLIC_STOCK,
            handler=_tool_sellable_qty_stub,
            public_safe=True,
            parameters_schema={"sku": "product SKU"},
        )
    )
    registry.register(
        ToolSpec(
            name="catalog.search_products",
            description="Search products by name (Magento and/or sales history)",
            scope=ToolScope.PUBLIC_CATALOG,
            handler=_tool_search_products,
            public_safe=True,
            parameters_schema={
                "query": "product name fragment, e.g. cemento",
                "limit": "max results (default 5)",
            },
        )
    )
