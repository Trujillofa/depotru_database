"""Thin Magento REST client for platform tools.

Default path is read-only (sellable qty, product search). Optional
``post_source_items`` supports gated MSI writes for website stock tooling
(issue #182). Prefer configuring b2c.smart-business warehouse denylist first —
that feed may overwrite Magento during business hours.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class MagentoConfig:
    base_url: str
    access_token: str
    timeout_sec: float = 30.0

    @classmethod
    def from_env(cls) -> Optional["MagentoConfig"]:
        base = (os.getenv("MAGENTO_BASE_URL") or "").strip().rstrip("/")
        token = (os.getenv("MAGENTO_ACCESS_TOKEN") or "").strip()
        if not base or not token:
            return None
        timeout = float(os.getenv("MAGENTO_TIMEOUT_SEC") or "30")
        return cls(base_url=base, access_token=token, timeout_sec=timeout)

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.access_token)


class MagentoRestClient:
    """Minimal REST helper using stdlib (no extra deps)."""

    def __init__(self, config: MagentoConfig) -> None:
        self.config = config

    def _request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
    ) -> Any:
        url = f"{self.config.base_url}{path}"
        data = None
        headers = {
            "Authorization": f"Bearer {self.config.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if body is not None:
            data = json.dumps(body).encode("utf-8")
        req = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=self.config.timeout_sec) as resp:  # nosec B310
                raw = resp.read().decode("utf-8")
                if not raw:
                    return None
                return json.loads(raw)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Magento HTTP {exc.code} on {path}: {detail[:500]}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(f"Magento connection error: {exc}") from exc

    def get_product(self, sku: str) -> Dict[str, Any]:
        from urllib.parse import quote

        encoded = quote(sku, safe="")
        data = self._request("GET", f"/rest/V1/products/{encoded}")
        if isinstance(data, dict):
            return data
        return {}

    @staticmethod
    def _custom_attr(item: Dict[str, Any], code: str) -> str:
        attrs = item.get("custom_attributes") or []
        if not isinstance(attrs, list):
            return ""
        for attr in attrs:
            if not isinstance(attr, dict):
                continue
            if str(attr.get("attribute_code") or "") == code:
                return str(attr.get("value") or "").strip()
        return ""

    def product_url_for_key(self, url_key: str) -> str:
        """Build storefront PDP URL from Magento url_key."""
        key = (url_key or "").strip().strip("/")
        if not key:
            return ""
        store = (os.getenv("MAGENTO_STOREFRONT_URL") or "").strip().rstrip(
            "/"
        ) or self.config.base_url.rstrip("/")
        if not store:
            return ""
        suffix = os.getenv("MAGENTO_PRODUCT_URL_SUFFIX", ".html")
        if not suffix.startswith(".") and suffix:
            suffix = f".{suffix}"
        # url_key may already include .html
        if key.endswith(suffix) or key.endswith(".html"):
            return f"{store}/{key}"
        return f"{store}/{key}{suffix}"

    def search_products(
        self,
        query: str,
        *,
        page_size: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search products by name (LIKE) via Magento REST searchCriteria."""
        from urllib.parse import quote

        q = (query or "").strip()
        if not q:
            return []
        page_size = max(1, min(int(page_size), 20))
        # filter name like %query%
        params = (
            "searchCriteria[filter_groups][0][filters][0][field]=name"
            f"&searchCriteria[filter_groups][0][filters][0][value]=%{quote(q)}%"
            "&searchCriteria[filter_groups][0][filters][0][condition_type]=like"
            f"&searchCriteria[pageSize]={page_size}"
            "&searchCriteria[currentPage]=1"
        )
        data = self._request("GET", f"/rest/V1/products?{params}")
        if not isinstance(data, dict):
            return []
        items = data.get("items") or []
        out: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            url_key = self._custom_attr(item, "url_key")
            product_url = self.product_url_for_key(url_key) if url_key else ""
            out.append(
                {
                    "sku": str(item.get("sku") or ""),
                    "name": str(item.get("name") or ""),
                    "url_key": url_key,
                    "product_url": product_url,
                    "status": item.get("status"),
                    "type_id": item.get("type_id"),
                }
            )
        return out

    def get_source_items(self, sku: str) -> List[Dict[str, Any]]:
        """MSI source items for a SKU (searchCriteria)."""
        from urllib.parse import quote

        # searchCriteria[filter_groups][0][filters][0][field]=sku
        q = (
            "searchCriteria[filter_groups][0][filters][0][field]=sku"
            f"&searchCriteria[filter_groups][0][filters][0][value]={quote(sku)}"
            "&searchCriteria[filter_groups][0][filters][0][condition_type]=eq"
        )
        data = self._request("GET", f"/rest/V1/inventory/source-items?{q}")
        if isinstance(data, dict):
            return list(data.get("items") or [])
        return []

    def sellable_qty(
        self,
        sku: str,
        *,
        safety_stock: float = 10.0,
    ) -> Dict[str, Any]:
        """Estimate sellable qty: sum MSI qty minus SafetyStock threshold policy.

        Magento SafetyStock forces OOS when qty ≤ 10; we mirror that for answers.
        """
        items = self.get_source_items(sku)
        total = 0.0
        sources: List[Dict[str, Any]] = []
        for item in items:
            qty = float(item.get("quantity") or 0)
            status = int(item.get("status") or 0)
            sources.append(
                {
                    "source_code": item.get("source_code"),
                    "quantity": qty,
                    "status": status,
                }
            )
            if status == 1:
                total += qty
        # Sellable after safety buffer (match DepositoTrujillo_SafetyStock spirit)
        sellable = max(0.0, total - safety_stock) if total > safety_stock else 0.0
        return {
            "sku": sku,
            "raw_qty": total,
            "sellable_qty": sellable,
            "safety_stock": safety_stock,
            "in_stock": sellable > 0,
            "sources": sources,
            "status": "ok",
        }

    def post_source_items(self, items: List[Dict[str, Any]]) -> Any:
        """POST /V1/inventory/source-items (MSI write).

        Each item: sku, source_code, quantity, status (1 in-stock / 0 OOS).
        Requires an integration token with inventory write ACL.
        """
        if not items:
            return {"message": "empty"}
        payload = {"sourceItems": items}
        return self._request("POST", "/rest/V1/inventory/source-items", body=payload)
