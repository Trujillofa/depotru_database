from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TypedDict, TypeVar, cast, overload

from typing_extensions import TypeAlias

from .value_coercion import NormalizedMetricValue, coerce_metric_value


class RowContractError(ValueError):
    pass


ExtractedRowValue: TypeAlias = NormalizedMetricValue
SQLRowLike: TypeAlias = Mapping[str, object]


class SQLMetricRow(TypedDict, total=False):
    TotalMasIva: object
    PrecioTotal: object
    precio_total_iva: object
    TotalSinIva: object
    PrecioUnitario: object
    precio_total: object
    ValorCosto: object
    CostoUnitario: object
    cost: object
    costo: object
    Cantidad: object
    quantity: object
    cantidad: object
    TercerosNombres: object
    NombreCliente: object
    customer_name: object
    cliente: object
    ArticulosNombre: object
    Descripcion: object
    product_name: object
    producto: object
    Fecha: object
    fecha: object
    date: object
    Categoria: object
    categoria: object
    category: object


TDefault = TypeVar("TDefault")


def _ensure_mapping(row: object) -> SQLRowLike:
    if not isinstance(row, Mapping):
        raise RowContractError("Row payload must be a mapping[str, object]")
    return cast(SQLRowLike, row)


def coerce_row_value(value: object) -> ExtractedRowValue:
    return coerce_metric_value(value)


@overload
def extract_row_value(row: object, keys: Sequence[str]) -> ExtractedRowValue: ...


@overload
def extract_row_value(
    row: object, keys: Sequence[str], default: TDefault
) -> ExtractedRowValue | TDefault: ...


def extract_row_value(
    row: object, keys: Sequence[str], default: object = None
) -> ExtractedRowValue | object:
    if not keys:
        raise RowContractError("At least one row key must be provided")

    row_mapping = _ensure_mapping(row)

    for key in keys:
        value = row_mapping.get(key)
        if value is not None:
            return coerce_row_value(value)

    return default
