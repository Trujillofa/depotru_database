"""Inbox persistence contract, plus the in-memory adapter the tests use.

The protocol is deliberately small: the inbox is written by the Magento
consumer and read by dispatch, and neither of them should grow a dialect of
SQL of its own. The real adapter lands with the table migration; this one
encodes the same idempotency rules so a test that passes here describes the
production contract.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from typing import Optional, Protocol, Sequence

from modules.inbox.contracts import (
    STATUS_ASSIGNED,
    STATUS_PENDING,
    DuplicateOrderConflict,
    OrderInboxEntry,
)

TRIP_STATE_PLANNED = "planned"


@dataclass(frozen=True)
class Trip:
    trip_id: str
    vehicle_plate: str
    site: str
    order_ids: tuple[str, ...]
    total_weight_kg: Decimal
    reason: str
    state: str
    created_by: str
    created_at: datetime


class InboxRepository(Protocol):
    def get_order(self, magento_order_id: str) -> Optional[OrderInboxEntry]:
        ...  # pragma: no cover

    def upsert(self, entry: OrderInboxEntry) -> OrderInboxEntry:
        """Store the entry; a conflicting replay raises DuplicateOrderConflict."""
        ...  # pragma: no cover

    def all_orders(self) -> list[OrderInboxEntry]:
        ...  # pragma: no cover

    def pending(self, site: Optional[str] = None) -> list[OrderInboxEntry]:
        ...  # pragma: no cover

    def assign(self, order_ids: Sequence[str], trip_id: str) -> int:
        ...  # pragma: no cover

    def add_trip(self, trip: Trip) -> None:
        ...  # pragma: no cover

    def trips(self) -> list[Trip]:
        ...  # pragma: no cover


class InMemoryInboxRepository:
    """Reference implementation: dict-backed, same rules as the real one."""

    def __init__(self) -> None:
        self._orders: dict[str, OrderInboxEntry] = {}
        self._trips: dict[str, Trip] = {}

    def get_order(self, magento_order_id: str) -> Optional[OrderInboxEntry]:
        return self._orders.get(magento_order_id)

    def upsert(self, entry: OrderInboxEntry) -> OrderInboxEntry:
        current = self._orders.get(entry.magento_order_id)
        if current is None:
            self._orders[entry.magento_order_id] = entry
            return entry

        if _load_fingerprint(current) != _load_fingerprint(entry):
            raise DuplicateOrderConflict(
                f"la orden {entry.magento_order_id!r} ya existe con otro peso o destino"
            )

        return current

    def all_orders(self) -> list[OrderInboxEntry]:
        return sorted(
            self._orders.values(), key=lambda e: (e.placed_at, e.magento_order_id)
        )

    def pending(self, site: Optional[str] = None) -> list[OrderInboxEntry]:
        return [
            entry
            for entry in self.all_orders()
            if entry.status == STATUS_PENDING and (site is None or entry.site == site)
        ]

    def assign(self, order_ids: Sequence[str], trip_id: str) -> int:
        assigned = 0
        for order_id in order_ids:
            current = self._orders.get(order_id)
            if current is None or current.status != STATUS_PENDING:
                continue
            self._orders[order_id] = replace(
                current, status=STATUS_ASSIGNED, trip_id=trip_id
            )
            assigned += 1

        return assigned

    def add_trip(self, trip: Trip) -> None:
        self._trips[trip.trip_id] = trip

    def trips(self) -> list[Trip]:
        return sorted(self._trips.values(), key=lambda t: t.trip_id)


def _load_fingerprint(entry: OrderInboxEntry) -> tuple[object, ...]:
    """What dispatch plans from. Status is excluded: it changes, the load does not."""
    return (
        entry.weight_kg,
        entry.dest_city,
        entry.dest_department,
        entry.site,
        entry.placed_at,
    )
