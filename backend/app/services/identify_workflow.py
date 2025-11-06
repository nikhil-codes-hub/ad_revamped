"""
Identify workflow for AssistedDiscovery.

Matches new XML NodeFacts against saved patterns to identify known structures.
Implements Phase 3: Pattern Identification.
"""

import logging
import uuid
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
from collections import defaultdict

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.database import Run, RunKind, RunStatus, NodeFact, Pattern, PatternMatch
from app.services.xml_parser import detect_ndc_version_fast
from app.services.discovery_workflow import DiscoveryWorkflow
from app.services.pattern_generator import PatternGenerator
from app.services.llm_extractor import get_llm_extractor
from app.services.utils import normalize_iata_prefix

logger = logging.getLogger(__name__)


class IdentifyWorkflow:
    """Orchestrates the identify process: extract NodeFacts and match against patterns."""

    def __init__(self, db_session: Session):
        """Initialize identify workflow."""
        self.db_session = db_session
        self.discovery = DiscoveryWorkflow(db_session)
        self.pattern_gen = PatternGenerator(db_session)

    @staticmethod
    def _normalize_node_type(node_type: Optional[str]) -> str:
        """Normalize node type names for flexible matching and comparison."""
        if not node_type:
            return ""

        nt = node_type.lower()

        # Only normalize explicit synonyms; keep other types distinct
        if nt in {'paxlist', 'passengerlist'}:
            return 'pax_list'
        if nt in {'paxjourneylist', 'passengerjourneylist'}:
            return 'pax_journey_list'
        if nt in {'paxsegmentlist', 'passengersegmentlist'}:
            return 'pax_segment_list'

        return nt

    def calculate_pattern_similarity(self,
                                     node_fact_structure: Dict[str, Any],
                                     pattern_decision_rule: Dict[str, Any]) -> float:
        """
        Calculate similarity score between a NodeFact structure and a Pattern decision rule.

        Returns:
            Float between 0.0 and 1.0 representing similarity
        """
        score = 0.0
        total_weight = 0.0

        # 1. Node type match (HARD REQUIREMENT - 30% weight)
        # Support name variations: PaxList, PassengerList, etc.
        weight_node_type = 0.3
        total_weight += weight_node_type

        pattern_node = self._normalize_node_type(pattern_decision_rule.get('node_type'))
        fact_node = self._normalize_node_type(node_fact_structure.get('node_type'))

        node_type_matches = (pattern_node == fact_node) or \
                           (node_fact_structure.get('node_type') == pattern_decision_rule.get('node_type'))

        if node_type_matches:
            score += weight_node_type
        else:
            # Node type mismatch - cap final score at 20% regardless of other matches
            # This prevents matching completely different node types
            pass  # Score remains 0 for this component

        # 2. Must-have attributes match (30% weight)
        weight_must_have = 0.3
        total_weight += weight_must_have

        pattern_must_have = set(pattern_decision_rule.get('must_have_attributes', []))
        pattern_optional = set(pattern_decision_rule.get('optional_attributes', []))

        # Filter out metadata fields that are added during extraction
        # These are NOT real XML attributes and should not be compared
        METADATA_FIELDS = {'summary', 'child_count', 'confidence', 'node_ordinal'}
        all_fact_attributes = set(node_fact_structure.get('attributes', {}).keys())
        fact_attributes = all_fact_attributes - METADATA_FIELDS

        # Calculate match score based on required attributes
        if pattern_must_have:
            must_have_match = len(pattern_must_have & fact_attributes) / len(pattern_must_have)
            score += weight_must_have * must_have_match
        else:
            # No required attributes - start with full score
            score += weight_must_have

        # PENALTY: Reduce score for extra unexpected attributes
        # Extra = attributes in NodeFact that are NOT in pattern's required OR optional lists
        expected_all_attributes = pattern_must_have | pattern_optional
        extra_attributes = fact_attributes - expected_all_attributes

        if extra_attributes and expected_all_attributes:
            # Penalize 10% per extra attribute (cap at 30% total penalty)
            extra_penalty = min(0.3, len(extra_attributes) * 0.10)
            score -= extra_penalty
            logger.info(f"Found {len(extra_attributes)} unexpected attribute(s): {extra_attributes}. Applying {extra_penalty*100:.0f}% penalty.")

        # 3. Child structure match (25% weight)
        weight_child = 0.25
        total_weight += weight_child

        pattern_child = pattern_decision_rule.get('child_structure', {})
        fact_children = node_fact_structure.get('children', [])

        if pattern_child.get('has_children'):
            if fact_children:
                # Both have children
                pattern_is_container = pattern_child.get('is_container', False)
                fact_is_container = isinstance(fact_children[0], dict) if fact_children else False

                if pattern_is_container == fact_is_container:
                    score += weight_child * 0.5

                    # Check child types if container
                    # Support name variations: Pax, Passenger, etc.
                    if pattern_is_container and fact_is_container:
                        def normalize_child_type(child_type):
                            """Normalize child type names for flexible matching."""
                            if not child_type:
                                return ""
                            ct = child_type.lower()

                            # Only normalize exact synonyms
                            if ct in ['pax', 'passenger']:
                                return 'pax'
                            elif ct in ['paxjourney', 'passengerjourney']:
                                return 'pax_journey'
                            elif ct in ['paxsegment', 'passengersegment']:
                                return 'pax_segment'

                            return ct

                        # Normalize both pattern and fact child types
                        pattern_types = set(normalize_child_type(t) for t in pattern_child.get('child_types', []))
                        fact_types = set(normalize_child_type(child.get('node_type', '')) for child in fact_children)

                        if pattern_types and fact_types:
                            type_overlap = len(pattern_types & fact_types) / len(pattern_types | fact_types)
                            score += weight_child * 0.5 * type_overlap
                        else:
                            score += weight_child * 0.5
        else:
            # Pattern has no children
            if not fact_children:
                score += weight_child

        # 4. Reference patterns match (15% weight)
        # CRITICAL: Must match relationship types AND directions (airline-specific!)
        weight_refs = 0.15
        total_weight += weight_refs

        pattern_refs = pattern_decision_rule.get('reference_patterns', [])
        fact_relationships = node_fact_structure.get('relationships', [])

        if pattern_refs:
            if fact_relationships:
                # Build relationship signatures including direction (type + direction)
                # This ensures INF→ADT doesn't match ADT→INF (airline-specific!)
                def get_ref_signature(ref):
                    """Create unique signature for relationship including direction."""
                    ref_type = ref.get('type', '')
                    direction = ref.get('direction', '')
                    # For infant_parent, direction is CRITICAL (varies by airline)
                    if ref_type == 'infant_parent' and direction:
                        return f"{ref_type}:{direction}"
                    return ref_type

                pattern_ref_sigs = set(get_ref_signature(r) for r in pattern_refs)
                fact_ref_sigs = set(get_ref_signature(r) for r in fact_relationships)

                # Calculate overlap - must match both type AND direction
                if pattern_ref_sigs:
                    ref_overlap = len(pattern_ref_sigs & fact_ref_sigs) / len(pattern_ref_sigs)
                    score += weight_refs * ref_overlap
                else:
                    score += weight_refs
        else:
            # No reference patterns required
            score += weight_refs

        # Normalize score
        normalized_score = min(1.0, score / total_weight) if total_weight > 0 else 0.0

        # CRITICAL: If node types don't match, cap the score at 20%
        # This prevents PaxSegmentList from matching BaggageAllowanceList
        if not node_type_matches:
            normalized_score = min(normalized_score, 0.20)

        # 5. VALIDATION: Check for relationship mismatches
        # Compare actual relationships vs pattern's expected relationships
        # Only penalize MISMATCHES (not expected broken relationships!)
        expected_relationships = pattern_decision_rule.get('expected_relationships', [])

        if expected_relationships:
            # Pattern has expected relationships - compare actual vs expected
            fact_relationships = node_fact_structure.get('relationships', [])

            # Build lookup map: target_section_path -> actual relationship
            actual_rel_map = {}
            for rel in fact_relationships:
                target = rel.get('target_section_path', '')
                actual_rel_map[target] = rel

            # Check for mismatches
            mismatch_count = 0
            for expected in expected_relationships:
                target = expected.get('target_section_path', '')
                expected_valid = bool(expected.get('is_valid', True))  # Ensure boolean

                # Find corresponding actual relationship
                actual = actual_rel_map.get(target)

                if actual:
                    actual_valid = bool(actual.get('is_valid', True))  # Ensure boolean

                    # Mismatch: expected valid but got broken, or expected broken but got valid
                    if expected_valid != actual_valid:
                        mismatch_count += 1
                        logger.debug(f"Relationship mismatch for {target}: "
                                   f"expected is_valid={expected_valid} ({type(expected_valid).__name__}), "
                                   f"actual is_valid={actual_valid} ({type(actual_valid).__name__})")
                else:
                    # Expected relationship is missing - this is also a mismatch
                    mismatch_count += 1
                    logger.debug(f"Expected relationship to {target} is missing")

            if mismatch_count > 0:
                # Penalize relationship mismatches - 30% per mismatch
                penalty = min(0.6, mismatch_count * 0.3)  # Cap at 60% penalty
                normalized_score = normalized_score * (1.0 - penalty)
                logger.warning(f"Node has {mismatch_count} relationship mismatch(es), applying {penalty*100:.0f}% penalty. "
                             f"Original score: {normalized_score/(1.0-penalty):.2f}, New score: {normalized_score:.2f}")
        else:
            # Pattern has NO expected relationships - use old logic for backward compatibility
            fact_relationships = node_fact_structure.get('relationships', [])
            if fact_relationships:
                broken_count = sum(1 for rel in fact_relationships if not rel.get('is_valid', True))
                if broken_count > 0:
                    # Penalize broken relationships - reduce score by 30% per broken relationship
                    penalty = min(0.6, broken_count * 0.3)  # Cap at 60% penalty
                    normalized_score = normalized_score * (1.0 - penalty)
                    logger.warning(f"Node has {broken_count} broken relationship(s) (pattern has no expected relationships), "
                                 f"applying {penalty*100:.0f}% penalty. "
                                 f"Original score: {normalized_score/(1.0-penalty):.2f}, New score: {normalized_score:.2f}")

        return normalized_score

    def match_node_fact_to_patterns(self,
                                     node_fact: NodeFact,
                                     spec_version: str,
                                     message_root: str,
                                     airline_code: Optional[str] = None,
                                     allow_cross_airline: bool = False) -> List[Dict[str, Any]]:
        """
        Match a single NodeFact against all patterns for the same version and airline.

        Args:
            node_fact: NodeFact to match
            spec_version: NDC version to match against
            message_root: Message root to match against
            airline_code: Airline code to match against (can be None)
            allow_cross_airline: If True, match against patterns from all airlines

        Returns:
            List of matches with confidence scores
        """
        from app.models.database import NodeRelationship

        # Query patterns for same version/message/airline (VERSION & AIRLINE FILTERED!)
        # Only match against active patterns (not superseded)
        query = self.db_session.query(Pattern).filter(
            Pattern.spec_version == spec_version,
            Pattern.message_root == message_root,
            Pattern.superseded_by.is_(None)  # Exclude superseded patterns
        )

        # Filter by airline_code if provided AND cross-airline mode is disabled
        if airline_code and not allow_cross_airline:
            query = query.filter(Pattern.airline_code == airline_code)

        patterns = query.all()

        airline_info = f"/{airline_code}" if airline_code and not allow_cross_airline else ""
        cross_airline_info = " (cross-airline mode)" if allow_cross_airline else ""
        if not patterns:
            logger.info(f"No patterns found for {spec_version}/{message_root}{airline_info}{cross_airline_info}")
            return []

        if allow_cross_airline:
            logger.info(f"Cross-airline matching enabled: found {len(patterns)} patterns across all airlines for {spec_version}/{message_root}")

        # Query ALL relationships for this NodeFact from database
        all_relationships = self.db_session.query(NodeRelationship).filter(
            NodeRelationship.source_node_fact_id == node_fact.id
        ).all()

        # Build relationships list for fact_structure
        relationships_list = []
        broken_count = 0
        for rel in all_relationships:
            relationships_list.append({
                'target_section_path': rel.target_section_path,
                'target_node_type': rel.target_node_type,
                'reference_type': rel.reference_type,
                'is_valid': rel.is_valid
            })
            if not rel.is_valid:
                broken_count += 1

        if broken_count > 0:
            logger.warning(f"NodeFact {node_fact.id} ({node_fact.node_type}) has {broken_count} broken relationship(s)")

        matches = []

        fact_structure = node_fact.fact_json
        if isinstance(fact_structure, str):
            try:
                fact_structure = json.loads(fact_structure)
            except json.JSONDecodeError:
                logger.warning("Failed to decode NodeFact fact_json for node %s", node_fact.id)
                fact_structure = {}

        # Add relationships to fact_structure for comparison
        fact_structure['relationships'] = relationships_list

        fact_node_normalized = self._normalize_node_type(
            fact_structure.get('node_type') or node_fact.node_type
        )
        fact_section_normalized = normalize_iata_prefix(
            (node_fact.section_path or "").strip("/"),
            message_root or ""
        ).strip("/").lower()

        for pattern in patterns:
            pattern_decision_rule = pattern.decision_rule or {}

            pattern_node_normalized = self._normalize_node_type(
                pattern_decision_rule.get('node_type')
            )

            node_type_override = False

            # Skip patterns with incompatible node types to avoid unrelated matches
            if fact_node_normalized and pattern_node_normalized and fact_node_normalized != pattern_node_normalized:
                pattern_section_normalized = normalize_iata_prefix(
                    (pattern.section_path or "").strip("/"),
                    message_root or ""
                ).strip("/").lower()

                # Allow mismatched node types when section path is identical (signals structural differences)
                if pattern_section_normalized and pattern_section_normalized == fact_section_normalized:
                    node_type_override = True
                else:
                    continue

            # Calculate similarity
            confidence = self.calculate_pattern_similarity(
                fact_structure,
                pattern_decision_rule
            )

            if node_type_override:
                # Ensure mismatch-driven comparisons remain low confidence
                confidence = min(confidence, 0.4)

            # Relationship penalties are now handled inside calculate_pattern_similarity()
            # by comparing actual relationships vs expected relationships from the pattern

            # Determine verdict based on confidence
            if confidence >= 0.95:
                verdict = "EXACT_MATCH"
            elif confidence >= 0.85:
                verdict = "HIGH_MATCH"
            elif confidence >= 0.70:
                verdict = "PARTIAL_MATCH"
            elif confidence >= 0.50:
                verdict = "LOW_MATCH"
            else:
                verdict = "NO_MATCH"

            matches.append({
                'pattern_id': pattern.id,
                'pattern': pattern,
                'confidence': confidence,
                'verdict': verdict
            })

        # Sort by confidence (highest first)
        matches.sort(key=lambda x: x['confidence'], reverse=True)

        return matches

    def get_quick_explanation(self,
                              node_fact: NodeFact,
                              pattern: Optional[Pattern],
                              confidence: float,
                              verdict: str) -> str:
        """
        Generate quick template-based explanation for business analysts.

        Returns business-friendly explanation without using LLM.
        """
        node_type = node_fact.node_type or "Unknown"

        if verdict == "NEW_PATTERN":
            return f"🆕 New pattern discovered: '{node_type}' structure has not been seen before in the pattern library."

        if not pattern:
            return f"❓ No matching pattern found for '{node_type}'."

        airline_info = f" ({pattern.airline_code})" if pattern.airline_code else ""

        if verdict == "EXACT_MATCH":
            return f"✅ Perfect match: '{node_type}' exactly matches the expected{airline_info} pattern with {confidence*100:.0f}% confidence."

        elif verdict == "HIGH_MATCH":
            return f"✅ Strong match: '{node_type}' closely matches the expected{airline_info} pattern with {confidence*100:.0f}% confidence."

        elif verdict == "PARTIAL_MATCH":
            return f"⚠️ Partial match: '{node_type}' partially matches the expected{airline_info} pattern ({confidence*100:.0f}% confidence). Some differences detected. Click 'Explain' for details."

        elif verdict == "LOW_MATCH":
            return f"⚠️ Low confidence match: '{node_type}' has only {confidence*100:.0f}% similarity to the expected{airline_info} pattern. Click 'Explain' for details."

        elif verdict == "NO_MATCH":
            return f"❌ Does not match: '{node_type}' does not match the expected{airline_info} pattern. Click 'Explain' for details."

        return f"'{node_type}' evaluated against pattern with {confidence*100:.0f}% confidence."

    def store_pattern_match(self,
                           run_id: str,
                           node_fact: NodeFact,
                           pattern_id: Optional[int],
                           confidence: float,
                           verdict: str,
                           quick_explanation: str = "",
                           quality_checks: Optional[Dict[str, Any]] = None):
        """Store pattern match result in database."""
        match_metadata = {
            'quick_explanation': quick_explanation
        }
        if isinstance(quality_checks, dict):
            match_metadata['quality_checks'] = quality_checks

        pattern_match = PatternMatch(
            run_id=run_id,
            node_fact_id=node_fact.id,
            pattern_id=pattern_id,
            confidence=confidence,
            verdict=verdict,
            match_metadata=match_metadata
        )

        self.db_session.add(pattern_match)

    def run_identify(self,
                     xml_file_path: str,
                     target_version: Optional[str] = None,
                     target_message_root: Optional[str] = None,
                     target_airline_code: Optional[str] = None,
                     allow_cross_airline: bool = False) -> Dict[str, Any]:
        """
        Run identify workflow on new XML file.

        Phase 1: Extract NodeFacts (reuse Discovery extraction)
        Phase 2: Match NodeFacts against saved patterns
        Phase 3: Generate gap analysis report

        Args:
            xml_file_path: Path to XML file to identify
            target_version: Optional specific NDC version to match against (e.g., "18.1")
            target_message_root: Optional specific message root to match against (e.g., "OrderViewRS")
            target_airline_code: Optional specific airline code to match against (e.g., "SQ", "AF")
            allow_cross_airline: If True, match against patterns from all airlines (default: False)

        Returns:
            Dict with identification results
        """
        logger.info(f"Starting identify workflow: {xml_file_path}")

        file_path = Path(xml_file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"XML file not found: {xml_file_path}")

        # Detect version first
        version_info = detect_ndc_version_fast(xml_file_path)

        if not version_info or not version_info.spec_version:
            raise ValueError("Could not detect NDC version from XML file")

        spec_version = version_info.spec_version
        message_root = version_info.message_root
        airline_code = version_info.airline_code

        # Use target filters if provided, otherwise use detected values
        match_version = target_version if target_version else spec_version
        match_message_root = target_message_root if target_message_root else message_root
        match_airline_code = target_airline_code if target_airline_code else airline_code

        logger.info(f"Detected: {spec_version}/{message_root} - Airline: {airline_code or 'N/A'}")
        if target_version or target_message_root or target_airline_code:
            logger.info(f"Matching against: {match_version}/{match_message_root} - Airline: {match_airline_code or 'N/A'}")
        if allow_cross_airline:
            logger.info(f"Cross-airline matching ENABLED - will match against patterns from all airlines")

        # PHASE 1: Extract NodeFacts (reuse Discovery workflow but mark as IDENTIFY run)
        logger.info("Phase 1: Extracting NodeFacts from XML")

        # Run discovery extraction but SKIP pattern generation (Identify only matches, doesn't create patterns)
        discovery_results = self.discovery.run_discovery(xml_file_path, skip_pattern_generation=True)

        run_id = discovery_results['run_id']

        # Update run kind to IDENTIFY
        run = self.db_session.query(Run).filter(Run.id == run_id).first()
        if run:
            run.kind = RunKind.IDENTIFY
            self.db_session.commit()

        node_facts_extracted = discovery_results.get('node_facts_extracted', 0)

        if node_facts_extracted == 0:
            logger.warning("No NodeFacts extracted from XML")
            return {
                'run_id': run_id,
                'status': 'completed',
                'spec_version': spec_version,
                'message_root': message_root,
                'node_facts_extracted': 0,
                'matches': [],
                'gap_analysis': {
                    'new_patterns': 0,
                    'unmatched_facts': 0,
                    'total_node_facts': 0,
                    'matched_facts': 0,
                    'match_rate': 0
                },
                'started_at': discovery_results.get('started_at'),
                'finished_at': datetime.utcnow().isoformat(),
                'file_size_bytes': discovery_results.get('file_size_bytes'),
                'subtrees_processed': discovery_results.get('subtrees_processed', 0),
                'version_info': {
                    'spec_version': spec_version,
                    'message_root': message_root
                }
            }

        # PHASE 2: Match NodeFacts against patterns
        logger.info(f"Phase 2: Matching {node_facts_extracted} NodeFacts against patterns")

        node_facts = self.db_session.query(NodeFact).filter(
            NodeFact.run_id == run_id
        ).all()

        match_results = []
        matched_count = 0
        high_confidence_count = 0
        new_patterns_count = 0
        quality_issue_count = 0
        quality_coverage_total = 0.0
        quality_alerts: List[Dict[str, Any]] = []

        for nf in node_facts:
            fact_payload = nf.fact_json if isinstance(nf.fact_json, dict) else {}
            if not isinstance(fact_payload, dict):
                try:
                    fact_payload = json.loads(nf.fact_json or "{}")
                except (TypeError, json.JSONDecodeError):
                    fact_payload = {}

            quality_checks = fact_payload.get('quality_checks') or {}
            if isinstance(quality_checks, dict):
                quality_checks = dict(quality_checks)  # shallow copy for safe mutation
            else:
                quality_checks = {}

            quality_status = str(quality_checks.get('status', 'ok')).lower()
            missing_elements = quality_checks.get('missing_elements') or []
            if not isinstance(missing_elements, list):
                missing_elements = [missing_elements]

            match_percentage = quality_checks.get('match_percentage')
            if match_percentage is None:
                match_percentage = 0 if quality_status == 'error' else 100
            try:
                match_percentage_value = float(match_percentage)
            except (TypeError, ValueError):
                match_percentage_value = 0.0 if quality_status == 'error' else 100.0
            quality_checks['match_percentage'] = match_percentage_value
            match_percentage = match_percentage_value

            quality_coverage_total += match_percentage

            quality_summary = ""
            if missing_elements:
                details = []
                for item in missing_elements:
                    if isinstance(item, dict):
                        path = item.get('path', 'unknown path')
                        reason = item.get('reason', 'unspecified reason')
                        details.append(f"{path} ({reason})")
                    else:
                        details.append(str(item))
                quality_summary = "; ".join(details)

            matches = self.match_node_fact_to_patterns(
                nf,
                match_version,
                match_message_root,
                match_airline_code,
                allow_cross_airline=allow_cross_airline
            )

            if matches:
                # Use best match
                best_match = matches[0]

                # ATTRIBUTE COMPARISON: Check if pattern's required_attributes exist in NodeFact
                # This catches missing fields that the LLM didn't detect during extraction
                pattern = best_match['pattern']
                pattern_decision_rule = pattern.decision_rule or {}

                # Get child structures from pattern (for container nodes like DatedOperatingSegmentList)
                pattern_child_structures = pattern_decision_rule.get('child_structure', {}).get('child_structures', [])

                # For container nodes, check child attributes
                if pattern_child_structures and fact_payload.get('children'):
                    for child_struct_pattern in pattern_child_structures:
                        required_child_attrs = set(child_struct_pattern.get('required_attributes', []))

                        # Check each child instance in the NodeFact
                        children = fact_payload.get('children', [])
                        for idx, child in enumerate(children):
                            if not isinstance(child, dict):
                                continue

                            child_attrs = child.get('attributes', {})
                            # Filter out metadata fields
                            METADATA_FIELDS = {'summary', 'child_count', 'confidence', 'node_ordinal', 'missing_elements'}
                            actual_child_attrs = set(child_attrs.keys()) - METADATA_FIELDS

                            # Helper function for fuzzy attribute matching (handles LLM normalization)
                            def attrs_match_fuzzy(pattern_attr: str, actual_attrs: set) -> bool:
                                """Check if pattern attribute exists in actual attributes (with fuzzy matching)."""
                                # Exact match
                                if pattern_attr in actual_attrs:
                                    return True

                                # Normalize both to lowercase for comparison
                                pattern_lower = pattern_attr.lower()

                                for actual_attr in actual_attrs:
                                    actual_lower = actual_attr.lower()

                                    # Case-insensitive exact match
                                    if pattern_lower == actual_lower:
                                        return True

                                    # Semantic equivalents (e.g., "distance" <-> "DistanceMeasure")
                                    # Check if one is contained in the other
                                    if pattern_lower in actual_lower or actual_lower in pattern_lower:
                                        # Additional check: ensure they're semantically related
                                        # "distance" should match "DistanceMeasure" but not "distant_code"
                                        if len(pattern_lower) >= 4 and len(actual_lower) >= 4:
                                            # Check if the shorter term is a significant substring of the longer
                                            shorter = pattern_lower if len(pattern_lower) < len(actual_lower) else actual_lower
                                            longer = actual_lower if shorter == pattern_lower else pattern_lower

                                            # If shorter is at least 4 chars and starts the longer, it's a match
                                            if longer.startswith(shorter):
                                                return True

                                            # Special case: normalized names like "duration" matches "Duration"
                                            # (already covered by case-insensitive check above)

                                return False

                            # Find missing required attributes (with fuzzy matching to handle LLM normalization)
                            missing_attrs = set()
                            for required_attr in required_child_attrs - METADATA_FIELDS:
                                if not attrs_match_fuzzy(required_attr, actual_child_attrs):
                                    missing_attrs.add(required_attr)

                            if missing_attrs:
                                # Add to missing_elements
                                child_node_type = child.get('node_type', 'Unknown')
                                child_ordinal = child.get('ordinal', idx + 1)
                                child_path = f"{nf.node_type}[1]/{child_node_type}[{child_ordinal}]"

                                for missing_attr in missing_attrs:
                                    missing_elements.append({
                                        'path': f"{child_path}/{missing_attr}",
                                        'reason': f"Required attribute '{missing_attr}' not found in {child_node_type}"
                                    })

                                # Update quality checks
                                if not quality_checks.get('missing_elements'):
                                    quality_checks['missing_elements'] = []
                                quality_checks['missing_elements'].extend(missing_elements)
                                quality_checks['status'] = 'error'

                                # Recalculate match percentage
                                total_children = len(children)
                                children_with_issues = len([c for c in children if any(
                                    attr not in (set(c.get('attributes', {}).keys()) - METADATA_FIELDS)
                                    for attr in required_child_attrs - METADATA_FIELDS
                                )])
                                match_percentage = ((total_children - children_with_issues) / total_children * 100) if total_children > 0 else 0
                                quality_checks['match_percentage'] = match_percentage
                                quality_status = 'error'

                # Generate quick explanation
                quick_explanation = self.get_quick_explanation(
                    node_fact=nf,
                    pattern=best_match['pattern'],
                    confidence=best_match['confidence'],
                    verdict=best_match['verdict']
                )

                if quality_status == 'error':
                    quality_issue_count += 1
                    quality_alerts.append({
                        'node_fact_id': nf.id,
                        'node_type': nf.node_type,
                        'section_path': nf.section_path,
                        'match_percentage': match_percentage,
                        'missing_elements': missing_elements,
                        'quality_checks': quality_checks
                    })

                    adjusted_confidence = best_match['confidence']
                    if match_percentage is not None:
                        adjusted_confidence = min(adjusted_confidence, max(match_percentage, 0) / 100.0)
                        best_match['confidence'] = adjusted_confidence

                    best_match['verdict'] = 'QUALITY_BREAK'

                    if quality_summary:
                        quick_explanation = (
                            f"{quick_explanation} ⚠️ Quality break detected: {quality_summary}."
                        )
                    else:
                        quick_explanation = (
                            f"{quick_explanation} ⚠️ Quality break detected: Missing required content."
                        )

                # Store match
                self.store_pattern_match(
                    run_id=run_id,
                    node_fact=nf,
                    pattern_id=best_match['pattern_id'],
                    confidence=best_match['confidence'],
                    verdict=best_match['verdict'],
                    quick_explanation=quick_explanation,
                    quality_checks=quality_checks
                )

                match_results.append({
                    'node_fact_id': nf.id,
                    'node_type': nf.node_type,
                    'section_path': nf.section_path,
                    'quality_checks': quality_checks,
                    'best_match': {
                        'pattern_id': best_match['pattern_id'],
                        'confidence': best_match['confidence'],
                        'verdict': best_match['verdict'],
                        'quality_checks': quality_checks
                    },
                    'all_matches': [
                        {
                            'pattern_id': m['pattern_id'],
                            'confidence': m['confidence'],
                            'verdict': m['verdict']
                        }
                        for m in matches[:5]  # Top 5 matches
                    ]
                })

                if best_match['confidence'] >= 0.70 and quality_status != 'error':
                    matched_count += 1
                if best_match['confidence'] >= 0.85 and quality_status != 'error':
                    high_confidence_count += 1

                # Update pattern times_seen for high confidence matches
                if best_match['confidence'] >= 0.85:
                    pattern = best_match['pattern']
                    pattern.times_seen += 1
                    pattern.last_seen_at = datetime.utcnow()

            else:
                # No patterns found - this is a NEW pattern
                new_patterns_count += 1

                # Generate quick explanation for new pattern
                quick_explanation = self.get_quick_explanation(
                    node_fact=nf,
                    pattern=None,
                    confidence=0.0,
                    verdict="NEW_PATTERN"
                )

                if quality_status == 'error':
                    quality_issue_count += 1
                    quality_alerts.append({
                        'node_fact_id': nf.id,
                        'node_type': nf.node_type,
                        'section_path': nf.section_path,
                        'match_percentage': match_percentage,
                        'missing_elements': missing_elements,
                        'quality_checks': quality_checks
                    })

                    if quality_summary:
                        quick_explanation = (
                            f"{quick_explanation} ⚠️ Quality break detected: {quality_summary}."
                        )
                    else:
                        quick_explanation = (
                            f"{quick_explanation} ⚠️ Quality break detected: Missing required content."
                        )

                self.store_pattern_match(
                    run_id=run_id,
                    node_fact=nf,
                    pattern_id=None,
                    confidence=0.0,
                    verdict="NEW_PATTERN",
                    quick_explanation=quick_explanation,
                    quality_checks=quality_checks
                )

                match_results.append({
                    'node_fact_id': nf.id,
                    'node_type': nf.node_type,
                    'section_path': nf.section_path,
                    'best_match': None,
                    'verdict': 'NEW_PATTERN',
                    'quality_checks': quality_checks
                })

        # Commit all pattern matches
        self.db_session.commit()

        # PHASE 3: Gap Analysis
        logger.info("Phase 3: Generating gap analysis")

        confidence_match_rate = (matched_count / node_facts_extracted * 100) if node_facts_extracted > 0 else 0
        quality_match_rate = (quality_coverage_total / node_facts_extracted) if node_facts_extracted > 0 else 0
        effective_match_rate = quality_match_rate if quality_issue_count > 0 else confidence_match_rate

        # PHASE 3.1: Identify MISSING patterns (patterns in library but NOT in uploaded XML)
        logger.info("Phase 3.1: Identifying missing patterns from uploaded XML")

        # Get all expected patterns for this version/message/airline
        # Only include active patterns (not superseded)
        expected_patterns_query = self.db_session.query(Pattern).filter(
            Pattern.spec_version == match_version,
            Pattern.message_root == match_message_root,
            Pattern.superseded_by.is_(None)  # Exclude superseded patterns
        )
        if match_airline_code:
            expected_patterns_query = expected_patterns_query.filter(Pattern.airline_code == match_airline_code)

        all_expected_patterns = expected_patterns_query.all()

        # Build set of node types that were matched (deduplicate by node type, not pattern ID)
        # This prevents showing "DatedMarketingSegmentList missing" when one version was matched
        matched_node_types = set()
        for match in match_results:
            if match.get('best_match') and match['best_match'].get('pattern_id'):
                pattern_id = match['best_match']['pattern_id']
                # Get the pattern to extract node type
                matched_pattern = self.db_session.query(Pattern).filter(Pattern.id == pattern_id).first()
                if matched_pattern and matched_pattern.decision_rule:
                    node_type = matched_pattern.decision_rule.get('node_type')
                    if node_type:
                        matched_node_types.add(node_type)

        # Find patterns that were NOT matched (missing from uploaded XML)
        # Deduplicate by node_type to avoid showing duplicates
        missing_patterns = []
        seen_node_types = set()
        for pattern in all_expected_patterns:
            decision_rule = pattern.decision_rule or {}
            node_type = decision_rule.get('node_type', 'Unknown')

            # Skip if this node type was already matched or already added to missing list
            if node_type in matched_node_types or node_type in seen_node_types:
                continue

            seen_node_types.add(node_type)
            missing_patterns.append({
                'pattern_id': pattern.id,
                'node_type': node_type,
                'section_path': pattern.section_path,
                'airline_code': pattern.airline_code,
                'times_seen': pattern.times_seen,
                'last_seen_at': pattern.last_seen_at.isoformat() if pattern.last_seen_at else None,
                'must_have_attributes': decision_rule.get('must_have_attributes', []),
                'has_children': decision_rule.get('child_structure', {}).get('has_children', False)
                })

        missing_patterns_count = len(missing_patterns)
        logger.info(f"Found {missing_patterns_count} patterns in library that are missing from uploaded XML")

        gap_analysis = {
            'total_node_facts': node_facts_extracted,
            'matched_facts': matched_count,
            'high_confidence_matches': high_confidence_count,
            'new_patterns': new_patterns_count,
            'unmatched_facts': node_facts_extracted - matched_count,
            'quality_breaks': quality_issue_count,
            'match_rate': effective_match_rate,
            'quality_match_rate': quality_match_rate,
            'confidence_match_rate': confidence_match_rate,
            'high_confidence_rate': (high_confidence_count / node_facts_extracted * 100) if node_facts_extracted > 0 else 0,
            'quality_alerts': quality_alerts,
            'missing_patterns': missing_patterns,
            'missing_patterns_count': missing_patterns_count,
            'total_expected_patterns': len(all_expected_patterns),
            'pattern_coverage_rate': ((len(all_expected_patterns) - missing_patterns_count) / len(all_expected_patterns) * 100) if len(all_expected_patterns) > 0 else 0
        }

        # Update run with summary AND set finished_at timestamp
        if run:
            run.metadata_json = {
                **run.metadata_json,
                'identify_results': {
                    'matches': matched_count,
                    'new_patterns': new_patterns_count,
                    'match_rate': gap_analysis['match_rate'],
                    'quality_breaks': quality_issue_count
                },
                'allow_cross_airline': allow_cross_airline
            }
            run.status = RunStatus.COMPLETED
            run.finished_at = datetime.utcnow()
            self.db_session.commit()

        results = {
            'run_id': run_id,
            'status': 'completed',
            'spec_version': spec_version,
            'message_root': message_root,
            'node_facts_extracted': node_facts_extracted,
            'matches': match_results,
            'gap_analysis': gap_analysis,
            'started_at': discovery_results.get('started_at'),
            'finished_at': datetime.utcnow().isoformat(),
            'file_size_bytes': discovery_results.get('file_size_bytes'),
            'subtrees_processed': discovery_results.get('subtrees_processed', 0),
            'version_info': {
                'spec_version': spec_version,
                'message_root': message_root
            }
        }

        logger.info(f"Identify workflow completed: {run_id} - "
                   f"Matched: {matched_count}/{node_facts_extracted}, "
                   f"New: {new_patterns_count}, "
                   f"Match rate: {gap_analysis['match_rate']:.1f}%")

        return results


def create_identify_workflow(db_session: Session) -> IdentifyWorkflow:
    """Create identify workflow instance."""
    return IdentifyWorkflow(db_session)
