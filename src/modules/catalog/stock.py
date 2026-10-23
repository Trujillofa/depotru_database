"""``catalog.stock`` — exact SKU/sede availability from J3 inventory.

Fail-closed, read-only, parameterized tool for an authorized sales flow. Emits
exact fixed-point decimal strings (never JSON floats); any ambiguity blocks the
SKU without inventing a figure. See docs/contracts/catalog-stock.md.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal
from typing import Any, List, Tuple

MIN_SKUS = 1
MAX_SKUS = 5
MAX_SKU_LENGTH = 40

_QUERY_TIMEOUT_SECONDS = 10
_QUERY_RETRIES = 0

MAX_RESULT_ROWS = 1000
_SENTINEL_ROWS = MAX_RESULT_ROWS + 1

_MSG_ENTRADA_INVALIDA = "entrada inválida para catalog.stock"
_MSG_ERROR_CONSULTA = "error consultando inventario J3"

_SKU_RE = re.compile(r"^[A-Z0-9._-]+$")
_DECIMAL_RE = re.compile(r"^\d+(\.\d+)?$")

_NEIVA = frozenset({"ALM", "BD6", "SUR", "DIS", "BOD"})
_FLORENCIA = frozenset({"FLO"})
_BAJA_ROTACION = frozenset({"B.ROT"})
_EXCLUDED = frozenset({"CON", "CEN", "EXH", "EXD", "BDT", "MDL", "TRA"})

_EXPECTED_KEYS = frozenset(
    {
        "norm_sku",
        "articulos_id",
        "almacen_id",
        "almacen_codigo",
        "saldo_actual",
        "num_filas_ano",
    }
)


class _InvalidInputError(Exception):
    """Closed-schema input violation (→ entrada_invalida)."""


class _InvalidValue(Exception):
    """Unsignable / non-exact saldo value (→ validacion_fallida)."""


# ---------------------------------------------------------------------------
# Exact decimal (§9)
# ---------------------------------------------------------------------------


def _canonicalize(value: Decimal) -> str:
    text = "0" if value == 0 else format(value, "f")
    if not _DECIMAL_RE.fullmatch(text) or Decimal(text) != value:
        raise _InvalidValue
    return text


def _coerce_number(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise _InvalidValue
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise _InvalidValue
        return value
    raise _InvalidValue


# ---------------------------------------------------------------------------
# Input normalization (§2)
# ---------------------------------------------------------------------------


def _upper_ascii(text: str) -> str | None:
    out: List[str] = []
    for ch in text:
        o = ord(ch)
        if o > 127:
            return None
        out.append(chr(o - 32) if 97 <= o <= 122 else ch)
    return "".join(out)


def _normalize_one_sku(raw: Any) -> str:
    if not isinstance(raw, str):
        raise _InvalidInputError
    upper = _upper_ascii(raw.strip())
    if (
        upper is None
        or not upper
        or len(upper) > MAX_SKU_LENGTH
        or not _SKU_RE.fullmatch(upper)
    ):
        raise _InvalidInputError
    return upper


def _normalize_sede(raw: Any) -> str:
    if raw is None:
        return "ambas"
    if not isinstance(raw, str):
        raise _InvalidInputError
    value = raw.strip().lower()
    if value not in ("neiva", "florencia"):
        raise _InvalidInputError
    return value


def _validate_input(params: Any) -> Tuple[List[str], str]:
    if (
        not isinstance(params, Mapping)
        or not set(params) <= {"skus", "sede"}
        or "skus" not in params
    ):
        raise _InvalidInputError

    raw_skus = params["skus"]
    if not isinstance(raw_skus, list) or not (MIN_SKUS <= len(raw_skus) <= MAX_SKUS):
        raise _InvalidInputError

    normalized = [_normalize_one_sku(sku) for sku in raw_skus]
    if len(set(normalized)) != len(normalized):
        raise _InvalidInputError

    return normalized, _normalize_sede(params.get("sede"))


# ---------------------------------------------------------------------------
# Warehouse classification (§6, §7)
# ---------------------------------------------------------------------------


def _normalize_warehouse_code(code: Any) -> str | None:
    if not isinstance(code, str):
        return None
    trimmed = code.strip()
    if not trimmed:
        return None
    return _upper_ascii(trimmed)


def _classify_warehouse(code: str | None) -> str | None:
    if code in _NEIVA:
        return "neiva"
    if code in _FLORENCIA:
        return "florencia"
    if code in _BAJA_ROTACION:
        return "baja_rotacion"
    if code in _EXCLUDED:
        return "excluded"
    return None


# ---------------------------------------------------------------------------
# Read-only, parameterized T-SQL (§10, §11)
# ---------------------------------------------------------------------------


def _build_stock_sql(skus: List[str]) -> Tuple[str, Tuple[str, ...]]:
    from business_analyzer.core.j3system_sales_warehouse import qualified_j3_table

    articulos = qualified_j3_table("AdmArticulos")
    existencias = qualified_j3_table("InvExistencias")
    detalle = qualified_j3_table("InvDetalleExistencias")
    almacen = qualified_j3_table("AdmAlmacen")

    placeholders = ", ".join(["%s"] * len(skus))

    sql = f"""
SELECT TOP ({_SENTINEL_ROWS})
    cat.norm_sku AS norm_sku,
    cat.ArticulosID AS articulos_id,
    ranked.AlmacenID AS almacen_id,
    ranked.AlmacenCodigo AS almacen_codigo,
    ranked.SaldoActual AS saldo_actual,
    ranked.num_filas_ano AS num_filas_ano
FROM (
    SELECT DISTINCT
        UPPER(LTRIM(RTRIM(a.ArticulosCodigo))) AS norm_sku,
        a.ArticulosID
    FROM {articulos} a
    WHERE UPPER(LTRIM(RTRIM(a.ArticulosCodigo))) IN ({placeholders})
) cat
LEFT JOIN (
    SELECT
        base.ArticulosID,
        base.AlmacenID,
        base.SaldoActual,
        base.num_filas_ano,
        al.AlmacenCodigo
    FROM (
        SELECT
            e.ArticulosID,
            d.AlmacenID,
            d.SaldoActual,
            d.Ano,
            COUNT(*) OVER (PARTITION BY e.ArticulosID, d.AlmacenID, d.Ano) AS num_filas_ano,
            ROW_NUMBER() OVER (
                PARTITION BY e.ArticulosID, d.AlmacenID ORDER BY d.Ano DESC
            ) AS rn
        FROM {detalle} d
        JOIN {existencias} e ON e.ExistenciasID = d.ExistenciasID
    ) base
    LEFT JOIN {almacen} al ON al.AlmacenID = base.AlmacenID
    WHERE base.rn = 1
) ranked ON ranked.ArticulosID = cat.ArticulosID
ORDER BY cat.norm_sku, cat.ArticulosID, ranked.AlmacenID
""".strip()
    return sql, tuple(skus)


def _query_j3_system(sql: str, params: Tuple[str, ...]) -> list:
    import pymssql

    from business_analyzer.core.config import Config

    conn = pymssql.connect(
        server=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME_J3SYSTEM,
        port=str(Config.DB_PORT),
        login_timeout=_QUERY_TIMEOUT_SECONDS,
        timeout=_QUERY_TIMEOUT_SECONDS,
        tds_version=Config.DB_TDS_VERSION,
    )
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(sql, params)
        rows = list(cursor)
        cursor.close()
        return rows
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Per-SKU processing (precedence §5.2)
# ---------------------------------------------------------------------------


def _blocked(sku: str, reason: str) -> dict:
    return {"sku": sku, "status": "bloqueado", "reason": reason}


def _not_found(sku: str) -> dict:
    return {"sku": sku, "status": "no_encontrado"}


def _unknown_inventory(sku: str) -> dict:
    return {"sku": sku, "status": "inventario_desconocido"}


def _bucket_state(bucket: str, has: set, sums: dict) -> Tuple[str, str | None]:
    if bucket not in has:
        return ("absent", None)
    total = sums[bucket]
    return ("positive", _canonicalize(total)) if total > 0 else ("zero", "0")


def _low_rotation_signal(rot_state: str, requested: List[str]) -> str:
    if rot_state in ("zero", "absent"):
        return "not_required"
    if any(state == "positive" for state in requested):
        return "not_required"
    if all(state == "zero" for state in requested):
        return "required"
    return "unknown"


def _process_one(sku: str, rows: List[dict], sede: str) -> dict:
    ids = {row["articulos_id"] for row in rows}
    if not ids:
        return _not_found(sku)
    if len(ids) > 1:
        return _blocked(sku, "validacion_fallida")

    real = [row for row in rows if row["almacen_id"] is not None]
    if not real:
        return _unknown_inventory(sku)
    if any(row["num_filas_ano"] > 1 for row in real):
        return _blocked(sku, "validacion_fallida")

    included: List[Tuple[str, Any]] = []
    for row in real:
        cls = _classify_warehouse(_normalize_warehouse_code(row.get("almacen_codigo")))
        if cls is None:
            return _blocked(sku, "codigo_no_clasificado")
        if cls != "excluded":
            included.append((cls, row.get("saldo_actual")))

    for _, saldo in included:
        try:
            num = _coerce_number(saldo)
        except _InvalidValue:
            continue
        if num is not None and num < 0:
            return _blocked(sku, "saldo_negativo")

    sums: dict = {}
    has: set = set()
    for bucket, saldo in included:
        try:
            num = _coerce_number(saldo)
        except _InvalidValue:
            return _blocked(sku, "validacion_fallida")
        if num is None:
            return _blocked(sku, "validacion_fallida")
        has.add(bucket)
        sums[bucket] = sums.get(bucket, Decimal(0)) + num

    neiva = _bucket_state("neiva", has, sums)
    florencia = _bucket_state("florencia", has, sums)
    rot = _bucket_state("baja_rotacion", has, sums)

    if sede == "neiva":
        sedes = {"neiva": neiva[1]}
        requested = [neiva[0]]
    elif sede == "florencia":
        sedes = {"florencia": florencia[1]}
        requested = [florencia[0]]
    else:
        sedes = {"neiva": neiva[1], "florencia": florencia[1]}
        requested = [neiva[0], florencia[0]]

    return {
        "sku": sku,
        "status": "ok",
        "sedes": sedes,
        "baja_rotacion": rot[1],
        "baja_rotacion_confirmation": _low_rotation_signal(rot[0], requested),
    }


def _valid_multiplicity(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _usable_id(value: Any) -> bool:
    if value is None:
        return False
    try:
        hash(value)
    except TypeError:
        return False
    return True


def _process(rows: list, skus: List[str], sede: str) -> dict:
    requested = set(skus)
    grouped: dict = {sku: [] for sku in skus}
    for row in rows:
        if not isinstance(row, Mapping) or not _EXPECTED_KEYS.issubset(row):
            return _error_consulta()
        norm = row["norm_sku"]
        if not isinstance(norm, str) or norm not in requested:
            return _error_consulta()
        if not _usable_id(row["articulos_id"]):
            return _error_consulta()
        if row["almacen_id"] is not None and not _valid_multiplicity(
            row["num_filas_ano"]
        ):
            return _error_consulta()
        grouped[norm].append(row)

    results = [_process_one(sku, grouped[sku], sede) for sku in skus]
    return {"ok": True, "sede": sede, "results": results}


# ---------------------------------------------------------------------------
# Fixed error responses (§5.1)
# ---------------------------------------------------------------------------


def _error_entrada_invalida() -> dict:
    return {
        "ok": False,
        "error": {"type": "entrada_invalida", "message": _MSG_ENTRADA_INVALIDA},
    }


def _error_consulta() -> dict:
    return {
        "ok": False,
        "error": {"type": "error_consulta", "message": _MSG_ERROR_CONSULTA},
    }


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


def catalog_stock(ctx: Any, params: Any) -> dict:
    try:
        skus, sede = _validate_input(params)
    except _InvalidInputError:
        return _error_entrada_invalida()

    try:
        sql, sql_params = _build_stock_sql(skus)
        rows = _query_j3_system(sql, sql_params)
    except Exception:  # noqa: BLE001 — fixed message, no raw logging
        return _error_consulta()

    if not isinstance(rows, list) or len(rows) > MAX_RESULT_ROWS:
        return _error_consulta()

    try:
        return _process(rows, skus, sede)
    except Exception:  # noqa: BLE001 — fixed message, no raw logging
        return _error_consulta()
