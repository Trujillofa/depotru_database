"""Platform API v1 — tools, assistant, health.

Mounted alongside legacy ``/analyze`` routes in ``api.py``.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from depotru_kernel.auth import Audience
from depotru_tools.registry import (
    ToolContext,
    ToolNotFoundError,
    ToolPermissionError,
    get_default_registry,
)
from modules.assistant.chat import ChatRequest, run_assistant_turn

router = APIRouter(prefix="/v1", tags=["platform-v1"])


def _parse_audience(raw: Optional[str]) -> Audience:
    if not raw:
        return Audience.SERVICE
    try:
        return Audience(raw.strip().lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid audience: {raw}",
        )


def require_scoped_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_audience: Optional[str] = Header(None, alias="X-Audience"),
) -> Audience:
    """Auth: optional API_KEY; audience from header (default service).

    When API_KEY is set, header must match. When PLATFORM_API_KEYS is set as
    ``key:audience,key2:audience2``, map key → audience (overrides X-Audience).
    """
    multi = (os.getenv("PLATFORM_API_KEYS") or "").strip()
    if multi:
        mapping: Dict[str, str] = {}
        for part in multi.split(","):
            part = part.strip()
            if not part or ":" not in part:
                continue
            k, aud = part.split(":", 1)
            mapping[k.strip()] = aud.strip()
        if not x_api_key or x_api_key not in mapping:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API key",
            )
        return _parse_audience(mapping[x_api_key])

    expected = (os.getenv("API_KEY") or "").strip()
    if expected:
        if not x_api_key or x_api_key != expected:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API key",
            )
    return _parse_audience(x_audience)


class ToolCallBody(BaseModel):
    name: str
    params: Dict[str, Any] = Field(default_factory=dict)


class ToolCallResponse(BaseModel):
    name: str
    result: Any
    audience: str


class AssistantChatBody(BaseModel):
    message: str
    session_id: Optional[str] = None
    locale: str = "es_CO"


class AssistantChatResponse(BaseModel):
    reply: str
    session_id: str
    tools_used: List[str]
    grounded: bool
    mode: str


@router.get("/health")
async def v1_health(audience: Audience = Depends(require_scoped_api_key)):
    reg = get_default_registry()
    result = reg.call(
        "platform.health",
        {},
        context=ToolContext(audience=audience),
    )
    return {"status": "ok", "audience": audience.value, "detail": result}


@router.get("/tools")
async def list_tools(audience: Audience = Depends(require_scoped_api_key)):
    reg = get_default_registry()
    return {
        "audience": audience.value,
        "tools": reg.list_tools(audience=audience),
    }


@router.post("/tools/call", response_model=ToolCallResponse)
async def call_tool(
    body: ToolCallBody,
    audience: Audience = Depends(require_scoped_api_key),
):
    reg = get_default_registry()
    ctx = ToolContext(audience=audience)
    try:
        result = reg.call(body.name, body.params, context=ctx)
    except ToolNotFoundError:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {body.name}")
    except ToolPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return ToolCallResponse(name=body.name, result=result, audience=audience.value)


@router.post("/assistant/chat", response_model=AssistantChatResponse)
async def assistant_chat(
    body: AssistantChatBody,
    audience: Audience = Depends(require_scoped_api_key),
):
    # Clamp elevated keys: if service/admin call chat, allow; public via key map.
    chat_audience = audience
    if audience in (Audience.SERVICE, Audience.ADMIN, Audience.AGENT):
        # Service accounts may simulate public for storefront proxy testing
        chat_audience = Audience.PUBLIC

    resp = run_assistant_turn(
        ChatRequest(
            message=body.message,
            audience=chat_audience,
            session_id=body.session_id,
            locale=body.locale,
        )
    )
    return AssistantChatResponse(
        reply=resp.reply,
        session_id=resp.session_id,
        tools_used=resp.tools_used,
        grounded=resp.grounded,
        mode=resp.mode,
    )


@router.get("/affinity/contract")
async def affinity_contract(audience: Audience = Depends(require_scoped_api_key)):
    from depotru_integrations.affinity.contract import (
        AFFINITY_CONTRACT_VERSION,
        CROSSSELL_CSV_COLUMNS,
        CROSSSELL_POLICY,
        MANIFEST_SCHEMA,
        RELATED_POLICY,
        related_csv_columns,
    )

    return {
        "contract_version": AFFINITY_CONTRACT_VERSION,
        "related_policy": RELATED_POLICY,
        "crosssell_policy": CROSSSELL_POLICY,
        "related_columns": related_csv_columns(),
        "crosssell_columns": list(CROSSSELL_CSV_COLUMNS),
        "manifest": MANIFEST_SCHEMA,
        "audience": audience.value,
    }
