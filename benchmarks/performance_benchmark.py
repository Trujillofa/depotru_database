"""
Performance Benchmark Suite for Business Analyzer

Measures execution times for critical operations:
- Database queries
- Analysis calculations
- Data processing

Usage:
    python benchmarks/performance_benchmark.py
    python benchmarks/performance_benchmark.py --verbose
"""

import time
import random
import statistics
from typing import Dict, List, Any, Callable
from dataclasses import dataclass
from datetime import datetime

# Try to import analysis modules
try:
    import sys
    from pathlib import Path

    # Add src to path for imports
    src_path = Path(__file__).parent.parent / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    # Import original analysis modules
    from business_analyzer.analysis.financial import FinancialAnalyzer
    from business_analyzer.analysis.customer import CustomerAnalyzer
    from business_analyzer.analysis.product import ProductAnalyzer
    from business_analyzer.analysis.inventory import InventoryAnalyzer

    # Import optimized versions
    from business_analyzer.analysis.financial_optimized import (
        OptimizedFinancialAnalyzer,
    )
    from business_analyzer.analysis.customer_optimized import OptimizedCustomerAnalyzer
    from business_analyzer.analysis.unified import UnifiedAnalyzer

    ANALYSIS_AVAILABLE = True
    OPTIMIZED_AVAILABLE = True
    UNIFIED_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Analysis modules not available: {e}")
    import traceback

    traceback.print_exc()
    ANALYSIS_AVAILABLE = False
    OPTIMIZED_AVAILABLE = False


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""

    name: str
    execution_time_ms: float
    iterations: int
    avg_time_ms: float
    min_time_ms: float
    max_time_ms: float
    std_dev_ms: float


class PerformanceBenchmark:
    """Benchmark suite for business analyzer operations."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: List[BenchmarkResult] = []

    def log(self, message: str):
        """Print message if verbose mode enabled."""
        if self.verbose:
            print(f"  {message}")

    def run_benchmark(
        self, name: str, func: Callable, iterations: int = 100, warmup: int = 10
    ) -> BenchmarkResult:
        """Run a benchmark function multiple times and collect statistics."""
        print(f"\n📊 Benchmarking: {name}")
        print(f"   Iterations: {iterations} (warmup: {warmup})")

        # Warmup runs
        self.log(f"Running {warmup} warmup iterations...")
        for _ in range(warmup):
            func()

        # Actual benchmark runs
        self.log(f"Running {iterations} benchmark iterations...")
        times = []
        for i in range(iterations):
            start = time.perf_counter()
            func()
            end = time.perf_counter()
            times.append((end - start) * 1000)  # Convert to milliseconds

        # Calculate statistics
        avg_time = statistics.mean(times)
        min_time = min(times)
        max_time = max(times)
        std_dev = statistics.stdev(times) if len(times) > 1 else 0.0
        total_time = sum(times)

        result = BenchmarkResult(
            name=name,
            execution_time_ms=total_time,
            iterations=iterations,
            avg_time_ms=avg_time,
            min_time_ms=min_time,
            max_time_ms=max_time,
            std_dev_ms=std_dev,
        )

        self.results.append(result)

        print(
            f"   ✓ Avg: {avg_time:.3f}ms | Min: {min_time:.3f}ms | Max: {max_time:.3f}ms | StdDev: {std_dev:.3f}ms"
        )

        return result

    def generate_test_data(self, size: int) -> List[Dict[str, Any]]:
        """Generate synthetic test data of specified size."""
        products = [
            "Hammer",
            "Screwdriver",
            "Wrench",
            "Drill",
            "Saw",
            "Nails",
            "Screws",
            "Paint",
            "Brush",
            "Tape Measure",
        ]
        customers = [
            "John Doe",
            "Jane Smith",
            "Bob Johnson",
            "Alice Brown",
            "Charlie Wilson",
            "Diana Davis",
            "Eve Miller",
            "Frank Garcia",
        ]

        data = []
        for i in range(size):
            row = {
                "TercerosNombres": random.choice(customers),
                "ArticulosNombre": random.choice(products),
                "ArticulosCodigo": f"SKU-{random.randint(1000, 9999)}",
                "TotalMasIva": round(random.uniform(100, 5000), 2),
                "TotalSinIva": round(random.uniform(90, 4500), 2),
                "ValorCosto": round(random.uniform(50, 3000), 2),
                "Cantidad": random.randint(1, 50),
                "Fecha": f"2025-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
            }
            data.append(row)

        return data

    def benchmark_data_generation(self):
        """Benchmark test data generation."""
        sizes = [100, 1000, 10000]

        for size in sizes:

            def generate():
                return self.generate_test_data(size)

            self.run_benchmark(
                f"Data Generation ({size:,} rows)",
                generate,
                iterations=10 if size >= 10000 else 50,
            )

    def benchmark_financial_analysis(self):
        """Benchmark financial analysis operations."""
        if not ANALYSIS_AVAILABLE:
            print("\n⚠️  Skipping financial analysis benchmarks (modules not available)")
            return

        sizes = [100, 1000, 5000]

        for size in sizes:
            data = self.generate_test_data(size)
            analyzer = FinancialAnalyzer(data)

            def analyze():
                return analyzer.analyze()

            self.run_benchmark(
                f"Financial Analysis ({size:,} rows)",
                analyze,
                iterations=20 if size <= 1000 else 5,
            )

            # Benchmark additional methods
            def calculate_iva():
                return analyzer.calculate_iva_collected()

            self.run_benchmark(
                f"IVA Calculation ({size:,} rows)",
                calculate_iva,
                iterations=20 if size <= 1000 else 5,
            )

    def benchmark_customer_analysis(self):
        """Benchmark customer analysis operations."""
        if not ANALYSIS_AVAILABLE:
            print("\n⚠️  Skipping customer analysis benchmarks (modules not available)")
            return

        sizes = [100, 1000, 5000]

        for size in sizes:
            data = self.generate_test_data(size)
            analyzer = CustomerAnalyzer(data)

            def analyze():
                return analyzer.analyze()

            self.run_benchmark(
                f"Customer Analysis ({size:,} rows)",
                analyze,
                iterations=20 if size <= 1000 else 5,
            )

    def benchmark_product_analysis(self):
        """Benchmark product analysis operations."""
        if not ANALYSIS_AVAILABLE:
            print("\n⚠️  Skipping product analysis benchmarks (modules not available)")
            return

        sizes = [100, 1000, 5000]

        for size in sizes:
            data = self.generate_test_data(size)
            analyzer = ProductAnalyzer(data)

            def analyze():
                return analyzer.analyze()

            self.run_benchmark(
                f"Product Analysis ({size:,} rows)",
                analyze,
                iterations=20 if size <= 1000 else 5,
            )

    def benchmark_inventory_analysis(self):
        """Benchmark inventory analysis operations."""
        if not ANALYSIS_AVAILABLE:
            print("\n⚠️  Skipping inventory analysis benchmarks (modules not available)")
            return

        sizes = [100, 1000, 5000]

        for size in sizes:
            data = self.generate_test_data(size)
            analyzer = InventoryAnalyzer(data)

            def analyze():
                return analyzer.analyze()

            self.run_benchmark(
                f"Inventory Analysis ({size:,} rows)",
                analyze,
                iterations=20 if size <= 1000 else 5,
            )

            # Benchmark summary method
            def summary():
                return analyzer.get_inventory_summary()

            self.run_benchmark(
                f"Inventory Summary ({size:,} rows)",
                summary,
                iterations=20 if size <= 1000 else 5,
            )

    def benchmark_combined_analysis(self):
        """Benchmark running all analyzers together."""
        if not ANALYSIS_AVAILABLE:
            print("\n⚠️  Skipping combined analysis benchmarks (modules not available)")
            return

        sizes = [100, 1000, 5000]

        for size in sizes:
            data = self.generate_test_data(size)

            def combined():
                financial = FinancialAnalyzer(data)
                customer = CustomerAnalyzer(data)
                product = ProductAnalyzer(data)
                inventory = InventoryAnalyzer(data)

                return {
                    "financial": financial.analyze(),
                    "customer": customer.analyze(),
                    "product": product.analyze(),
                    "inventory": inventory.analyze(),
                }

            self.run_benchmark(
                f"Combined Analysis ({size:,} rows)",
                combined,
                iterations=10 if size <= 1000 else 3,
            )

    def benchmark_optimization_comparison(self):
        """Compare original vs optimized implementations."""
        if not ANALYSIS_AVAILABLE or not OPTIMIZED_AVAILABLE:
            print("\n⚠️  Skipping optimization comparison (modules not available)")
            return

        print("\n" + "=" * 80)
        print("OPTIMIZATION COMPARISON BENCHMARKS")
        print("=" * 80)

        sizes = [1000, 5000]

        for size in sizes:
            data = self.generate_test_data(size)

            # Original Financial Analyzer
            def original_financial():
                analyzer = FinancialAnalyzer(data)
                return analyzer.analyze()

            result_orig = self.run_benchmark(
                f"Original Financial ({size:,} rows)",
                original_financial,
                iterations=10 if size <= 1000 else 5,
            )

            # Optimized Financial Analyzer
            def optimized_financial():
                analyzer = OptimizedFinancialAnalyzer(data)
                return analyzer.analyze()

            result_opt = self.run_benchmark(
                f"Optimized Financial ({size:,} rows)",
                optimized_financial,
                iterations=10 if size <= 1000 else 5,
            )

            # Calculate improvement
            improvement = (
                (result_orig.avg_time_ms - result_opt.avg_time_ms)
                / result_orig.avg_time_ms
            ) * 100
            print(f"   📈 Improvement: {improvement:.1f}% faster")

            # Original Customer Analyzer
            def original_customer():
                analyzer = CustomerAnalyzer(data)
                return analyzer.analyze()

            result_orig_cust = self.run_benchmark(
                f"Original Customer ({size:,} rows)",
                original_customer,
                iterations=10 if size <= 1000 else 5,
            )

            # Optimized Customer Analyzer
            def optimized_customer():
                analyzer = OptimizedCustomerAnalyzer(data)
                return analyzer.analyze()

            result_opt_cust = self.run_benchmark(
                f"Optimized Customer ({size:,} rows)",
                optimized_customer,
                iterations=10 if size <= 1000 else 5,
            )

            # Calculate improvement
            improvement_cust = (
                (result_orig_cust.avg_time_ms - result_opt_cust.avg_time_ms)
                / result_orig_cust.avg_time_ms
            ) * 100
            print(f"   📈 Improvement: {improvement_cust:.1f}% faster")

            # Unified Analyzer - single pass for all metrics
            def unified_all():
                analyzer = UnifiedAnalyzer(data)
                return analyzer.analyze_all()

            result_unified = self.run_benchmark(
                f"Unified Analyzer ({size:,} rows)",
                unified_all,
                iterations=10 if size <= 1000 else 5,
            )

            # Calculate improvement vs running 4 separate analyzers
            combined_time = result_orig.avg_time_ms + result_orig_cust.avg_time_ms
            improvement_unified = (
                (combined_time - result_unified.avg_time_ms) / combined_time
            ) * 100
            print(f"   📈 Unified vs Separate: {improvement_unified:.1f}% faster")

    def print_summary(self):
        """Print benchmark summary report."""
        print("\n" + "=" * 80)
        print("PERFORMANCE BENCHMARK SUMMARY")
        print("=" * 80)
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total benchmarks: {len(self.results)}")
        print("-" * 80)

        # Group by category
        categories = {}
        for result in self.results:
            category = result.name.split("(")[0].strip()
            if category not in categories:
                categories[category] = []
            categories[category].append(result)

        for category, results in sorted(categories.items()):
            print(f"\n{category}:")
            print("-" * 60)
            for result in results:
                size_part = (
                    result.name[result.name.find("(") : result.name.find(")") + 1]
                    if "(" in result.name
                    else ""
                )
                print(
                    f"  {size_part:20s} Avg: {result.avg_time_ms:8.3f}ms  "
                    f"(min: {result.min_time_ms:6.3f}, max: {result.max_time_ms:7.3f})"
                )

        print("\n" + "=" * 80)

        # Find slowest operations
        print("\nSLOWEST OPERATIONS:")
        sorted_results = sorted(
            self.results, key=lambda x: x.avg_time_ms, reverse=True
        )[:5]
        for i, result in enumerate(sorted_results, 1):
            print(f"  {i}. {result.name}: {result.avg_time_ms:.3f}ms avg")

        print("\n" + "=" * 80)

    def export_results(self, filename: str = "benchmark_results.json"):
        """Export results to JSON file."""
        import json

        data = {
            "timestamp": datetime.now().isoformat(),
            "total_benchmarks": len(self.results),
            "results": [
                {
                    "name": r.name,
                    "execution_time_ms": r.execution_time_ms,
                    "iterations": r.iterations,
                    "avg_time_ms": r.avg_time_ms,
                    "min_time_ms": r.min_time_ms,
                    "max_time_ms": r.max_time_ms,
                    "std_dev_ms": r.std_dev_ms,
                }
                for r in self.results
            ],
        }

        with open(filename, "w") as f:
            json.dump(data, f, indent=2)

        print(f"\n✓ Results exported to: {filename}")


def main():
    """Run performance benchmarks."""
    import argparse

    parser = argparse.ArgumentParser(description="Performance Benchmark Suite")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--export",
        "-e",
        type=str,
        default="benchmark_results.json",
        help="Export results to JSON file",
    )
    args = parser.parse_args()

    print("=" * 80)
    print("BUSINESS ANALYZER PERFORMANCE BENCHMARK SUITE")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    benchmark = PerformanceBenchmark(verbose=args.verbose)

    # Run all benchmarks
    print("\n" + "=" * 80)
    print("DATA GENERATION BENCHMARKS")
    print("=" * 80)
    benchmark.benchmark_data_generation()

    print("\n" + "=" * 80)
    print("FINANCIAL ANALYSIS BENCHMARKS")
    print("=" * 80)
    benchmark.benchmark_financial_analysis()

    print("\n" + "=" * 80)
    print("CUSTOMER ANALYSIS BENCHMARKS")
    print("=" * 80)
    benchmark.benchmark_customer_analysis()

    print("\n" + "=" * 80)
    print("PRODUCT ANALYSIS BENCHMARKS")
    print("=" * 80)
    benchmark.benchmark_product_analysis()

    print("\n" + "=" * 80)
    print("INVENTORY ANALYSIS BENCHMARKS")
    print("=" * 80)
    benchmark.benchmark_inventory_analysis()

    print("\n" + "=" * 80)
    print("COMBINED ANALYSIS BENCHMARKS")
    print("=" * 80)
    benchmark.benchmark_combined_analysis()

    # Optimization comparison
    benchmark.benchmark_optimization_comparison()

    # Print summary
    benchmark.print_summary()

    # Export results
    if args.export:
        benchmark.export_results(args.export)

    print("\n✅ Benchmark suite completed!")


if __name__ == "__main__":
    main()
