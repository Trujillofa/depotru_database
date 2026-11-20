"""Materializa la afinidad de canasta en ``advisor_cross_sell_affinity``.

Lee **sólo** de J3 (``SmartBusiness.dbo.banco_datos``); nunca escribe en J3.
El destino es la tabla precalculada del asesor (Postgres/Neon) o un SQLite de
demo. Sin ``--apply`` el comando es un dry-run: mide y muestra, no escribe.

Uso típico::

    PYTHONPATH=src .venv/bin/python -m business_analyzer.jobs.cross_sell_affinity
    PYTHONPATH=src .venv/bin/python -m business_analyzer.jobs.cross_sell_affinity \
        --apply --env-file ~/Projects/depotru-inbox-prod/.env.local

La ventana se cuenta desde ``--as-of`` (hoy por defecto) hacia atrás. La canasta
es ``(DocumentosCodigo, NumeroDocumento)``; se descartan canastas de más de 40
líneas porque una remisión o un traslado no dicen nada de afinidad.
"""

from __future__ import annotations

import argparse
import calendar
import json
import math
import os
import sqlite3
import sys
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Mapping, Sequence

from business_analyzer.core.database import Database
from depotru_integrations.affinity.store import (
    DATABASE_URL_ENV,
    FALLBACK_DATABASE_URL_ENV,
    SQLITE_ENV,
    AffinityRecord,
    AffinityStore,
    AffinityStoreError,
    PostgresAffinityStore,
    SqliteAffinityStore,
    configured_store,
)
from depotru_kernel.documents import excluded_document_sql_in_list

WINDOW_MONTHS = 12
MIN_BASKETS = 20
MAX_BASKET_LINES = 40
SOURCE_TABLE = "SmartBusiness.dbo.banco_datos"
SQLITE_SOURCE_TABLE = "banco_datos"
DEFAULT_SAMPLE = 5

#: CTE sobre la fuente de ventas. Sólo SELECT: el job no puede escribir en J3.
MATERIALIZE_SQL = """
WITH lineas AS (
    SELECT
        DocumentosCodigo AS doc,
        NumeroDocumento AS num,
        ArticulosCodigo AS sku,
        MAX(ArticulosNombre) AS nombre,
        SUM(Cantidad) AS qty
    FROM __TABLE__
    WHERE Fecha >= __P__
      AND Cantidad > 0
      AND DocumentosCodigo NOT IN (__EXCLUDED_DOCS__)
    GROUP BY DocumentosCodigo, NumeroDocumento, ArticulosCodigo
),
canastas AS (
    SELECT doc, num
    FROM lineas
    GROUP BY doc, num
    HAVING COUNT(*) BETWEEN 2 AND __MAX_LINES__
),
pares AS (
    SELECT
        a.sku AS sku,
        MAX(a.nombre) AS sku_name,
        b.sku AS complement_sku,
        MAX(b.nombre) AS complement_name,
        COUNT(*) AS baskets
    FROM lineas a
    JOIN canastas k ON k.doc = a.doc AND k.num = a.num
    JOIN lineas b ON b.doc = a.doc AND b.num = a.num AND b.sku <> a.sku
    GROUP BY a.sku, b.sku
    HAVING COUNT(*) >= __P__
),
sku_totales AS (
    SELECT l.sku, COUNT(*) AS baskets_sku
    FROM lineas l
    JOIN canastas k ON k.doc = l.doc AND k.num = l.num
    GROUP BY l.sku
),
total_canastas AS (
    SELECT COUNT(*) AS n FROM canastas
)
SELECT
    p.sku AS sku,
    p.sku_name AS sku_name,
    p.complement_sku AS complement_sku,
    p.complement_name AS complement_name,
    p.baskets AS baskets,
    1.0 * p.baskets / st.baskets_sku AS confidence,
    (1.0 * p.baskets / st.baskets_sku)
        / (1.0 * ct.baskets_sku / tc.n) AS lift
FROM pares p
JOIN sku_totales st ON st.sku = p.sku
JOIN sku_totales ct ON ct.sku = p.complement_sku
CROSS JOIN total_canastas tc
ORDER BY p.sku, p.baskets DESC, p.complement_sku
__OPTION__
""".replace(
    "__EXCLUDED_DOCS__", excluded_document_sql_in_list()
)


class AffinityJobError(RuntimeError):
    """El job no pudo medir o escribir la tabla."""


def build_affinity_sql(
    *,
    table: str = SOURCE_TABLE,
    placeholder: str = "%s",
) -> str:
    """SQL canónico. ``table`` y ``placeholder`` son constantes internas."""
    if table not in {SOURCE_TABLE, SQLITE_SOURCE_TABLE}:
        raise ValueError("source_table inválida")
    if placeholder not in {"%s", "?"}:
        raise ValueError("placeholder inválido")
    return (
        MATERIALIZE_SQL.replace("__TABLE__", table)
        .replace("__MAX_LINES__", str(int(MAX_BASKET_LINES)))
        .replace("__P__", placeholder)
        .replace(
            "__OPTION__",
            "OPTION (FORCE ORDER)" if table == SOURCE_TABLE else "",
        )
    )


def _cutoff(as_of: date, months: int) -> datetime:
    # Mes calendario exacto, sin el error de 30 días: 12 meses son 12 meses.
    month_index = as_of.year * 12 + (as_of.month - 1) - months
    year, month = divmod(month_index, 12)
    month += 1
    day = min(as_of.day, calendar.monthrange(year, month)[1])
    return datetime.combine(date(year, month, day), time.min)


def _read_env_file(path: str | os.PathLike[str]) -> dict[str, str]:
    """Lee sólo las llaves de destino de un .env; no carga el resto."""
    wanted = {DATABASE_URL_ENV, FALLBACK_DATABASE_URL_ENV, SQLITE_ENV}
    values: dict[str, str] = {}
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in wanted:
            continue
        cleaned = value.strip().strip('"').strip("'")
        if cleaned:
            values[key] = cleaned
    return values


def _to_record(row: Mapping[str, Any], window_months: int) -> AffinityRecord:
    return AffinityRecord(
        sku=str(row.get("sku") or "").strip(),
        complement_sku=str(row.get("complement_sku") or "").strip(),
        sku_name=str(row.get("sku_name") or "").strip(),
        complement_name=str(row.get("complement_name") or "").strip(),
        baskets=int(row.get("baskets") or 0),
        confidence=float(row.get("confidence") or 0.0),
        lift=float(row.get("lift") or 0.0),
        window_months=window_months,
    )


def compute_records(
    *,
    months: int = WINDOW_MONTHS,
    min_baskets: int = MIN_BASKETS,
    as_of: date | None = None,
    source_sqlite: str | os.PathLike[str] | None = None,
) -> list[AffinityRecord]:
    """Mide los pares en J3 (o en un SQLite de prueba) y los normaliza."""
    if months < 1 or months > 60:
        raise AffinityJobError("months debe estar entre 1 y 60")
    if min_baskets < 1 or min_baskets > 100_000:
        raise AffinityJobError("min_baskets debe estar entre 1 y 100000")
    cutoff = _cutoff(as_of or date.today(), months)

    rows: Sequence[Mapping[str, Any]]
    if source_sqlite:
        sql = build_affinity_sql(table=SQLITE_SOURCE_TABLE, placeholder="?")
        conn = sqlite3.connect(str(source_sqlite))
        conn.row_factory = sqlite3.Row
        try:
            rows = [
                dict(row)
                for row in conn.execute(
                    sql, (cutoff.date().isoformat(), min_baskets)
                ).fetchall()
            ]
        except sqlite3.Error as exc:
            raise AffinityJobError(f"sqlite_source_error: {exc}") from exc
        finally:
            conn.close()
    else:
        sql = build_affinity_sql()
        try:
            with Database() as db:
                raw_rows = db.execute_query(sql, (cutoff, min_baskets))
        except Exception as exc:  # noqa: BLE001 - el job informa, no adivina
            raise AffinityJobError(f"j3_unavailable: {type(exc).__name__}") from exc
        if not isinstance(raw_rows, list):
            raise AffinityJobError("j3_query_sin_filas")
        rows = raw_rows

    records: dict[tuple[str, str], AffinityRecord] = {}
    for row in rows:
        record = _to_record(row, months)
        if not record.sku or not record.complement_sku:
            raise AffinityJobError("fila sin sku o complement_sku")
        if record.sku == record.complement_sku:
            raise AffinityJobError(f"par reflexivo: {record.sku}")
        if record.baskets < min_baskets:
            raise AffinityJobError(
                f"par {record.sku}->{record.complement_sku} con "
                f"{record.baskets} < {min_baskets} canastas"
            )
        if not (0.0 < record.confidence <= 1.0):
            raise AffinityJobError(
                f"confidence fuera de rango: {record.sku}->{record.complement_sku}"
            )
        if not math.isfinite(record.lift) or record.lift <= 0.0:
            raise AffinityJobError(
                f"lift fuera de rango: {record.sku}->{record.complement_sku}"
            )
        key = (record.sku, record.complement_sku)
        previous = records.get(key)
        if previous is None or record.baskets > previous.baskets:
            records[key] = record

    return sorted(
        records.values(),
        key=lambda record: (record.sku, -record.baskets, record.complement_sku),
    )


def _resolve_store(
    *,
    target_sqlite: str | os.PathLike[str] | None,
    database_url: str | None,
) -> AffinityStore | None:
    if target_sqlite:
        return SqliteAffinityStore(target_sqlite)
    if database_url:
        return PostgresAffinityStore(database_url)
    return configured_store()


def run_job(
    *,
    months: int = WINDOW_MONTHS,
    min_baskets: int = MIN_BASKETS,
    as_of: date | None = None,
    source_sqlite: str | os.PathLike[str] | None = None,
    target_sqlite: str | os.PathLike[str] | None = None,
    database_url: str | None = None,
    apply: bool = False,
    sample: int = DEFAULT_SAMPLE,
    category_snapshot: str | None = None,
) -> dict[str, Any]:
    """Mide y, sólo con ``apply=True``, reemplaza la tabla destino."""
    store = _resolve_store(target_sqlite=target_sqlite, database_url=database_url)
    if apply and store is None:
        raise AffinityJobError(
            "sin destino: usa --target-sqlite, --database-url o ADVISOR_DATABASE_URL"
        )

    records = compute_records(
        months=months,
        min_baskets=min_baskets,
        as_of=as_of,
        source_sqlite=source_sqlite,
    )

    category_products = None
    if category_snapshot:
        if months != WINDOW_MONTHS or source_sqlite:
            raise AffinityJobError("category snapshot requires 12 months and J3 source")
        from business_analyzer.jobs.category_snapshot import compute_category_snapshot

        category_products = compute_category_snapshot(as_of=as_of)

    current_rows: int | None = None
    if store is not None:
        try:
            current_rows = store.count()
        except AffinityStoreError:
            current_rows = None

    target_kind: str | None = None
    if store is not None:
        target_kind = "sqlite" if isinstance(store, SqliteAffinityStore) else "postgres"

    result: dict[str, Any] = {
        "window_months": months,
        "min_baskets": min_baskets,
        "as_of": (as_of or date.today()).isoformat(),
        "pairs": len(records),
        "skus": len({record.sku for record in records}),
        "complements": len({record.complement_sku for record in records}),
        "target": target_kind,
        "rows_before": current_rows,
        "applied": False,
    }

    if apply:
        assert store is not None  # validado arriba
        written = store.replace_all(
            records,
            window_months=months,
            updated_at=datetime.now().astimezone(),
        )
        rows_after = store.count()
        if rows_after != len(records):
            raise AffinityJobError(
                f"verificación falló: escribí {written} y la tabla tiene {rows_after}"
            )
        result.update(
            {
                "applied": True,
                "rows_written": written,
                "rows_after": rows_after,
            }
        )

    result["sample"] = [
        {
            "sku": record.sku,
            "complement_sku": record.complement_sku,
            "name": record.complement_name,
            "baskets": record.baskets,
            "lift": round(record.lift, 4),
        }
        for record in sorted(records, key=lambda item: (-item.baskets, -item.lift))[
            : max(0, int(sample))
        ]
    ]
    if category_products is not None:
        result["category_snapshot_products"] = len(category_products)
        result["category_snapshot_applied"] = False
        if apply:
            from depotru_integrations.affinity.category_snapshot import write_snapshot

            assert category_snapshot is not None
            write_snapshot(category_products, Path(category_snapshot))
            result["category_snapshot_applied"] = True
    return result


def _print_human(result: Mapping[str, Any]) -> None:
    print(
        f"Afinidad de canasta — {result['window_months']} meses "
        f"(desde {result['as_of']}), >= {result['min_baskets']} canastas"
    )
    print(
        f"Pares: {result['pairs']} | SKU ancla: {result['skus']} | "
        f"complementos: {result['complements']}"
    )
    target = result.get("target") or "sin destino"
    before = result.get("rows_before")
    print(
        f"Destino: {target} (tabla advisor_cross_sell_affinity) — "
        + (f"{before} filas actuales" if before is not None else "no configurado")
    )
    for item in result.get("sample") or []:
        print(
            f"  {item['sku']} -> {item['complement_sku']} "
            f"({item['baskets']} canastas, lift {item['lift']})"
        )
    if result.get("applied"):
        print(
            f"APLICADO: {result['rows_written']} filas escritas; "
            f"verificación: {result['rows_after']} en la tabla."
        )
    else:
        print("DRY-RUN: no se escribió nada (usa --apply para reemplazar la tabla).")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="depotru-cross-sell-affinity",
        description=(
            "Materializa la afinidad de canasta de J3 en "
            "advisor_cross_sell_affinity. Dry-run por defecto."
        ),
    )
    parser.add_argument("--months", type=int, default=WINDOW_MONTHS)
    parser.add_argument("--min-baskets", type=int, default=MIN_BASKETS)
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=None,
        help="fecha de corte de la ventana (YYYY-MM-DD); por defecto hoy",
    )
    parser.add_argument(
        "--source-sqlite",
        default=None,
        help="fuente SQLite de demo/pruebas (nunca se usa en producción)",
    )
    parser.add_argument(
        "--target-sqlite",
        default=None,
        help="destino SQLite de demo/pruebas",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Postgres/Neon del asesor (por defecto ADVISOR_DATABASE_URL)",
    )
    parser.add_argument(
        "--env-file",
        default=None,
        help="archivo .env del que leer DATABASE_URL/ADVISOR_DATABASE_URL",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="escribir la tabla; sin este flag el job es dry-run",
    )
    parser.add_argument("--sample", type=int, default=DEFAULT_SAMPLE)
    parser.add_argument(
        "--category-snapshot",
        default=None,
        metavar="PATH",
        help="add individual-invoice/public-price snapshot (writes only with --apply)",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.env_file:
        for key, value in _read_env_file(args.env_file).items():
            os.environ[key] = value
    try:
        result = run_job(
            months=args.months,
            min_baskets=args.min_baskets,
            as_of=args.as_of,
            source_sqlite=args.source_sqlite,
            target_sqlite=args.target_sqlite,
            database_url=args.database_url,
            apply=args.apply,
            sample=args.sample,
            category_snapshot=args.category_snapshot,
        )
    except Exception as exc:  # noqa: BLE001 - CLI: mensaje claro y código 1
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_human(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
