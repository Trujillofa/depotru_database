"""CI-safe tests for Magento SSH stock apply (no live SSH / Magento)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from business_analyzer.core.website_stock_magento_ssh import (
    _APPLY_PHP,
    MAGENTO_ROOT_DEFAULT,
    MagentoSshConfig,
    _load_env_php_ssh,
    _read_passphrase_file,
    apply_payload_via_ssh,
    build_excluded_payload,
)


def _sample_payload():
    return [
        {
            "sku": "SKU-001",
            "website_qty": 12.0,
            "excluded_qty": 4.0,
            "all_warehouses_qty": 16.0,
            "name": "Taladro",
        },
        {
            "sku": "SKU-OOS",
            "website_qty": 0.0,
            "excluded_qty": 8.0,
            "all_warehouses_qty": 8.0,
            "name": "Solo denylist",
        },
    ]


@pytest.mark.unit
def test_dry_run_does_not_ssh_or_require_config():
    """Dry-run must stay local: no SSH connect, no Magento writes."""
    with patch(
        "business_analyzer.core.website_stock_magento_ssh._ssh_connect"
    ) as ssh_connect, patch(
        "business_analyzer.core.website_stock_magento_ssh.MagentoSshConfig.from_env"
    ) as from_env:
        result = apply_payload_via_ssh(_sample_payload(), dry_run=True)

    ssh_connect.assert_not_called()
    from_env.assert_not_called()
    assert result["mode"] == "dry-run"
    assert result["ssh"] is False
    assert result["updated_skus"] == 0
    assert result["updated_items"] == 0
    assert result["would_update_skus"] == 2
    assert result["would_zero_skus"] == 1
    assert result["errors"] == []
    assert "no SSH" in result["note"]


@pytest.mark.unit
def test_local_dry_run_result_skips_blank_skus():
    payload = [
        {"sku": "", "website_qty": 3},
        {"sku": "KEEP", "website_qty": 1, "excluded_qty": 2},
    ]
    from business_analyzer.core.website_stock_magento_ssh import local_dry_run_result

    result = local_dry_run_result(payload)
    assert result["sku_count"] == 1
    assert result["sample"][0]["sku"] == "KEEP"
    assert result["ssh"] is False


@pytest.mark.unit
def test_apply_without_config_raises_before_ssh():
    with patch(
        "business_analyzer.core.website_stock_magento_ssh.MagentoSshConfig.from_env",
        return_value=None,
    ), patch(
        "business_analyzer.core.website_stock_magento_ssh._ssh_connect"
    ) as ssh_connect:
        with pytest.raises(RuntimeError, match="Magento SSH not configured"):
            apply_payload_via_ssh(_sample_payload(), dry_run=False)
    ssh_connect.assert_not_called()


@pytest.mark.unit
def test_apply_empty_payload_does_not_ssh():
    with patch(
        "business_analyzer.core.website_stock_magento_ssh._ssh_connect"
    ) as ssh_connect:
        result = apply_payload_via_ssh(
            [],
            cfg=MagentoSshConfig(host="example.test", username="u", password="x"),
            dry_run=False,
        )
    ssh_connect.assert_not_called()
    assert result["updated_skus"] == 0
    assert result["note"] == "empty payload"


@pytest.mark.unit
def test_apply_path_uses_ssh_and_skips_reindex_when_disabled():
    client = MagicMock()
    sftp = MagicMock()
    client.open_sftp.return_value = sftp
    with patch(
        "business_analyzer.core.website_stock_magento_ssh._ssh_connect",
        return_value=client,
    ) as ssh_connect, patch(
        "business_analyzer.core.website_stock_magento_ssh._ssh_exec",
        return_value=('{"updated_skus": 2, "updated_items": 2, "errors": []}\n', "", 0),
    ) as ssh_exec:
        result = apply_payload_via_ssh(
            _sample_payload(),
            cfg=MagentoSshConfig(
                host="example.test",
                username="deploy",
                password="secret",
                magento_root="/var/www/magento",
            ),
            dry_run=False,
            reindex=False,
            batch_size=40,
        )

    ssh_connect.assert_called_once()
    # One apply batch + cleanup rm. No indexer/cache when reindex=False.
    apply_cmds = [
        call.args[1]
        for call in ssh_exec.call_args_list
        if "php" in call.args[1] and "indexer" not in call.args[1]
    ]
    assert any("apply" in cmd for cmd in apply_cmds)
    assert not any(
        "indexer:reindex" in call.args[1] for call in ssh_exec.call_args_list
    )
    assert result["mode"] == "apply"
    assert result["updated_skus"] == 2
    assert "reindex_status" not in result
    client.close.assert_called()


@pytest.mark.unit
def test_php_applier_only_saves_in_apply_mode():
    assert '$mode === "apply"' in _APPLY_PHP
    assert "$save->execute($toSave)" in _APPLY_PHP


@pytest.mark.unit
def test_from_env_reads_explicit_credentials(monkeypatch):
    monkeypatch.setenv("MAGENTO_SSH_HOST", "magento.example.test")
    monkeypatch.setenv("MAGENTO_SSH_USER", "deploy")
    monkeypatch.setenv("MAGENTO_SSH_PASSWORD", "not-a-real-secret")
    monkeypatch.setenv("MAGENTO_ROOT", "/var/www/magento")
    monkeypatch.setenv("MAGENTO_SSH_PORT", "2222")
    monkeypatch.delenv("MAGENTO_ENV_PHP", raising=False)
    with patch(
        "business_analyzer.core.website_stock_magento_ssh._load_env_php_ssh",
        return_value=None,
    ):
        cfg = MagentoSshConfig.from_env()
    assert cfg is not None
    assert cfg.host == "magento.example.test"
    assert cfg.username == "deploy"
    assert cfg.password == "not-a-real-secret"
    assert cfg.port == 2222
    assert cfg.magento_root == "/var/www/magento"


@pytest.mark.unit
def test_from_env_returns_none_without_host_or_auth(monkeypatch):
    for key in (
        "MAGENTO_SSH_HOST",
        "MAGENTO_SSH_USER",
        "MAGENTO_SSH_PASSWORD",
        "MAGENTO_SSH_KEY",
        "MAGENTO_ENV_PHP",
    ):
        monkeypatch.delenv(key, raising=False)
    with patch(
        "business_analyzer.core.website_stock_magento_ssh._load_env_php_ssh",
        return_value=None,
    ):
        assert MagentoSshConfig.from_env() is None


@pytest.mark.unit
def test_read_passphrase_file_skips_banners(tmp_path: Path):
    notes = tmp_path / "notes.txt"
    notes.write_text(
        "MAGENTO SSH NOTES\nGenerating public/private key pair.\nssh-ed25519 AAAA\nshort-secret\n",
        encoding="utf-8",
    )
    assert _read_passphrase_file(notes) == "short-secret"


@pytest.mark.unit
def test_load_env_php_ssh_missing_file(tmp_path: Path):
    assert _load_env_php_ssh(str(tmp_path / "missing-env.php")) is None


@pytest.mark.unit
def test_build_excluded_payload_from_runner():
    rows = [
        {
            "sku": "A",
            "website_qty": 3,
            "excluded_qty": 10,
            "all_warehouses_qty": 13,
            "name": "Item A",
        },
        {
            "sku": "",
            "website_qty": 1,
            "excluded_qty": 9,
            "all_warehouses_qty": 10,
            "name": "blank",
        },
        {
            "sku": "B",
            "website_qty": 2,
            "excluded_qty": 0,
            "all_warehouses_qty": 2,
            "name": "below min",
        },
    ]
    runner = MagicMock()
    runner.skus_with_excluded_stock.return_value = rows
    with patch("business_analyzer.core.database.Database"), patch(
        "business_analyzer.core.j3system_website_stock.WebsiteStockRunner",
        return_value=runner,
    ):
        payload = build_excluded_payload(top_n=10, min_excluded=0.01)

    assert [row["sku"] for row in payload] == ["A"]
    assert payload[0]["website_qty"] == 3.0
    assert MAGENTO_ROOT_DEFAULT == ""


@pytest.mark.unit
def test_build_excluded_payload_explicit_skus():
    runner = MagicMock()
    runner.stock_by_sku.return_value = [
        {
            "sku": "KEEP",
            "website_qty": 1,
            "excluded_qty": 0,
            "all_warehouses_qty": 1,
            "name": "Named",
        }
    ]
    with patch("business_analyzer.core.database.Database"), patch(
        "business_analyzer.core.j3system_website_stock.WebsiteStockRunner",
        return_value=runner,
    ):
        payload = build_excluded_payload(skus=["KEEP"], min_excluded=99)
    runner.stock_by_sku.assert_called_once()
    assert payload[0]["sku"] == "KEEP"


@pytest.mark.unit
def test_from_env_merges_env_php_and_passphrase_file(monkeypatch, tmp_path: Path):
    notes = tmp_path / "pass.txt"
    notes.write_text("file-secret\n", encoding="utf-8")
    monkeypatch.setenv("MAGENTO_SSH_HOST", "")
    monkeypatch.setenv("MAGENTO_SSH_USER", "")
    monkeypatch.setenv("MAGENTO_SSH_PASSWORD", "")
    monkeypatch.setenv("MAGENTO_SSH_KEY", "")
    monkeypatch.setenv("MAGENTO_SSH_KEY_PASSPHRASE_FILE", str(notes))
    monkeypatch.delenv("MAGENTO_SSH_KEY_PASSPHRASE", raising=False)
    parsed = {
        "host": "from-php.example.test",
        "username": "phpuser",
        "password": "php-pass",
        "key_filename": "/tmp/id",
        "key_passphrase": None,
        "magento_root": "/var/www/from-php",
    }
    with patch(
        "business_analyzer.core.website_stock_magento_ssh._load_env_php_ssh",
        return_value=parsed,
    ):
        cfg = MagentoSshConfig.from_env()
    assert cfg is not None
    assert cfg.host == "from-php.example.test"
    assert cfg.username == "phpuser"
    assert cfg.password == "php-pass"
    assert cfg.key_passphrase == "file-secret"
    assert cfg.magento_root == "/var/www/from-php"


@pytest.mark.unit
def test_read_passphrase_file_oserror_and_fallback(tmp_path: Path):
    missing = tmp_path / "nope.txt"
    assert _read_passphrase_file(missing) is None
    only_banners = tmp_path / "banners.txt"
    only_banners.write_text(
        "MAGENTO\nGenerating key pair now\nssh-ed25519 AAAA\n",
        encoding="utf-8",
    )
    assert "Generating" in (_read_passphrase_file(only_banners) or "")


@pytest.mark.unit
def test_load_env_php_ssh_reads_tools_config(tmp_path: Path):
    env_php = tmp_path / "depositotrujillo.co" / "config" / "env.php"
    env_php.parent.mkdir(parents=True)
    env_php.write_text("<?php return [];", encoding="utf-8")

    def load_config(_path):
        return {
            "server": {
                "host": "php.example.test",
                "username": "deploy",
                "password": "from-php",
                "key_filename": "",
                "key_passphrase": "",
            },
            "magento": {"root_path": "/var/www/magento"},
        }

    fake_tools = type("tools", (), {})()
    fake_common = type("common", (), {"load_config": staticmethod(load_config)})()
    import sys

    with patch.dict(sys.modules, {"tools": fake_tools, "tools.common": fake_common}):
        parsed = _load_env_php_ssh(str(env_php))
    assert parsed["host"] == "php.example.test"
    assert parsed["password"] == "from-php"
    assert parsed["magento_root"] == "/var/www/magento"


@pytest.mark.unit
def test_load_env_php_ssh_swallows_loader_errors(tmp_path: Path):
    env_php = tmp_path / "depositotrujillo.co" / "config" / "env.php"
    env_php.parent.mkdir(parents=True)
    env_php.write_text("<?php", encoding="utf-8")
    assert _load_env_php_ssh(str(env_php)) is None


@pytest.mark.unit
def test_ssh_connect_and_exec_use_password(monkeypatch):
    import sys

    from business_analyzer.core.website_stock_magento_ssh import _ssh_connect, _ssh_exec

    client = MagicMock()
    stdout = MagicMock()
    stdout.read.return_value = b"ok"
    stdout.channel.recv_exit_status.return_value = 0
    stderr = MagicMock()
    stderr.read.return_value = b""
    client.exec_command.return_value = (MagicMock(), stdout, stderr)
    paramiko = MagicMock()
    paramiko.SSHClient.return_value = client
    paramiko.RejectPolicy.return_value = "reject"
    with patch.dict(sys.modules, {"paramiko": paramiko}):
        cfg = MagentoSshConfig(
            host="example.test",
            username="deploy",
            password="secret",
            magento_root="/var/www/magento",
        )
        connected = _ssh_connect(cfg)
        out, err, status = _ssh_exec(
            connected, "echo hi", working_dir="/var/www/magento"
        )
    client.connect.assert_called_once()
    assert client.connect.call_args.kwargs["password"] == "secret"
    assert out == "ok"
    assert status == 0
    client.exec_command.assert_called_once()


@pytest.mark.unit
def test_ssh_connect_key_fallback_to_password(tmp_path: Path):
    import sys

    from business_analyzer.core.website_stock_magento_ssh import _ssh_connect

    key = tmp_path / "id_rsa"
    key.write_text("not-a-real-key", encoding="utf-8")
    client = MagicMock()
    paramiko = MagicMock()
    paramiko.SSHClient.return_value = client
    paramiko.PKey.from_path.side_effect = RuntimeError("bad key")
    with patch.dict(sys.modules, {"paramiko": paramiko}):
        cfg = MagentoSshConfig(
            host="example.test",
            username="deploy",
            password="secret",
            key_filename=str(key),
            magento_root="/var/www/magento",
        )
        _ssh_connect(cfg)
    assert client.connect.call_args.kwargs["password"] == "secret"


@pytest.mark.unit
def test_ssh_connect_requires_auth():
    import sys

    from business_analyzer.core.website_stock_magento_ssh import _ssh_connect

    paramiko = MagicMock()
    paramiko.SSHClient.return_value = MagicMock()
    with patch.dict(sys.modules, {"paramiko": paramiko}):
        with pytest.raises(RuntimeError, match="no usable key"):
            _ssh_connect(
                MagentoSshConfig(
                    host="example.test",
                    username="deploy",
                    magento_root="/var/www/magento",
                )
            )


@pytest.mark.unit
def test_apply_records_remote_errors_and_reindex():
    client = MagicMock()
    sftp = MagicMock()
    client.open_sftp.return_value = sftp

    def exec_side_effect(client_arg, command, *, working_dir, timeout=300):
        if "indexer" in command:
            return ("reindexed", "", 0)
        if "cache:clean" in command:
            return ("cleaned", "", 0)
        if command.startswith("rm "):
            return ("", "", 0)
        return (
            '{"updated_skus": 2, "updated_items": 3, "errors": [{"sku": "X"}]}\n',
            "",
            0,
        )

    with patch(
        "business_analyzer.core.website_stock_magento_ssh._ssh_connect",
        return_value=client,
    ), patch(
        "business_analyzer.core.website_stock_magento_ssh._ssh_exec",
        side_effect=exec_side_effect,
    ):
        result = apply_payload_via_ssh(
            _sample_payload(),
            cfg=MagentoSshConfig(
                host="example.test",
                username="deploy",
                password="secret",
                magento_root="/var/www/magento",
            ),
            dry_run=False,
            reindex=True,
        )
    assert result["updated_skus"] == 2
    assert result["reindex_status"] == 0
    assert result["cache_clean_status"] == 0
    assert result["errors"][0]["sku"] == "X"


@pytest.mark.unit
def test_apply_handles_nonzero_status_and_bad_json():
    client = MagicMock()
    client.open_sftp.return_value = MagicMock()
    with patch(
        "business_analyzer.core.website_stock_magento_ssh._ssh_connect",
        return_value=client,
    ), patch(
        "business_analyzer.core.website_stock_magento_ssh._ssh_exec",
        return_value=("", "php boom", 2),
    ):
        failed = apply_payload_via_ssh(
            _sample_payload(),
            cfg=MagentoSshConfig(
                host="example.test", username="u", password="p", magento_root="/m"
            ),
            reindex=False,
        )
    assert failed["errors"][0]["status"] == 2

    with patch(
        "business_analyzer.core.website_stock_magento_ssh._ssh_connect",
        return_value=client,
    ), patch(
        "business_analyzer.core.website_stock_magento_ssh._ssh_exec",
        return_value=("not-json", "", 0),
    ):
        parsed = apply_payload_via_ssh(
            _sample_payload(),
            cfg=MagentoSshConfig(
                host="example.test", username="u", password="p", magento_root="/m"
            ),
            reindex=False,
        )
    assert "parse" in parsed["errors"][0]["error"]
