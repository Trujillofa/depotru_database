# DEPOSITO TRUJILLO SAS - Investigation Report

**Generated:** 2025-11-26
**Status:** Internal Operations - EXCLUDED from Customer Analysis

---

## Summary

**DEPOSITO TRUJILLO SAS** represents **internal inventory operations**, NOT customer sales.

### Transaction Details:

| Year | Transactions | Revenue | Profit | Units |
|------|--------------|---------|--------|-------|
| 2024 | 174 | $144,912,257 | $39,967,981 | 1,675 |
| 2025 | 309 | $167,255,310 | $49,725,202 | 2,962 |
| **Total** | **483** | **$312,167,567** | **$89,693,183** | **4,637** |

---

## Document Codes Found:

- **YX** - Inventory transfers/adjustments
- **ISC** - Internal stock corrections

These document types represent internal operations, not customer sales transactions.

---

## Sample Transactions (Nov 2025):

All transactions show single-unit inventory adjustments across multiple SKUs:

| Date | Doc | SKU | Product | Quantity | Revenue |
|------|-----|-----|---------|----------|---------|
| 2025-11-24 | YX | 0020280001 | SIKA 1 X 1 KG | 1 | $19,048 |
| 2025-11-24 | YX | 0020280002 | SIKA 1 X 2 KG | 1 | $37,858 |
| 2025-11-24 | YX | 0020280049 | SIKADUR 31 ADH/GRIS 2KG | 1 | $286,472 |
| 2025-11-24 | YX | 0020280058 | SIKAFLEX 1A PLUS 300CC BLANCO | 1 | $52,203 |
| 2025-11-14 | ISC | 0020280212 | SIKAFLEX 1A PLUS 300CC GRIS | 4 | $208,808 |

Pattern: Small quantities (typically 1-4 units) across many different products, suggesting inventory adjustments rather than customer orders.

---

## Action Taken:

### Updated Filters in `sika_analysis.py`:

```sql
WHERE categoria = 'PRODUCTOS SIKA'
  AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
  AND TercerosNombres != 'DEPOSITO TRUJILLO SAS'
  AND ano IN (2024, 2025)
```

### Exclusions Applied:
1. **Customer Name:** DEPOSITO TRUJILLO SAS
2. **Document Codes:** YX, ISC (in addition to existing XY, AS, TS)

---

## Impact on Analysis:

### Revenue Adjustment:
- **Before exclusion:** $4,771,066,918 (2024), $5,716,676,620 (2025)
- **After exclusion:** $4,626,154,661 (2024), $5,549,421,310 (2025)
- **Reduction:** $144.9M (2024), $167.3M (2025)

### Customer Count:
- **Before:** 4,336 (2024), 5,018 (2025)
- **After:** 4,335 (2024), 5,017 (2025)
- **Change:** -1 customer per year (DEPOSITO TRUJILLO SAS removed)

---

## Conclusion:

✅ **DEPOSITO TRUJILLO SAS has been correctly excluded from customer analysis**

These transactions represent internal inventory management operations, not customer sales. The updated analysis now provides a more accurate picture of actual customer revenue and performance.

All reports have been regenerated with corrected data:
- `/home/yderf/SIKA_ANALYSIS_REPORT.md` (English)
- `/home/yderf/REPORTE_SIKA_ESPANOL.md` (Spanish)
- `/home/yderf/sika_analysis_report.json` (Raw data)
