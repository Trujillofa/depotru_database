"""Catalog / digital module — affinity, Magento related/cross-sell bridge."""

from depotru_integrations.affinity.contract import (
    AFFINITY_CONTRACT_VERSION,
    CROSSSELL_POLICY,
    RELATED_POLICY,
)

MODULE_NAME = "catalog"

__all__ = [
    "AFFINITY_CONTRACT_VERSION",
    "CROSSSELL_POLICY",
    "MODULE_NAME",
    "RELATED_POLICY",
]
