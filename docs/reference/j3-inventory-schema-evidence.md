# Evidencia de esquema de inventario J3 (solo metadatos)

> Metadata-only schema note (22 oct 2026). Source: `describe_table` tool of the
> `depotru-database` MCP against database `J3System`, schema `dbo`. Only column names and types;
> no business/row data was read. The tool reports no precision or scale for `decimal`/`numeric`
> columns (`max_length` is null).

## Columnas relevantes para `catalog.stock`

| Tabla | Columna | Tipo | Nullable |
|---|---|---|---|
| `InvDetalleExistencias` | `SaldoActual` | `decimal` | sí |
| `InvDetalleExistencias` | `Ano` | `numeric` | no |
| `InvDetalleExistencias` | `AlmacenID` | `int` | no |

## Qué se puede afirmar

- `InvDetalleExistencias.AlmacenID` es `int NOT NULL`.
- `InvDetalleExistencias.SaldoActual` es `decimal NULL`.
- `InvDetalleExistencias.Ano` es `numeric NOT NULL`.

## Qué NO se puede afirmar con esta evidencia

- La precisión y escala exactas de `SaldoActual` (y de las demás columnas `decimal`/`numeric`).
- El tipo concreto que devuelve el driver Python para una columna `decimal`/`numeric` (p. ej.
  `Decimal` vía pymssql): no se probó aquí.
