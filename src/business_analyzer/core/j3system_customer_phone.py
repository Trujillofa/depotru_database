"""Resolve one phone to a TercerosID. Read-only. No customer name.

A phone selects a customer only when exactly one matched tercero has a
usable tariff (``TarifasID`` set, not 0, not 006 AL COSTO). Several usable
lists stay unresolved so a person can choose by ``TercerosIdentificacion``.
Junk phones (no digit 1-9, or fewer than 7 digits) match nobody.

The quote tool still receives the resolved id. This module does not read
prices, stock, cost, or margin, and it does not write.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional, Sequence

from business_analyzer.core.j3system_customer_quote import (
    tarifa_payload,
    tariff_decision,
)
from business_analyzer.core.j3system_sales_warehouse import qualified_j3_table

MIN_PHONE_DIGITS = 7
MAX_PHONE_DIGITS = 15
MAX_PHONE_RAW = 40
MAX_CANDIDATES = 12

PHONE_COLUMNS: tuple[str, ...] = (
    "TercerosCelular",
    "TercerosCelular2",
    "TelefonoContacto",
)
_PHONE_ALIASES = ("celular", "celular2", "telefono")
_SEPARATORS = (" ", "-", "+", "(", ")", ".", "/", "\t")
_IDENTIFICACION = re.compile(r"^[0-9A-Za-z.\-]{1,32}$")

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


def phone_digits(value: Any) -> str:
    """Keep decimal digits. Separators and letters drop out."""
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def phone_keys(value: Any) -> tuple[str, ...] | str:
    """Return exact digit keys, or ``phone_required`` / ``phone_invalid``.

    A leading ``57`` and the national number are the same key when both
    stay inside the digit bounds. The phone text itself is never a SQL
    literal.
    """
    if value is None or isinstance(value, bool):
        return "phone_required" if value is None else "phone_invalid"
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
    digits = phone_digits(raw)
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
    """Match the three phone columns. Keys are bound parameters, one pair each."""
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
    tf.TarifasNombre AS tarifa_nombre,
    t.TercerosIdentificacion AS identificacion,
    t.TercerosCelular AS celular,
    t.TercerosCelular2 AS celular2,
    t.TelefonoContacto AS telefono
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


def _identificacion(value: Any) -> str:
    text = str(value or "").strip()
    if _IDENTIFICACION.fullmatch(text):
        return text
    return ""


def _row_matches(row: Mapping[str, Any], keys: set[str]) -> bool:
    return any(phone_digits(row.get(alias)) in keys for alias in _PHONE_ALIASES)


def _error(reason: str, **extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"status": "error", "reason": reason}
    body.update(extra)
    return body


def decide_phone_rows(
    rows: Sequence[Mapping[str, Any]],
    keys: Sequence[str],
) -> dict[str, Any]:
    """Pick one usable list, or refuse. Phone columns are not copied out."""
    keyset = set(keys)
    matched: list[Mapping[str, Any]] = []
    seen: set[int] = set()
    for row in rows:
        if not isinstance(row, Mapping) or not _row_matches(row, keyset):
            continue
        terceros_id = _terceros_id(row)
        if terceros_id is None:
            continue
        if terceros_id in seen:
            return _error("erp_unavailable")
        seen.add(terceros_id)
        matched.append(row)
    if not matched:
        return _error("customer_not_found")

    usable = [row for row in matched if tariff_decision(row) is None]
    if len(usable) == 1:
        chosen = usable[0]
        return {
            "status": "ok",
            "terceros_id": _terceros_id(chosen),
            "tarifa": tarifa_payload(chosen),
        }
    if not usable:
        if len(matched) == 1:
            row = matched[0]
            return _error(
                tariff_decision(row) or "tariff_missing",
                terceros_id=_terceros_id(row),
                tarifa=tarifa_payload(row),
            )
        return _error("customer_not_found")
    if len(usable) > MAX_CANDIDATES:
        return _error("phone_ambiguous", truncated=True, candidates=[])

    candidates = [
        {
            "terceros_id": _terceros_id(row),
            "identificacion": _identificacion(row.get("identificacion")),
            "tarifa_codigo": str(row.get("tarifa_codigo") or "").strip(),
        }
        for row in sorted(usable, key=lambda item: _terceros_id(item) or 0)
    ]
    return _error("phone_ambiguous", truncated=False, candidates=candidates)


def fetch_customer_by_phone(db: Any, phone: Any) -> dict[str, Any]:
    """Read matching terceros. ``db.execute_query`` must already be connected.

    A failure of the read is ``erp_unavailable``. The driver message is not
    returned.
    """
    keys = phone_keys(phone)
    if isinstance(keys, str):
        return _error(keys)
    try:
        rows = db.execute_query(build_phone_match_sql(len(keys)), tuple(keys) * 3)
    except Exception:  # noqa: BLE001 — fail closed; do not leak the driver message
        return _error("erp_unavailable")
    if not isinstance(rows, list):
        return _error("erp_unavailable")
    return decide_phone_rows(rows, keys)
