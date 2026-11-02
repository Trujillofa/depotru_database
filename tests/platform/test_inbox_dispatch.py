"""Shipping slice B — dispatch policy and the system agent that applies it.

The model: a consolidated trip leaves when the load reaches the threshold or
when the oldest waiting order has waited too long; an order that alone fills a
truck leaves at once on a dedicated trip. An order no vehicle at that site can
carry is BLOCKED and reported — it never rides on a truck it would overload and
it never blocks the orders behind it.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from modules.inbox.dispatch import (
    REASON_DEDICATED,
    REASON_MAX_WAIT,
    REASON_THRESHOLD,
    DispatchPolicy,
    Vehicle,
    plan_dispatch,
)
from modules.inbox.repository import InMemoryInboxRepository
from modules.inbox.service import InboxService

NOW = datetime(2026, 11, 2, 8, 0, 0)

VEHICLES = (
    Vehicle(plate="TRK-01", capacity_kg=8000, site="florencia"),
    Vehicle(plate="TRK-02", capacity_kg=3000, site="florencia"),
    Vehicle(plate="TRK-09", capacity_kg=8000, site="neiva"),
)

POLICY = DispatchPolicy(threshold_kg=6000, max_wait_hours=24)


def order(order_id, weight, *, site="florencia", hours_ago=1, city="Florencia"):
    return {
        "magento_order_id": order_id,
        "weight_kg": str(weight),
        "dest_city": city,
        "dest_department": "Caquetá",
        "site": site,
        "placed_at": (NOW - timedelta(hours=hours_ago)).isoformat(),
    }


def inbox(*orders):
    svc = InboxService(InMemoryInboxRepository())
    for item in orders:
        svc.ingest(item)
    return svc


def test_below_threshold_and_young_creates_no_trip():
    svc = inbox(order("A", 1000, hours_ago=2))

    plan = plan_dispatch(svc.pending(), VEHICLES, NOW, POLICY)

    assert plan.trips == ()


def test_reaching_the_threshold_creates_one_trip_with_the_smallest_fitting_vehicle():
    svc = inbox(order("A", 3000, hours_ago=3), order("B", 3200, hours_ago=2))

    plan = plan_dispatch(svc.pending(), VEHICLES, NOW, POLICY)

    assert len(plan.trips) == 1
    trip = plan.trips[0]
    assert trip.reason == REASON_THRESHOLD
    assert trip.vehicle_plate == "TRK-01"  # 6200 kg does not fit TRK-02
    assert trip.total_weight_kg == 6200
    assert trip.order_ids == ("A", "B")


def test_oldest_order_past_max_wait_leaves_even_below_threshold():
    svc = inbox(order("A", 500, hours_ago=30), order("B", 500, hours_ago=1))

    plan = plan_dispatch(svc.pending(), VEHICLES, NOW, POLICY)

    assert len(plan.trips) == 1
    assert plan.trips[0].reason == REASON_MAX_WAIT
    # FIFO: the oldest order leaves, the young one keeps waiting.
    assert plan.trips[0].order_ids == ("A",)


def test_one_order_over_the_threshold_gets_a_dedicated_trip():
    svc = inbox(order("BIG", 7000, hours_ago=1), order("SMALL", 100, hours_ago=1))

    plan = plan_dispatch(svc.pending(), VEHICLES, NOW, POLICY)

    assert [t.reason for t in plan.trips] == [REASON_DEDICATED]
    assert plan.trips[0].order_ids == ("BIG",)
    assert plan.trips[0].vehicle_plate == "TRK-01"


def test_order_heavier_than_every_vehicle_is_blocked_and_does_not_stop_the_rest():
    svc = inbox(order("HUGE", 9000, hours_ago=1), order("A", 6000, hours_ago=1))

    plan = plan_dispatch(svc.pending(), VEHICLES, NOW, POLICY)

    assert [b.order_id for b in plan.blocked] == ["HUGE"]
    assert "capacidad" in plan.blocked[0].reason
    assert len(plan.trips) == 1
    assert plan.trips[0].order_ids == ("A",)


def test_sites_never_share_a_truck():
    svc = inbox(order("F1", 3000, site="florencia"), order("N1", 3000, site="neiva"))

    plan = plan_dispatch(svc.pending(), VEHICLES, NOW, POLICY)

    assert plan.trips == ()


def test_dispatch_is_deterministic():
    svc = inbox(order("A", 3000, hours_ago=3), order("B", 3200, hours_ago=2))

    first = plan_dispatch(svc.pending(), VEHICLES, NOW, POLICY)
    second = plan_dispatch(svc.pending(), VEHICLES, NOW, POLICY)

    assert first == second


def test_vehicle_capacity_is_never_exceeded():
    svc = inbox(
        order("A", 2000, hours_ago=5),
        order("B", 2000, hours_ago=4),
        order("C", 2000, hours_ago=3),
        order("D", 2000, hours_ago=2),
    )

    plan = plan_dispatch(svc.pending(), VEHICLES, NOW, POLICY)

    capacities = {v.plate: v.capacity_kg for v in VEHICLES}
    for trip in plan.trips:
        assert trip.total_weight_kg <= capacities[trip.vehicle_plate]


def test_system_agent_turns_a_plan_into_trips_once():
    svc = inbox(order("A", 3000, hours_ago=3), order("B", 3200, hours_ago=2))

    report = svc.run_dispatch(VEHICLES, NOW, POLICY)

    assert report.trips_created == 1
    assert report.orders_assigned == 2
    assert report.created_by == "system:dispatch"
    assert svc.pending() == []
    assert [t.state for t in svc.trips()] == ["planned"]

    again = svc.run_dispatch(VEHICLES, NOW, POLICY)
    assert again.trips_created == 0
    assert len(svc.trips()) == 1


def test_blocked_orders_stay_pending_and_visible():
    svc = inbox(order("HUGE", 9000, hours_ago=1))

    report = svc.run_dispatch(VEHICLES, NOW, POLICY)

    assert report.blocked_order_ids == ("HUGE",)
    assert [e.magento_order_id for e in svc.pending()] == ["HUGE"]
