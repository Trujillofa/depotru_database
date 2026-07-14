"""Assistant BFF core — tool-routing for storefront customers.

Public turns use the tool registry. Customers describe *problems/jobs*;
we answer with product types and catalog names — never SKU codes.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from depotru_kernel.auth import Audience
from depotru_tools.registry import ToolContext, get_default_registry
from modules.assistant.problem_guides import (
    extract_problem_topic,
    format_need_list,
    looks_like_problem,
    match_guide,
    search_queries_for_guide,
)


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
# "tienen cemento?", "busco varilla", "necesito pintura" (product name, not problem)
_PRODUCT_QUERY_RE = re.compile(
    r"(?:"
    r"tienen\s+(.+?)(?:\?|$)|"
    r"tiene\s+(.+?)(?:\?|$)|"
    r"hay\s+(.+?)(?:\?|$)|"
    r"stock\s+(?:de\s+|del\s+)?(.+?)(?:\?|$)|"
    r"existencia\s+(?:de\s+|del\s+)?(.+?)(?:\?|$)|"
    r"busco\s+(.+?)(?:\?|$)|"
    r"necesito\s+(?!material(?:es)?\s+para|cosas\s+para|productos?\s+para)(.+?)(?:\?|$)|"
    r"venden\s+(.+?)(?:\?|$)|"
    r"precio\s+(?:de\s+|del\s+)?(.+?)(?:\?|$)|"
    r"me\s+recomiendan?\s+(.+?)(?:\?|$)"
    r")",
    re.I,
)
_STOP_QUERY = re.compile(
    r"\b(sku|sede|sucursal|horario|producto|productos|relacionad\w*|stock)\b",
    re.I,
)

_HELP_REPLY = (
    "Soy el asistente de Depósito Trujillo. "
    "Cuéntame el trabajo o el problema (ej. «tengo una gotera», "
    "«qué necesito para pintar una habitación», «fuga en el grifo») "
    "y te armo una lista de productos. "
    "También puedo indicar sedes o buscar un producto por nombre "
    "(«¿tienen cemento?»). "
    "No invento precios de costo ni datos de terceros."
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
    q = re.sub(r"\s+(por\s+favor|pls|please)\s*$", "", q, flags=re.I).strip()
    if len(q) < 2 or _STOP_QUERY.search(q):
        return ""
    # pure numbers are internal codes — customers don't use them
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


def _search_products(
    registry: Any,
    ctx: ToolContext,
    query: str,
    limit: int = 5,
) -> Dict[str, Any]:
    result = registry.call(
        "catalog.search_products",
        {"query": query, "limit": limit},
        context=ctx,
    )
    return result if isinstance(result, dict) else {}


def _product_names(products: List[Dict[str, Any]], limit: int = 5) -> List[str]:
    names: List[str] = []
    for p in products[:limit]:
        name = (p.get("name") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _format_product_bullets(names: List[str]) -> str:
    return "\n".join(f"• {n}" for n in names)


def _reply_problem_guide(
    registry: Any,
    ctx: ToolContext,
    tools_used: List[str],
    tool_results: List[Dict[str, Any]],
    text: str,
) -> Optional[str]:
    guide = match_guide(text)
    if not guide:
        return None

    parts = [
        guide.title,
        guide.intro,
        format_need_list(guide.needs),
    ]
    if guide.tip:
        parts.append(f"\nConsejo: {guide.tip}")

    # Ground with a few real catalog names (no SKUs)
    found_names: List[str] = []
    search_url = ""
    for q in search_queries_for_guide(guide, max_queries=3):
        result = _search_products(registry, ctx, q, limit=2)
        tools_used.append("catalog.search_products")
        tool_results.append({"tool": "catalog.search_products", "result": result})
        found_names.extend(_product_names(result.get("products") or [], limit=2))
        if not search_url:
            search_url = result.get("search_url") or ""

    # de-dupe names preserving order
    uniq: List[str] = []
    for n in found_names:
        if n not in uniq:
            uniq.append(n)
    if uniq:
        parts.append("\nAlgunos productos de nuestro catálogo que pueden servir:")
        parts.append(_format_product_bullets(uniq[:6]))
    if search_url:
        # Use first need query for a useful storefront link when possible
        first_q = guide.needs[0].query if guide.needs else guide.title
        result_url = _search_products(registry, ctx, first_q, limit=1)
        tools_used.append("catalog.search_products")
        tool_results.append({"tool": "catalog.search_products", "result": result_url})
        url = result_url.get("search_url") or search_url
        parts.append(f"\nVer opciones en la tienda: {url}")

    parts.append(
        "\nSi me das más detalle (medidas, material o foto del problema), "
        "afino la lista."
    )
    return "\n".join(parts)


def _reply_problem_topic(
    registry: Any,
    ctx: ToolContext,
    tools_used: List[str],
    tool_results: List[Dict[str, Any]],
    topic: str,
) -> str:
    """No curated guide — search by topic words and explain generically."""
    result = _search_products(registry, ctx, topic, limit=6)
    tools_used.append("catalog.search_products")
    tool_results.append({"tool": "catalog.search_products", "result": result})
    products = result.get("products") or []
    search_url = result.get("search_url") or ""
    names = _product_names(products, limit=6)

    parts = [
        f"Para «{topic}» te oriento con productos por nombre "
        f"(sin códigos internos):",
    ]
    if names:
        parts.append(_format_product_bullets(names))
        parts.append(
            "\nSi me cuentas más del problema (gotera, pintura, plomería, "
            "electricidad, etc.), te armo una lista de materiales paso a paso."
        )
    else:
        parts.append(
            "No encontré coincidencias rápidas con esa frase. "
            "Prueba describir el problema: por ejemplo "
            "«tengo una gotera», «quiero pintar una habitación» o "
            "«se me dañó el grifo»."
        )
    if search_url:
        parts.append(f"Búsqueda en la tienda: {search_url}")
    return "\n".join(parts)


def _reply_product_name_search(
    registry: Any,
    ctx: ToolContext,
    tools_used: List[str],
    tool_results: List[Dict[str, Any]],
    product_q: str,
) -> str:
    result = _search_products(registry, ctx, product_q, limit=5)
    tools_used.append("catalog.search_products")
    tool_results.append({"tool": "catalog.search_products", "result": result})
    products = result.get("products") or []
    search_url = result.get("search_url") or ""
    names = _product_names(products, limit=5)

    if names:
        reply = (
            f"Encontré estos productos relacionados con «{product_q}»:\n"
            + _format_product_bullets(names)
            + "\n\n¿Es para algún trabajo en particular? "
            "Dime el problema (pintar, gotera, plomería, etc.) "
            "y te sugiero qué más suele hacer falta."
        )
        if search_url:
            reply += f"\nVer más: {search_url}"
        return reply

    reply = (
        f"No encontré coincidencias rápidas para «{product_q}» en el catálogo "
        f"consultado."
    )
    if search_url:
        reply += f" Prueba la búsqueda de la tienda: {search_url}"
    reply += (
        " También puedes describir el problema: "
        "«qué necesito para…» y te armo una lista."
    )
    return reply


def run_assistant_turn(req: ChatRequest) -> ChatResponse:
    """Deterministic tool-routing for public/customer audiences."""
    session_id = req.session_id or str(uuid.uuid4())
    registry = get_default_registry()
    ctx = ToolContext(audience=req.audience, request_id=session_id)
    tools_used: List[str] = []
    tool_results: List[Dict[str, Any]] = []
    text = (req.message or "").strip()

    if not text:
        return ChatResponse(
            reply=(
                "¿En qué puedo ayudarte? Cuéntame el trabajo o problema "
                "(ej. gotera, pintar, grifo que gotea) o pregunta por un "
                "producto por nombre. También indico sedes."
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
            f"- {b['name']} ({b.get('city', '')})" for b in result.get("branches", [])
        ]
        reply = "Nuestras sedes comerciales:\n" + "\n".join(lines)
        return ChatResponse(
            reply=reply,
            session_id=session_id,
            tools_used=tools_used,
            tool_results=tool_results,
        )

    # Problem / project first (customer language)
    if looks_like_problem(text) or match_guide(text):
        guide_reply = _reply_problem_guide(
            registry, ctx, tools_used, tool_results, text
        )
        if guide_reply:
            return ChatResponse(
                reply=guide_reply,
                session_id=session_id,
                tools_used=tools_used,
                tool_results=tool_results,
            )
        topic = extract_problem_topic(text)
        if topic:
            reply = _reply_problem_topic(registry, ctx, tools_used, tool_results, topic)
            return ChatResponse(
                reply=reply,
                session_id=session_id,
                tools_used=tools_used,
                tool_results=tool_results,
            )

    # Product name search: "tienen cemento?", "busco varilla"
    product_q = extract_product_query(text)
    if product_q:
        # If the product phrase is itself a problem phrase, prefer guide
        if match_guide(product_q) or looks_like_problem(product_q):
            guide_reply = _reply_problem_guide(
                registry, ctx, tools_used, tool_results, product_q
            )
            if guide_reply:
                return ChatResponse(
                    reply=guide_reply,
                    session_id=session_id,
                    tools_used=tools_used,
                    tool_results=tool_results,
                )
        reply = _reply_product_name_search(
            registry, ctx, tools_used, tool_results, product_q
        )
        return ChatResponse(
            reply=reply,
            session_id=session_id,
            tools_used=tools_used,
            tool_results=tool_results,
        )

    # Free-text fallback: try guide match on whole text already done;
    # if message is long enough, treat as soft topic search
    if len(text) >= 12 and not _BRANCH_RE.search(text):
        # Avoid treating pure greetings as product search
        if not re.fullmatch(
            r"(hola|buenas|buenos\s+d[ií]as|buenas\s+tardes|hey|hi)[\s!.]*",
            text,
            flags=re.I,
        ):
            # Prefer problem topic extraction one more time
            topic = extract_problem_topic(text) or text[:80]
            if looks_like_problem(text) or extract_problem_topic(text):
                reply = _reply_problem_topic(
                    registry, ctx, tools_used, tool_results, topic
                )
                return ChatResponse(
                    reply=reply,
                    session_id=session_id,
                    tools_used=tools_used,
                    tool_results=tool_results,
                )

    # Default help (no SKU language)
    health = registry.call("platform.health", {}, context=ctx)
    tools_used.append("platform.health")
    tool_results.append({"tool": "platform.health", "result": health})
    return ChatResponse(
        reply=_HELP_REPLY,
        session_id=session_id,
        tools_used=tools_used,
        tool_results=tool_results,
    )
