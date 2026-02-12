"""
AI package test suite.

Run with: python -m pytest tests/ai/ -v
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))
