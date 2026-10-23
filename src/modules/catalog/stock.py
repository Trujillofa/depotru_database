"""``catalog.stock`` — exact SKU/sede availability from J3 inventory.

Fail-closed, read-only, parameterized tool for an authorized sales flow. Emits
exact fixed-point decimal strings (never JSON floats); any ambiguity blocks the
SKU without inventing a figure. See docs/contracts/catalog-stock.md.
"""

from __future__ import annotations

import decimal
from collections.abc import Mapping
from decimal import Decimal
from typing import Any, List, Tuple

from modules.catalog.stock_aggregate import (
    _canonicalize,
    _classify_warehouse,
    _coerce_number,
    _InvalidInputError,
    _InvalidValue,
    _normalize_one_sku,
    _normalize_sede,
    _normalize_warehouse_code,
    _usable_id,
    _valid_multiplicity,
    exact_add,
)

MIN_SKUS = 1
MAX_SKUS = 5

_QUERY_TIMEOUT_SECONDS = 10
_QUERY_RETRIES = 0

MAX_RESULT_ROWS = 1000
_SENTINEL_ROWS = MAX_RESULT_ROWS + 1

_MSG_ENTRADA_INVALIDA = "entrada inválida para catalog.stock"
_MSG_ERROR_CONSULTA = "error consultando inventario J3"

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


# ---------------------------------------------------------------------------
# Input validation (§2)
# ---------------------------------------------------------------------------


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
        return {"sku": sku, "status": "no_encontrado"}
    if len(ids) > 1:
        return _blocked(sku, "validacion_fallida")

    real = [row for row in rows if row["almacen_id"] is not None]
    if not real:
        return {"sku": sku, "status": "inventario_desconocido"}
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
        try:
            sums[bucket] = exact_add(sums.get(bucket, Decimal(0)), num)
        except decimal.Inexact:
            return _blocked(sku, "validacion_fallida")

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


def _process(rows: list, skus: List[str], sede: str) -> dict:
    requested = set(skus)
    grouped: dict = {sku: [] for sku in skus}
    for row in rows:
        if not isinstance(row, Mapping) or not _EXPECTED_KEYS.issubset(row):
            return _error("error_consulta", _MSG_ERROR_CONSULTA)
        norm = row["norm_sku"]
        if not isinstance(norm, str) or norm not in requested:
            return _error("error_consulta", _MSG_ERROR_CONSULTA)
        if not _usable_id(row["articulos_id"]):
            return _error("error_consulta", _MSG_ERROR_CONSULTA)
        aid = row["almacen_id"]
        if aid is None:
            if any(
                row[k] is not None
                for k in ("almacen_codigo", "saldo_actual", "num_filas_ano")
            ):
                return _error("error_consulta", _MSG_ERROR_CONSULTA)
        elif not isinstance(aid, int) or isinstance(aid, bool):
            return _error("error_consulta", _MSG_ERROR_CONSULTA)
        elif not _valid_multiplicity(row["num_filas_ano"]):
            return _error("error_consulta", _MSG_ERROR_CONSULTA)
        grouped[norm].append(row)

    results = [_process_one(sku, grouped[sku], sede) for sku in skus]
    return {"ok": True, "sede": sede, "results": results}


# ---------------------------------------------------------------------------
# Fixed error responses (§5.1)
# ---------------------------------------------------------------------------


def _error(error_type: str, message: str) -> dict:
    return {"ok": False, "error": {"type": error_type, "message": message}}


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


def catalog_stock(ctx: Any, params: Any) -> dict:
    try:
        skus, sede = _validate_input(params)
    except _InvalidInputError:
        return _error("entrada_invalida", _MSG_ENTRADA_INVALIDA)

    try:
        sql, sql_params = _build_stock_sql(skus)
        rows = _query_j3_system(sql, sql_params)
    except Exception:  # noqa: BLE001 — fixed message, no raw logging
        return _error("error_consulta", _MSG_ERROR_CONSULTA)

    if not isinstance(rows, list) or len(rows) > MAX_RESULT_ROWS:
        return _error("error_consulta", _MSG_ERROR_CONSULTA)

    try:
        return _process(rows, skus, sede)
    except Exception:  # noqa: BLE001 — fixed message, no raw logging
        return _error("error_consulta", _MSG_ERROR_CONSULTA)
