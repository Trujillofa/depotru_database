from __future__ import annotations

from typing import TypedDict

from ..contracts.row_contracts import ExtractedRowValue, extract_row_value


class FinancialRowValues(TypedDict):
    revenue_iva: ExtractedRowValue
    revenue_no_iva: ExtractedRowValue
    cost: ExtractedRowValue
    quantity: ExtractedRowValue


def extract_financial_row_values(row: object) -> FinancialRowValues:
    return {
        "revenue_iva": extract_row_value(
            row, ["TotalMasIva", "PrecioTotal", "precio_total_iva"]
        ),
        "revenue_no_iva": extract_row_value(
            row, ["TotalSinIva", "PrecioUnitario", "precio_total"]
        ),
        "cost": extract_row_value(
            row, ["ValorCosto", "CostoUnitario", "cost", "costo"]
        ),
        "quantity": extract_row_value(row, ["Cantidad", "quantity"], default=1),
    }
