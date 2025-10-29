"""
Pattern generation service for AssistedDiscovery.

Analyzes NodeFacts to generate reusable Pattern signatures for future matching.
Implements Phase 2: Pattern Discovery.
"""

import logging
import hashlib
import json
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime
from collections import defaultdict
from sqlalchemy.orm import Session
from openai import AzureOpenAI, OpenAI
import httpx

from app.models.database import NodeFact, Pattern, Run
from app.core.config import settings
from app.services.llm_extractor import get_llm_extractor
from app.services.utils import normalize_iata_prefix
from app.prompts import get_pattern_description_prompt

logger = logging.getLogger(__name__)


class PatternGenerator:
    """Generates pattern signatures from NodeFacts."""

    def __init__(self, db_session: Session):
        """Initialize pattern generator with database session."""
        self.db_session = db_session

    def _normalize_path(self, path: str, message_root: str) -> str:
        """Normalize section path for consistent matching."""
        # Remove leading/trailing slashes
        normalized = path.strip('/')

        # Remove IATA_ prefix for any message type (OrderViewRS, AirShoppingRS, etc.)
        normalized = normalize_iata_prefix(normalized, message_root)

        return normalized

    def _extract_required_attributes(self, fact_json: Dict[str, Any]) -> List[str]:
        """Extract required attributes from a NodeFact."""
        attributes = fact_json.get('attributes', {})

        # Filter out metadata fields added during extraction - these are NOT real XML attributes
        METADATA_FIELDS = {
            'summary',          # LLM-generated summary
            'description',      # LLM-generated description
            'notes',           # Internal notes
            'child_count',     # Count of children
            'confidence',      # Extraction confidence score
            'node_ordinal',    # Node position/ordering
            'missing_elements' # Quality check tracking field
        }

        required = []
        for key in sorted(attributes.keys()):
            # Skip metadata/descriptive fields
            if key not in METADATA_FIELDS:
                required.append(key)

        return required

    def _extract_optional_attributes(self, facts_group: List[Dict[str, Any]]) -> List[str]:
        """
        Determine optional attributes by comparing across similar NodeFacts.
        Attributes present in some but not all facts are considered optional.
        """
        if not facts_group:
            return []

        # Filter out metadata fields (same as _extract_required_attributes)
        METADATA_FIELDS = {
            'summary', 'description', 'notes', 'child_count',
            'confidence', 'node_ordinal', 'missing_elements'
        }

        # Count attribute occurrences
        attr_counts = defaultdict(int)
        total_facts = len(facts_group)

        for fact in facts_group:
            attributes = fact.get('attributes', {})
            for key in attributes.keys():
                if key not in METADATA_FIELDS:
                    attr_counts[key] += 1

        # Optional: present in >0 but <100% of facts
        optional = []
        for attr, count in attr_counts.items():
            if 0 < count < total_facts:
                optional.append(attr)

        return sorted(optional)

    def _get_child_structure_fingerprint(self, children: List[Any]) -> Dict[str, Any]:
        """
        Generate fingerprint of child structure.

        Returns:
            {
                "has_children": bool,
                "child_types": ["Passenger", "ContactInfo"],
                "child_structure": {...}
            }
        """
        if not children:
            return {"has_children": False}

        # Check if children are objects (container) or simple strings (item)
        if isinstance(children[0], dict):
            # Container with nested children
            child_types = set()
            child_structures = []

            for child in children:
                node_type = child.get('node_type', 'Unknown')
                child_types.add(node_type)

                # Get child's required attributes
                child_attrs = self._extract_required_attributes(child)
                child_refs = list(child.get('references', {}).keys())

                child_structures.append({
                    'node_type': node_type,
                    'required_attributes': sorted(child_attrs),
                    'reference_fields': sorted(child_refs)
                })

            return {
                "has_children": True,
                "is_container": True,
                "child_types": sorted(list(child_types)),
                "child_structures": child_structures
            }
        else:
            # Simple children (item extraction)
            return {
                "has_children": True,
                "is_container": False,
                "child_names": sorted(set(children))
            }

    def _extract_reference_patterns(self, fact_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract reference patterns from fact (auto-discovery mode).

        Args:
            fact_json: NodeFact JSON data

        Returns list of reference patterns like:
        [
            {
                "type": "infant_parent",
                "parent": "PAX1",
                "child": "PAX1.1",
                "direction": "INF→ADT"
            }
        ]
        """
        patterns = []

        # Extract from relationships field (LLM-discovered)
        relationships = fact_json.get('relationships', [])
        for rel in relationships:
            patterns.append({
                'type': rel.get('type', 'unknown'),
                'parent': rel.get('parent'),
                'child': rel.get('child'),
                'direction': rel.get('direction')
            })

        # Extract from cross_references
        cross_refs = fact_json.get('cross_references', {})
        for ref_type, ref_list in cross_refs.items():
            if isinstance(ref_list, list):
                for ref in ref_list:
                    patterns.append({
                        'type': f'cross_reference_{ref_type}',
                        'reference': ref
                    })

        return patterns

    def _extract_bi_schema(self, fact_json: Dict[str, Any]) -> Dict[str, Any]:
        """Extract business intelligence schema structure."""
        bi = fact_json.get('business_intelligence', {})

        if not bi:
            return {}

        schema = {}

        # Type breakdown structure
        if 'type_breakdown' in bi and bi['type_breakdown'] is not None:
            schema['has_type_breakdown'] = True
            schema['breakdown_keys'] = sorted(list(bi['type_breakdown'].keys()))

        # Passenger counts structure
        if 'passenger_counts' in bi:
            schema['has_passenger_counts'] = True

        # Contact counts structure
        if 'contact_counts' in bi:
            schema['has_contact_counts'] = True

        # Flags
        flags = []
        for key, value in bi.items():
            if key.startswith('has_') and isinstance(value, bool):
                flags.append(key)

        if flags:
            schema['flags'] = sorted(flags)

        return schema

    def generate_decision_rule(self, facts_group: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate decision rule from a group of similar NodeFacts.

        Args:
            facts_group: List of fact_json dicts from similar NodeFacts

        Returns:
            Decision rule dict
        """
        if not facts_group:
            return {}

        # Use first fact as template
        template = facts_group[0]

        # Extract must-have attributes (present in ALL facts)
        must_have_attrs = set(self._extract_required_attributes(template))
        for fact in facts_group[1:]:
            fact_attrs = set(self._extract_required_attributes(fact))
            must_have_attrs &= fact_attrs  # Intersection

        # Optional attributes
        optional_attrs = self._extract_optional_attributes(facts_group)

        # Child structure
        child_structure = self._get_child_structure_fingerprint(
            template.get('children', [])
        )

        # Reference patterns (auto-discovered by LLM)
        reference_patterns = self._extract_reference_patterns(template)

        # Business intelligence schema
        bi_schema = self._extract_bi_schema(template)

        decision_rule = {
            'node_type': template.get('node_type', 'Unknown'),
            'must_have_attributes': sorted(list(must_have_attrs)),
            'optional_attributes': sorted(optional_attrs),
            'child_structure': child_structure,
            'reference_patterns': reference_patterns,
            'business_intelligence_schema': bi_schema
        }

        return decision_rule

    def generate_signature_hash(self, decision_rule: Dict[str, Any],
                                spec_version: str,
                                section_path: str) -> str:
        """
        Generate unique signature hash for a pattern.

        Hash is based on:
        - Normalized section path
        - Node type
        - Required attributes
        - Child structure
        - Reference patterns
        - Spec version
        """
        # Extract message_root from decision_rule or section_path
        message_root = decision_rule.get('message_root', section_path.split('/')[0] if '/' in section_path else '')

        components = {
            'path': self._normalize_path(section_path, message_root),
            'version': spec_version,
            'node_type': decision_rule.get('node_type', ''),
            'must_have': decision_rule.get('must_have_attributes', []),
            'child_structure': decision_rule.get('child_structure', {}),
            'references': [p.get('type', '') for p in decision_rule.get('reference_patterns', [])]
        }

        # Create deterministic JSON string
        signature_string = json.dumps(components, sort_keys=True)

        # Generate SHA256 hash, use first 16 chars
        hash_obj = hashlib.sha256(signature_string.encode('utf-8'))
        return hash_obj.hexdigest()[:16]

    def generate_selector_xpath(self, section_path: str, node_type: str) -> str:
        """Generate XPath selector for pattern matching."""
        # Simple XPath based on node type
        # Example: ./PassengerList or ./BaggageAllowanceList
        return f"./{node_type}"

    def _generate_pattern_description(self,
                                      decision_rule: Dict[str, Any],
                                      section_path: str) -> Optional[str]:
        """
        Generate human-readable description of pattern using LLM.

        Args:
            decision_rule: The pattern decision rule
            section_path: XML section path

        Returns:
            Short description string (1-2 sentences) or None if LLM unavailable
        """
        try:
            llm_extractor = get_llm_extractor()

            sync_client = None
            model_name = settings.LLM_MODEL

            if settings.LLM_PROVIDER == "azure" and settings.AZURE_OPENAI_KEY:
                # Create httpx client with increased timeouts
                http_client = httpx.Client(
                    timeout=httpx.Timeout(60.0, connect=10.0),
                    limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
                    follow_redirects=True,
                    verify=False  # Disable SSL verification for corporate proxies
                )

                sync_client = AzureOpenAI(
                    api_key=settings.AZURE_OPENAI_KEY,
                    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                    api_version=settings.AZURE_API_VERSION,
                    http_client=http_client
                )
                model_name = settings.MODEL_DEPLOYMENT_NAME
                logger.debug("Using Azure OpenAI for description generation")
            elif settings.OPENAI_API_KEY:
                sync_client = OpenAI(api_key=settings.OPENAI_API_KEY)
                model_name = settings.LLM_MODEL
                logger.debug("Using OpenAI for description generation")
            elif llm_extractor.client:
                sync_client = llm_extractor.client

            if not sync_client:
                logger.debug("LLM client not available for description generation")
                return None

            node_type = decision_rule.get('node_type', 'Unknown')
            must_have = decision_rule.get('must_have_attributes', [])
            child_structure = decision_rule.get('child_structure', {})
            reference_patterns = decision_rule.get('reference_patterns', [])

            prompt = get_pattern_description_prompt(
                node_type=node_type,
                section_path=section_path,
                must_have_attributes=', '.join(must_have) if must_have else 'None',
                has_children='Yes' if child_structure.get('has_children', False) else 'No',
                child_elements=', '.join(child_structure.get('child_types', [])) if child_structure.get('child_types') else 'None',
                references=', '.join([p.get('type', '') for p in reference_patterns]) if reference_patterns else 'None'
            )

            if hasattr(sync_client, "chat"):
                response = sync_client.chat.completions.create(
                    model=model_name,
                    max_tokens=150,
                    temperature=0.3,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )
                description = response.choices[0].message.content.strip()
            else:
                import asyncio

                async def _async_call():
                    resp = await sync_client.chat.completions.create(
                        model=model_name,
                        max_tokens=150,
                        temperature=0.3,
                        messages=[{
                            "role": "user",
                            "content": prompt
                        }]
                    )
                    return resp.choices[0].message.content.strip()

                description = asyncio.run(_async_call())

            logger.info(f"Generated description for {node_type}: {description}")
            return description

        except Exception as e:
            logger.warning(f"Failed to generate pattern description: {e}")
            import traceback
            logger.warning(f"Description generation traceback: {traceback.format_exc()}")
            return None

    def find_or_create_pattern(self,
                               spec_version: str,
                               message_root: str,
                               airline_code: str,
                               section_path: str,
                               decision_rule: Dict[str, Any],
                               example_node_fact_id: int) -> Pattern:
        """
        Find existing pattern or create new one.

        Returns:
            NdcPattern instance (either existing or newly created)
        """
        # Generate signature hash
        signature_hash = self.generate_signature_hash(
            decision_rule,
            spec_version,
            section_path
        )

        # Check if pattern already exists (including airline_code)
        existing = self.db_session.query(Pattern).filter(
            Pattern.spec_version == spec_version,
            Pattern.message_root == message_root,
            Pattern.airline_code == airline_code,
            Pattern.signature_hash == signature_hash
        ).first()

        if existing:
            # Update existing pattern
            existing.times_seen += 1
            existing.last_seen_at = datetime.utcnow()

            # Add new example (keep last 5)
            examples = existing.examples or []
            examples.append({
                'node_fact_id': example_node_fact_id,
                'timestamp': datetime.utcnow().isoformat()
            })
            existing.examples = examples[-5:]  # Keep last 5 examples

            logger.info(f"Updated existing pattern {existing.id}: {signature_hash} "
                       f"(times_seen: {existing.times_seen})")

            return existing
        else:
            # Create new pattern
            selector_xpath = self.generate_selector_xpath(
                section_path,
                decision_rule.get('node_type', 'Unknown')
            )

            # Generate LLM-powered description
            description = self._generate_pattern_description(decision_rule, section_path)

            new_pattern = Pattern(
                spec_version=spec_version,
                message_root=message_root,
                airline_code=airline_code,
                section_path=self._normalize_path(section_path, message_root),
                selector_xpath=selector_xpath,
                decision_rule=decision_rule,
                description=description,  # Add generated description
                signature_hash=signature_hash,
                times_seen=1,
                created_by_model=settings.LLM_MODEL,
                examples=[{
                    'node_fact_id': example_node_fact_id,
                    'timestamp': datetime.utcnow().isoformat()
                }],
                created_at=datetime.utcnow(),
                last_seen_at=datetime.utcnow()
            )

            self.db_session.add(new_pattern)

            airline_info = f" - {airline_code}" if airline_code else ""
            desc_info = f" - {description[:50]}..." if description else ""
            logger.info(f"Created new pattern: {signature_hash} for "
                       f"{spec_version}/{message_root}{airline_info}/{section_path}{desc_info}")

            return new_pattern

    def generate_patterns_from_run(self, run_id: str) -> Dict[str, Any]:
        """
        Generate patterns from all NodeFacts in a run (fully automatic).

        Args:
            run_id: Discovery run ID

        Returns:
            Statistics about pattern generation
        """
        logger.info(f"Generating patterns from run: {run_id} (auto-discovery mode)")

        # Get the Run to extract airline_code
        run = self.db_session.query(Run).filter(Run.id == run_id).first()
        if not run:
            logger.warning(f"Run not found: {run_id}")
            return {
                'run_id': run_id,
                'node_facts_analyzed': 0,
                'patterns_created': 0,
                'patterns_updated': 0,
                'errors': []
            }

        airline_code = run.airline_code

        # Get all NodeFacts from this run
        node_facts = self.db_session.query(NodeFact).filter(
            NodeFact.run_id == run_id
        ).all()

        if not node_facts:
            logger.warning(f"No NodeFacts found for run: {run_id}")
            return {
                'run_id': run_id,
                'node_facts_analyzed': 0,
                'patterns_created': 0,
                'patterns_updated': 0,
                'errors': []
            }

        # Group NodeFacts by (spec_version, message_root, section_path, node_type)
        groups = defaultdict(list)

        for nf in node_facts:
            key = (
                nf.spec_version,
                nf.message_root,
                nf.section_path,
                nf.node_type
            )
            groups[key].append({
                'id': nf.id,
                'fact_json': nf.fact_json
            })

        logger.info(f"Grouped {len(node_facts)} NodeFacts into {len(groups)} pattern groups")

        # Generate patterns for each group
        patterns_created = 0
        patterns_updated = 0
        errors = []

        for (spec_version, message_root, section_path, node_type), facts in groups.items():
            try:
                # Extract fact_json from each NodeFact
                fact_jsons = [f['fact_json'] for f in facts]

                # Generate decision rule (all references auto-discovered by LLM)
                decision_rule = self.generate_decision_rule(fact_jsons)

                # Find or create pattern
                pattern = self.find_or_create_pattern(
                    spec_version=spec_version,
                    message_root=message_root,
                    airline_code=airline_code,
                    section_path=section_path,
                    decision_rule=decision_rule,
                    example_node_fact_id=facts[0]['id']  # Use first fact as example
                )

                if pattern.id:
                    # Existing pattern was updated
                    patterns_updated += 1
                else:
                    # New pattern was created
                    patterns_created += 1

            except Exception as e:
                error_msg = f"Failed to generate pattern for {section_path}/{node_type}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        # Commit all pattern changes
        try:
            self.db_session.commit()
            logger.info(f"Pattern generation completed: {patterns_created} created, "
                       f"{patterns_updated} updated")
        except Exception as e:
            self.db_session.rollback()
            error_msg = f"Failed to commit patterns: {e}"
            logger.error(error_msg)
            errors.append(error_msg)

        return {
            'run_id': run_id,
            'node_facts_analyzed': len(node_facts),
            'pattern_groups': len(groups),
            'patterns_created': patterns_created,
            'patterns_updated': patterns_updated,
            'errors': errors,
            'success': len(errors) == 0
        }

    def generate_patterns_from_all_runs(self,
                                       spec_version: Optional[str] = None,
                                       message_root: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate patterns from all NodeFacts across all runs.

        Useful for batch pattern generation after multiple discoveries.
        """
        logger.info("Generating patterns from all runs")

        # Query all NodeFacts
        query = self.db_session.query(NodeFact)

        if spec_version:
            query = query.filter(NodeFact.spec_version == spec_version)
        if message_root:
            query = query.filter(NodeFact.message_root == message_root)

        all_facts = query.all()

        if not all_facts:
            return {
                'node_facts_analyzed': 0,
                'patterns_created': 0,
                'patterns_updated': 0,
                'errors': []
            }

        # Group by (spec_version, message_root, section_path, node_type)
        groups = defaultdict(list)

        for nf in all_facts:
            key = (
                nf.spec_version,
                nf.message_root,
                nf.section_path,
                nf.node_type
            )
            groups[key].append({
                'id': nf.id,
                'fact_json': nf.fact_json
            })

        logger.info(f"Grouped {len(all_facts)} NodeFacts into {len(groups)} pattern groups")

        # Generate patterns
        patterns_created = 0
        patterns_updated = 0
        errors = []

        for (spec_version, message_root, section_path, node_type), facts in groups.items():
            try:
                fact_jsons = [f['fact_json'] for f in facts]
                decision_rule = self.generate_decision_rule(fact_jsons)

                pattern = self.find_or_create_pattern(
                    spec_version=spec_version,
                    message_root=message_root,
                    section_path=section_path,
                    decision_rule=decision_rule,
                    example_node_fact_id=facts[0]['id']
                )

                if pattern.id:
                    patterns_updated += 1
                else:
                    patterns_created += 1

            except Exception as e:
                error_msg = f"Failed to generate pattern for {section_path}/{node_type}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        # Commit
        try:
            self.db_session.commit()
            logger.info(f"Batch pattern generation completed: {patterns_created} created, "
                       f"{patterns_updated} updated")
        except Exception as e:
            self.db_session.rollback()
            error_msg = f"Failed to commit patterns: {e}"
            logger.error(error_msg)
            errors.append(error_msg)

        return {
            'node_facts_analyzed': len(all_facts),
            'pattern_groups': len(groups),
            'patterns_created': patterns_created,
            'patterns_updated': patterns_updated,
            'errors': errors,
            'success': len(errors) == 0
        }


def create_pattern_generator(db_session: Session) -> PatternGenerator:
    """Create pattern generator instance."""
    return PatternGenerator(db_session)
