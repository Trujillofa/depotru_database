"""Apply J3×IVA list prices to Magento via BasePriceStorageInterface over SSH.

Never cache:flush. After apply: indexer:reindex catalog_product_price and
cache:clean block_html full_page.
"""

from __future__ import annotations

import json
import logging
import shlex
import time
import uuid
from typing import Any, Dict, List, Mapping, Optional, Sequence

from business_analyzer.core.website_price_policy import (
    build_j3_venta_sql,
    build_price_payload,
    parse_magento_price_tsv,
    payload_stats,
)
from business_analyzer.core.website_stock_magento_ssh import (
    MagentoSshConfig,
    _ssh_connect,
    _ssh_exec,
)

logger = logging.getLogger(__name__)

FETCH_PHP = r"""<?php
declare(strict_types=1);
require "app/bootstrap.php";
$bootstrap = \Magento\Framework\App\Bootstrap::create(BP, $_SERVER);
$om = $bootstrap->getObjectManager();
$state = $om->get(\Magento\Framework\App\State::class);
try { $state->setAreaCode("adminhtml"); } catch (\Exception $e) {}
$res = $om->get(\Magento\Framework\App\ResourceConnection::class);
$conn = $res->getConnection();
$sql = "
SELECT cpe.sku AS sku,
       price.value AS price,
       special.value AS special_price
FROM catalog_product_entity cpe
INNER JOIN eav_attribute pa
        ON pa.attribute_code='price'
INNER JOIN catalog_product_entity_decimal price
        ON price.entity_id = cpe.entity_id
       AND price.store_id = 0
       AND price.attribute_id = pa.attribute_id
LEFT JOIN eav_attribute sa
       ON sa.attribute_code='special_price'
LEFT JOIN catalog_product_entity_decimal special
       ON special.entity_id = cpe.entity_id
       AND special.store_id = 0
       AND special.attribute_id = sa.attribute_id
";
foreach ($conn->fetchAll($sql) as $row) {
    $sp = $row['special_price'];
    echo $row['sku'] . "\t" . $row['price'] . "\t" . ($sp === null || $sp === '' ? 'NULL' : $sp) . "\n";
}
"""

APPLY_PHP = r"""<?php
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

$storage = $om->get(\Magento\Catalog\Api\BasePriceStorageInterface::class);
$factory = $om->get(\Magento\Catalog\Api\Data\BasePriceInterfaceFactory::class);

$out = [
    "mode" => $mode,
    "offset" => $batchOffset,
    "batch_size" => $batchSize,
    "slice_count" => count($slice),
    "updated_skus" => 0,
    "updated_items" => 0,
    "errors" => [],
];

$prices = [];
foreach ($slice as $row) {
    $sku = (string)($row["sku"] ?? "");
    $price = $row["price"] ?? null;
    if ($sku === "" || $price === null) {
        continue;
    }
    try {
        $item = $factory->create();
        $item->setSku($sku);
        $item->setPrice((float)$price);
        $item->setStoreId(0);
        $prices[] = $item;
        $out["updated_skus"]++;
        $out["updated_items"]++;
    } catch (\Throwable $e) {
        $out["errors"][] = ["sku" => $sku, "error" => $e->getMessage()];
    }
}
if ($mode === "apply" && $prices) {
    try {
        $storage->update($prices);
    } catch (\Throwable $e) {
        $out["errors"][] = ["sku" => "*", "error" => $e->getMessage()];
    }
}
echo json_encode($out, JSON_UNESCAPED_UNICODE) . "\n";
"""


def magento_update_rows(payload: Sequence[Mapping[str, Any]]) -> List[dict]:
    """Shape rows for BasePriceStorageInterface (sku, price, store_id=0)."""
    rows: List[dict] = []
    for item in payload:
        sku = str(item.get("sku") or "").strip()
        if not sku:
            continue
        rows.append(
            {
                "sku": sku,
                "price": int(item["target"]),
                "store_id": 0,
            }
        )
    return rows


def fetch_j3_venta_rows() -> List[dict]:
    from business_analyzer.core.database import Database

    db = Database()
    db.connect()
    rows = db.execute_query(build_j3_venta_sql())
    if not isinstance(rows, list):
        return []
    out: List[dict] = []
    for row in rows:
        sku = str(row.get("sku") or "").strip()
        if sku:
            out.append({"sku": sku, "venta": row.get("venta")})
    return out


def fetch_magento_prices_via_ssh(
    cfg: Optional[MagentoSshConfig] = None,
) -> List[dict]:
    cfg = cfg or MagentoSshConfig.from_env()
    if not cfg:
        raise RuntimeError("Magento SSH not configured")
    client = _ssh_connect(cfg)
    token = uuid.uuid4().hex[:12]
    remote_php = f"/tmp/dt_wps_fetch_{token}.php"  # nosec B108
    try:
        sftp = client.open_sftp()
        with sftp.file(remote_php, "w") as handle:
            handle.write(FETCH_PHP)
        sftp.close()
        out, err, status = _ssh_exec(
            client,
            f"php {shlex.quote(remote_php)}",
            working_dir=cfg.magento_root,
            timeout=300,
        )
        if status != 0:
            raise RuntimeError(f"Magento price fetch failed: {(err or out)[:500]}")
        parsed: List[dict] = parse_magento_price_tsv(out)
        return parsed
    finally:
        try:
            _ssh_exec(
                client,
                f"rm -f {remote_php}",
                working_dir=cfg.magento_root,
                timeout=30,
            )
        except Exception:  # noqa: BLE001
            pass
        client.close()


def build_drift_payload(
    *,
    magento_rows: Optional[Sequence[Mapping[str, Any]]] = None,
    j3_rows: Optional[Sequence[Mapping[str, Any]]] = None,
    cfg: Optional[MagentoSshConfig] = None,
) -> List[dict]:
    if j3_rows is None:
        j3_rows = fetch_j3_venta_rows()
    if magento_rows is None:
        magento_rows = fetch_magento_prices_via_ssh(cfg=cfg)
    built: List[dict] = build_price_payload(j3_rows=j3_rows, magento_rows=magento_rows)
    return built


def apply_price_payload_via_ssh(
    payload: List[Mapping[str, Any]],
    *,
    cfg: Optional[MagentoSshConfig] = None,
    dry_run: bool = True,
    batch_size: int = 80,
    reindex: bool = True,
) -> Dict[str, Any]:
    """Upload payload and apply Magento base prices in batches."""
    cfg = cfg or MagentoSshConfig.from_env()
    stats = payload_stats(payload)
    mode = "dry-run" if dry_run else "apply"
    result: Dict[str, Any] = {
        "mode": mode,
        "sku_count": len(payload),
        "updated_skus": 0,
        "updated_items": 0,
        "errors": [],
        "batches": 0,
        **stats,
    }
    if not payload:
        result["note"] = "empty payload"
        return result
    if not cfg:
        if dry_run:
            result["note"] = "dry-run-payload-only"
            result["sample"] = list(payload)[:8]
            return result
        raise RuntimeError("Magento SSH not configured")

    update_rows = magento_update_rows(payload)
    client = _ssh_connect(cfg)
    token = uuid.uuid4().hex[:12]
    remote_php = f"/tmp/dt_wps_{token}.php"  # nosec B108
    remote_payload = f"/tmp/dt_wps_{token}.json"  # nosec B108
    batch_size = max(1, min(int(batch_size), 200))
    try:
        sftp = client.open_sftp()
        with sftp.file(remote_php, "w") as handle:
            handle.write(APPLY_PHP)
        with sftp.file(remote_payload, "w") as handle:
            handle.write(json.dumps(update_rows, ensure_ascii=False))
        sftp.close()

        offset = 0
        while offset < len(update_rows):
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
            time.sleep(0.15)

        if (
            not dry_run
            and reindex
            and result["updated_skus"] > 0
            and not result["errors"]
        ):
            reindex_cmd = (
                "php -d memory_limit=2G bin/magento indexer:reindex "
                "catalog_product_price 2>&1 | tail -15"
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
