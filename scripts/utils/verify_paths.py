#!/usr/bin/env python3
"""
Verification script to ensure all file paths are correct after reorganization.
Run from repository root: python scripts/utils/verify_paths.py
"""
import os
import sys

def check_path(path, description):
    """Check if a path exists and print result."""
    exists = os.path.exists(path)
    symbol = "✅" if exists else "❌"
    print(f"{symbol} {description}: {path}")
    return exists

def main():
    print("Repository Organization Verification")
    print("=" * 60)
    print(f"Current directory: {os.getcwd()}")
    print()
    
    all_ok = True
    
    # Check directory structure
    print("Directory Structure:")
    print("-" * 60)
    all_ok &= check_path("scripts/analysis", "Analysis scripts directory")
    all_ok &= check_path("scripts/reports", "Report scripts directory")
    all_ok &= check_path("scripts/utils", "Utility scripts directory")
    all_ok &= check_path("reports", "Reports directory")
    all_ok &= check_path("reports/data", "Reports data directory")
    all_ok &= check_path("docs/ai-context", "AI context docs directory")
    print()
    
    # Check key scripts
    print("Analysis Scripts:")
    print("-" * 60)
    all_ok &= check_path("scripts/analysis/sika_analysis.py", "SIKA analysis")
    all_ok &= check_path("scripts/analysis/run_analysis.py", "General analysis")
    all_ok &= check_path("scripts/analysis/investigate_deposito.py", "Investigation")
    all_ok &= check_path("scripts/analysis/check_document_codes.py", "Document check")
    print()
    
    # Check report generators
    print("Report Generators:")
    print("-" * 60)
    all_ok &= check_path("scripts/reports/generate_sika_report.py", "English SIKA report")
    all_ok &= check_path("scripts/reports/generate_sika_report_es.py", "Spanish SIKA report")
    all_ok &= check_path("scripts/reports/generate_report.py", "General report")
    print()
    
    # Check utility scripts
    print("Utility Scripts:")
    print("-" * 60)
    all_ok &= check_path("scripts/utils/test_connection.py", "Connection test")
    all_ok &= check_path("scripts/utils/test_vanna.py", "Vanna test")
    all_ok &= check_path("scripts/utils/run_tests.py", "Test runner")
    print()
    
    # Check reports
    print("Generated Reports:")
    print("-" * 60)
    all_ok &= check_path("reports/ANALYSIS_REPORT.md", "General analysis report")
    all_ok &= check_path("reports/SIKA_ANALYSIS_REPORT.md", "SIKA report (English)")
    all_ok &= check_path("reports/REPORTE_SIKA_ESPANOL.md", "SIKA report (Spanish)")
    all_ok &= check_path("reports/data/analysis_report.json", "Analysis JSON data")
    all_ok &= check_path("reports/data/sika_analysis_report.json", "SIKA JSON data")
    print()
    
    # Check AI context docs
    print("AI Context Documentation:")
    print("-" * 60)
    all_ok &= check_path("docs/ai-context/claude.md", "Claude documentation")
    all_ok &= check_path("docs/ai-context/claude_depotru.md", "Claude Depotru reference")
    all_ok &= check_path("docs/ai-context/grok_depotru.md", "Grok reference")
    print()
    
    # Check README files
    print("Documentation:")
    print("-" * 60)
    all_ok &= check_path("scripts/README.md", "Scripts README")
    all_ok &= check_path("reports/README.md", "Reports README")
    all_ok &= check_path("docs/ai-context/README.md", "AI context README")
    all_ok &= check_path("README.md", "Main README")
    print()
    
    # Summary
    print("=" * 60)
    if all_ok:
        print("✅ All paths verified successfully!")
        print("\nRepository is properly organized. You can now run:")
        print("  - Analysis: python scripts/analysis/sika_analysis.py")
        print("  - Reports:  python scripts/reports/generate_sika_report.py")
        print("  - Tests:    python scripts/utils/test_connection.py")
        return 0
    else:
        print("❌ Some paths are missing or incorrect.")
        print("Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
