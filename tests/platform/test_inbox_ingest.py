"""Shipping slice B — order inbox: fail-closed ingest, idempotent by Magento order.

The inbox is the only place a Magento order becomes a thing the dispatcher can
see. A wrong weight here becomes a wrong truck, so an order that does not carry
a positive weight and a destination is REFUSED and reported, never guessed at.
"""

from __future__ import annotations

import pytest

from modules.inbox.contracts import DuplicateOrderConflict, InboxValidationError
from modules.inbox.repository import InMemoryInboxRepository
from modules.inbox.service import InboxService


def payload(**overrides):
    base = {
        "magento_order_id": "000000417",
        "weight_kg": "1200.5",
        "dest_city": "Florencia",
        "dest_department": "Caquetá",
        "site": "florencia",
        "placed_at": "2026-11-01T09:30:00",
    }
    base.update(overrides)
    return base


@pytest.fixture()
def service():
    return InboxService(InMemoryInboxRepository())


def test_ingest_keeps_the_fixed_point_weight(service):
    entry = service.ingest(payload())

    assert entry.magento_order_id == "000000417"
    assert str(entry.weight_kg) == "1200.5"
    assert entry.dest_city == "Florencia"
    assert entry.status == "pending"


def test_missing_weight_is_refused(service):
    with pytest.raises(InboxValidationError) as excinfo:
        service.ingest(payload(weight_kg=""))

    assert "peso" in str(excinfo.value)


def test_zero_weight_is_refused_not_treated_as_empty(service):
    with pytest.raises(InboxValidationError):
        service.ingest(payload(weight_kg="0"))


def test_negative_weight_is_refused(service):
    with pytest.raises(InboxValidationError):
        service.ingest(payload(weight_kg="-5"))


def test_weight_above_a_truck_is_refused(service):
    with pytest.raises(InboxValidationError):
        service.ingest(payload(weight_kg="41000"))


def test_float_weight_is_accepted_but_never_kept_as_float(service):
    entry = service.ingest(payload(weight_kg=1200.5))

    assert str(entry.weight_kg) == "1200.5"


def test_destination_city_is_required(service):
    with pytest.raises(InboxValidationError) as excinfo:
        service.ingest(payload(dest_city="   "))

    assert "ciudad" in str(excinfo.value)


def test_unknown_site_is_refused(service):
    with pytest.raises(InboxValidationError):
        service.ingest(payload(site="bogota"))


def test_magento_order_id_is_required(service):
    with pytest.raises(InboxValidationError):
        service.ingest(payload(magento_order_id=""))


def test_replaying_the_same_order_changes_nothing(service):
    first = service.ingest(payload())
    second = service.ingest(payload())

    assert first == second
    assert len(service.repository.all_orders()) == 1


def test_same_order_with_a_different_weight_is_a_conflict(service):
    service.ingest(payload())

    with pytest.raises(DuplicateOrderConflict):
        service.ingest(payload(weight_kg="990"))


def test_inbox_lists_pending_orders_per_site(service):
    service.ingest(payload())
    service.ingest(
        payload(magento_order_id="000000418", site="neiva", dest_city="Neiva")
    )

    assert [e.magento_order_id for e in service.pending(site="florencia")] == [
        "000000417"
    ]
    assert [e.magento_order_id for e in service.pending(site="neiva")] == ["000000418"]
