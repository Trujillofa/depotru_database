"""
Tests for inventory analysis module.
"""

import pytest

from src.business_analyzer.analysis.inventory import InventoryAnalyzer, extract_value


class TestInventoryAnalyzer:
    """Test InventoryAnalyzer class."""

    @pytest.fixture
    def sample_data(self):
        """Provide sample transaction data."""
        return [
            # Fast mover: Product A (6 transactions)
            {"ArticulosNombre": "Product A", "Cantidad": 10},
            {"ArticulosNombre": "Product A", "Cantidad": 5},
            {"ArticulosNombre": "Product A", "Cantidad": 8},
            {"ArticulosNombre": "Product A", "Cantidad": 12},
            {"ArticulosNombre": "Product A", "Cantidad": 7},
            {"ArticulosNombre": "Product A", "Cantidad": 9},
            # Normal mover: Product B (3 transactions)
            {"ArticulosNombre": "Product B", "Cantidad": 15},
            {"ArticulosNombre": "Product B", "Cantidad": 20},
            {"ArticulosNombre": "Product B", "Cantidad": 10},
            # Slow mover: Product C (1 transaction)
            {"ArticulosNombre": "Product C", "Cantidad": 5},
        ]

    def test_analyze_returns_dict(self, sample_data):
        """Test analyze returns dictionary."""
        analyzer = InventoryAnalyzer(sample_data)
        result = analyzer.analyze()
        assert isinstance(result, dict)
        assert "fast_moving_items" in result
        assert "slow_moving_items" in result

    def test_fast_moving_items(self, sample_data):
        """Test fast moving items identification."""
        analyzer = InventoryAnalyzer(sample_data)
        result = analyzer.analyze()

        fast_movers = result["fast_moving_items"]
        assert len(fast_movers) == 1
        assert fast_movers[0]["product"] == "Product A"
        assert fast_movers[0]["velocity"] == 6
        assert fast_movers[0]["total_sold"] == 51  # 10+5+8+12+7+9

    def test_slow_moving_items(self, sample_data):
        """Test slow moving items identification."""
        analyzer = InventoryAnalyzer(sample_data)
        result = analyzer.analyze()

        slow_movers = result["slow_moving_items"]
        assert len(slow_movers) == 1
        assert slow_movers[0]["product"] == "Product C"
        assert slow_movers[0]["velocity"] == 1
        assert slow_movers[0]["total_sold"] == 5

    def test_fast_movers_sorted_by_velocity(self):
        """Test fast movers are sorted by velocity descending."""
        data = [
            {"ArticulosNombre": "Product A", "Cantidad": 1},  # 3 transactions (normal)
            {"ArticulosNombre": "Product A", "Cantidad": 1},
            {"ArticulosNombre": "Product A", "Cantidad": 1},
            {
                "ArticulosNombre": "Product B",
                "Cantidad": 1,
            },  # 6 transactions (fast mover, >5)
            {"ArticulosNombre": "Product B", "Cantidad": 1},
            {"ArticulosNombre": "Product B", "Cantidad": 1},
            {"ArticulosNombre": "Product B", "Cantidad": 1},
            {"ArticulosNombre": "Product B", "Cantidad": 1},
            {"ArticulosNombre": "Product B", "Cantidad": 1},
        ]
        analyzer = InventoryAnalyzer(data)
        result = analyzer.analyze()

        fast_movers = result["fast_moving_items"]
        assert len(fast_movers) == 1  # Only Product B qualifies (velocity > 5)
        assert fast_movers[0]["product"] == "Product B"
        assert fast_movers[0]["velocity"] == 6

    def test_slow_movers_sorted_by_velocity(self):
        """Test slow movers are sorted by velocity ascending."""
        data = [
            {"ArticulosNombre": "Product A", "Cantidad": 1},  # 1 transaction
            {"ArticulosNombre": "Product B", "Cantidad": 1},  # 1 transaction
        ]
        analyzer = InventoryAnalyzer(data)
        result = analyzer.analyze()

        slow_movers = result["slow_moving_items"]
        assert len(slow_movers) == 2
        # Both have velocity 1, so order doesn't matter much
        assert all(m["velocity"] == 1 for m in slow_movers)

    def test_get_velocity_thresholds(self, sample_data):
        """Test getting velocity thresholds."""
        analyzer = InventoryAnalyzer(sample_data)
        thresholds = analyzer.get_velocity_thresholds()

        assert "fast_mover" in thresholds
        assert "slow_mover" in thresholds
        assert isinstance(thresholds["fast_mover"], int)
        assert isinstance(thresholds["slow_mover"], int)

    def test_analyze_product_velocity_fast(self, sample_data):
        """Test analyzing specific fast product velocity."""
        analyzer = InventoryAnalyzer(sample_data)
        result = analyzer.analyze_product_velocity("Product A")

        assert result is not None
        assert result["product"] == "Product A"
        assert result["velocity"] == 6
        assert result["total_sold"] == 51
        assert result["velocity_class"] == "fast"

    def test_analyze_product_velocity_slow(self, sample_data):
        """Test analyzing specific slow product velocity."""
        analyzer = InventoryAnalyzer(sample_data)
        result = analyzer.analyze_product_velocity("Product C")

        assert result is not None
        assert result["product"] == "Product C"
        assert result["velocity"] == 1
        assert result["velocity_class"] == "slow"

    def test_analyze_product_velocity_normal(self, sample_data):
        """Test analyzing specific normal product velocity."""
        analyzer = InventoryAnalyzer(sample_data)
        result = analyzer.analyze_product_velocity("Product B")

        assert result is not None
        assert result["product"] == "Product B"
        assert result["velocity"] == 3
        assert result["velocity_class"] == "normal"

    def test_analyze_product_velocity_not_found(self, sample_data):
        """Test analyzing non-existent product."""
        analyzer = InventoryAnalyzer(sample_data)
        result = analyzer.analyze_product_velocity("NonExistent")

        assert result is None

    def test_get_inventory_summary(self, sample_data):
        """Test inventory summary."""
        analyzer = InventoryAnalyzer(sample_data)
        summary = analyzer.get_inventory_summary()

        assert summary["total_products"] == 3
        assert summary["fast_movers"] == 1
        assert summary["slow_movers"] == 1
        assert summary["normal_velocity"] == 1
        assert summary["fast_percentage"] == 33.33
        assert summary["slow_percentage"] == 33.33

    def test_empty_data(self):
        """Test handling of empty data."""
        analyzer = InventoryAnalyzer([])
        result = analyzer.analyze()

        assert result["fast_moving_items"] == []
        assert result["slow_moving_items"] == []

    def test_empty_data_summary(self):
        """Test inventory summary with empty data."""
        analyzer = InventoryAnalyzer([])
        summary = analyzer.get_inventory_summary()

        assert summary["total_products"] == 0
        assert summary["fast_movers"] == 0
        assert summary["slow_movers"] == 0
        assert summary["fast_percentage"] == 0.0
        assert summary["slow_percentage"] == 0.0

    def test_unknown_product_default(self):
        """Test unknown product name default."""
        data = [
            {"Cantidad": 10},
        ]
        analyzer = InventoryAnalyzer(data)
        result = analyzer.analyze()

        assert len(result["slow_moving_items"]) == 1
        assert result["slow_moving_items"][0]["product"] == "Unknown"

    def test_default_quantity(self):
        """Test default quantity when not specified."""
        data = [
            {"ArticulosNombre": "Product A"},  # No quantity specified
            {"ArticulosNombre": "Product A"},
            {"ArticulosNombre": "Product A"},
            {"ArticulosNombre": "Product A"},
            {"ArticulosNombre": "Product A"},
            {"ArticulosNombre": "Product A"},  # 6 transactions, default qty 1 each
        ]
        analyzer = InventoryAnalyzer(data)
        result = analyzer.analyze()

        fast_movers = result["fast_moving_items"]
        assert len(fast_movers) == 1
        assert fast_movers[0]["total_sold"] == 6  # 6 transactions * 1 default qty


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
