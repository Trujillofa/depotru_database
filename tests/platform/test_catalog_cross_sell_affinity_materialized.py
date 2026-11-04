"""Afinidad materializada: carga SQLite, lectura BFF y fallback a J3.

La tabla real vive en el Postgres/Neon del asesor; aquí se usa SQLite con el
mismo contrato para verificar la carga completa sin red ni J3.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime, timezone

import pytest

from business_analyzer.jobs import cross_sell_affinity as job
from depotru_integrations.affinity.store import (
    DATABASE_URL_ENV,
    FALLBACK_DATABASE_URL_ENV,
    SQLITE_ENV,
    AffinityRecord,
    PostgresAffinityStore,
    SqliteAffinityStore,
)
from depotru_integrations.j3 import affinity as affinity_module
from depotru_kernel.auth import Audience
from depotru_tools.builtins import _tool_cross_sell_affinity
from depotru_tools.registry import ToolContext

CTX = ToolContext(audience=Audience.PUBLIC)
AS_OF = date(2026, 11, 1)


def _line(
    rows: list[tuple[str, str, str, str, str, float]],
    doc: str,
    num: str,
    fecha: str,
    sku: str,
    name: str,
    qty: float = 1.0,
) -> None:
    rows.append((doc, num, fecha, sku, name, qty))


def _make_source(path) -> None:
    """Cuatro canastas válidas + una vieja, una en cero y una de 41 líneas."""
    rows: list[tuple[str, str, str, str, str, float]] = []
    _line(rows, "F1", "1", "2026-06-01", "A", "Cemento Gris", 2)
    _line(rows, "F1", "1", "2026-06-01", "B", "Barra Corrugada", 3)
    _line(rows, "F1", "1", "2026-06-01", "C", "Malla Electrosoldada", 1)
    _line(rows, "F1", "2", "2026-06-02", "A", "Cemento Gris", 1)
    _line(rows, "F1", "2", "2026-06-02", "B", "Barra Corrugada", 4)
    _line(rows, "F1", "3", "2026-06-03", "A", "Cemento Gris", 1)
    _line(rows, "F1", "3", "2026-06-03", "B", "Barra Corrugada", 1)
    _line(rows, "F1", "3", "2026-06-03", "D", "Tubo Presión", 1)
    _line(rows, "F1", "4", "2026-06-04", "A", "Cemento Gris", 1)
    _line(rows, "F1", "4", "2026-06-04", "C", "Malla Electrosoldada", 2)
    # Fuera de la ventana de 12 meses: no debe entrar.
    _line(rows, "F1", "5", "2023-01-01", "A", "Cemento Gris", 1)
    _line(rows, "F1", "5", "2023-01-01", "B", "Barra Corrugada", 1)
    # Cantidad 0: no es venta.
    _line(rows, "F1", "6", "2026-06-05", "A", "Cemento Gris", 0)
    _line(rows, "F1", "6", "2026-06-05", "B", "Barra Corrugada", 0)
    # Canasta de 41 líneas: remisión/traslado, no afinidad.
    _line(rows, "F1", "7", "2026-06-06", "A", "Cemento Gris", 1)
    for index in range(40):
        _line(
            rows,
            "F1",
            "7",
            "2026-06-06",
            f"X{index:02d}",
            f"Relleno {index}",
            1,
        )

    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE banco_datos ("
            "DocumentosCodigo TEXT, NumeroDocumento TEXT, Fecha TEXT, "
            "ArticulosCodigo TEXT, ArticulosNombre TEXT, Cantidad REAL)"
        )
        conn.executemany("INSERT INTO banco_datos VALUES (?, ?, ?, ?, ?, ?)", rows)
        conn.commit()
    finally:
        conn.close()


def _run_apply(source, target) -> dict:
    return job.run_job(
        as_of=AS_OF,
        min_baskets=2,
        source_sqlite=source,
        target_sqlite=target,
        apply=True,
    )


@pytest.fixture()
def source(tmp_path):
    path = tmp_path / "source.sqlite3"
    _make_source(path)
    return path


@pytest.fixture()
def target(tmp_path):
    return tmp_path / "target.sqlite3"


@pytest.mark.unit
def test_job_loads_pairs_with_confidence_and_lift(source, target):
    result = _run_apply(source, target)

    assert result["applied"] is True
    assert result["pairs"] == 4
    assert result["rows_after"] == 4

    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM advisor_cross_sell_affinity ORDER BY sku, complement_sku"
        ).fetchall()
    finally:
        conn.close()

    by_pair = {(row["sku"], row["complement_sku"]): row for row in rows}
    assert set(by_pair) == {("A", "B"), ("A", "C"), ("B", "A"), ("C", "A")}

    ab = by_pair[("A", "B")]
    assert ab["sku_name"] == "Cemento Gris"
    assert ab["complement_name"] == "Barra Corrugada"
    assert ab["baskets"] == 3
    assert ab["confidence"] == pytest.approx(0.75)
    assert ab["lift"] == pytest.approx(1.0)
    assert ab["window_months"] == 12
    assert ab["updated_at"]

    # La canasta vieja, la de cantidad cero y la de 41 líneas no entraron.
    assert by_pair[("A", "C")]["baskets"] == 2
    assert not any(key[1] in {"D", "X00"} for key in by_pair)


@pytest.mark.unit
def test_apply_replaces_the_whole_table_atomically(source, target):
    _run_apply(source, target)

    # Cambia la fuente: la canasta 3 desaparece. El job debe reemplazar, no sumar.
    conn = sqlite3.connect(source)
    try:
        conn.execute("DELETE FROM banco_datos WHERE NumeroDocumento = '3'")
        conn.commit()
    finally:
        conn.close()

    result = _run_apply(source, target)
    assert result["rows_after"] == 4

    conn = sqlite3.connect(target)
    try:
        ab = conn.execute(
            "SELECT baskets FROM advisor_cross_sell_affinity "
            "WHERE sku = 'A' AND complement_sku = 'B'"
        ).fetchone()
        total = conn.execute(
            "SELECT COUNT(*) FROM advisor_cross_sell_affinity"
        ).fetchone()[0]
    finally:
        conn.close()
    assert ab[0] == 2
    assert total == 4


@pytest.mark.unit
def test_dry_run_never_writes(source, target):
    store = SqliteAffinityStore(target)
    store.replace_all(
        [
            AffinityRecord(
                sku="ZZ",
                complement_sku="YY",
                sku_name="Viejo",
                complement_name="Sentinela",
                baskets=99,
                confidence=0.9,
                lift=2.0,
            )
        ],
        window_months=12,
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    result = job.run_job(
        as_of=AS_OF,
        min_baskets=2,
        source_sqlite=source,
        target_sqlite=target,
        apply=False,
    )

    assert result["applied"] is False
    assert result["rows_before"] == 1
    assert store.count() == 1
    assert store.top_for_sku("ZZ", 5)[0].complement_sku == "YY"


@pytest.mark.unit
def test_cli_dry_run_says_so_and_leaves_table_untouched(source, target, capsys):
    store = SqliteAffinityStore(target)
    store.replace_all(
        [],
        window_months=12,
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    code = job.main(
        [
            "--source-sqlite",
            str(source),
            "--target-sqlite",
            str(target),
            "--min-baskets",
            "2",
            "--as-of",
            "2026-11-01",
        ]
    )

    assert code == 0
    assert "DRY-RUN" in capsys.readouterr().out
    assert store.count() == 0


@pytest.mark.unit
def test_tool_reads_the_precomputed_table_without_touching_j3(
    source, target, monkeypatch
):
    _run_apply(source, target)
    monkeypatch.setenv(SQLITE_ENV, str(target))
    monkeypatch.delenv(DATABASE_URL_ENV, raising=False)
    monkeypatch.delenv(FALLBACK_DATABASE_URL_ENV, raising=False)
    affinity_module._cached.cache_clear()

    def no_j3(sku, limit):  # pragma: no cover - debe fallar si se llama
        raise AssertionError("la tabla precalculada debía evitar la consulta a J3")

    monkeypatch.setattr(affinity_module, "_fetch", no_j3)

    result = _tool_cross_sell_affinity(CTX, {"sku": "A", "limit": 5})

    assert result["status"] == "ok"
    assert result["source"] == "precomputed"
    assert result["source_table"] == "advisor_cross_sell_affinity"
    assert [p["sku"] for p in result["products"]] == ["B", "C"]
    assert result["products"][0]["baskets"] == 3
    assert result["products"][0]["name"] == "Barra Corrugada"
    assert "table_status" not in result


@pytest.mark.unit
def test_empty_table_falls_back_to_live_j3(target, monkeypatch):
    SqliteAffinityStore(target).replace_all(
        [],
        window_months=12,
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    monkeypatch.setenv(SQLITE_ENV, str(target))
    monkeypatch.delenv(DATABASE_URL_ENV, raising=False)
    monkeypatch.delenv(FALLBACK_DATABASE_URL_ENV, raising=False)
    affinity_module._cached.cache_clear()
    monkeypatch.setattr(
        affinity_module,
        "_fetch",
        lambda sku, limit: [("Z", "Producto en vivo", 25)],
    )

    result = _tool_cross_sell_affinity(CTX, {"sku": "A", "limit": 5})

    assert result["status"] == "ok"
    assert result["source"] == "j3_baskets"
    assert result["table_status"] == "table_empty"
    assert result["products"] == [
        {"sku": "Z", "name": "Producto en vivo", "baskets": 25, "relation": "basket"}
    ]


@pytest.mark.unit
def test_unreadable_table_falls_back_to_live_j3(tmp_path, monkeypatch):
    broken = tmp_path / "broken.sqlite3"
    conn = sqlite3.connect(broken)
    try:
        conn.execute("CREATE TABLE otra_cosa (id INTEGER)")
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setenv(SQLITE_ENV, str(broken))
    monkeypatch.delenv(DATABASE_URL_ENV, raising=False)
    monkeypatch.delenv(FALLBACK_DATABASE_URL_ENV, raising=False)
    affinity_module._cached.cache_clear()
    monkeypatch.setattr(
        affinity_module,
        "_fetch",
        lambda sku, limit: [("Z", "Producto en vivo", 25)],
    )

    result = _tool_cross_sell_affinity(CTX, {"sku": "A", "limit": 5})

    assert result["source"] == "j3_baskets"
    assert result["table_status"].startswith("table_unavailable:")
    assert result["products"][0]["sku"] == "Z"


@pytest.mark.unit
def test_env_file_overrides_an_ambient_database_url(
    source, target, tmp_path, monkeypatch, capsys
):
    env_file = tmp_path / "job.env"
    env_file.write_text(
        f"{FALLBACK_DATABASE_URL_ENV}=postgresql://file/neondb\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(FALLBACK_DATABASE_URL_ENV, "postgresql://ambient/otra")

    code = job.main(
        [
            "--env-file",
            str(env_file),
            "--source-sqlite",
            str(source),
            "--target-sqlite",
            str(target),
            "--min-baskets",
            "2",
            "--as-of",
            "2026-11-01",
            "--json",
        ]
    )

    assert code == 0
    assert os.environ[FALLBACK_DATABASE_URL_ENV] == "postgresql://file/neondb"
    capsys.readouterr()


@pytest.mark.unit
def test_cutoff_uses_calendar_months_not_30_day_arithmetic():
    assert job._cutoff(date(2026, 11, 3), 12) == datetime(2025, 11, 3)
    assert job._cutoff(date(2026, 3, 31), 1) == datetime(2026, 2, 28)
    assert job._cutoff(date(2024, 2, 29), 12) == datetime(2023, 2, 28)


@pytest.mark.unit
def test_materialize_sql_is_read_only():
    sql = job.build_affinity_sql()
    upper = sql.upper()
    for forbidden in (
        "INSERT",
        "UPDATE",
        "DELETE",
        "MERGE",
        "DROP",
        "ALTER",
        "CREATE",
        "TRUNCATE",
        "EXEC",
    ):
        assert forbidden not in upper
    assert "SMARTBUSINESS.DBO.BANCO_DATOS" in upper


@pytest.mark.unit
def test_sqlite_source_never_opens_j3(source, monkeypatch):
    class NoJ3:
        def __enter__(self):
            raise AssertionError("la fuente SQLite no debe abrir J3")

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(job, "Database", NoJ3)
    records = job.compute_records(
        as_of=AS_OF,
        min_baskets=2,
        source_sqlite=source,
    )
    assert len(records) == 4


@pytest.mark.unit
def test_postgres_write_is_one_transaction_and_uses_stdin_copy(monkeypatch):
    store = PostgresAffinityStore(
        "postgresql://user:secret@db.example/neondb?sslmode=require",
        psql="/usr/bin/psql",
    )
    captured: dict[str, str] = {}

    def fake_run(sql: str, **kwargs) -> str:
        captured["sql"] = sql
        return ""

    monkeypatch.setattr(store, "_run", fake_run)
    store.replace_all(
        [
            AffinityRecord(
                sku="A",
                complement_sku="B",
                sku_name="Cemento",
                complement_name="Barra",
                baskets=30,
                confidence=0.5,
                lift=1.7,
            )
        ],
        window_months=12,
        updated_at=datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc),
    )

    sql = captured["sql"]
    assert sql.startswith("BEGIN;\n")
    assert "DELETE FROM advisor_cross_sell_affinity;" in sql
    assert "COPY advisor_cross_sell_affinity" in sql
    assert "FROM STDIN WITH (FORMAT csv);" in sql
    assert sql.rstrip().endswith("COMMIT;")
    assert "\nA,B,Cemento,Barra,30,0.500000,1.700000,12," in sql


@pytest.mark.unit
def test_postgres_password_never_goes_in_argv():
    store = PostgresAffinityStore(
        "postgresql://user:secret@db.example/neondb?sslmode=require",
        psql="/usr/bin/psql",
    )
    args, env = store._client()

    assert "secret" not in " ".join(args)
    assert env["PGPASSWORD"] == "secret"
    assert env["PGSSLMODE"] == "require"
