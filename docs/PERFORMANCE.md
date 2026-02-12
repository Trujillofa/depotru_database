# Performance Characteristics & Optimization Guide

## Executive Summary

This document provides performance benchmarks, bottleneck analysis, and optimization recommendations for the Business Analyzer system.

**Key Findings:**
- Current system processes 5,000 records in ~25ms for combined analysis
- Individual analyzers are already well-optimized
- The main opportunity is reducing multiple data passes when running combined analysis
- No critical performance issues identified

## Performance Baseline

### Benchmark Environment
- **Date**: 2026-02-12
- **Test Data**: Synthetic records with 10 products, 8 customers
- **Iterations**: 10-50 per test (with 10 warmup runs)
- **Measurement**: Average execution time in milliseconds

### Current Performance Metrics

| Operation | 100 rows | 1,000 rows | 5,000 rows | Scaling |
|-----------|----------|------------|------------|---------|
| **Data Generation** | 0.28ms | 2.80ms | 27.9ms | O(n) |
| **Financial Analysis** | 0.17ms | 1.37ms | 6.54ms | O(n) |
| **Customer Analysis** | 0.14ms | 1.30ms | 6.46ms | O(n) |
| **Product Analysis** | 0.17ms | 1.52ms | 7.54ms | O(n) |
| **Inventory Analysis** | 0.06ms | 0.63ms | 3.14ms | O(n) |
| **Combined Analysis** | 0.58ms | 4.95ms | 24.6ms | O(n) |

### Scaling Characteristics

All analyzers show linear O(n) scaling with data size:
- 10× data → ~10× time (excellent scaling)
- No exponential degradation observed
- Memory usage remains constant (streaming processing)

## Bottleneck Analysis

### Identified Bottlenecks

#### 1. Multiple Data Passes (Combined Analysis)
**Severity**: Medium
**Impact**: When running all 4 analyzers, data is iterated 4 times

```
Current: 4 passes × 5,000 rows = 20,000 row operations
Optimized: 1 pass × 5,000 rows = 5,000 row operations
Potential: 75% reduction in row operations
```

**Evidence**:
- Combined Analysis (5,000 rows): 24.6ms
- Sum of individual analyzers: ~24.2ms
- Overhead: Minimal (<2%)

#### 2. extract_value() Function Calls
**Severity**: Low
**Impact**: Multiple key lookups per field access

```python
# Called for every field access
revenue = extract_value(row, ["TotalMasIva", "PrecioTotal", "precio_total_iva"])
```

**Characteristics**:
- ~3-5 calls per row per analyzer
- String operations for type conversion
- Date detection regex matching

#### 3. No Result Caching
**Severity**: Low
**Impact**: Methods like `calculate_iva_collected()` reprocess data

**Example**:
```python
analyzer.analyze()  # Processes all data
analyzer.calculate_iva_collected()  # Reprocesses all data
```

## Optimization Attempts & Results

### Attempt 1: Cached Analyzer Results
**Approach**: Store intermediate calculations in `_cache` dictionary
**Result**: ❌ **Slower** (-8% to -1%)
**Analysis**: Caching overhead exceeds benefit for single-pass operations

### Attempt 2: Single-Pass Unified Analyzer
**Approach**: Process all metrics in one data iteration
**Result**: ⚠️ **Mixed** (-26% to +18%)
**Analysis**: 
- More efficient for combined analysis
- Overhead of extracting all fields negates benefit
- Better approach: Shared extraction layer

### Attempt 3: Import Path Optimization
**Approach**: Fixed relative imports in analysis modules
**Result**: ✅ **Success**
**Impact**: Enables proper benchmarking and testing

## Recommended Optimizations

### High Priority

#### 1. Smart Combined Analyzer
Create a `CombinedAnalyzer` that shares data extraction:

```python
class CombinedAnalyzer:
    def __init__(self, data):
        self.data = data
        self._extracted = None
    
    def _extract_all(self):
        if self._extracted is None:
            self._extracted = [self._extract_row(row) for row in self.data]
        return self._extracted
    
    def analyze_all(self):
        extracted = self._extract_all()
        return {
            'financial': self._analyze_financial(extracted),
            'customer': self._analyze_customer(extracted),
            'product': self._analyze_product(extracted),
            'inventory': self._analyze_inventory(extracted),
        }
```

**Expected Improvement**: 40-50% faster for combined analysis

### Medium Priority

#### 2. Field Name Normalization
Pre-process data to use consistent field names:

```python
# Instead of multiple key lookups per row
revenue = row.get('total_revenue')  # Normalized name
```

**Expected Improvement**: 10-15% per analyzer

#### 3. Lazy Evaluation for Secondary Methods
Methods like `calculate_iva_collected()` should use cached `analyze()` results:

```python
def calculate_iva_collected(self):
    if 'iva' not in self._cache:
        analysis = self.analyze()  # Use cached result
        self._cache['iva'] = analysis['revenue']['total_with_iva'] - analysis['revenue']['total_without_iva']
    return self._cache['iva']
```

**Expected Improvement**: 60% faster for secondary calculations

### Low Priority

#### 4. NumPy for Large Datasets
For datasets > 100,000 rows, use NumPy arrays:

```python
# Current: Python lists
revenues = [extract_value(row, ['TotalMasIva']) for row in data]
total = sum(revenues)

# Optimized: NumPy arrays
revenues = np.array([extract_value(row, ['TotalMasIva']) for row in data])
total = revenues.sum()  # Vectorized, ~5x faster
```

**Expected Improvement**: 5x for very large datasets (>100k rows)

## Performance Best Practices

### For Users

1. **Use Individual Analyzers When Possible**
   ```python
   # If you only need financial metrics
   from business_analyzer.analysis.financial import FinancialAnalyzer
   # Not: from business_analyzer.analysis import UnifiedAnalyzer
   ```

2. **Process Data in Chunks for Large Datasets**
   ```python
   CHUNK_SIZE = 10000
   for chunk in pd.read_sql(query, conn, chunksize=CHUNK_SIZE):
       analyzer = FinancialAnalyzer(chunk.to_dict('records'))
       results.append(analyzer.analyze())
   ```

3. **Cache Results at Application Level**
   ```python
   @lru_cache(maxsize=128)
   def get_cached_analysis(date_range):
       data = fetch_data(date_range)
       return CombinedAnalyzer(data).analyze_all()
   ```

### For Developers

1. **Profile Before Optimizing**
   ```bash
   python -m cProfile -o profile.stats benchmarks/performance_benchmark.py
   python -m pstats profile.stats
   ```

2. **Maintain O(n) Complexity**
   - All current analyzers are O(n) ✓
   - Avoid nested loops over data
   - Use dictionaries for O(1) lookups

3. **Benchmark After Changes**
   ```bash
   python benchmarks/performance_benchmark.py --export results.json
   ```

## Database Query Performance

### Current Query Structure
```python
# From database.py
query = f"SELECT TOP %s {col_str} FROM [{db_name}].[dbo].[{table_name}] ..."
```

### Optimization Opportunities

1. **Indexed Columns**: Ensure `Fecha`, `TercerosNombres`, `ArticulosNombre` are indexed
2. **Query Caching**: Cache results for identical queries within time window
3. **Connection Pooling**: Reuse database connections (already implemented)

### Query Performance Guidelines

| Records | Expected Time | Optimization |
|---------|---------------|--------------|
| 1,000 | < 100ms | No action needed |
| 10,000 | < 500ms | Add LIMIT clause |
| 100,000 | < 2s | Use indexed columns only |
| 1,000,000 | < 10s | Consider aggregation in SQL |

## Memory Usage

### Current Characteristics
- **Streaming Processing**: ✓ Data processed row-by-row
- **Constant Memory**: O(1) additional memory per analyzer
- **Aggregation Storage**: O(unique customers + unique products)

### Memory Estimates

| Data Size | Approximate Memory |
|-----------|-------------------|
| 1,000 rows | ~2 MB |
| 10,000 rows | ~5 MB |
| 100,000 rows | ~20 MB |
| 1,000,000 rows | ~100 MB |

## Benchmarking Tools

### Running Benchmarks
```bash
# Full benchmark suite
python benchmarks/performance_benchmark.py

# With verbose output
python benchmarks/performance_benchmark.py --verbose

# Export results
python benchmarks/performance_benchmark.py --export results.json
```

### Interpreting Results

**Good Performance**:
- < 1ms for 100 rows
- < 10ms for 1,000 rows
- < 50ms for 5,000 rows

**Needs Attention**:
- > 5ms for 100 rows
- > 50ms for 1,000 rows
- > 200ms for 5,000 rows

## Future Performance Work

### Planned Optimizations
1. [ ] Implement smart combined analyzer (40-50% improvement)
2. [ ] Add field name normalization layer (10-15% improvement)
3. [ ] Implement lazy evaluation for secondary methods (60% improvement)
4. [ ] Add NumPy backend for large datasets (5x improvement)

### Monitoring
- Track performance regression in CI/CD
- Automated benchmarks on PR
- Performance budgets per analyzer

## Conclusion

The Business Analyzer system demonstrates **excellent performance characteristics**:

✅ **Linear scaling** with data size  
✅ **Efficient memory usage** with streaming processing  
✅ **Fast execution** for typical dataset sizes (<10k rows)  
✅ **Well-structured** for further optimization  

**Current Status**: Production-ready performance  
**Optimization Priority**: Low (current performance acceptable)  
**Next Steps**: Implement smart combined analyzer for 40-50% improvement in multi-metric scenarios  

---

*Last Updated: 2026-02-12*  
*Benchmark Version: 1.0*  
*Test Environment: Python 3.11, Linux x86_64*
