"""Assistant BFF core — Phase 0 stub (no free-form LLM yet).

Public turns are answered via tool registry only so Magento can integrate
before full tool-calling LLM is wired.
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
    r"\b(sede|sucursal|horario|ubicaci[oó]n|d[oó]nde est[aá]n)\b",
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


def run_assistant_turn(req: ChatRequest) -> ChatResponse:
    """Deterministic tool-routing stub for public/customer audiences.

    Full LLM tool-calling lands later; this proves BFF + registry wiring.
    """
    session_id = req.session_id or str(uuid.uuid4())
    registry = get_default_registry()
    ctx = ToolContext(audience=req.audience, request_id=session_id)
    tools_used: List[str] = []
    tool_results: List[Dict[str, Any]] = []
    text = (req.message or "").strip()

    if not text:
        return ChatResponse(
            reply="¿En qué puedo ayudarte? Puedo indicar sedes, stock (cuando esté configurado) o productos relacionados.",
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

    # Stock
    if sku and _STOCK_RE.search(text):
        result = registry.call("inventory.sellable_qty", {"sku": sku}, context=ctx)
        tools_used.append("inventory.sellable_qty")
        tool_results.append({"tool": "inventory.sellable_qty", "result": result})
        if result.get("status") == "unavailable":
            reply = (
                f"Aún no puedo consultar existencias en vivo del SKU {sku} "
                f"(adaptador Magento no configurado). "
                f"Cuando esté activo, responderé con cantidad vendible (MSI − stock de seguridad)."
            )
        else:
            qty = result.get("sellable_qty")
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

    # Related
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
                f"No hay candidatos de afinidad cargados en esta sesión para {sku}. "
                f"Use el export de afinidad → Magento para poblar links."
            )
        return ChatResponse(
            reply=reply,
            session_id=session_id,
            tools_used=tools_used,
            tool_results=tool_results,
        )

    # Health / default help
    health = registry.call("platform.health", {}, context=ctx)
    tools_used.append("platform.health")
    tool_results.append({"tool": "platform.health", "result": health})
    reply = (
        "Soy el asistente de Depósito Trujillo (modo herramientas). "
        "Prueba: «¿dónde están las sedes?», «stock del SKU 1234567890», "
        "o «productos relacionados al SKU …». "
        "No invento precios de costo ni carteras de terceros."
    )
    return ChatResponse(
        reply=reply,
        session_id=session_id,
        tools_used=tools_used,
        tool_results=tool_results,
    )
