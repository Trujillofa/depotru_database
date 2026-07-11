"""Assistant BFF core — tool-routing stub (no free-form LLM yet).

Public turns use the tool registry so Magento can integrate safely.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from depotru_kernel.auth import Audience
from depotru_tools.registry import ToolContext, get_default_registry


@dataclass
class ChatRequest:
    message: str
    audience: Audience = Audience.PUBLIC
    session_id: Optional[str] = None
    locale: str = "es_CO"


@dataclass
class ChatResponse:
    reply: str
    session_id: str
    tools_used: List[str] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    grounded: bool = True
    mode: str = "stub_tools"


_SKU_RE = re.compile(r"\b(\d{4,14})\b")
_BRANCH_RE = re.compile(
    r"(?:"
    r"\bsedes?\b|"  # sede / sedes
    r"\bsucursales?\b|"
    r"\bhorarios?\b|"
    r"\bubicaci[oó]n(?:es)?\b|"
    r"d[oó]nde\s+est[aá]n|"
    r"cu[aá]les\s+son\s+las\s+sedes"
    r")",
    re.I,
)
_STOCK_RE = re.compile(
    r"\b(stock|existencia|disponible|hay|inventario|qty|cantidad)\b",
    re.I,
)
_RELATED_RE = re.compile(
    r"\b(relacionad|complement|cross.?sell|junto|afinidad)\b",
    re.I,
)
# "tienen cemento?", "stock de cemento", "busco varilla", "necesito pintura"
_PRODUCT_QUERY_RE = re.compile(
    r"(?:"
    r"tienen\s+(.+?)(?:\?|$)|"
    r"tiene\s+(.+?)(?:\?|$)|"
    r"hay\s+(.+?)(?:\?|$)|"
    r"stock\s+(?:de\s+|del\s+)?(.+?)(?:\?|$)|"
    r"existencia\s+(?:de\s+|del\s+)?(.+?)(?:\?|$)|"
    r"busco\s+(.+?)(?:\?|$)|"
    r"necesito\s+(.+?)(?:\?|$)|"
    r"venden\s+(.+?)(?:\?|$)|"
    r"precio\s+(?:de\s+|del\s+)?(.+?)(?:\?|$)"
    r")",
    re.I,
)
_STOP_QUERY = re.compile(
    r"\b(sku|sede|sucursal|horario|producto|productos|relacionad\w*)\b",
    re.I,
)


def _clean_product_query(raw: str) -> str:
    q = (raw or "").strip()
    q = re.sub(r"[¿?¡!.,;:]+$", "", q).strip()
    q = re.sub(
        r"^(el|la|los|las|un|una|unos|unas|de|del|en)\s+",
        "",
        q,
        flags=re.I,
    ).strip()
    # drop trailing politeness
    q = re.sub(r"\s+(por\s+favor|pls|please)\s*$", "", q, flags=re.I).strip()
    if len(q) < 2 or _STOP_QUERY.search(q):
        return ""
    # reject pure numbers (handled as SKU elsewhere)
    if re.fullmatch(r"\d{4,14}", q):
        return ""
    return q[:80]


def extract_product_query(text: str) -> Optional[str]:
    """Pull a product name fragment from natural Spanish storefront questions."""
    m = _PRODUCT_QUERY_RE.search(text or "")
    if not m:
        return None
    for g in m.groups():
        if g:
            cleaned = _clean_product_query(g)
            if cleaned:
                return cleaned
    return None


def run_assistant_turn(req: ChatRequest) -> ChatResponse:
    """Deterministic tool-routing stub for public/customer audiences."""
    session_id = req.session_id or str(uuid.uuid4())
    registry = get_default_registry()
    ctx = ToolContext(audience=req.audience, request_id=session_id)
    tools_used: List[str] = []
    tool_results: List[Dict[str, Any]] = []
    text = (req.message or "").strip()

    if not text:
        return ChatResponse(
            reply=(
                "¿En qué puedo ayudarte? Puedo indicar sedes, buscar productos "
                "(ej. cemento), stock por SKU o productos relacionados."
            ),
            session_id=session_id,
            mode="stub_tools",
        )

    # Branches / store info
    if _BRANCH_RE.search(text):
        result = registry.call("info.branches", {}, context=ctx)
        tools_used.append("info.branches")
        tool_results.append({"tool": "info.branches", "result": result})
        lines = [
            f"- {b['code']}: {b['name']} ({b.get('city', '')})"
            for b in result.get("branches", [])
        ]
        reply = "Nuestras sedes comerciales:\n" + "\n".join(lines)
        return ChatResponse(
            reply=reply,
            session_id=session_id,
            tools_used=tools_used,
            tool_results=tool_results,
        )

    sku_match = _SKU_RE.search(text)
    sku = sku_match.group(1) if sku_match else None

    # Stock by SKU
    if sku and _STOCK_RE.search(text):
        result = registry.call("inventory.sellable_qty", {"sku": sku}, context=ctx)
        tools_used.append("inventory.sellable_qty")
        tool_results.append({"tool": "inventory.sellable_qty", "result": result})
        if result.get("status") == "unavailable":
            reply = (
                f"Aún no puedo consultar existencias en vivo del SKU {sku} "
                f"(adaptador Magento no configurado). "
                f"Cuando esté activo, responderé con cantidad vendible "
                f"(MSI − stock de seguridad)."
            )
        elif result.get("status") == "error":
            reply = (
                f"No pude consultar el stock del SKU {sku} en este momento. "
                f"Intenta de nuevo o búscalo en la tienda."
            )
        else:
            qty = result.get("sellable_qty")
            in_stock = result.get("in_stock")
            if in_stock is False or qty == 0:
                reply = (
                    f"SKU {sku}: sin cantidad vendible en este momento "
                    f"(política de stock de seguridad aplicada)."
                )
            else:
                reply = (
                    f"SKU {sku}: cantidad vendible aproximada {qty}. "
                    f"(Política SafetyStock aplicada.)"
                )
        return ChatResponse(
            reply=reply,
            session_id=session_id,
            tools_used=tools_used,
            tool_results=tool_results,
        )

    # Related by SKU
    if sku and _RELATED_RE.search(text):
        result = registry.call(
            "catalog.related_for_sku",
            {"sku": sku, "candidates": {}},
            context=ctx,
        )
        tools_used.append("catalog.related_for_sku")
        tool_results.append({"tool": "catalog.related_for_sku", "result": result})
        related = result.get("related") or []
        if related:
            reply = f"Relacionados para {sku}: {', '.join(related)}"
        else:
            reply = (
                f"No tengo links de afinidad cargados para el SKU {sku} en esta sesión. "
                f"Puedes buscarlo en la tienda o indicar otro SKU."
            )
        return ChatResponse(
            reply=reply,
            session_id=session_id,
            tools_used=tools_used,
            tool_results=tool_results,
        )

    # Product name search: "tienen cemento?", "stock de cemento"
    product_q = extract_product_query(text)
    if product_q:
        result = registry.call(
            "catalog.search_products",
            {"query": product_q, "limit": 5},
            context=ctx,
        )
        tools_used.append("catalog.search_products")
        tool_results.append({"tool": "catalog.search_products", "result": result})
        products = result.get("products") or []
        search_url = result.get("search_url") or ""
        if products:
            lines = []
            for p in products[:5]:
                sku_p = p.get("sku") or ""
                name_p = p.get("name") or ""
                lines.append(f"- {sku_p}: {name_p}" if sku_p else f"- {name_p}")
            reply = (
                f"Encontré estos productos relacionados con «{product_q}»:\n"
                + "\n".join(lines)
                + "\n\nPuedes pedir stock con: «stock del SKU …»."
            )
            if search_url:
                reply += f"\nVer más en la tienda: {search_url}"
        else:
            reply = (
                f"No encontré coincidencias rápidas para «{product_q}» en el catálogo "
                f"consultado."
            )
            if search_url:
                reply += f" Prueba la búsqueda de la tienda: {search_url}"
            reply += " Si tienes el código SKU, escribe «stock del SKU ##########»."
        return ChatResponse(
            reply=reply,
            session_id=session_id,
            tools_used=tools_used,
            tool_results=tool_results,
        )

    # Default help
    health = registry.call("platform.health", {}, context=ctx)
    tools_used.append("platform.health")
    tool_results.append({"tool": "platform.health", "result": health})
    reply = (
        "Soy el asistente de Depósito Trujillo (modo herramientas). "
        "Puedes preguntar: «¿dónde están las sedes?», «¿tienen cemento?», "
        "«stock del SKU 1234567890», o «productos relacionados al SKU …». "
        "No invento precios de costo ni carteras de terceros."
    )
    return ChatResponse(
        reply=reply,
        session_id=session_id,
        tools_used=tools_used,
        tool_results=tool_results,
    )
