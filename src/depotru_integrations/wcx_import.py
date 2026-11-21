"""Offline WCX inventory prototype. Counts only: no DB, network or file writes.

Run with PYTHONPATH=src python -m depotru_integrations.wcx_import --dry-run.
Source records and identifiers must never be printed, even on failure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, NoReturn, Optional, Set, Tuple


def normalize_phone(raw: Any) -> Optional[str]:
    """Return a conservative Colombian E.164 candidate, not identity proof.

    Accept current mobile and geographic fixed-line numbers only. No extension,
    foreign number, legacy area code, inferred missing digit or channel prefix.
    """
    if not isinstance(raw, str) or not raw.isascii():
        return None
    value = raw.strip()
    if not re.fullmatch(r"\+?[0-9 ()\-]+", value):
        return None
    if value.count("(") != value.count(")") or value.count("(") > 1:
        return None
    if "(" in value and value.index("(") > value.index(")"):
        return None
    if "(" in value and not re.fullmatch(
        r"[ \-]*[0-9][0-9 \-]*", value[value.index("(") + 1 : value.index(")")]
    ):
        return None
    digits = re.sub(r"[ ()\-]", "", value)
    if digits.startswith("+57"):
        digits = digits[3:]
    elif digits.startswith("0057"):
        digits = digits[4:]
    elif digits.startswith("57") and len(digits) == 12:
        digits = digits[2:]
    if re.fullmatch(r"(?:3[0-9]{9}|60[1245678][0-9]{7})", digits):
        return "+57" + digits
    return None


def _positive_id(value: Any) -> bool:
    return type(value) is int and value > 0


def dedupe_key(
    source: str, entity: str, identifier: Any, case_id: Any = None
) -> Tuple[Any, ...]:
    """Stable source identity, never phone/body/timestamp or export shard order."""
    if (
        not re.fullmatch(r"[a-z0-9_-]{1,64}", source)
        or entity not in ("customer", "case", "message")
        or not _positive_id(identifier)
        or (entity == "message" and not _positive_id(case_id))
    ):
        raise ValueError("invalid_identity")
    if entity == "message":
        return source, entity, case_id, identifier
    return source, entity, identifier


def _fingerprint(value: Any) -> bytes:
    payload = json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).digest()


def scan_export(root: Path, source: str) -> Dict[str, int]:
    """Stream JSONL records, retain only keys/hashes and return aggregate counts.

    Inventory rows are counted separately from detail envelopes. Conflicts are
    observations, never last-write-wins updates. Memory grows with unique IDs.
    """
    dedupe_key(source, "case", 1)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("unsafe_input")
    counts: Counter = Counter(
        {
            key: 0
            for key in (
                "files",
                "rows",
                "inventory_rows",
                "detail_rows",
                "cases_unique",
                "cases_duplicate",
                "cases_conflict",
                "cases_without_customer_id",
                "customers_unique",
                "phones_unique",
                "phones_shared_by_customers",
                "customers_with_multiple_phones",
                "cases_phone_valid",
                "cases_phone_invalid",
                "movements",
                "movements_without_id",
                "movements_wrong_case",
                "messages_unique",
                "messages_duplicate",
                "messages_conflict",
            )
        }
    )
    seen: Dict[Tuple[Any, ...], Set[bytes]] = {}
    customers = set()
    phone_customers = defaultdict(set)
    customer_phones = defaultdict(set)

    def observe(entity: str, key: Tuple[Any, ...], value: Any) -> None:
        digest = _fingerprint(value)
        if key not in seen:
            counts[entity + "_unique"] += 1
            seen[key] = {digest}
        elif digest in seen[key]:
            counts[entity + "_duplicate"] += 1
        else:
            counts[entity + "_conflict"] += 1
            seen[key].add(digest)

    # Do not follow symlink directories or files, including nested directories.
    if any(path.is_symlink() for path in root.rglob("*")):
        raise ValueError("unsafe_input")
    files = sorted(root.rglob("*.jsonl"))
    if not files:
        raise ValueError("empty_input")
    for path in files:
        counts["files"] += 1
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                row = json.loads(line)
                counts["rows"] += 1
                if not isinstance(row, dict):
                    raise ValueError("invalid_structure")
                if "detail" not in row and "movements" not in row:
                    if not _positive_id(row.get("id")) or "idCustomer" not in row:
                        raise ValueError("invalid_structure")
                    counts["inventory_rows"] += 1
                    continue
                detail, movements = row.get("detail"), row.get("movements")
                if not isinstance(detail, dict) or not isinstance(movements, list):
                    raise ValueError("invalid_structure")
                case_id = row.get("id")
                key = dedupe_key(source, "case", case_id)
                if type(detail.get("id")) is not int or detail["id"] != case_id:
                    raise ValueError("invalid_structure")
                counts["detail_rows"] += 1
                observe("cases", key, detail)
                customer_id = detail.get("idCustomer")
                phone = normalize_phone(detail.get("customerPhone"))
                counts["cases_phone_valid" if phone else "cases_phone_invalid"] += 1
                if _positive_id(customer_id):
                    customer = dedupe_key(source, "customer", customer_id)
                    customers.add(customer)
                    if phone:
                        phone_customers[phone].add(customer)
                        customer_phones[customer].add(phone)
                else:
                    counts["cases_without_customer_id"] += 1
                for movement in movements:
                    if not isinstance(movement, dict):
                        raise ValueError("invalid_structure")
                    counts["movements"] += 1
                    if not _positive_id(movement.get("id")):
                        counts["movements_without_id"] += 1
                        continue
                    if (
                        type(movement.get("idTicket")) is not int
                        or movement["idTicket"] != case_id
                    ):
                        counts["movements_wrong_case"] += 1
                        continue
                    key = dedupe_key(source, "message", movement["id"], case_id)
                    observe("messages", key, movement)
    if not counts["rows"]:
        raise ValueError("empty_input")
    counts["customers_unique"] = len(customers)
    counts["phones_unique"] = len(phone_customers)
    counts["phones_shared_by_customers"] = sum(
        len(ids) > 1 for ids in phone_customers.values()
    )
    counts["customers_with_multiple_phones"] = sum(
        len(phones) > 1 for phones in customer_phones.values()
    )
    return dict(sorted(counts.items()))


class _SafeParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        self.exit(2, "wcx_import: invalid_arguments\n")


def main() -> int:
    """Require dry-run explicitly. The executable intentionally has no apply mode."""
    parser = _SafeParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", required=True)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path.home() / "wcx/raw/wcx-chats-export-12mo",
    )
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    try:
        counts = scan_export(args.input, args.source)
    except (ValueError, OSError, UnicodeError, RecursionError):
        print("wcx_import: invalid_or_unreadable_export", file=sys.stderr)
        return 2
    print(json.dumps(counts, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
