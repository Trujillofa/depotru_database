# Read-only J3 comparison

80 baseline calls (20 queries × 2 limits × 2 refs), plus 40 integrated calls; all completed without errors.
Counts are returned rows, not catalog totals. Precision is evaluated separately from count.

| # | Limit | Query | Main | Advisor | Integrated | Assessment |
|---|---:|---|---:|---:|---:|---|
| 1 | 6 | `sikafill galon` | 6 | 6 | 6 | Preserves advisor recall and first six. |
| 1 | 25 | `sikafill galon` | 10 | 25 | 25 | Preserves advisor recall and first six. |
| 2 | 6 | `varila 3/8` | 0 | 0 | 0 | Unchanged empty; typo suggestions remain a separate confirmation path. |
| 2 | 25 | `varila 3/8` | 0 | 0 | 0 | Unchanged empty; typo suggestions remain a separate confirmation path. |
| 3 | 6 | `cemento gris` | 6 | 6 | 6 | Same SKU order; stock changed between sequential runs. |
| 3 | 25 | `cemento gris` | 8 | 8 | 8 | Same SKU order; stock changed between sequential runs. |
| 4 | 6 | `sikafill` | 6 | 6 | 6 | Preserves advisor recall; stock drift on one SKU. |
| 4 | 25 | `sikafill` | 10 | 25 | 25 | Preserves advisor recall; stock drift on one SKU. |
| 5 | 6 | `sikafill 7 galon` | 6 | 6 | 6 | Preserves advisor precision: family 7 must match name, never a SKU substring. |
| 5 | 25 | `sikafill 7 galon` | 10 | 12 | 12 | Preserves advisor precision: family 7 must match name, never a SKU substring. |
| 6 | 6 | `sikafill 7 x galon precio` | 6 | 0 | 6 | Improves main recall at 25; noise removed and family 7 enforced. |
| 6 | 25 | `sikafill 7 x galon precio` | 10 | 0 | 12 | Improves main recall at 25; noise removed and family 7 enforced. |
| 7 | 6 | `precio sikafill` | 6 | 4 | 6 | Improves main recall at 25; price is noise, not a product-name constraint. |
| 7 | 25 | `precio sikafill` | 10 | 4 | 25 | Improves main recall at 25; price is noise, not a product-name constraint. |
| 8 | 6 | `sikafill galón` | 0 | 0 | 6 | Improves both: accented galón normalized. |
| 8 | 25 | `sikafill galón` | 0 | 0 | 25 | Improves both: accented galón normalized. |
| 9 | 6 | `sikafill/galon` | 6 | 0 | 6 | Preserves main first six, improves recall at 25; slash separated. |
| 9 | 25 | `sikafill/galon` | 10 | 0 | 25 | Preserves main first six, improves recall at 25; slash separated. |
| 10 | 6 | `sika fill galon` | 6 | 6 | 6 | Preserves advisor recall and first six. |
| 10 | 25 | `sika fill galon` | 10 | 25 | 25 | Preserves advisor recall and first six. |
| 11 | 6 | `varilla 3/8` | 5 | 3 | 3 | Preserves advisor three literal 3/8 matches; stock drift on one SKU. |
| 11 | 25 | `varilla 3/8` | 5 | 3 | 3 | Preserves advisor three literal 3/8 matches; stock drift on one SKU. |
| 12 | 6 | `varilla 1/2` | 6 | 3 | 3 | Preserves advisor three literal 1/2 matches; not a semantic suitability guarantee. |
| 12 | 25 | `varilla 1/2` | 10 | 3 | 3 | Preserves advisor three literal 1/2 matches; not a semantic suitability guarantee. |
| 13 | 6 | `cemento gris 50` | 3 | 3 | 3 | Preserves three 50KG/50 KG matches without matching 150KG or SKU digits. |
| 13 | 25 | `cemento gris 50` | 3 | 3 | 3 | Preserves three 50KG/50 KG matches without matching 150KG or SKU digits. |
| 14 | 6 | `cemento argos` | 6 | 6 | 6 | Identical to both. |
| 14 | 25 | `cemento argos` | 6 | 6 | 6 | Identical to both. |
| 15 | 6 | `sikaflex 1a` | 6 | 6 | 6 | Preserves advisor recall and first six; combo relevance is not certified. |
| 15 | 25 | `sikaflex 1a` | 10 | 12 | 12 | Preserves advisor recall and first six; combo relevance is not certified. |
| 16 | 6 | `sikadur 32` | 6 | 6 | 6 | Identical to both. |
| 16 | 25 | `sikadur 32` | 6 | 6 | 6 | Identical to both. |
| 17 | 6 | `pintura blanca` | 1 | 1 | 1 | Identical to both; one result does not certify family coverage. |
| 17 | 25 | `pintura blanca` | 1 | 1 | 1 | Identical to both; one result does not certify family coverage. |
| 18 | 6 | `tubo pvc 1/2` | 6 | 3 | 0 | LOWER COUNT: 0 intentionally replaces CPVC/11/2/PEGATUBO 1/256. No valid PVC 1/2 lost from either observed baseline. |
| 18 | 25 | `tubo pvc 1/2` | 10 | 3 | 0 | LOWER COUNT: 0 intentionally replaces CPVC/11/2/PEGATUBO 1/256. No valid PVC 1/2 lost from either observed baseline. |
| 19 | 6 | `impermeabilizante sika` | 0 | 0 | 0 | Unchanged empty; storefront category/semantic search not measured here. |
| 19 | 25 | `impermeabilizante sika` | 0 | 0 | 0 | Unchanged empty; storefront category/semantic search not measured here. |
| 20 | 6 | `revestimiento` | 0 | 0 | 0 | Unchanged empty; storefront categories remain a separate path. |
| 20 | 25 | `revestimiento` | 0 | 0 | 0 | Unchanged empty; storefront categories remain a separate path. |
