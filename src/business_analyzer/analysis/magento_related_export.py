"""
Affinity → Magento related / cross-sell export.

Grounds Magento related & cross-sell link recommendations in hybrid product
affinity (co-occurrence first), optionally merging brand-peer candidates from
``brand_link_fill`` so sales co-purchase outranks same-brand name peers.

Merge policy (store convention):
  - related:  fill-empty-only — never wipe existing non-empty related links
  - cross-sell: merge — union existing + new, existing first, then affinity/brand

Magento CSV shapes match depositotrujillo.co brand_link_fill:
  - related:  SKU, Rel_1_SKU … Rel_N_SKU
  - cross-sell: sku, crosssell_skus, upsell_skus  (+ optional .manifest.json)
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set

logger = logging.getLogger(__name__)

# Lower number = higher priority. Brand peers lose to any sales/metadata affinity.
SOURCE_PRIORITY: Dict[str, int] = {
    "co_occurrence": 0,
    "customer_affinity": 1,
    "text_similarity": 2,
    "category_fallback": 3,
    "brand_peer": 4,
    "unknown": 99,
}

# Sources that represent real co-purchase / sales affinity (vs name peers).
AFFINITY_SALES_SOURCES: frozenset = frozenset({"co_occurrence", "customer_affinity"})

RELATED_POLICY = "fill_empty_only"
CROSSSELL_POLICY = "merge"


@dataclass(frozen=True)
class LinkCandidate:
    """One recommended linked SKU for a source product."""

    sku: str
    score: float = 0.0
    source: str = "unknown"
    name: str = ""

    def priority(self) -> int:
        return SOURCE_PRIORITY.get(self.source, SOURCE_PRIORITY["unknown"])


def parse_affinity_csv(
    path: Path,
    *,
    top_n: int = 10,
) -> Dict[str, List[LinkCandidate]]:
    """Parse hybrid affinity output (top_N related products per SKU CSV).

    Expected columns: SKU, Rel_i_SKU, Rel_i_Nombre, Rel_i_Score, Rel_i_Source
    (Nombre/Score/Source optional but preferred).
    """
    path = Path(path)
    result: Dict[str, List[LinkCandidate]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            sku = (row.get("SKU") or row.get("sku") or "").strip()
            if not sku:
                continue
            links: List[LinkCandidate] = []
            for i in range(1, top_n + 1):
                rel = (row.get(f"Rel_{i}_SKU") or "").strip()
                if not rel:
                    continue
                score_raw = row.get(f"Rel_{i}_Score") or "0"
                try:
                    score = float(score_raw) if str(score_raw).strip() else 0.0
                except ValueError:
                    score = 0.0
                source = (row.get(f"Rel_{i}_Source") or "unknown").strip() or "unknown"
                name = (row.get(f"Rel_{i}_Nombre") or "").strip()
                links.append(
                    LinkCandidate(sku=rel, score=score, source=source, name=name)
                )
            if links:
                result[sku] = links
    return result


def parse_brand_related_csv(path: Path, *, limit: int = 10) -> Dict[str, List[str]]:
    """Parse Magento-style related fill CSV: SKU, Rel_1_SKU, …"""
    path = Path(path)
    out: Dict[str, List[str]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            sku = (row.get("SKU") or row.get("sku") or "").strip()
            if not sku:
                continue
            picks: List[str] = []
            for i in range(1, limit + 1):
                rel = (row.get(f"Rel_{i}_SKU") or "").strip()
                if rel:
                    picks.append(rel)
            # Also accept a single related_skus column
            if not picks and row.get("related_skus"):
                picks = [s.strip() for s in row["related_skus"].split(",") if s.strip()]
            if picks:
                out[sku] = picks
    return out


def parse_brand_crosssell_csv(path: Path) -> Dict[str, List[str]]:
    """Parse Magento-style cross-sell batch: sku, crosssell_skus[, upsell_skus]."""
    path = Path(path)
    out: Dict[str, List[str]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            sku = (row.get("sku") or row.get("SKU") or "").strip()
            if not sku:
                continue
            raw = row.get("crosssell_skus") or ""
            picks = [s.strip() for s in raw.split(",") if s.strip()]
            if picks:
                out[sku] = picks
    return out


def brand_peers_to_candidates(
    peers: Mapping[str, Sequence[str]],
    *,
    score: float = 0.1,
) -> Dict[str, List[LinkCandidate]]:
    """Wrap brand-peer SKU lists as LinkCandidate with source=brand_peer."""
    return {
        sku: [
            LinkCandidate(sku=p, score=score, source="brand_peer")
            for p in picks
            if p and p != sku
        ]
        for sku, picks in peers.items()
    }


def _pick_best_candidate(
    existing: Optional[LinkCandidate],
    incoming: LinkCandidate,
) -> LinkCandidate:
    if existing is None:
        return incoming
    if incoming.priority() < existing.priority():
        return incoming
    if incoming.priority() == existing.priority() and incoming.score > existing.score:
        return incoming
    return existing


def merge_link_candidates(
    affinity: Mapping[str, Sequence[LinkCandidate]],
    brand_peers: Optional[Mapping[str, Sequence[LinkCandidate]]] = None,
    *,
    top_n: int = 10,
    min_affinity_score: float = 0.0,
) -> Dict[str, List[LinkCandidate]]:
    """Merge affinity + optional brand peers per source SKU.

    Priority: co_occurrence > customer_affinity > text_similarity >
    category_fallback > brand_peer.

    When co-purchase evidence exists for a pair, brand-name peers for the same
    target SKU are dropped. Empty affinity does not invent links — brand peers
    may still fill if provided.
    """
    brand_peers = brand_peers or {}
    all_skus: Set[str] = set(affinity.keys()) | set(brand_peers.keys())
    merged: Dict[str, List[LinkCandidate]] = {}

    for sku in all_skus:
        best_by_target: Dict[str, LinkCandidate] = {}

        for cand in affinity.get(sku, []):
            if cand.sku == sku:
                continue
            if min_affinity_score > 0 and cand.score < min_affinity_score:
                continue
            best_by_target[cand.sku] = _pick_best_candidate(
                best_by_target.get(cand.sku), cand
            )

        for cand in brand_peers.get(sku, []):
            if cand.sku == sku:
                continue
            # Brand peer never invents when we already have any affinity hit
            # for the same target; _pick_best_candidate handles priority.
            best_by_target[cand.sku] = _pick_best_candidate(
                best_by_target.get(cand.sku), cand
            )

        ranked = sorted(
            best_by_target.values(),
            key=lambda c: (c.priority(), -c.score, c.sku),
        )
        if ranked:
            merged[sku] = ranked[:top_n]

    return merged


def apply_fill_policy(
    candidates: Mapping[str, Sequence[LinkCandidate]],
    existing_links: Mapping[str, Sequence[str]],
    *,
    policy: str,
    limit: int = 10,
) -> Dict[str, List[str]]:
    """Apply Magento fill policy and return SKU → linked SKU strings.

    Policies:
      - fill_empty_only: emit only source SKUs with no existing links
      - merge: union existing (first) + new candidates, dedupe, cap at limit
      - replace: ignore existing (export full candidate list) — rarely used
    """
    if policy not in ("fill_empty_only", "merge", "replace"):
        raise ValueError(f"Unknown policy: {policy!r}")

    out: Dict[str, List[str]] = {}
    # SKUs we care about: candidates + existing when merging
    skus: Set[str] = set(candidates.keys())
    if policy == "merge":
        skus |= set(existing_links.keys())

    for sku in skus:
        existing = [s for s in existing_links.get(sku, []) if s and s != sku]
        cand_skus = [c.sku for c in candidates.get(sku, []) if c.sku != sku]

        if policy == "fill_empty_only":
            if existing:
                continue
            picks = _dedupe_cap(cand_skus, limit)
            if picks:
                out[sku] = picks
        elif policy == "merge":
            picks = _dedupe_cap(list(existing) + cand_skus, limit)
            # Only emit if merge adds something new or we need a full row
            if picks and (not existing or any(s not in existing for s in picks)):
                # Always emit when there is any change vs existing, or full set
                if picks != list(existing)[:limit]:
                    out[sku] = picks
                elif not existing:
                    out[sku] = picks
        else:  # replace
            picks = _dedupe_cap(cand_skus, limit)
            if picks:
                out[sku] = picks

    return out


def _dedupe_cap(items: Sequence[str], limit: int) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for s in items:
        s = (s or "").strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
        if len(out) >= limit:
            break
    return out


def write_related_csv(
    path: Path,
    related_fill: Mapping[str, Sequence[str]],
    *,
    limit: int = 10,
) -> int:
    """Write Magento-style related fill CSV. Returns row count."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = ["SKU"] + [f"Rel_{i}_SKU" for i in range(1, limit + 1)]
    rows_written = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        for sku in sorted(related_fill):
            picks = list(related_fill[sku])[:limit]
            if not picks:
                continue
            writer.writerow([sku] + picks + [""] * (limit - len(picks)))
            rows_written += 1
    return rows_written


def write_crosssell_batch(
    batch_path: Path,
    manifest_path: Optional[Path],
    cross_fill: Mapping[str, Sequence[str]],
    *,
    batch_id: str,
    cross_limit: int = 8,
    note: str = "Affinity-improved cross-sell (merge policy).",
) -> int:
    """Write Magento cross-sell import batch CSV + optional manifest."""
    batch_path = Path(batch_path)
    batch_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for sku in sorted(cross_fill):
        picks = list(cross_fill[sku])[:cross_limit]
        if not picks:
            continue
        rows.append(
            {
                "sku": sku,
                "crosssell_skus": ",".join(picks),
                "upsell_skus": "",
            }
        )
    fieldnames = ["sku", "crosssell_skus", "upsell_skus"]
    with batch_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    if manifest_path is not None:
        manifest_path = Path(manifest_path)
        checksum = hashlib.sha256(batch_path.read_bytes()).hexdigest()
        manifest = {
            "batch_id": batch_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "batch_checksum": checksum,
            "sku_count": len(rows),
            "import_columns": fieldnames,
            "note": note,
            "policy": CROSSSELL_POLICY,
            "source": "hybrid_affinity+brand_peer",
        }
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
    return len(rows)


def write_audit_json(
    path: Path,
    *,
    related: Mapping[str, Sequence[str]],
    cross: Mapping[str, Sequence[str]],
    merged: Mapping[str, Sequence[LinkCandidate]],
    extra: Optional[dict] = None,
) -> None:
    """Write a small audit of sources used in the export."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    source_counts: Dict[str, int] = {}
    co_purchase_skus = 0
    for sku, cands in merged.items():
        has_sales = False
        for c in cands:
            source_counts[c.source] = source_counts.get(c.source, 0) + 1
            if c.source in AFFINITY_SALES_SOURCES:
                has_sales = True
        if has_sales:
            co_purchase_skus += 1
    payload = {
        "related_fill_count": sum(1 for v in related.values() if v),
        "cross_fill_count": sum(1 for v in cross.values() if v),
        "related_avg": (sum(len(v) for v in related.values()) / max(len(related), 1)),
        "cross_avg": (sum(len(v) for v in cross.values()) / max(len(cross), 1)),
        "merged_sku_count": len(merged),
        "skus_with_sales_affinity": co_purchase_skus,
        "source_counts": source_counts,
        "related_policy": RELATED_POLICY,
        "crosssell_policy": CROSSSELL_POLICY,
    }
    if extra:
        payload.update(extra)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def build_magento_export(
    affinity: Mapping[str, Sequence[LinkCandidate]],
    *,
    brand_related_peers: Optional[Mapping[str, Sequence[str]]] = None,
    brand_cross_peers: Optional[Mapping[str, Sequence[str]]] = None,
    existing_related: Optional[Mapping[str, Sequence[str]]] = None,
    existing_cross: Optional[Mapping[str, Sequence[str]]] = None,
    related_limit: int = 10,
    cross_limit: int = 8,
    min_affinity_score: float = 0.0,
) -> tuple[Dict[str, List[str]], Dict[str, List[str]], Dict[str, List[LinkCandidate]],]:
    """Full pure pipeline: merge candidates → apply policies → link maps.

    Returns (related_fill, cross_fill, merged_candidates).
    """
    brand_related_peers = brand_related_peers or {}
    brand_cross_peers = brand_cross_peers or {}
    existing_related = existing_related or {}
    existing_cross = existing_cross or {}

    # Related uses brand related peers; cross uses brand cross peers (may overlap).
    brand_rel_cands = brand_peers_to_candidates(brand_related_peers)
    brand_cross_cands = brand_peers_to_candidates(brand_cross_peers)

    # For related: affinity + brand related peers
    merged_related = merge_link_candidates(
        affinity,
        brand_rel_cands,
        top_n=related_limit,
        min_affinity_score=min_affinity_score,
    )
    # For cross-sell: same affinity, brand cross peers
    merged_cross = merge_link_candidates(
        affinity,
        brand_cross_cands,
        top_n=cross_limit,
        min_affinity_score=min_affinity_score,
    )

    related_fill = apply_fill_policy(
        merged_related,
        existing_related,
        policy=RELATED_POLICY,
        limit=related_limit,
    )
    cross_fill = apply_fill_policy(
        merged_cross,
        existing_cross,
        policy=CROSSSELL_POLICY,
        limit=cross_limit,
    )
    # Prefer related-side merged map for audit (richer top_n)
    return related_fill, cross_fill, merged_related


def export_from_affinity_file(
    affinity_csv: Path,
    output_dir: Path,
    *,
    brand_related_csv: Optional[Path] = None,
    brand_crosssell_csv: Optional[Path] = None,
    existing_related: Optional[Mapping[str, Sequence[str]]] = None,
    existing_cross: Optional[Mapping[str, Sequence[str]]] = None,
    batch_id: str = "affinity-improved-related-crosssell",
    related_limit: int = 10,
    cross_limit: int = 8,
    sku_filter: Optional[Iterable[str]] = None,
) -> dict:
    """Load files, build export, write Magento CSVs under *output_dir*.

    Returns a small stats dict (also written to audit JSON).
    """
    affinity_csv = Path(affinity_csv)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    affinity = parse_affinity_csv(affinity_csv, top_n=related_limit)
    brand_related: Dict[str, List[str]] = {}
    brand_cross: Dict[str, List[str]] = {}
    if brand_related_csv and Path(brand_related_csv).is_file():
        brand_related = parse_brand_related_csv(
            Path(brand_related_csv), limit=related_limit
        )
    if brand_crosssell_csv and Path(brand_crosssell_csv).is_file():
        brand_cross = parse_brand_crosssell_csv(Path(brand_crosssell_csv))

    if sku_filter is not None:
        allow = {s.strip() for s in sku_filter if s and str(s).strip()}
        affinity = {k: v for k, v in affinity.items() if k in allow}
        brand_related = {k: v for k, v in brand_related.items() if k in allow}
        brand_cross = {k: v for k, v in brand_cross.items() if k in allow}

    related_fill, cross_fill, merged = build_magento_export(
        affinity,
        brand_related_peers=brand_related,
        brand_cross_peers=brand_cross,
        existing_related=existing_related,
        existing_cross=existing_cross,
        related_limit=related_limit,
        cross_limit=cross_limit,
    )

    related_path = output_dir / f"{batch_id}-related.csv"
    cross_path = output_dir / f"import-batch-{batch_id}.csv"
    manifest_path = output_dir / f"import-batch-{batch_id}.manifest.json"
    audit_path = output_dir / f"{batch_id}-audit.json"

    n_rel = write_related_csv(related_path, related_fill, limit=related_limit)
    n_cross = write_crosssell_batch(
        cross_path,
        manifest_path,
        cross_fill,
        batch_id=batch_id,
        cross_limit=cross_limit,
        note=(
            "Affinity-improved cross-sell. Merge policy: keep existing links, "
            "append co-occurrence/affinity then brand peers. "
            "Related file uses fill-empty-only."
        ),
    )
    write_audit_json(
        audit_path,
        related=related_fill,
        cross=cross_fill,
        merged=merged,
        extra={
            "affinity_csv": str(affinity_csv),
            "brand_related_csv": str(brand_related_csv) if brand_related_csv else None,
            "brand_crosssell_csv": (
                str(brand_crosssell_csv) if brand_crosssell_csv else None
            ),
            "related_path": str(related_path),
            "cross_path": str(cross_path),
            "related_rows": n_rel,
            "cross_rows": n_cross,
        },
    )

    stats = {
        "related_rows": n_rel,
        "cross_rows": n_cross,
        "merged_skus": len(merged),
        "related_path": str(related_path),
        "cross_path": str(cross_path),
        "audit_path": str(audit_path),
    }
    logger.info(
        "Export done: related=%d cross=%d merged_skus=%d → %s",
        n_rel,
        n_cross,
        len(merged),
        output_dir,
    )
    return stats
