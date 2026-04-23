#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument(
        "--output",
        default="data/autoresearch_vanna_examples.jsonl",
    )
    parser.add_argument("--source", default="autoresearch")
    parser.add_argument("--allow-non-select", action="store_true")
    parser.add_argument("--no-start", action="store_true")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument(
        "--converter",
        default="scripts/utils/autoresearch_to_vanna.py",
    )
    parser.add_argument("--vanna-entry", default="src/vanna_grok.py")
    return parser.parse_args()


def run_converter(
    repo_root: Path,
    python_exec: str,
    converter: Path,
    input_file: Path,
    output_file: Path,
    source: str,
    allow_non_select: bool,
) -> int:
    cmd = [
        python_exec,
        str(converter),
        "--input",
        str(input_file),
        "--output",
        str(output_file),
        "--source",
        source,
    ]
    if allow_non_select:
        cmd.append("--allow-non-select")

    print("Running converter...")
    print(" ".join(cmd))
    result = subprocess.run(cmd, cwd=repo_root, check=False)
    return result.returncode


def start_vanna(
    repo_root: Path, python_exec: str, entry_path: Path, training_file: Path
) -> int:
    env = os.environ.copy()
    env["AUTORESEARCH_TRAINING_FILE"] = str(training_file.resolve())

    cmd = [python_exec, str(entry_path)]
    print("\nStarting Vanna server with external training file...")
    print(f"AUTORESEARCH_TRAINING_FILE={training_file.resolve()}")
    print(" ".join(cmd))

    try:
        result = subprocess.run(cmd, cwd=repo_root, env=env, check=False)
        return result.returncode
    except KeyboardInterrupt:
        print("\nStopped by user.")
        return 130


def main() -> int:
    args = parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    input_file = Path(args.input)
    output_file = Path(args.output)

    if not input_file.is_absolute():
        input_file = repo_root / input_file
    if not output_file.is_absolute():
        output_file = repo_root / output_file

    converter_path = Path(args.converter)
    if not converter_path.is_absolute():
        converter_path = repo_root / converter_path

    entry_path = Path(args.vanna_entry)
    if not entry_path.is_absolute():
        entry_path = repo_root / entry_path

    if not input_file.exists():
        print(f"Input file not found: {input_file}")
        return 1

    if not converter_path.exists():
        print(f"Converter script not found: {converter_path}")
        return 1

    if not entry_path.exists() and not args.no_start:
        print(f"Vanna entry file not found: {entry_path}")
        return 1

    output_file.parent.mkdir(parents=True, exist_ok=True)

    converter_rc = run_converter(
        repo_root=repo_root,
        python_exec=args.python,
        converter=converter_path,
        input_file=input_file,
        output_file=output_file,
        source=args.source,
        allow_non_select=args.allow_non_select,
    )
    if converter_rc != 0:
        return converter_rc

    if not output_file.exists() or output_file.stat().st_size == 0:
        print(f"Converted output is empty: {output_file}")
        return 1

    if args.no_start:
        print("\nConversion complete (--no-start set).")
        print(
            "Next step:\n"
            f"AUTORESEARCH_TRAINING_FILE={output_file.resolve()} {args.python} {entry_path}"
        )
        return 0

    return start_vanna(
        repo_root=repo_root,
        python_exec=args.python,
        entry_path=entry_path,
        training_file=output_file,
    )


if __name__ == "__main__":
    raise SystemExit(main())
