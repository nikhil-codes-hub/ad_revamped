"""
Relationship Analyzer Service

Uses LLM to discover and validate relationships between nodes in XML.
Handles both BA-configured expected_references and auto-discovery.
"""

from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
import structlog
import json
from openai import AzureOpenAI, OpenAI

from app.models.database import NodeFact, NodeRelationship, NodeConfiguration
from app.core.config import settings

logger = structlog.get_logger(__name__)


class RelationshipAnalyzer:
    """Analyzes relationships between extracted NodeFacts using LLM."""

    def __init__(self, db: Session):
        self.db = db
        self.llm_client = None
        self.model = settings.LLM_MODEL
        self._init_sync_client()

    def _init_sync_client(self):
        """Initialize synchronous LLM client."""
        try:
            if settings.LLM_PROVIDER == "azure" and settings.AZURE_OPENAI_KEY:
                self.llm_client = AzureOpenAI(
                    api_key=settings.AZURE_OPENAI_KEY,
                    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                    api_version=settings.AZURE_API_VERSION
                )
                self.model = settings.MODEL_DEPLOYMENT_NAME
                logger.info("Initialized sync Azure OpenAI client for relationship analysis")
            elif settings.OPENAI_API_KEY:
                self.llm_client = OpenAI(api_key=settings.OPENAI_API_KEY)
                self.model = settings.LLM_MODEL
                logger.info("Initialized sync OpenAI client for relationship analysis")
            else:
                logger.error("No LLM API keys found for relationship analysis")
        except Exception as e:
            logger.error(f"Failed to initialize sync LLM client: {e}")

    def analyze_relationships(self, run_id: str, node_facts: List[NodeFact]) -> Dict[str, Any]:
        """
        Analyze relationships between all NodeFacts in a run (synchronous).

        Args:
            run_id: The run ID
            node_facts: List of extracted NodeFacts

        Returns:
            Dictionary with statistics and discovered relationships
        """
        logger.info("Starting relationship analysis", run_id=run_id, node_count=len(node_facts))

        # Group node facts by section_path for efficient processing
        node_groups = self._group_by_section(node_facts)

        relationships = []
        stats = {
            'total_comparisons': 0,
            'relationships_found': 0,
            'valid_relationships': 0,
            'broken_relationships': 0,
            'expected_validated': 0,
            'expected_missing': 0,
            'unexpected_discovered': 0
        }

        # Analyze each source node type against all target node types
        for source_path, source_facts in node_groups.items():
            # Get expected references from configuration
            expected_refs = self._get_expected_references(source_path, source_facts[0])

            logger.info(f"Analyzing {source_path}",
                       fact_count=len(source_facts),
                       expected_refs=expected_refs)

            # Check relationships with all other node types
            for target_path, target_facts in node_groups.items():
                if source_path == target_path:
                    continue

                stats['total_comparisons'] += 1

                # Use LLM to discover references
                discovered = self._discover_references_llm(
                    source_facts[0],  # Sample source fact
                    target_facts[0],   # Sample target fact
                    expected_refs
                )

                if not discovered or not discovered.get('has_references'):
                    continue

                # Validate discovered references for all instances
                for ref_info in discovered.get('references', []):
                    validated_rels = self._validate_reference_instances(
                        source_facts,
                        target_facts,
                        ref_info,
                        run_id,
                        expected_refs
                    )

                    relationships.extend(validated_rels)
                    stats['relationships_found'] += len(validated_rels)
                    stats['valid_relationships'] += sum(1 for r in validated_rels if r['is_valid'])
                    stats['broken_relationships'] += sum(1 for r in validated_rels if not r['is_valid'])

                    if ref_info.get('was_expected'):
                        stats['expected_validated'] += 1
                    else:
                        stats['unexpected_discovered'] += 1

            # Check for expected references that weren't found
            stats['expected_missing'] += len(expected_refs) - stats['expected_validated']

        # Bulk insert relationships to database
        if relationships:
            self._save_relationships(relationships)

        logger.info("Relationship analysis complete", run_id=run_id, stats=stats)
        return {
            'success': True,
            'statistics': stats,
            'relationships_count': len(relationships)
        }

    def _group_by_section(self, node_facts: List[NodeFact]) -> Dict[str, List[NodeFact]]:
        """Group node facts by section_path."""
        groups = {}
        for fact in node_facts:
            if fact.section_path not in groups:
                groups[fact.section_path] = []
            groups[fact.section_path].append(fact)
        return groups

    def _get_expected_references(self, section_path: str, sample_fact: NodeFact) -> List[str]:
        """Get expected references from node configuration."""
        config = self.db.query(NodeConfiguration).filter(
            NodeConfiguration.section_path == section_path,
            NodeConfiguration.spec_version == sample_fact.spec_version,
            NodeConfiguration.message_root == sample_fact.message_root
        ).first()

        if config and config.expected_references:
            return config.expected_references
        return []

    def _extract_xml_snippet(self, fact_json: Dict[str, Any]) -> str:
        """
        Extract XML snippet from node fact JSON.

        Handles both direct xml_snippet field and nested children structure.
        Reconstructs a representative XML snippet from the stored data.
        """
        # Try direct xml_snippet field first
        if 'xml_snippet' in fact_json and fact_json['xml_snippet']:
            return fact_json['xml_snippet']

        # Reconstruct from children snippets
        xml_parts = []
        node_type = fact_json.get('node_type', 'UnknownNode')

        # Build container opening tag
        xml_parts.append(f"<{node_type}>")

        # Add children snippets
        children = fact_json.get('children', [])
        for child in children[:5]:  # Limit to first 5 children to keep snippet size reasonable
            if 'snippet' in child and child['snippet']:
                xml_parts.append(child['snippet'])
            else:
                # Fallback: construct minimal snippet from attributes
                child_type = child.get('node_type', 'Child')
                child_attrs = child.get('attributes', {})
                xml_parts.append(f"<{child_type}>")
                for key, value in list(child_attrs.items())[:3]:  # First 3 attributes
                    xml_parts.append(f"  <{key}>{value}</{key}>")
                xml_parts.append(f"</{child_type}>")

        # If no children, try to extract from refs or attributes
        if not children:
            attributes = fact_json.get('attributes', {})
            for key, value in list(attributes.items())[:5]:
                if isinstance(value, (str, int, float)):
                    xml_parts.append(f"  <{key}>{value}</{key}>")

        # Add container closing tag
        xml_parts.append(f"</{node_type}>")

        xml_snippet = '\n'.join(xml_parts)

        logger.debug(f"Reconstructed XML snippet for {node_type}",
                    has_children=len(children),
                    snippet_length=len(xml_snippet))

        return xml_snippet

    def _discover_references_llm(
        self,
        source_fact: NodeFact,
        target_fact: NodeFact,
        expected_refs: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Use LLM to discover if source node references target node.

        Args:
            source_fact: Sample source node fact
            target_fact: Sample target node fact
            expected_refs: BA-configured expected references

        Returns:
            Dictionary with discovered references or None
        """
        # Extract XML snippets from fact_json (handle nested structure)
        source_xml = self._extract_xml_snippet(source_fact.fact_json)
        target_xml = self._extract_xml_snippet(target_fact.fact_json)

        prompt = self._build_discovery_prompt(
            source_fact.node_type,
            source_xml,
            target_fact.node_type,
            target_xml,
            expected_refs
        )

        try:
            # Use synchronous LLM client
            if not self.llm_client:
                logger.error("LLM client not initialized")
                return None

            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an XML relationship analysis expert. Analyze XML structures and return structured JSON results."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Low temperature for consistency
                max_tokens=1000,
                response_format={"type": "json_object"}  # Ensure JSON response
            )

            # Parse JSON response
            content = response.choices[0].message.content
            result = json.loads(content)

            # Debug logging
            logger.info(f"LLM relationship result: {source_fact.node_type} -> {target_fact.node_type}",
                       has_references=result.get('has_references'),
                       references_count=len(result.get('references', [])),
                       result=result)

            return result

        except Exception as e:
            logger.error("LLM reference discovery failed",
                        error=str(e),
                        source=source_fact.node_type,
                        target=target_fact.node_type)
            return None

    def _build_discovery_prompt(
        self,
        source_type: str,
        source_xml: str,
        target_type: str,
        target_xml: str,
        expected_refs: List[str]
    ) -> str:
        """Build LLM prompt for reference discovery."""
        return f"""Analyze if the SOURCE node contains references to the TARGET node.

SOURCE NODE TYPE: {source_type}
SOURCE XML SAMPLE:
```xml
{source_xml}
```

TARGET NODE TYPE: {target_type}
TARGET XML SAMPLE:
```xml
{target_xml}
```

EXPECTED REFERENCES (configured by Business Analyst): {', '.join(expected_refs) if expected_refs else 'None - auto-discover all references'}

TASK:
1. Identify if SOURCE contains reference fields pointing to TARGET
2. For each reference found, determine:
   - reference_type: Semantic name (e.g., "pax_reference", "segment_reference", "infant_parent")
   - reference_field: XML element/attribute containing the reference (e.g., "PaxRefID", "SegmentKey")
   - reference_value: The actual reference ID/key value from this sample
   - confidence: Your confidence level (0.0 - 1.0)
   - was_expected: Is this reference in the EXPECTED REFERENCES list?

3. If BA provided EXPECTED REFERENCES, validate if they exist in the XML

Return ONLY valid JSON (no markdown, no explanation):
{{
  "has_references": true|false,
  "references": [
    {{
      "reference_type": "pax_reference",
      "reference_field": "PaxRefID",
      "reference_value": "PAX1",
      "confidence": 0.95,
      "was_expected": true
    }}
  ],
  "missing_expected": ["infant_parent"],
  "validation_notes": "Brief note if needed"
}}"""

    def _validate_reference_instances(
        self,
        source_facts: List[NodeFact],
        target_facts: List[NodeFact],
        ref_info: Dict[str, Any],
        run_id: str,
        expected_refs: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Validate reference across all instances of source and target nodes.

        Args:
            source_facts: All source node instances
            target_facts: All target node instances
            ref_info: Reference information from LLM
            run_id: Run ID
            expected_refs: Expected references list

        Returns:
            List of validated relationship dictionaries
        """
        relationships = []
        reference_field = ref_info.get('reference_field')

        for source_fact in source_facts:
            # Extract reference value from source fact
            ref_value = self._extract_reference_value(source_fact, reference_field)

            if not ref_value:
                continue

            # Try to find matching target node
            target_fact = self._find_target_by_reference(target_facts, ref_value)

            relationships.append({
                'run_id': run_id,
                'source_node_fact_id': source_fact.id,
                'source_node_type': source_fact.node_type,
                'source_section_path': source_fact.section_path,
                'target_node_fact_id': target_fact.id if target_fact else None,
                'target_node_type': target_facts[0].node_type,
                'target_section_path': target_facts[0].section_path,
                'reference_type': ref_info.get('reference_type'),
                'reference_field': reference_field,
                'reference_value': ref_value,
                'is_valid': target_fact is not None,
                'was_expected': ref_info.get('reference_type') in expected_refs,
                'confidence': float(ref_info.get('confidence', 1.0)),
                'discovered_by': 'llm',
                'model_used': self.model
            })

        return relationships

    def _extract_reference_value(self, fact: NodeFact, reference_field: str) -> Optional[str]:
        """
        Extract reference value from node fact using field name.

        Handles nested structure where data is stored in children[].attributes or children[].references.
        Returns the first matching reference value found.
        """
        fact_data = fact.fact_json

        # Try direct field lookup
        if reference_field in fact_data:
            return fact_data[reference_field]

        # Try nested lookup in child_references
        child_refs = fact_data.get('child_references', {})
        if reference_field in child_refs:
            return child_refs[reference_field]

        # Search in children structure
        children = fact_data.get('children', [])
        for child in children:
            # Check attributes
            attributes = child.get('attributes', {})

            # Look for exact field name match (case-insensitive)
            for attr_key, attr_value in attributes.items():
                if attr_key.lower() == reference_field.lower():
                    logger.debug(f"Exact match found: {attr_key} == {reference_field}")
                    return attr_value
                # Also check for common variations (e.g., operating_leg_ref_id vs DatedOperatingLegRefID)
                # Remove underscores and compare
                normalized_attr = attr_key.lower().replace('_', '')
                normalized_field = reference_field.lower().replace('_', '')
                if normalized_attr == normalized_field:
                    logger.debug(f"Normalized match found: {attr_key} matches {reference_field}")
                    return attr_value
                # Check if the field name is contained in the attribute (e.g., "legrefid" in "operating_leg_ref_id")
                # But only if the match is substantial (at least 5 characters)
                if normalized_field in normalized_attr or normalized_attr in normalized_field:
                    if ('id' in normalized_field or 'ref' in normalized_field) and min(len(normalized_field), len(normalized_attr)) >= 5:
                        logger.debug(f"Partial match found: {attr_key} contains {reference_field}")
                        return attr_value

            # Check references
            references = child.get('references', {})
            for ref_type, ref_values in references.items():
                if isinstance(ref_values, list) and len(ref_values) > 0:
                    # If reference field name matches the type, return first value
                    if ref_type.lower() in reference_field.lower() or reference_field.lower() in ref_type.lower():
                        return ref_values[0]

        # Try in refs section at root level
        refs = fact_data.get('refs', {})
        if reference_field in refs:
            ref_value = refs[reference_field]
            if isinstance(ref_value, list) and len(ref_value) > 0:
                return ref_value[0]
            elif isinstance(ref_value, str):
                return ref_value

        return None

    def _find_target_by_reference(self, target_facts: List[NodeFact], ref_value: str) -> Optional[NodeFact]:
        """
        Find target node that matches the reference value.

        Searches in nested structure (children[].attributes, children[].references) for matching IDs.
        """
        for fact in target_facts:
            fact_data = fact.fact_json

            # Check common ID fields at root level
            if fact_data.get('ID') == ref_value:
                return fact
            if fact_data.get('Key') == ref_value:
                return fact
            if fact_data.get('ObjectKey') == ref_value:
                return fact

            # Search in children structure
            children = fact_data.get('children', [])
            for child in children:
                # Check attributes for ID/Key fields
                attributes = child.get('attributes', {})
                for attr_key, attr_value in attributes.items():
                    # Check if this is an ID field and matches our reference
                    if attr_value == ref_value:
                        return fact
                    # Also check if the attribute contains part of the reference (segment matching)
                    if isinstance(attr_value, str) and isinstance(ref_value, str):
                        # Handle cases like "seg0542686836-leg0" matching "seg0542686836"
                        if ref_value in attr_value or attr_value in ref_value:
                            if 'id' in attr_key.lower() or 'key' in attr_key.lower() or 'ref' in attr_key.lower():
                                return fact

                # Check references section
                references = child.get('references', {})
                for ref_type, ref_values in references.items():
                    if isinstance(ref_values, list):
                        if ref_value in ref_values:
                            return fact
                        # Check partial matches
                        for rv in ref_values:
                            if isinstance(rv, str) and (ref_value in rv or rv in ref_value):
                                return fact

            # Check in refs section at root level
            refs = fact_data.get('refs', {})
            for ref_key, ref_vals in refs.items():
                if isinstance(ref_vals, list):
                    if ref_value in ref_vals:
                        return fact
                    # Check partial matches
                    for rv in ref_vals:
                        if isinstance(rv, str) and (ref_value in rv or rv in ref_value):
                            return fact
                elif ref_vals == ref_value:
                    return fact

            # Check in child_values at root level
            for key, value in fact_data.items():
                if value == ref_value and ('ID' in key or 'Key' in key):
                    return fact

        return None

    def _save_relationships(self, relationships: List[Dict[str, Any]]):
        """Bulk insert relationships to database."""
        try:
            # Use bulk_insert_mappings for performance
            self.db.bulk_insert_mappings(NodeRelationship, relationships)
            self.db.commit()
            logger.info(f"Saved {len(relationships)} relationships to database")
        except Exception as e:
            self.db.rollback()
            logger.error("Failed to save relationships", error=str(e))
            raise


def create_relationship_analyzer(db: Session) -> RelationshipAnalyzer:
    """Factory function to create RelationshipAnalyzer instance."""
    return RelationshipAnalyzer(db)
