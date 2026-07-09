"""Affinity → Magento catalog bridge contract."""

from depotru_integrations.affinity.contract import (
    AFFINITY_CONTRACT_VERSION,
    CROSSSELL_CSV_COLUMNS,
    RELATED_CSV_COLUMNS,
    validate_crosssell_csv_header,
    validate_related_csv_header,
)

__all__ = [
    "AFFINITY_CONTRACT_VERSION",
    "CROSSSELL_CSV_COLUMNS",
    "RELATED_CSV_COLUMNS",
    "validate_crosssell_csv_header",
    "validate_related_csv_header",
]
