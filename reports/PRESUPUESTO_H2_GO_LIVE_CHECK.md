# Presupuesto H2 2026 — Go-live check

**Generated:** 2026-07-09T16:44:38
**Sales data through:** 2026-07-08
**Status:** H2 lock=`current` applied (Jul–Dec only); H1 untouched
**Commits:** `558c8bc` apply · `a3d9284` blurb comercial

## Verdict

| Check | Expected | Actual | OK? |
|-------|----------|--------|:---:|
| H1 company meta | ~$49,73B / 108 rows / 18 codes | $49.730.331.450 / 108 rows / 18 codes | ✅ |
| H2 company meta | ~$59,24B / 108 rows / 18 codes | $59.237.323.566 / 108 rows / 18 codes | ✅ |
| Full year meta | ~$108,97B | $108.967.655.016 | ✅ |
| 162 William in H2 | Present | Present | ✅ |

**DB side is go-live OK.** Use ERP **Julio 2026** (not junio) to confirm the UI.

## Company totals

- **H1 (ene–jun):** $49.730.331.450
- **H2 (jul–dic):** $59.237.323.566
- **Año 2026:** $108.967.655.016
- Implied H2 stretch vs H1-rebased base (~$52,2B): **+13,5%** (reshape, not a raise of the annual pie)

## June vs July meta (selected codes)

June = pre-revision flat month. July = post two-pot lock=current.

| Code | Nombre | Meta jun | Meta jul | Δ jul vs jun |
|------|--------|---------:|---------:|-------------:|
| 095 | DANIEL ENRIQUE CAICEDO | $841.936.064 | $1.219.143.547 | +44.8% |
| 035 | OSCAR IVAN POLANIA GARCIA | $884.632.192 | $1.024.307.407 | +15.8% |
| 116 | FELIPE RAMIREZ | $631.777.289 | $794.008.450 | +25.7% |
| 089 | ANDRES MAURICIO CORTEZ CULMA | $597.979.760 | $542.208.183 | -9.3% |
| 057 | ANDRES FELIPE VARGAS JOVEL | $684.878.319 | $950.279.599 | +38.8% |
| 060 | YULI ALEJANDRA HIGUERA | $457.769.546 | $1.016.279.780 | +122.0% |
| 003 | CARLOS EFREY PASCUAS | $502.681.514 | $667.977.338 | +32.9% |
| 106 | DIANA PATRICIA CULMA | $553.008.106 | $831.034.394 | +50.3% |
| 140 | LUIS ESTEBAN MEDINA | $368.848.015 | $580.838.672 | +57.5% |
| 000 | SIN COMISION | $284.444.882 | $372.335.282 | +30.9% |
| 130 | JAVIER ANDRES APACHE | $333.213.904 | $414.803.229 | +24.5% |
| 163 | BETSY GUZMAN | $291.987.997 | $429.272.056 | +47.0% |
| 102 | JULIAN ANDRES PINEDA | $138.482.932 | $263.687.695 | +90.4% |
| 131 | OLGA LUCIA TORRES | $218.290.773 | $109.641.926 | -49.8% |
| 044 | HUBER SANTIAGO ENCISO | $159.178.263 | $325.445.605 | +104.5% |
| 159 | LINA ISABEL TOVAR | $55.490.894 | $129.450.518 | +133.3% |
| 162 | WILLIAM HERNANDO QUINTERO G | $14.363.389 | $34.755.396 | +142.0% |
| 164 | CRISTIAN GUSTAVO | $338.743 | $819.664 | +142.0% |

### Direction check (apply package)

| Code | Expected | Observed jul vs jun |
|------|----------|---------------------|
| 131 | down | down ($108.648.847) ✅ |
| 089 | down | down ($55.771.577) ✅ |
| 044 | up | up ($166.267.342) ✅ |
| 095 | up | up ($377.207.483) ✅ |
| 060 | up | up ($558.510.234) ✅ |

## Julio MTD cumplimiento (code-only, through 2026-07-08)

Rough signal only: actual = `vendedor_codigo` on `banco_datos` (not full Asignado attribution). Month incomplete.

| Code | Meta jul | Ventas MTD | Cumpl. MTD |
|------|---------:|-----------:|-----------:|
| 095 | $1.219.143.547 | $225.503.576 | 18.5% |
| 035 | $1.024.307.407 | $204.028.894 | 19.9% |
| 060 | $1.016.279.780 | $56.231.500 | 5.5% |
| 057 | $950.279.599 | $138.318.471 | 14.6% |
| 106 | $831.034.394 | $47.704.077 | 5.7% |
| 116 | $794.008.450 | $146.058.454 | 18.4% |
| 003 | $667.977.338 | $50.150.355 | 7.5% |
| 140 | $580.838.672 | $25.857.033 | 4.5% |
| 089 | $542.208.183 | $66.116.074 | 12.2% |
| 163 | $429.272.056 | $79.439.879 | 18.5% |
| 130 | $414.803.229 | $22.983.434 | 5.5% |
| 000 | $372.335.282 | $77.180.231 | 20.7% |
| 044 | $325.445.605 | $135.254.463 | 41.6% |
| 102 | $263.687.695 | $37.367.962 | 14.2% |
| 159 | $129.450.518 | $-2.354 | -0.0% |
| 131 | $109.641.926 | $17.087.276 | 15.6% |
| 162 | $34.755.396 | $2.095.422 | 6.0% |
| 164 | $819.664 | $3.012.530 | 367.5% |
| **TOTAL** | $9.706.288.739 | $1.334.387.277 | 13.7% |

## Field hygiene (this week)

From purity + ownership card — **ops, not code:**

1. **044 = Huber only** — Daniel → **095**, Julián → **102** (June purity was already clean on 044; keep it).
2. **131 = Olga Calle 5 (FET)** — Carlos → **003**, Diana → **106** (still the main purity error).
3. **163 = Betsy** (+ crédito de Huber); Asignado 163 gana si Factura dice Huber.
4. **162** only for William Sika (not 123/133).

### Live purity (last 7 days, through ~2026-07-09)

| Sev | Code | Issue |
|-----|------|--------|
| **error** | **131** | Carlos ~**$14,0M** on 131 (should be **003**); multi-name + FED not FET |
| warn | 131 | Same volume outside preferred sede FET |
| info | 133 | Tiny orphan (~$83k) → prefer **162** |

**044** in last 7d: Huber-only clean.
Source: [`VENDOR_CODE_PURITY_last7d.md`](VENDOR_CODE_PURITY_last7d.md)

Re-check: `python scripts/utils/vendor_code_purity.py --days 7`

## Your 10 minutes

1. ERP → **Ejecución Presupuesto Vendedores** → mes **JULIO** / año **2026** (no junio).
2. Compartir blurb: [`PRESUPUESTO_H2_BLURB_COMERCIAL.md`](PRESUPUESTO_H2_BLURB_COMERCIAL.md)
3. Dec de piso: Carlos→003; 044=Huber.

## Links

| Doc | Path |
|------|------|
| Blurb comercial | [`PRESUPUESTO_H2_BLURB_COMERCIAL.md`](PRESUPUESTO_H2_BLURB_COMERCIAL.md) |
| Apply package | [`PRESUPUESTO_H2_APPLY_CURRENT.md`](PRESUPUESTO_H2_APPLY_CURRENT.md) |
| Compare lock=current | [`PRESUPUESTO_H2_COMPARE_TWOPOT_LOCKCURRENT.md`](PRESUPUESTO_H2_COMPARE_TWOPOT_LOCKCURRENT.md) |
| Purity last 7d | [`VENDOR_CODE_PURITY_last7d.md`](VENDOR_CODE_PURITY_last7d.md) |
| Hygiene duals | [`CODE_HYGIENE_VENDOR_DUALS_2026-07.md`](CODE_HYGIENE_VENDOR_DUALS_2026-07.md) |

*Read-only verification — no presupuesto writes in this check.*
