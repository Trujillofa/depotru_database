"""Storefront / multi-channel AI assistant (tool-calling, grounded answers)."""

from modules.assistant.chat import ChatRequest, ChatResponse, run_assistant_turn

MODULE_NAME = "assistant"

__all__ = ["ChatRequest", "ChatResponse", "MODULE_NAME", "run_assistant_turn"]
