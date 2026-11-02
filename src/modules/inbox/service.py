"""Inbox service: ingest orders, and let the system agent plan the trucks.

``run_dispatch`` is the system agent from the shipping model. It is the only
writer of trips, it signs everything with ``SYSTEM_AGENT``, and it plans from a
pure function so the same snapshot always yields the same trucks.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from modules.inbox.contracts import OrderInboxEntry
from modules.inbox.dispatch import DispatchPlan, DispatchPolicy, Vehicle, plan_dispatch
from modules.inbox.repository import TRIP_STATE_PLANNED, InboxRepository, Trip

SYSTEM_AGENT = "system:dispatch"


@dataclass(frozen=True)
class DispatchReport:
    trips_created: int
    orders_assigned: int
    blocked_order_ids: tuple[str, ...]
    created_by: str


class InboxService:
    def __init__(self, repository: InboxRepository) -> None:
        self.repository = repository

    def ingest(self, payload: object) -> OrderInboxEntry:
        """Validate and store one Magento order; a replay is a no-op."""
        from modules.inbox.contracts import build_entry

        entry = build_entry(payload)

        return self.repository.upsert(entry)

    def pending(self, site: Optional[str] = None) -> list[OrderInboxEntry]:
        entries: list[OrderInboxEntry] = self.repository.pending(site)
        return entries

    def all_orders(self) -> list[OrderInboxEntry]:
        entries: list[OrderInboxEntry] = self.repository.all_orders()
        return entries

    def trips(self) -> list[Trip]:
        trips: list[Trip] = self.repository.trips()
        return trips

    def plan(
        self,
        vehicles: Sequence[Vehicle],
        now: datetime,
        policy: DispatchPolicy,
    ) -> DispatchPlan:
        return plan_dispatch(self.pending(), vehicles, now, policy)

    def run_dispatch(
        self,
        vehicles: Sequence[Vehicle],
        now: datetime,
        policy: DispatchPolicy,
    ) -> DispatchReport:
        plan = self.plan(vehicles, now, policy)
        existing = len(self.repository.trips())
        assigned = 0

        for offset, planned in enumerate(plan.trips, start=1):
            trip_id = f"TRIP-{planned.site.upper()}-{existing + offset:04d}"
            self.repository.add_trip(
                Trip(
                    trip_id=trip_id,
                    vehicle_plate=planned.vehicle_plate,
                    site=planned.site,
                    order_ids=planned.order_ids,
                    total_weight_kg=planned.total_weight_kg,
                    reason=planned.reason,
                    state=TRIP_STATE_PLANNED,
                    created_by=SYSTEM_AGENT,
                    created_at=now,
                )
            )
            assigned += self.repository.assign(planned.order_ids, trip_id)

        return DispatchReport(
            trips_created=len(plan.trips),
            orders_assigned=assigned,
            blocked_order_ids=tuple(b.order_id for b in plan.blocked),
            created_by=SYSTEM_AGENT,
        )
