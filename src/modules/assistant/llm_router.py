"""LLM tool-calling for storefront assistant (hybrid fallback path).

Only used when the deterministic stub would return generic help.
Tools execute exclusively through the platform registry with public audience.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from depotru_kernel.auth import Audience
from depotru_tools.registry import (
    ToolContext,
    ToolNotFoundError,
    ToolPermissionError,
    ToolRegistry,
)

logger = logging.getLogger(__name__)

# v1 allowlist — never expose SKU-affinity, health noise, or stock invent risk
_LLM_TOOL_ALLOWLIST = frozenset(
    {
        "info.branches",
        "catalog.search_products",
    }
)

_DEFAULT_MODEL = "grok-4-1-fast-non-reasoning"
_GROK_BASE_URL = "https://api.x.ai/v1"
_MAX_ROUNDS = 3
_TIMEOUT_SEC = 25.0

_SYSTEM_PROMPT = """Eres el asistente de Depósito Trujillo (ferretería y materiales, Neiva, Colombia).

Reglas:
- Responde en español colombiano, breve y claro.
- Usa SOLO las herramientas disponibles para datos de sedes/bodegas o productos del catálogo.
- Si preguntan por sedes, bodegas, dirección o horarios, llama info.branches y repite
  dirección, horario, teléfono/WhatsApp y enlace de mapa de cada punto (no resumas a solo el nombre).
- NUNCA inventes precios, stock, costos, direcciones ni datos de terceros.
- NUNCA muestres códigos SKU ni códigos internos ERP (FED/FEF/FET) al cliente.
- Si no hay resultados de herramientas, dilo y sugiere reformular o visitar una sede.
- Para trabajos de casa (gotera, pintar, plomería) sugiere materiales útiles y ofrece buscar por nombre.
- No digas que eres un modelo de IA genérico; eres el asistente de la tienda.
"""

_SKU_LINE_RE = re.compile(r"(?i)\bsku\b\s*[:=]?\s*\S+")


def llm_enabled() -> bool:
    """True when ASSISTANT_LLM is on and a Grok/xAI key is present."""
    flag = (os.getenv("ASSISTANT_LLM") or "").strip().lower()
    if flag not in ("1", "true", "yes", "on"):
        return False
    key = (os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY") or "").strip()
    return bool(key) and not key.startswith("your-")


def _api_key() -> str:
    return (os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY") or "").strip()


def _model_name() -> str:
    return (
        os.getenv("ASSISTANT_LLM_MODEL") or _DEFAULT_MODEL
    ).strip() or _DEFAULT_MODEL


def tools_for_llm(registry: ToolRegistry, audience: Audience) -> List[Dict[str, Any]]:
    """OpenAI-compatible tool definitions from the registry (allowlisted)."""
    out: List[Dict[str, Any]] = []
    for item in registry.list_tools(audience=audience):
        name = item.get("name") or ""
        if name not in _LLM_TOOL_ALLOWLIST:
            continue
        props: Dict[str, Any] = {}
        required: List[str] = []
        raw_params = item.get("parameters") or {}
        if isinstance(raw_params, Mapping):
            for pname, pdesc in raw_params.items():
                if pname == "limit":
                    props[pname] = {
                        "type": "integer",
                        "description": str(pdesc),
                    }
                else:
                    props[pname] = {
                        "type": "string",
                        "description": str(pdesc),
                    }
                if pname in ("query",):
                    required.append(pname)
        parameters: Dict[str, Any] = {
            "type": "object",
            "properties": props,
            "additionalProperties": False,
        }
        if required:
            parameters["required"] = required
        out.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": item.get("description") or name,
                    "parameters": parameters,
                },
            }
        )
    return out


def sanitize_customer_reply(text: str) -> str:
    """Drop accidental SKU mentions from model text."""
    lines = []
    for line in (text or "").splitlines():
        if _SKU_LINE_RE.search(line) and "sku" in line.lower():
            cleaned = _SKU_LINE_RE.sub("", line).strip(" -–—:\t")
            if cleaned:
                lines.append(cleaned)
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _parse_tool_args(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _execute_tool(
    registry: ToolRegistry,
    ctx: ToolContext,
    name: str,
    params: Mapping[str, Any],
) -> Tuple[Any, Optional[str]]:
    """Return (result, error_message)."""
    if name not in _LLM_TOOL_ALLOWLIST:
        return None, f"Tool not allowed: {name}"
    try:
        result = registry.call(name, params, context=ctx)
        return result, None
    except ToolNotFoundError:
        return None, f"Unknown tool: {name}"
    except ToolPermissionError as exc:
        return None, str(exc)
    except Exception as exc:  # noqa: BLE001 — surface to model, never crash chat
        logger.warning("assistant LLM tool %s failed: %s", name, exc)
        return None, f"Tool error: {exc}"


def run_llm_turn(
    *,
    message: str,
    session_id: str,
    audience: Audience,
    registry: ToolRegistry,
    locale: str = "es_CO",
) -> Optional[Tuple[str, List[str], List[Dict[str, Any]]]]:
    """Run OpenAI-compatible tool loop.

    Returns (reply, tools_used, tool_results) or None on failure / disabled.
    """
    if not llm_enabled():
        return None

    tools = tools_for_llm(registry, audience)
    if not tools:
        return None

    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai package missing; assistant LLM disabled")
        return None

    try:
        client = OpenAI(
            api_key=_api_key(),
            base_url=_GROK_BASE_URL,
            timeout=_TIMEOUT_SEC,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("assistant LLM client init failed: %s", exc)
        return None

    ctx = ToolContext(audience=audience, request_id=session_id)
    tools_used: List[str] = []
    tool_results: List[Dict[str, Any]] = []

    # OpenAI SDK message types are overly strict for dynamic tool loops
    messages: List[Any] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"(locale={locale}) {message}",
        },
    ]
    tools_param: Any = tools

    try:
        for _round in range(_MAX_ROUNDS):
            response = client.chat.completions.create(
                model=_model_name(),
                messages=messages,
                tools=tools_param,
                tool_choice="auto",
                temperature=0.3,
            )
            choice = response.choices[0]
            msg = choice.message
            raw_calls = list(msg.tool_calls or [])

            if not raw_calls:
                content = (msg.content or "").strip()
                if not content:
                    return None
                return sanitize_customer_reply(content), tools_used, tool_results

            # Append assistant message with tool_calls for the API protocol
            tc_payloads = []
            for tc in raw_calls:
                fn = getattr(tc, "function", None)
                if fn is None:
                    continue
                tc_payloads.append(
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": getattr(fn, "name", "") or "",
                            "arguments": getattr(fn, "arguments", None) or "{}",
                        },
                    }
                )
            if not tc_payloads:
                content = (msg.content or "").strip()
                if not content:
                    return None
                return sanitize_customer_reply(content), tools_used, tool_results

            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content or None,
                    "tool_calls": tc_payloads,
                }
            )

            for tc_p in tc_payloads:
                fn = tc_p["function"]
                name = fn.get("name") or ""
                params = _parse_tool_args(fn.get("arguments"))
                result, err = _execute_tool(registry, ctx, name, params)
                tools_used.append(name)
                payload = {"error": err} if err else {"result": _jsonable(result)}
                tool_results.append({"tool": name, "result": payload})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc_p["id"],
                        "content": json.dumps(payload, ensure_ascii=False, default=str)[
                            :8000
                        ],
                    }
                )

        # Final round without tools if we exhausted tool rounds
        response = client.chat.completions.create(
            model=_model_name(),
            messages=messages,
            temperature=0.3,
        )
        content = (response.choices[0].message.content or "").strip()
        if not content:
            return None
        return sanitize_customer_reply(content), tools_used, tool_results
    except Exception as exc:  # noqa: BLE001
        logger.warning("assistant LLM turn failed: %s", exc)
        return None


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_jsonable(v) for v in value]
    return str(value)
