"""catalog.term_suggest: the catalogue's own words, to forgive typos."""

from __future__ import annotations

import pytest

from depotru_integrations.j3 import terms
from depotru_tools.builtins import _tool_term_suggest

NAMES = [
    "CEMENTO GRIS USO GENERAL CEMEX 50KG",
    "CEMENTO BLANCO CEMEX 25KG",
    "SIKAFLEX 1A PLUS BLANCO 300 ML",
    "SIKAFLEX 1A PLUS GRIS 300 ML",
    "VINILO TIPO 1 BLANCO GALON",
    "VARILLA CORRUGADA 3/8",
]


@pytest.fixture(autouse=True)
def _vocabulary(monkeypatch):
    terms.reset_cache()
    monkeypatch.setattr(terms, "_read_names", lambda: list(NAMES))
    yield
    terms.reset_cache()


def test_suggests_the_catalogue_word_for_a_typo():
    result = terms.suggest_terms("semento")
    assert result["status"] == "ok"
    assert result["suggestions"][0]["term"] == "cemento"


def test_suggests_a_colour_typo():
    result = terms.suggest_terms("blnaco")
    assert result["status"] == "ok"
    assert result["suggestions"][0]["term"] == "blanco"


def test_an_exact_word_is_reported_as_such():
    result = terms.suggest_terms("sikaflex")
    assert result["exact"] is True
    assert result["suggestions"][0]["score"] == 1.0


def test_nothing_close_means_no_suggestion():
    result = terms.suggest_terms("zzzzqqq")
    assert result["status"] == "empty"
    assert result["suggestions"] == []


def test_short_words_are_not_guessed():
    assert terms.suggest_terms("ab")["status"] == "empty"


def test_a_broken_catalogue_never_raises(monkeypatch):
    def boom():
        raise RuntimeError("J3 caído")

    monkeypatch.setattr(terms, "_read_names", boom)
    out = _tool_term_suggest(None, {"query": "semento"})  # type: ignore[arg-type]
    assert out["status"] == "error"
    assert out["suggestions"] == []
