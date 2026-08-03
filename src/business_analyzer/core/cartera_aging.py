"""Cartera / AR aging analytics from SmartBusiness ``banco_cartera``.

Uses the latest ``fecha_carga`` snapshot only (v1). Optional ``as_of_date``
selects the newest snapshot on or before that calendar day. KPI math aligns
with Q9 in ``kpi_sql_pack.sql.template``. Optional DSO uses ``banco_datos``
with the canonical sales document exclusions.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Dict, List, Mapping, Optional, Sequence, cast

from business_analyzer.core.database import Database, qualified_sb_table
from depotru_kernel.documents import (
    CANONICAL_EXCLUDED_DOCUMENT_CODES,
    excluded_document_sql_in_list,
)

DEFAULT_TOP_N = 25
DEFAULT_DSO_DAYS = 30

# Columns allowed in SELECT (decision summary / Q9 family).
SNAPSHOT_SELECT_COLUMNS: tuple[str, ...] = (
    "cliente_uid",
    "cliente_nit",
    "cliente_razon_social",
    "cliente_ciudad",
    "cliente_departamento",
    "vendedor_nombre",
    "corriente",
    "vencido",
    "vencido_30",
    "vencido_60",
    "vencido_90",
    "vencido_120",
    "vencido_360",
    "vencido_superior",
    "total",
    "dias_vencidos",
    "cliente_cupo",
    "fecha_carga",
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

BUCKET_KEYS: tuple[tuple[str, str], ...] = (
    ("corriente", "Corriente (al día)"),
    ("vencido_30", "Vencido 1–30 d"),
    ("vencido_60", "Vencido 31–60 d"),
    ("vencido_90", "Vencido 61–90 d"),
    ("vencido_120", "Vencido 91–120 d"),
    ("vencido_360", "Vencido 121–360 d"),
    ("vencido_superior", "Vencido >360 d"),
)


def _as_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _as_int(value: Any) -> int:
    try:
        if value is None:
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def validate_as_of_date(as_of_date: str) -> str:
    raw = (as_of_date or "").strip()
    if not _DATE_RE.fullmatch(raw):
        raise ValueError(f"Invalid as_of_date (use YYYY-MM-DD): {as_of_date!r}")
    date.fromisoformat(raw)
    return raw


def default_as_of_date(*, today: Optional[date] = None) -> str:
    """Default as-of date: yesterday."""
    ref = today or date.today()
    return (ref - timedelta(days=1)).isoformat()


def safe_divide(n: float, d: float, default: float = 0.0) -> float:
    return n / d if d != 0 else default


def build_snapshot_sql(
    *,
    as_of_date: Optional[str] = None,
    sb_database: Optional[str] = None,
) -> str:
    """SQL for open AR rows on the latest ``fecha_carga`` snapshot.

    When ``as_of_date`` is set, picks the newest snapshot on or before that day.
    """
    table = qualified_sb_table("banco_cartera", sb_database)
    cols = ",\n        ".join(SNAPSHOT_SELECT_COLUMNS)
    if as_of_date:
        as_of = validate_as_of_date(as_of_date)
        snapshot_filter = (
            f"fecha_carga = ("
            f"SELECT MAX(fecha_carga) FROM {table} "
            f"WHERE CAST(fecha_carga AS DATE) <= CAST('{as_of}' AS DATE)"
            f")"
        )
    else:
        snapshot_filter = f"fecha_carga = (SELECT MAX(fecha_carga) FROM {table})"
    return f"""
SELECT
        {cols}
FROM {table}
WHERE {snapshot_filter}
""".strip()


def build_dso_sales_sql(
    *,
    as_of_date: str,
    dso_days: int = DEFAULT_DSO_DAYS,
    sb_database: Optional[str] = None,
) -> str:
    """Net sales (sin IVA) for DSO denominator over ``dso_days`` ending on as_of."""
    as_of = validate_as_of_date(as_of_date)
    days = int(dso_days)
    if days <= 0:
        raise ValueError("dso_days must be positive")
    banco = qualified_sb_table("banco_datos", sb_database)
    excluded = excluded_document_sql_in_list()
    return f"""
SELECT
    SUM(TotalSinIva) AS ventas_netas,
    {days} AS dias_periodo
FROM {banco}
WHERE DocumentosCodigo NOT IN ({excluded})
  AND Fecha >= DATEADD(DAY, -{days - 1}, CAST('{as_of}' AS DATE))
  AND Fecha <= CAST('{as_of}' AS DATE)
""".strip()


def aggregate_clients(
    rows: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Roll document-level snapshot rows up to one row per customer."""
    buckets: Dict[str, Dict[str, Any]] = {}
    for raw in rows:
        uid = raw.get("cliente_uid")
        nit = str(raw.get("cliente_nit") or "").strip()
        name = str(raw.get("cliente_razon_social") or "").strip()
        if uid is not None:
            key = f"uid:{uid}"
        elif nit:
            key = f"nit:{nit}"
        elif name:
            key = f"name:{name}"
        else:
            key = f"row:{id(raw)}"
        b = buckets.get(key)
        if b is None:
            b = {
                "cliente_uid": uid,
                "cliente_nit": nit,
                "cliente_razon_social": name,
                "cliente_ciudad": raw.get("cliente_ciudad"),
                "cliente_departamento": raw.get("cliente_departamento"),
                "vendedor_nombre": raw.get("vendedor_nombre"),
                "cliente_cupo": _as_float(raw.get("cliente_cupo")),
                "corriente": 0.0,
                "vencido": 0.0,
                "vencido_30": 0.0,
                "vencido_60": 0.0,
                "vencido_90": 0.0,
                "vencido_120": 0.0,
                "vencido_360": 0.0,
                "vencido_superior": 0.0,
                "total": 0.0,
                "dias_vencidos": 0,
                "documentos": 0,
            }
            buckets[key] = b
        for money_key in (
            "corriente",
            "vencido",
            "vencido_30",
            "vencido_60",
            "vencido_90",
            "vencido_120",
            "vencido_360",
            "vencido_superior",
            "total",
        ):
            b[money_key] = _as_float(b[money_key]) + _as_float(raw.get(money_key))
        cupo = _as_float(raw.get("cliente_cupo"))
        if cupo > _as_float(b.get("cliente_cupo")):
            b["cliente_cupo"] = cupo
        dias = _as_int(raw.get("dias_vencidos"))
        if dias > _as_int(b.get("dias_vencidos")):
            b["dias_vencidos"] = dias
        if raw.get("vendedor_nombre") and not b.get("vendedor_nombre"):
            b["vendedor_nombre"] = raw.get("vendedor_nombre")
        if raw.get("cliente_ciudad") and not b.get("cliente_ciudad"):
            b["cliente_ciudad"] = raw.get("cliente_ciudad")
        b["documentos"] = _as_int(b.get("documentos")) + 1

    clients = list(buckets.values())
    for c in clients:
        cupo = _as_float(c.get("cliente_cupo"))
        total = _as_float(c.get("total"))
        c["sobre_cupo"] = bool(cupo > 0 and total > cupo)
        c["exceso_cupo"] = max(total - cupo, 0.0) if cupo > 0 else 0.0
        c["vencido_90_plus"] = (
            _as_float(c.get("vencido_90"))
            + _as_float(c.get("vencido_120"))
            + _as_float(c.get("vencido_360"))
            + _as_float(c.get("vencido_superior"))
        )
        c["share_total"] = 0.0  # filled after totals known
    return clients


def compute_summary(
    clients: Sequence[Mapping[str, Any]],
    *,
    document_row_count: int = 0,
    dso_dias: Optional[float] = None,
    ventas_netas: Optional[float] = None,
    dias_periodo: int = DEFAULT_DSO_DAYS,
    fecha_carga: Any = None,
) -> Dict[str, Any]:
    """Portfolio KPIs aligned with Q9 (client-aggregated where sensible)."""
    cartera_total = sum(_as_float(c.get("total")) for c in clients)
    corriente = sum(_as_float(c.get("corriente")) for c in clients)
    vencido = sum(_as_float(c.get("vencido")) for c in clients)
    v30 = sum(_as_float(c.get("vencido_30")) for c in clients)
    v60 = sum(_as_float(c.get("vencido_60")) for c in clients)
    v90 = sum(_as_float(c.get("vencido_90")) for c in clients)
    v120 = sum(_as_float(c.get("vencido_120")) for c in clients)
    v360 = sum(_as_float(c.get("vencido_360")) for c in clients)
    vsup = sum(_as_float(c.get("vencido_superior")) for c in clients)
    vencido_90_plus = v90 + v120 + v360 + vsup

    weighted_days = 0.0
    for c in clients:
        total = _as_float(c.get("total"))
        dias = max(_as_int(c.get("dias_vencidos")), 0)
        weighted_days += total * dias
    dias_prom = safe_divide(weighted_days, cartera_total, 0.0)

    sobre = sum(1 for c in clients if c.get("sobre_cupo"))
    con_saldo = sum(1 for c in clients if abs(_as_float(c.get("total"))) > 0.005)

    return {
        "Cartera_Total": cartera_total,
        "Cartera_Corriente": corriente,
        "Cartera_Vencida": vencido,
        "Cartera_Vencida_Pct": safe_divide(vencido * 100.0, cartera_total),
        "Cartera_Vencida_90_Plus": vencido_90_plus,
        "Cartera_Vencida_90_Plus_Pct": safe_divide(
            vencido_90_plus * 100.0, cartera_total
        ),
        "Clientes_Con_Saldo": con_saldo,
        "Clientes_Sobre_Cupo": sobre,
        "Documentos_Filas": int(document_row_count),
        "Dias_Vencidos_Promedio_Ponderado": dias_prom,
        "DSO_Dias": dso_dias,
        "Ventas_Netas_Periodo": ventas_netas,
        "Dias_Periodo": int(dias_periodo),
        "Fecha_Carga_Cartera": fecha_carga,
        "Bucket_Corriente": corriente,
        "Bucket_Vencido_30": v30,
        "Bucket_Vencido_60": v60,
        "Bucket_Vencido_90": v90,
        "Bucket_Vencido_120": v120,
        "Bucket_Vencido_360": v360,
        "Bucket_Vencido_Superior": vsup,
    }


def bucket_breakdown(
    summary: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    """Aging bucket amounts + share of total AR."""
    total = _as_float(summary.get("Cartera_Total"))
    mapping = {
        "corriente": summary.get("Bucket_Corriente"),
        "vencido_30": summary.get("Bucket_Vencido_30"),
        "vencido_60": summary.get("Bucket_Vencido_60"),
        "vencido_90": summary.get("Bucket_Vencido_90"),
        "vencido_120": summary.get("Bucket_Vencido_120"),
        "vencido_360": summary.get("Bucket_Vencido_360"),
        "vencido_superior": summary.get("Bucket_Vencido_Superior"),
    }
    out: List[Dict[str, Any]] = []
    for key, label in BUCKET_KEYS:
        amount = _as_float(mapping.get(key))
        out.append(
            {
                "bucket": key,
                "label": label,
                "amount": amount,
                "share_pct": safe_divide(amount * 100.0, total),
            }
        )
    return out


def top_overdue(
    clients: Sequence[Mapping[str, Any]],
    *,
    top_n: int = DEFAULT_TOP_N,
) -> List[Dict[str, Any]]:
    """Clients ranked by overdue balance (then days overdue)."""
    filtered = [
        dict(c)
        for c in clients
        if _as_float(c.get("vencido")) > 0 or _as_int(c.get("dias_vencidos")) > 0
    ]
    filtered.sort(
        key=lambda c: (
            -_as_float(c.get("vencido")),
            -_as_int(c.get("dias_vencidos")),
            -_as_float(c.get("total")),
        )
    )
    return filtered[: max(0, int(top_n))]


def top_concentration(
    clients: Sequence[Mapping[str, Any]],
    *,
    top_n: int = DEFAULT_TOP_N,
) -> List[Dict[str, Any]]:
    """Largest AR balances with cumulative share (concentration)."""
    ranked = sorted(
        (dict(c) for c in clients if abs(_as_float(c.get("total"))) > 0.005),
        key=lambda c: -_as_float(c.get("total")),
    )
    total = sum(_as_float(c.get("total")) for c in ranked) or 1.0
    cum = 0.0
    out: List[Dict[str, Any]] = []
    for c in ranked[: max(0, int(top_n))]:
        amt = _as_float(c.get("total"))
        cum += amt
        row = dict(c)
        row["share_total"] = safe_divide(amt, total)
        row["share_acum"] = safe_divide(cum, total)
        out.append(row)
    return out


def over_limit_clients(
    clients: Sequence[Mapping[str, Any]],
    *,
    top_n: int = DEFAULT_TOP_N,
) -> List[Dict[str, Any]]:
    """Clients with total AR above credit limit."""
    filtered = [dict(c) for c in clients if c.get("sobre_cupo")]
    filtered.sort(key=lambda c: -_as_float(c.get("exceso_cupo")))
    return filtered[: max(0, int(top_n))]


def by_vendedor(
    clients: Sequence[Mapping[str, Any]],
    *,
    top_n: int = 15,
) -> List[Dict[str, Any]]:
    """AR and overdue totals by seller name."""
    buckets: Dict[str, Dict[str, Any]] = {}
    for c in clients:
        name = (
            str(c.get("vendedor_nombre") or "(sin vendedor)").strip()
            or "(sin vendedor)"
        )
        b = buckets.setdefault(
            name,
            {
                "vendedor_nombre": name,
                "clientes": 0,
                "total": 0.0,
                "vencido": 0.0,
                "vencido_90_plus": 0.0,
            },
        )
        b["clientes"] += 1
        b["total"] = _as_float(b["total"]) + _as_float(c.get("total"))
        b["vencido"] = _as_float(b["vencido"]) + _as_float(c.get("vencido"))
        b["vencido_90_plus"] = _as_float(b["vencido_90_plus"]) + _as_float(
            c.get("vencido_90_plus")
        )
    ranked = sorted(buckets.values(), key=lambda x: -_as_float(x.get("total")))
    return ranked[: max(0, int(top_n))]


def compute_dso(cartera_total: float, ventas_netas: float, dias_periodo: int) -> float:
    """DSO = Cartera / (ventas_netas / días) = cartera * días / ventas."""
    if ventas_netas is None or ventas_netas == 0 or dias_periodo <= 0:
        return 0.0
    return (cartera_total * float(dias_periodo)) / float(ventas_netas)


def build_report_from_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    as_of_date: str,
    top_n: int = DEFAULT_TOP_N,
    dso_days: int = DEFAULT_DSO_DAYS,
    ventas_netas: Optional[float] = None,
    include_dso: bool = True,
) -> Dict[str, Any]:
    """Pure builder: assemble full report dict from snapshot rows (+ optional sales)."""
    as_of = validate_as_of_date(as_of_date)
    clients = aggregate_clients(rows)
    fecha_carga = None
    if rows:
        fecha_carga = rows[0].get("fecha_carga")
        for r in rows:
            fc = r.get("fecha_carga")
            if fc is not None and (fecha_carga is None or str(fc) > str(fecha_carga)):
                fecha_carga = fc

    dso_val: Optional[float] = None
    ventas = ventas_netas
    if include_dso and ventas is not None:
        dso_val = compute_dso(
            sum(_as_float(c.get("total")) for c in clients),
            float(ventas),
            int(dso_days),
        )

    summary = compute_summary(
        clients,
        document_row_count=len(rows),
        dso_dias=dso_val,
        ventas_netas=ventas,
        dias_periodo=int(dso_days),
        fecha_carga=fecha_carga,
    )
    # Fill share on all clients for consumers
    total_ar = _as_float(summary.get("Cartera_Total")) or 1.0
    for c in clients:
        c["share_total"] = safe_divide(_as_float(c.get("total")), total_ar)

    return {
        "as_of_date": as_of,
        "fecha_carga_snapshot": fecha_carga,
        "source": "banco_cartera",
        "dso_days_window": int(dso_days),
        "include_dso": bool(include_dso),
        "excluded_document_codes": list(CANONICAL_EXCLUDED_DOCUMENT_CODES),
        "summary": summary,
        "buckets": bucket_breakdown(summary),
        "top_overdue": top_overdue(clients, top_n=top_n),
        "top_concentration": top_concentration(clients, top_n=top_n),
        "over_limit": over_limit_clients(clients, top_n=top_n),
        "by_vendedor": by_vendedor(clients),
        "client_count": len(clients),
        "document_row_count": len(rows),
    }


class CarteraAgingRunner:
    """Fetch latest AR snapshot and assemble the aging report."""

    def __init__(
        self,
        db: Optional[Database] = None,
        *,
        sb_database: Optional[str] = None,
        top_n: int = DEFAULT_TOP_N,
        dso_days: int = DEFAULT_DSO_DAYS,
        include_dso: bool = True,
    ) -> None:
        self.db = db or Database()
        self.sb_database = sb_database
        self.top_n = int(top_n)
        self.dso_days = int(dso_days)
        self.include_dso = bool(include_dso)

    def _execute_query(self, sql: str) -> List[Dict[str, Any]]:
        self.db.connect()
        rows = cast(List[Dict[str, Any]], self.db.execute_query(sql))
        return [dict(row) for row in rows]

    def fetch_snapshot_rows(
        self, as_of_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        sql = build_snapshot_sql(as_of_date=as_of_date, sb_database=self.sb_database)
        return self._execute_query(sql)

    def fetch_ventas_netas(self, as_of_date: str) -> tuple[float, int]:
        sql = build_dso_sales_sql(
            as_of_date=as_of_date,
            dso_days=self.dso_days,
            sb_database=self.sb_database,
        )
        rows = self._execute_query(sql)
        if not rows:
            return 0.0, self.dso_days
        row = rows[0]
        return (
            _as_float(row.get("ventas_netas")),
            _as_int(row.get("dias_periodo")) or self.dso_days,
        )

    def build_report(self, as_of_date: str) -> Dict[str, Any]:
        as_of = validate_as_of_date(as_of_date)
        rows = self.fetch_snapshot_rows(as_of)
        ventas: Optional[float] = None
        if self.include_dso:
            ventas, _ = self.fetch_ventas_netas(as_of)
        return build_report_from_rows(
            rows,
            as_of_date=as_of,
            top_n=self.top_n,
            dso_days=self.dso_days,
            ventas_netas=ventas,
            include_dso=self.include_dso,
        )
