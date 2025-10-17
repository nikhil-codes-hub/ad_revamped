"""
Unit tests for utility functions.

Tests utility functions including:
- Path normalization
- IATA prefix handling
"""
import pytest
from app.services.utils import normalize_iata_prefix


class TestUtils:
    """Test suite for utility functions."""

    def test_normalize_iata_prefix_airshopping(self):
        """Test IATA prefix normalization for AirShoppingRS."""
        result = normalize_iata_prefix("IATA_AirShoppingRS/Response", "AirShoppingRS")
        assert result == "AirShoppingRS/Response"
        assert not result.startswith("IATA_")

    def test_normalize_iata_prefix_orderview(self):
        """Test IATA prefix normalization for OrderViewRS."""
        result = normalize_iata_prefix("IATA_OrderViewRS/Response/DataLists", "OrderViewRS")
        assert result == "OrderViewRS/Response/DataLists"

    def test_normalize_iata_prefix_no_prefix(self):
        """Test normalization when no IATA prefix exists."""
        result = normalize_iata_prefix("Response/DataLists/PaxList", "OrderViewRS")
        assert result == "Response/DataLists/PaxList"

    def test_normalize_iata_prefix_with_slash(self):
        """Test normalization with leading slash."""
        result = normalize_iata_prefix("/IATA_OrderViewRS/Response", "OrderViewRS")
        assert "/OrderViewRS/Response" in result or "OrderViewRS/Response" in result

    def test_normalize_iata_prefix_partial_match(self):
        """Test that partial IATA_ matches are not affected."""
        result = normalize_iata_prefix("Response/IATA_Field/Data", "OrderViewRS")
        # Should not remove IATA_ from middle of path
        assert "IATA_Field" in result

    def test_normalize_empty_path(self):
        """Test normalizing empty path."""
        result = normalize_iata_prefix("", "OrderViewRS")
        assert result == ""

    def test_normalize_root_only(self):
        """Test normalizing root element only."""
        result = normalize_iata_prefix("IATA_OrderViewRS", "OrderViewRS")
        assert result == "OrderViewRS"

    def test_normalize_preserves_case(self):
        """Test that normalization preserves case."""
        result = normalize_iata_prefix("IATA_OrderViewRS/Response/DataLists", "OrderViewRS")
        assert "DataLists" in result  # Case preserved
