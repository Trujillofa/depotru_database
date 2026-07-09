"""Magento REST adapter (read-first; writes via ops scripts)."""

from depotru_integrations.magento.client import MagentoConfig, MagentoRestClient

__all__ = ["MagentoConfig", "MagentoRestClient"]
