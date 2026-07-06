# J3System — Retrieve `Almacen` per Sale

> Ported from [depositotrujillo.co PR #33](https://github.com/Trujillofa/depositotrujillo.co/pull/33) (branch `docs/j3system-sales-warehouse-query`).

## Schema Relationship

```
InvVentas (sales header)              InvImpresionFactura (invoice line items)
├── VentaID          int    PK  ◄───  ├── VentaID          numeric    FK
├── NumeroDocumento  numeric          ├── Almancen         nvarchar(5)   ◄── warehouse code
├── Fecha            date             ├── Articulos        nvarchar(20)
├── TercerosID       int              ├── Descripcion      nvarchar(200)
├── NroFactura       nvarchar(50)     ├── Cantidad         decimal
├── DocumentosID     int              ├── Iva              decimal
└── VendedorID       int              ├── SinIva           money
                                      ├── ConIva           money
                                      └── ...
```

- **`InvVentas.VentaID`** (int) ↔ **`InvImpresionFactura.VentaID`** (numeric) — 1:N (one sale → multiple line items).
- Cast required: `CAST(InvImpresionFactura.VentaID AS int)` because the types differ.
- The warehouse column is **`Almancen`** (typo in J3System schema — missing second 'a').
- Decode codes via `AdmAlmacen.AlmacenCodigo` → `AdmAlmacen.AlmacenNombre`.

## Working Query

```sql
SELECT
    v.VentaID,
    v.NumeroDocumento,
    v.Fecha,
    v.NroFactura,
    v.TercerosID,
    iif.Almancen,
    a.AlmacenNombre
FROM InvVentas v
JOIN InvImpresionFactura iif ON CAST(iif.VentaID AS int) = v.VentaID
LEFT JOIN AdmAlmacen a ON a.AlmacenCodigo = iif.Almancen
ORDER BY v.Fecha DESC
```

## Warehouse Codes

| Code | Name |
|------|------|
| `ALM` | 001 |
| `SUR` | SUR |
| `BD6` | BD6 |
| `DIS` | DISTRIBUCIONES |
| `BOD` | MANGUERAS |
| `BDT` | BODEGA AJUSTES TEMPORALES |
| `FLO` | ALMACEN FLORENCIA |
| `CEN` | 005 GARANTIAS |
| `MDL` | MERCADO LIBRE |
| `EXH` | BOD EXHIBICION ALMACEN |
| `TRA` | MCIA COMITECAFE |
| `CON` | CONTABILIDAD |
| `B.ROT` | PRODUCTOS DE BAJA ROTACION |
| `EXD` | BOD EXHIBICION DISTRIBUCIONES |

## Caveats

- One `VentaID` maps to **multiple rows** in `InvImpresionFactura` (one per line item). If you need one warehouse per sale, use `DISTINCT` or pick the first non-empty `Almancen` — some rows have `Almancen = ''`.
- `AdmAlmacenUbicacion` exists if physical location detail is needed beyond the warehouse code.
