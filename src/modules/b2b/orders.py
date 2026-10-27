"""Task 10 — idempotent order adapter contract (interface + fake).

R15: automatic ERP submission is **blocked** — no Magento→ERP order write
and no direct SQL writes. What ships here is the contract only:

- same key + same payload → same ERP ID (idempotent replay)
- same key + different payload → reject (``IdempotencyConflictError``)
- timeout → ``unknown`` state; retry/lookup queries by key first; a vendor
  lookup reconciles ``unknown`` → ``submitted``
- the real adapter (``J3OrderAdapter``) raises ``OrderSubmitDisabled`` until
  a Task 5 approved API exists
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Protocol

STATE_SUBMITTED = "submitted"
STATE_UNKNOWN = "unknown"


class IdempotencyConflictError(RuntimeError):
    """Same idempotency key reused with a different payload."""


class OrderSubmitDisabled(RuntimeError):
    """R15: real ERP submission is not enabled."""


@dataclass(frozen=True)
class OrderSubmitResult:
    order_key: str
    state: str  # STATE_SUBMITTED | STATE_UNKNOWN
    erp_order_id: Optional[str]

    def with_state(
        self, state: str, erp_order_id: Optional[str] = None
    ) -> "OrderSubmitResult":
        return OrderSubmitResult(self.order_key, state, erp_order_id)


def canonical_payload(payload: Mapping[str, Any]) -> str:
    """Stable JSON encoding so payload comparison never depends on key order."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


class OrderAdapter(Protocol):
    def submit(self, order_key: str, payload: Mapping[str, Any]) -> OrderSubmitResult:
        ...  # pragma: no cover

    def lookup(self, order_key: str) -> Optional[OrderSubmitResult]:
        ...  # pragma: no cover


class FakeOrderAdapter:
    """In-memory reference implementation of the idempotency semantics."""

    def __init__(self, *, timeout_keys: Optional[set[str]] = None) -> None:
        self._results: dict[str, OrderSubmitResult] = {}
        self._payloads: dict[str, str] = {}
        self._timeout_keys = set(timeout_keys or ())
        self._counter = 0

    def submit(self, order_key: str, payload: Mapping[str, Any]) -> OrderSubmitResult:
        key = str(order_key or "").strip()
        if not key:
            raise ValueError("order_key is required")
        canon = hashlib.sha256(canonical_payload(payload).encode()).hexdigest()
        if key in self._payloads:
            if self._payloads[key] != canon:
                raise IdempotencyConflictError(
                    f"order_key {key!r} already used with a different payload"
                )
            return self._results[key]  # replay: same ERP ID, same state
        self._payloads[key] = canon
        if key in self._timeout_keys:
            result = OrderSubmitResult(key, STATE_UNKNOWN, None)
        else:
            self._counter += 1
            result = OrderSubmitResult(key, STATE_SUBMITTED, f"ERP-{self._counter:06d}")
        self._results[key] = result
        return result

    def lookup(self, order_key: str) -> Optional[OrderSubmitResult]:
        return self._results.get(str(order_key or "").strip())

    def reconcile(self, order_key: str, erp_order_id: str) -> OrderSubmitResult:
        """Vendor/ops lookup proof: unknown → submitted with the real ERP ID."""
        key = str(order_key or "").strip()
        current = self._results.get(key)
        if current is None:
            raise KeyError(order_key)
        reconciled = current.with_state(STATE_SUBMITTED, str(erp_order_id))
        self._results[key] = reconciled
        return reconciled


class J3OrderAdapter:
    """Real adapter — permanently disabled while R15 is blocked."""

    def submit(self, order_key: str, payload: Mapping[str, Any]) -> OrderSubmitResult:
        raise OrderSubmitDisabled("r15_blocked")

    def lookup(self, order_key: str) -> Optional[OrderSubmitResult]:
        raise OrderSubmitDisabled("r15_blocked")


def get_order_adapter() -> OrderAdapter:
    """Tool handlers get the real (disabled) adapter unless tests opt in."""
    mode = (os.getenv("B2B_ORDER_ADAPTER") or "").strip().lower()
    if mode == "fake":
        return FakeOrderAdapter()
    return J3OrderAdapter()
