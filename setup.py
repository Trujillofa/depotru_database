#!/usr/bin/env python3
"""
Setup configuration for Business Data Analyzer package.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read long description from README
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

# Read requirements
requirements = []
with open("requirements.txt", "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        # Skip comments, empty lines, and installation instructions
        if line and not line.startswith("#"):
            # Extract just the package name and version spec
            if ">=" in line or "==" in line or "~=" in line:
                requirements.append(line)

setup(
    name="business-data-analyzer",
    version="2.0.0",
    author="Business Data Analyzer Team",
    author_email="",
    description="Comprehensive business intelligence platform for hardware store operations with AI-powered natural language SQL queries",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Trujillofa/coding_omarchy",
    project_urls={
        "Bug Tracker": "https://github.com/Trujillofa/coding_omarchy/issues",
        "Documentation": "https://github.com/Trujillofa/coding_omarchy/blob/main/docs/START_HERE.md",
        "Source Code": "https://github.com/Trujillofa/coding_omarchy",
    },
    packages=find_packages(where=".", include=["src", "src.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Topic :: Office/Business",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Natural Language :: English",
        "Natural Language :: Spanish",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
            "mypy>=0.950",
            "isort>=5.12.0",
        ],
        "jupyter": [
            "jupyter>=1.0.0",
            "ipython>=8.0.0",
            "ipykernel>=6.0.0",
        ],
        "all": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
            "mypy>=0.950",
            "isort>=5.12.0",
            "jupyter>=1.0.0",
            "ipython>=8.0.0",
            "ipykernel>=6.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "business-analyzer=src.business_analyzer_combined:main",
            "vanna-grok=src.vanna_grok:main",
            "vanna-chat=src.vanna_chat:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.json", "*.md", "*.txt"],
    },
    zip_safe=False,
    keywords=[
        "business-intelligence",
        "data-analysis",
        "sql",
        "natural-language",
        "ai",
        "grok",
        "vanna",
        "analytics",
        "retail",
        "hardware-store",
    ],
)
