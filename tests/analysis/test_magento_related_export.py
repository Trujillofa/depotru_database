"""Unit tests for Magento related/cross-sell affinity export (shipped path)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from business_analyzer.analysis.magento_related_export import (
    AFFINITY_SALES_SOURCES,
    CROSSSELL_POLICY,
    RELATED_POLICY,
    SOURCE_PRIORITY,
    LinkCandidate,
    apply_fill_policy,
    brand_peers_to_candidates,
    build_magento_export,
    export_from_affinity_file,
    merge_link_candidates,
    parse_affinity_csv,
    write_crosssell_batch,
    write_related_csv,
)


def _cand(sku: str, score: float, source: str, name: str = "") -> LinkCandidate:
    return LinkCandidate(sku=sku, score=score, source=source, name=name or sku)


class TestSourcePriority:
    def test_co_occurrence_beats_brand_peer(self):
        assert SOURCE_PRIORITY["co_occurrence"] < SOURCE_PRIORITY["brand_peer"]

    def test_sales_sources_defined(self):
        assert "co_occurrence" in AFFINITY_SALES_SOURCES
        assert "brand_peer" not in AFFINITY_SALES_SOURCES


class TestParseCoincidenciasCsv:
    def test_coincidencias_maps_to_co_occurrence_score(self, tmp_path: Path):
        path = tmp_path / "aff.csv"
        path.write_text(
            "SKU,Rel_1_SKU,Rel_1_Nombre,Rel_1_Coincidencias,"
            "Rel_2_SKU,Rel_2_Nombre,Rel_2_Coincidencias\n"
            "A,B,Prod B,42,C,Prod C,7\n",
            encoding="utf-8",
        )
        parsed = parse_affinity_csv(path, top_n=10)
        assert "A" in parsed
        assert parsed["A"][0].sku == "B"
        assert parsed["A"][0].score == 42.0
        assert parsed["A"][0].source == "co_occurrence"
        assert parsed["A"][1].sku == "C"
        assert parsed["A"][1].score == 7.0


class TestMergeLinkCandidates:
    def test_affinity_wins_over_brand_peer_same_target(self):
        """Co-purchase for A→B outranks brand-peer A→B."""
        affinity = {
            "A": [_cand("B", 0.4, "co_occurrence", "Bought together")],
        }
        brand = brand_peers_to_candidates({"A": ["B", "C"]}, score=0.9)
        merged = merge_link_candidates(affinity, brand, top_n=5)

        by_target = {c.sku: c for c in merged["A"]}
        assert by_target["B"].source == "co_occurrence"
        # Brand peer C still present as fallback for other targets
        assert by_target["C"].source == "brand_peer"
        # Order: co_occurrence first
        assert merged["A"][0].sku == "B"
        assert merged["A"][0].source == "co_occurrence"

    def test_empty_affinity_falls_back_to_brand_without_inventing(self):
        """No affinity pairs → brand peers only; no phantom SKUs."""
        affinity: dict = {}
        brand = brand_peers_to_candidates({"X": ["Y", "Z"]})
        merged = merge_link_candidates(affinity, brand, top_n=5)
        assert set(c.sku for c in merged["X"]) == {"Y", "Z"}
        assert all(c.source == "brand_peer" for c in merged["X"])
        # No invented SKUs
        assert "X" not in {c.sku for c in merged["X"]}

    def test_empty_both_yields_no_links(self):
        merged = merge_link_candidates({}, {}, top_n=5)
        assert merged == {}

    def test_co_occurrence_outranks_text_similarity(self):
        affinity = {
            "A": [
                _cand("B", 0.2, "co_occurrence"),
                _cand("C", 0.99, "text_similarity"),
            ]
        }
        merged = merge_link_candidates(affinity, top_n=5)
        assert merged["A"][0].sku == "B"
        assert merged["A"][0].source == "co_occurrence"
        assert merged["A"][1].sku == "C"

    def test_top_n_cap(self):
        affinity = {
            "A": [_cand(f"S{i}", 1.0 - i * 0.01, "co_occurrence") for i in range(20)]
        }
        merged = merge_link_candidates(affinity, top_n=3)
        assert len(merged["A"]) == 3

    def test_self_links_dropped(self):
        affinity = {
            "A": [_cand("A", 1.0, "co_occurrence"), _cand("B", 0.5, "co_occurrence")]
        }
        merged = merge_link_candidates(affinity, top_n=5)
        assert [c.sku for c in merged["A"]] == ["B"]


class TestFillPolicy:
    def test_related_fill_empty_only_skips_nonempty(self):
        cands = {
            "EMPTY": [_cand("R1", 0.5, "co_occurrence")],
            "FULL": [_cand("R9", 0.9, "co_occurrence")],
        }
        existing = {"FULL": ["ALREADY"], "EMPTY": []}
        out = apply_fill_policy(cands, existing, policy=RELATED_POLICY, limit=10)
        assert "EMPTY" in out
        assert out["EMPTY"] == ["R1"]
        assert "FULL" not in out  # never wipe non-empty related

    def test_crosssell_merge_keeps_existing_first(self):
        cands = {
            "S": [
                _cand("NEW1", 0.8, "co_occurrence"),
                _cand("NEW2", 0.7, "co_occurrence"),
            ]
        }
        existing = {"S": ["OLD1", "OLD2"]}
        out = apply_fill_policy(cands, existing, policy=CROSSSELL_POLICY, limit=8)
        assert out["S"][0] == "OLD1"
        assert out["S"][1] == "OLD2"
        assert "NEW1" in out["S"]
        assert "NEW2" in out["S"]

    def test_crosssell_merge_dedupes_existing_overlap(self):
        cands = {
            "S": [_cand("OLD1", 0.9, "co_occurrence"), _cand("NEW", 0.5, "brand_peer")]
        }
        existing = {"S": ["OLD1"]}
        out = apply_fill_policy(cands, existing, policy="merge", limit=8)
        assert out["S"].count("OLD1") == 1
        assert out["S"] == ["OLD1", "NEW"]

    def test_fill_empty_with_no_candidates_emits_nothing(self):
        out = apply_fill_policy({}, {"A": []}, policy="fill_empty_only", limit=5)
        assert out == {}

    def test_unknown_policy_raises(self):
        with pytest.raises(ValueError, match="Unknown policy"):
            apply_fill_policy({}, {}, policy="wipe_all", limit=5)


class TestBuildMagentoExport:
    def test_end_to_end_affinity_over_brand(self):
        affinity = {
            "SKU1": [
                _cand("COBUY", 0.55, "co_occurrence"),
                _cand("PEER", 0.2, "text_similarity"),
            ],
            "SKU2": [],  # no affinity — should not invent
        }
        brand_related = {"SKU1": ["PEER", "BRAND_ONLY"], "SKU2": ["FALLBACK"]}
        brand_cross = {"SKU1": ["PEER"], "SKU3": ["CX"]}
        # SKU1 related already filled → related fill skips it
        existing_related = {"SKU1": ["MANUAL"], "SKU2": []}
        existing_cross = {"SKU1": ["OLD_CS"]}

        related, cross, merged = build_magento_export(
            affinity,
            brand_related_peers=brand_related,
            brand_cross_peers=brand_cross,
            existing_related=existing_related,
            existing_cross=existing_cross,
            related_limit=10,
            cross_limit=8,
        )

        # Related: fill-empty only → SKU1 skipped, SKU2 gets brand fallback
        assert "SKU1" not in related
        assert related["SKU2"][0] == "FALLBACK"

        # Cross-sell merge: existing first, then affinity co-buy before brand
        assert cross["SKU1"][0] == "OLD_CS"
        assert "COBUY" in cross["SKU1"]
        # Affinity for COBUY preferred over pure brand for PEER ranking inside merge list
        assert merged["SKU1"][0].sku == "COBUY"
        assert merged["SKU1"][0].source == "co_occurrence"


class TestParseAndWrite:
    def test_parse_affinity_csv_roundtrip_sources(self, tmp_path: Path):
        csv_path = tmp_path / "affinity.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "SKU",
                    "Nombre_Producto",
                    "Ventas_Totales",
                    "Rel_1_SKU",
                    "Rel_1_Nombre",
                    "Rel_1_Score",
                    "Rel_1_Source",
                    "Rel_2_SKU",
                    "Rel_2_Nombre",
                    "Rel_2_Score",
                    "Rel_2_Source",
                ]
            )
            w.writerow(
                [
                    "0020090002",
                    "CEMENTO",
                    "100",
                    "0020190001",
                    "BARRA",
                    "0.5289",
                    "co_occurrence",
                    "0010150032",
                    "PUNTILLA",
                    "0.3",
                    "customer_affinity",
                ]
            )
        parsed = parse_affinity_csv(csv_path)
        assert "0020090002" in parsed
        assert parsed["0020090002"][0].sku == "0020190001"
        assert parsed["0020090002"][0].source == "co_occurrence"
        assert parsed["0020090002"][0].score == pytest.approx(0.5289)

    def test_write_related_and_crosssell_shapes(self, tmp_path: Path):
        related_path = tmp_path / "related.csv"
        cross_path = tmp_path / "cross.csv"
        man_path = tmp_path / "cross.manifest.json"
        n = write_related_csv(related_path, {"A": ["B", "C"]}, limit=10)
        assert n == 1
        with related_path.open() as f:
            rows = list(csv.reader(f))
        assert rows[0][0] == "SKU"
        assert rows[0][1] == "Rel_1_SKU"
        assert rows[1][0] == "A"
        assert rows[1][1] == "B"

        n2 = write_crosssell_batch(
            cross_path, man_path, {"A": ["B", "C"]}, batch_id="test-batch"
        )
        assert n2 == 1
        with cross_path.open() as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["sku"] == "A"
        assert rows[0]["crosssell_skus"] == "B,C"
        man = json.loads(man_path.read_text())
        assert man["batch_id"] == "test-batch"
        assert man["sku_count"] == 1


class TestExportFromAffinityFile:
    def test_cli_entry_writes_artifacts(self, tmp_path: Path):
        affinity = tmp_path / "aff.csv"
        with affinity.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "SKU",
                    "Nombre_Producto",
                    "Ventas_Totales",
                    "Rel_1_SKU",
                    "Rel_1_Nombre",
                    "Rel_1_Score",
                    "Rel_1_Source",
                ]
            )
            w.writerow(
                [
                    "SKU_A",
                    "Product A",
                    "50",
                    "SKU_B",
                    "Product B",
                    "0.6",
                    "co_occurrence",
                ]
            )
        brand_rel = tmp_path / "brand_rel.csv"
        with brand_rel.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["SKU", "Rel_1_SKU", "Rel_2_SKU"])
            w.writerow(["SKU_A", "SKU_BRAND", "SKU_B"])

        out = tmp_path / "export"
        stats = export_from_affinity_file(
            affinity,
            out,
            brand_related_csv=brand_rel,
            batch_id="unit-test-batch",
            # empty existing → related fill-empty emits SKU_A
            existing_related={},
            existing_cross={},
        )
        assert stats["related_rows"] >= 1
        related_file = Path(stats["related_path"])
        assert related_file.is_file()
        with related_file.open() as f:
            body = f.read()
        # Affinity co-occurrence target should appear (not brand-only first)
        assert "SKU_A" in body
        assert "SKU_B" in body
        # Audit cites sales source
        audit = json.loads(Path(stats["audit_path"]).read_text())
        assert audit["source_counts"].get("co_occurrence", 0) >= 1
        assert audit["related_policy"] == "fill_empty_only"
        assert audit["crosssell_policy"] == "merge"
