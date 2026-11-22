"""Built-in tools for Phase 0 (no Magento live calls required)."""

from __future__ import annotations

import math
import re
from decimal import Decimal
from typing import Any, Mapping, Optional

from depotru_kernel.attribution import resolve_seller
from depotru_kernel.auth import ToolScope
from depotru_kernel.documents import CANONICAL_EXCLUDED_DOCUMENT_CODES
from depotru_tools.registry import ToolContext, ToolRegistry, ToolSpec
from modules.catalog.stock import catalog_stock

# Public storefront locations (SSOT for customers: depositotrujillo.co/bodegas).
# Do not expose ERP document codes (FED/FEF/FET) to customers.
_PUBLIC_HOURS = (
    "Lunes a sábado (no festivos): 8:00 a.m. a 12:00 m. y 2:00 p.m. a 5:00 p.m."
)
_BODEGAS_URL = "https://www.depositotrujillo.co/bodegas"

BRANCHES = [
    {
        "name": "Bodega del Sur",
        "kind": "bodega",
        "city": "Neiva",
        "department": "Huila",
        "address": "Calle 24 con Carrera 20, Neiva, Huila",
        "phone": None,
        "whatsapp": None,
        "hours": _PUBLIC_HOURS,
        # Google place: Depósito Trujillo @ Cl. 24 & Cra. 20
        "maps_url": (
            "https://www.google.com/maps/place/Deposito+Trujillo/"
            "@2.9008497,-75.279817,17z"
        ),
        "note": "La más grande y amplia de Neiva; almacenamiento y distribución.",
    },
    {
        "name": "Bodega Mangueras",
        "kind": "bodega",
        "city": "Neiva",
        "department": "Huila",
        "address": "Calle 23 Sur # 6, Neiva, Huila",
        "phone": None,
        "whatsapp": None,
        "hours": _PUBLIC_HOURS,
        "maps_url": "https://www.google.com/maps/search/?api=1&query=2.907155,-75.284999",
        "note": (
            "Tanques plásticos, pozos sépticos, mallas, mangueras de riego y afines."
        ),
    },
    {
        "name": "Bodega 6",
        "kind": "bodega",
        "city": "Neiva",
        "department": "Huila",
        "address": "Recrificadora Santofimio, Neiva, Huila",
        "phone": None,
        "whatsapp": None,
        "hours": _PUBLIC_HOURS,
        # Google place: Recrificadora Santofimio
        "maps_url": (
            "https://www.google.com/maps/place/Recrificadora+Santofimio/"
            "@2.9223815,-75.2892973,17z"
        ),
        "note": "Punto de la red de bodegas en el centro de Neiva.",
    },
    {
        "name": "Sede Distribuciones (Sede Quinta / Calle 5)",
        "kind": "sede",
        "city": "Neiva",
        "department": "Huila",
        "address": "Calle 5 # 4-55, Neiva, Huila",
        "phone": "3152091771",
        "whatsapp": "3152091771",
        "hours": _PUBLIC_HOURS,
        "maps_url": "https://www.google.com/maps/search/?api=1&query=2.924377,-75.288068",
        "note": "Sede comercial Calle 5 (también referida como Sede Quinta).",
    },
]

STORE_CONTACT = {
    "whatsapp": "3168688799",
    "customer_service_phone": "3009109549",
    "hours": _PUBLIC_HOURS,
    "more_info_url": _BODEGAS_URL,
    "city": "Neiva",
    "department": "Huila",
    "legal_address": "Calle 4 # 2-20, Neiva, Huila (oficina / razón social)",
}


def format_branches_customer_reply(
    payload: Optional[Mapping[str, Any]] = None,
) -> str:
    """Spanish customer-facing list with address, hours, phones and maps."""
    data = dict(payload or {})
    branches = data.get("branches") or BRANCHES
    contact = data.get("contact") or STORE_CONTACT
    lines = [
        "Nuestras sedes y bodegas en Neiva (Huila):",
        "",
    ]
    for b in branches:
        if not isinstance(b, Mapping):
            continue
        name = (b.get("name") or "").strip()
        if not name:
            continue
        lines.append(f"• {name}")
        address = (b.get("address") or "").strip()
        if address:
            lines.append(f"  Dirección: {address}")
        hours = (b.get("hours") or contact.get("hours") or "").strip()
        if hours:
            lines.append(f"  Horario: {hours}")
        phone = (b.get("phone") or "").strip()
        if phone:
            pretty = _pretty_phone(phone)
            lines.append(f"  Teléfono: {pretty}")
        wa = (b.get("whatsapp") or "").strip()
        if wa and wa != phone:
            lines.append(f"  WhatsApp sede: {_pretty_phone(wa)}")
        maps_url = (b.get("maps_url") or "").strip()
        if maps_url:
            lines.append(f"  Mapa: {maps_url}")
        note = (b.get("note") or "").strip()
        if note:
            lines.append(f"  Nota: {note}")
        lines.append("")

    wa_main = (contact.get("whatsapp") or "").strip()
    svc = (contact.get("customer_service_phone") or "").strip()
    more = (contact.get("more_info_url") or _BODEGAS_URL).strip()
    if wa_main:
        lines.append(f"WhatsApp general: {_pretty_phone(wa_main)}")
    if svc:
        lines.append(f"Servicio al cliente: {_pretty_phone(svc)}")
    if more:
        lines.append(f"Más información y mapas: {more}")
    return "\n".join(lines).strip()


def _pretty_phone(raw: str) -> str:
    digits = "".join(c for c in raw if c.isdigit())
    if len(digits) == 10:
        return f"{digits[:3]} {digits[3:6]} {digits[6:]}"
    return raw.strip()


def _tool_platform_health(ctx: ToolContext, params: Mapping[str, Any]) -> dict:
    return {
        "status": "ok",
        "audience": ctx.audience.value,
        "excluded_document_codes": list(CANONICAL_EXCLUDED_DOCUMENT_CODES),
        "platform": "depotru",
        "kernel_version": "0.1.0",
    }


def _tool_branches_info(ctx: ToolContext, params: Mapping[str, Any]) -> dict:
    return {
        "branches": BRANCHES,
        "contact": STORE_CONTACT,
        "locale": "es_CO",
        "source": _BODEGAS_URL,
    }


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


def _catalog_search_tokens(query: str) -> list[str]:
    """Split a free-text catalog query into AND-able name tokens.

    Drops filler words (precio, de, x) so «sikafill 7 x galon precio» becomes
    ``sikafill``, ``7``, ``galon`` and matches names with intervening words.
    """
    noise = {
        "precio",
        "precios",
        "valor",
        "cuesta",
        "cuanto",
        "cuánto",
        "vale",
        "de",
        "del",
        "la",
        "el",
        "los",
        "las",
        "un",
        "una",
        "unos",
        "unas",
        "por",
        "para",
        "con",
        "x",
        "y",
        "en",
    }
    tokens: list[str] = []
    for raw in re.split(r"[\s+/,_-]+", (query or "").strip()):
        t = raw.strip(".,;:¿?¡!\"'()").casefold()
        if len(t) < 1 or t in noise:
            continue
        if t not in tokens:
            tokens.append(t)
        if len(tokens) >= 6:
            break
    return tokens


def _search_products_db(query: str, limit: int = 5) -> list[dict]:
    """Best-effort product search on SmartBusiness sales history."""
    q = (query or "").strip()
    tokens = _catalog_search_tokens(q)
    if not q or (len(q) < 2 and not tokens):
        return []
    try:
        from business_analyzer.core.database import Database
        from depotru_kernel.documents import excluded_document_sql_in_list

        excl = excluded_document_sql_in_list()
        use_tokens = tokens if len(tokens) >= 2 else []
        if use_tokens:
            name_clause = " AND ".join(["ArticulosNombre LIKE %s"] * len(use_tokens))
            params: tuple = tuple(f"%{t}%" for t in use_tokens)
        else:
            name_clause = "ArticulosNombre LIKE %s"
            params = (f"%{q}%",)
        sql = f"""
            SELECT TOP {int(limit)}
                ArticulosCodigo AS sku,
                MAX(ArticulosNombre) AS name,
                SUM(Cantidad) AS qty_sold
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ({excl})
              AND {name_clause}
            GROUP BY ArticulosCodigo
            ORDER BY SUM(Cantidad) DESC
        """  # nosec B608 — excl from constants; limit cast int; tokens bounded
        with Database() as db:
            rows = db.execute_query(sql, params)
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


def _tool_cross_sell_affinity(ctx: ToolContext, params: Mapping[str, Any]) -> dict:
    """Complementos medidos en las facturas de J3 (afinidad de canasta)."""
    from depotru_integrations.j3.affinity import cross_sell_affinity

    sku = str(params.get("sku") or "").strip()
    if not sku:
        return {"status": "error", "reason": "missing_sku", "products": []}
    # `limit` inf (p. ej. el JSON 1e309) lanza OverflowError en int() y el
    # worker responde 500 (hallazgo 8 de la firma). Rechaza el valor
    # inválido en vez de caerse.
    raw_limit = params.get("limit")
    if isinstance(raw_limit, float) and not math.isfinite(raw_limit):
        return {"status": "error", "reason": "invalid_limit", "products": []}
    try:
        limit = int(params.get("limit") or 5)
    except (TypeError, ValueError, OverflowError):
        return {"status": "error", "reason": "invalid_limit", "products": []}
    result: dict[str, Any] = cross_sell_affinity(sku, limit)
    return result


def _tool_cross_sell(ctx: ToolContext, params: Mapping[str, Any]) -> dict:
    """Lo que la tienda declara como complemento de un SKU (sin variantes)."""
    sku = str(params.get("sku") or params.get("query") or "").strip()
    limit = int(params.get("limit") or 5)
    limit = max(1, min(limit, 10))
    from depotru_integrations.magento.storefront import cross_sell_storefront

    result: dict[str, Any] = cross_sell_storefront(sku, limit=limit)
    return result


def _tool_names_by_sku(ctx: ToolContext, params: Mapping[str, Any]) -> dict:
    """Nombre comercial de varios SKU en una sola consulta a la tienda."""
    from depotru_integrations.magento.storefront import names_by_sku

    raw = params.get("skus") or []
    if isinstance(raw, str):
        raw = [part for part in raw.split(",") if part.strip()]
    result: dict[str, Any] = names_by_sku(list(raw))
    return result


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
    reason = ""

    # La tienda primero: nombra, describe y clasifica el producto como lo ve el
    # cliente, y su índice busca también en categorías («revestimiento» es una
    # categoría, no un artículo: el ERP no la dice nunca). Precio y cantidad no
    # se leen aquí, son de J3.
    try:
        from depotru_integrations.magento.storefront import search_storefront

        found = search_storefront(query, limit=limit)
        if found.get("status") == "error":
            reason = str(found.get("reason") or "storefront_error")
        products = found.get("products") or []
        total_count = int(found.get("total_count") or 0)
        if products:
            source = "ecommerce"
    except Exception as exc:  # noqa: BLE001 — un fallo debe verse, no esconderse
        products = []
        total_count = 0
        reason = f"storefront_error: {str(exc)[:160]}"

    if not products:
        total_count = 0
        products = _search_products_db(query, limit=limit)
        if products:
            source = "banco_datos"

    result = {
        "query": query,
        "products": products,
        "count": len(products),
        "source": source,
        "search_url": _storefront_search_url(query),
        "status": "ok" if products else "empty",
    }
    if source == "ecommerce":
        result["total_count"] = total_count
    if reason:
        # Sin esto, «la tienda no respondió» y «la tienda no tiene nada» se ven
        # igual, que es el defecto que dejó esta herramienta mintiendo un año.
        result["reason"] = reason
    return result


_QUOTE_SEARCH_REQUIRED_ALIASES = (
    "sku",
    "name",
    "price",
    "iva_rate",
    "line_id",
    "website_qty",
)


def _quote_search_j3_rows(sql: str, params: tuple, *, limit: int) -> list[dict]:
    """Execute a quote-search SQL and validate required aliases."""
    from business_analyzer.core.database import Database

    del limit  # limit is already baked into ``sql`` via TOP/LIMIT
    with Database(suppress_error_details=True) as db:
        rows = db.execute_query(sql, params)
    if not isinstance(rows, list):
        raise RuntimeError("unreadable result set")
    out: list[dict] = []
    for r in rows:
        if not isinstance(r, Mapping):
            raise RuntimeError("unreadable result set")
        row = dict(r)
        if any(alias not in row for alias in _QUOTE_SEARCH_REQUIRED_ALIASES):
            raise RuntimeError("unreadable result set")
        sku = row.get("sku")
        if sku is None or not str(sku).strip():
            raise RuntimeError("unreadable result set")
        out.append(row)
    return out


def _quote_search_j3(query: str, limit: int = 6) -> list[dict]:
    """Raw J3 rows: list price + IVA rate + website-allowlist stock. No cost.

    Raises a fixed internal failure on any J3 connection/query failure or an
    unreadable/malformed result set (missing required alias or a missing/blank
    SKU); the caller maps that to the fixed ``catalog_unavailable`` tool error.
    Driver details are suppressed.

    Phrase matches satisfy the same material/dimension guards as token matches.
    Suggestions never enter this path or silently rewrite a quote.
    """
    from depotru_tools.catalog_query import query_tokens, quote_search_statement

    tokens = query_tokens(query or "")
    if not tokens:
        return []
    if len(tokens) >= 2:
        sql, params = quote_search_statement(query, limit=limit, phrase=True)
        rows = _quote_search_j3_rows(sql, params, limit=limit)
        if rows:
            return rows
    sql, params = quote_search_statement(query, limit=limit)
    return _quote_search_j3_rows(sql, params, limit=limit)


def _tool_quote_search(ctx: ToolContext, params: Mapping[str, Any]) -> dict:
    """Agent quote: J3 price (before IVA) + IVA + stock, Magento display-only."""
    raw_query = params.get("query")
    query = raw_query.strip() if isinstance(raw_query, str) else ""
    raw_limit = params.get("limit")
    if isinstance(raw_limit, bool):
        limit = 6
    elif isinstance(raw_limit, int):
        limit = max(1, min(raw_limit, 40))
    else:
        limit = 6
    search_url = _storefront_search_url(query)
    if len(query) < 2:
        return {
            "query": query,
            "products": [],
            "count": 0,
            "source": "none",
            "search_url": search_url,
            "status": "error",
            "reason": "query_required",
        }

    magento_by_sku: dict[str, dict] = {}
    try:
        from depotru_integrations.magento.client import MagentoConfig, MagentoRestClient

        config = MagentoConfig.from_env()
        if config is not None:
            items = MagentoRestClient(config).search_products(
                query, page_size=limit, exact_prices=True
            )
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    sku = str(item.get("sku") or "")
                    if sku:
                        magento_by_sku[sku] = item
    except Exception:  # noqa: BLE001 — fail closed, never fall back to sales history
        magento_by_sku = {}

    try:
        j3_rows = _quote_search_j3(query, limit=limit)
    except Exception:  # noqa: BLE001 — map any J3 failure to the fixed reason
        return {
            "query": query,
            "products": [],
            "count": 0,
            "source": "none",
            "search_url": search_url,
            "status": "error",
            "reason": "catalog_unavailable",
        }

    from business_analyzer.core.quote_search_iva import build_product

    products: list[dict] = []
    try:
        for row in j3_rows:
            sku = str(row.get("sku") or "")
            products.append(build_product(j3_row=row, magento=magento_by_sku.get(sku)))

        if not products:
            for sku, mag in magento_by_sku.items():
                products.append(build_product(magento=mag))
    except Exception:  # noqa: BLE001 — unexpected validation/Decimal failure
        return {
            "query": query,
            "products": [],
            "count": 0,
            "source": "none",
            "search_url": search_url,
            "status": "error",
            "reason": "catalog_unavailable",
        }

    return {
        "query": query,
        "products": products,
        "count": len(products),
        "source": "j3" if j3_rows else ("magento" if magento_by_sku else "none"),
        "search_url": search_url,
        "status": "ok" if products else "empty",
    }


_QUOTE_SKUS_MAX = 20


def _tool_quote_skus(ctx: ToolContext, params: Mapping[str, Any]) -> dict:
    """Batch exact-SKU quote: N codes in ONE J3 query + short TTL cache.

    ``catalog.quote_search`` by SKU pays ~2.4 s of SQL Server time per call
    because its name predicate is non-sargable (full-inventory aggregate).
    The exact-code ``IN (...)`` predicate gets predicate pushdown, and a
    per-SKU cache with single-flight absorbs repeats/stampedes: cache
    misses of one call are resolved by ONE batch query whose rows fill the
    per-SKU entries (including empty answers for missing codes). Prices
    and stock follow the same closed quote contract as quote_search (J3
    ``ArticulosVenta`` before IVA, website-allowlist qty); no cost, no
    writes, Magento not consulted.
    """
    del ctx  # audience is enforced by the registry before this handler runs
    from depotru_tools.catalog_query import quote_skus_statement
    from depotru_tools.quote_cache import get_quote_sku_cache

    def _error(reason: str, skus: list[str]) -> dict:
        return {
            "skus": skus,
            "products": [],
            "count": 0,
            "found": [],
            "missing": [],
            "status": "error",
            "source": "none",
            "reason": reason,
        }

    raw = params.get("skus")
    if not isinstance(raw, (list, tuple)):
        return _error("skus_required", [])
    cleaned: list[str] = []
    seen: set[str] = set()
    invalid = False
    for item in raw:
        if not isinstance(item, str):
            invalid = True
            continue
        code = item.strip()
        if not code:
            continue
        key = code.casefold()
        if key not in seen:
            seen.add(key)
            cleaned.append(code)
    if invalid or len(cleaned) > _QUOTE_SKUS_MAX:
        return _error("skus_invalid", cleaned[:_QUOTE_SKUS_MAX])
    if not cleaned:
        return _error("skus_required", [])
    lower_skus = [c.casefold() for c in cleaned]

    cache = get_quote_sku_cache()

    if cache.ttl_seconds <= 0:
        # Cache disabled: ONE batch query for all keys. Going through
        # cache.resolve() here would run one query per SKU (peek() is always
        # None without a TTL), i.e. N round trips — the exact profile this
        # tool removes.
        try:
            sql, sql_params = quote_skus_statement(lower_skus)
            rows = _quote_search_j3_rows(sql, sql_params, limit=len(lower_skus))
        except Exception:  # noqa: BLE001 — map any J3 failure to the fixed reason
            return _error("catalog_unavailable", cleaned)
        grouped: dict[str, list[dict]] = {}
        for row in rows:
            grouped.setdefault(str(row.get("sku") or "").casefold(), []).append(row)
        rows_by_key = {sku_key: grouped.get(sku_key, []) for sku_key in lower_skus}
    else:

        def _batch_compute(sku_key: str) -> list[dict]:
            # One query for every key of THIS call still missing from the cache;
            # sibling entries (and empty answers) are stored from the same rows.
            # A concurrent overlapping call may run its own batch for keys this
            # flight has not stored yet — bounded duplication, same answers.
            missing_now = [k for k in lower_skus if cache.peek(k) is None]
            if not missing_now:
                return cache.peek(sku_key) or []
            sql, sql_params = quote_skus_statement(missing_now)
            rows = _quote_search_j3_rows(sql, sql_params, limit=len(missing_now))
            grouped: dict[str, list[dict]] = {}
            for row in rows:
                grouped.setdefault(str(row.get("sku") or "").casefold(), []).append(row)
            for k in missing_now:
                cache.store(k, grouped.get(k, []))
            return grouped.get(sku_key, [])

        try:
            rows_by_key = {
                sku_key: cache.resolve(sku_key, _batch_compute)
                for sku_key in lower_skus
            }
        except Exception:  # noqa: BLE001 — map any J3 failure to the fixed reason
            return _error("catalog_unavailable", cleaned)

    from business_analyzer.core.quote_search_iva import build_product

    products: list[dict] = []
    found: list[str] = []
    missing: list[str] = []
    try:
        for sku_key in lower_skus:
            rows = rows_by_key.get(sku_key) or []
            if not rows:
                missing.append(sku_key)
                continue
            found.append(sku_key)
            for row in rows:
                products.append(build_product(j3_row=row))
    except Exception:  # noqa: BLE001 — unexpected validation/Decimal failure
        return _error("catalog_unavailable", cleaned)

    return {
        "skus": cleaned,
        "products": products,
        "count": len(products),
        "found": found,
        "missing": missing,
        "status": "ok" if products else "empty",
        "source": "j3" if products else "none",
    }


def _tool_quote_for_customer(ctx: ToolContext, params: Mapping[str, Any]) -> dict:
    """Customer list price before IVA and per-warehouse stock. Fails closed.

    Does not write prices, stock, or cartera. A missing ERP answer is an
    error, never an empty catalog and never the mostrador price.
    """
    del ctx  # audience is enforced by the registry before this handler runs
    from business_analyzer.core.j3system_customer_quote import (
        fetch_customer_quote,
        parse_quote_request,
    )

    request, error = parse_quote_request(params)
    if error is not None:
        return error
    try:
        from business_analyzer.core.database import Database

        with Database() as db:
            return fetch_customer_quote(db, request)
    except Exception:  # noqa: BLE001 — fail closed; do not leak the driver message
        return {
            "status": "error",
            "reason": "erp_unavailable",
            "price_includes_iva": False,
            "lines": [],
            "terceros_id": request.terceros_id,
            "site": request.site,
        }


def _tool_resolve_customer_phone(ctx: ToolContext, params: Mapping[str, Any]) -> dict:
    """One usable price list for a phone, or a reason. Does not quote or write."""
    del ctx  # audience is enforced by the registry before this handler runs
    from business_analyzer.core.j3system_customer_phone import (
        fetch_customer_by_phone,
        phone_keys,
    )

    if isinstance(phone_keys(params.get("phone")), str):
        return fetch_customer_by_phone(None, params.get("phone"))
    try:
        from business_analyzer.core.database import Database

        with Database() as db:
            return fetch_customer_by_phone(db, params.get("phone"))
    except Exception:  # noqa: BLE001 — fail closed; do not leak the driver message
        return {"status": "error", "reason": "erp_unavailable"}


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

    # Sin Magento: stock real del ERP. `catalog.stock` ya resuelve bodegas de
    # venta web, año máximo, decimales exactos y distingue 0 de ausente.
    try:
        stock = catalog_stock(ctx, {"skus": [sku]})
    except Exception:  # noqa: BLE001 — nunca inventar una cifra
        return {
            "sku": sku,
            "sellable_qty": None,
            "in_stock": None,
            "status": "error",
            "reason": "j3_request_failed",
            "policy": "nunca inventar stock; sin dato si J3 no responde",
        }

    if not stock.get("ok"):
        return {
            "sku": sku,
            "sellable_qty": None,
            "in_stock": None,
            "status": "error",
            "reason": "j3_request_failed",
            "policy": "nunca inventar stock; sin dato si J3 no responde",
        }

    row = stock["results"][0]
    if row.get("status") != "ok":
        return {
            "sku": sku,
            "sellable_qty": None,
            "in_stock": None,
            "status": "unknown",
            "reason": row.get("status"),
            "source": "j3",
            "policy": "sin dato: el SKU no es publicable con certeza",
        }

    total = sum(
        (Decimal(v) for v in row["sedes"].values() if v is not None),
        Decimal(0),
    )
    qty = format(total, "f")
    return {
        "sku": sku,
        "sellable_qty": qty,
        "website_qty": qty,  # alias para la normalización de lib/catalog.ts
        "in_stock": total > 0,
        "status": "ok",
        "source": "j3_website_allowlist",
        "policy": "on-hand ERP en bodegas de venta web; no descuenta reservas",
    }


def _tool_brand_categories(ctx: ToolContext, params: Mapping[str, Any]) -> dict:
    """Categories and subcategories of a brand, from the Ecommerce storefront.

    The J3 category columns are not customer-facing ("OTRAS" holds most of
    Pintuco); the storefront taxonomy is what the customer sees. Read-only.
    """
    brand = str(params.get("brand") or params.get("marca") or "").strip()
    try:
        from depotru_integrations.magento.categories import brand_category_overview

        return dict(brand_category_overview(brand))
    except Exception as exc:  # noqa: BLE001 — a tool must never crash the inbox
        return {
            "brand": brand,
            "status": "error",
            "reason": "adapter_error",
            "detail": str(exc)[:200],
            "categories": [],
        }


def _tool_brand_suggest(ctx: ToolContext, params: Mapping[str, Any]) -> dict:
    """Storefront brands that look like the word the customer used.

    A typo («accesco» for ACESCO) must not end the conversation: naming the
    closest brand the storefront carries is a recommendation, not a guess —
    the customer confirms it.
    """
    query = str(params.get("query") or params.get("brand") or "").strip()
    try:
        limit = int(params.get("limit") or 3)
    except (TypeError, ValueError):
        limit = 3
    try:
        from depotru_integrations.magento.categories import suggest_brands

        return dict(suggest_brands(query, limit))
    except Exception as exc:  # noqa: BLE001 — a tool must never crash the inbox
        return {
            "query": query,
            "status": "error",
            "reason": "adapter_error",
            "detail": str(exc)[:200],
            "suggestions": [],
        }


def _tool_term_suggest(ctx: ToolContext, params: Mapping[str, Any]) -> dict:
    """Catalogue words that look like the word the customer typed.

    «semento»/«cemento», «blnaco»/«blanco»: the dictionary comes from the ERP
    article names, so a suggestion is always a word the catalogue really uses.
    """
    query = str(params.get("query") or params.get("term") or "").strip()
    try:
        limit = int(params.get("limit") or 3)
    except (TypeError, ValueError):
        limit = 3
    try:
        from depotru_integrations.j3.terms import suggest_terms

        return dict(suggest_terms(query, limit))
    except Exception as exc:  # noqa: BLE001 — a tool must never crash the inbox
        return {
            "query": query,
            "status": "error",
            "reason": "adapter_error",
            "detail": str(exc)[:200],
            "suggestions": [],
        }


def register_builtin_tools(registry: ToolRegistry) -> None:
    from modules.b2b.register import register_b2b_tools

    register_b2b_tools(registry)
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
            description=(
                "List storefront sedes/bodegas with full address, hours, "
                "phones and map links (Neiva, Huila)"
            ),
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
            name="catalog.brand_suggest",
            description=(
                "Storefront brands close to what the customer typed; used to "
                "recommend a real brand instead of refusing a typo. Read-only."
            ),
            scope=ToolScope.PUBLIC_CATALOG,
            handler=_tool_brand_suggest,
            public_safe=True,
            parameters_schema={
                "query": "word the customer used, e.g. accesco",
                "limit": "max suggestions (default 3)",
            },
        )
    )
    registry.register(
        ToolSpec(
            name="catalog.term_suggest",
            description=(
                "Catalogue words close to what the customer typed, taken from "
                "the ERP article names. Read-only, no prices."
            ),
            scope=ToolScope.PUBLIC_CATALOG,
            handler=_tool_term_suggest,
            public_safe=True,
            parameters_schema={
                "query": "word the customer used, e.g. semento",
                "limit": "max suggestions (default 3)",
            },
        )
    )
    from depotru_integrations.magento.category_products import category_products

    registry.register(
        ToolSpec(
            name="catalog.category_products",
            description=(
                "Products of a brand and stable storefront category url_path. "
                "Window 40, ranked by nightly 12-month invoice snapshot then "
                "smaller presentation. Public IVA-inclusive prices, no stock."
            ),
            scope=ToolScope.PUBLIC_CATALOG,
            handler=lambda ctx, params: category_products(
                params.get("brand"), params.get("url_path")
            ),
            public_safe=True,
            parameters_schema={
                "brand": "brand name, e.g. sika",
                "url_path": "stable category url_path from catalog.brand_categories",
            },
        )
    )
    registry.register(
        ToolSpec(
            name="catalog.brand_categories",
            description=(
                "Categories and subcategories of one brand as the Ecommerce "
                "storefront organises them. Read-only, no prices."
            ),
            scope=ToolScope.PUBLIC_CATALOG,
            handler=_tool_brand_categories,
            public_safe=True,
            parameters_schema={"brand": "brand name, e.g. pintuco"},
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
    registry.register(
        ToolSpec(
            name="catalog.quote_search",
            description=(
                "Agent quote search: J3 list price + website-allowlist stock, "
                "Magento PDP URL when configured"
            ),
            scope=ToolScope.PUBLIC_CATALOG,
            handler=_tool_quote_search,
            public_safe=True,
            parameters_schema={
                "query": "product name or SKU fragment",
                "limit": "max results (default 6)",
            },
        )
    )
    registry.register(
        ToolSpec(
            name="catalog.quote_skus",
            description=(
                "Batch exact-SKU quote: resolves 1-20 ArticulosCodigo in ONE "
                "J3 query (price before IVA, IVA rate, website-allowlist "
                "stock) with a short TTL cache. Use this instead of N "
                "quote_search calls when the SKUs are already known. Reports "
                "found/missing per code; fails closed with "
                "catalog_unavailable. Does not write."
            ),
            scope=ToolScope.PUBLIC_CATALOG,
            handler=_tool_quote_skus,
            public_safe=True,
            parameters_schema={
                "skus": 'list of 1-20 exact SKU codes, e.g. ["0020090002"]',
            },
        )
    )
    registry.register(
        ToolSpec(
            name="catalog.quote_for_customer",
            description=(
                "Customer quote: AdmPrecios net (before IVA) for a resolved "
                "TercerosID, unit UND, and per-warehouse stock at neiva "
                "(ALM, BD6, SUR, DIS, BOD) or florencia (FLO). Fails closed. "
                "Does not write."
            ),
            scope=ToolScope.SALES_PORTFOLIO,
            handler=_tool_quote_for_customer,
            public_safe=False,
            parameters_schema={
                "terceros_id": "AdmTerceros.TercerosID already resolved",
                "site": "neiva or florencia",
                "skus": "list of ArticulosCodigo, max 20",
            },
        )
    )
    registry.register(
        ToolSpec(
            name="catalog.resolve_customer_phone",
            description=(
                "Resolve a phone to one TercerosID when exactly one matched "
                "tercero has a usable tariff (not null, not 0, not 006 AL "
                "COSTO). Otherwise fail closed. Reads TercerosCelular, "
                "TercerosCelular2, and TelefonoContacto. Does not return the "
                "phone or the customer name, and does not write."
            ),
            scope=ToolScope.SALES_PORTFOLIO,
            handler=_tool_resolve_customer_phone,
            public_safe=False,
            parameters_schema={"phone": "customer phone, digits or formatted"},
        )
    )
    registry.register(
        ToolSpec(
            name="catalog.cross_sell",
            description=(
                "Products the Ecommerce storefront declares as complements of "
                "one SKU (cross-sell, related, upsell), without colour or "
                "presentation variants. Read-only, no prices."
            ),
            scope=ToolScope.PUBLIC_CATALOG,
            handler=_tool_cross_sell,
            public_safe=True,
            parameters_schema={
                "sku": "SKU already quoted, e.g. 0020090002",
                "limit": "max results (default 5)",
            },
        )
    )
    registry.register(
        ToolSpec(
            name="catalog.cross_sell_affinity",
            description=(
                "Complements of one SKU measured on J3 invoices (basket affinity, "
                "last 12 months): what customers actually buy together, ordered by "
                "shared baskets. Reads the nightly precomputed table and falls back "
                "to the live J3 query when it has no row. Read-only, no prices."
            ),
            scope=ToolScope.PUBLIC_CATALOG,
            handler=_tool_cross_sell_affinity,
            public_safe=True,
            parameters_schema={
                "sku": "SKU already quoted, e.g. 0020090002",
                "limit": "max results (default 5)",
            },
        )
    )
    registry.register(
        ToolSpec(
            name="catalog.names_by_sku",
            description=(
                "Commercial name of several SKUs in one storefront call. Used to "
                "name a quote with the store's identity instead of the warehouse's. "
                "Names only: price and quantity stay in J3."
            ),
            scope=ToolScope.PUBLIC_CATALOG,
            handler=_tool_names_by_sku,
            public_safe=True,
            parameters_schema={
                "skus": 'list of SKUs already quoted, e.g. ["0020090002"]',
            },
        )
    )
    registry.register(
        ToolSpec(
            name="catalog.stock",
            description=(
                "Exact SKU/sede availability from J3 inventory (sales flow). "
                "Read-only, fail-closed; returns exact fixed-point decimal strings."
            ),
            scope=ToolScope.SALES_PORTFOLIO,
            handler=catalog_stock,
            public_safe=False,
            parameters_schema={
                "skus": "list of 1-5 exact SKU codes",
                "sede": "optional 'neiva' | 'florencia' (absent → ambas)",
            },
        )
    )
