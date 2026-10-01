"""Chat-log guide mining. SYNTHETIC fixtures only — no real user questions."""

from __future__ import annotations

import csv
import io
import json
import logging
import random
import re
import time
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


def _stripe_secret(kind: str, env: str, body: str) -> str:
    """Assemble a Stripe-like key at runtime so the source has no full token."""
    return f"{kind}_{env}_{body}"


def _jwt_token(*parts: str) -> str:
    """Assemble a JWT-shaped string at runtime so the source has no full token."""
    return ".".join(parts)


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


def test_redact_email_split_by_newline_around_dot():
    """A newline around the domain dot must still redact as email."""
    gmail = clg.redact_pii("SYNTHETIC: juan@gmail.\ncom cuanto demo")
    assert "juan@gmail" not in gmail.lower()
    assert "gmail." not in gmail.lower()
    assert "email" in gmail
    gmail_display = clg.project_for_display(gmail)
    assert "juan" not in gmail_display
    assert "gmail" not in gmail_display

    prepared = clg.prepare_for_redaction("juan@gmail.\ncom", keep_newlines=True)
    assert "juan@gmail.com" in prepared

    hardware = clg.redact_pii("SYNTHETIC: material@cemento.\ndemo cuanto")
    assert "material@cemento" not in hardware.lower()
    assert "email" in hardware
    hardware_display = clg.project_for_display(hardware)
    assert "material" not in hardware_display.split()
    assert "cemento" not in hardware_display.split()
    assert "demo" not in hardware_display.split()


def test_email_join_does_not_eat_name_triggers_or_cuanto():
    """A complete address plus prose must not steal the next word as TLD."""
    name_cases = (
        "SYNTHETIC: juan@gmail.com, soy Ana Demo cuanto",
        "SYNTHETIC: juan@gmail.com, me llamo Ana Demo cuanto",
        "SYNTHETIC: juan@gmail.com, mi nombre es Ana Demo cuanto",
        "SYNTHETIC: juan@gmail.com, cliente Ana Demo cuanto",
        "SYNTHETIC: juan@gmail.com, nombre: Ana Demo cuanto",
        "SYNTHETIC: juan@gmail.com,\nsoy Ana Demo cuanto",
    )
    for raw in name_cases:
        redacted = clg.redact_pii(raw)
        displayed = clg.project_for_display(redacted)
        assert "email" in redacted.lower(), raw
        assert "nombre" in redacted.lower(), raw
        assert "juan@gmail" not in redacted.lower(), raw
        tokens = displayed.split()
        assert "ana" not in tokens, (raw, displayed)
        assert "demo" not in tokens, (raw, displayed)
        assert "juan" not in tokens, (raw, displayed)
        assert "gmail" not in tokens, (raw, displayed)

    cement = clg.redact_pii("SYNTHETIC: correo juan@gmail.com, cuanto vale el cemento")
    cement_display = clg.project_for_display(cement)
    assert "email" in cement.lower()
    assert "cuanto" in cement.lower()
    assert "cuanto" in cement_display.split()
    assert "cemento" in cement_display.split()
    assert "juan@gmail.com.cuanto" not in clg.prepare_for_redaction(
        "correo juan@gmail.com, cuanto vale el cemento", keep_newlines=True
    )


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
    assert "synthetic" in md.lower()
    assert "gotera" not in md.lower() or "synthetic" in md.lower()


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


def test_unrelated_user_files_survive_without_draft(tmp_path: Path):
    log = _write_log(
        tmp_path / "chat_log.jsonl",
        [_line("SYNTHETIC: horario de atencion sede demo")],
    )
    out = tmp_path / "out"
    out.mkdir()
    notes = out / "borrador_mis_notas.md"
    notes.write_text("notas del usuario", encoding="utf-8")
    letter = out / "borrador_carta_abuela.md"
    letter.write_text("carta", encoding="utf-8")
    contract = out / "borrador_contrato.md"
    contract.write_text("contrato", encoding="utf-8")
    generated = out / "borrador_guia_c0123456789ab.md"
    generated.write_text("old generated", encoding="utf-8")
    assert clg.main(["--log-path", str(log), "--output-dir", str(out)]) == 0
    assert notes.read_text(encoding="utf-8") == "notas del usuario"
    assert letter.read_text(encoding="utf-8") == "carta"
    assert contract.read_text(encoding="utf-8") == "contrato"
    assert generated.read_text(encoding="utf-8") == "old generated"


def test_unrelated_user_files_survive_with_draft(tmp_path: Path):
    log = _write_log(
        tmp_path / "chat_log.jsonl",
        [_line("SYNTHETIC: horario de atencion sede demo")],
    )
    out = tmp_path / "out"
    out.mkdir()
    notes = out / "borrador_mis_notas.md"
    notes.write_text("notas del usuario", encoding="utf-8")
    leftover = out / "borrador_guia_cabcdefghijkl.md"
    leftover.write_text("old generated", encoding="utf-8")
    leftover_issue = out / "borrador_issue_cabcdefghijkl.md"
    leftover_issue.write_text("old issue", encoding="utf-8")
    not_hex = out / "borrador_guia_cpreviousrun.md"
    not_hex.write_text("user-ish name", encoding="utf-8")
    assert clg.main(["--log-path", str(log), "--output-dir", str(out), "--draft"]) == 0
    assert notes.read_text(encoding="utf-8") == "notas del usuario"
    assert not_hex.read_text(encoding="utf-8") == "user-ish name"
    assert not leftover.exists()
    assert not leftover_issue.exists()
    names = {path.name for path in out.glob("borrador_*.md")}
    assert "borrador_mis_notas.md" in names
    assert any(name.startswith("borrador_guia_c") for name in names)


def test_symlink_named_like_draft_is_not_unlinked(tmp_path: Path):
    log = _write_log(
        tmp_path / "chat_log.jsonl",
        [_line("SYNTHETIC: horario de atencion sede demo")],
    )
    out = tmp_path / "out"
    out.mkdir()
    target = tmp_path / "outside_secret.md"
    target.write_text("destino externo", encoding="utf-8")
    link = out / "borrador_guia_cabcdefghijkl.md"
    link.symlink_to(target)
    assert clg.main(["--log-path", str(log), "--output-dir", str(out), "--draft"]) == 0
    assert link.is_symlink()
    assert target.read_text(encoding="utf-8") == "destino externo"


def test_subdir_draft_is_not_touched(tmp_path: Path):
    log = _write_log(
        tmp_path / "chat_log.jsonl",
        [_line("SYNTHETIC: horario de atencion sede demo")],
    )
    out = tmp_path / "out"
    nested = out / "sub"
    nested.mkdir(parents=True)
    nested_file = nested / "borrador_guia_c0123456789ab.md"
    nested_file.write_text("nested", encoding="utf-8")
    assert clg.main(["--log-path", str(log), "--output-dir", str(out), "--draft"]) == 0
    assert nested_file.read_text(encoding="utf-8") == "nested"


def test_directory_named_like_draft_does_not_abort(tmp_path: Path, capsys):
    log = _write_log(
        tmp_path / "chat_log.jsonl",
        [_line("SYNTHETIC: horario de atencion sede demo")],
    )
    out = tmp_path / "out"
    out.mkdir()
    decoy = out / "borrador_x.md"
    decoy.mkdir()
    generated_dir = out / "borrador_guia_cabcdefghijkl.md"
    generated_dir.mkdir()
    code = clg.main(["--log-path", str(log), "--output-dir", str(out), "--draft"])
    assert code == 0
    assert decoy.is_dir()
    assert generated_dir.is_dir()
    assert "permiso" not in capsys.readouterr().out.lower()


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


def test_cluster_id_is_letters_hash_of_allowlisted_text():
    rec = clg.parse_record(_line("SYNTHETIC: cuanto vale el cemento demo xyz"))
    assert rec is not None
    cluster = clg.cluster_unmatched([rec])[0]
    assert cluster.cluster_id == clg.cluster_id_for(cluster.representative)
    assert cluster.cluster_id.startswith("c")
    assert cluster.cluster_id[1:].isalpha()
    assert not any(char.isdigit() for char in cluster.cluster_id)
    assert rec.message not in cluster.cluster_id
    assert rec.displayed == cluster.representative


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
    bearer_jwt = _jwt_token("eyJ" + "hbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", "aaa")
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
        f"SYNTHETIC: Bearer {bearer_jwt} brocas demo",
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
        bearer_jwt,
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


def _cli_blobs(stdout: str, out: Path) -> str:
    blobs = [stdout]
    for path in out.rglob("*"):
        blobs.append(path.name)
        if path.is_file() and not path.is_symlink():
            blobs.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(blobs)


def test_cli_review2_leaks_on_all_surfaces(tmp_path: Path, capsys):
    lrm = "\u200e"
    rlm = "\u200f"
    lre = "\u202a"
    vs16 = "\ufe0f"
    cgj = "\u034f"
    sk_live = _stripe_secret("sk", "live", "FakeStripeLiveKey99")
    sk_test = _stripe_secret("sk", "test", "FakeStripeTestKey99")
    pk_live = _stripe_secret("pk", "live", "FakePublishable99")
    rk_live = _stripe_secret("rk", "live", "FakeRestricted99")
    jwt_full = _jwt_token(
        "eyJ" + "hbGciOiJIUzI1NiJ9",
        "eyJ" + "zdWIiOiIxMjM0In0",
        "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
    )
    jwt_sig = "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    messages = [
        "SYNTHETIC: juan (arroba) example punto test cemento demo",
        "SYNTHETIC: ñu arroba example.test varilla demo",
        "SYNTHETIC: cvv 123 horario demo",
        "SYNTHETIC: FED-12351 cotizacion demo",
        "SYNTHETIC: orden #12352 unica demo",
        "SYNTHETIC: www.tienda.example.test/pedido/98765 brocas demo",
        f"SYNTHETIC: {sk_live} domingo demo",
        "SYNTHETIC: cliente: Ramiro Demo Perez portal demo",
        "SYNTHETIC: Sr. Hernando Demo envio demo",
        "SYNTHETIC: contraseña: SuperClave99 material demo",
        "SYNTHETIC: clave: OtraClave99 herramienta demo",
        "SYNTHETIC: password es PassEs99 atencion demo",
        'SYNTHETIC: "password":"QuotedPass99" electronica demo',
        "SYNTHETIC: DB_PASSWORD=DbPass99 domicilio demo",
        "SYNTHETIC: PIN 4321 cotizacion demo",
        "SYNTHETIC: OTP 998877 sede demo",
        "SYNTHETIC: cvc 321 barrio demo",
        f"SYNTHETIC: {sk_test} clave demo",
        f"SYNTHETIC: {pk_live} cuanto demo",
        f"SYNTHETIC: {rk_live} vale demo",
        "SYNTHETIC: gho_FakeOauthToken99 precio demo",
        "SYNTHETIC: ghs_FakeServerToken99 horario demo",
        "SYNTHETIC: ghu_FakeUserToken99 cemento demo",
        "SYNTHETIC: ASIAIOSFODNN7EXAMPLE varilla demo",
        "SYNTHETIC: xoxp-FakeSlackUser99 brocas demo",
        "SYNTHETIC: xoxb-FakeSlackBot99 domingo demo",
        f"SYNTHETIC: jwt {jwt_full} mayorista demo",
        "SYNTHETIC: uuid 123e4567-e89b-12d3-a456-426614174000 portal demo",
        "SYNTHETIC: Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ== envio demo",
        "SYNTHETIC: https://example.test/x?auth=AuthParam99 material demo",
        "SYNTHETIC: https://example.test/x?sig=SigParam99 herramienta demo",
        "SYNTHETIC: https://example.test/x?code=CodeParam99 atencion demo",
        "SYNTHETIC: https://example.test/x?session=SessParam99 electronica demo",
        "SYNTHETIC: https://example.test/x?sid=SidParam99 domicilio demo",
        "SYNTHETIC: https://example.test/x?pass=PassParam99 cotizacion demo",
        "SYNTHETIC: https://example.test/x?client_secret=ClientSecret99 unica demo",
        "SYNTHETIC: https://example.test/x?refresh_token=RefreshTok99 sede demo",
        "SYNTHETIC: https://example.test/x?key=UrlKey99 barrio demo",
        "SYNTHETIC: https://example.test/x?apikey=ApiKeyParam99 clave demo",
        "SYNTHETIC: https://usuario:claveoculta99@host.example.test cuanto demo",
        "SYNTHETIC: ana at example dot test vale demo",
        "SYNTHETIC: ana arroba example punto test precio demo",
        "SYNTHETIC: luis (arroba) example (punto) test horario demo",
        "SYNTHETIC: ipv6 ::1 cemento demo",
        "SYNTHETIC: mac 00-1A-2B-3C-4D-5E varilla demo",
        "SYNTHETIC: mac 00:1a:2b:3c:4d:5f brocas demo",
        f"SYNTHETIC: tel 311{lrm}222{rlm}3366 domingo demo",
        f"SYNTHETIC: tel 311{lre}222{vs16}3367 mayorista demo",
        f"SYNTHETIC: tel 311{cgj}2223368 portal demo",
        "SYNTHETIC: 311 dos dos dos 4411 envio demo",
        "SYNTHETIC: Sra. Marta Demo material demo",
        "SYNTHETIC: doña Elena Demo herramienta demo",
        "SYNTHETIC: don Pedro Demo atencion demo",
        "SYNTHETIC: señor Carlos Demo electronica demo",
        "SYNTHETIC: habla Lucia Demo domicilio demo",
        "SYNTHETIC: atiende Mario Demo cotizacion demo",
        "SYNTHETIC: a nombre de Sofia Demo unica demo",
        "SYNTHETIC: Cll. 10 20 sede demo",
        "SYNTHETIC: Cra. 8 15 barrio demo",
        "SYNTHETIC: Kra 4 6 clave demo",
        "SYNTHETIC: Diag. 30 2 cuanto demo",
        "SYNTHETIC: Tv 11 3 vale demo",
        "SYNTHETIC: apto 501 precio demo",
        "SYNTHETIC: torre 4 horario demo",
        "SYNTHETIC: casa 88 cemento demo",
        "SYNTHETIC: barrio 12 varilla demo",
        "SYNTHETIC: manzana 7 brocas demo",
        "SYNTHETIC: conjunto 9 domingo demo",
        "SYNTHETIC: GH-99 referencia demo",
    ]
    leaks = [
        "juan (arroba) example punto test",
        "juan@example.test",
        "example.test",
        "cvv 123",
        "FED-12351",
        "orden #12352",
        "#12352",
        "www.tienda.example.test/pedido/98765",
        "tienda.example.test",
        sk_live,
        "Ramiro Demo Perez",
        "Hernando Demo",
        "SuperClave99",
        "OtraClave99",
        "PassEs99",
        "QuotedPass99",
        "DbPass99",
        "PIN 4321",
        "OTP 998877",
        "cvc 321",
        sk_test,
        pk_live,
        rk_live,
        "gho_FakeOauthToken99",
        "ghs_FakeServerToken99",
        "ghu_FakeUserToken99",
        "ASIAIOSFODNN7EXAMPLE",
        "xoxp-FakeSlackUser99",
        "xoxb-FakeSlackBot99",
        jwt_full,
        jwt_sig,
        "123e4567-e89b-12d3-a456-426614174000",
        "QWxhZGRpbjpvcGVuIHNlc2FtZQ==",
        "AuthParam99",
        "SigParam99",
        "CodeParam99",
        "SessParam99",
        "SidParam99",
        "PassParam99",
        "ClientSecret99",
        "RefreshTok99",
        "UrlKey99",
        "ApiKeyParam99",
        "usuario:claveoculta99",
        "claveoculta99",
        "ana at example dot test",
        "ana@example.test",
        "luis@example.test",
        "::1",
        "00-1A-2B-3C-4D-5E",
        "00:1a:2b:3c:4d:5f",
        "3112223366",
        "3112223367",
        "3112223368",
        "311 dos dos dos 4411",
        "Marta Demo",
        "Elena Demo",
        "Pedro Demo",
        "Carlos Demo",
        "Lucia Demo",
        "Mario Demo",
        "Sofia Demo",
        "Cll. 10 20",
        "Cra. 8 15",
        "Kra 4 6",
        "Diag. 30 2",
        "Tv 11 3",
        "apto 501",
        "torre 4",
        "casa 88",
        "barrio 12",
        "manzana 7",
        "conjunto 9",
        "GH-99",
    ]
    log = _write_log(tmp_path / "chat_log.jsonl", [_line(msg) for msg in messages])
    out = tmp_path / "out"
    code = clg.main(
        ["--log-path", str(log), "--output-dir", str(out), "--draft", "--top", "80"]
    )
    assert code == 0
    combined = _cli_blobs(capsys.readouterr().out, out)
    missing = [token for token in leaks if token in combined]
    assert missing == [], missing
    for cluster in clg.mine_chat_log(log, top=80).clusters:
        assert cluster.cluster_id not in leaks
        for token in leaks:
            assert token not in cluster.cluster_id


def test_soy_constructor_is_not_redacted_as_name():
    redacted = clg.redact_pii(
        "SYNTHETIC: soy constructor y soy nuevo cliente frecuente"
    )
    assert "constructor" in redacted
    assert "nuevo" in redacted
    assert "frecuente" in redacted
    assert "nombre" not in redacted


def test_bare_product_code_is_not_generic_numero():
    redacted = clg.redact_pii("SYNTHETIC: referencia 7701234 cemento demo")
    assert "7701234" in redacted
    assert "numero" not in redacted


def test_prepare_collapses_whitespace_first():
    text = " " * 40000 + "SYNTHETIC: hola"
    redacted = clg.prepare_for_redaction(text)
    assert "hola" in redacted
    assert "  " not in redacted


def test_escape_markdown_neutralizes_urls_and_gh_refs():
    text = clg.escape_markdown("ver https://example.test/x y GH-99 y www.demo.test/a")
    assert "https://example.test/x" not in text
    assert "www.demo.test/a" not in text
    assert "GH-99" not in text


@pytest.fixture
def isolated_settings(monkeypatch):
    monkeypatch.delenv("ASSISTANT_CHAT_LOG", raising=False)
    return monkeypatch


def _user_fields_clean(text: str) -> None:
    assert not any(char.isdigit() for char in text), text
    folded = clg.fold_letters(text)
    for token in re.findall(r"[a-z]+", folded):
        assert token in clg.ALLOWLIST, token


def test_allowlist_file_is_plain_text_and_human_extendable(tmp_path: Path):
    path = tmp_path / "extra.txt"
    path.write_text("# comentario\n\nMiPalabra\n123no\ncanción\n", encoding="utf-8")
    vocab = clg.load_allowlist(path)
    assert "mipalabra" in vocab
    assert "cancion" in vocab
    assert "123no" not in vocab
    assert "el" in vocab
    assert "email" in vocab
    missing = clg.load_allowlist(tmp_path / "no-such-allowlist.txt")
    assert "pregunta" in missing
    assert clg._ALLOWLIST_PATH.is_file()


def test_project_for_display_drops_unknown_words_and_digits():
    text = clg.project_for_display("Juan Perez tel 3112223348 cemento demo")
    assert "juan" not in text
    assert "perez" not in text
    assert "3112223348" not in text
    assert not any(char.isdigit() for char in text)
    assert "cemento" in text
    assert "demo" in text
    for token in text.split():
        assert token in clg.ALLOWLIST


def test_digit_words_stay_words_on_display():
    rec = clg.parse_record(_line("SYNTHETIC: necesito uno dos de cemento"))
    assert rec is not None
    assert "1" not in rec.displayed
    assert "2" not in rec.displayed
    assert "uno" in rec.displayed
    assert "dos" in rec.displayed
    assert "cada 1" not in rec.displayed


def test_sku_code_is_not_labelled_documento():
    redacted = clg.redact_pii("SYNTHETIC: SKU-123456 cemento demo")
    assert "documento" not in redacted
    displayed = clg.project_for_display(redacted)
    assert not any(char.isdigit() for char in displayed)
    assert "sku" in displayed
    assert "cemento" in displayed


def test_calle_cemento_keeps_product_word():
    rec = clg.parse_record(_line("SYNTHETIC: calle 45 de cemento demo"))
    assert rec is not None
    assert "45" not in rec.displayed
    assert "cemento" in rec.displayed


def test_truncate_happens_after_redaction():
    secret = "xai-" + "placeholdersecretkey99"
    raw = ("SYNTHETIC cemento " * 60) + f" clave: {secret}"
    assert len(raw) > clg.MAX_MSG_CHARS
    rec = clg.parse_record(_line(raw))
    assert rec is not None
    assert secret not in rec.redacted
    assert secret not in rec.displayed
    assert len(rec.displayed) <= clg.MAX_MSG_CHARS


def test_overlong_lines_are_not_reported_as_empty(tmp_path: Path):
    huge = json.dumps(_line("SYNTHETIC: " + ("cemento " * 2000)))
    assert len(huge.encode("utf-8")) > clg.MAX_LINE_BYTES
    path = tmp_path / "chat_log.jsonl"
    path.write_bytes(huge.encode("utf-8") + b"\n")
    result = clg.mine_chat_log(path)
    assert result.empty is True
    assert "vacío" not in result.message.lower()
    assert "vacio" not in result.message.lower()
    assert result.skipped_lines >= 1


def test_output_md_directory_collision_is_spanish(tmp_path: Path, capsys):
    log = _write_log(
        tmp_path / "chat_log.jsonl",
        [_line("SYNTHETIC: horario de atencion sede demo")],
    )
    out = tmp_path / "out"
    out.mkdir()
    (out / "unmatched_question_clusters.md").mkdir()
    code = clg.main(["--log-path", str(log), "--output-dir", str(out)])
    assert code == 1
    text = capsys.readouterr().out.lower()
    assert "carpeta" in text
    assert "permiso" not in text


def test_write_replaces_symlink_instead_of_following(tmp_path: Path):
    log = _write_log(
        tmp_path / "chat_log.jsonl",
        [_line("SYNTHETIC: horario de atencion sede demo")],
    )
    out = tmp_path / "out"
    out.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("destino externo", encoding="utf-8")
    link = out / "unmatched_question_clusters.md"
    link.symlink_to(outside)
    assert clg.main(["--log-path", str(log), "--output-dir", str(out)]) == 0
    assert outside.read_text(encoding="utf-8") == "destino externo"
    assert link.is_file()
    assert not link.is_symlink()
    assert "horario" in link.read_text(encoding="utf-8")


def _fresh_leak_payloads(seed: int) -> tuple[list[str], list[str]]:
    rng = random.Random(seed)
    marks = ["", " ", ".", "-", "\u200b", "\u200e", "\u034f", "\ufe0f"]
    cases = (str.lower, str.upper, str.title)

    def sprinkle(digits: str) -> str:
        out = []
        for char in digits:
            out.append(rng.choice(marks))
            out.append(char)
        return "".join(out)

    messages: list[str] = []
    leaks: list[str] = []

    mobile = "3" + "".join(str(rng.randint(0, 9)) for _ in range(9))
    mobile_txt = sprinkle(mobile)
    messages.append(f"SYNTHETIC: cel {mobile_txt} cemento demo")
    leaks.extend([mobile, mobile_txt, re.sub(r"\D", "", mobile_txt)])

    nit = "".join(str(rng.randint(0, 9)) for _ in range(9))
    nit_txt = f"{nit[:3]}.{nit[3:6]}.{nit[6:]}"
    messages.append(f"SYNTHETIC: NIT {nit_txt} varilla demo")
    leaks.extend([nit, nit_txt])

    card = "4111" + "".join(str(rng.randint(0, 9)) for _ in range(12))
    card_txt = ".".join(card[i : i + 4] for i in range(0, 16, 4))
    messages.append(f"SYNTHETIC: tarjeta {card_txt} brocas demo")
    leaks.extend([card, card_txt])

    labels = (
        "cedula",
        "CC",
        "CE",
        "TI",
        "RUT",
        "RUC",
        "DNI",
        "pasaporte",
        "factura",
        "remision",
        "OC",
        "guia",
        "FE",
    )
    for label in labels:
        number = str(rng.randint(1000, 9999999))
        shown = rng.choice(cases)(label) + " " + number
        messages.append(f"SYNTHETIC: {shown} horario demo")
        leaks.append(number)
        leaks.append(shown)

    local = "ana"
    domain = "ejemplo"
    messages.append(f"SYNTHETIC: {local} (at) {domain} (dot) co cemento demo")
    messages.append(f"SYNTHETIC: {local}_arroba_{domain}.com varilla demo")
    messages.append(f"SYNTHETIC: {local}@{domain},com brocas demo")
    leaks.extend(
        [
            f"{local}@{domain}.co",
            f"{local}@{domain}.com",
            f"{local}@{domain},com",
            f"{local}_arroba_{domain}.com",
            f"{local} (at) {domain} (dot) co",
        ]
    )

    secret_bodies = {
        "psw": "FakePsw" + str(rng.randint(10, 99)),
        "pwd": "FakePwd" + str(rng.randint(10, 99)),
        "apikey": "FakeApi" + str(rng.randint(10, 99)),
        "token": "FakeTok" + str(rng.randint(10, 99)),
        "pin": str(rng.randint(1000, 9999)),
        "otp": str(rng.randint(100000, 999999)),
    }
    messages.append(f"SYNTHETIC: psw: {secret_bodies['psw']} domingo demo")
    messages.append(f"SYNTHETIC: pwd={secret_bodies['pwd']} mayorista demo")
    messages.append(f"SYNTHETIC: apikey {secret_bodies['apikey']} portal demo")
    messages.append(f"SYNTHETIC: token de acceso: {secret_bodies['token']} envio demo")
    messages.append(
        f"SYNTHETIC: clave de acceso {secret_bodies['token']} material demo"
    )
    messages.append(
        f"SYNTHETIC: codigo de verificacion {secret_bodies['otp']} " f"herramienta demo"
    )
    messages.append(f"SYNTHETIC: mi pin es {secret_bodies['pin']} atencion demo")
    leaks.extend(secret_bodies.values())

    prefixes = (
        ("glpat-", "FakeGitLab" + str(rng.randint(10, 99))),
        ("npm_", "FakeNpm" + str(rng.randint(10, 99))),
        ("SG.", "FakeSend" + str(rng.randint(10, 99))),
        ("dop_v1_", "FakeDoppler" + str(rng.randint(10, 99))),
        ("shpat_", "FakeShopify" + str(rng.randint(10, 99))),
    )
    for prefix, body in prefixes:
        token = prefix + body
        messages.append(f"SYNTHETIC: {token} electronica demo")
        leaks.append(token)

    account = "Account" + "Key=" + "FakeAzure" + str(rng.randint(10, 99))
    endpoints = "Default" + "EndpointsProtocol=https"
    messages.append(f"SYNTHETIC: {account} domicilio demo")
    messages.append(f"SYNTHETIC: {endpoints} cotizacion demo")
    leaks.extend([account, "FakeAzure", endpoints])

    for scheme in ("postgres", "mssql", "mysql"):
        user = "dbuser" + str(rng.randint(10, 99))
        password = "dbpass" + str(rng.randint(10, 99))
        uri = f"{scheme}://{user}:{password}@host.example.test/db"
        messages.append(f"SYNTHETIC: {uri} unica demo")
        leaks.extend([uri, user, password, f"{user}:{password}"])

    name = rng.choice(("Hernando", "Ramiro", "Lucia")) + " Demo"
    messages.append(f"SYNTHETIC: atendido por {name} sede demo")
    messages.append(f"SYNTHETIC: Dr. {name} barrio demo")
    messages.append(f"SYNTHETIC: Ing. {name} clave demo")
    leaks.append(name)

    messages.append("SYNTHETIC: Av. Boyaca 68-45 cemento demo")
    messages.append("SYNTHETIC: Mz 5 Cs 12 varilla demo")
    leaks.extend(["68-45", "Boyaca", "Boyacá"])

    return messages, [item for item in leaks if item]


@pytest.mark.parametrize("seed", [20260930, 202609301, 884422])
def test_fuzz_default_deny_cli_surfaces(tmp_path: Path, capsys, seed: int):
    messages, leaks = _fresh_leak_payloads(seed)
    log = _write_log(tmp_path / "chat_log.jsonl", [_line(msg) for msg in messages])
    out = tmp_path / "out"
    code = clg.main(
        ["--log-path", str(log), "--output-dir", str(out), "--draft", "--top", "80"]
    )
    assert code == 0
    stdout = capsys.readouterr().out
    combined = _cli_blobs(stdout, out)
    missing = [token for token in leaks if token and token in combined]
    assert missing == [], missing

    result = clg.mine_chat_log(log, top=80)
    assert result.empty is False
    for cluster in result.clusters:
        _user_fields_clean(cluster.representative)
        assert re.fullmatch(r"c[a-z]{12}", cluster.cluster_id)
        assert not any(char.isdigit() for char in cluster.cluster_id)
        for example in cluster.examples:
            _user_fields_clean(example)

    csv_text = (out / "unmatched_question_clusters.csv").read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        _user_fields_clean(row["representativa"])
        assert re.fullmatch(r"c[a-z]{12}", row["cluster_id"])
        if row["ejemplos"]:
            _user_fields_clean(row["ejemplos"])

    for path in out.glob("borrador_*.md"):
        assert re.fullmatch(r"borrador_(?:guia|issue)_c[a-z]{12}\.md", path.name)
        assert not any(char.isdigit() for char in path.name)


def test_regex_layer_catches_review_digit_shapes():
    samples = {
        "3112223348": "SYNTHETIC: cel 3112223348 cemento demo",
        "+573112223361": "SYNTHETIC: tel +573112223361 varilla demo",
        "311.222.3349": "SYNTHETIC: cel 311.222.3349 brocas demo",
        "900.123.459-0": "SYNTHETIC: NIT 900.123.459-0 horario demo",
        "4111.1111.1111.1113": "SYNTHETIC: tarjeta 4111.1111.1111.1113 demo",
        "1234567894": "SYNTHETIC: c.c 1234567894 cemento demo",
        "12348": "SYNTHETIC: factura No. 12348 varilla demo",
        "4326": "SYNTHETIC: remision No. 4326 brocas demo",
        "7327": "SYNTHETIC: OC 7327 horario demo",
    }
    for leak, raw in samples.items():
        redacted = clg.redact_pii(raw)
        displayed = clg.project_for_display(redacted)
        assert leak not in redacted
        assert leak not in displayed
        assert not any(char.isdigit() for char in displayed)


def test_three_or_more_digit_words_collapse_to_numero():
    rec = clg.parse_record(_line("SYNTHETIC: cinco tres dos de cemento demo"))
    assert rec is not None
    assert "cinco" not in rec.displayed
    assert "tres" not in rec.displayed
    assert "dos" not in rec.displayed
    assert "numero" in rec.displayed
    assert "cemento" in rec.displayed
    long_run = clg.redact_pii(
        "SYNTHETIC: tres uno uno dos dos dos siete siete cero uno cemento"
    )
    assert "tres" not in long_run.split()
    assert "uno" not in long_run.split()
    assert "numero" in long_run
    pair = clg.parse_record(_line("SYNTHETIC: necesito uno dos de cemento"))
    assert pair is not None
    assert "uno" in pair.displayed
    assert "dos" in pair.displayed
    assert "1" not in pair.displayed
    assert "2" not in pair.displayed


def test_clave_and_pin_word_are_redacted_as_secrets():
    samples = (
        "SYNTHETIC: clave grapa material demo",
        "SYNTHETIC: pin grapa material demo",
        "SYNTHETIC: password grapa material demo",
        "SYNTHETIC: passphrase grapa material demo",
    )
    for raw in samples:
        redacted = clg.redact_pii(raw)
        displayed = clg.project_for_display(redacted)
        assert "grapa" not in redacted.lower()
        assert "grapa" not in displayed
        assert "secreto" in redacted.lower()


def test_labeled_passphrase_consumes_rest_of_sentence():
    multi = clg.redact_pii("SYNTHETIC: passphrase es caballo bateria grapa correcta")
    for leak in ("caballo", "bateria", "grapa", "correcta"):
        assert leak not in multi.lower()
    assert "secreto" in multi.lower()

    two_words = clg.redact_pii("SYNTHETIC: passphrase grapa cemento")
    assert "grapa" not in two_words.lower()
    assert "cemento" not in two_words.lower()

    punctuated = (
        "SYNTHETIC: la clave, es grapa",
        "SYNTHETIC: clave - grapa cemento",
        "SYNTHETIC: pass: grapa",
        "SYNTHETIC: codigo secreto grapa",
        "SYNTHETIC: clave...grapa",
        "SYNTHETIC: contraseña del wifi es grapa",
    )
    for raw in punctuated:
        redacted = clg.redact_pii(raw)
        assert "grapa" not in redacted.lower(), raw
        assert "secreto" in redacted.lower()

    bounded = clg.redact_pii("SYNTHETIC: passphrase grapa caballo. precio cemento demo")
    assert "grapa" not in bounded.lower()
    assert "caballo" not in bounded.lower()
    assert "cemento" in bounded.lower()


def test_repeated_pin_labels_scale_near_linear():
    def _run(n: int) -> tuple[float, str]:
        payload = ("pin " * n).rstrip()
        start = time.perf_counter()
        redacted = clg._redact_labeled_passphrases(payload)
        return time.perf_counter() - start, redacted

    t_n, out_n = _run(2000)
    t_4n, out_4n = _run(8000)
    for redacted in (out_n, out_4n):
        assert "pin" not in redacted.lower()
        assert "secreto" in redacted.lower()
    # 4× input; allow CI slop but stay well under quadratic (~16×).
    assert t_4n < (t_n * 10) + 0.4, (t_n, t_4n)


def test_inner_label_does_not_cross_sentence_end():
    helper = clg._redact_labeled_passphrases("clave grapa pin. precio cemento")
    assert "precio cemento" in helper
    assert "grapa" not in helper.lower()
    redacted = clg.redact_pii("SYNTHETIC: clave grapa pin. precio cemento")
    assert "grapa" not in redacted.lower()
    assert "cemento" in redacted.lower()
    assert "precio" in redacted.lower()


def test_token_secreto_redacts_following_value():
    one = clg.redact_pii("SYNTHETIC: token secreto grapa material demo")
    assert "grapa" not in one.lower()
    assert "secreto" in one.lower()
    labeled = clg.redact_pii("SYNTHETIC: token secreto: caballo bateria")
    assert "caballo" not in labeled.lower()
    assert "bateria" not in labeled.lower()


def test_passphrase_redaction_does_not_cross_newline():
    redacted = clg.redact_pii("SYNTHETIC: clave es grapa\nNecesito cemento demo")
    assert "grapa" not in redacted.lower()
    assert "cemento" in redacted.lower()


def test_unique_cluster_ids_uses_per_key_nonce():
    shared = [
        clg.QuestionCluster(
            cluster_id="cabcdefghijkl",
            count=1,
            representative="synthetic precio",
            examples=(),
            normalized="synthetic precio",
        )
        for _ in range(40)
    ]
    result = clg._unique_cluster_ids(shared)
    ids = [item.cluster_id for item in result]
    assert len(ids) == len(set(ids))
    assert ids[0] == "cabcdefghijkl"
    assert ids[1] == clg.cluster_id_for("synthetic precio\nsynthetic precio\n1")
    assert ids[2] == clg.cluster_id_for("synthetic precio\nsynthetic precio\n2")
    assert ids[39] == clg.cluster_id_for("synthetic precio\nsynthetic precio\n39")


_DETACHED_SUFFIX_RE = re.compile(
    r"(?:stico|ptico|ctrico|ctrica|ltico|sicas|mpara|mparas)$"
)
_INCOMPLETE_STEM_RE = re.compile(r"(?:si|ci|ig|corr|eri|iad)$")
# Real short words that look like stems/prefixes of longer entries.
# Do not infer fragments from "word is a prefix of another word".
_ALLOWLIST_REAL_WORD_EXCEPTIONS = frozenset({"cal"})
_FORBIDDEN_ALLOWLIST_NAMES = frozenset(
    {
        "ada",
        "marco",
        "mina",
        "cielo",
        "blanca",
        "estrella",
        "diamante",
        "cortes",
        "luz",
        "neiva",
        "huila",
        "mica",
    }
)
_FORBIDDEN_ALLOWLIST_FRAGMENTS = frozenset(
    {
        "hidr",
        "xido",
        "bsika",
        "bdrywall",
        "iluminaci",
        "ilumina",
        "nivelaci",
        "sif",
        "xic",
        "xico",
        "impermeabil",
        "ferreter",
        "ete",
        "tap",
        "tel",
        "rot",
        "met",
        "asf",
        "cer",
        "mpara",
        "sicas",
        "stico",
        "ptico",
        "lica",
        "ctrico",
        "ibre",
        "tica",
        "cicl",
        "divisi",
        "fundaci",
        "habitaci",
        "filtraci",
        "inspecci",
        "presi",
        "despu",
        "desag",
        "hormig",
        "carpinter",
        "tuber",
        "grifer",
        "anticorr",
        "averi",
        "averiad",
        "epox",
        "fe",
        "fv",
        "oc",
        "x",
        "xyz",
        "ruc",
    }
)
_ALLOWED_SHORT = frozenset(
    {
        "a",
        "al",
        "de",
        "e",
        "el",
        "en",
        "es",
        "la",
        "le",
        "lo",
        "me",
        "mi",
        "ni",
        "no",
        "o",
        "se",
        "si",
        "su",
        "te",
        "tu",
        "un",
        "y",
        "ya",
    }
)


def _read_allowlist_words() -> list[str]:
    words: list[str] = []
    for line in clg._ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines():
        raw = line.split("#", 1)[0].strip().lower()
        if not raw:
            continue
        words.append(raw)
    return words


def _is_truncated_allowlist_stem(word: str) -> bool:
    """True for incomplete Spanish stems or detached suffixes.

    Real words in ``_ALLOWLIST_REAL_WORD_EXCEPTIONS`` are never fragments.
    This does not treat a word as truncated just because a longer cousin
    exists (``material`` must stay allowed if ``materializar`` is added).
    """
    if word in _ALLOWLIST_REAL_WORD_EXCEPTIONS:
        return False
    if len(word) >= 5 and _INCOMPLETE_STEM_RE.search(word):
        if not word.endswith(("cion", "sion", "cia", "cio", "cie")):
            return True
    return bool(_DETACHED_SUFFIX_RE.fullmatch(word))


def test_allowlist_txt_rejects_names_junk_and_duplicates():
    words = _read_allowlist_words()
    assert words
    assert len(words) == len(set(words))
    for word in words:
        assert word.isascii() and word.isalpha(), word
        assert word not in _FORBIDDEN_ALLOWLIST_NAMES
        assert word not in _FORBIDDEN_ALLOWLIST_FRAGMENTS
        if len(word) < 3:
            assert word in _ALLOWED_SHORT, word
        assert not _is_truncated_allowlist_stem(word), word


def test_allowlist_keeps_cal_as_real_word():
    words = set(_read_allowlist_words())
    assert "cal" in words
    assert "cal" in _ALLOWLIST_REAL_WORD_EXCEPTIONS
    rec = clg.parse_record(_line("SYNTHETIC: precio de la cal"))
    assert rec is not None
    assert "cal" in rec.displayed.split()
    assert rec.displayed == "synthetic precio de la cal"


def test_allowlist_fragment_rule_is_explicit_not_prefix():
    """Fragments are an explicit denylist, not 'prefix of a longer word'."""
    assert "ilumina" in _FORBIDDEN_ALLOWLIST_FRAGMENTS
    assert "xico" in _FORBIDDEN_ALLOWLIST_FRAGMENTS
    assert "impermeabil" in _FORBIDDEN_ALLOWLIST_FRAGMENTS
    assert "ferreter" in _FORBIDDEN_ALLOWLIST_FRAGMENTS
    words = _read_allowlist_words()
    assert "ilumina" not in words
    assert "xico" not in words
    assert "impermeabil" not in words
    assert "ferreter" not in words
    assert _is_truncated_allowlist_stem("ilumina") is False
    assert _is_truncated_allowlist_stem("material") is False
    assert _is_truncated_allowlist_stem("cal") is False


def test_missing_allowlist_logs_warning(tmp_path: Path, caplog):
    missing = tmp_path / "no-such-allowlist.txt"
    with caplog.at_level(logging.WARNING):
        vocab = clg.load_allowlist(missing)
    assert "pregunta" in vocab
    assert any(
        "lista blanca" in record.message.lower()
        or "allowlist" in record.message.lower()
        for record in caplog.records
    )


def test_same_projection_clusters_do_not_collide(tmp_path: Path):
    rows = [
        _line("SYNTHETIC: precio qzxalpha qzxbeta qzxgamma"),
        _line("SYNTHETIC: precio qzxdelta qzxepsilon qxzzeta"),
    ]
    records = [clg.parse_record(row) for row in rows]
    records = [row for row in records if row is not None]
    assert [row.displayed for row in records] == [
        "synthetic precio",
        "synthetic precio",
    ]
    clusters = clg.cluster_unmatched(records)
    assert len(clusters) == 2
    ids = [cluster.cluster_id for cluster in clusters]
    assert len(ids) == len(set(ids))
    out = tmp_path / "out"
    written = clg.write_outputs(clusters, out, write_drafts=True)
    drafts = list(out.glob("borrador_guia_*.md"))
    assert len(drafts) == 2
    csv_text = written["csv"].read_text(encoding="utf-8-sig")
    reader = list(csv.DictReader(io.StringIO(csv_text)))
    assert {row["cluster_id"] for row in reader} == set(ids)
