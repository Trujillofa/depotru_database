"""Unit tests for affinity result blending."""

from business_analyzer.analysis.blender import ENGINE_PRIORITY, merge


def _result(sku_a, sku_b, source, score=1.0, name_a=None, name_b=None):
    return {
        "sku_a": sku_a,
        "sku_b": sku_b,
        "name_a": name_a or sku_a,
        "name_b": name_b or sku_b,
        "score": score,
        "source": source,
    }


class TestAffinityBlender:
    def test_co_occurrence_wins_over_text_similarity(self):
        engine_results = {
            "co_occurrence": [_result("A", "B", "co_occurrence", score=0.9)],
            "text_similarity": [_result("A", "B", "text_similarity", score=0.99)],
        }
        blended = merge(engine_results, top_n=5)
        assert blended["A"][0]["sku"] == "B"
        assert blended["A"][0]["source"] == "co_occurrence"

    def test_respects_top_n_per_sku(self):
        engine_results = {
            "co_occurrence": [
                _result("A", "B", "co_occurrence", score=0.9),
                _result("A", "C", "co_occurrence", score=0.8),
                _result("A", "D", "co_occurrence", score=0.7),
            ],
        }
        blended = merge(engine_results, top_n=2)
        assert len(blended["A"]) == 2
        assert blended["A"][0]["sku"] == "B"
        assert blended["A"][1]["sku"] == "C"

    def test_bidirectional_entries(self):
        engine_results = {
            "category_fallback": [_result("X", "Y", "category_fallback", score=0.5)],
        }
        blended = merge(engine_results, top_n=3)
        assert blended["X"][0]["sku"] == "Y"
        assert blended["Y"][0]["sku"] == "X"

    def test_engine_priority_order(self):
        assert ENGINE_PRIORITY["co_occurrence"] < ENGINE_PRIORITY["text_similarity"]
