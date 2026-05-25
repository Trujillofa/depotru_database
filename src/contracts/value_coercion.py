from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import cast

from typing_extensions import TypeAlias

NormalizedMetricValue: TypeAlias = "float | int | str | date | datetime | None"

_NUMERIC_STRING_PATTERN = re.compile(r"^[+-]?(?:\d{1,3}(?:,\d{3})*|\d+)(?:\.\d+)?$")


def looks_like_numeric_string(value: str) -> bool:
    return bool(_NUMERIC_STRING_PATTERN.fullmatch(value.strip()))


def coerce_metric_value(value: object) -> NormalizedMetricValue:
    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, str):
        stripped = value.strip()
        if looks_like_numeric_string(stripped):
            try:
                return float(stripped.replace(",", ""))
            except ValueError:
                return value

    return cast(NormalizedMetricValue, value)
