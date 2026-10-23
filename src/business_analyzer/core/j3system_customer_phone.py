"""Resolve one phone to a TercerosID. Read-only. No customer name.

A phone selects a customer only when exactly one matched tercero has a
usable tariff (``TarifasID`` set, not 0, not 006 AL COSTO). Several usable
lists stay unresolved so a person can choose. Junk phones fail closed.

The phone is PII for the entire lifetime of this slice: it is never
selected, never returned, never logged, and never interpolated into SQL.
It is passed only as bound parameters. The quote tool still receives the
resolved id; this module does not read prices, stock, cost, or margin, and
it does not write.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from business_analyzer.core.j3system_customer_quote import tariff_decision
from business_analyzer.core.j3system_sales_warehouse import qualified_j3_table
from depotru_kernel.auth import Audience

MIN_PHONE_DIGITS = 7
MAX_PHONE_DIGITS = 15
MAX_PHONE_RAW = 40
MAX_CANDIDATES = 12

ALLOWED_AUDIENCES = frozenset({Audience.SALES, Audience.ADMIN})
ALLOWED_PARAM_KEYS = frozenset({"phone"})

PHONE_COLUMNS: tuple[str, ...] = (
    "TercerosCelular",
    "TercerosCelular2",
    "TelefonoContacto",
)
_SEPARATORS = (" ", "-", "+", "(", ")", ".", "/", "\t")
_DIGITS = frozenset("0123456789")
_ALLOWED_CHARS = _DIGITS | frozenset(_SEPARATORS)

FORBIDDEN_SQL_FRAGMENTS: tuple[str, ...] = (
    "ArticulosCosto",
    "ArticulosUltmoCosto",
    "ArticulosMargen",
    "UltimoCostoCompra",
    "CostoInicial",
    "CostoDepre",
    "ValorCosto",
    "ListadoPreciosCosto",
    "CostoSinIva",
    "CostoMasIva",
    "CostoAnterior",
    "PreciosIncremento",
    "PreciosValor",
    "ArticulosVenta",
    "TercerosNombres",
)

# Fixed, non-interpolating Spanish messages per reason (never the phone).
FIXED_MESSAGES: dict[str, str] = {
    "phone_required": "El teléfono es obligatorio.",
    "phone_invalid": "El teléfono no es válido.",
    "customer_not_found": (
        "No se encontró un cliente con tarifa usable para ese teléfono."
    ),
    "tariff_missing": "El cliente no tiene una tarifa asignada.",
    "tariff_refused": "La tarifa del cliente (AL COSTO) no permite cotizar.",
    "phone_ambiguous": (
        "Hay varios clientes posibles; se requiere intervención humana para elegir."
    ),
    "erp_unavailable": "No fue posible consultar el sistema en este momento.",
    "audience_not_allowed": "No autorizado para esta audiencia.",
    "unexpected_parameters": "Parámetros no esperados.",
}


def error_payload(reason: str, **extra: Any) -> dict[str, Any]:
    """Fixed error shape; ``reason`` is a closed enum, never the input."""
    body: dict[str, Any] = {"status": "error", "reason": reason}
    body.update(extra)
    return body


def phone_keys(value: Any) -> tuple[str, ...] | str:
    """Return exact digit keys, or ``phone_required`` / ``phone_invalid``.

    Only ASCII digits and the allowed separators survive; any other
    character (letters, symbols, unicode digits) fails ``phone_invalid``
    rather than being silently dropped. A leading ``57`` and the national
    number become the same key pair when both stay inside the digit bounds.
    The phone text itself is never a SQL literal.
    """
    if value is None:
        return "phone_required"
    if isinstance(value, bool):
        return "phone_invalid"
    if isinstance(value, int):
        raw = str(value) if value > 0 else ""
    elif isinstance(value, str):
        raw = value.strip()
    else:
        return "phone_invalid"
    if not raw:
        return "phone_required"
    if len(raw) > MAX_PHONE_RAW:
        return "phone_invalid"
    if any(ch not in _ALLOWED_CHARS for ch in raw):
        return "phone_invalid"
    digits = "".join(ch for ch in raw if ch in _DIGITS)
    if (
        len(digits) < MIN_PHONE_DIGITS
        or len(digits) > MAX_PHONE_DIGITS
        or not any(ch in "123456789" for ch in digits)
    ):
        return "phone_invalid"
    keys = [digits]
    if digits.startswith("57") and len(digits) - 2 >= MIN_PHONE_DIGITS:
        keys.append(digits[2:])
    elif not digits.startswith("57"):
        international = "57" + digits
        if len(international) <= MAX_PHONE_DIGITS:
            keys.append(international)
    unique: list[str] = []
    for key in keys:
        if key not in unique:
            unique.append(key)
    return tuple(unique)


def _stripped(column: str) -> str:
    if column not in PHONE_COLUMNS:
        raise ValueError("Unknown phone column")
    expr = f"ISNULL(t.{column}, '')"
    for char in _SEPARATORS:
        literal = "CHAR(9)" if char == "\t" else f"'{char}'"
        expr = f"REPLACE({expr}, {literal}, '')"
    return expr


def build_phone_match_sql(key_count: int) -> str:
    """Match the three phone columns only in the WHERE clause.

    The phone columns are never selected: no raw phone value crosses the
    driver boundary. Keys are bound parameters, one full key set per phone
    column (``tuple(keys) * 3``).
    """
    if key_count not in (1, 2):
        raise ValueError("key_count")
    placeholders = ", ".join(["%s"] * key_count)
    terceros = qualified_j3_table("AdmTerceros")
    tarifas = qualified_j3_table("AdmTarifas")
    where = " OR ".join(
        f"{_stripped(column)} IN ({placeholders})" for column in PHONE_COLUMNS
    )
    return f"""
SELECT
    t.TercerosID AS terceros_id,
    t.TarifasID AS tarifas_id,
    tf.TarifasCodigo AS tarifa_codigo,
    tf.TarifasNombre AS tarifa_nombre
FROM {terceros} t
LEFT JOIN {tarifas} tf ON tf.TarifasID = t.TarifasID
WHERE {where}
""".strip()


def _terceros_id(row: Mapping[str, Any]) -> Optional[int]:
    raw = row.get("terceros_id")
    if isinstance(raw, bool) or raw is None or raw == "":
        return None
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _tarifa_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    """Minimal local tariff payload ``{"codigo", "nombre"}`` (B2 unchanged)."""
    return {
        "codigo": str(row.get("tarifa_codigo") or "").strip(),
        "nombre": str(row.get("tarifa_nombre") or "").strip(),
    }


def _tarifa_codigo(row: Mapping[str, Any]) -> str:
    return str(row.get("tarifa_codigo") or "").strip()


def decide_phone_rows(rows: Sequence[Any]) -> dict[str, Any]:
    """Pick one usable list, or refuse. Phone columns are not re-checked.

    ``rows`` is already the SQL ``WHERE``-matched set: there is no in-memory
    re-check of phone values, and no customer name, identification, or phone
    value is copied out.
    """
    matched: list[Mapping[str, Any]] = []
    seen: set[int] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        terceros_id = _terceros_id(row)
        if terceros_id is None:
            continue
        if terceros_id in seen:
            return error_payload("erp_unavailable")
        seen.add(terceros_id)
        matched.append(row)
    if not matched:
        return error_payload("customer_not_found")

    usable = [row for row in matched if tariff_decision(row) is None]
    if len(usable) == 1:
        chosen = usable[0]
        return {
            "status": "ok",
            "terceros_id": _terceros_id(chosen),
            "tarifa": _tarifa_payload(chosen),
        }
    if not usable:
        if len(matched) == 1:
            row = matched[0]
            return error_payload(tariff_decision(row) or "tariff_missing")
        return error_payload("customer_not_found")
    if len(usable) > MAX_CANDIDATES:
        return error_payload("phone_ambiguous", truncated=True, candidates=[])

    candidates = [
        {
            "terceros_id": _terceros_id(row),
            "tarifa_codigo": _tarifa_codigo(row),
        }
        for row in sorted(usable, key=lambda item: _terceros_id(item) or 0)
    ]
    return error_payload("phone_ambiguous", truncated=False, candidates=candidates)


def fetch_customer_by_phone(db: Any, phone: Any) -> dict[str, Any]:
    """Read matching terceros. ``db.execute_query`` must already be connected.

    A failure of the read is ``erp_unavailable``. The driver message is not
    returned, and the phone is never logged or interpolated.
    """
    keys = phone_keys(phone)
    if isinstance(keys, str):
        return error_payload(keys)
    try:
        rows = db.execute_query(build_phone_match_sql(len(keys)), tuple(keys) * 3)
    except Exception:  # noqa: BLE001 — fail closed; do not leak the driver message
        return error_payload("erp_unavailable")
    if not isinstance(rows, list):
        return error_payload("erp_unavailable")
    return decide_phone_rows(rows)
