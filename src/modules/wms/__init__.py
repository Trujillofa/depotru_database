"""WMS / WSM module — ops stock, coverage, OTIF (distinct from Magento MSI).

Phase 0 scaffold. J3 InvDetalleExistencias + KPI Q13/Q14 power this module.

Website stock allowlist (issue #182): see
``business_analyzer.core.website_warehouse_policy`` and CLI ``depotru-website-stock``.
"""

MODULE_NAME = "wms"

# Re-export policy helpers for platform tools
from business_analyzer.core.website_warehouse_policy import (  # noqa: E402
    WEBSITE_WAREHOUSE_DENYLIST,
    policy_summary,
    website_warehouse_allowlist,
)

__all__ = [
    "MODULE_NAME",
    "WEBSITE_WAREHOUSE_DENYLIST",
    "policy_summary",
    "website_warehouse_allowlist",
]
