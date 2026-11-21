"""Empresas-legible cartera responses (read-only; R23 display-only).

Two surfaces, both B2B-scope and never public:

- ``cartera_detail_response`` — ONE staff-linked TercerosID: identity
  header, cupo, aging buckets and every open document. Magento resolves
  membership (R3) and only ever passes the member's own TercerosID.
- ``cartera_summary_response`` — client-grain summary across ALL open
  accounts for the platform-admin view (admin sees all debt, member
  never receives this payload from the storefront: the controller gate
  is admin-only).

No credit terms, no reserve, no payment method: R14 stays blocked. An
ERP outage answers ``{"status": "unavailable", ...}`` and nothing else.
Amounts cross the wire only as fixed-point strings (``format_amount``).
"""

from __future__ import annotations

import os
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Optional

from modules.b2b.contracts import ErpTimeoutError, ErpUnavailableError, format_amount
from modules.b2b.j3_cartera import (
    build_cartera_docs_sql,
    build_cartera_header_sql,
    build_cartera_summary_sql,
)
from modules.b2b.j3_customer_quote import parse_terceros_id

_TIMEOUT_MARKERS = ("timeout", "timed out", "10060")

SUMMARY_MAX_ROWS_DEFAULT = 200
SUMMARY_MAX_ROWS_CAP = 500

BUCKET_KEYS: tuple[str, ...] = (
    "corriente",
    "vencido_30",
    "vencido_60",
    "vencido_90",
    "vencido_120",
    "vencido_360",
    "vencido_superior",
)


# ---------------------------------------------------------------------------
# J3 client (same gate shape as J3CustomerQuoteClient)
# ---------------------------------------------------------------------------


class J3CarteraClient:
    """Live J3 open-AR reads. Requires ``B2B_ERP_MODE=j3``."""

    def __init__(self, db_factory: Optional[Callable[[], Any]] = None) -> None:
        self._db_factory = db_factory

    def cartera_detail(self, terceros_id: Any, *, now: Optional[date] = None) -> dict:
        parsed = parse_terceros_id(terceros_id)
        if parsed is None:
            raise ErpUnavailableError("terceros_id_invalid")
        result: dict = self._run("j3_unavailable", self._detail, parsed)
        return result

    def cartera_summary(self, max_rows: int) -> list:
        rows: list = self._run("j3_unavailable", self._summary, int(max_rows))
        return rows

    # -- internals ----------------------------------------------------------

    def _detail(self, db: Any, parsed: int) -> dict:
        header_rows = db.execute_query(build_cartera_header_sql(), (parsed,))
        if not isinstance(header_rows, list) or not header_rows:
            raise ErpUnavailableError("customer_not_found")
        doc_rows = db.execute_query(build_cartera_docs_sql(), (parsed,))
        docs = (
            [dict(r) for r in doc_rows if isinstance(r, dict)]
            if isinstance(doc_rows, list)
            else []
        )
        return {"header": dict(header_rows[0]), "documents": docs}

    def _summary(self, db: Any, max_rows: int) -> list:
        rows = db.execute_query(build_cartera_summary_sql(int(max_rows)))
        if not isinstance(rows, list):
            return []
        return [dict(r) for r in rows if isinstance(r, dict)]

    def _run(self, unknown_reason: str, fn: Callable[..., Any], *args: Any) -> Any:
        mode = (os.getenv("B2B_ERP_MODE") or "").strip().lower()
        if mode != "j3":
            raise ErpUnavailableError("b2b_erp_disabled")
        try:
            if self._db_factory is not None:
                return fn(self._db_factory(), *args)
            from business_analyzer.core.database import Database

            with Database(suppress_error_details=True) as db:
                return fn(db, *args)
        except (ErpUnavailableError, ErpTimeoutError):
            raise
        except Exception as exc:  # noqa: BLE001 — unknown J3 failure fails closed
            text = str(exc).lower()
            if any(marker in text for marker in _TIMEOUT_MARKERS):
                raise ErpTimeoutError("j3_timeout") from exc
            raise ErpUnavailableError(unknown_reason) from exc


def get_b2b_cartera_client() -> J3CarteraClient:
    """Single supported entry point for tool handlers."""
    return J3CarteraClient()


# ---------------------------------------------------------------------------
# Response shaping (whitelist, never passthrough)
# ---------------------------------------------------------------------------


def _as_decimal(value: Any) -> Optional[Decimal]:
    if value is None or value == "" or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value if value.is_finite() else None
    if isinstance(value, float):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _money(value: Any) -> str:
    decimals = _as_decimal(value)
    out: str = format_amount(decimals) if decimals is not None else "0"
    return out


def _iso_date(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return ""


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()) if value is not None else ""


def _bucket_days(due: Any, as_of: date) -> Optional[str]:
    """Which aging bucket a document's due date lands in (None = current)."""
    due_date = due if isinstance(due, date) and not isinstance(due, datetime) else None
    if isinstance(due, datetime):
        due_date = due.date()
    if due_date is None:
        return None
    days = (as_of - due_date).days
    if days <= 0:
        return "corriente"
    if days <= 30:
        return "vencido_30"
    if days <= 60:
        return "vencido_60"
    if days <= 90:
        return "vencido_90"
    if days <= 120:
        return "vencido_120"
    if days <= 360:
        return "vencido_360"
    return "vencido_superior"


def _empty_buckets() -> dict:
    return {key: "0.00" for key in BUCKET_KEYS}


def _unavailable(reason: str) -> dict:
    return {
        "status": "unavailable",
        "reason": reason,
        "currency": None,
        "as_of": None,
        "terceros_id": None,
        "company_name": None,
        "cupo_total": None,
        "open_total": None,
        "buckets": None,
        "documents": [],
    }


UNAVAILABLE_KEYS = {
    "status",
    "reason",
    "currency",
    "as_of",
    "terceros_id",
    "company_name",
    "cupo_total",
    "open_total",
    "buckets",
    "documents",
}


def _fail(exc: Exception) -> dict:
    if isinstance(exc, ErpTimeoutError):
        return _unavailable("erp_timeout")
    return _unavailable(str(exc) or "erp_unavailable")


def cartera_detail_response(
    terceros_id: Any,
    erp: Any,
    *,
    now: Optional[datetime] = None,
) -> dict:
    """One company's open AR. ``now`` is injectable for deterministic aging."""
    as_of = (now or datetime.now()).date()
    parsed = parse_terceros_id(terceros_id)
    if parsed is None:
        return _unavailable("terceros_id_invalid")
    try:
        raw = erp.cartera_detail(parsed, now=as_of)
    except ErpUnavailableError as exc:
        return _fail(exc)
    except ErpTimeoutError as exc:
        return _fail(exc)
    except Exception:  # noqa: BLE001 — unknown boundary failure fails closed
        return _unavailable("erp_unavailable")

    header = dict(raw.get("header") or {})
    doc_rows = list(raw.get("documents") or [])
    buckets = _empty_buckets()
    open_total = Decimal("0")
    documents = []
    for row in doc_rows:
        saldo = _as_decimal(row.get("saldo"))
        if saldo is None:
            continue
        open_total += saldo
        bucket = _bucket_days(row.get("fecha_vence"), as_of)
        if bucket is None:
            bucket = "corriente"
        bucket_base = _as_decimal(buckets[bucket]) or Decimal("0")
        buckets[bucket] = format_amount(bucket_base + saldo)
        documents.append(
            {
                "documentos_codigo": _text(row.get("documentos_codigo")),
                "numero_factura": _text(row.get("numero_factura")),
                "fecha": _iso_date(row.get("fecha")),
                "fecha_vence": _iso_date(row.get("fecha_vence")),
                "valor": _money(row.get("valor")),
                "saldo": _money(row.get("saldo")),
            }
        )
    return {
        "status": "ok",
        "reason": None,
        "currency": "COP",
        "as_of": as_of.isoformat(),
        "terceros_id": str(parsed),
        "company_name": _text(header.get("nombres")),
        "identificacion": _text(header.get("identificacion")),
        "ciudad": _text(header.get("ciudad")),
        "cupo_total": _money(header.get("cupo")),
        "open_total": format_amount(open_total),
        "buckets": buckets,
        "document_count": len(documents),
        "documents": documents,
    }


def cartera_summary_response(
    max_rows: Any,
    erp: Any,
) -> dict:
    """All open accounts, biggest debt first, for the platform-admin view."""
    cap = _parse_max_rows(max_rows)
    if cap is None:
        return _unavailable("invalid_max_rows")
    try:
        rows = erp.cartera_summary(cap)
    except ErpUnavailableError as exc:
        return _fail(exc)
    except ErpTimeoutError as exc:
        return _fail(exc)
    except Exception:  # noqa: BLE001 — unknown boundary failure fails closed
        return _unavailable("erp_unavailable")

    clients = []
    for row in rows:
        buckets = _empty_buckets()
        for key in BUCKET_KEYS:
            buckets[key] = _money(row.get(key))
        clients.append(
            {
                "terceros_id": _text(row.get("terceros_id")),
                "identificacion": _text(row.get("identificacion")),
                "nombres": _text(row.get("nombres")),
                "ciudad": _text(row.get("ciudad")),
                "cupo_total": _money(row.get("cupo")),
                "open_total": _money(row.get("open_total")),
                "buckets": buckets,
                "documents": int(row.get("documents") or 0),
            }
        )
    return {
        "status": "ok",
        "reason": None,
        "currency": "COP",
        "as_of": date.today().isoformat(),
        "open_total": format_amount(
            sum(
                (
                    dec
                    for dec in (_as_decimal(c["open_total"]) for c in clients)
                    if dec is not None
                ),
                Decimal("0"),
            )
        ),
        "client_count": len(clients),
        "clients": clients,
    }


def _parse_max_rows(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        if value is None:
            return SUMMARY_MAX_ROWS_DEFAULT
        return None
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
    elif isinstance(value, int):
        parsed = value
    else:
        return None
    if not 1 <= parsed <= SUMMARY_MAX_ROWS_CAP:
        return None
    return parsed
