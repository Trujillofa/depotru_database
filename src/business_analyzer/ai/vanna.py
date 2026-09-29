"""Composed AIVanna class (provider + routing + SQL runtime + summaries).

Mixin order is load-bearing:
- LLMMixin first so ``AIVanna()`` uses our ``__init__``
- SqlRuntimeMixin before Vanna parents so ``super().generate_sql`` works
- ChromaDB_VectorStore / OpenAI_Chat last (same parents as before)
"""

from __future__ import annotations

from vanna.legacy.chromadb.chromadb_vector import ChromaDB_VectorStore
from vanna.legacy.openai import OpenAI_Chat

from .llm import LLMMixin
from .manager_report_routing import ManagerReportMixin
from .sql_routing import SqlRoutingMixin
from .sql_runtime import SqlRuntimeMixin
from .summaries import SummaryMixin


class AIVanna(
    LLMMixin,
    SqlRuntimeMixin,
    SqlRoutingMixin,
    ManagerReportMixin,
    SummaryMixin,
    ChromaDB_VectorStore,
    OpenAI_Chat,
):
    """
    Multi-provider Vanna AI class supporting Grok, OpenAI, DeepSeek, Anthropic,
    and Ollama.

    Provider selection via AI_PROVIDER environment variable:
    - grok (default): xAI Grok
    - openai: OpenAI GPT-4
    - deepseek: DeepSeek's OpenAI-compatible API
    - anthropic: Anthropic Claude
    - ollama: Local Ollama instance
    """


def _bind_composed_aivanna(cls=AIVanna) -> None:
    """Let mixin modules keep historical ``AIVanna._foo()`` lookups."""
    from . import manager_report_routing, sql_routing, sql_runtime, summaries

    sql_routing.AIVanna = cls
    sql_runtime.AIVanna = cls
    manager_report_routing.AIVanna = cls
    summaries.AIVanna = cls


_bind_composed_aivanna()
