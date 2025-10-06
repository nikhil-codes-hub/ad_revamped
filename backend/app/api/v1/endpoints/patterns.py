"""
Pattern management endpoints for AssistedDiscovery.

Handles retrieval and querying of discovered patterns.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import structlog

from app.models.schemas import PatternResponse
from app.core.logging import get_logger
from app.services.database import get_db_session
from app.services.pattern_generator import create_pattern_generator
from app.models.database import Pattern

router = APIRouter()
logger = get_logger(__name__)


@router.get("/", response_model=List[PatternResponse])
async def list_patterns(
    message_root: Optional[str] = Query(None, description="Filter by message root (e.g., OrderViewRS)"),
    section_path: Optional[str] = Query(None, description="Filter by section path"),
    spec_version: Optional[str] = Query(None, description="Filter by NDC specification version"),
    run_id: Optional[str] = Query(None, description="Filter by run ID (patterns generated from this run)"),
    airline_code: Optional[str] = Query(None, description="Filter by airline code"),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum number of patterns to return"),
    offset: int = Query(default=0, ge=0, description="Number of patterns to skip for pagination"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum times_seen count"),
    db: Session = Depends(get_db_session)
) -> List[PatternResponse]:
    """
    List discovered patterns with filtering and pagination.

    - **message_root**: Filter by message type (e.g., 'OrderViewRS')
    - **section_path**: Filter by XML section path (supports partial matching)
    - **spec_version**: Filter by NDC version (e.g., '17.2')
    - **run_id**: Filter by Discovery run (only show patterns from this run)
    - **airline_code**: Filter by airline code (e.g., 'SQ', 'VY')
    - **limit**: Maximum patterns to return (1-200)
    - **offset**: Skip patterns for pagination
    - **min_confidence**: Minimum times_seen count for pattern quality
    """
    logger.info("Listing patterns",
                message_root=message_root,
                section_path=section_path,
                spec_version=spec_version,
                run_id=run_id,
                airline_code=airline_code,
                limit=limit,
                offset=offset)

    query = db.query(Pattern)

    # Apply filters
    if message_root:
        query = query.filter(Pattern.message_root == message_root)
    if section_path:
        query = query.filter(Pattern.section_path.like(f'%{section_path}%'))
    if spec_version:
        query = query.filter(Pattern.spec_version == spec_version)
    if airline_code:
        query = query.filter(
            (Pattern.airline_code == airline_code) | (Pattern.airline_code == None)
        )
    if run_id:
        # Filter patterns generated from node_facts in this specific run
        # Get node_fact IDs from this run, then find patterns that have examples from these facts
        from app.models.database import NodeFact

        run_node_fact_ids = db.query(NodeFact.id).filter(NodeFact.run_id == run_id).all()
        run_node_fact_ids = [nf_id[0] for nf_id in run_node_fact_ids]

        if run_node_fact_ids:
            # Patterns are generated from node_facts, so we filter by matching:
            # 1. spec_version and message_root from the run
            # 2. section_path matching node_facts from this run
            from app.models.database import Run
            run = db.query(Run).filter(Run.id == run_id).first()

            if run:
                # Get unique section_paths from this run's node_facts
                run_section_paths = db.query(NodeFact.section_path).filter(
                    NodeFact.run_id == run_id
                ).distinct().all()
                run_section_paths = [path[0] for path in run_section_paths]

                # Normalize paths to match pattern format (remove leading slash)
                normalized_paths = [path.lstrip('/') for path in run_section_paths]

                # Filter patterns by run's version/message and section paths
                query = query.filter(
                    Pattern.spec_version == run.spec_version,
                    Pattern.message_root == run.message_root,
                    Pattern.section_path.in_(normalized_paths)
                )

                # If run has airline_code, prioritize airline-specific patterns
                if run.airline_code:
                    query = query.filter(
                        (Pattern.airline_code == run.airline_code) | (Pattern.airline_code == None)
                    )
            else:
                # Run not found, return empty
                logger.warning(f"Run {run_id} not found")
                return []
        else:
            # No node_facts for this run, return empty
            logger.warning(f"No node_facts found for run {run_id}")
            return []

    if min_confidence:
        query = query.filter(Pattern.times_seen >= int(min_confidence))

    # Sort by times_seen (most common first)
    query = query.order_by(Pattern.times_seen.desc(), Pattern.created_at.desc())

    # Pagination
    query = query.offset(offset).limit(limit)

    patterns = query.all()

    logger.info(f"Retrieved {len(patterns)} patterns")

    return [
        PatternResponse(
            id=p.id,
            spec_version=p.spec_version,
            message_root=p.message_root,
            airline_code=p.airline_code,
            section_path=p.section_path,
            selector_xpath=p.selector_xpath,
            decision_rule=p.decision_rule,
            signature_hash=p.signature_hash,
            times_seen=p.times_seen,
            created_by_model=p.created_by_model,
            examples=p.examples or [],
            created_at=p.created_at.isoformat() if p.created_at else None,
            last_seen_at=p.last_seen_at.isoformat() if p.last_seen_at else None
        )
        for p in patterns
    ]


@router.get("/{pattern_id}", response_model=PatternResponse)
async def get_pattern(pattern_id: int) -> PatternResponse:
    """
    Get details of a specific pattern.

    - **pattern_id**: Unique identifier for the pattern
    """
    logger.info("Getting pattern details", pattern_id=pattern_id)

    # TODO: Implement pattern retrieval
    # 1. Query database for pattern details
    # 2. Include usage statistics and examples
    # 3. Handle not found cases

    # Placeholder response
    return PatternResponse(
        id=pattern_id,
        spec_version="17.2",
        message_root="OrderViewRS",
        section_path="/OrderViewRS/Response/Order/BookingReferences",
        selector_xpath="./BookingReference[ID]",
        decision_rule={
            "must_have_children": ["ID"],
            "optional_children": ["AirlineID", "OtherID"],
            "attrs": {}
        },
        signature_hash="a1b2c3d4e5f6",
        times_seen=15,
        created_by_model="gpt-4-turbo-preview",
        examples=[
            {"node_type": "BookingReference", "snippet": "<BookingReference ID=ABC123>"}
        ],
        created_at="2025-09-26T10:30:00Z",
        last_seen_at="2025-09-26T11:45:00Z"
    )


@router.get("/{pattern_id}/matches")
async def get_pattern_matches(
    pattern_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
):
    """
    Get recent matches for a specific pattern.

    Shows which node facts have been matched by this pattern in identify runs.
    """
    logger.info("Getting pattern matches", pattern_id=pattern_id, limit=limit, offset=offset)

    # TODO: Implement pattern match history
    # 1. Query pattern_matches table
    # 2. Include associated node_fact details
    # 3. Show confidence scores and verdicts

    return {
        "pattern_id": pattern_id,
        "matches": [],
        "total_matches": 0,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "has_more": False
        }
    }


@router.get("/stats/coverage")
async def get_coverage_stats(
    spec_version: Optional[str] = Query(None, description="Filter by NDC version"),
    message_root: Optional[str] = Query(None, description="Filter by message type")
):
    """
    Get pattern coverage statistics.

    Shows coverage percentages by section importance and completeness metrics.
    """
    logger.info("Getting coverage statistics", spec_version=spec_version, message_root=message_root)

    # TODO: Implement coverage statistics
    # 1. Query v_pattern_coverage view
    # 2. Calculate coverage by importance levels
    # 3. Include gap analysis

    return {
        "spec_version": spec_version or "all",
        "message_root": message_root or "all",
        "coverage_by_importance": {
            "critical": {"covered": 12, "total": 15, "percentage": 80.0},
            "high": {"covered": 18, "total": 20, "percentage": 90.0},
            "medium": {"covered": 15, "total": 17, "percentage": 88.2},
            "low": {"covered": 8, "total": 10, "percentage": 80.0}
        },
        "overall_coverage": 85.2,
        "patterns_by_section": {},
        "generated_at": "2025-09-26T11:45:00Z"
    }


@router.post("/generate")
async def generate_patterns(
    run_id: Optional[str] = Query(None, description="Generate patterns from specific run"),
    spec_version: Optional[str] = Query(None, description="Generate patterns for specific version"),
    message_root: Optional[str] = Query(None, description="Generate patterns for specific message type"),
    db: Session = Depends(get_db_session)
):
    """
    Manually trigger pattern generation.

    - **run_id**: Generate patterns from a specific discovery run
    - **spec_version**: Generate patterns from all runs of a specific version
    - **message_root**: Generate patterns from all runs of a specific message type
    - If no parameters: Generate patterns from ALL NodeFacts
    """
    logger.info("Manual pattern generation triggered",
                run_id=run_id,
                spec_version=spec_version,
                message_root=message_root)

    pattern_generator = create_pattern_generator(db)

    if run_id:
        # Generate from specific run
        results = pattern_generator.generate_patterns_from_run(run_id)
    else:
        # Generate from all runs (with optional filters)
        results = pattern_generator.generate_patterns_from_all_runs(
            spec_version=spec_version,
            message_root=message_root
        )

    logger.info("Pattern generation completed", results=results)

    return {
        "success": results.get('success', False),
        "message": "Pattern generation completed",
        "statistics": {
            "node_facts_analyzed": results.get('node_facts_analyzed', 0),
            "pattern_groups": results.get('pattern_groups', 0),
            "patterns_created": results.get('patterns_created', 0),
            "patterns_updated": results.get('patterns_updated', 0)
        },
        "errors": results.get('errors', [])
    }