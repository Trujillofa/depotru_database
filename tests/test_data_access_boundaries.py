from typing import Any, Optional

import pytest

import src.data_access.banco_datos as banco_datos_module
import src.data_access.connection_resolver as connection_resolver_module
from src.config import Config
from src.data_access.banco_datos import build_banco_datos_query, fetch_banco_datos
from src.data_access.connection_resolver import resolve_connection_details


def test_resolve_connection_details_prefers_direct_env_config(monkeypatch):
    monkeypatch.setattr(Config, "DB_HOST", "env-host")
    monkeypatch.setattr(Config, "DB_PORT", 1433)
    monkeypatch.setattr(Config, "DB_USER", "env-user")
    monkeypatch.setattr(Config, "DB_PASSWORD", "env-password")
    monkeypatch.setattr(Config, "DB_NAME", "EnvBusiness")

    details = resolve_connection_details("/tmp/does-not-matter.ncx")

    assert details == {
        "Host": "env-host",
        "Port": 1433,
        "UserName": "env-user",
        "Password": "env-password",
        "Database": "EnvBusiness",
    }


def test_resolve_connection_details_uses_ncx_when_direct_config_missing(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(Config, "DB_HOST", None)
    monkeypatch.setattr(Config, "DB_USER", None)
    monkeypatch.setattr(Config, "DB_PASSWORD", None)

    ncx_path = tmp_path / "connections.ncx"
    ncx_path.write_text(
        (
            '<Connections><Connection Host="server-1" Port="1444" '
            'UserName="db-user" Password="enc" Database="SmartBusiness" '
            "/></Connections>"
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        connection_resolver_module,
        "decrypt_navicat_password",
        lambda encrypted_password: f"decrypted-{encrypted_password}",
    )

    details = resolve_connection_details(str(ncx_path))

    assert details == {
        "Host": "server-1",
        "Port": 1444,
        "UserName": "db-user",
        "Password": "decrypted-enc",
        "Database": "SmartBusiness",
    }


def test_resolve_connection_details_raises_for_missing_ncx(monkeypatch):
    monkeypatch.setattr(Config, "DB_HOST", None)
    monkeypatch.setattr(Config, "DB_USER", None)
    monkeypatch.setattr(Config, "DB_PASSWORD", None)

    missing_path = "/tmp/definitely-missing-connections.ncx"
    with pytest.raises(ValueError, match="No valid connections found"):
        resolve_connection_details(missing_path)


def test_build_banco_datos_query_keeps_document_code_exclusion(monkeypatch):
    monkeypatch.setattr(Config, "DB_NAME", "SmartBusiness")
    monkeypatch.setattr(Config, "DB_TABLE", "banco_datos")
    monkeypatch.setattr(Config, "EXCLUDED_DOCUMENT_CODES", ["XY", "AS", "TS"])

    query, params = build_banco_datos_query(limit=25)

    assert "DocumentosCodigo NOT IN ('XY', 'AS', 'TS')" in query
    assert params == (25,)


class _FakeCursor:
    def __init__(self, rows: list[dict[str, Any]]):
        self._rows = rows
        self.executed: list[tuple[str, Optional[tuple[Any, ...]]]] = []
        self.description = [("col",)]

    def execute(self, query: str, params: Optional[tuple[Any, ...]] = None) -> None:
        self.executed.append((query, params))

    def fetchone(self) -> dict[str, int]:
        return {"test": 1}

    def __iter__(self):
        return iter(self._rows)


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor):
        self._cursor = cursor
        self.closed = False

    def cursor(self, as_dict: bool = False) -> _FakeCursor:
        assert as_dict is True
        return self._cursor

    def close(self) -> None:
        self.closed = True


def test_fetch_banco_datos_executes_filtered_query(monkeypatch):
    monkeypatch.setattr(Config, "DB_NAME", "SmartBusiness")
    monkeypatch.setattr(Config, "DB_TABLE", "banco_datos")
    monkeypatch.setattr(Config, "EXCLUDED_DOCUMENT_CODES", ["XY", "AS", "TS"])
    monkeypatch.setattr(Config, "DB_LOGIN_TIMEOUT", 10)
    monkeypatch.setattr(Config, "DB_TIMEOUT", 10)
    monkeypatch.setattr(Config, "DB_TDS_VERSION", "7.4")

    fake_cursor = _FakeCursor(rows=[{"DocumentosCodigo": "AA"}])
    fake_connection = _FakeConnection(fake_cursor)

    monkeypatch.setattr(
        banco_datos_module.pymssql,
        "connect",
        lambda **_kwargs: fake_connection,
    )

    data = fetch_banco_datos(
        {
            "Host": "server",
            "Port": 1433,
            "UserName": "user",
            "Password": "password",
            "Database": "SmartBusiness",
        },
        limit=10,
    )

    query, params = fake_cursor.executed[2]
    assert "DocumentosCodigo NOT IN ('XY', 'AS', 'TS')" in query
    assert params == (10,)
    assert data == [{"DocumentosCodigo": "AA"}]
    assert fake_connection.closed is True
