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
import httpx

from app.models.database import NodeFact, NodeRelationship, NodeConfiguration
from app.core.config import settings
from app.prompts import get_relationship_discovery_prompt, get_relationship_system_prompt

logger = structlog.get_logger(__name__)


class RelationshipAnalyzer:
    """Analyzes relationships between extracted NodeFacts using LLM."""

    def __init__(self, db: Session):
        self.db = db
        self.llm_client = None
        self.model = settings.LLM_MODEL
        self._init_sync_client()

    @staticmethod
    def _normalize_reference_value(value: Any) -> Optional[str]:
        """Convert reference values to a comparable string representation."""
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, (dict, list)):
            try:
                return json.dumps(value, sort_keys=True)
            except TypeError:
                return str(value)
        return str(value)

    def _init_sync_client(self):
        """Initialize synchronous LLM client."""
        try:
            if settings.LLM_PROVIDER == "azure" and settings.AZURE_OPENAI_KEY:
                # Create httpx client with increased timeouts
                http_client = httpx.Client(
                    timeout=httpx.Timeout(60.0, connect=10.0),
                    limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
                    follow_redirects=True,
                    verify=False  # Disable SSL verification for corporate proxies
                )

                self.llm_client = AzureOpenAI(
                    api_key=settings.AZURE_OPENAI_KEY,
                    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                    api_version=settings.AZURE_API_VERSION,
                    http_client=http_client
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
        logger.info("=" * 80)
        logger.info("🔍 STARTING RELATIONSHIP ANALYSIS")
        logger.info("=" * 80)
        logger.info(f"Run ID: {run_id}")
        logger.info(f"Total NodeFacts to analyze: {len(node_facts)}")

        # Log LLM client status
        if self.llm_client:
            logger.info(f"✅ LLM Client: INITIALIZED ({self.model})")
        else:
            logger.error(f"❌ LLM Client: NOT INITIALIZED - Relationship discovery will fail!")
            return {
                'success': False,
                'statistics': {},
                'relationships_count': 0,
                'error': 'LLM client not initialized'
            }

        # Group node facts by section_path for efficient processing
        node_groups = self._group_by_section(node_facts)
        logger.info(f"Grouped into {len(node_groups)} distinct sections:")
        for section_path, facts in node_groups.items():
            logger.info(f"  - {section_path}: {len(facts)} nodes")

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
            logger.info("")
            logger.info("-" * 60)
            logger.info(f"📊 Analyzing SOURCE: {source_path}")
            logger.info(f"   Node count: {len(source_facts)}")
            logger.info(f"   Mode: Auto-discover all relationships (LLM-powered)")

            # Check relationships with all other node types
            for target_path, target_facts in node_groups.items():
                if source_path == target_path:
                    continue

                try:
                    logger.info(f"   🔗 Checking relationship: {source_path} -> {target_path}")
                    stats['total_comparisons'] += 1

                    # Validate we have facts to analyze
                    if not source_facts or not target_facts:
                        logger.warning(f"      ⚠️  Skipping: empty facts list (source={len(source_facts)}, target={len(target_facts)})")
                        continue

                    # Use LLM to discover references
                    discovered = self._discover_references_llm(
                        source_facts[0],  # Sample source fact
                        target_facts[0]    # Sample target fact
                    )

                    # Handle error cases: None, empty dict, or invalid structure
                    if not discovered:
                        logger.info(f"      ❌ No references found: {source_path} -> {target_path} (LLM returned None)")
                        continue

                    if not isinstance(discovered, dict):
                        logger.warning(f"      ❌ Invalid LLM response type: {type(discovered)} (expected dict)")
                        continue

                    if not discovered.get('has_references'):
                        logger.info(f"      ❌ No references found: {source_path} -> {target_path}")
                        continue

                    logger.info(f"      ✅ FOUND {len(discovered.get('references', []))} reference(s)!")

                    # Validate discovered references for all instances
                    for ref_info in discovered.get('references', []):
                        if not isinstance(ref_info, dict):
                            logger.warning(f"      ⚠️  Skipping invalid reference info: {type(ref_info)}")
                            continue

                        validated_rels = self._validate_reference_instances(
                            source_facts,
                            target_facts,
                            ref_info,
                            run_id
                        )

                        relationships.extend(validated_rels)
                        stats['relationships_found'] += len(validated_rels)
                        stats['valid_relationships'] += sum(1 for r in validated_rels if r['is_valid'])
                        stats['broken_relationships'] += sum(1 for r in validated_rels if not r['is_valid'])
                        stats['unexpected_discovered'] += 1

                except Exception as e:
                    logger.error(f"      ❌ Error checking relationship {source_path} -> {target_path}: {str(e)}")
                    logger.error(f"         Error type: {type(e).__name__}")
                    import traceback
                    logger.error(f"         Traceback: {traceback.format_exc()}")
                    # Continue to next relationship instead of failing entire analysis
                    continue

        # Bulk insert relationships to database
        if relationships:
            self._save_relationships(relationships)
            logger.info(f"💾 Saved {len(relationships)} relationships to database")
        else:
            logger.warning(f"⚠️  NO RELATIONSHIPS TO SAVE")

        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 RELATIONSHIP ANALYSIS SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total comparisons: {stats['total_comparisons']}")
        logger.info(f"Relationships found: {stats['relationships_found']}")
        logger.info(f"Valid relationships: {stats['valid_relationships']}")
        logger.info(f"Broken relationships: {stats['broken_relationships']}")
        logger.info(f"Auto-discovered relationships: {stats['unexpected_discovered']}")
        logger.info("=" * 80)

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


    def _extract_xml_snippet(self, fact_json: Any) -> str:
        """
        Extract XML snippet from node fact JSON.

        Handles both direct xml_snippet field and nested children structure.
        Reconstructs a representative XML snippet from the stored data.
        """
        # Handle case where fact_json is a string (should be parsed to dict)
        if isinstance(fact_json, str):
            try:
                fact_json = json.loads(fact_json)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse fact_json string, returning empty snippet")
                return "<UnknownNode />"

        # Ensure we have a dict
        if not isinstance(fact_json, dict):
            logger.warning(f"fact_json is not a dict (type: {type(fact_json)}), returning empty snippet")
            return "<UnknownNode />"

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
        target_fact: NodeFact
    ) -> Optional[Dict[str, Any]]:
        """
        Use LLM to discover if source node references target node.

        Args:
            source_fact: Sample source node fact
            target_fact: Sample target node fact

        Returns:
            Dictionary with discovered references or None
        """
        logger.debug(f"🤖 Calling LLM to discover references...")
        logger.debug(f"   Source: {source_fact.node_type} (section: {source_fact.section_path})")
        logger.debug(f"   Target: {target_fact.node_type} (section: {target_fact.section_path})")

        # Extract XML snippets from fact_json (handle nested structure)
        source_xml = self._extract_xml_snippet(source_fact.fact_json)
        target_xml = self._extract_xml_snippet(target_fact.fact_json)

        logger.debug(f"   Source XML snippet length: {len(source_xml)} chars")
        logger.debug(f"   Target XML snippet length: {len(target_xml)} chars")
        logger.debug(f"   Source XML preview: {source_xml[:200]}...")
        logger.debug(f"   Target XML preview: {target_xml[:200]}...")

        prompt = get_relationship_discovery_prompt(
            source_fact.node_type,
            source_xml,
            target_fact.node_type,
            target_xml
        )

        logger.debug(f"   Prompt length: {len(prompt)} chars")

        try:
            # Use synchronous LLM client
            if not self.llm_client:
                logger.error("❌ LLM client not initialized in _discover_references_llm")
                return None

            logger.debug(f"   Calling LLM model: {self.model}")

            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": get_relationship_system_prompt()
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,  # Zero temperature for maximum consistency
                max_tokens=1000,
                response_format={"type": "json_object"},  # Ensure JSON response
                seed=42  # Fixed seed for deterministic responses
            )

            # Parse JSON response
            content = response.choices[0].message.content
            logger.debug(f"   LLM Response: {content}")

            # Parse and validate response
            try:
                result = json.loads(content)
            except json.JSONDecodeError as json_err:
                logger.error(f"❌ Failed to parse LLM JSON response: {json_err}")
                logger.error(f"   Raw content: {content[:500]}")
                return None

            # Validate result structure
            if not isinstance(result, dict):
                logger.error(f"❌ LLM returned non-dict response: {type(result)}")
                return None

            # Enhanced debug logging
            has_refs = result.get('has_references', False)
            refs_count = len(result.get('references', []))

            logger.info(f"      🤖 LLM Result: {source_fact.node_type} -> {target_fact.node_type}")
            logger.info(f"         has_references: {has_refs}")
            logger.info(f"         references_count: {refs_count}")

            if has_refs and refs_count > 0:
                for ref in result.get('references', []):
                    if isinstance(ref, dict):
                        logger.info(f"         - {ref.get('reference_type')}: {ref.get('reference_field')} = {ref.get('reference_value')}")
                    else:
                        logger.warning(f"         - Invalid reference format (not a dict): {type(ref)}")

            return result

        except Exception as e:
            logger.error(f"❌ LLM reference discovery FAILED")
            logger.error(f"   Error: {str(e)}")
            logger.error(f"   Source: {source_fact.node_type}")
            logger.error(f"   Target: {target_fact.node_type}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            return None


    def _validate_reference_instances(
        self,
        source_facts: List[NodeFact],
        target_facts: List[NodeFact],
        ref_info: Dict[str, Any],
        run_id: str
    ) -> List[Dict[str, Any]]:
        """
        Validate reference across all instances of source and target nodes.

        Args:
            source_facts: All source node instances
            target_facts: All target node instances
            ref_info: Reference information from LLM
            run_id: Run ID

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
                'was_expected': False,  # DEPRECATED: All relationships are auto-discovered
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
            return self._normalize_reference_value(fact_data[reference_field])

        # Try nested lookup in child_references
        child_refs = fact_data.get('child_references', {})
        if reference_field in child_refs:
            return self._normalize_reference_value(child_refs[reference_field])

        # Search in children structure
        children = fact_data.get('children', [])
        for child in children:
            # Check attributes
            attributes = child.get('attributes', {})

            # Look for exact field name match (case-insensitive)
            for attr_key, attr_value in attributes.items():
                if attr_key.lower() == reference_field.lower():
                    logger.debug(f"Exact match found: {attr_key} == {reference_field}")
                    return self._normalize_reference_value(attr_value)
                # Also check for common variations (e.g., operating_leg_ref_id vs DatedOperatingLegRefID)
                # Remove underscores and compare
                normalized_attr = attr_key.lower().replace('_', '')
                normalized_field = reference_field.lower().replace('_', '')
                if normalized_attr == normalized_field:
                    logger.debug(f"Normalized match found: {attr_key} matches {reference_field}")
                    return self._normalize_reference_value(attr_value)
                # Check if the field name is contained in the attribute (e.g., "legrefid" in "operating_leg_ref_id")
                # But only if the match is substantial (at least 5 characters)
                if normalized_field in normalized_attr or normalized_attr in normalized_field:
                    if ('id' in normalized_field or 'ref' in normalized_field) and min(len(normalized_field), len(normalized_attr)) >= 5:
                        logger.debug(f"Partial match found: {attr_key} contains {reference_field}")
                        return self._normalize_reference_value(attr_value)

            # Check references
            references = child.get('references', {})
            for ref_type, ref_values in references.items():
                if isinstance(ref_values, list) and len(ref_values) > 0:
                    # If reference field name matches the type, return first value
                    if ref_type.lower() in reference_field.lower() or reference_field.lower() in ref_type.lower():
                        return self._normalize_reference_value(ref_values[0])
                elif isinstance(ref_values, dict):
                    # Handle nested dicts like 'other': {'DatedMarketingSegmentRefId': 'value'}
                    for nested_key, nested_value in ref_values.items():
                        if nested_key.lower() == reference_field.lower():
                            logger.debug(f"Found in nested references: {nested_key} == {reference_field}")
                            return self._normalize_reference_value(nested_value)
                        # Check normalized match
                        normalized_nested = nested_key.lower().replace('_', '')
                        normalized_field = reference_field.lower().replace('_', '')
                        if normalized_nested == normalized_field:
                            logger.debug(f"Found in nested references (normalized): {nested_key} matches {reference_field}")
                            return self._normalize_reference_value(nested_value)

        # Try in refs section at root level
        refs = fact_data.get('refs', {})
        if reference_field in refs:
            ref_value = refs[reference_field]
            if isinstance(ref_value, list) and len(ref_value) > 0:
                return self._normalize_reference_value(ref_value[0])
            else:
                return self._normalize_reference_value(ref_value)

        return None

    def _find_target_by_reference(self, target_facts: List[NodeFact], ref_value: Any) -> Optional[NodeFact]:
        """
        Find target node that matches the reference value.

        Searches in nested structure (children[].attributes, children[].references) for matching IDs.
        """
        normalized_ref = self._normalize_reference_value(ref_value)
        if normalized_ref is None:
            return None

        for fact in target_facts:
            fact_data = fact.fact_json

            # Check common ID fields at root level
            if self._normalize_reference_value(fact_data.get('ID')) == normalized_ref:
                return fact
            if self._normalize_reference_value(fact_data.get('Key')) == normalized_ref:
                return fact
            if self._normalize_reference_value(fact_data.get('ObjectKey')) == normalized_ref:
                return fact

            # Search in children structure
            children = fact_data.get('children', [])
            for child in children:
                # Check attributes for ID/Key fields
                attributes = child.get('attributes', {})
                for attr_key, attr_value in attributes.items():
                    normalized_attr = self._normalize_reference_value(attr_value)

                    # Check if this is an ID field and matches our reference (EXACT match only)
                    if normalized_attr == normalized_ref:
                        return fact
                    # Handle composite IDs: only allow partial match if one is a prefix/suffix of the other
                    # AND they share a substantial common portion (at least 80% match)
                    # Example: "seg0542686836-leg0" should match "seg0542686836" but NOT "seg-999" vs "seg-001"
                    if isinstance(normalized_attr, str) and isinstance(normalized_ref, str):
                        if 'id' in attr_key.lower() or 'key' in attr_key.lower():
                            # Calculate string similarity - only match if substantial overlap
                            min_len = min(len(normalized_ref), len(normalized_attr))
                            max_len = max(len(normalized_ref), len(normalized_attr))

                            # Only consider partial match if:
                            # 1. One string contains the other as a prefix/suffix (not middle substring)
                            # 2. The shorter string is at least 80% of the longer string length
                            if min_len >= max_len * 0.8:
                                if normalized_attr.startswith(normalized_ref) or normalized_ref.startswith(normalized_attr):
                                    return fact
                                if normalized_attr.endswith(normalized_ref) or normalized_ref.endswith(normalized_attr):
                                    return fact

                # Check references section
                references = child.get('references', {})
                for ref_type, ref_values in references.items():
                    if isinstance(ref_values, list):
                        for rv in ref_values:
                            normalized_rv = self._normalize_reference_value(rv)
                            if normalized_rv == normalized_ref:
                                return fact
                            # Check partial matches
                            if isinstance(normalized_rv, str) and isinstance(normalized_ref, str):
                                if normalized_ref in normalized_rv or normalized_rv in normalized_ref:
                                    return fact

            # Check in refs section at root level
            refs = fact_data.get('refs', {})
            for ref_key, ref_vals in refs.items():
                if isinstance(ref_vals, list):
                    for rv in ref_vals:
                        normalized_rv = self._normalize_reference_value(rv)
                        if normalized_rv == normalized_ref:
                            return fact
                        # Check partial matches
                        if isinstance(normalized_rv, str) and isinstance(normalized_ref, str):
                            if normalized_ref in normalized_rv or normalized_rv in normalized_ref:
                                return fact
                elif self._normalize_reference_value(ref_vals) == normalized_ref:
                    return fact

            # Check in child_values at root level
            for key, value in fact_data.items():
                if self._normalize_reference_value(value) == normalized_ref and ('ID' in key or 'Key' in key):
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
