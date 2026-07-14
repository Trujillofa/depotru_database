"""Apply J3 website allowlist stock to Magento MSI over SSH (#182).

Used when b2c.smart-business still pushes all-warehouse totals and no Magento
REST token is available. Sets each existing MSI source row for affected SKUs
to ``website_qty`` (allowlist sum). Denylist-only SKUs become qty 0 / OOS.

Requires paramiko + Magento SSH credentials (password or key).
"""

from __future__ import annotations

import json
import logging
import os
import shlex
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

MAGENTO_ROOT_DEFAULT = "/home/deptrujillob2c/public_html"

# PHP applier uploaded to the Magento host (SourceItemsSaveInterface).
_APPLY_PHP = r"""<?php
declare(strict_types=1);
require "app/bootstrap.php";
$bootstrap = \Magento\Framework\App\Bootstrap::create(BP, $_SERVER);
$om = $bootstrap->getObjectManager();
$state = $om->get(\Magento\Framework\App\State::class);
try { $state->setAreaCode("adminhtml"); } catch (\Exception $e) {}

$payloadPath = $argv[1] ?? "";
$mode = $argv[2] ?? "dry-run";
$batchOffset = (int)($argv[3] ?? 0);
$batchSize = (int)($argv[4] ?? 50);

if ($payloadPath === "" || !is_file($payloadPath)) {
    fwrite(STDERR, "payload required\n");
    exit(2);
}
$rows = json_decode(file_get_contents($payloadPath), true);
if (!is_array($rows)) {
    fwrite(STDERR, "invalid payload\n");
    exit(3);
}
$slice = array_slice($rows, $batchOffset, $batchSize);

$getBySku = $om->get(\Magento\InventoryApi\Api\GetSourceItemsBySkuInterface::class);
$save = $om->get(\Magento\InventoryApi\Api\SourceItemsSaveInterface::class);
$factory = $om->get(\Magento\InventoryApi\Api\Data\SourceItemInterfaceFactory::class);

$out = [
    "mode" => $mode,
    "offset" => $batchOffset,
    "batch_size" => $batchSize,
    "slice_count" => count($slice),
    "updated_skus" => 0,
    "updated_items" => 0,
    "errors" => [],
];

foreach ($slice as $row) {
    $sku = (string)($row["sku"] ?? "");
    $websiteQty = (float)($row["website_qty"] ?? 0);
    if ($sku === "") {
        continue;
    }
    try {
        $existing = $getBySku->execute($sku);
        $toSave = [];
        if (!$existing) {
            $item = $factory->create();
            $item->setSku($sku);
            $item->setSourceCode("default");
            $item->setQuantity($websiteQty);
            $item->setStatus($websiteQty > 0
                ? \Magento\InventoryApi\Api\Data\SourceItemInterface::STATUS_IN_STOCK
                : \Magento\InventoryApi\Api\Data\SourceItemInterface::STATUS_OUT_OF_STOCK);
            $toSave[] = $item;
        } else {
            foreach ($existing as $srcItem) {
                $srcItem->setQuantity($websiteQty);
                $srcItem->setStatus($websiteQty > 0
                    ? \Magento\InventoryApi\Api\Data\SourceItemInterface::STATUS_IN_STOCK
                    : \Magento\InventoryApi\Api\Data\SourceItemInterface::STATUS_OUT_OF_STOCK);
                $toSave[] = $srcItem;
            }
        }
        if ($mode === "apply" && $toSave) {
            $save->execute($toSave);
        }
        $out["updated_skus"]++;
        $out["updated_items"] += count($toSave);
    } catch (\Throwable $e) {
        $out["errors"][] = ["sku" => $sku, "error" => $e->getMessage()];
    }
}
echo json_encode($out, JSON_UNESCAPED_UNICODE) . "\n";
"""


@dataclass
class MagentoSshConfig:
    host: str
    username: str
    password: Optional[str] = None
    key_filename: Optional[str] = None
    key_passphrase: Optional[str] = None
    port: int = 22
    magento_root: str = MAGENTO_ROOT_DEFAULT

    @classmethod
    def from_env(cls) -> Optional["MagentoSshConfig"]:
        host = (os.getenv("MAGENTO_SSH_HOST") or "").strip()
        user = (os.getenv("MAGENTO_SSH_USER") or "").strip()
        password = (os.getenv("MAGENTO_SSH_PASSWORD") or "").strip() or None
        key = (os.getenv("MAGENTO_SSH_KEY") or "").strip() or None
        passphrase = (os.getenv("MAGENTO_SSH_KEY_PASSPHRASE") or "").strip() or None
        pf = (os.getenv("MAGENTO_SSH_KEY_PASSPHRASE_FILE") or "").strip()
        if pf and Path(pf).is_file() and not passphrase:
            passphrase = Path(pf).read_text(encoding="utf-8").strip() or None
        root = (
            os.getenv("MAGENTO_ROOT") or MAGENTO_ROOT_DEFAULT
        ).strip() or MAGENTO_ROOT_DEFAULT
        port = int(os.getenv("MAGENTO_SSH_PORT") or "22")

        # Fallback: sibling depositotrujillo.co config/env.php
        if (not password and not key) or not host or not user:
            env_php = os.getenv("MAGENTO_ENV_PHP") or os.path.expanduser(
                "~/Projects/depositotrujillo.co/config/env.php"
            )
            parsed = _load_env_php_ssh(env_php)
            if parsed:
                host = host or parsed.get("host") or ""
                user = user or parsed.get("username") or ""
                password = password or parsed.get("password")
                key = key or parsed.get("key_filename")
                root = parsed.get("magento_root") or root

        if not host or not user:
            return None
        if not password and not key:
            return None
        return cls(
            host=host,
            username=user,
            password=password,
            key_filename=key,
            key_passphrase=passphrase,
            port=port,
            magento_root=root,
        )


def _load_env_php_ssh(path: str) -> Optional[Dict[str, Optional[str]]]:
    """Best-effort parse of depositotrujillo config/env.php server block."""
    p = Path(path).expanduser()
    if not p.is_file():
        return None
    try:
        # Prefer sibling tools if available
        depo = p.resolve().parents[1]
        import sys

        if str(depo) not in sys.path:
            sys.path.insert(0, str(depo))
        from tools.common import load_config

        cfg = load_config(str(p))
        server = cfg.get("server") or {}
        magento = cfg.get("magento") or {}
        key_raw = str(server.get("key_filename") or "").strip()
        return {
            "host": str(server.get("host") or ""),
            "username": str(server.get("username") or ""),
            "password": str(server.get("password") or ""),
            "key_filename": key_raw or None,
            "magento_root": str(magento.get("root_path") or MAGENTO_ROOT_DEFAULT),
        }
    except Exception as exc:  # noqa: BLE001
        logger.debug("env.php load via tools failed: %s", exc)
        return None


def _ssh_connect(cfg: MagentoSshConfig):
    import paramiko  # type: ignore[import-untyped]

    client = paramiko.SSHClient()
    # Prefer known_hosts; reject unknown hosts (ops host must be trusted once).
    client.load_system_host_keys()
    try:
        client.load_host_keys(str(Path.home() / ".ssh" / "known_hosts"))
    except OSError:
        pass
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    kwargs: Dict[str, Any] = {
        "hostname": cfg.host,
        "username": cfg.username,
        "port": cfg.port,
        "timeout": 45,
        "look_for_keys": False,
        "allow_agent": False,
        "compress": True,
    }
    if cfg.key_filename:
        try:
            pkey = paramiko.RSAKey.from_private_key_file(
                cfg.key_filename, password=cfg.key_passphrase
            )
            kwargs["pkey"] = pkey
        except Exception:
            try:
                pkey = paramiko.Ed25519Key.from_private_key_file(
                    cfg.key_filename, password=cfg.key_passphrase
                )
                kwargs["pkey"] = pkey
            except Exception as exc:
                if cfg.password:
                    logger.warning("SSH key unusable (%s); using password", exc)
                    kwargs["password"] = cfg.password
                else:
                    raise
    elif cfg.password:
        kwargs["password"] = cfg.password
    client.connect(**kwargs)
    return client


def _ssh_exec(
    client, command: str, *, working_dir: str, timeout: int = 300
) -> tuple[str, str, int]:
    # Quote cwd; command is built only from fixed templates + int offsets.
    full = f"cd {shlex.quote(working_dir)} && {command}"
    _stdin, stdout, stderr = client.exec_command(full, timeout=timeout)  # nosec B601
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    status = stdout.channel.recv_exit_status()
    return out, err, status


def build_excluded_payload(
    *,
    top_n: int = 5000,
    min_excluded: float = 0.01,
    skus: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """Build apply payload from J3 website stock runner."""
    from business_analyzer.core.database import Database
    from business_analyzer.core.j3system_website_stock import WebsiteStockRunner

    runner = WebsiteStockRunner(Database())
    if skus:
        rows = runner.stock_by_sku(skus=list(skus), top_n=len(skus))
    else:
        rows = runner.skus_with_excluded_stock(top_n=top_n, min_excluded=min_excluded)
    payload: List[Dict[str, Any]] = []
    for r in rows:
        sku = str(r.get("sku") or "").strip()
        if not sku:
            continue
        excl = float(r.get("excluded_qty") or 0)
        if skus is None and excl < min_excluded:
            continue
        payload.append(
            {
                "sku": sku,
                "website_qty": float(r.get("website_qty") or 0),
                "excluded_qty": excl,
                "all_warehouses_qty": float(r.get("all_warehouses_qty") or 0),
                "name": str(r.get("name") or "")[:80],
            }
        )
    payload.sort(key=lambda x: -float(x.get("excluded_qty") or 0))
    return payload


def apply_payload_via_ssh(
    payload: List[Dict[str, Any]],
    *,
    cfg: Optional[MagentoSshConfig] = None,
    dry_run: bool = False,
    batch_size: int = 40,
    reindex: bool = True,
) -> Dict[str, Any]:
    """Upload payload and apply in batches on Magento host."""
    cfg = cfg or MagentoSshConfig.from_env()
    if not cfg:
        raise RuntimeError(
            "Magento SSH not configured. Set MAGENTO_SSH_HOST/USER/PASSWORD "
            "or MAGENTO_ENV_PHP pointing at depositotrujillo config/env.php"
        )
    if not payload:
        return {
            "mode": "dry-run" if dry_run else "apply",
            "updated_skus": 0,
            "updated_items": 0,
            "errors": [],
            "note": "empty payload",
        }

    client = _ssh_connect(cfg)
    token = uuid.uuid4().hex[:12]
    # Unique remote names under /tmp (Magento host jailshell; no shared sticky issues)
    remote_php = f"/tmp/dt_wsa_{token}.php"  # nosec B108
    remote_payload = f"/tmp/dt_wsa_{token}.json"  # nosec B108
    mode = "dry-run" if dry_run else "apply"
    if mode not in ("dry-run", "apply"):
        raise ValueError(f"invalid mode: {mode}")
    batch_size = max(1, min(int(batch_size), 100))
    result: Dict[str, Any] = {
        "mode": mode,
        "sku_count": len(payload),
        "updated_skus": 0,
        "updated_items": 0,
        "errors": [],
        "batches": 0,
    }
    try:
        sftp = client.open_sftp()
        with sftp.file(remote_php, "w") as handle:
            handle.write(_APPLY_PHP)
        with sftp.file(remote_payload, "w") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
        sftp.close()

        offset = 0
        while offset < len(payload):
            cmd = (
                f"php {shlex.quote(remote_php)} {shlex.quote(remote_payload)} "
                f"{shlex.quote(mode)} {int(offset)} {int(batch_size)}"
            )
            out, err, status = _ssh_exec(
                client, cmd, working_dir=cfg.magento_root, timeout=600
            )
            if status != 0:
                result["errors"].append(
                    {
                        "offset": offset,
                        "status": status,
                        "stderr": (err or "")[:500],
                        "stdout": (out or "")[:300],
                    }
                )
                break
            try:
                line = (out or "").strip().splitlines()[-1]
                data = json.loads(line)
            except Exception as exc:  # noqa: BLE001
                result["errors"].append(
                    {
                        "offset": offset,
                        "error": f"parse: {exc}",
                        "raw": (out or "")[:300],
                    }
                )
                break
            result["updated_skus"] += int(data.get("updated_skus") or 0)
            result["updated_items"] += int(data.get("updated_items") or 0)
            result["errors"].extend(data.get("errors") or [])
            result["batches"] += 1
            offset += batch_size
            time.sleep(0.2)

        if not dry_run and reindex and result["updated_skus"] > 0:
            reindex_cmd = (
                "php -d memory_limit=2G bin/magento indexer:reindex "
                "inventory cataloginventory_stock 2>&1 | tail -15"
            )
            out, err, status = _ssh_exec(
                client, reindex_cmd, working_dir=cfg.magento_root, timeout=600
            )
            result["reindex_status"] = status
            result["reindex_out"] = ((out or "") + (err or ""))[-800:]
            clean_cmd = (
                "php bin/magento cache:clean block_html full_page 2>&1 | tail -8"
            )
            out, err, status = _ssh_exec(
                client, clean_cmd, working_dir=cfg.magento_root, timeout=120
            )
            result["cache_clean_status"] = status
            result["cache_clean_out"] = ((out or "") + (err or ""))[-400:]
    finally:
        try:
            _ssh_exec(
                client,
                f"rm -f {remote_php} {remote_payload}",
                working_dir=cfg.magento_root,
                timeout=30,
            )
        except Exception:  # noqa: BLE001
            pass
        client.close()

    return result
