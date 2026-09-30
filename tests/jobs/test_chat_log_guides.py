"""Chat-log guide mining. SYNTHETIC fixtures only — no real user questions."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

from business_analyzer.core.config import Settings
from business_analyzer.jobs import chat_log_guides as clg
from modules.assistant.problem_guides import match_guide


def _line(
    message: str,
    *,
    guide_id: str | None = None,
    session_id: str = "SYNTHETIC-SESS-1",
    extra: dict | None = None,
) -> dict:
    rec = {
        "ts": "2026-09-30T12:00:00+00:00",
        "session_id": session_id,
        "audience": "public",
        "locale": "es_CO",
        "message": message,
        "reply_preview": "SYNTHETIC reply preview",
        "tools_used": [],
        "mode": "stub_tools",
        "guide_id": guide_id,
        "product_query": None,
        "grounded": True,
    }
    if extra:
        rec.update(extra)
    return rec


def _write_log(path: Path, rows: list[dict], extra_text: str = "") -> Path:
    chunks = [json.dumps(row, ensure_ascii=False) for row in rows]
    text = "\n".join(chunks)
    if extra_text:
        text = text + extra_text
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")
    return path


def test_redact_email_phone_digits_and_document_numbers():
    raw = (
        "SYNTHETIC: enviar a demo.user@example.test tel +57 300 123 4567 "
        "CC 1234567890 NIT 800.123.456-1 cuenta 987654321012"
    )
    redacted = clg.redact_pii(raw)
    assert "demo.user@example.test" not in redacted
    assert "300 123 4567" not in redacted
    assert "1234567890" not in redacted
    assert "800.123.456-1" not in redacted
    assert "987654321012" not in redacted
    assert "email" in redacted
    assert "tel" in redacted
    assert "documento" in redacted
    assert "numero" in redacted


def test_redact_secrets_like_api_keys():
    raw = "SYNTHETIC clave xai-placeholdersecretkey y sk-ant-placeholdersecret"
    redacted = clg.redact_pii(raw)
    assert "xai-placeholdersecretkey" not in redacted
    assert "sk-ant-placeholdersecret" not in redacted
    assert "secreto" in redacted


def test_normalize_lowercases_strips_accents_and_punctuation():
    assert (
        clg.normalize_question("¿Cuánto vale el Cemento?") == "cuanto vale el cemento"
    )
    assert clg.normalize_question("  HOLA, DEMO!  ") == "hola demo"


def test_known_storefront_job_still_matches_existing_guide():
    """Mining must reuse match_guide; it must not change assistant routing."""
    assert match_guide("tengo una gotera en el techo") is not None
    rec = clg.parse_record(_line("tengo una gotera en el techo", guide_id=None))
    assert rec is not None
    assert rec.matched is True


def test_logged_guide_id_counts_as_matched():
    rec = clg.parse_record(
        _line("SYNTHETIC: frase inventada sin patron", guide_id="gotera")
    )
    assert rec is not None
    assert rec.matched is True


def test_unmatched_synthetic_question_is_flagged():
    rec = clg.parse_record(
        _line("SYNTHETIC: cuanto vale el cemento demo xyz", guide_id=None)
    )
    assert rec is not None
    assert rec.matched is False
    assert match_guide(rec.message) is None


def test_clusters_similar_normalized_and_overlapping_questions():
    rows = [
        _line("SYNTHETIC: ¿Cuánto vale el cemento demo xyz?"),
        _line("SYNTHETIC: cuanto vale el cemento demo xyz"),
        _line("SYNTHETIC: precio del cemento demo xyz"),
        _line("SYNTHETIC: horario de atencion sede demo"),
        _line("tengo una gotera"),
    ]
    records = [clg.parse_record(r) for r in rows]
    records = [r for r in records if r is not None]
    clusters = clg.cluster_unmatched(records)
    ids_by_count = sorted(clusters, key=lambda c: (-c.count, c.normalized))
    assert ids_by_count[0].count == 3
    assert "cemento" in ids_by_count[0].representative
    assert all("gotera" not in c.representative for c in clusters)
    assert any("horario" in c.representative for c in clusters)


def test_top_clusters_are_limited_and_sorted_by_count():
    topics = (
        "cuanto vale el cemento demo xyz",
        "horario de atencion sede demo",
        "factura electronica pedido demo",
        "tienen domicilio a barrio demo",
        "necesito cotizacion de varilla demo",
        "catalogo de brocas demo xyz",
        "abren el domingo sede demo",
        "pedido mayorista ferreteria demo",
        "cambiar clave portal demo",
        "estado de envio pedido demo",
        "devolucion de material demo xyz",
        "garantia de herramienta demo",
    )
    rows = []
    for i, topic in enumerate(topics):
        rows.extend(_line(f"SYNTHETIC: {topic}") for _ in range(12 - i))
    records = [clg.parse_record(r) for r in rows]
    records = [r for r in records if r is not None]
    top = clg.top_unmatched_clusters(clg.cluster_unmatched(records), n=10)
    assert len(top) == 10
    counts = [c.count for c in top]
    assert counts == sorted(counts, reverse=True)
    assert top[0].count == 12
    assert top[-1].count == 3


def test_outputs_never_include_pii_session_or_secrets(tmp_path: Path):
    secret_phone = "3001234567"
    rows = [
        _line(
            f"SYNTHETIC: cotizar a demo.user@example.test tel {secret_phone}",
            session_id="sess-should-never-leak",
        ),
        _line("SYNTHETIC: cotizar a otro.user@example.test tel 3109876543"),
    ]
    path = _write_log(tmp_path / "chat_log.jsonl", rows)
    result = clg.mine_chat_log(path)
    assert result.empty is False
    blob = (
        clg.render_markdown(result.clusters)
        + clg.render_csv(result.clusters)
        + clg.render_draft_guide(result.clusters[0])
        + clg.render_draft_issue_body(result.clusters[0])
    )
    assert "demo.user@example.test" not in blob
    assert "otro.user@example.test" not in blob
    assert secret_phone not in blob
    assert "3109876543" not in blob
    assert "sess-should-never-leak" not in blob
    assert "SYNTHETIC reply preview" not in blob


def test_csv_guards_formula_injection():
    cluster = clg.QuestionCluster(
        cluster_id="demo_1",
        count=1,
        representative="=cmd",
        examples=("+payload",),
        normalized="cmd",
    )
    text = clg.render_csv((cluster,))
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    assert rows[1][3].startswith("'")
    assert rows[1][4].startswith("'")


def test_missing_log_is_spanish_and_graceful():
    result = clg.mine_chat_log(Path("/tmp/does-not-exist-chat-log-depotru.jsonl"))
    assert result.empty is True
    assert result.clusters == ()
    assert "no se encontró" in result.message.lower()
    assert "chat" in result.message.lower()


def test_empty_log_is_spanish_and_graceful(tmp_path: Path):
    path = tmp_path / "chat_log.jsonl"
    path.write_text("", encoding="utf-8")
    result = clg.mine_chat_log(path)
    assert result.empty is True
    assert "vacío" in result.message.lower() or "vacio" in result.message.lower()


def test_malformed_and_blank_lines_are_skipped(tmp_path: Path):
    path = tmp_path / "chat_log.jsonl"
    path.write_text(
        "\n".join(
            [
                "{not json",
                "",
                json.dumps(_line("")),
                json.dumps(_line("SYNTHETIC: unica pregunta demo xyz")),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    result = clg.mine_chat_log(path)
    assert result.skipped_lines >= 2
    assert result.empty is False
    assert result.clusters[0].count == 1


def test_all_matched_questions_have_spanish_message(tmp_path: Path):
    path = _write_log(tmp_path / "chat_log.jsonl", [_line("tengo una gotera")])
    result = clg.mine_chat_log(path)
    assert result.empty is True
    assert "guía" in result.message.lower() or "guia" in result.message.lower()


def test_draft_guide_is_spanish_template_and_not_published():
    cluster = clg.QuestionCluster(
        cluster_id="cemento_demo",
        count=4,
        representative="SYNTHETIC: cuanto vale el cemento demo xyz",
        examples=("SYNTHETIC: precio del cemento demo xyz",),
        normalized="synthetic cuanto vale el cemento demo xyz",
    )
    draft = clg.render_draft_guide(cluster)
    issue = clg.render_draft_issue_body(cluster)
    for text in (draft, issue):
        assert "BORRADOR" in text
        assert "no publicar" in text.lower() or "no se publica" in text.lower()
        assert "no crear" in text.lower()
        assert "SYNTHETIC" in text
        assert "necesito" in text.lower() or "lista" in text.lower()


def test_resolve_log_path_uses_settings_not_raw_getenv(isolated_settings, tmp_path):
    isolated_settings.setenv(
        "ASSISTANT_CHAT_LOG", str(tmp_path / "from-settings.jsonl")
    )
    settings = Settings()
    resolved = clg.resolve_log_path(explicit=None, settings=settings)
    assert resolved == tmp_path / "from-settings.jsonl"


def test_resolve_log_path_explicit_wins(isolated_settings, tmp_path):
    isolated_settings.setenv("ASSISTANT_CHAT_LOG", str(tmp_path / "ignored.jsonl"))
    explicit = tmp_path / "explicit.jsonl"
    resolved = clg.resolve_log_path(explicit=explicit, settings=Settings())
    assert resolved == explicit


def test_main_writes_markdown_csv_and_optional_drafts(tmp_path: Path):
    log = _write_log(
        tmp_path / "chat_log.jsonl",
        [
            _line("SYNTHETIC: cuanto vale el cemento demo xyz"),
            _line("SYNTHETIC: ¿Cuánto vale el cemento demo xyz?"),
            _line("SYNTHETIC: horario de atencion sede demo"),
        ],
    )
    out = tmp_path / "out"
    code = clg.main(
        [
            "--log-path",
            str(log),
            "--output-dir",
            str(out),
            "--draft",
        ]
    )
    assert code == 0
    md = (out / "unmatched_question_clusters.md").read_text(encoding="utf-8")
    csv_text = (out / "unmatched_question_clusters.csv").read_text(encoding="utf-8")
    assert "cemento" in md.lower()
    assert "count" in csv_text or "conteo" in csv_text.lower()
    drafts = list(out.glob("borrador_*.md"))
    assert drafts
    assert all("BORRADOR" in p.read_text(encoding="utf-8") for p in drafts)


def test_main_missing_log_prints_spanish_and_exits_zero(tmp_path: Path, capsys):
    code = clg.main(
        [
            "--log-path",
            str(tmp_path / "missing.jsonl"),
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )
    assert code == 0
    captured = capsys.readouterr()
    text = captured.out + captured.err
    assert "no se encontró" in text.lower()
    assert not (tmp_path / "out" / "unmatched_question_clusters.md").exists()


def test_main_synthetic_uses_labelled_fixture_only(tmp_path: Path):
    code = clg.main(["--synthetic", "--output-dir", str(tmp_path / "out")])
    assert code == 0
    md = (tmp_path / "out" / "unmatched_question_clusters.md").read_text(
        encoding="utf-8"
    )
    assert "SYNTHETIC" in md
    assert "gotera" not in md.lower() or "SYNTHETIC" in md


def test_argparse_help_is_spanish(capsys):
    with pytest.raises(SystemExit):
        clg.parse_args(["--help"])
    help_text = capsys.readouterr().out.lower()
    assert "registro" in help_text or "preguntas" in help_text
    assert "borrador" in help_text


def test_synthetic_fixture_is_labelled_and_has_no_real_looking_pii():
    for line in clg.SYNTHETIC_CHAT_LOG_JSONL.splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        assert "SYNTHETIC" in rec["message"] or rec.get("guide_id") == "gotera"
        assert "@" not in rec["message"] or "example.test" in rec["message"]


def test_jaccard_empty_token_sets():
    assert clg.jaccard(frozenset(), frozenset()) == 1.0
    assert clg.jaccard(frozenset({"a"}), frozenset()) == 0.0


def test_parse_record_rejects_non_dict_and_blank_guide():
    assert clg.parse_record(["no-dict"]) is None
    rec = clg.parse_record(_line("SYNTHETIC: unica pregunta demo xyz", guide_id="   "))
    assert rec is not None
    assert rec.guide_id is None
    assert rec.matched is False
    assert clg.parse_record(_line("...")) is None


def test_mine_chat_log_text_blank_is_empty():
    result = clg.mine_chat_log_text("  \n\t")
    assert result.empty is True
    assert "vacío" in result.message.lower() or "vacio" in result.message.lower()


def test_resolve_log_path_reads_settings_snapshot(isolated_settings):
    resolved = clg.resolve_log_path(explicit=None, settings=None)
    assert resolved == clg.DEFAULT_LOG_RELATIVE


def test_draft_title_fallback_and_safe_filename():
    cluster = clg.QuestionCluster(
        cluster_id="***",
        count=1,
        representative="SYNTHETIC:",
        examples=(),
        normalized="synthetic",
    )
    draft = clg.render_draft_guide(cluster)
    assert "Sin título" in draft or "Guía" in draft
    assert clg._safe_filename("***") == "cluster"


def test_mine_log_directory_is_spanish(tmp_path: Path):
    folder = tmp_path / "not-a-file"
    folder.mkdir()
    result = clg.mine_chat_log(folder)
    assert result.empty is True
    assert "archivo" in result.message.lower()


def test_resolve_log_path_default_relative(isolated_settings):
    isolated_settings.delenv("ASSISTANT_CHAT_LOG", raising=False)
    assert clg.resolve_log_path(settings=Settings()) == clg.DEFAULT_LOG_RELATIVE


def test_render_markdown_empty_clusters():
    text = clg.render_markdown(())
    assert "0" in text


def test_main_without_draft_skips_borrador_files(tmp_path: Path):
    log = _write_log(
        tmp_path / "chat_log.jsonl",
        [_line("SYNTHETIC: cuanto vale el cemento demo xyz")],
    )
    out = tmp_path / "out"
    assert clg.main(["--log-path", str(log), "--output-dir", str(out)]) == 0
    assert (out / "unmatched_question_clusters.md").is_file()
    assert list(out.glob("borrador_*.md")) == []


def test_cluster_unmatched_ignores_already_matched():
    rows = [
        clg.parse_record(_line("tengo una gotera")),
        clg.parse_record(_line("SYNTHETIC: horario de atencion sede demo")),
    ]
    clusters = clg.cluster_unmatched([row for row in rows if row is not None])
    assert len(clusters) == 1
    assert "horario" in clusters[0].representative


def test_script_wrapper_exists():
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts" / "analysis" / "mine_chat_log_guides.py"
    assert script.is_file()
    assert "chat_log_guides" in script.read_text(encoding="utf-8")


@pytest.fixture
def isolated_settings(monkeypatch):
    monkeypatch.delenv("ASSISTANT_CHAT_LOG", raising=False)
    return monkeypatch
