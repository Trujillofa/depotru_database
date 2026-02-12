# Modular Architecture Design for Business Data Analyzer

> **Technical specification for refactoring the 1,690-line monolith into a maintainable, testable modular package.**

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Proposed Package Structure](#proposed-package-structure)
4. [Module Responsibilities](#module-responsibilities)
5. [Public API Design](#public-api-design)
6. [Data Flow Architecture](#data-flow-architecture)
7. [Dependency Graph](#dependency-graph)
8. [Migration Plan](#migration-plan)
9. [Testing Strategy](#testing-strategy)
10. [Risks and Mitigations](#risks-and-mitigations)

---

## Executive Summary

### Problem Statement

The current `business_analyzer_combined.py` is a **1,690-line monolith** that violates the Single Responsibility Principle. It contains:

- Database connection logic mixed with business analytics
- Visualization code intertwined with data processing
- Utility functions scattered throughout
- No clear separation of concerns

### Solution Overview

Transform the monolith into a **modular Python package** with:

- **8 focused modules** (each <300 lines)
- **Clear dependency hierarchy** (no circular dependencies)
- **Clean public API** (minimal surface area)
- **Backward compatibility** (existing CLI continues to work)

### Success Criteria

| Metric | Current | Target |
|--------|---------|--------|
| Lines per file | 1,690 | <300 |
| Test coverage | ~17% | >70% |
| Import time | Unknown | <500ms |
| Circular deps | N/A | 0 |

---

## Current State Analysis

### Monolith Structure

```
business_analyzer_combined.py (1,690 lines)
├── Imports & Setup (lines 1-70)
├── Utility Functions (lines 71-249)
│   ├── DecimalEncoder
│   ├── safe_divide
│   ├── validate_date_format
│   ├── validate_date_range
│   ├── validate_limit
│   ├── validate_sql_identifier
│   └── Navicat decryption
├── BusinessMetricsCalculator Class (lines 251-712)
│   ├── __init__
│   ├── calculate_all_metrics
│   ├── _extract_value
│   ├── calculate_financial_metrics
│   ├── analyze_customers
│   ├── _segment_customer
│   ├── _aggregate_segments
│   ├── analyze_products
│   ├── analyze_categories
│   ├── analyze_inventory
│   ├── analyze_trends
│   ├── analyze_profitability
│   ├── calculate_risk_metrics
│   └── calculate_operational_efficiency
├── Database Functions (lines 715-890)
│   ├── decrypt_navicat_password
│   ├── load_connections
│   └── fetch_banco_datos
├── Recommendation Functions (lines 892-961)
│   ├── generate_recommendations
│   └── generate_magento_strategies
├── Visualization (lines 964-1394)
│   └── generate_visualization_report
├── Output Functions (lines 1397-1459)
│   └── print_detailed_statistics
└── Main Function (lines 1462-1689)
    └── main (CLI entry point)
```

### Identified Concerns

1. **Mixed Responsibilities**: Database, analytics, visualization, and CLI all in one file
2. **Tight Coupling**: `BusinessMetricsCalculator` does everything - hard to test in isolation
3. **Hidden Dependencies**: Uses global `Config`, `logger`, `MATPLOTLIB_AVAILABLE`
4. **No Reusability**: Can't import just the financial metrics without bringing in visualization
5. **Testing Difficulty**: Need to mock database to test analytics

---

## Proposed Package Structure

```
src/business_analyzer/
├── __init__.py                    # Public API exports (~50 lines)
├── cli.py                         # Command-line interface (~150 lines)
│
├── core/                          # Foundation layer
│   ├── __init__.py
│   ├── config.py                  # Configuration management (~150 lines)
│   ├── database.py                # Database connections (~200 lines)
│   └── validation.py              # Input validation (~100 lines)
│
├── analysis/                      # Business logic layer
│   ├── __init__.py
│   ├── base.py                    # Base calculator with _extract_value (~80 lines)
│   ├── financial.py               # Financial metrics (~150 lines)
│   ├── customer.py                # Customer segmentation (~150 lines)
│   ├── product.py                 # Product performance (~150 lines)
│   ├── category.py                # Category analytics (~150 lines)
│   ├── inventory.py               # Inventory velocity (~100 lines)
│   ├── trends.py                  # Trend analysis (~100 lines)
│   ├── profitability.py           # Profitability analysis (~100 lines)
│   ├── risk.py                    # Risk metrics (~80 lines)
│   └── operational.py             # Operational efficiency (~80 lines)
│
├── reporting/                     # Output layer
│   ├── __init__.py
│   ├── recommendations.py         # Business recommendations (~100 lines)
│   └── magento.py                 # Magento strategies (~80 lines)
│
├── viz/                           # Visualization layer
│   ├── __init__.py
│   └── charts.py                  # Matplotlib charts (~250 lines)
│
└── utils/                         # Utilities layer
    ├── __init__.py
    ├── encoding.py                # DecimalEncoder (~50 lines)
    ├── math.py                    # safe_divide (~30 lines)
    └── navicat.py                 # Password decryption (~80 lines)
```

### Module Size Targets

| Module | Target Lines | Rationale |
|--------|--------------|-----------|
| `__init__.py` | <50 | Just exports |
| `cli.py` | <150 | Argument parsing, orchestration |
| `core/*.py` | <200 | Foundation - keep focused |
| `analysis/*.py` | <150 | One concern per file |
| `reporting/*.py` | <100 | Simple output generation |
| `viz/charts.py` | <250 | Complex but isolated |
| `utils/*.py` | <100 | Pure functions |

---

## Module Responsibilities

### Layer 1: Core (Foundation)

#### `core/config.py`
**Responsibility**: Application configuration

**Exports**:
- `Config` - Main configuration class
- `CustomerSegmentation` - Segmentation thresholds
- `InventoryConfig` - Inventory thresholds  
- `ProfitabilityConfig` - Margin thresholds

**Dependencies**: None (bottom layer)

**Migration**: Move from `src/config.py`

---

#### `core/database.py`
**Responsibility**: Database connectivity

**Exports**:
- `fetch_banco_datos(conn_details, limit, start_date, end_date)` - Fetch data with filters
- `load_connections(ncx_file_path)` - Parse Navicat NCX files
- `ConnectionError` - Custom exception

**Dependencies**: `core.config`, `core.validation`, `utils.navicat`

**Migration**: Extract from lines 715-890 of monolith

---

#### `core/validation.py`
**Responsibility**: Input validation and sanitization

**Exports**:
- `validate_date_format(date_str, param_name)` - Date parsing
- `validate_date_range(start_date, end_date)` - Range validation
- `validate_limit(limit)` - Record limit validation
- `validate_sql_identifier(identifier, param_name)` - SQL injection prevention

**Dependencies**: None (pure functions)

**Migration**: Extract from lines 107-229 of monolith

---

### Layer 2: Analysis (Business Logic)

#### `analysis/base.py`
**Responsibility**: Base calculator functionality

**Exports**:
- `BaseCalculator` - Abstract base with `_extract_value()`

**Dependencies**: None (abstract base)

**Migration**: Extract `_extract_value` from line 271 of monolith

---

#### `analysis/financial.py`
**Responsibility**: Financial KPIs

**Exports**:
- `FinancialAnalyzer` - Calculate revenue, costs, profit, margins
- `FinancialMetrics` - TypedDict for return structure

**Dependencies**: `analysis.base`, `utils.math`

**Migration**: Extract from lines 291-352 of monolith

---

#### `analysis/customer.py`
**Responsibility**: Customer segmentation and analytics

**Exports**:
- `CustomerAnalyzer` - Customer analytics
- `CustomerSegment` - Enum for segments (VIP, High Value, etc.)
- `segment_customer(revenue, orders)` - Standalone segmentation

**Dependencies**: `analysis.base`, `core.config.CustomerSegmentation`, `utils.math`

**Migration**: Extract from lines 354-441 of monolith

---

#### `analysis/product.py`
**Responsibility**: Product performance analysis

**Exports**:
- `ProductAnalyzer` - Product analytics
- `ProductMetrics` - TypedDict structure

**Dependencies**: `analysis.base`, `core.config.ProfitabilityConfig`, `utils.math`

**Migration**: Extract from lines 443-501 of monolith

---

#### `analysis/category.py`
**Responsibility**: Category and subcategory analytics

**Exports**:
- `CategoryAnalyzer` - Category performance
- `RiskLevel` - Enum (CRITICAL, HIGH, MEDIUM, LOW)

**Dependencies**: `analysis.base`, `utils.math`

**Migration**: Extract from lines 503-576 of monolith

---

#### `analysis/inventory.py`
**Responsibility**: Inventory velocity tracking

**Exports**:
- `InventoryAnalyzer` - Fast/slow mover identification

**Dependencies**: `analysis.base`, `core.config.InventoryConfig`

**Migration**: Extract from lines 578-619 of monolith

---

#### `analysis/trends.py`
**Responsibility**: Trend and seasonality analysis

**Exports**:
- `TrendAnalyzer` - Monthly trends, category distribution

**Dependencies**: `analysis.base`

**Migration**: Extract from lines 621-651 of monolith

---

#### `analysis/profitability.py`
**Responsibility**: Deep profitability analysis

**Exports**:
- `ProfitabilityAnalyzer` - Category-level profitability

**Dependencies**: `analysis.base`, `utils.math`

**Migration**: Extract from lines 653-689 of monolith

---

#### `analysis/risk.py`
**Responsibility**: Business risk metrics

**Exports**:
- `RiskAnalyzer` - Risk calculations
- `RiskLevel` - Risk classifications

**Dependencies**: `analysis.base`

**Migration**: Extract from lines 691-697 of monolith

---

#### `analysis/operational.py`
**Responsibility**: Operational efficiency metrics

**Exports**:
- `OperationalAnalyzer` - Transaction efficiency

**Dependencies**: `analysis.base`

**Migration**: Extract from lines 699-712 of monolith

---

### Layer 3: Reporting (Output Generation)

#### `reporting/recommendations.py`
**Responsibility**: Generate business recommendations

**Exports**:
- `generate_recommendations(metrics)` - List of recommendation strings

**Dependencies**: None (pure function, takes metrics dict)

**Migration**: Extract from lines 892-930 of monolith

---

#### `reporting/magento.py`
**Responsibility**: Magento e-commerce strategies

**Exports**:
- `generate_magento_strategies(metrics)` - Strategy dictionary

**Dependencies**: None (pure function)

**Migration**: Extract from lines 933-961 of monolith

---

### Layer 4: Visualization (Charts)

#### `viz/charts.py`
**Responsibility**: Matplotlib visualization generation

**Exports**:
- `generate_visualization_report(analysis, output_path)` - PNG report
- `MATPLOTLIB_AVAILABLE` - Boolean flag

**Dependencies**: `core.config` (for OUTPUT_DIR, REPORT_DPI)

**Migration**: Extract from lines 964-1394 of monolith

---

### Layer 5: Utilities (Helpers)

#### `utils/encoding.py`
**Responsibility**: JSON encoding for special types

**Exports**:
- `DecimalEncoder` - JSONEncoder for Decimal/datetime

**Dependencies**: None

**Migration**: Extract from lines 73-79 of monolith

---

#### `utils/math.py`
**Responsibility**: Safe mathematical operations

**Exports**:
- `safe_divide(numerator, denominator, default=0.0)` - Zero-safe division

**Dependencies**: None

**Migration**: Extract from lines 83-103 of monolith

---

#### `utils/navicat.py`
**Responsibility**: Navicat password decryption

**Exports**:
- `decrypt_navicat_password(encrypted_password)` - Decrypt NCX passwords
- `NAVICAT_CIPHER_AVAILABLE` - Boolean flag

**Dependencies**: None (optional external deps)

**Migration**: Extract from lines 715-736 of monolith

---

### Layer 6: CLI (Entry Point)

#### `cli.py`
**Responsibility**: Command-line interface

**Exports**:
- `main()` - CLI entry point

**Dependencies**: ALL other modules (orchestrates them)

**Migration**: Extract from lines 1462-1689 of monolith

---

## Public API Design

### Design Principles

1. **Minimal Surface Area**: Export only what's needed
2. **Backward Compatible**: Existing scripts continue to work
3. **Discoverable**: Clear naming conventions
4. **Typed**: Use type hints throughout

### Public Exports (`__init__.py`)

```python
"""Business Data Analyzer - Modular Business Intelligence Package

This package provides comprehensive business analytics for hardware store operations.
"""

# Version
__version__ = "2.1.0"

# Core - Configuration
from .core.config import Config, CustomerSegmentation, InventoryConfig, ProfitabilityConfig

# Core - Database
from .core.database import fetch_banco_datos, load_connections, ConnectionError

# Core - Validation
from .core.validation import (
    validate_date_format,
    validate_date_range,
    validate_limit,
    validate_sql_identifier,
)

# Analysis - Main Interface
from .analysis.financial import FinancialAnalyzer
from .analysis.customer import CustomerAnalyzer, CustomerSegment, segment_customer
from .analysis.product import ProductAnalyzer
from .analysis.category import CategoryAnalyzer, RiskLevel
from .analysis.inventory import InventoryAnalyzer
from .analysis.trends import TrendAnalyzer
from .analysis.profitability import ProfitabilityAnalyzer

# Reporting
from .reporting.recommendations import generate_recommendations
from .reporting.magento import generate_magento_strategies

# Visualization
from .viz.charts import generate_visualization_report, MATPLOTLIB_AVAILABLE

# Utilities
from .utils.encoding import DecimalEncoder
from .utils.math import safe_divide

# Convenience - Orchestrator (replaces BusinessMetricsCalculator)
from .orchestrator import BusinessAnalyzer

__all__ = [
    # Version
    "__version__",
    # Core
    "Config",
    "CustomerSegmentation",
    "InventoryConfig",
    "ProfitabilityConfig",
    "fetch_banco_datos",
    "load_connections",
    "ConnectionError",
    # Validation
    "validate_date_format",
    "validate_date_range",
    "validate_limit",
    "validate_sql_identifier",
    # Analysis
    "BusinessAnalyzer",  # Main orchestrator
    "FinancialAnalyzer",
    "CustomerAnalyzer",
    "CustomerSegment",
    "segment_customer",
    "ProductAnalyzer",
    "CategoryAnalyzer",
    "RiskLevel",
    "InventoryAnalyzer",
    "TrendAnalyzer",
    "ProfitabilityAnalyzer",
    # Reporting
    "generate_recommendations",
    "generate_magento_strategies",
    # Visualization
    "generate_visualization_report",
    "MATPLOTLIB_AVAILABLE",
    # Utilities
    "DecimalEncoder",
    "safe_divide",
]
```

### Main Orchestrator Class

Replace the monolithic `BusinessMetricsCalculator` with a focused orchestrator:

```python
# orchestrator.py (new file)
"""Main orchestrator that coordinates all analyzers."""

from typing import List, Dict, Any
from .analysis.financial import FinancialAnalyzer
from .analysis.customer import CustomerAnalyzer
from .analysis.product import ProductAnalyzer
from .analysis.category import CategoryAnalyzer
from .analysis.inventory import InventoryAnalyzer
from .analysis.trends import TrendAnalyzer
from .analysis.profitability import ProfitabilityAnalyzer
from .analysis.risk import RiskAnalyzer
from .analysis.operational import OperationalAnalyzer
from .reporting.recommendations import generate_recommendations
from .reporting.magento import generate_magento_strategies


class BusinessAnalyzer:
    """Main business analysis orchestrator.
    
    Coordinates multiple specialized analyzers to provide comprehensive
    business intelligence. Replaces the monolithic BusinessMetricsCalculator.
    
    Example:
        >>> from business_analyzer import BusinessAnalyzer
        >>> analyzer = BusinessAnalyzer(data)
        >>> metrics = analyzer.analyze_all()
    """
    
    def __init__(self, data: List[Dict[str, Any]]):
        self.data = data
        # Initialize specialized analyzers
        self._financial = FinancialAnalyzer(data)
        self._customer = CustomerAnalyzer(data)
        self._product = ProductAnalyzer(data)
        self._category = CategoryAnalyzer(data)
        self._inventory = InventoryAnalyzer(data)
        self._trends = TrendAnalyzer(data)
        self._profitability = ProfitabilityAnalyzer(data)
        self._risk = RiskAnalyzer(data)
        self._operational = OperationalAnalyzer(data)
    
    def analyze_all(self) -> Dict[str, Any]:
        """Run all analyses and return comprehensive metrics."""
        return {
            "financial_metrics": self._financial.calculate(),
            "customer_analytics": self._customer.analyze(),
            "product_analytics": self._product.analyze(),
            "category_analytics": self._category.analyze(),
            "inventory_analytics": self._inventory.analyze(),
            "trend_analytics": self._trends.analyze(),
            "profitability_analytics": self._profitability.analyze(),
            "risk_metrics": self._risk.calculate(),
            "operational_efficiency": self._operational.calculate(),
        }
    
    def analyze_financial(self) -> Dict[str, Any]:
        """Run financial analysis only."""
        return self._financial.calculate()
    
    def analyze_customers(self) -> Dict[str, Any]:
        """Run customer analysis only."""
        return self._customer.analyze()
    
    # ... additional partial analysis methods
```

---

## Data Flow Architecture

### Analysis Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        Data Flow                               │
└─────────────────────────────────────────────────────────────────┘

User Input (CLI)
       │
       ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   cli.py     │────▶│  core/       │────▶│  core/       │
│              │     │  validation  │     │  database    │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                │
                                                ▼
                                         ┌──────────────┐
                                         │  SQL Server  │
                                         └──────┬───────┘
                                                │
                                                ▼
                                         ┌──────────────┐
                                         │  Raw Data    │
                                         │  (List[Dict])│
                                         └──────┬───────┘
                                                │
                    ┌───────────────────────────┼───────────────────────────┐
                    │                           │                           │
                    ▼                           ▼                           ▼
           ┌──────────────┐           ┌──────────────┐           ┌──────────────┐
           │  analysis/   │           │  analysis/   │           │  analysis/   │
           │  financial   │           │  customer    │           │  product     │
           └──────┬───────┘           └──────┬───────┘           └──────┬───────┘
                  │                           │                           │
                  └───────────────────────────┼───────────────────────────┘
                                              │
                                              ▼
                                       ┌──────────────┐
                                       │  analysis/   │
                                       │  base.py     │
                                       │  (_extract)  │
                                       └──────┬───────┘
                                              │
                                              ▼
                                       ┌──────────────┐
                                       │  Metrics     │
                                       │  (Dict)      │
                                       └──────┬───────┘
                                              │
                    ┌──────────────────────────┼──────────────────────────┐
                    │                          │                          │
                    ▼                          ▼                          ▼
           ┌──────────────┐          ┌──────────────┐          ┌──────────────┐
           │  reporting/  │          │  viz/        │          │  reporting/  │
           │recommendations│         │  charts      │          │  magento     │
           └──────────────┘          └──────────────┘          └──────────────┘
```

### Dependency Direction

```
                    ┌─────────┐
                    │  cli.py │  (Entry point - depends on all)
                    └────┬────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
   ┌──────────┐   ┌──────────┐   ┌──────────┐
   │   viz/   │   │reporting/│   │ analysis/│
   │  charts  │   │    *     │   │    *     │
   └────┬─────┘   └────┬─────┘   └────┬─────┘
        │              │              │
        └──────────────┼──────────────┘
                       │
                       ▼
              ┌────────────────┐
              │     core/      │  (Foundation - no deps)
              │ config,        │
              │ database,      │
              │ validation     │
              └────────────────┘
                       │
                       ▼
              ┌────────────────┐
              │     utils/     │  (Pure functions - no deps)
              │ encoding, math │
              └────────────────┘
```

---

## Dependency Graph

### Module Dependencies

```
core/config.py
└── (no dependencies - bottom layer)

core/validation.py
└── (no dependencies)

utils/math.py
└── (no dependencies)

utils/encoding.py
└── (no dependencies)

utils/navicat.py
└── (optional: NavicatCipher, Crypto)

core/database.py
├── core/config.py
├── core/validation.py
└── utils/navicat.py

analysis/base.py
└── (no dependencies - abstract)

analysis/financial.py
├── analysis/base.py
└── utils/math.py

analysis/customer.py
├── analysis/base.py
├── core/config.py (CustomerSegmentation)
└── utils/math.py

analysis/product.py
├── analysis/base.py
├── core/config.py (ProfitabilityConfig)
└── utils/math.py

analysis/category.py
├── analysis/base.py
└── utils/math.py

analysis/inventory.py
├── analysis/base.py
└── core/config.py (InventoryConfig)

analysis/trends.py
├── analysis/base.py
└── (no other deps)

analysis/profitability.py
├── analysis/base.py
└── utils/math.py

analysis/risk.py
├── analysis/base.py
└── (no other deps)

analysis/operational.py
├── analysis/base.py
└── (no other deps)

reporting/recommendations.py
└── (no dependencies - pure function)

reporting/magento.py
└── (no dependencies - pure function)

viz/charts.py
├── core/config.py (OUTPUT_DIR, REPORT_DPI)
└── matplotlib (optional)

orchestrator.py (BusinessAnalyzer)
├── analysis/financial
├── analysis/customer
├── analysis/product
├── analysis/category
├── analysis/inventory
├── analysis/trends
├── analysis/profitability
├── analysis/risk
├── analysis/operational
├── reporting/recommendations
└── reporting/magento

cli.py
├── core/config.py
├── core/database.py
├── core/validation.py
├── orchestrator.py (BusinessAnalyzer)
├── viz/charts.py
├── utils/encoding.py
└── reporting/* (via orchestrator)
```

### Circular Dependency Check

**Result**: ✅ NO CIRCULAR DEPENDENCIES

All dependencies flow downward:
- `cli` → `orchestrator` → `analysis` → `core`/`utils`
- `viz` → `core`
- `reporting` → (no deps, pure functions)

---

## Migration Plan

### Phase 1: Foundation (Week 1)

**Goal**: Create core infrastructure

1. **Create package structure**
   ```bash
   mkdir -p src/business_analyzer/{core,analysis,reporting,viz,utils}
   touch src/business_analyzer/__init__.py
   touch src/business_analyzer/{core,analysis,reporting,viz,utils}/__init__.py
   ```

2. **Migrate config** (Task 7.1)
   - Copy `src/config.py` → `src/business_analyzer/core/config.py`
   - Update imports in existing files to use new location
   - Keep backward compatibility shim in old location

3. **Create utils** (Task 7.2)
   - Extract `DecimalEncoder` → `utils/encoding.py`
   - Extract `safe_divide` → `utils/math.py`
   - Extract Navicat functions → `utils/navicat.py`

4. **Create validation** (Task 7.3)
   - Extract validation functions → `core/validation.py`

### Phase 2: Database Layer (Week 1-2)

**Goal**: Isolate database connectivity

1. **Migrate database functions** (Task 7.4)
   - Extract `fetch_banco_datos`, `load_connections` → `core/database.py`
   - Ensure proper error handling
   - Add connection pooling (future enhancement)

### Phase 3: Analysis Layer (Week 2-3)

**Goal**: Modularize business logic

1. **Create base analyzer** (Task 8.1)
   - Create `analysis/base.py` with `BaseCalculator`
   - Implement `_extract_value` method

2. **Migrate analyzers** (Tasks 8.2-8.10)
   - Extract each analyzer to separate file
   - Ensure each has <150 lines
   - Add type hints

3. **Create orchestrator** (Task 8.11)
   - Create `orchestrator.py` with `BusinessAnalyzer` class
   - Replace `BusinessMetricsCalculator`

### Phase 4: Reporting & Viz (Week 3)

**Goal**: Isolate output generation

1. **Migrate reporting** (Task 9.1)
   - Extract `generate_recommendations` → `reporting/recommendations.py`
   - Extract `generate_magento_strategies` → `reporting/magento.py`

2. **Migrate visualization** (Task 9.2)
   - Extract `generate_visualization_report` → `viz/charts.py`
   - Keep matplotlib as optional dependency

### Phase 5: CLI & Integration (Week 4)

**Goal**: Complete the migration

1. **Create new CLI** (Task 9.3)
   - Create `cli.py` with refactored `main()`
   - Use new modular imports

2. **Update entry points** (Task 9.4)
   - Update `pyproject.toml` console scripts
   - Ensure backward compatibility

3. **Remove monolith** (Task 9.5)
   - Delete `business_analyzer_combined.py`
   - Update all documentation

### Phase 6: Testing & Validation (Week 4-5)

**Goal**: Ensure quality

1. **Update tests** (Task 10.1)
   - Migrate existing tests to new structure
   - Add unit tests for each module
   - Target >70% coverage

2. **Integration testing** (Task 10.2)
   - Test CLI with real database
   - Verify all outputs match previous version

### Migration Checklist

| Task | Description | Lines | Dependencies | Risk |
|------|-------------|-------|--------------|------|
| 7.1 | Migrate config | 142 | None | Low |
| 7.2 | Create utils | 160 | None | Low |
| 7.3 | Create validation | 122 | None | Low |
| 7.4 | Migrate database | 175 | 7.1, 7.2, 7.3 | Medium |
| 8.1 | Create base analyzer | 80 | None | Low |
| 8.2 | Migrate financial | 62 | 8.1, 7.2 | Low |
| 8.3 | Migrate customer | 88 | 8.1, 7.1, 7.2 | Low |
| 8.4 | Migrate product | 59 | 8.1, 7.1, 7.2 | Low |
| 8.5 | Migrate category | 74 | 8.1, 7.2 | Low |
| 8.6 | Migrate inventory | 42 | 8.1, 7.1 | Low |
| 8.7 | Migrate trends | 31 | 8.1 | Low |
| 8.8 | Migrate profitability | 37 | 8.1, 7.2 | Low |
| 8.9 | Migrate risk | 7 | 8.1 | Low |
| 8.10 | Migrate operational | 14 | 8.1 | Low |
| 8.11 | Create orchestrator | 80 | 8.2-8.10 | Medium |
| 9.1 | Migrate reporting | 70 | None | Low |
| 9.2 | Migrate visualization | 431 | 7.1 | Medium |
| 9.3 | Create new CLI | 228 | All | Medium |
| 9.4 | Update entry points | 10 | 9.3 | Low |
| 9.5 | Remove monolith | -1690 | All | High |
| 10.1 | Update tests | ~500 | All | Medium |
| 10.2 | Integration testing | - | All | Medium |

---

## Testing Strategy

### Unit Testing

Each module gets dedicated tests:

```
tests/
├── conftest.py                    # Shared fixtures
├── test_core/
│   ├── test_config.py
│   ├── test_database.py
│   └── test_validation.py
├── test_analysis/
│   ├── test_financial.py
│   ├── test_customer.py
│   ├── test_product.py
│   ├── test_category.py
│   ├── test_inventory.py
│   ├── test_trends.py
│   ├── test_profitability.py
│   ├── test_risk.py
│   └── test_operational.py
├── test_reporting/
│   ├── test_recommendations.py
│   └── test_magento.py
├── test_viz/
│   └── test_charts.py
├── test_utils/
│   ├── test_encoding.py
│   ├── test_math.py
│   └── test_navicat.py
└── test_integration/
    ├── test_cli.py
    └── test_end_to_end.py
```

### Test Patterns

#### Analyzer Tests

```python
# tests/test_analysis/test_financial.py
import pytest
from business_analyzer.analysis.financial import FinancialAnalyzer


class TestFinancialAnalyzer:
    """Test financial metrics calculation."""
    
    @pytest.fixture
    def sample_data(self):
        return [
            {
                "TotalMasIva": 1000.0,
                "TotalSinIva": 840.0,
                "ValorCosto": 500.0,
                "Cantidad": 2,
            },
            {
                "TotalMasIva": 2000.0,
                "TotalSinIva": 1680.0,
                "ValorCosto": 1000.0,
                "Cantidad": 4,
            },
        ]
    
    def test_calculate_revenue(self, sample_data):
        analyzer = FinancialAnalyzer(sample_data)
        result = analyzer.calculate()
        
        assert result["revenue"]["total_with_iva"] == 3000.0
        assert result["revenue"]["total_without_iva"] == 2520.0
    
    def test_calculate_profit(self, sample_data):
        analyzer = FinancialAnalyzer(sample_data)
        result = analyzer.calculate()
        
        expected_profit = 2520.0 - 1500.0  # revenue - cost
        assert result["profit"]["gross_profit"] == expected_profit
```

#### Database Tests (Mocked)

```python
# tests/test_core/test_database.py
import pytest
from unittest.mock import Mock, patch
from business_analyzer.core.database import fetch_banco_datos


class TestDatabase:
    """Test database connectivity with mocked connections."""
    
    @pytest.fixture
    def conn_details(self):
        return {
            "Host": "test-server",
            "Port": 1433,
            "UserName": "test-user",
            "Password": "test-pass",
            "Database": "TestDB",
        }
    
    @patch("business_analyzer.core.database.pymssql")
    def test_fetch_banco_datos_success(self, mock_pymssql, conn_details):
        # Setup mock
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = {"test": 1}
        mock_cursor.__iter__ = Mock(return_value=iter([{"col": "val"}]))
        mock_conn.cursor.return_value = mock_cursor
        mock_pymssql.connect.return_value = mock_conn
        
        # Execute
        result = fetch_banco_datos(conn_details, limit=10)
        
        # Assert
        assert len(result) == 1
        mock_pymssql.connect.assert_called_once()
        mock_conn.close.assert_called_once()  # Ensure cleanup
```

### Coverage Targets

| Module | Target Coverage | Priority |
|--------|-----------------|----------|
| `core/validation.py` | 95% | Critical |
| `utils/math.py` | 100% | Critical |
| `analysis/*.py` | 80% | High |
| `core/database.py` | 70% | High |
| `reporting/*.py` | 75% | Medium |
| `viz/charts.py` | 60% | Medium |
| `cli.py` | 70% | Medium |

---

## Risks and Mitigations

### Risk 1: Breaking Changes

**Risk**: Existing scripts using `business_analyzer_combined.py` will break

**Mitigation**:
- Keep backward compatibility shim:
  ```python
  # business_analyzer_combined.py (temporary shim)
  """Backward compatibility shim - redirects to new package."""
  import warnings
  warnings.warn(
      "business_analyzer_combined.py is deprecated. "
      "Use 'from business_analyzer import BusinessAnalyzer' instead.",
      DeprecationWarning,
      stacklevel=2
  )
  from business_analyzer import BusinessAnalyzer, main
  from business_analyzer.core.database import fetch_banco_datos
  # ... etc
  ```
- Update all internal references before removing shim
- Provide migration guide in release notes

### Risk 2: Import Performance

**Risk**: Modular structure may slow down imports

**Mitigation**:
- Use lazy imports in `__init__.py`
- Profile import time: `python -X importtime -c "import business_analyzer"`
- Target: <500ms for full import

### Risk 3: Circular Dependencies

**Risk**: Refactoring may introduce circular imports

**Mitigation**:
- Use dependency graph tool: `pydeps src/business_analyzer`
- Keep dependency direction: cli → analysis → core → utils
- Use TYPE_CHECKING for type hints if needed

### Risk 4: Test Coverage Gaps

**Risk**: New modules may lack tests

**Mitigation**:
- Require tests for each new module
- Use pytest-cov to enforce coverage thresholds
- Block PRs that decrease coverage

### Risk 5: Database Connection Issues

**Risk**: Refactored database code may have connection leaks

**Mitigation**:
- Always use context managers:
  ```python
  with DatabaseConnection(conn_details) as conn:
      data = conn.fetch_data()
  # Auto-closes here
  ```
- Add connection cleanup tests
- Monitor connection pool in production

### Risk 6: Visualization Dependencies

**Risk**: matplotlib optional dependency handling

**Mitigation**:
- Keep `MATPLOTLIB_AVAILABLE` flag pattern
- Graceful degradation when not installed
- Clear error messages: "Install with: pip install matplotlib"

---

## Appendix A: File Size Comparison

### Before (Monolith)

| File | Lines | Responsibilities |
|------|-------|------------------|
| `business_analyzer_combined.py` | 1,690 | Everything |

### After (Modular)

| File | Lines | Responsibility |
|------|-------|--------------|
| `__init__.py` | 50 | Public API |
| `cli.py` | 150 | CLI entry point |
| `orchestrator.py` | 80 | Main coordinator |
| `core/config.py` | 142 | Configuration |
| `core/database.py` | 175 | Database |
| `core/validation.py` | 122 | Validation |
| `analysis/base.py` | 80 | Base class |
| `analysis/financial.py` | 62 | Financial metrics |
| `analysis/customer.py` | 88 | Customer analytics |
| `analysis/product.py` | 59 | Product analytics |
| `analysis/category.py` | 74 | Category analytics |
| `analysis/inventory.py` | 42 | Inventory |
| `analysis/trends.py` | 31 | Trends |
| `analysis/profitability.py` | 37 | Profitability |
| `analysis/risk.py` | 7 | Risk |
| `analysis/operational.py` | 14 | Operational |
| `reporting/recommendations.py` | 39 | Recommendations |
| `reporting/magento.py` | 29 | Magento |
| `viz/charts.py` | 431 | Visualization |
| `utils/encoding.py` | 7 | JSON encoding |
| `utils/math.py` | 21 | Math helpers |
| `utils/navicat.py` | 22 | Navicat |
| **Total** | **1,758** | **21 files** |

**Net change**: +68 lines (due to imports, docstrings, `__init__.py` files)
**Average per file**: 84 lines (vs 1,690 before)
**Largest file**: `viz/charts.py` at 431 lines (acceptable for visualization)

---

## Appendix B: Import Examples

### Basic Usage

```python
# Import the main orchestrator
from business_analyzer import BusinessAnalyzer

# Load data (using new modular API)
from business_analyzer import fetch_banco_datos, load_connections

connections = load_connections("connections.ncx")
data = fetch_banco_datos(connections[0], limit=1000)

# Analyze
analyzer = BusinessAnalyzer(data)
metrics = analyzer.analyze_all()
```

### Specific Analysis

```python
# Import just what you need
from business_analyzer.analysis.financial import FinancialAnalyzer
from business_analyzer.analysis.customer import CustomerAnalyzer

financial = FinancialAnalyzer(data).calculate()
customers = CustomerAnalyzer(data).analyze()
```

### Validation

```python
from business_analyzer import validate_date_range, validate_limit

# Validate before fetching
try:
    validate_date_range("2025-01-01", "2025-12-31")
    validate_limit(5000)
    data = fetch_banco_datos(conn, limit=5000, 
                            start_date="2025-01-01", 
                            end_date="2025-12-31")
except ValueError as e:
    print(f"Invalid input: {e}")
```

### Utilities

```python
from business_analyzer import safe_divide, DecimalEncoder
import json

# Safe division
margin = safe_divide(profit, revenue, default=0.0)

# JSON encoding
json_str = json.dumps(data, cls=DecimalEncoder)
```

---

## Appendix C: Migration Script

```python
#!/usr/bin/env python3
"""Migration helper for business_analyzer_combined.py users."""

import sys
import re


def migrate_imports(file_path: str) -> str:
    """Update imports from old to new structure."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Old import patterns → New import patterns
    replacements = [
        # BusinessMetricsCalculator
        (
            r'from business_analyzer_combined import BusinessMetricsCalculator',
            'from business_analyzer import BusinessAnalyzer'
        ),
        (
            r'from business_analyzer_combined import fetch_banco_datos',
            'from business_analyzer import fetch_banco_datos'
        ),
        (
            r'from business_analyzer_combined import load_connections',
            'from business_analyzer import load_connections'
        ),
        (
            r'from business_analyzer_combined import generate_recommendations',
            'from business_analyzer import generate_recommendations'
        ),
        (
            r'from business_analyzer_combined import generate_visualization_report',
            'from business_analyzer import generate_visualization_report'
        ),
        (
            r'from business_analyzer_combined import DecimalEncoder',
            'from business_analyzer import DecimalEncoder'
        ),
        (
            r'from business_analyzer_combined import safe_divide',
            'from business_analyzer import safe_divide'
        ),
        (
            r'from business_analyzer_combined import validate_date_format',
            'from business_analyzer import validate_date_format'
        ),
        (
            r'from business_analyzer_combined import validate_date_range',
            'from business_analyzer import validate_date_range'
        ),
        (
            r'from business_analyzer_combined import validate_limit',
            'from business_analyzer import validate_limit'
        ),
        (
            r'from business_analyzer_combined import validate_sql_identifier',
            'from business_analyzer import validate_sql_identifier'
        ),
        # Config imports
        (
            r'from config import Config',
            'from business_analyzer import Config'
        ),
        (
            r'from config import CustomerSegmentation',
            'from business_analyzer import CustomerSegmentation'
        ),
        (
            r'from config import InventoryConfig',
            'from business_analyzer import InventoryConfig'
        ),
        (
            r'from config import ProfitabilityConfig',
            'from business_analyzer import ProfitabilityConfig'
        ),
    ]
    
    for old, new in replacements:
        content = re.sub(old, new, content)
    
    return content


def main():
    if len(sys.argv) < 2:
        print("Usage: python migrate.py <file_to_migrate.py>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    new_content = migrate_imports(file_path)
    
    # Write to new file
    new_path = file_path.replace('.py', '_migrated.py')
    with open(new_path, 'w') as f:
        f.write(new_content)
    
    print(f"✅ Migrated: {file_path} → {new_path}")
    print("Review the changes and test before replacing the original.")


if __name__ == "__main__":
    main()
```

---

**Document Version**: 1.0.0  
**Last Updated**: 2026-02-12  
**Author**: Architecture Design Task  
**Status**: Ready for Implementation
