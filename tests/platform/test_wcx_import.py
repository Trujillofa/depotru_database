"""Synthetic-only WCX contract tests. No customer export is loaded here."""

import json
import subprocess
import sys

import pytest

from depotru_integrations.wcx_import import dedupe_key, normalize_phone, scan_export


@pytest.mark.parametrize(
    "raw",
    ["3000000000", "573000000000", "+57 (300) 000-0000", "00573000000000"],
)
def test_colombian_mobile_variants(raw):
    assert normalize_phone(raw) == "+573000000000"


@pytest.mark.parametrize(
    "raw",
    [
        None,
        True,
        3000000000,
        "",
        "tg:3000000000",
        "+13000000000",
        "123",
        "3000000000 ext 2",
        "٣٠٠٠٠٠٠٠٠٠",
        "++573000000000",
        "(3000000000",
        "3000000000/3000000001",
        "03000000000",
        "\u00a03000000000\u00a0",
        "()3000000000",
    ],
)
def test_ambiguous_or_invalid_phone_is_not_linked(raw):
    assert normalize_phone(raw) is None


def test_fixed_line_requires_current_colombian_prefix():
    assert normalize_phone("6010000000") == "+576010000000"
    assert normalize_phone("5710000000") is None


def test_keys_are_source_and_case_scoped():
    assert dedupe_key("synthetic", "message", 10, 1) == ("synthetic", "message", 1, 10)
    assert dedupe_key("synthetic", "message", 10, 1) != dedupe_key(
        "synthetic", "message", 10, 2
    )
    assert dedupe_key("other", "case", 10) != dedupe_key("synthetic", "case", 10)


@pytest.mark.parametrize("identifier", [None, True, 0, -1, "1", 1.0])
def test_dedupe_requires_positive_integer_source_ids(identifier):
    with pytest.raises(ValueError, match="invalid_identity"):
        dedupe_key("synthetic", "case", identifier)


def record(case_id=1, customer_id=2, message_id=3):
    return {
        "id": case_id,
        "code": "SYNTHETIC",
        "exportedAt": "2026-01-01T00:00:00Z",
        "detail": {
            "id": case_id,
            "idCustomer": customer_id,
            "customerPhone": "+573000000000",
            "subject": "SYNTHETIC",
        },
        "movements": [
            {
                "id": message_id,
                "idTicket": case_id,
                "contentText": "SYNTHETIC",
                "dateValue": None,
            }
        ],
    }


def write_rows(tmp_path, rows):
    (tmp_path / "synthetic.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )


def test_reimport_duplicates_and_conflicts_are_distinct(tmp_path):
    first = record()
    repeat = record()
    repeat["exportedAt"] = "2026-02-01T00:00:00Z"
    changed = record()
    changed["movements"][0]["contentText"] = "SYNTHETIC EDIT"
    write_rows(tmp_path, [first, repeat, changed])
    counts = scan_export(tmp_path, "synthetic")
    assert counts["cases_unique"] == 1
    assert counts["cases_duplicate"] == 2
    assert counts["messages_unique"] == 1
    assert counts["messages_duplicate"] == 1
    assert counts["messages_conflict"] == 1
    assert scan_export(tmp_path, "synthetic") == counts


def test_same_message_id_in_different_cases_is_preserved(tmp_path):
    write_rows(tmp_path, [record(), record(case_id=4)])
    counts = scan_export(tmp_path, "synthetic")
    assert counts["messages_unique"] == 2
    assert counts["customers_unique"] == 1


def test_shared_phone_does_not_merge_source_customers(tmp_path):
    write_rows(tmp_path, [record(), record(case_id=4, customer_id=5)])
    counts = scan_export(tmp_path, "synthetic")
    assert counts["customers_unique"] == 2
    assert counts["phones_shared_by_customers"] == 1


def test_quarantine_bad_identity_and_events(tmp_path):
    row = record()
    row["movements"] += [{"id": 0}, {"id": 8, "idTicket": 99}]
    missing = record(case_id=4, customer_id=0)
    write_rows(tmp_path, [row, missing])
    counts = scan_export(tmp_path, "synthetic")
    assert counts["movements_without_id"] == 1
    assert counts["movements_wrong_case"] == 1
    assert counts["cases_without_customer_id"] == 1
    assert counts["messages_unique"] == 2


def test_inventory_rows_are_not_detail_records(tmp_path):
    write_rows(tmp_path, [{"id": 1, "idCustomer": 2}, record()])
    assert scan_export(tmp_path, "synthetic")["inventory_rows"] == 1


def test_bad_structure_has_sanitized_error(tmp_path):
    write_rows(tmp_path, [{"id": 1, "detail": "SYNTHETIC PRIVATE", "movements": []}])
    with pytest.raises(ValueError, match="invalid_structure"):
        scan_export(tmp_path, "synthetic")


def test_cli_requires_dry_run_and_never_writes(tmp_path):
    write_rows(tmp_path, [record()])
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    command = [
        sys.executable,
        "-m",
        "depotru_integrations.wcx_import",
        "--input",
        str(tmp_path),
        "--source",
        "synthetic",
    ]
    refused = subprocess.run(command, capture_output=True, text=True)
    assert refused.returncode == 2
    success = subprocess.run(command + ["--dry-run"], capture_output=True, text=True)
    assert success.returncode == 0
    counts = json.loads(success.stdout)
    assert counts["cases_unique"] == 1
    assert all(type(v) is int for v in counts.values())
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before
    assert "SYNTHETIC" not in success.stdout


def test_cli_hides_parse_errors_and_paths(tmp_path):
    (tmp_path / "synthetic.jsonl").write_text("SYNTHETIC PRIVATE", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "depotru_integrations.wcx_import",
            "--dry-run",
            "--input",
            str(tmp_path),
            "--source",
            "synthetic",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "SYNTHETIC PRIVATE" not in result.stderr
    assert str(tmp_path) not in result.stderr


@pytest.mark.parametrize("body", ["", " \n\n"])
def test_empty_jsonl_is_rejected(tmp_path, body):
    (tmp_path / "synthetic.jsonl").write_text(body, encoding="utf-8")
    with pytest.raises(ValueError, match="empty_input"):
        scan_export(tmp_path, "synthetic")


@pytest.mark.parametrize("order", [(0, 1, 1), (1, 0, 1), (1, 1, 0)])
def test_conflict_counts_are_independent_of_record_order(tmp_path, order):
    variants = [record(), record()]
    variants[1]["movements"][0]["contentText"] = "SYNTHETIC EDIT"
    write_rows(tmp_path, [variants[index] for index in order])
    counts = scan_export(tmp_path, "synthetic")
    assert counts["messages_unique"] == 1
    assert counts["messages_duplicate"] == 1
    assert counts["messages_conflict"] == 1


def test_symlink_input_is_rejected(tmp_path):
    write_rows(tmp_path, [record()])
    (tmp_path / "alias.jsonl").symlink_to(tmp_path / "synthetic.jsonl")
    with pytest.raises(ValueError, match="unsafe_input"):
        scan_export(tmp_path, "synthetic")
