"""Dispatch policy: when a truck leaves, and what rides on it.

The agreed model (shipping slice B): freight moves on consolidated trips that
leave when the load reaches the threshold, or when the oldest waiting order has
waited past the maximum. An order that alone fills a truck does not wait for
company. A vehicle is never overloaded: an order no vehicle at that site can
carry is blocked and reported, and the orders behind it still leave.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from modules.inbox.contracts import STATUS_PENDING, OrderInboxEntry

REASON_THRESHOLD = "threshold"
REASON_MAX_WAIT = "max_wait"
REASON_DEDICATED = "dedicated"

# Candidate values — sales/dispatch has to confirm them before the flag flips.
DEFAULT_THRESHOLD_KG = Decimal("6000")
DEFAULT_MAX_WAIT_HOURS = 24


@dataclass(frozen=True)
class Vehicle:
    plate: str
    capacity_kg: Decimal
    site: str
    active: bool = True


@dataclass(frozen=True)
class DispatchPolicy:
    threshold_kg: Decimal = DEFAULT_THRESHOLD_KG
    max_wait_hours: int = DEFAULT_MAX_WAIT_HOURS

    def waited_too_long(self, placed_at: datetime, now: datetime) -> bool:
        return now - placed_at >= timedelta(hours=self.max_wait_hours)


@dataclass(frozen=True)
class TripPlan:
    vehicle_plate: str
    site: str
    order_ids: tuple[str, ...]
    total_weight_kg: Decimal
    reason: str


@dataclass(frozen=True)
class BlockedOrder:
    order_id: str
    weight_kg: Decimal
    reason: str


@dataclass(frozen=True)
class DispatchPlan:
    trips: tuple[TripPlan, ...] = ()
    blocked: tuple[BlockedOrder, ...] = ()


def _trip_for(
    vehicle: Optional[Vehicle],
    site: str,
    orders: Sequence[OrderInboxEntry],
    reason: str,
) -> Optional[TripPlan]:
    if vehicle is None or not orders:
        return None
    total = Decimal("0")
    for entry in orders:
        total += entry.weight_kg
    return TripPlan(
        vehicle_plate=vehicle.plate,
        site=site,
        order_ids=tuple(entry.magento_order_id for entry in orders),
        total_weight_kg=total,
        reason=reason,
    )


def _smallest_fitting(
    vehicles: Sequence[Vehicle], weight: Decimal
) -> Optional[Vehicle]:
    """Smallest vehicle that carries the load, so the big truck stays free."""
    candidates = [v for v in vehicles if v.capacity_kg >= weight]
    if not candidates:
        return None

    return min(candidates, key=lambda v: (v.capacity_kg, v.plate))


def plan_dispatch(
    entries: Sequence[OrderInboxEntry],
    vehicles: Sequence[Vehicle],
    now: datetime,
    policy: DispatchPolicy,
) -> DispatchPlan:
    """Pure plan: same inputs, same plan. No I/O, no clock."""
    trips: list[TripPlan] = []
    blocked: list[BlockedOrder] = []

    pending = [e for e in entries if e.status == STATUS_PENDING]
    sites = sorted({e.site for e in pending})

    for site in sites:
        site_orders = sorted(
            (e for e in pending if e.site == site),
            key=lambda e: (e.placed_at, e.magento_order_id),
        )
        site_vehicles = [v for v in vehicles if v.active and v.site == site]

        if not site_vehicles:
            for entry in site_orders:
                blocked.append(
                    BlockedOrder(
                        entry.magento_order_id,
                        entry.weight_kg,
                        "no hay vehículo en la sede",
                    )
                )
            continue

        largest = max(v.capacity_kg for v in site_vehicles)
        batch: list[OrderInboxEntry] = []
        batch_weight = Decimal("0")

        for entry in site_orders:
            if entry.weight_kg > largest:
                blocked.append(
                    BlockedOrder(
                        entry.magento_order_id,
                        entry.weight_kg,
                        f"excede la capacidad del vehículo más grande ({largest} kg)",
                    )
                )
                continue

            if entry.weight_kg >= policy.threshold_kg:
                trip = _trip_for(
                    _smallest_fitting(site_vehicles, entry.weight_kg),
                    site,
                    [entry],
                    REASON_DEDICATED,
                )
                if trip is not None:
                    trips.append(trip)
                continue

            if batch_weight + entry.weight_kg > largest:
                trip = _trip_for(
                    _smallest_fitting(site_vehicles, batch_weight),
                    site,
                    batch,
                    REASON_THRESHOLD,
                )
                if trip is not None:
                    trips.append(trip)
                batch, batch_weight = [], Decimal("0")

            batch.append(entry)
            batch_weight += entry.weight_kg

            if batch_weight >= policy.threshold_kg:
                trip = _trip_for(
                    _smallest_fitting(site_vehicles, batch_weight),
                    site,
                    batch,
                    REASON_THRESHOLD,
                )
                if trip is not None:
                    trips.append(trip)
                batch, batch_weight = [], Decimal("0")

        if batch:
            # Only the orders that actually aged out leave; a young order keeps
            # waiting for a full truck instead of hitching a ride on a van.
            aged = [e for e in batch if policy.waited_too_long(e.placed_at, now)]
            if aged:
                trip = _trip_for(
                    _smallest_fitting(
                        site_vehicles, sum((e.weight_kg for e in aged), Decimal("0"))
                    ),
                    site,
                    aged,
                    REASON_MAX_WAIT,
                )
                if trip is not None:
                    trips.append(trip)

    return DispatchPlan(trips=tuple(trips), blocked=tuple(blocked))
