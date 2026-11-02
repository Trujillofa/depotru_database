"""Order inbox contracts: entries, states, and the validation rules.

One validator, used by the ingest path and by anything that replays a backlog.
A weight that is missing, zero, negative or absurd is an ERROR: the truck is
planned from this number, so guessing it moves freight nobody will pay for.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

STATUS_PENDING = "pending"
STATUS_ASSIGNED = "assigned"
STATUS_DISPATCHED = "dispatched"
STATUS_CANCELLED = "cancelled"

# Sites v1 (R9): Neiva and Florencia only.
SITES = ("neiva", "florencia")

# A single order above this is not a delivery, it is a data error.
MAX_ORDER_WEIGHT_KG = Decimal("40000")

_ORDER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class InboxError(RuntimeError):
    """Base class for inbox failures."""


class InboxValidationError(InboxError):
    """The order cannot be accepted as given. Nothing was stored."""


class DuplicateOrderConflict(InboxError):
    """The same Magento order arrived with a different payload."""


@dataclass(frozen=True)
class OrderInboxEntry:
    """One Magento order, as the dispatcher sees it."""

    magento_order_id: str
    weight_kg: Decimal
    dest_city: str
    dest_department: str
    site: str
    placed_at: datetime
    status: str = STATUS_PENDING
    trip_id: Optional[str] = None


def parse_weight(value: object) -> Decimal:
    """Fixed-point kilograms, or a refusal. Never a float in the result."""
    if isinstance(value, bool) or value is None:
        raise InboxValidationError("peso requerido: la orden no trae peso en kg")

    text = str(value).strip().replace(",", ".")
    if not text:
        raise InboxValidationError("peso requerido: la orden no trae peso en kg")

    try:
        weight = Decimal(text)
    except (InvalidOperation, ValueError):
        raise InboxValidationError(f"peso inválido: {value!r} no es un número en kg")

    if not weight.is_finite():
        raise InboxValidationError(f"peso inválido: {value!r} no es un número finito")
    if weight <= 0:
        raise InboxValidationError("peso inválido: debe ser mayor que cero")
    if weight > MAX_ORDER_WEIGHT_KG:
        raise InboxValidationError(
            f"peso fuera de rango: {weight} kg supera el máximo de una orden "
            f"({MAX_ORDER_WEIGHT_KG} kg)"
        )

    return weight


def parse_placed_at(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.strip())
        except ValueError:
            raise InboxValidationError(f"fecha inválida: {value!r}")
    raise InboxValidationError("fecha requerida: la orden no trae placed_at")


def parse_order_id(value: object) -> str:
    order_id = str(value or "").strip()
    if not order_id:
        raise InboxValidationError("id de pedido requerido: falta el número de Magento")
    if not _ORDER_ID_RE.match(order_id):
        raise InboxValidationError(f"id de pedido inválido: {order_id!r}")
    return order_id


def parse_site(value: object) -> str:
    site = str(value or "").strip().lower()
    if site not in SITES:
        raise InboxValidationError(
            f"sede desconocida: {value!r} (válidas: {', '.join(SITES)})"
        )
    return site


def build_entry(payload: object) -> OrderInboxEntry:
    """Validate a raw payload into an entry, refusing anything ambiguous."""
    if not isinstance(payload, dict):
        raise InboxValidationError("la orden debe venir como objeto")

    city = str(payload.get("dest_city") or "").strip()
    if not city:
        raise InboxValidationError("ciudad de destino requerida")

    return OrderInboxEntry(
        magento_order_id=parse_order_id(payload.get("magento_order_id")),
        weight_kg=parse_weight(payload.get("weight_kg")),
        dest_city=city,
        dest_department=str(payload.get("dest_department") or "").strip(),
        site=parse_site(payload.get("site")),
        placed_at=parse_placed_at(payload.get("placed_at")),
    )
