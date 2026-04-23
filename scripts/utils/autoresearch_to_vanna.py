#!/usr/bin/env python3

import argparse
import csv
import json
from pathlib import Path

QUESTION_KEYS = ("question", "prompt", "nl", "input", "query_text")
SQL_KEYS = ("sql", "query", "completion", "target", "answer_sql")
DOC_FILTER = "DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')"


def _insert_before_tail(sql: str, fragment: str) -> str:
    lower = sql.lower()
    positions = [
        p
        for p in (
            lower.find(" group by "),
            lower.find(" order by "),
            lower.find(" having "),
            lower.find(" limit "),
        )
        if p != -1
    ]
    insert_at = min(positions) if positions else len(sql)
    head = sql[:insert_at].rstrip()
    tail = sql[insert_at:]
    if head.endswith(";"):
        head = head[:-1].rstrip()
    return f"{head} {fragment}{tail}"


def _ensure_doc_filter(sql: str) -> str:
    lower = sql.lower()
    if "from banco_datos" not in lower or "documentoscodigo" in lower:
        return sql
    if " where " in lower:
        return _insert_before_tail(sql, f"AND {DOC_FILTER}")
    return _insert_before_tail(sql, f"WHERE {DOC_FILTER}")


def _is_sql_like(sql: str) -> bool:
    upper = sql.upper()
    return "SELECT" in upper or "WITH" in upper


def _extract_from_mapping(item: dict[str, object]) -> tuple[str, str]:
    question = ""
    sql = ""
    for key in QUESTION_KEYS:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            question = value.strip()
            break
    for key in SQL_KEYS:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            sql = value.strip()
            break
    return question, sql


def _records_from_jsonl(file_path: Path) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    with file_path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(item, dict):
                continue
            records.append(_extract_from_mapping(item))
    return records


def _records_from_delimited(file_path: Path, delimiter: str) -> list[tuple[str, str]]:
    with file_path.open("r", encoding="utf-8") as handle:
        rows = list(csv.reader(handle, delimiter=delimiter))

    if not rows:
        return []

    header = [cell.strip().lower() for cell in rows[0]]
    has_named_fields = any(key in header for key in QUESTION_KEYS + SQL_KEYS)
    records: list[tuple[str, str]] = []

    if has_named_fields:
        q_index = next(
            (i for i, col in enumerate(header) if col in QUESTION_KEYS), None
        )
        s_index = next((i for i, col in enumerate(header) if col in SQL_KEYS), None)
        if q_index is None and s_index is not None and len(header) >= 2:
            q_index = 0 if s_index != 0 else 1
        if s_index is None and q_index is not None and len(header) >= 2:
            s_index = 0 if q_index != 0 else 1
        if q_index is None or s_index is None:
            return []
        for row in rows[1:]:
            if max(q_index, s_index) >= len(row):
                continue
            records.append((row[q_index].strip(), row[s_index].strip()))
        return records

    for row in rows:
        if len(row) < 2:
            continue
        records.append((row[0].strip(), row[1].strip()))
    return records


def load_records(file_path: Path) -> list[tuple[str, str]]:
    ext = file_path.suffix.lower()
    if ext == ".jsonl":
        return _records_from_jsonl(file_path)
    if ext == ".tsv":
        return _records_from_delimited(file_path, "\t")
    if ext == ".csv":
        return _records_from_delimited(file_path, ",")
    raise ValueError(f"Unsupported input format: {ext}")


def convert(
    input_path: Path, output_path: Path, source: str, allow_non_select: bool
) -> tuple[int, int]:
    records = load_records(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    skipped = 0
    with output_path.open("w", encoding="utf-8") as handle:
        for index, (question, sql) in enumerate(records, start=1):
            if not question or not sql:
                skipped += 1
                continue
            if not allow_non_select and not _is_sql_like(sql):
                skipped += 1
                continue
            normalized_sql = _ensure_doc_filter(sql)
            row = {
                "question": question,
                "sql": normalized_sql,
                "source": source,
                "row_number": index,
            }
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            written += 1

    return written, skipped


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--source", default="autoresearch")
    parser.add_argument("--allow-non-select", action="store_true")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        return 1

    try:
        written, skipped = convert(
            input_path=input_path,
            output_path=output_path,
            source=args.source,
            allow_non_select=args.allow_non_select,
        )
    except Exception as exc:
        print(f"Conversion failed: {exc}")
        return 1

    print(f"Converted examples: {written}")
    print(f"Skipped rows: {skipped}")
    print(f"Output file: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
