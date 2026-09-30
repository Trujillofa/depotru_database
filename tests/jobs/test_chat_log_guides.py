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


def test_redact_obfuscated_email_after_normalize():
    redacted = clg.redact_pii("SYNTHETIC: juan [at] example.test cuanto demo")
    assert "juan [at] example.test" not in redacted
    assert "juan@example.test" not in redacted
    assert "email" in redacted


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
    assert "tel tel" not in redacted


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
    isolated_settings.delenv("ASSISTANT_CHAT_LOG", raising=False)
    settings = Settings(ASSISTANT_CHAT_LOG=str(tmp_path / "from-settings.jsonl"))
    isolated_settings.setenv("ASSISTANT_CHAT_LOG", str(tmp_path / "from-env.jsonl"))
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


def test_escape_markdown_neutralizes_mentions_and_issue_close():
    text = clg.escape_markdown("ver @usuario y closes #65 <img> | col")
    assert "@usuario" not in text
    assert "#65" not in text
    assert "<img>" not in text
    assert "|" not in text or "\\|" in text


def test_csv_file_uses_utf8_sig(tmp_path: Path):
    log = _write_log(
        tmp_path / "chat_log.jsonl",
        [_line("SYNTHETIC: horario de atencion sede demo")],
    )
    out = tmp_path / "out"
    assert clg.main(["--log-path", str(log), "--output-dir", str(out)]) == 0
    raw = (out / "unmatched_question_clusters.csv").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")


def test_plural_one_grupo(tmp_path: Path, capsys):
    log = _write_log(
        tmp_path / "chat_log.jsonl",
        [_line("SYNTHETIC: horario de atencion sede demo")],
    )
    clg.main(["--log-path", str(log), "--output-dir", str(tmp_path / "out")])
    text = capsys.readouterr().out
    assert "1 grupo " in text
    assert "1 grupos" not in text


def test_stale_drafts_are_removed(tmp_path: Path):
    log = _write_log(
        tmp_path / "chat_log.jsonl",
        [_line("SYNTHETIC: horario de atencion sede demo")],
    )
    out = tmp_path / "out"
    out.mkdir()
    stale = out / "borrador_guia_OLD.md"
    stale.write_text("stale", encoding="utf-8")
    assert clg.main(["--log-path", str(log), "--output-dir", str(out)]) == 0
    assert not stale.exists()
    assert list(out.glob("borrador_*.md")) == []


def test_stale_drafts_are_replaced_on_draft_rerun(tmp_path: Path):
    log = _write_log(
        tmp_path / "chat_log.jsonl",
        [_line("SYNTHETIC: horario de atencion sede demo")],
    )
    out = tmp_path / "out"
    out.mkdir()
    leftover = out / "borrador_guia_cpreviousrun.md"
    leftover.write_text("leftover from previous run", encoding="utf-8")
    leftover_issue = out / "borrador_issue_cpreviousrun.md"
    leftover_issue.write_text("leftover issue", encoding="utf-8")
    assert clg.main(["--log-path", str(log), "--output-dir", str(out), "--draft"]) == 0
    names = {path.name for path in out.glob("borrador_*.md")}
    assert leftover.name not in names
    assert leftover_issue.name not in names
    assert any(name.startswith("borrador_guia_") for name in names)
    assert any(name.startswith("borrador_issue_") for name in names)
    for path in out.glob("borrador_*.md"):
        assert "leftover" not in path.read_text(encoding="utf-8")


def test_output_dir_file_is_spanish_error(tmp_path: Path, capsys):
    log = _write_log(
        tmp_path / "chat_log.jsonl",
        [_line("SYNTHETIC: horario de atencion sede demo")],
    )
    out = tmp_path / "not-a-dir"
    out.write_text("x", encoding="utf-8")
    code = clg.main(["--log-path", str(log), "--output-dir", str(out)])
    assert code == 1
    assert "carpeta" in capsys.readouterr().out.lower()


def test_permission_denied_is_spanish(tmp_path: Path, monkeypatch, capsys):
    log = _write_log(
        tmp_path / "chat_log.jsonl",
        [_line("SYNTHETIC: horario de atencion sede demo")],
    )
    original = Path.read_bytes

    def _blocked(self: Path) -> bytes:
        if self == log:
            raise PermissionError("denied")
        return original(self)

    monkeypatch.setattr(Path, "read_bytes", _blocked)
    code = clg.main(["--log-path", str(log), "--output-dir", str(tmp_path / "out")])
    assert code == 1
    assert "permiso" in capsys.readouterr().out.lower()


def test_binary_log_is_spanish(tmp_path: Path, capsys):
    path = tmp_path / "chat_log.jsonl"
    path.write_bytes(b"\x00\x01\x02binary\x00")
    code = clg.main(["--log-path", str(path), "--output-dir", str(tmp_path / "out")])
    assert code == 1
    assert "binario" in capsys.readouterr().out.lower()


def test_invalid_utf8_lines_are_skipped(tmp_path: Path):
    good = json.dumps(_line("SYNTHETIC: horario de atencion sede demo"))
    path = tmp_path / "chat_log.jsonl"
    path.write_bytes(good.encode("utf-8") + b"\n" + b"\xff\xfe\xfa\n")
    result = clg.mine_chat_log(path)
    assert result.empty is False
    assert result.skipped_lines >= 1


def test_cluster_id_is_hash_of_redacted_text():
    rec = clg.parse_record(_line("SYNTHETIC: cuanto vale el cemento demo xyz"))
    assert rec is not None
    cluster = clg.cluster_unmatched([rec])[0]
    assert cluster.cluster_id == clg.cluster_id_for(cluster.normalized)
    assert cluster.cluster_id.startswith("c")
    assert rec.message not in cluster.cluster_id


def test_cluster_cap_keeps_overflow_as_singletons():
    topics = (
        "alphaaaa",
        "betabbbb",
        "gammagggg",
        "deltadddd",
        "epsiloneee",
        "zetazzzzz",
    )
    rows = [clg.parse_record(_line(f"SYNTHETIC: {topic}")) for topic in topics]
    records = [row for row in rows if row is not None]
    clusters = clg.cluster_unmatched(records, max_groups=2)
    assert len(clusters) == 6


def test_cli_adversarial_synthetic_leaks_on_all_surfaces(tmp_path: Path, capsys):
    """CLI surfaces must not echo adversarial SYNTHETIC identifiers."""
    zwsp = "\u200b"
    endash = "\u2013"
    full_at = "\uff20"
    messages = [
        f"SYNTHETIC: llama al (311) 222 3352 pedido demo {1}",
        "SYNTHETIC: cel 311 222 33 63 horario demo",
        "SYNTHETIC: +57 (311) 222 3362 cemento demo",
        f"SYNTHETIC: tel 311{endash}222{endash}3364 varilla demo",
        f"SYNTHETIC: tel 311{zwsp}222{zwsp}3365 brocas demo",
        "SYNTHETIC: fijo 601 555 1234 domingo demo",
        "SYNTHETIC: fijo 555-1239 mayorista demo",
        "SYNTHETIC: NIT 900 123 458 9 portal demo",
        "SYNTHETIC: CC 1 234 567 899 envio demo",
        "SYNTHETIC: CC 1-234-567-900 material demo",
        "SYNTHETIC: CC. 1 234 567 895 herramienta demo",
        "SYNTHETIC: NIT 1.234.567,901 atencion demo",
        "SYNTHETIC: tarjeta 4111 1111 1111 1111 electronica demo",
        "SYNTHETIC: tarjeta 4111-1111-1111-1112 domicilio demo",
        "SYNTHETIC: FV-12345 cotizacion demo",
        "SYNTHETIC: factura 12347 unica demo",
        "SYNTHETIC: remision 9988 sede demo",
        "SYNTHETIC: pedido 7701 barrio demo",
        "SYNTHETIC: orden 8802 clave demo",
        "SYNTHETIC: juan [at] example.test cuanto demo",
        "SYNTHETIC: ana (at) example.test vale demo",
        f"SYNTHETIC: luis{full_at}example.test precio demo",
        "SYNTHETIC: maria arroba example.test horario demo",
        "SYNTHETIC: pedro [at] example [dot] test cemento demo",
        "SYNTHETIC: https://example.test/x?token=abcSECRET99 varilla demo",
        "SYNTHETIC: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.aaa brocas demo",
        "SYNTHETIC: password=SuperFake99 domingo demo",
        "SYNTHETIC: pwd=FakePwd99 mayorista demo",
        "SYNTHETIC: api_key=FAKEAPIKEY99 portal demo",
        "SYNTHETIC: token=FAKETOKEN99 envio demo",
        "SYNTHETIC: secret=FAKESECRET99 material demo",
        "SYNTHETIC: ghp_FakeGitHubToken1234567890abcd herramienta demo",
        "SYNTHETIC: github_pat_FakePatXXXXXXXXXXXXXXXX atencion demo",
        "SYNTHETIC: AKIAIOSFODNN7EXAMPLE electronica demo",
        "SYNTHETIC: sk-ant-api03-fake-abc_def domicilio demo",
        "SYNTHETIC: sk-proj-fakeProjectKey_123 cotizacion demo",
        "SYNTHETIC: sk-fakeOpenAIKeyXXXXXXXX unica demo",
        "SYNTHETIC: xai-placeholdersecretkey99 sede demo",
        "SYNTHETIC: hex deadbeefdeadbeefdeadbeefdeadbeef barrio demo",
        "SYNTHETIC: b64 VGVzdEJhc2U2NEZha2VUb2tlbkZvclRlc3Rz clave demo",
        "SYNTHETIC: ip 192.0.2.10 cuanto demo",
        "SYNTHETIC: ipv6 2001:db8::1 vale demo",
        "SYNTHETIC: me llamo Juan Demo Perez precio demo",
        "SYNTHETIC: soy Ana Demo horario demo",
        "SYNTHETIC: mi nombre es Luis Demo cemento demo",
        "SYNTHETIC: cliente Carla Demo varilla demo",
        "SYNTHETIC: vivo en calle 12 34 56 brocas demo",
        "SYNTHETIC: carrera 7 n 12 domingo demo",
        "SYNTHETIC: cra 15 20 mayorista demo",
        "SYNTHETIC: cl 45 10 portal demo",
        "SYNTHETIC: kr 9 8 envio demo",
        "SYNTHETIC: avenida 19 100 material demo",
        "SYNTHETIC: diagonal 40 20 herramienta demo",
        "SYNTHETIC: transversal 5 6 atencion demo",
    ]
    leaks = [
        "(311) 222 3352",
        "311 222 33 63",
        "+57 (311) 222 3362",
        "311-222-3364",
        "3112223365",
        "601 555 1234",
        "555-1239",
        "900 123 458 9",
        "1 234 567 899",
        "1-234-567-900",
        "1 234 567 895",
        "1.234.567,901",
        "4111 1111 1111 1111",
        "4111-1111-1111-1112",
        "FV-12345",
        "factura 12347",
        "remision 9988",
        "pedido 7701",
        "orden 8802",
        "juan [at] example.test",
        "juan@example.test",
        "ana (at) example.test",
        "ana@example.test",
        "luis@example.test",
        "maria arroba example.test",
        "maria@example.test",
        "pedro@example.test",
        "abcSECRET99",
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.aaa",
        "SuperFake99",
        "FakePwd99",
        "FAKEAPIKEY99",
        "FAKETOKEN99",
        "FAKESECRET99",
        "ghp_FakeGitHubToken1234567890abcd",
        "github_pat_FakePatXXXXXXXXXXXXXXXX",
        "AKIAIOSFODNN7EXAMPLE",
        "sk-ant-api03-fake-abc_def",
        "sk-proj-fakeProjectKey_123",
        "sk-fakeOpenAIKeyXXXXXXXX",
        "xai-placeholdersecretkey99",
        "deadbeefdeadbeefdeadbeefdeadbeef",
        "VGVzdEJhc2U2NEZha2VUb2tlbkZvclRlc3Rz",
        "192.0.2.10",
        "2001:db8::1",
        "Juan Demo Perez",
        "Ana Demo",
        "Luis Demo",
        "Carla Demo",
        "calle 12 34 56",
        "carrera 7 n 12",
        "cra 15 20",
        "cl 45 10",
        "kr 9 8",
        "avenida 19 100",
        "diagonal 40 20",
        "transversal 5 6",
        "demo.user@example.test",
    ]
    log = _write_log(tmp_path / "chat_log.jsonl", [_line(msg) for msg in messages])
    out = tmp_path / "out"
    code = clg.main(
        ["--log-path", str(log), "--output-dir", str(out), "--draft", "--top", "50"]
    )
    assert code == 0
    stdout = capsys.readouterr().out
    blobs = [stdout]
    for path in out.rglob("*"):
        blobs.append(path.name)
        if path.is_file():
            blobs.append(path.read_text(encoding="utf-8", errors="replace"))
    combined = "\n".join(blobs)
    missing = [token for token in leaks if token in combined]
    assert missing == [], missing
    for path in out.glob("borrador_*.md"):
        assert path.name.startswith("borrador_")
        assert path.name.startswith("borrador_guia_c") or path.name.startswith(
            "borrador_issue_c"
        )
        assert "Juan" not in path.name
        assert "311222" not in path.name
        assert "example.test" not in path.name


@pytest.fixture
def isolated_settings(monkeypatch):
    monkeypatch.delenv("ASSISTANT_CHAT_LOG", raising=False)
    return monkeypatch
