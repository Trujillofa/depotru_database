"""Assistant BFF core — tool-routing for storefront customers.

Public turns use the tool registry. Customers describe *problems/jobs*;
we answer with product types and catalog names — never SKU codes.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

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
    mode: str = "stub_tools"  # stub_tools | llm_tools
    guide_id: Optional[str] = None
    product_query: Optional[str] = None
    # Internal: True only for generic-help stub path → hybrid may call LLM
    llm_eligible: bool = False


_BRANCH_RE = re.compile(
    r"(?:"
    r"\bsedes?\b|"  # sede / sedes
    r"\bsucursales?\b|"
    r"\bhorarios?\b|"
    r"\bubicaci[oó]n(?:es)?\b|"
    r"d[oó]nde\s+(?:est[aá]n|est[aá]|queda|quede)|"
    r"cu[aá]les\s+son\s+las\s+sedes|"
    r"sede\s+principal"
    r")",
    re.I,
)
# Full-message greetings only (no product/job content).
_GREETING_ONLY_RE = re.compile(
    r"^\s*(?:"
    r"hola(?:\s+(?:buenos?\s+d[ií]as|buenas?\s+(?:tardes|noches)|buenas))?|"
    r"buenos?\s+d[ií]as|"
    r"buen\s+d[ií]a|"
    r"buenas?\s+(?:tardes|noches)|"
    r"buenas|"
    r"hello(?:\s+\w+)?|"
    r"hi|"
    r"hey|"
    r"saludos"
    r")[\s!.¡¿,?]*$",
    re.I,
)
# Leading greeting on mixed turns: "HOLA ANDO BUSCANDO…"
_LEADING_GREETING_RE = re.compile(
    r"^\s*(?:"
    r"hola|"
    r"buenos?\s+d[ií]as|"
    r"buen\s+d[ií]a|"
    r"buenas?\s+(?:tardes|noches)|"
    r"buenas|"
    r"hello|"
    r"hi|"
    r"hey"
    r")[\s,!.¡¿:]+",
    re.I,
)
# Checkout / online payment — not a product search.
_CART_PAY_RE = re.compile(
    r"(?:"
    r"\bpagar\b|"
    r"\bpago\b|"
    r"\bpagos?\b|"
    r"\bcarrito\b|"
    r"carro\s+de\s+compras|"
    r"\bcheckout\b|"
    r"pasarela\s+de\s+pago|"
    r"medio\s+de\s+pago|"
    r"pagar\s+por\s+internet|"
    r"lo\s+que\s+tengo\s+en\s+el\s+carro"
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
    r"ando\s+buscando\s+(.+?)(?:\?|$)|"
    r"buscando\s+(.+?)(?:\?|$)|"
    r"cotizar\s+(?:un|una|unos|unas)?\s*(.+?)(?:\?|$)|"
    r"necesito\s+(?!material(?:es)?\s+para|cosas\s+para|productos?\s+para)(.+?)(?:\?|$)|"
    r"venden\s+(.+?)(?:\?|$)|"
    r"precio\s+(?:de\s+|del\s+)?(.+?)(?:\?|$)|"
    r"me\s+recomiendan?\s+(.+?)(?:\?|$)|"
    r"suministro[,\s]+(?:transporte[,\s]+)?(?:e\s+)?instalaci[oó]n\s+de\s+(.+?)(?:\?|$)"
    r")",
    re.I,
)
_STOP_QUERY = re.compile(
    r"\b(sku|sede|sucursal|horario|producto|productos|relacionad\w*|stock)\b",
    re.I,
)
# Leading quantity: "15 rodillos profesional…"
_LEADING_QTY_RE = re.compile(
    r"^\s*\d+(?:[.,]\d+)?\s*(?:x\s*)?(?:und(?:s|ades?)?|unidades?)?\s+",
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

_CART_REPLY = (
    "Para pagar o finalizar lo que tienes en el carrito, usa el "
    "checkout de la tienda en www.depositotrujillo.co (ícono del carrito). "
    "Desde este chat no puedo cobrar ni ver tu carrito. "
    "Si necesitas un producto, sedes u orientación para un trabajo, dímelo."
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
    q = _LEADING_QTY_RE.sub("", q).strip()
    q = re.sub(r"\s+(por\s+favor|pls|please)\s*$", "", q, flags=re.I).strip()
    if len(q) < 2 or _STOP_QUERY.search(q):
        return ""
    # pure numbers are internal codes — customers don't use them
    if re.fullmatch(r"\d{4,14}", q):
        return ""
    return q[:80]


def _strip_leading_greeting(text: str) -> str:
    """Remove leading hola/buenas so mixed turns can product-route."""
    return _LEADING_GREETING_RE.sub("", text or "", count=1).strip()


def is_greeting_only(text: str) -> bool:
    return bool(_GREETING_ONLY_RE.match((text or "").strip()))


def is_cart_pay_intent(text: str) -> bool:
    return bool(_CART_PAY_RE.search(text or ""))


def extract_product_query(text: str) -> Optional[str]:
    """Pull a product name fragment from natural Spanish storefront questions."""
    t = _strip_leading_greeting(text or "")
    if not t:
        t = text or ""
    m = _PRODUCT_QUERY_RE.search(t)
    if not m:
        return None
    for g in m.groups():
        if g:
            cleaned = _clean_product_query(g)
            if cleaned:
                return cleaned
    return None


def bare_product_query(text: str) -> Optional[str]:
    """Treat free-text as a catalog query when it looks like a product name.

    Used after explicit extract fails: «SDS anticorrisvo negro», «Lavaropas…».
    Long free-form prose is left for hybrid LLM (not forced through catalog).
    """
    t = _strip_leading_greeting(text or "")
    t = (t or text or "").strip()
    t = re.sub(r"[¿?¡!]+", "", t).strip()
    if len(t) < 4:
        return None
    if is_greeting_only(t) or is_cart_pay_intent(t) or _BRANCH_RE.search(t):
        return None
    # Single short token with no letters of substance
    if re.fullmatch(r"\d+", t):
        return None
    # Prefer messages that look like product names / specs, not long prose
    cleaned = _clean_product_query(t)
    if not cleaned or len(cleaned) < 4:
        return None
    # Skip pure help questions / free-form intents (hybrid LLM path)
    if re.match(
        r"^(c[oó]mo|qu[eé]|por\s+qu[eé]|ayuda|help|quiero|quisiera|"
        r"me\s+gustar[ií]a|ayúdame|ayudame|podr[ií]as|me\s+puedes|"
        r"explica|recomi[eé]ndame|necesito\s+ayuda)\b",
        cleaned,
        flags=re.I,
    ):
        return None
    # Long prose (many tokens, no clear product phrase) → LLM-eligible help
    words = cleaned.split()
    if len(words) > 10:
        return None
    return cleaned[:80]


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


def _collect_products(
    products: List[Any],
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """De-dupe by name; prefer entries that already have product_url."""
    by_name: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for raw in products:
        if not isinstance(raw, dict):
            continue
        p: Dict[str, Any] = raw
        name = (p.get("name") or "").strip()
        if not name:
            continue
        key = name.casefold()
        existing = by_name.get(key)
        if existing is None:
            by_name[key] = p
            order.append(key)
        elif (
            not (existing.get("product_url") or "").strip()
            and (p.get("product_url") or "").strip()
        ):
            by_name[key] = p
    # Prefer linked products first, preserve relative order within groups
    linked = [
        by_name[k] for k in order if (by_name[k].get("product_url") or "").strip()
    ]
    plain = [
        by_name[k] for k in order if not (by_name[k].get("product_url") or "").strip()
    ]
    return (linked + plain)[:limit]


def format_product_lines(products: List[Dict[str, Any]], limit: int = 5) -> str:
    """Customer-facing bullets: name + optional PDP URL (never SKU)."""
    lines: List[str] = []
    for p in _collect_products(products, limit=limit):
        name = (p.get("name") or "").strip()
        url = (p.get("product_url") or "").strip()
        if url:
            lines.append(f"• {name} — {url}")
        else:
            lines.append(f"• {name}")
    return "\n".join(lines)


def _reply_problem_guide(
    registry: Any,
    ctx: ToolContext,
    tools_used: List[str],
    tool_results: List[Dict[str, Any]],
    text: str,
) -> Optional[Tuple[str, str]]:
    """Return (reply, guide_id) or None."""
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

    found: List[Dict[str, Any]] = []
    search_url = ""
    for q in search_queries_for_guide(guide, max_queries=3):
        result = _search_products(registry, ctx, q, limit=2)
        tools_used.append("catalog.search_products")
        tool_results.append({"tool": "catalog.search_products", "result": result})
        found.extend(result.get("products") or [])
        if not search_url:
            search_url = result.get("search_url") or ""

    product_block = format_product_lines(found, limit=6)
    if product_block:
        parts.append("\nAlgunos productos de nuestro catálogo que pueden servir:")
        parts.append(product_block)
    if search_url:
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
    return "\n".join(parts), guide.id


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
    product_block = format_product_lines(products, limit=6)

    parts = [
        f"Para «{topic}» te oriento con productos por nombre "
        f"(sin códigos internos):",
    ]
    if product_block:
        parts.append(product_block)
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
    product_block = format_product_lines(products, limit=5)

    if product_block:
        reply = (
            f"Encontré estos productos relacionados con «{product_q}»:\n"
            + product_block
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


def run_stub_turn(req: ChatRequest) -> ChatResponse:
    """Deterministic tool-routing for public/customer audiences.

    Sets ``llm_eligible=True`` only on generic help (hybrid may escalate).
    """
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

    # Greeting-only: friendly help, no platform.health noise
    if is_greeting_only(text):
        return ChatResponse(
            reply="¡Hola! " + _HELP_REPLY,
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

    # Cart / online payment (before product extract — "carro" ≠ product)
    if is_cart_pay_intent(text):
        return ChatResponse(
            reply=_CART_REPLY,
            session_id=session_id,
            mode="stub_tools",
        )

    # Problem / project first (customer language)
    if looks_like_problem(text) or match_guide(text):
        guided = _reply_problem_guide(registry, ctx, tools_used, tool_results, text)
        if guided:
            guide_reply, guide_id = guided
            return ChatResponse(
                reply=guide_reply,
                session_id=session_id,
                tools_used=tools_used,
                tool_results=tool_results,
                guide_id=guide_id,
            )
        topic = extract_problem_topic(text)
        if topic:
            reply = _reply_problem_topic(registry, ctx, tools_used, tool_results, topic)
            return ChatResponse(
                reply=reply,
                session_id=session_id,
                tools_used=tools_used,
                tool_results=tool_results,
                product_query=topic,
            )

    # Product name search: "tienen cemento?", "busco varilla", "cotizar un tanque"
    product_q = extract_product_query(text)
    if product_q:
        # If the product phrase is itself a problem phrase, prefer guide
        if match_guide(product_q) or looks_like_problem(product_q):
            guided = _reply_problem_guide(
                registry, ctx, tools_used, tool_results, product_q
            )
            if guided:
                guide_reply, guide_id = guided
                return ChatResponse(
                    reply=guide_reply,
                    session_id=session_id,
                    tools_used=tools_used,
                    tool_results=tool_results,
                    guide_id=guide_id,
                    product_query=product_q,
                )
        # Full message may match a guide even when extract is a product noun
        if match_guide(text):
            guided = _reply_problem_guide(registry, ctx, tools_used, tool_results, text)
            if guided:
                guide_reply, guide_id = guided
                return ChatResponse(
                    reply=guide_reply,
                    session_id=session_id,
                    tools_used=tools_used,
                    tool_results=tool_results,
                    guide_id=guide_id,
                    product_query=product_q,
                )
        reply = _reply_product_name_search(
            registry, ctx, tools_used, tool_results, product_q
        )
        return ChatResponse(
            reply=reply,
            session_id=session_id,
            tools_used=tools_used,
            tool_results=tool_results,
            product_query=product_q,
        )

    # Problem topic free-text (no curated guide)
    topic = extract_problem_topic(text)
    if topic:
        reply = _reply_problem_topic(registry, ctx, tools_used, tool_results, topic)
        return ChatResponse(
            reply=reply,
            session_id=session_id,
            tools_used=tools_used,
            tool_results=tool_results,
            product_query=topic,
        )

    # Bare product name / model / industrial phrase fallthrough
    bare_q = bare_product_query(text)
    if bare_q:
        if match_guide(bare_q) or match_guide(text):
            guided = _reply_problem_guide(
                registry,
                ctx,
                tools_used,
                tool_results,
                text if match_guide(text) else bare_q,
            )
            if guided:
                guide_reply, guide_id = guided
                return ChatResponse(
                    reply=guide_reply,
                    session_id=session_id,
                    tools_used=tools_used,
                    tool_results=tool_results,
                    guide_id=guide_id,
                    product_query=bare_q,
                )
        reply = _reply_product_name_search(
            registry, ctx, tools_used, tool_results, bare_q
        )
        return ChatResponse(
            reply=reply,
            session_id=session_id,
            tools_used=tools_used,
            tool_results=tool_results,
            product_query=bare_q,
        )

    # Default help — LLM-eligible (hybrid may escalate)
    return ChatResponse(
        reply=_HELP_REPLY,
        session_id=session_id,
        mode="stub_tools",
        llm_eligible=True,
    )


def run_assistant_turn(req: ChatRequest) -> ChatResponse:
    """Hybrid: deterministic stub first; LLM tools only on generic-help fallback."""
    stub = run_stub_turn(req)
    if not stub.llm_eligible:
        return stub

    from modules.assistant import llm_router

    if not llm_router.llm_enabled():
        return stub

    registry = get_default_registry()
    llm_out = llm_router.run_llm_turn(
        message=(req.message or "").strip(),
        session_id=stub.session_id,
        audience=req.audience,
        registry=registry,
        locale=req.locale,
    )
    if not llm_out:
        return stub

    reply, tools_used, tool_results = llm_out
    if not reply:
        return stub

    return ChatResponse(
        reply=reply,
        session_id=stub.session_id,
        tools_used=tools_used,
        tool_results=tool_results,
        grounded=True,
        mode="llm_tools",
        llm_eligible=False,
    )
