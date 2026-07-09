"""Build 2026 vendor/line presupuesto metas from 2025 actuals.

Active vendors = last complete calendar month sales codes ∪ FEF (Sika) codes,
with explicit merges (William Quintero → 162). Company stretch default +25%.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import (
    Dict,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
    Tuple,
)

# Ownership card + Factura map live in vendor_ownership (single source of truth).
from business_analyzer.core.vendor_ownership import (
    DEFAULT_CODE_MERGES,
    OFFICIAL_CODE_NAMES,
    OFFICIAL_FACTURA_OWNERS,
)
from business_analyzer.core.vendor_ownership import (
    official_owner_for_factura as _official_owner_for_factura,
)
from business_analyzer.core.vendor_ownership import (
    parse_asignado_code as _parse_asignado_code_vo,
)

DEFAULT_GROWTH = 0.25
DEFAULT_NEWCOMER_GROWTH = 0.10
DEFAULT_NEWCOMER_CAP_PCT = 0.01
DEFAULT_FLOOR_FACTOR = 1.0
DEFAULT_META_MIN_MULT = 0.95
DEFAULT_META_MAX_MULT = 1.40
GROWTH_POT_EXCLUDED_CODES = frozenset({"000"})
H1_MONTHS: Tuple[int, ...] = (1, 2, 3, 4, 5, 6)
H2_MONTHS: Tuple[int, ...] = (7, 8, 9, 10, 11, 12)
SIKA_DOC_CODE = "FEF"
EXCLUDED_DOC_CODES = ("XY", "AS", "TS")
EXCLUDED_PRODUCT_NAMES = (
    "SERVICIO DE CORTE",
    "BOLSA BIODEGRADABLE PARA ENTREGA",
)


def year_month_to_periodo(year: int, month: int) -> int:
    if not (1 <= month <= 12):
        raise ValueError(f"Month must be between 1 and 12, got {month}")
    if month < 10:
        return year * 10 + month
    return year * 100 + month


def periodo_calendar_parts(periodo: int) -> Tuple[int, int]:
    if periodo >= 100000:
        return periodo // 100, periodo % 100
    return periodo // 10, periodo % 10


def last_complete_month(as_of: date) -> Tuple[int, int]:
    """Return (year, month) for the last complete calendar month before as_of's month."""
    if as_of.month == 1:
        return as_of.year - 1, 12
    return as_of.year, as_of.month - 1


def normalize_code(code: Optional[str]) -> Optional[str]:
    if code is None:
        return None
    c = str(code).strip()
    return c or None


def normalize_name(name: Optional[str]) -> str:
    if not name:
        return ""
    return " ".join(str(name).upper().split())


def apply_code_merge(code: str, merges: Mapping[str, str]) -> str:
    """Resolve canonical code (follow merge chain once or more)."""
    seen = set()
    cur = code
    while cur in merges and cur not in seen:
        seen.add(cur)
        cur = merges[cur]
    return cur


def canonical_active_codes(
    raw_codes: Iterable[str],
    merges: Mapping[str, str] = DEFAULT_CODE_MERGES,
) -> List[str]:
    """Unique sorted active meta codes after merges."""
    out = {apply_code_merge(normalize_code(c) or "", merges) for c in raw_codes}
    out.discard("")
    # Drop pure source codes that only exist as merge sources
    for src, dst in merges.items():
        if src in out and src != dst:
            # source stays only if it was not merged away — we always drop sources
            out.discard(src)
    return sorted(out)


@dataclass
class SalesKey:
    code: Optional[str]
    name: str
    year: int
    month: int


def parse_asignado_code(asignado: Optional[str]) -> Optional[str]:
    """Extract leading code from values like ``044-HUBER SANTIAGO ENCISO``."""
    result: Optional[str] = _parse_asignado_code_vo(asignado)
    return result


def official_owner_for_factura(name: Optional[str]) -> Optional[str]:
    """Commercial owner code from VendedorFactura (budget rule overrides)."""
    result: Optional[str] = _official_owner_for_factura(name)
    return result


def build_name_to_code_map(
    coded_name_sales: Sequence[Tuple[str, str, float]],
    *,
    allowed_codes: Optional[Sequence[str]] = None,
    merges: Mapping[str, str] = DEFAULT_CODE_MERGES,
) -> Dict[str, str]:
    """Majority map normalize(name) → canonical code from (code, name, sales).

    Official commercial owners always win over majority vote.
    """
    allowed = set(allowed_codes) if allowed_codes is not None else None
    scores: Dict[str, Dict[str, float]] = {}
    for code, name, sales in coded_name_sales:
        c = normalize_code(code)
        n = normalize_name(name)
        if not c or not n:
            continue
        c = apply_code_merge(c, merges)
        if allowed is not None and c not in allowed:
            continue
        scores.setdefault(n, {})
        scores[n][c] = scores[n].get(c, 0.0) + float(sales)
    mapping: Dict[str, str] = {}
    for n, by_code in scores.items():
        mapping[n] = max(by_code.items(), key=lambda kv: kv[1])[0]
    # Force commercial ownership
    for n in list(mapping.keys()):
        owner = official_owner_for_factura(n)
        if owner:
            mapping[n] = apply_code_merge(owner, merges)
    return mapping


def attribute_sale(
    *,
    code: Optional[str] = None,
    name: Optional[str] = None,
    asignado: Optional[str] = None,
    name_to_code: Mapping[str, str],
    active_codes: Sequence[str],
    merges: Mapping[str, str] = DEFAULT_CODE_MERGES,
    pool_key: str = "POOL",
) -> str:
    """Return active canonical code or POOL.

    Priority (budget):
      1) VendedorAsignado leading code  (e.g. transferred book: 163-BETSY)
      2) VendedorFactura official owner / name map  (fallback only)
      3) vendedor_codigo
      4) POOL

    Huber→Betsy credit handoff: keep Asignado 163 on those customers; do not
    reassign to 044 just because Factura still shows HUBER.
    """
    active = set(active_codes)

    # 1) Asignado
    ac = parse_asignado_code(asignado)
    if ac:
        ac = apply_code_merge(ac, merges)
        if ac in active:
            return ac
        return pool_key

    # 2) Factura — official owner then statistical map
    n = normalize_name(name)
    owner = official_owner_for_factura(n)
    if owner:
        owner = apply_code_merge(owner, merges)
        if owner in active:
            return owner
    if n and n in name_to_code:
        mapped = apply_code_merge(name_to_code[n], merges)
        if mapped in active:
            return mapped

    # 3) Explicit codigo (same as Asignado when both present in ERP)
    c = normalize_code(code)
    if c:
        c = apply_code_merge(c, merges)
        if c in active:
            return c
        return pool_key

    return pool_key


def aggregate_attributed(
    rows: Sequence[Tuple],
    *,
    name_to_code: Mapping[str, str],
    active_codes: Sequence[str],
    merges: Mapping[str, str] = DEFAULT_CODE_MERGES,
) -> Dict[Tuple[str, int, int], float]:
    """rows: (code, factura, year, month, sales) or
    (code, factura, asignado, year, month, sales).
    """
    out: Dict[Tuple[str, int, int], float] = {}
    for row in rows:
        if len(row) == 5:
            code, name, year, month, sales = row
            asignado = None
        else:
            code, name, asignado, year, month, sales = row
        attr = attribute_sale(
            code=code,
            name=name,
            asignado=asignado,
            name_to_code=name_to_code,
            active_codes=active_codes,
            merges=merges,
        )
        key = (attr, int(year), int(month))
        out[key] = out.get(key, 0.0) + float(sales)
    return out


def redistribute_pool(
    attributed: Mapping[Tuple[str, int, int], float],
    *,
    active_codes: Sequence[str],
    base_year: int = 2025,
    pool_key: str = "POOL",
) -> Dict[Tuple[str, int], float]:
    """Collapse to (code, month) for base_year; spread POOL by vendor annual share.

    Returns {(code, month): sales} for active codes only.
    """
    by_vm: Dict[Tuple[str, int], float] = {}
    pool_by_month: Dict[int, float] = {}
    annual: Dict[str, float] = {c: 0.0 for c in active_codes}

    for (code, year, month), sales in attributed.items():
        if year != base_year:
            continue
        if code == pool_key:
            pool_by_month[month] = pool_by_month.get(month, 0.0) + sales
            continue
        if code not in annual:
            # inactive attributed (shouldn't happen) → pool
            pool_by_month[month] = pool_by_month.get(month, 0.0) + sales
            continue
        by_vm[(code, month)] = by_vm.get((code, month), 0.0) + sales
        annual[code] += sales

    total_annual = sum(annual.values())
    if total_annual <= 0:
        # edge: no active base — leave pool undistributed (caller must handle)
        return by_vm

    for month, pool_sales in pool_by_month.items():
        if pool_sales <= 0:
            continue
        for code in active_codes:
            share = annual[code] / total_annual
            by_vm[(code, month)] = by_vm.get((code, month), 0.0) + pool_sales * share

    return by_vm


def draft_metas_from_base(
    base_vm: Mapping[Tuple[str, int], float],
    *,
    active_codes: Sequence[str],
    target_year: int = 2026,
    growth: float = DEFAULT_GROWTH,
) -> Dict[Tuple[str, int], float]:
    """Meta_v,m = base_v,m * (1+growth); renormalize to sum(base)* (1+growth)."""
    del target_year  # API compatibility; metas are month-keyed only
    draft: Dict[Tuple[str, int], float] = {}
    base_total = 0.0
    for (code, month), sales in base_vm.items():
        if code not in active_codes:
            continue
        base_total += sales
        draft[(code, month)] = sales * (1.0 + growth)

    target = base_total * (1.0 + growth)
    draft_total = sum(draft.values())
    if draft_total > 0 and abs(draft_total - target) > 1e-6:
        scale = target / draft_total
        draft = {k: v * scale for k, v in draft.items()}
    return draft


def sum_code_months(
    vm: Mapping[Tuple[str, int], float],
    months: Sequence[int],
) -> Dict[str, float]:
    """Sum vendor-month values for the given calendar months."""
    wanted = set(months)
    out: Dict[str, float] = {}
    for (code, month), sales in vm.items():
        if month in wanted:
            out[code] = out.get(code, 0.0) + float(sales)
    return out


def h2_base_from_h1_seasonality(
    h1_by_code: Mapping[str, float],
    seasonality: Mapping[int, float],
    *,
    h2_months: Sequence[int] = H2_MONTHS,
    h1_months: Sequence[int] = H1_MONTHS,
) -> Dict[Tuple[str, int], float]:
    """H2 budget base from H1 actuals shaped by 2025 company seasonality.

    annual_implied_i = h1_i / sum(seasonality[H1])
    base_i,m = annual_implied_i * seasonality[m] for m in H2
    """
    h1_share = sum(float(seasonality.get(m, 0.0)) for m in h1_months)
    if h1_share <= 0:
        h1_share = 0.5
    out: Dict[Tuple[str, int], float] = {}
    for code, h1 in h1_by_code.items():
        c = str(code).strip() if code is not None else ""
        if not c or float(h1 or 0) <= 0:
            continue
        annual = float(h1) / h1_share
        for m in h2_months:
            out[(c, int(m))] = annual * float(seasonality.get(int(m), 0.0))
    return out


def apply_twopot_sqrt(
    base_vm: Mapping[Tuple[str, int], float],
    *,
    active_codes: Sequence[str],
    growth: float = DEFAULT_GROWTH,
    floor_factor: float = DEFAULT_FLOOR_FACTOR,
    min_mult: float = DEFAULT_META_MIN_MULT,
    max_mult: float = DEFAULT_META_MAX_MULT,
    exclude_from_growth: frozenset = GROWTH_POT_EXCLUDED_CODES,
    company_target: Optional[float] = None,
) -> Dict[Tuple[str, int], float]:
    """Two-pot growth: floor = factor×base; growth pot ∝ √base; cap; re-lock.

    Codes in ``exclude_from_growth`` (default ``000``) keep floor only and do
    not receive a share of the growth pot (their unused stretch stays in pot).
    ``company_target`` overrides base × (1+growth) — used to lock the company
    total to an externally fixed number (reshape-only mode).
    """
    active = set(active_codes)
    base_by_code: Dict[str, float] = {}
    for (code, _month), sales in base_vm.items():
        if code not in active:
            continue
        base_by_code[code] = base_by_code.get(code, 0.0) + float(sales)

    company_base = sum(base_by_code.values())
    if company_base <= 0:
        return {}

    if company_target is None:
        company_target = company_base * (1.0 + growth)
    floors = {c: b * floor_factor for c, b in base_by_code.items()}
    floor_sum = sum(floors.values())
    growth_pot = company_target - floor_sum

    if growth_pot < 0 and floor_sum > 0:
        scale_f = company_target / floor_sum
        floors = {c: v * scale_f for c, v in floors.items()}
        growth_pot = 0.0

    eligible = [
        c
        for c in active_codes
        if c in base_by_code and c not in exclude_from_growth and base_by_code[c] > 0
    ]
    weights = {c: math.sqrt(base_by_code[c]) for c in eligible}
    wsum = sum(weights.values()) or 1.0
    growth_alloc = {
        c: (growth_pot * weights[c] / wsum if growth_pot > 0 else 0.0) for c in eligible
    }

    annual_meta: Dict[str, float] = {}
    for c, b in base_by_code.items():
        raw = floors.get(c, 0.0) + growth_alloc.get(c, 0.0)
        lo = b * min_mult
        hi = b * max_mult
        annual_meta[c] = max(lo, min(hi, raw))

    tot = sum(annual_meta.values())
    if tot > 0:
        scale = company_target / tot
        annual_meta = {c: v * scale for c, v in annual_meta.items()}

    # Spread back to months using each code's base month mix
    month_bases: Dict[str, Dict[int, float]] = {}
    for (code, month), sales in base_vm.items():
        if code not in annual_meta:
            continue
        month_bases.setdefault(code, {})
        month_bases[code][month] = month_bases[code].get(month, 0.0) + float(sales)

    out: Dict[Tuple[str, int], float] = {}
    for code, meta in annual_meta.items():
        mb = month_bases.get(code) or {}
        bsum = sum(mb.values()) or 1.0
        for month, bv in mb.items():
            out[(code, month)] = meta * (bv / bsum)
    return out


def merge_h1_h2_metas(
    h1_metas: Mapping[Tuple[str, int], float],
    h2_metas: Mapping[Tuple[str, int], float],
) -> Dict[Tuple[str, int], float]:
    """Combine H1 months from one method with H2 months from another."""
    out: Dict[Tuple[str, int], float] = {}
    for (c, m), v in h1_metas.items():
        if m in H1_MONTHS:
            out[(c, m)] = float(v)
    for (c, m), v in h2_metas.items():
        if m in H2_MONTHS:
            out[(c, m)] = float(v)
    return out


def _row_float(value: object) -> float:
    """Coerce a comparison-row cell (float or None) to float for mypy."""
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def build_h2_revision_comparison(
    *,
    flat_metas: Mapping[Tuple[str, int], float],
    h1_by_code: Mapping[str, float],
    seasonality: Mapping[int, float],
    active_codes: Sequence[str],
    names: Mapping[str, str],
    growth: float = DEFAULT_GROWTH,
    floor_factor: float = DEFAULT_FLOOR_FACTOR,
    min_mult: float = DEFAULT_META_MIN_MULT,
    max_mult: float = DEFAULT_META_MAX_MULT,
    h2_company_lock: str = "growth",
) -> Tuple[List[Dict[str, object]], Dict[str, float]]:
    """Compare current flat×growth full-year vs H2 rebased two-pot+√.

    Hybrid year = H1 months from flat_metas + H2 months from two-pot on
    H1-seasonality base. No DB side effects.

    ``h2_company_lock``:
      - ``"growth"`` (default): H2 target = H2_base(H1) × (1+growth)
      - ``"current"``: H2 target = Σ current flat H2 metas (reshape only)

    Returns (per-vendor rows, company summary dict).
    """
    if h2_company_lock not in ("growth", "current"):
        raise ValueError(
            f"h2_company_lock must be 'growth' or 'current', got {h2_company_lock!r}"
        )
    h2_base = h2_base_from_h1_seasonality(h1_by_code, seasonality)
    h2_flat_on_h1base = draft_metas_from_base(
        h2_base, active_codes=active_codes, growth=growth
    )
    h2_base_company = sum(v for (c, m), v in h2_base.items() if c in set(active_codes))
    h2_target: Optional[float] = None
    if h2_company_lock == "current":
        h2_target = sum(v for (c, m), v in flat_metas.items() if m in H2_MONTHS)
    h2_twopot = apply_twopot_sqrt(
        h2_base,
        active_codes=active_codes,
        growth=growth,
        floor_factor=floor_factor,
        min_mult=min_mult,
        max_mult=max_mult,
        company_target=h2_target,
    )
    hybrid = merge_h1_h2_metas(flat_metas, h2_twopot)

    h1_meta_flat = sum_code_months(flat_metas, H1_MONTHS)
    h2_meta_flat = sum_code_months(flat_metas, H2_MONTHS)
    h2_meta_twopot = sum_code_months(h2_twopot, H2_MONTHS)
    h2_base_tot = sum_code_months(h2_base, H2_MONTHS)
    full_flat = sum_code_months(flat_metas, list(H1_MONTHS) + list(H2_MONTHS))
    full_hybrid = sum_code_months(hybrid, list(H1_MONTHS) + list(H2_MONTHS))

    codes = sorted(
        set(active_codes)
        | set(h1_by_code)
        | set(h1_meta_flat)
        | set(h2_meta_flat)
        | set(h2_meta_twopot)
    )
    rows: List[Dict[str, object]] = []
    for code in codes:
        h1_act = float(h1_by_code.get(code, 0.0) or 0.0)
        h1_m = float(h1_meta_flat.get(code, 0.0) or 0.0)
        h2_b = float(h2_base_tot.get(code, 0.0) or 0.0)
        h2_f = float(h2_meta_flat.get(code, 0.0) or 0.0)
        h2_t = float(h2_meta_twopot.get(code, 0.0) or 0.0)
        cumpl = (h1_act / h1_m * 100.0) if h1_m > 0 else None
        delta_h2 = h2_t - h2_f
        rows.append(
            {
                "vendedor_codigo": code,
                "vendedor_nombre": names.get(code) or OFFICIAL_CODE_NAMES.get(code, ""),
                "h1_actual": h1_act,
                "h1_meta_flat": h1_m,
                "h1_cumpl_pct": cumpl,
                "h2_base_from_h1": h2_b,
                "h2_meta_flat_2025": h2_f,
                "h2_meta_twopot_h1": h2_t,
                "h2_delta_twopot_vs_flat": delta_h2,
                "h2_delta_pct": (delta_h2 / h2_f * 100.0) if h2_f > 0 else None,
                "full_year_flat": float(full_flat.get(code, 0.0) or 0.0),
                "full_year_hybrid": float(full_hybrid.get(code, 0.0) or 0.0),
            }
        )

    rows.sort(key=lambda r: _row_float(r.get("h1_meta_flat")), reverse=True)

    company_h1_meta = sum(_row_float(r["h1_meta_flat"]) for r in rows)
    company_h1_act = sum(_row_float(r["h1_actual"]) for r in rows)
    summary: Dict[str, float] = {
        "growth": float(growth),
        "pool_note": 0.0,  # placeholder; filled by caller if needed
        "company_h1_meta_flat": company_h1_meta,
        "company_h1_actual": company_h1_act,
        "company_h1_cumpl_pct": (
            company_h1_act / company_h1_meta * 100.0 if company_h1_meta else 0.0
        ),
        "company_h2_meta_flat": sum(_row_float(r["h2_meta_flat_2025"]) for r in rows),
        "company_h2_base_from_h1": sum(_row_float(r["h2_base_from_h1"]) for r in rows),
        "company_h2_meta_twopot": sum(_row_float(r["h2_meta_twopot_h1"]) for r in rows),
        "company_full_flat": sum(_row_float(r["full_year_flat"]) for r in rows),
        "company_full_hybrid": sum(_row_float(r["full_year_hybrid"]) for r in rows),
        "company_h2_flat_on_h1base": sum(h2_flat_on_h1base.values()),
        "h2_lock_current": 1.0 if h2_company_lock == "current" else 0.0,
    }
    company_h2_twopot = summary["company_h2_meta_twopot"]
    if h2_base_company > 0:
        summary["implied_h2_growth_pct"] = (
            company_h2_twopot / h2_base_company - 1.0
        ) * 100.0
    return rows, summary


def render_h2_revision_markdown(
    rows: Sequence[Mapping[str, object]],
    summary: Mapping[str, float],
    *,
    title: str = "Presupuesto H2 revision dry-run",
    notes: Sequence[str] = (),
) -> str:
    """Markdown table: flat ×1.25 vs H1-rebased two-pot+√ (no DB writes)."""
    lines: List[str] = [
        f"# {title}",
        "",
        "## Method",
        "",
        "1. **Flat (current):** 2025 attributed base × company growth (after pool + newcomers).",
        "2. **H2 rebased two-pot+√:** H2 base = H1 actual annualized via 2025 seasonality; "
        "meta = 1.00× floor + growth pot by √base; `000` excluded from growth pot; "
        "caps 0.95×–1.40× base; re-lock to the H2 company target (see lock line below).",
        "3. **Hybrid full year:** H1 months keep flat metas; H2 months use two-pot.",
        "",
        "## Company summary",
        "",
        f"- Growth: {summary.get('growth', DEFAULT_GROWTH):.0%}",
        f"- H1 meta (flat): ${summary.get('company_h1_meta_flat', 0):,.0f}".replace(
            ",", "."
        ),
        f"- H1 actual: ${summary.get('company_h1_actual', 0):,.0f}".replace(",", "."),
        f"- H1 cumplimiento: {summary.get('company_h1_cumpl_pct', 0):.1f}%",
        f"- H2 meta flat (from 2025 path): "
        f"${summary.get('company_h2_meta_flat', 0):,.0f}".replace(",", "."),
        f"- H2 base from H1 signal: "
        f"${summary.get('company_h2_base_from_h1', 0):,.0f}".replace(",", "."),
        f"- H2 meta two-pot on H1 base: "
        f"${summary.get('company_h2_meta_twopot', 0):,.0f}".replace(",", "."),
        "- H2 company lock: "
        + (
            "**current** (Σ = current flat H2; reshape only)"
            if summary.get("h2_lock_current")
            else f"**growth** (H2 base × {summary.get('growth', DEFAULT_GROWTH) + 1.0:.2f})"
        ),
        f"- Implied H2 growth vs H1-rebased base: "
        f"{summary.get('implied_h2_growth_pct', 0):+.1f}%",
        f"- Full-year flat: ${summary.get('company_full_flat', 0):,.0f}".replace(
            ",", "."
        ),
        f"- Full-year hybrid (H1 flat + H2 two-pot): "
        f"${summary.get('company_full_hybrid', 0):,.0f}".replace(",", "."),
        "",
        "## Per vendor",
        "",
        "| Code | Name | H1 actual | H1 meta flat | H1 % | "
        "H2 base(H1) | H2 meta flat | H2 meta 2pot | Δ H2 | Δ% |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        cumpl = r.get("h1_cumpl_pct")
        cumpl_s = f"{_row_float(cumpl):.1f}" if cumpl is not None else "—"
        dp = r.get("h2_delta_pct")
        dp_s = f"{_row_float(dp):+.1f}%" if dp is not None else "—"
        lines.append(
            "| {code} | {name} | ${h1a:,.0f} | ${h1m:,.0f} | {cumpl} | "
            "${h2b:,.0f} | ${h2f:,.0f} | ${h2t:,.0f} | ${d:,.0f} | {dp} |".format(
                code=r.get("vendedor_codigo"),
                name=(str(r.get("vendedor_nombre") or "")[:28]),
                h1a=_row_float(r.get("h1_actual")),
                h1m=_row_float(r.get("h1_meta_flat")),
                cumpl=cumpl_s,
                h2b=_row_float(r.get("h2_base_from_h1")),
                h2f=_row_float(r.get("h2_meta_flat_2025")),
                h2t=_row_float(r.get("h2_meta_twopot_h1")),
                d=_row_float(r.get("h2_delta_twopot_vs_flat")),
                dp=dp_s,
            ).replace(",", ".")
        )
    lines.append("")
    if notes:
        lines.append("## Notes")
        lines.append("")
        for n in notes:
            lines.append(f"- {n}")
        lines.append("")
    lines.extend(
        [
            "## Interpretation",
            "",
            "- Large **negative Δ H2** on a code = current flat meta over-located vs H1 run-rate "
            "(e.g. 131 if Olga book is small).",
            "- Large **positive Δ H2** = under-located vs H1 (e.g. 044 if residual book is larger).",
            "- Two-pot vs flat-on-same-H1-base only reshapes **growth**; H2 re-base is the big "
            "mislocation fix.",
            "- Company +25% on an H1-rebased H2 pie may still be aggressive if H1 run-rate is "
            "below the original stretch path — board decision.",
            "",
            "*Dry-run only — no DB writes.*",
            "",
        ]
    )
    return "\n".join(lines)


def inject_newcomers(
    metas: MutableMapping[Tuple[str, int], float],
    *,
    newcomer_h1: Mapping[str, float],
    active_codes: Sequence[str],
    company_h1_2025: float,
    seasonality: Mapping[int, float],
    newcomer_growth: float = DEFAULT_NEWCOMER_GROWTH,
    newcomer_cap_pct: float = DEFAULT_NEWCOMER_CAP_PCT,
    established_2025_annual: Mapping[str, float],
) -> Dict[Tuple[str, int], float]:
    """Add metas for newcomers with ~0 2025 base; fund by shaving established.

    newcomer_h1: code → 2026 H1 sales
    seasonality: month → share (sum≈1)
    """
    # Newcomers: active, some H1 sales, little/no 2025 base
    newcomers = [
        c
        for c in active_codes
        if newcomer_h1.get(c, 0.0) > 0
        and established_2025_annual.get(c, 0.0) < 1_000_000
    ]
    if not newcomers:
        return dict(metas)

    h1_share = sum(seasonality.get(m, 0.0) for m in range(1, 7))
    if h1_share <= 0:
        h1_share = 0.5

    company_target = sum(metas.values())
    cap = company_target * newcomer_cap_pct
    newcomer_annuals: Dict[str, float] = {}
    for c in newcomers:
        h1 = newcomer_h1.get(c, 0.0)
        annual = (h1 / h1_share) * (1.0 + newcomer_growth)
        newcomer_annuals[c] = annual
    total_new = sum(newcomer_annuals.values())
    if total_new > cap > 0:
        scale = cap / total_new
        newcomer_annuals = {c: a * scale for c, a in newcomer_annuals.items()}
        total_new = cap

    if total_new <= 0:
        return dict(metas)

    # Shave established months proportionally
    est_total = sum(
        v
        for (c, m), v in metas.items()
        if established_2025_annual.get(c, 0.0) >= 1_000_000
    )
    if est_total <= 0:
        est_total = sum(metas.values()) or 1.0
    shave = min(total_new, est_total * 0.99)
    factor = 1.0 - (shave / est_total)
    out: Dict[Tuple[str, int], float] = {}
    for (c, m), v in metas.items():
        if established_2025_annual.get(c, 0.0) >= 1_000_000:
            out[(c, m)] = v * factor
        else:
            out[(c, m)] = v

    for c, annual in newcomer_annuals.items():
        for m, share in seasonality.items():
            out[(c, m)] = out.get((c, m), 0.0) + annual * share
    return out


def company_seasonality(base_vm: Mapping[Tuple[str, int], float]) -> Dict[int, float]:
    by_m: Dict[int, float] = {m: 0.0 for m in range(1, 13)}
    for (_c, m), s in base_vm.items():
        if 1 <= m <= 12:
            by_m[m] += s
    tot = sum(by_m.values())
    if tot <= 0:
        return {m: 1.0 / 12.0 for m in range(1, 13)}
    return {m: by_m[m] / tot for m in range(1, 13)}


def allocate_lineas(
    vendor_month_metas: Mapping[Tuple[str, int], float],
    line_shares: Mapping[str, Sequence[Tuple[str, str, float]]],
    *,
    target_year: int = 2026,
) -> List[Dict[str, object]]:
    """line_shares[code] = [(linea, grupo, share), ...] shares sum to ~1.

    Returns list of dicts for CSV/DB.
    """
    rows: List[Dict[str, object]] = []
    for (code, month), meta in sorted(vendor_month_metas.items()):
        periodo = year_month_to_periodo(target_year, month)
        shares = list(line_shares.get(code) or line_shares.get("__COMPANY__") or [])
        if not shares:
            shares = [("000", "000", 1.0)]
        # normalize
        ssum = sum(s for _l, _g, s in shares) or 1.0
        allocated = 0.0
        parts = []
        for i, (linea, grupo, share) in enumerate(shares):
            if i == len(shares) - 1:
                val = meta - allocated
            else:
                val = meta * (share / ssum)
                allocated += val
            parts.append((linea, grupo, val))
        for linea, grupo, val in parts:
            if abs(val) < 1e-9:
                continue
            rows.append(
                {
                    "periodo": periodo,
                    "vendedor_codigo": code,
                    "linea": linea,
                    "grupo": grupo,
                    "valor": val,
                }
            )
    return rows


def metas_to_vendor_rows(
    vendor_month_metas: Mapping[Tuple[str, int], float],
    *,
    names: Mapping[str, str],
    target_year: int = 2026,
) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for (code, month), valor in sorted(vendor_month_metas.items()):
        if valor <= 0:
            continue
        rows.append(
            {
                "periodo": year_month_to_periodo(target_year, month),
                "vendedor_codigo": code,
                "vendedor_nombre": names.get(code),
                "valor": valor,
            }
        )
    return rows


def h1_validation(
    vendor_month_metas: Mapping[Tuple[str, int], float],
    h1_actual: Mapping[str, float],
) -> List[Dict[str, object]]:
    """Compare Jan–Jun metas vs H1 actuals per vendor."""
    meta_h1: Dict[str, float] = {}
    for (code, month), val in vendor_month_metas.items():
        if 1 <= month <= 6:
            meta_h1[code] = meta_h1.get(code, 0.0) + val
    codes = sorted(set(meta_h1) | set(h1_actual))
    out = []
    for c in codes:
        m = meta_h1.get(c, 0.0)
        a = h1_actual.get(c, 0.0)
        cumpl = (a / m * 100.0) if m > 0 else None
        out.append(
            {
                "vendedor_codigo": c,
                "meta_h1": m,
                "actual_h1": a,
                "cumplimiento_pct": cumpl,
            }
        )
    return out


@dataclass
class PresupuestoBuildResult:
    active_codes: List[str]
    vendor_month_base_2025: Dict[Tuple[str, int], float]
    vendor_month_metas: Dict[Tuple[str, int], float]
    vendor_rows: List[Dict[str, object]]
    line_rows: List[Dict[str, object]]
    h1_report: List[Dict[str, object]]
    company_base_2025: float
    company_meta_2026: float
    pool_total_2025: float
    seasonality: Dict[int, float]
    names: Dict[str, str] = field(default_factory=dict)


def build_presupuesto_2026(
    *,
    active_raw_codes: Sequence[str],
    sales_rows: Sequence[Tuple[Optional[str], Optional[str], int, int, float]],
    coded_name_sales: Sequence[Tuple[str, str, float]],
    line_shares: Mapping[str, Sequence[Tuple[str, str, float]]],
    h1_2026_by_code: Mapping[str, float],
    primary_names: Mapping[str, str],
    merges: Mapping[str, str] = DEFAULT_CODE_MERGES,
    growth: float = DEFAULT_GROWTH,
    target_year: int = 2026,
    base_year: int = 2025,
) -> PresupuestoBuildResult:
    """End-to-end pure build from pre-fetched aggregates."""
    active = canonical_active_codes(active_raw_codes, merges)
    # Ensure merge targets are active if any source was
    for src, dst in merges.items():
        if src in {normalize_code(c) for c in active_raw_codes}:
            if dst not in active:
                active = sorted(set(active) | {dst})

    name_map = build_name_to_code_map(
        coded_name_sales, allowed_codes=active, merges=merges
    )
    attributed = aggregate_attributed(
        sales_rows,
        name_to_code=name_map,
        active_codes=active,
        merges=merges,
    )
    pool_total = sum(
        s
        for (code, year, _m), s in attributed.items()
        if code == "POOL" and year == base_year
    )
    base_vm = redistribute_pool(attributed, active_codes=active, base_year=base_year)
    seasonality = company_seasonality(base_vm)
    annual_2025 = {c: 0.0 for c in active}
    for (c, _m), s in base_vm.items():
        annual_2025[c] = annual_2025.get(c, 0.0) + s

    metas = draft_metas_from_base(
        base_vm, active_codes=active, target_year=target_year, growth=growth
    )

    # H1 actuals: attribute then spread POOL like 2025 so company total matches reality
    h1_raw: Dict[Tuple[str, int], float] = {}
    for (code, year, month), sales in attributed.items():
        if year == target_year and 1 <= month <= 6:
            h1_raw[(code, month)] = h1_raw.get((code, month), 0.0) + sales
    # Reuse redistribute shape: convert to attributed-like then pool-spread
    h1_attr_tuples = {
        (code, target_year, month): sales for (code, month), sales in h1_raw.items()
    }
    h1_vm = redistribute_pool(
        h1_attr_tuples, active_codes=active, base_year=target_year
    )
    h1_canon: Dict[str, float] = {c: 0.0 for c in active}
    for (c, _m), s in h1_vm.items():
        h1_canon[c] = h1_canon.get(c, 0.0) + s
    for c, s in h1_2026_by_code.items():
        cc = apply_code_merge(normalize_code(c) or "", merges)
        if cc in active and h1_canon.get(cc, 0.0) == 0.0 and float(s) > 0:
            h1_canon[cc] = float(s)

    metas = inject_newcomers(
        metas,
        newcomer_h1=h1_canon,
        active_codes=active,
        company_h1_2025=sum(s for (c, m), s in base_vm.items() if 1 <= m <= 6),
        seasonality=seasonality,
        established_2025_annual=annual_2025,
    )
    # Re-lock company total after newcomer inject
    base_total = sum(base_vm.values())
    target = base_total * (1.0 + growth)
    meta_total = sum(metas.values())
    if meta_total > 0:
        scale = target / meta_total
        metas = {k: v * scale for k, v in metas.items()}

    names: Dict[str, str] = {}
    for c in active:
        if c in OFFICIAL_CODE_NAMES:
            names[c] = OFFICIAL_CODE_NAMES[c]
            continue
        raw = primary_names.get(c) or primary_names.get(apply_code_merge(c, merges))
        names[c] = str(raw) if raw else ""

    vendor_rows = metas_to_vendor_rows(metas, names=names, target_year=target_year)
    line_rows = allocate_lineas(metas, line_shares, target_year=target_year)
    h1_rep = h1_validation(metas, h1_canon)

    return PresupuestoBuildResult(
        active_codes=active,
        vendor_month_base_2025=dict(base_vm),
        vendor_month_metas=dict(metas),
        vendor_rows=vendor_rows,
        line_rows=line_rows,
        h1_report=h1_rep,
        company_base_2025=base_total,
        company_meta_2026=sum(metas.values()),
        pool_total_2025=pool_total,
        seasonality=seasonality,
        names={c: names.get(c) or "" for c in active},
    )
