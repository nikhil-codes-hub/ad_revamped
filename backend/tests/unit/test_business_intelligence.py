"""
Unit tests for BusinessIntelligenceEnricher service.

Tests business intelligence enrichment including:
- Passenger list enrichment
- Contact information enrichment
- Baggage list enrichment
- Service list enrichment
"""
import pytest
from app.services.business_intelligence import BusinessIntelligenceEnricher


class TestBusinessIntelligenceEnricher:
    """Test suite for BusinessIntelligenceEnricher."""

    def test_enrich_passenger_list(self):
        """Test enriching passenger list with business intelligence."""
        enricher = BusinessIntelligenceEnricher()

        fact = {
            "node_type": "PaxList",
            "children": [
                {"attributes": {"PaxID": "PAX1", "PTC": "ADT"}},
                {"attributes": {"PaxID": "PAX2", "PTC": "ADT"}},
                {"attributes": {"PaxID": "PAX3", "PTC": "CHD"}},
            ]
        }

        result = enricher.enrich_passenger_list(fact)

        assert "business_intelligence" in result
        bi = result["business_intelligence"]
        assert bi["passenger_counts"]["adults"] == 2
        assert bi["passenger_counts"]["children"] == 1

    def test_enrich_contact_info_list(self):
        """Test enriching contact info list."""
        enricher = BusinessIntelligenceEnricher()

        fact = {
            "node_type": "ContactInfoList",
            "children": [
                {"attributes": {"Email": "test@example.com"}},
                {"attributes": {"Phone": "+1234567890"}},
            ]
        }

        result = enricher.enrich_contact_info_list(fact)

        assert "business_intelligence" in result
        bi = result["business_intelligence"]
        assert bi["has_email"] is True
        assert bi["has_phone"] is True

    def test_enrich_baggage_list(self):
        """Test enriching baggage list."""
        enricher = BusinessIntelligenceEnricher()

        fact = {
            "node_type": "BaggageAllowanceList",
            "children": [
                {"attributes": {"TypeCode": "Checked"}},
                {"attributes": {"TypeCode": "CarryOn"}},
            ]
        }

        result = enricher.enrich_baggage_list(fact)

        assert "business_intelligence" in result
        bi = result["business_intelligence"]
        assert bi["has_checked"] is True
        assert bi["has_carryon"] is True

    def test_enrich_service_list(self):
        """Test enriching service list."""
        enricher = BusinessIntelligenceEnricher()

        fact = {
            "node_type": "ServiceList",
            "children": [
                {"attributes": {"ServiceType": "Meal"}},
                {"attributes": {"ServiceType": "Baggage"}},
            ]
        }

        result = enricher.enrich_service_list(fact)

        assert "business_intelligence" in result
        bi = result["business_intelligence"]
        assert bi["total_items"] == 2

    def test_validate_relationships(self):
        """Test relationship validation."""
        enricher = BusinessIntelligenceEnricher()

        fact = {
            "relationships": [
                {"type": "infant_parent", "parent": "PAX1", "child": "PAX2"}
            ]
        }

        all_facts = [
            {"children": [{"attributes": {"PaxID": "PAX1"}}]},
            {"children": [{"attributes": {"PaxID": "PAX2"}}]},
        ]

        result = enricher.validate_relationships(fact, all_facts)

        assert len(result["relationships"]) == 1

    def test_enrich_fact_dispatcher(self):
        """Test that enrich_fact dispatches to correct enricher."""
        enricher = BusinessIntelligenceEnricher()

        fact = {"node_type": "PaxList", "children": []}
        result = enricher.enrich_fact(fact)

        # Should return enriched fact
        assert result is not None
