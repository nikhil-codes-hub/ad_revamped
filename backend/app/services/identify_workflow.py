"""
Identify workflow for AssistedDiscovery.

Matches new XML NodeFacts against saved patterns to identify known structures.
Implements Phase 3: Pattern Identification.
"""

import logging
import uuid
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

logger = logging.getLogger(__name__)


class IdentifyWorkflow:
    """Orchestrates the identify process: extract NodeFacts and match against patterns."""

    def __init__(self, db_session: Session):
        """Initialize identify workflow."""
        self.db_session = db_session
        self.discovery = DiscoveryWorkflow(db_session)
        self.pattern_gen = PatternGenerator(db_session)

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
        weight_node_type = 0.3
        total_weight += weight_node_type

        node_type_matches = node_fact_structure.get('node_type') == pattern_decision_rule.get('node_type')

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
        fact_attributes = set(node_fact_structure.get('attributes', {}).keys())

        if pattern_must_have:
            must_have_match = len(pattern_must_have & fact_attributes) / len(pattern_must_have)
            score += weight_must_have * must_have_match
        else:
            # No required attributes - consider it a match
            score += weight_must_have

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
                    if pattern_is_container and fact_is_container:
                        pattern_types = set(pattern_child.get('child_types', []))
                        fact_types = set(child.get('node_type', '') for child in fact_children)

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
        weight_refs = 0.15
        total_weight += weight_refs

        pattern_refs = pattern_decision_rule.get('reference_patterns', [])
        fact_relationships = node_fact_structure.get('relationships', [])

        if pattern_refs:
            if fact_relationships:
                # Compare reference types
                pattern_ref_types = set(r.get('type', '') for r in pattern_refs)
                fact_ref_types = set(r.get('type', '') for r in fact_relationships)

                ref_overlap = len(pattern_ref_types & fact_ref_types) / len(pattern_ref_types)
                score += weight_refs * ref_overlap
        else:
            # No reference patterns required
            score += weight_refs

        # Normalize score
        normalized_score = min(1.0, score / total_weight) if total_weight > 0 else 0.0

        # CRITICAL: If node types don't match, cap the score at 20%
        # This prevents PaxSegmentList from matching BaggageAllowanceList
        if not node_type_matches:
            normalized_score = min(normalized_score, 0.20)

        return normalized_score

    def match_node_fact_to_patterns(self,
                                     node_fact: NodeFact,
                                     spec_version: str,
                                     message_root: str) -> List[Dict[str, Any]]:
        """
        Match a single NodeFact against all patterns for the same version.

        Returns:
            List of matches with confidence scores
        """
        # Query patterns for same version/message (VERSION-FILTERED!)
        patterns = self.db_session.query(Pattern).filter(
            Pattern.spec_version == spec_version,
            Pattern.message_root == message_root
        ).all()

        if not patterns:
            logger.info(f"No patterns found for {spec_version}/{message_root}")
            return []

        matches = []

        for pattern in patterns:
            # Calculate similarity
            confidence = self.calculate_pattern_similarity(
                node_fact.fact_json,
                pattern.decision_rule
            )

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

    def store_pattern_match(self,
                           run_id: str,
                           node_fact: NodeFact,
                           pattern_id: Optional[int],
                           confidence: float,
                           verdict: str):
        """Store pattern match result in database."""
        pattern_match = PatternMatch(
            run_id=run_id,
            node_fact_id=node_fact.id,
            pattern_id=pattern_id,
            confidence=confidence,
            verdict=verdict
        )

        self.db_session.add(pattern_match)

    def run_identify(self, xml_file_path: str) -> Dict[str, Any]:
        """
        Run identify workflow on new XML file.

        Phase 1: Extract NodeFacts (reuse Discovery extraction)
        Phase 2: Match NodeFacts against saved patterns
        Phase 3: Generate gap analysis report

        Args:
            xml_file_path: Path to XML file to identify

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

        logger.info(f"Detected version: {spec_version}/{message_root}")

        # PHASE 1: Extract NodeFacts (reuse Discovery workflow but mark as IDENTIFY run)
        logger.info("Phase 1: Extracting NodeFacts from XML")

        # Run discovery extraction (but we'll create an IDENTIFY run manually)
        # First, let discovery extract the facts
        discovery_results = self.discovery.run_discovery(xml_file_path)

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

        for nf in node_facts:
            matches = self.match_node_fact_to_patterns(nf, spec_version, message_root)

            if matches:
                # Use best match
                best_match = matches[0]

                # Store match
                self.store_pattern_match(
                    run_id=run_id,
                    node_fact=nf,
                    pattern_id=best_match['pattern_id'],
                    confidence=best_match['confidence'],
                    verdict=best_match['verdict']
                )

                match_results.append({
                    'node_fact_id': nf.id,
                    'node_type': nf.node_type,
                    'section_path': nf.section_path,
                    'best_match': {
                        'pattern_id': best_match['pattern_id'],
                        'confidence': best_match['confidence'],
                        'verdict': best_match['verdict']
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

                if best_match['confidence'] >= 0.70:
                    matched_count += 1
                if best_match['confidence'] >= 0.85:
                    high_confidence_count += 1

                # Update pattern times_seen for high confidence matches
                if best_match['confidence'] >= 0.85:
                    pattern = best_match['pattern']
                    pattern.times_seen += 1
                    pattern.last_seen_at = datetime.utcnow()

            else:
                # No patterns found - this is a NEW pattern
                new_patterns_count += 1

                self.store_pattern_match(
                    run_id=run_id,
                    node_fact=nf,
                    pattern_id=None,
                    confidence=0.0,
                    verdict="NEW_PATTERN"
                )

                match_results.append({
                    'node_fact_id': nf.id,
                    'node_type': nf.node_type,
                    'section_path': nf.section_path,
                    'best_match': None,
                    'verdict': 'NEW_PATTERN'
                })

        # Commit all pattern matches
        self.db_session.commit()

        # PHASE 3: Gap Analysis
        logger.info("Phase 3: Generating gap analysis")

        gap_analysis = {
            'total_node_facts': node_facts_extracted,
            'matched_facts': matched_count,
            'high_confidence_matches': high_confidence_count,
            'new_patterns': new_patterns_count,
            'unmatched_facts': node_facts_extracted - matched_count,
            'match_rate': (matched_count / node_facts_extracted * 100) if node_facts_extracted > 0 else 0,
            'high_confidence_rate': (high_confidence_count / node_facts_extracted * 100) if node_facts_extracted > 0 else 0
        }

        # Update run with summary
        if run:
            run.metadata_json = {
                **run.metadata_json,
                'identify_results': {
                    'matches': matched_count,
                    'new_patterns': new_patterns_count,
                    'match_rate': gap_analysis['match_rate']
                }
            }
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
