from decimal import Decimal
from typing import Union

import pytest

from src.analytics.financial_rows import extract_financial_row_values
from src.contracts.row_contracts import RowContractError, extract_row_value
from src.contracts.value_coercion import coerce_metric_value


@pytest.mark.parametrize(
    ("row", "keys", "default", "expected"),
    [
        ({"TotalMasIva": Decimal("116.50")}, ["TotalMasIva"], 0, 116.5),
        ({"TotalSinIva": "100.43"}, ["TotalSinIva"], 0, 100.43),
        ({"Cantidad": None}, ["Cantidad"], 1, 1),
        ({}, ["ValorCosto"], 0, 0),
    ],
)
def test_extract_row_value_parity_with_legacy(
    row: dict[str, object],
    keys: list[str],
    default: object,
    expected: Union[float, int],
) -> None:
    assert extract_row_value(row, keys, default=default) == expected


def test_extract_financial_row_values_handles_decimal_string_and_null():
    values = extract_financial_row_values(
        {
            "TotalMasIva": Decimal("116.50"),
            "TotalSinIva": "100.43",
            "ValorCosto": None,
            "Cantidad": None,
        }
    )

    assert values == {
        "revenue_iva": 116.5,
        "revenue_no_iva": 100.43,
        "cost": None,
        "quantity": 1,
    }


def test_coerce_metric_value_handles_grouped_numeric_strings():
    assert coerce_metric_value("1,234.56") == 1234.56


def test_coerce_metric_value_keeps_non_numeric_strings_unchanged():
    assert coerce_metric_value("1,23x") == "1,23x"


def test_analyzer_financial_path_uses_shared_coercion() -> None:
    from src.business_analyzer_combined import BusinessMetricsCalculator

    calculator = BusinessMetricsCalculator(
        [
            {
                "TotalMasIva": Decimal("116.50"),
                "TotalSinIva": "100.43",
                "ValorCosto": None,
                "Cantidad": None,
            }
        ]
    )

    metrics = calculator.calculate_financial_metrics()

    assert metrics["revenue"]["total_with_iva"] == 116.5
    assert metrics["revenue"]["total_without_iva"] == 100.43
    assert metrics["costs"]["total_cost"] == 0


@pytest.mark.parametrize("malformed_row", [None, 10, ["not", "a", "mapping"]])
def test_extract_row_value_raises_for_malformed_rows(malformed_row: object) -> None:
    with pytest.raises(RowContractError, match="Row payload must be a mapping"):
        _ = extract_row_value(malformed_row, ["TotalMasIva"], default=0)


def test_extract_financial_row_values_raises_for_malformed_payload() -> None:
    with pytest.raises(RowContractError, match="Row payload must be a mapping"):
        _ = extract_financial_row_values("wrong")
