"""
Business Intelligence enrichment for NodeFacts.

Post-processes LLM-extracted facts to add business intelligence,
validate relationships, and enrich cross-references.
"""

import logging
from typing import Dict, List, Any, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class BusinessIntelligenceEnricher:
    """Enriches NodeFacts with business intelligence and validated relationships."""

    def enrich_fact(self, fact: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Enrich a single fact with business intelligence.

        Args:
            fact: The node fact to enrich
            context: Additional context (other facts, run info, etc.)

        Returns:
            Enriched fact with additional business intelligence
        """
        node_type = fact.get('node_type', '')

        # Dispatch to specific enrichment based on node type
        if 'PassengerList' in node_type or 'PaxList' in node_type:
            return self.enrich_passenger_list(fact)
        elif 'ContactInfo' in node_type or 'ContactList' in node_type:
            return self.enrich_contact_info_list(fact)
        elif 'BaggageAllowance' in node_type:
            return self.enrich_baggage_list(fact)
        elif 'ServiceList' in node_type:
            return self.enrich_service_list(fact)
        else:
            # Generic enrichment
            return fact

    def enrich_passenger_list(self, fact: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich PassengerList/PaxList with business intelligence.

        Adds:
        - PTC breakdown (ADT/CHD/INF counts)
        - Family relationships (adult-infant)
        - Contact references
        """
        children = fact.get('children', [])

        if not children or not isinstance(children[0], dict):
            # Old format or no children, skip
            return fact

        # Count passengers by PTC
        ptc_counts = defaultdict(int)
        relationships = []
        contact_references = []

        # Build passenger index for relationship resolution
        passenger_index = {}

        for child in children:
            attrs = child.get('attributes', {})
            refs = child.get('references', {})

            # Get passenger ID
            pax_id = attrs.get('id') or attrs.get('PassengerID') or attrs.get('PaxID')
            if pax_id:
                passenger_index[pax_id] = child

            # Count by PTC
            ptc = attrs.get('type') or attrs.get('PTC')
            if ptc:
                ptc_counts[ptc] += 1

            # Extract infant relationships
            infant_refs = refs.get('infant', [])
            if infant_refs:
                for infant_id in infant_refs:
                    relationships.append({
                        'type': 'infant_parent',
                        'parent': pax_id,
                        'child': infant_id,
                        'direction': 'parent_to_child'
                    })

            # Extract parent references (21.3 format)
            parent_ref = refs.get('parent')
            if parent_ref:
                relationships.append({
                    'type': 'infant_parent',
                    'parent': parent_ref,
                    'child': pax_id,
                    'direction': 'child_to_parent'
                })

            # Extract contact references
            contact_refs = refs.get('contact_info', [])
            if contact_refs:
                for contact_id in contact_refs:
                    contact_references.append({
                        'passenger': pax_id,
                        'contact': contact_id
                    })

        # Build or update business_intelligence object
        bi = fact.get('business_intelligence', {})
        bi.update({
            'type_breakdown': dict(ptc_counts),
            'total_items': len(children),
            'passenger_counts': {
                'adults': ptc_counts.get('ADT', 0),
                'children': ptc_counts.get('CHD', 0),
                'infants': ptc_counts.get('INF', 0)
            },
            'has_infants': ptc_counts.get('INF', 0) > 0,
            'has_children': ptc_counts.get('CHD', 0) > 0,
            'has_references': len(relationships) > 0 or len(contact_references) > 0
        })

        fact['business_intelligence'] = bi

        # Merge relationships if they exist
        existing_rels = fact.get('relationships', [])
        all_rels = existing_rels + relationships
        fact['relationships'] = all_rels

        # Add contact cross-references
        if contact_references:
            fact['cross_references'] = {
                'contacts': contact_references
            }

        logger.info(f"Enriched PassengerList: {ptc_counts}, {len(relationships)} relationships")

        return fact

    def enrich_contact_info_list(self, fact: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich ContactInfoList with business intelligence."""
        children = fact.get('children', [])

        if not children or not isinstance(children[0], dict):
            return fact

        # Count by contact type
        type_counts = defaultdict(int)
        has_email = 0
        has_phone = 0

        for child in children:
            attrs = child.get('attributes', {})

            contact_type = attrs.get('ContactType') or attrs.get('type')
            if contact_type:
                type_counts[contact_type] += 1

            # Check for email/phone
            if 'email' in str(attrs).lower():
                has_email += 1
            if 'phone' in str(attrs).lower():
                has_phone += 1

        bi = fact.get('business_intelligence', {})
        bi.update({
            'type_breakdown': dict(type_counts),
            'total_items': len(children),
            'has_email': has_email > 0,
            'has_phone': has_phone > 0,
            'contact_counts': {
                'with_email': has_email,
                'with_phone': has_phone
            }
        })

        fact['business_intelligence'] = bi
        logger.info(f"Enriched ContactInfoList: {len(children)} contacts")

        return fact

    def enrich_baggage_list(self, fact: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich BaggageAllowanceList with business intelligence."""
        children = fact.get('children', [])

        if not children or not isinstance(children[0], dict):
            return fact

        # Count by baggage type
        type_counts = defaultdict(int)

        for child in children:
            attrs = child.get('attributes', {})

            baggage_type = attrs.get('TypeCode') or attrs.get('type')
            if baggage_type:
                type_counts[baggage_type] += 1

        bi = fact.get('business_intelligence', {})
        bi.update({
            'type_breakdown': dict(type_counts),
            'total_items': len(children),
            'has_checked': type_counts.get('Checked', 0) > 0,
            'has_carryon': type_counts.get('CarryOn', 0) > 0
        })

        fact['business_intelligence'] = bi
        logger.info(f"Enriched BaggageAllowanceList: {len(children)} allowances")

        return fact

    def enrich_service_list(self, fact: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich ServiceList with business intelligence."""
        children = fact.get('children', [])

        if not children or not isinstance(children[0], dict):
            return fact

        # Count by service type
        type_counts = defaultdict(int)

        for child in children:
            attrs = child.get('attributes', {})

            service_type = attrs.get('ServiceType') or attrs.get('type')
            if service_type:
                type_counts[service_type] += 1

        bi = fact.get('business_intelligence', {})
        bi.update({
            'type_breakdown': dict(type_counts),
            'total_items': len(children)
        })

        fact['business_intelligence'] = bi
        logger.info(f"Enriched ServiceList: {len(children)} services")

        return fact

    def validate_relationships(self, fact: Dict[str, Any], all_facts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate relationships against all extracted facts.

        Checks if referenced IDs actually exist in other facts.
        """
        relationships = fact.get('relationships', [])

        if not relationships:
            return fact

        # Build index of all passenger/pax IDs
        all_ids = set()
        for other_fact in all_facts:
            for child in other_fact.get('children', []):
                if isinstance(child, dict):
                    attrs = child.get('attributes', {})
                    pax_id = attrs.get('id') or attrs.get('PassengerID') or attrs.get('PaxID')
                    if pax_id:
                        all_ids.add(pax_id)

        # Validate each relationship
        validated_relationships = []
        for rel in relationships:
            parent = rel.get('parent')
            child = rel.get('child')

            valid = True
            if parent and parent not in all_ids:
                logger.warning(f"Invalid relationship: parent {parent} not found")
                valid = False
            if child and child not in all_ids:
                logger.warning(f"Invalid relationship: child {child} not found")
                valid = False

            if valid:
                validated_relationships.append(rel)

        fact['relationships'] = validated_relationships

        return fact


# Global instance
bi_enricher = BusinessIntelligenceEnricher()


def get_bi_enricher() -> BusinessIntelligenceEnricher:
    """Get the business intelligence enricher instance."""
    return bi_enricher
