"""Almacén materializado de afinidad de canasta (tabla 035 del asesor).

La tabla ``advisor_cross_sell_affinity`` vive en el Postgres/Neon del asesor.
El job nocturno la reemplaza completa en una transacción; el BFF la lee antes
de gastar la consulta en vivo contra J3.

El destino real se atiende con ``psql`` (ya instalado en la máquina del BFF)
para no añadir un driver Postgres al servicio. SQLite es el destino de demo y
pruebas: mismo contrato, sin red.
"""

from __future__ import annotations

import csv
import io
import os
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping, Protocol, Sequence
from urllib.parse import parse_qs, unquote, urlsplit

TABLE = "advisor_cross_sell_affinity"
SQLITE_ENV = "ADVISOR_AFFINITY_SQLITE"
DATABASE_URL_ENV = "ADVISOR_DATABASE_URL"
FALLBACK_DATABASE_URL_ENV = "DATABASE_URL"

_DEFAULT_TIMEOUT_SECONDS = 8  # lectura BFF: si Neon no responde, cae a J3 rápido

_SQLITE_DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    sku TEXT NOT NULL,
    complement_sku TEXT NOT NULL,
    sku_name TEXT,
    complement_name TEXT,
    baskets INTEGER NOT NULL CHECK (baskets > 0),
    confidence REAL NOT NULL CHECK (confidence > 0 AND confidence <= 1),
    lift REAL NOT NULL CHECK (lift > 0),
    window_months INTEGER NOT NULL DEFAULT 12,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (sku, complement_sku)
)
"""

_SQLITE_INSERT = f"""
INSERT INTO {TABLE} (
    sku, complement_sku, sku_name, complement_name,
    baskets, confidence, lift, window_months, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_SQLITE_SELECT = f"""
SELECT sku, sku_name, complement_sku, complement_name,
       baskets, confidence, lift, window_months
FROM {TABLE}
WHERE sku = ?
ORDER BY baskets DESC, lift DESC, complement_sku
LIMIT ?
"""


class AffinityStoreError(RuntimeError):
    """El destino no está disponible o no se pudo escribir/leer."""


@dataclass(frozen=True)
class AffinityRecord:
    """Una fila de la tabla: sólo relación y conteos, nunca precios."""

    sku: str
    complement_sku: str
    sku_name: str
    complement_name: str
    baskets: int
    confidence: float
    lift: float
    window_months: int = 12


class AffinityStore(Protocol):
    """Contrato mínimo que comparten SQLite (demo) y Postgres (asesor)."""

    def replace_all(
        self,
        records: Sequence[AffinityRecord],
        *,
        window_months: int,
        updated_at: datetime,
    ) -> int:
        ...

    def top_for_sku(self, sku: str, limit: int = 5) -> list[AffinityRecord]:
        ...

    def count(self) -> int:
        ...


def _as_record(row: Mapping[str, object], window_months: int) -> AffinityRecord:
    try:
        stored_window = int(str(row["window_months"] or window_months))
    except (KeyError, IndexError):
        stored_window = window_months
    return AffinityRecord(
        sku=str(row["sku"] or "").strip(),
        complement_sku=str(row["complement_sku"] or "").strip(),
        sku_name=str(row["sku_name"] or "").strip(),
        complement_name=str(row["complement_name"] or "").strip(),
        baskets=int(str(row["baskets"])),
        confidence=float(str(row["confidence"])),
        lift=float(str(row["lift"])),
        window_months=stored_window,
    )


class SqliteAffinityStore:
    """Destino de demo/pruebas. Crea la tabla si no existe."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = str(path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_parent(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)

    def replace_all(
        self,
        records: Sequence[AffinityRecord],
        *,
        window_months: int,
        updated_at: datetime,
    ) -> int:
        self._ensure_parent()
        conn = self._connect()
        try:
            with conn:
                conn.execute(_SQLITE_DDL)
                conn.execute(f"DELETE FROM {TABLE}")
                conn.executemany(
                    _SQLITE_INSERT,
                    [
                        (
                            record.sku,
                            record.complement_sku,
                            record.sku_name or None,
                            record.complement_name or None,
                            record.baskets,
                            record.confidence,
                            record.lift,
                            window_months,
                            updated_at.isoformat(),
                        )
                        for record in records
                    ],
                )
        finally:
            conn.close()
        return len(records)

    def top_for_sku(self, sku: str, limit: int = 5) -> list[AffinityRecord]:
        if not Path(self.path).exists():
            raise AffinityStoreError("sqlite_missing")
        conn = self._connect()
        try:
            rows = conn.execute(_SQLITE_SELECT, (sku, max(1, int(limit)))).fetchall()
        except sqlite3.Error as exc:
            raise AffinityStoreError(f"sqlite_error: {type(exc).__name__}") from exc
        finally:
            conn.close()
        return [_as_record(row, 12) for row in rows]

    def count(self) -> int:
        if not Path(self.path).exists():
            return 0
        conn = self._connect()
        try:
            row = conn.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()
        except sqlite3.Error as exc:
            raise AffinityStoreError(f"sqlite_error: {type(exc).__name__}") from exc
        finally:
            conn.close()
        return int(row[0]) if row else 0


class PostgresAffinityStore:
    """Destino real (Neon/Postgres del asesor), hablado con ``psql``.

    La URL se descompone para pasar la contraseña por ``PGPASSWORD`` y no en
    ``argv``. El reemplazo es ``DELETE`` + ``COPY`` dentro de una transacción:
    o queda la tabla nueva completa, o queda la anterior.
    """

    def __init__(self, url: str, *, psql: str | None = None) -> None:
        cleaned = (url or "").strip()
        scheme = urlsplit(cleaned).scheme.lower().split("+", 1)[0]
        if scheme not in {"postgres", "postgresql"}:
            raise AffinityStoreError("database_url_invalid")
        self.url = cleaned
        self.psql = psql or shutil.which("psql") or ""

    def _client(self) -> tuple[list[str], dict[str, str]]:
        if not self.psql:
            raise AffinityStoreError("psql_missing")
        parsed = urlsplit(self.url)
        args = [self.psql, "-X", "-q", "-v", "ON_ERROR_STOP=1", "--csv", "-t"]
        if parsed.hostname:
            args += ["-h", parsed.hostname]
        if parsed.port:
            args += ["-p", str(parsed.port)]
        if parsed.username:
            args += ["-U", unquote(parsed.username)]
        database = unquote(parsed.path.lstrip("/"))
        if database:
            args += ["-d", database]
        env = os.environ.copy()
        if parsed.password:
            env["PGPASSWORD"] = unquote(parsed.password)
        query = parse_qs(parsed.query)
        if query.get("sslmode"):
            env["PGSSLMODE"] = query["sslmode"][0]
        if query.get("channel_binding"):
            env["PGCHANNELBINDING"] = query["channel_binding"][0]
        return args, env

    def _run(
        self,
        sql: str,
        *,
        variables: Mapping[str, str] | None = None,
        timeout: int = _DEFAULT_TIMEOUT_SECONDS,
    ) -> str:
        args, env = self._client()
        for key, value in (variables or {}).items():
            args += ["-v", f"{key}={value}"]
        args += ["-f", "-"]
        try:
            proc = subprocess.run(  # noqa: S603 - args list, no shell
                args,
                input=sql,
                text=True,
                capture_output=True,
                env=env,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AffinityStoreError(f"psql_error: {type(exc).__name__}") from exc
        if proc.returncode != 0:
            detail = " ".join(
                line.strip()
                for line in (proc.stderr or "").strip().splitlines()[-2:]
                if line.strip()
            )
            raise AffinityStoreError(f"psql_error: {detail[:300]}")
        return proc.stdout

    def replace_all(
        self,
        records: Sequence[AffinityRecord],
        *,
        window_months: int,
        updated_at: datetime,
    ) -> int:
        buffer = io.StringIO()
        buffer.write("BEGIN;\n")
        buffer.write(f"DELETE FROM {TABLE};\n")
        buffer.write(
            f"COPY {TABLE} (sku, complement_sku, sku_name, complement_name, "
            "baskets, confidence, lift, window_months, updated_at) "
            "FROM STDIN WITH (FORMAT csv);\n"
        )
        writer = csv.writer(buffer, lineterminator="\n")
        for record in records:
            writer.writerow(
                [
                    record.sku,
                    record.complement_sku,
                    record.sku_name,
                    record.complement_name,
                    record.baskets,
                    f"{record.confidence:.6f}",
                    f"{record.lift:.6f}",
                    window_months,
                    updated_at.isoformat(),
                ]
            )
        buffer.write("\\.\nCOMMIT;\n")
        self._run(buffer.getvalue(), timeout=120)
        return len(records)

    def top_for_sku(self, sku: str, limit: int = 5) -> list[AffinityRecord]:
        sql = (
            "SELECT sku_name, complement_sku, complement_name, baskets, "
            f"confidence, lift, window_months FROM {TABLE} "
            "WHERE sku = :'sku' "
            "ORDER BY baskets DESC, lift DESC, complement_sku "
            f"LIMIT {max(1, int(limit))};\n"
        )
        output = self._run(sql, variables={"sku": sku})
        rows = list(csv.reader(io.StringIO(output)))
        return [
            _as_record(
                {
                    "sku": sku,
                    "sku_name": row[0],
                    "complement_sku": row[1],
                    "complement_name": row[2],
                    "baskets": row[3],
                    "confidence": row[4],
                    "lift": row[5],
                    "window_months": row[6],
                },
                12,
            )
            for row in rows
            if len(row) >= 7
        ]

    def count(self) -> int:
        output = self._run(f"SELECT COUNT(*) FROM {TABLE};\n")
        rows = list(csv.reader(io.StringIO(output)))
        if not rows or not rows[0]:
            raise AffinityStoreError("psql_empty_result")
        return int(rows[0][0])


def configured_store(env: Mapping[str, str] | None = None) -> AffinityStore | None:
    """Destino configurado: SQLite de demo primero, luego Postgres del asesor."""
    values = os.environ if env is None else env
    sqlite_path = (values.get(SQLITE_ENV) or "").strip()
    if sqlite_path:
        return SqliteAffinityStore(sqlite_path)
    url = (values.get(DATABASE_URL_ENV) or "").strip()
    if not url:
        url = (values.get(FALLBACK_DATABASE_URL_ENV) or "").strip()
    if url:
        return PostgresAffinityStore(url)
    return None
