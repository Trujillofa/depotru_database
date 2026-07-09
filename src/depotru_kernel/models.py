"""Lightweight domain models shared across modules."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class Money:
    """Currency amount in COP (tax semantics left to caller)."""

    amount: Decimal
    currency: str = "COP"

    @classmethod
    def from_float(cls, value: float, currency: str = "COP") -> "Money":
        return cls(amount=Decimal(str(value)), currency=currency)


@dataclass(frozen=True)
class PartyRef:
    """Cross-system customer / tercero reference."""

    cedula_or_nit: Optional[str] = None
    magento_customer_id: Optional[int] = None
    j3_tercero_id: Optional[str] = None
    display_name: Optional[str] = None


@dataclass(frozen=True)
class SkuRef:
    """Cross-system product / article reference."""

    sku: str
    magento_entity_id: Optional[int] = None
    articulos_codigo: Optional[str] = None
    name: Optional[str] = None
