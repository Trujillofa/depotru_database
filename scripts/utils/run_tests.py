#!/usr/bin/env python3
"""
Test Runner for Business Data Analyzer
======================================
Convenient script to run tests with common options.

Usage:
    python run_tests.py              # Run all tests
    python run_tests.py -v           # Verbose output
    python run_tests.py --cov        # With coverage report
    python run_tests.py --quick      # Run only basic tests
    python run_tests.py --all        # Run all tests including those requiring dependencies
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Run tests with pytest."""
    # Check if pytest is available
    try:
        subprocess.run(["pytest", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Error: pytest is not installed.")
        print("Install it with: pip install pytest pytest-cov")
        return 1

    # Default arguments
    pytest_args = ["pytest"]

    # Parse simple command-line arguments
    if "-h" in sys.argv or "--help" in sys.argv:
        print(__doc__)
        return 0

    if "--quick" in sys.argv:
        # Only run basic tests that don't require dependencies
        pytest_args.extend(["tests/test_basic.py", "-v"])
    elif "--all" in sys.argv:
        # Run all tests including those requiring dependencies
        pytest_args.extend(["tests/", "-v"])
    elif "--cov" in sys.argv or "--coverage" in sys.argv:
        # Run with coverage
        pytest_args.extend(
            ["tests/", "--cov=src", "--cov-report=html", "--cov-report=term", "-v"]
        )
    else:
        # Default: run all tests
        pytest_args.extend(["tests/", "-v"])

    # Add verbose if requested
    if "-v" in sys.argv and "-v" not in pytest_args:
        pytest_args.append("-v")

    # Run pytest
    print("=" * 70)
    print("Running Business Data Analyzer Tests")
    print("=" * 70)
    print(f"Command: {' '.join(pytest_args)}")
    print()

    try:
        result = subprocess.run(pytest_args, stderr=subprocess.STDOUT)
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return 1

    if result.returncode == 0:
        print()
        print("=" * 70)
        print("✅ All tests passed!")
        print("=" * 70)
    else:
        print()
        print("=" * 70)
        print("❌ Some tests failed. See output above.")
        print("=" * 70)

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
