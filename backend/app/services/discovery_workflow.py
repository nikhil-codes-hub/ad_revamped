"""
Discovery workflow orchestrator for AssistedDiscovery.

Orchestrates the complete discovery process: XML parsing, target detection,
fact extraction, and storage. Implements the end-to-end Discovery pipeline.
"""

import logging
import uuid
from typing import Dict, List, Any, Optional, Iterator
from datetime import datetime
from pathlib import Path
import hashlib

from sqlalchemy.orm import Session
from sqlalchemy import create_engine

from app.core.config import settings
from app.models.database import Run, RunKind, RunStatus, NodeFact, NdcTargetPath, NodeConfiguration
from app.services.xml_parser import XmlStreamingParser, create_parser_for_version, XmlSubtree, detect_ndc_version_fast
from app.services.template_extractor import template_extractor
from app.services.llm_extractor import get_llm_extractor
from app.services.pii_masking import pii_engine
from app.services.pattern_generator import create_pattern_generator
from app.services.utils import normalize_iata_prefix
from app.services.parallel_processor import (
    ThreadSafeDatabaseManager,
    process_nodes_parallel
)

logger = logging.getLogger(__name__)


class DiscoveryWorkflow:
    """Orchestrates the complete discovery process."""

    def __init__(self, db_session: Session):
        """Initialize workflow with database session."""
        self.db_session = db_session
        self.message_root: Optional[str] = None

    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file."""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def _get_target_paths_from_db(self, spec_version: str = None,
                                 message_root: str = None) -> List[Dict]:
        """Get target paths from database."""
        query = self.db_session.query(NdcTargetPath)

        if spec_version:
            query = query.filter(NdcTargetPath.spec_version == spec_version)
        if message_root:
            query = query.filter(NdcTargetPath.message_root == message_root)

        target_paths = []
        for target in query.all():
            target_paths.append({
                'id': target.id,
                'spec_version': target.spec_version,
                'message_root': target.message_root,
                'path_local': target.path_local,
                'extractor_key': target.extractor_key,
                'is_required': target.is_required,
                'importance': target.importance,
                'notes': target.notes
            })

        return target_paths

    def _get_node_configurations(self, spec_version: str = None,
                                 message_root: str = None,
                                 airline_code: str = None) -> Dict[str, Dict]:
        """
        Get node configurations from database.

        Returns dict mapping section_path -> config dict with enabled status.
        """
        query = self.db_session.query(NodeConfiguration).filter(
            NodeConfiguration.enabled == True  # Only get enabled configs
        )

        if spec_version:
            query = query.filter(NodeConfiguration.spec_version == spec_version)
        if message_root:
            query = query.filter(NodeConfiguration.message_root == message_root)

        # Get both airline-specific and global configs (NULL airline_code)
        if airline_code:
            query = query.filter(
                (NodeConfiguration.airline_code == airline_code) |
                (NodeConfiguration.airline_code == None)
            )
        else:
            query = query.filter(NodeConfiguration.airline_code == None)

        configs = {}
        for config in query.all():
            configs[config.section_path] = {
                'id': config.id,
                'node_type': config.node_type,
                'enabled': config.enabled,
                'ba_remarks': config.ba_remarks
            }

        return configs

    def _convert_node_configs_to_target_paths(self, node_configs: Dict[str, Dict]) -> List[Dict]:
        """
        Convert node configurations to target_paths format for XML parser.

        Args:
            node_configs: Dict mapping section_path -> config

        Returns:
            List of target path dicts compatible with XmlStreamingParser
        """
        target_paths = []
        message_root = self.message_root or ''

        for section_path, config in node_configs.items():
            # Normalize path to match XML parser's format
            # Remove IATA_ prefix for any message type (OrderViewRS, AirShoppingRS, etc.)
            normalized_path = normalize_iata_prefix(section_path, message_root)

            # Convert to parser format
            target_paths.append({
                'id': config['id'],
                'spec_version': None,  # Will be set by parser
                'message_root': None,  # Will be set by parser
                'path_local': f"/{normalized_path}",  # Add leading slash for parser
                'extractor_key': 'llm',  # Use LLM extraction by default
                'is_required': False,
                'importance': 'medium',
                'notes': config.get('ba_remarks', '')
            })

        return target_paths

    def _should_extract_node(self, section_path: str, node_configs: Dict[str, Dict]) -> bool:
        """
        Check if a node should be extracted based on NodeConfiguration.

        If no configuration exists, default to extracting (backward compatibility).
        If configuration exists, respect the enabled flag.
        """
        if not node_configs:
            # No configs loaded - extract everything (backward compatibility)
            return True

        # Normalize the section_path to match node_configs format
        # Remove IATA_ prefix for any message type
        message_root = self.message_root or ''

        normalized_section = normalize_iata_prefix(section_path, message_root)

        # Check if this path has a configuration
        for config_path, config in node_configs.items():
            # Normalize config path too
            normalized_config = normalize_iata_prefix(config_path, message_root)

            if normalized_config in normalized_section or config_path in section_path:
                return config['enabled']

        # No matching config - default to extract
        return True

    def _create_run_record(self, file_path: str, file_hash: str, file_size: int) -> str:
        """Create a new run record in database."""
        run_id = str(uuid.uuid4())

        run = Run(
            id=run_id,
            kind=RunKind.DISCOVERY,
            status=RunStatus.STARTED,
            filename=Path(file_path).name,
            file_size_bytes=file_size,
            file_hash=file_hash,
            started_at=datetime.utcnow(),
            metadata_json={
                'workflow_version': '1.0',
                'max_xml_size_mb': settings.MAX_XML_SIZE_MB,
                'max_subtree_size_kb': settings.MAX_SUBTREE_SIZE_KB,
                'pii_masking_enabled': settings.PII_MASKING_ENABLED
            }
        )

        self.db_session.add(run)
        self.db_session.commit()

        logger.info(f"Created discovery run: {run_id}")
        return run_id

    def _update_run_version_info(self, run_id: str, spec_version: str, message_root: str,
                                 airline_code: str = None, airline_name: str = None):
        """Update run with detected version and airline information."""
        run = self.db_session.query(Run).filter(Run.id == run_id).first()
        if run:
            run.spec_version = spec_version
            run.message_root = message_root
            if airline_code:
                run.airline_code = airline_code
            if airline_name:
                run.airline_name = airline_name
            run.status = RunStatus.IN_PROGRESS
            self.db_session.commit()
            airline_info = f" - Airline: {airline_code}" if airline_code else ""
            logger.info(f"Updated run {run_id} with version: {spec_version}/{message_root}{airline_info}")

    def _update_run_status(self, run_id: str, status: RunStatus, error_details: str = None):
        """Update run status."""
        run = self.db_session.query(Run).filter(Run.id == run_id).first()
        if run:
            run.status = status
            run.finished_at = datetime.utcnow()
            if error_details:
                run.error_details = error_details
            self.db_session.commit()

    def _store_node_facts(self, run_id: str, subtree: XmlSubtree,
                         extraction_results: Dict[str, Any]):
        """Store extracted node facts in database."""
        run = self.db_session.query(Run).filter(Run.id == run_id).first()
        if not run:
            return

        node_facts_stored = 0

        for template_key, result in extraction_results['extraction_results'].items():
            if result['status'] == 'success' and result['facts']:
                for idx, fact_data in enumerate(result['facts']):
                    node_fact = NodeFact(
                        run_id=run_id,
                        spec_version=run.spec_version,
                        message_root=run.message_root,
                        section_path=subtree.path,
                        node_type=fact_data['node_type'],
                        node_ordinal=fact_data['node_ordinal'],
                        fact_json=fact_data,
                        pii_masked=settings.PII_MASKING_ENABLED,
                        created_at=datetime.utcnow()
                    )

                    self.db_session.add(node_fact)
                    node_facts_stored += 1

        if node_facts_stored > 0:
            self.db_session.commit()
            logger.debug(f"Stored {node_facts_stored} node facts for run {run_id}")

        return node_facts_stored

    def _store_llm_node_facts(self, run_id: str, subtree: XmlSubtree,
                             llm_result) -> int:
        """Store LLM-extracted node facts in database."""
        run = self.db_session.query(Run).filter(Run.id == run_id).first()
        if not run:
            return 0

        node_facts_stored = 0

        for fact_data in llm_result.node_facts:
            node_fact = NodeFact(
                run_id=run_id,
                spec_version=run.spec_version,
                message_root=run.message_root,
                section_path=subtree.path,
                node_type=fact_data['node_type'],
                node_ordinal=fact_data['node_ordinal'],
                fact_json=fact_data,
                pii_masked=settings.PII_MASKING_ENABLED,
                created_at=datetime.utcnow()
            )

            self.db_session.add(node_fact)
            node_facts_stored += 1

        if node_facts_stored > 0:
            self.db_session.commit()
            logger.debug(f"Stored {node_facts_stored} LLM-extracted node facts for run {run_id}")

        return node_facts_stored

    def _get_template_keys_for_path(self, target_path: Dict) -> List[str]:
        """Get template keys to use for a target path."""
        extractor_key = target_path.get('extractor_key', 'generic_llm')

        if extractor_key == 'template':
            # Map path to specific templates based on content
            path = target_path.get('path_local', '').lower()

            if 'booking' in path or 'reference' in path:
                return ['booking_reference']
            elif 'passenger' in path:
                return ['passenger']
            elif 'contact' in path:
                return ['contact']
            elif 'order' in path and 'item' not in path:
                return ['order']
            elif 'flight' in path and 'segment' in path:
                return ['flight_segment']
            elif 'origin' in path and 'destination' in path:
                return ['origin_destination']
            else:
                # Use all available templates for unknown paths
                return template_extractor.get_available_templates()

        else:
            # For generic_llm extractor, we'll implement LLM-based extraction later
            # For now, try all templates
            return template_extractor.get_available_templates()

    def run_discovery(self, xml_file_path: str, skip_pattern_generation: bool = False) -> Dict[str, Any]:
        """
        Run complete discovery workflow on XML file using optimized two-phase approach.

        Phase 1: Fast version detection from XML root element
        Phase 2: Targeted processing with version-specific target paths
        Phase 2.5: Relationship analysis (always runs)
        Phase 3: Pattern generation (skipped when called from Identify mode)

        Args:
            xml_file_path: Path to XML file to process
            skip_pattern_generation: If True, skip Phase 3 (pattern generation).
                                    Used when calling from Identify workflow.

        Returns:
            Dict containing workflow results and statistics
        """
        logger.info(f"Starting optimized discovery workflow: {xml_file_path}")

        # Reset message root context for this run
        self.message_root = None

        # Validate file
        file_path = Path(xml_file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"XML file not found: {xml_file_path}")

        file_size = file_path.stat().st_size
        file_hash = self._calculate_file_hash(xml_file_path)

        # Create run record
        run_id = self._create_run_record(xml_file_path, file_hash, file_size)

        workflow_results = {
            'run_id': run_id,
            'file_path': xml_file_path,
            'file_size_bytes': file_size,
            'file_hash': file_hash,
            'started_at': datetime.utcnow().isoformat(),
            'subtrees_processed': 0,
            'node_facts_extracted': 0,
            'status': 'started',
            'error_details': None,
            'optimization_used': None,
            'target_paths_loaded': 0,
            'warning': None
        }

        try:
            # PHASE 1: Fast version detection
            logger.info("Phase 1: Fast version detection")
            version_info = detect_ndc_version_fast(xml_file_path)

            target_paths = []
            node_configs = {}
            optimization_strategy = None

            if version_info and version_info.spec_version and version_info.message_root:
                # SUCCESS: Version detected, use optimized approach
                logger.info(f"Version detected: {version_info.spec_version}/{version_info.message_root}")

                # Cache message root for helper methods
                self.message_root = version_info.message_root

                # Update run with version info immediately
                self._update_run_version_info(
                    run_id,
                    version_info.spec_version,
                    version_info.message_root,
                    airline_code=version_info.airline_code,
                    airline_name=version_info.airline_name
                )

                # PRIORITY 1: Try to load node configurations (BA-defined extraction rules)
                node_configs = self._get_node_configurations(
                    spec_version=version_info.spec_version,
                    message_root=version_info.message_root,
                    airline_code=version_info.airline_code
                )

                if node_configs:
                    # Use node configurations as primary target paths
                    target_paths = self._convert_node_configs_to_target_paths(node_configs)
                    optimization_strategy = "node_configurations"
                    logger.info(f"Using {len(target_paths)} BA-configured target paths")
                else:
                    # PRIORITY 2: Fallback to ndc_target_paths table
                    target_paths = self._get_target_paths_from_db(
                        version_info.spec_version,
                        version_info.message_root
                    )
                    optimization_strategy = "ndc_target_paths"
                    warning_msg = (f"No node configurations found for {version_info.spec_version}/{version_info.message_root}. "
                                  f"Using fallback target paths from ndc_target_paths table. "
                                  f"Please configure nodes in Node Manager for better control.")
                    workflow_results['warning'] = warning_msg
                    logger.warning(warning_msg)

            else:
                # FALLBACK: Version detection failed
                logger.warning("Fast version detection failed - applying fallback strategy")

                # Try common versions as fallback (ordered by frequency in our XMLs)
                fallback_versions = [
                    ('21.3', 'OrderViewRS'),  # Most modern
                    ('18.1', 'OrderViewRS'),  # Very common
                    ('17.2', 'OrderViewRS'),  # Legacy but common
                    ('19.2', 'OrderViewRS'),  # Alternative
                ]

                target_paths = []
                fallback_version_used = None

                for version, message_root in fallback_versions:
                    candidate_paths = self._get_target_paths_from_db(version, message_root)
                    if candidate_paths:
                        target_paths = candidate_paths
                        fallback_version_used = f"{version}/{message_root}"
                        logger.info(f"Using fallback version: {fallback_version_used}")
                        self.message_root = message_root
                        break

                if not target_paths:
                    # Last resort - this should not happen if DB is populated
                    logger.error("No target paths found even for common versions")
                    raise ValueError("Version detection failed and no fallback versions available. "
                                   "Please ensure target paths are loaded in database or "
                                   "specify version manually.")

                optimization_strategy = f"fallback_version_{fallback_version_used}"
                logger.info(f"Loaded {len(target_paths)} target paths for fallback version {fallback_version_used}")

            if not target_paths:
                raise ValueError("No target paths found in database")

            # PHASE 2: Targeted XML processing
            logger.info(f"Phase 2: XML processing with {optimization_strategy}")
            parser = XmlStreamingParser(target_paths)

            # Initialize variables
            subtrees_processed = 0
            total_facts_extracted = 0
            version_updated_during_processing = False
            nodes_skipped_by_config = 0

            # Check if LLM is available and decide processing mode
            llm_extractor = get_llm_extractor()
            use_parallel = settings.ENABLE_PARALLEL_PROCESSING and llm_extractor.client

            if not llm_extractor.client:
                logger.warning("LLM client not available - parallel processing disabled")
                use_parallel = False

            # Collect subtrees from XML stream
            logger.info("Collecting subtrees from XML stream...")
            subtrees_to_process = []

            for subtree in parser.parse_stream(xml_file_path):
                # Handle version info if not detected in Phase 1
                if (not version_info and
                    not version_updated_during_processing and
                    parser.version_info.spec_version):

                    logger.info("Version detected during processing: "
                               f"{parser.version_info.spec_version}/"
                               f"{parser.version_info.message_root}")

                    self._update_run_version_info(
                        run_id,
                        parser.version_info.spec_version,
                        parser.version_info.message_root,
                        airline_code=parser.version_info.airline_code,
                        airline_name=parser.version_info.airline_name
                    )
                    version_updated_during_processing = True
                    version_info = parser.version_info
                    self.message_root = parser.version_info.message_root

                # Find matching target path for this subtree
                matching_target = None
                for target in parser.target_paths:
                    if target['path_local'] in subtree.path:
                        matching_target = target
                        break

                if matching_target:
                    # Only collect nodes that should be extracted
                    if optimization_strategy == "ndc_target_paths":
                        if self._should_extract_node(subtree.path, node_configs):
                            subtrees_to_process.append(subtree)
                        else:
                            logger.debug(f"Skipping node {subtree.path} - disabled by NodeConfiguration")
                            nodes_skipped_by_config += 1
                    else:
                        subtrees_to_process.append(subtree)
                else:
                    logger.warning(f"No matching target path found for subtree: {subtree.path}")

            logger.info(f"Collected {len(subtrees_to_process)} subtrees for processing "
                       f"({nodes_skipped_by_config} skipped by config)")

            # Process nodes - Parallel or Sequential based on configuration
            if use_parallel and len(subtrees_to_process) > 0:
                # PARALLEL PROCESSING
                logger.info(f"🚀 Starting PARALLEL processing with {settings.MAX_PARALLEL_NODES} workers")

                # Initialize thread-safe database manager
                db_manager = ThreadSafeDatabaseManager(self.db_session.bind)

                try:
                    # Process nodes in parallel
                    parallel_results = process_nodes_parallel(
                        subtrees=subtrees_to_process,
                        run_id=run_id,
                        spec_version=version_info.spec_version if version_info else None,
                        message_root=version_info.message_root if version_info else None,
                        llm_extractor=llm_extractor,
                        db_manager=db_manager,
                        optimization_strategy=optimization_strategy,
                        node_configs=node_configs,
                        max_workers=min(settings.MAX_PARALLEL_NODES, len(subtrees_to_process)),
                        should_extract_func=self._should_extract_node
                    )

                    # Extract results
                    subtrees_processed = parallel_results['subtrees_processed']
                    total_facts_extracted = parallel_results['total_facts_extracted']
                    nodes_skipped_by_config += parallel_results['nodes_skipped_by_config']

                    logger.info(f"✅ Parallel processing completed: "
                               f"{subtrees_processed} nodes processed, "
                               f"{total_facts_extracted} facts extracted")

                    # Handle errors if any
                    if parallel_results['processing_errors']:
                        error_count = len(parallel_results['processing_errors'])
                        logger.warning(f"⚠️ {error_count} nodes had processing errors")

                        # Build error summary for user visibility
                        error_summary_lines = []
                        for err in parallel_results['processing_errors'][:10]:  # First 10 errors
                            error_summary_lines.append(f"• {err['subtree_path']}: {err['error']}")

                        if error_count > 10:
                            error_summary_lines.append(f"• ... and {error_count - 10} more errors")

                        error_summary = "\n".join(error_summary_lines)

                        # Save errors to Run record so user can see them
                        run = self.db_session.query(Run).filter(Run.id == run_id).first()
                        if run:
                            run.error_details = f"LLM extraction failed for {error_count} of {len(subtrees_to_process)} nodes:\n\n{error_summary}"

                            # Also save detailed errors to metadata for debugging
                            if run.metadata_json is None:
                                run.metadata_json = {}
                            run.metadata_json['processing_errors'] = parallel_results['processing_errors']
                            run.metadata_json['error_count'] = error_count

                            self.db_session.commit()
                            logger.info(f"Saved {error_count} processing errors to Run record")

                        # If ALL nodes failed, mark run as FAILED and stop
                        if total_facts_extracted == 0:
                            error_msg = (f"Discovery completely failed: No NodeFacts extracted. "
                                        f"All {error_count} nodes had LLM extraction errors.\n\n"
                                        f"First error: {parallel_results['processing_errors'][0]['error']}")
                            logger.error(f"❌ {error_msg}")
                            self._update_run_status(run_id, RunStatus.FAILED, error_msg)
                            raise ValueError(error_msg)

                finally:
                    # Cleanup thread-local sessions
                    db_manager.cleanup_session()

            else:
                # SEQUENTIAL PROCESSING (Fallback/Legacy mode)
                logger.info("Using SEQUENTIAL processing (legacy mode)")

                for subtree in subtrees_to_process:
                    try:
                        # Use LLM-based extraction
                        logger.debug(f"Using LLM extraction for path: {subtree.path}")

                        llm_result = llm_extractor.extract_from_subtree_sync(
                            subtree,
                            context={
                                'run_id': run_id,
                                'spec_version': version_info.spec_version if version_info else None,
                                'message_root': version_info.message_root if version_info else None
                            }
                        )

                        # Store LLM-extracted facts
                        facts_stored = self._store_llm_node_facts(run_id, subtree, llm_result)
                        total_facts_extracted += facts_stored
                        subtrees_processed += 1

                        logger.info(f"Processed subtree {subtrees_processed}/{len(subtrees_to_process)}: "
                                   f"{subtree.path} -> {facts_stored} facts")

                    except ValueError as e:
                        # LLM extraction errors - stop processing
                        error_msg = str(e)
                        logger.error(f"❌ LLM EXTRACTION FAILED for {subtree.path}")
                        logger.error(f"   Error: {error_msg}")
                        raise ValueError(f"LLM Extraction Failed: {error_msg}")

                    except Exception as e:
                        logger.error(f"❌ UNEXPECTED ERROR during LLM extraction for {subtree.path}")
                        logger.error(f"   Error: {type(e).__name__}: {str(e)}")
                        import traceback
                        logger.error(f"   Traceback:\n{traceback.format_exc()}")
                        raise ValueError(f"Discovery Error: {type(e).__name__}: {str(e)}")

            # Update workflow results (but DON'T set finished_at yet - still have more phases!)
            workflow_results.update({
                'subtrees_processed': subtrees_processed,
                'node_facts_extracted': total_facts_extracted,
                'nodes_skipped_by_config': nodes_skipped_by_config,
                'node_configs_loaded': len(node_configs),
                'status': 'in_progress',  # Still processing - relationship analysis and pattern generation pending
                'optimization_used': optimization_strategy,
                'target_paths_loaded': len(target_paths),
                'version_info': {
                    'spec_version': version_info.spec_version if version_info else None,
                    'message_root': version_info.message_root if version_info else None,
                    'namespace_uri': version_info.namespace_uri if version_info else None,
                    'airline_code': version_info.airline_code if version_info else None,
                    'airline_name': version_info.airline_name if version_info else None
                }
            })

            # Add processing error info to workflow results for API response
            if use_parallel and parallel_results.get('processing_errors'):
                workflow_results['processing_errors_count'] = len(parallel_results['processing_errors'])
                if total_facts_extracted > 0:
                    # Partial success - add warning
                    workflow_results['warning'] = (
                        f"⚠️ {len(parallel_results['processing_errors'])} nodes had processing errors. "
                        f"See error details for more information."
                    )

            # DON'T update run status to completed yet - relationship analysis and pattern generation still pending

            logger.info(f"Optimized discovery workflow completed: {run_id} - "
                       f"Strategy: {optimization_strategy}, "
                       f"Paths loaded: {len(target_paths)}, "
                       f"Node configs: {len(node_configs)}, "
                       f"Subtrees: {subtrees_processed}, "
                       f"Facts: {total_facts_extracted}, "
                       f"Skipped by config: {nodes_skipped_by_config}")

            # PHASE 2.5: Relationship Analysis (if NodeFacts were extracted)
            logger.info(f"DEBUG: About to check Phase 2.5 condition - total_facts_extracted = {total_facts_extracted}")
            if total_facts_extracted > 0:
                logger.info(f"DEBUG: Phase 2.5 condition TRUE - entering relationship analysis")
                logger.info(f"Phase 2.5: Analyzing relationships between {total_facts_extracted} NodeFacts")
                try:
                    from app.services.relationship_analyzer import create_relationship_analyzer

                    # Get all extracted node facts for this run
                    node_facts = self.db_session.query(NodeFact).filter(
                        NodeFact.run_id == run_id
                    ).all()

                    # Analyze relationships using LLM
                    relationship_analyzer = create_relationship_analyzer(self.db_session)
                    relationship_results = relationship_analyzer.analyze_relationships(
                        run_id,
                        node_facts
                    )

                    workflow_results['relationship_analysis'] = relationship_results

                    logger.info(f"Relationship analysis completed: "
                               f"{relationship_results.get('relationships_count', 0)} relationships discovered, "
                               f"{relationship_results['statistics'].get('valid_relationships', 0)} valid, "
                               f"{relationship_results['statistics'].get('broken_relationships', 0)} broken")
                except Exception as e:
                    logger.error(f"Relationship analysis failed for run {run_id}: {e}")
                    workflow_results['relationship_analysis'] = {
                        'success': False,
                        'error': str(e)
                    }

            # PHASE 3: Pattern Generation (if NodeFacts were extracted AND not skipped)
            if total_facts_extracted > 0 and not skip_pattern_generation:
                logger.info(f"Phase 3: Generating patterns from {total_facts_extracted} NodeFacts (auto-discovery mode)")
                try:
                    pattern_generator = create_pattern_generator(self.db_session)
                    pattern_results = pattern_generator.generate_patterns_from_run(run_id)

                    workflow_results['pattern_generation'] = pattern_results

                    logger.info(f"Pattern generation completed: "
                               f"{pattern_results.get('patterns_created', 0)} created, "
                               f"{pattern_results.get('patterns_updated', 0)} updated")
                except Exception as e:
                    logger.error(f"Pattern generation failed for run {run_id}: {e}")
                    workflow_results['pattern_generation'] = {
                        'success': False,
                        'error': str(e)
                    }
            elif skip_pattern_generation:
                logger.info("Phase 3: Pattern generation SKIPPED (called from Identify mode)")

            # ALL PHASES COMPLETE - Now update run status and set finished_at timestamp
            workflow_results.update({
                'finished_at': datetime.utcnow().isoformat(),
                'status': 'completed'
            })
            self._update_run_status(run_id, RunStatus.COMPLETED)
            logger.info(f"✅ Discovery workflow fully completed: {run_id}")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Discovery workflow failed: {run_id} - {error_msg}")

            workflow_results.update({
                'status': 'failed',
                'error_details': error_msg,
                'finished_at': datetime.utcnow().isoformat()
            })

            # Update run status to failed
            self._update_run_status(run_id, RunStatus.FAILED, error_msg)

        return workflow_results

    def get_run_summary(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get summary of discovery run."""
        run = self.db_session.query(Run).filter(Run.id == run_id).first()
        if not run:
            return None

        # Count node facts
        node_facts_count = self.db_session.query(NodeFact).filter(
            NodeFact.run_id == run_id
        ).count()

        return {
            'run_id': run.id,
            'kind': run.kind,
            'status': run.status,
            'spec_version': run.spec_version,
            'message_root': run.message_root,
            'airline_code': run.airline_code,
            'airline_name': run.airline_name,
            'filename': run.filename,
            'file_size_bytes': run.file_size_bytes,
            'started_at': run.started_at.isoformat() if run.started_at else None,
            'finished_at': run.finished_at.isoformat() if run.finished_at else None,
            'duration_seconds': run.duration_seconds,
            'node_facts_count': node_facts_count,
            'metadata': run.metadata_json,
            'error_details': run.error_details
        }


def create_discovery_workflow(db_session: Session) -> DiscoveryWorkflow:
    """Create discovery workflow instance with database session."""
    return DiscoveryWorkflow(db_session)
