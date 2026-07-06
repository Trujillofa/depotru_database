# J3System — Retrieve `Almacen` per Sale

> Ported from [depositotrujillo.co PR #33](https://github.com/Trujillofa/depositotrujillo.co/pull/33), updated for production schema coverage.

## Schema Relationship

```
InvVentas (sales header)              InvVentasDetalle (sale line items)
├── VentaID          int    PK  ◄───  ├── VentaID          int           FK
├── NumeroDocumento  numeric          ├── AlmacenID        int           ◄── warehouse FK
├── Fecha            date             ├── Cantidad         decimal
├── TercerosID       int              ├── VentaSinIva      money
├── NroFactura       nvarchar(50)     ├── VentaMasIva      money
├── DocumentosID     int              └── ...
└── VendedorID       int

AdmAlmacen (warehouse master)
├── AlmacenID        int    PK
├── AlmacenCodigo    nvarchar(5)   ◄── warehouse code (ALM, SUR, BD6, …)
└── AlmacenNombre    nvarchar(200)
```

- **`InvVentas.VentaID`** (int) ↔ **`InvVentasDetalle.VentaID`** (int) — 1:N (one sale → multiple line items).
- Warehouse per line: **`InvVentasDetalle.AlmacenID`** → **`AdmAlmacen.AlmacenID`** → decode **`AlmacenCodigo`** / **`AlmacenNombre`**.
- **`InvImpresionFactura.Almancen`** exists for e-invoice print rows but only covers a small recent subset (~55k rows); use **`InvVentasDetalle`** for complete historical coverage.

## Working Query

```sql
SELECT
    v.VentaID,
    v.NumeroDocumento,
    v.Fecha,
    v.NroFactura,
    v.TercerosID,
    a.AlmacenCodigo AS Almancen,
    a.AlmacenNombre
FROM InvVentas v
JOIN InvVentasDetalle d ON d.VentaID = v.VentaID
LEFT JOIN AdmAlmacen a ON a.AlmacenID = d.AlmacenID
WHERE a.AlmacenCodigo IS NOT NULL AND a.AlmacenCodigo <> ''
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

- One `VentaID` maps to **multiple rows** in `InvVentasDetalle` (one per line item). If you need one warehouse per sale, use `CROSS APPLY TOP 1 d.AlmacenID` per `VentaID`.
- Filter with `a.AlmacenCodigo IS NOT NULL AND a.AlmacenCodigo <> ''` when excluding unassigned lines.
- `InvImpresionFactura` may be used for recent e-invoice staging but does not join to most historical `InvVentas` rows.
- `AdmAlmacenUbicacion` exists if physical location detail is needed beyond the warehouse code.

## Code & Vanna Integration

Python SQL builders live in `business_analyzer.core.j3system_sales_warehouse` (`build_sales_warehouse_detail_sql`, `build_sales_by_warehouse_sql`, `build_one_warehouse_per_sale_sql`). Vanna picks them up via `get_j3system_training_examples()` and runtime routing in `AIVanna.generate_sql` for warehouse-per-sale questions.
