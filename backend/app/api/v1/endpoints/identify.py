"""
Identify results endpoints for AssistedDiscovery.

Retrieves pattern matching results and gap analysis from identify runs.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.services.database import get_db_session
from app.models.database import Run, PatternMatch, NodeFact, Pattern, RunKind
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/{run_id}/matches")
async def get_identify_matches(
    run_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    verdict: Optional[str] = Query(None),
    db: Session = Depends(get_db_session)
):
    """
    Get pattern matching results for an identify run.

    - **run_id**: Identify run ID
    - **limit**: Maximum matches to return
    - **offset**: Skip matches for pagination
    - **min_confidence**: Filter by minimum confidence score
    - **verdict**: Filter by verdict (EXACT_MATCH, HIGH_MATCH, PARTIAL_MATCH, etc.)
    """
    logger.info(f"Getting identify matches for run: {run_id}")

    # Verify run exists and is identify type
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.kind != RunKind.IDENTIFY:
        raise HTTPException(status_code=400, detail="Run is not an identify run")

    # Query pattern matches
    query = db.query(PatternMatch).filter(PatternMatch.run_id == run_id)

    # Apply filters
    if min_confidence is not None:
        query = query.filter(PatternMatch.confidence >= min_confidence)
    if verdict:
        query = query.filter(PatternMatch.verdict == verdict)

    # Order by confidence (highest first)
    query = query.order_by(PatternMatch.confidence.desc())

    # Pagination
    total = query.count()
    matches = query.offset(offset).limit(limit).all()

    # Build response
    results = []
    for match in matches:
        # Get associated NodeFact
        node_fact = db.query(NodeFact).filter(NodeFact.id == match.node_fact_id).first()

        # Get associated Pattern (if matched)
        pattern = None
        if match.pattern_id:
            pattern = db.query(Pattern).filter(Pattern.id == match.pattern_id).first()

        result = {
            "match_id": match.id,
            "node_fact": {
                "id": node_fact.id if node_fact else None,
                "node_type": node_fact.node_type if node_fact else None,
                "section_path": node_fact.section_path if node_fact else None,
                "fact_json": node_fact.fact_json if node_fact else {}
            },
            "pattern": {
                "id": pattern.id if pattern else None,
                "section_path": pattern.section_path if pattern else None,
                "spec_version": pattern.spec_version if pattern else None,
                "message_root": pattern.message_root if pattern else None,
                "decision_rule": pattern.decision_rule if pattern else {},
                "times_seen": pattern.times_seen if pattern else 0
            } if pattern else None,
            "confidence": match.confidence,
            "verdict": match.verdict,
            "matched_at": match.created_at.isoformat() if match.created_at else None
        }

        results.append(result)

    return {
        "run_id": run_id,
        "total_matches": total,
        "matches": results,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total
        }
    }


@router.get("/{run_id}/gap-analysis")
async def get_gap_analysis(
    run_id: str,
    db: Session = Depends(get_db_session)
):
    """
    Get gap analysis for an identify run.

    Shows:
    - Total NodeFacts analyzed
    - Matched vs unmatched
    - New patterns discovered
    - Match rate statistics
    """
    logger.info(f"Getting gap analysis for run: {run_id}")

    # Verify run exists
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.kind != RunKind.IDENTIFY:
        raise HTTPException(status_code=400, detail="Run is not an identify run")

    # Get all matches for this run
    all_matches = db.query(PatternMatch).filter(PatternMatch.run_id == run_id).all()

    total_facts = len(all_matches)

    # Calculate statistics
    matched_count = 0
    high_confidence_count = 0
    new_patterns_count = 0

    verdict_breakdown = {
        "EXACT_MATCH": 0,
        "HIGH_MATCH": 0,
        "PARTIAL_MATCH": 0,
        "LOW_MATCH": 0,
        "NO_MATCH": 0,
        "NEW_PATTERN": 0
    }

    for match in all_matches:
        if match.verdict:
            verdict_breakdown[match.verdict] = verdict_breakdown.get(match.verdict, 0) + 1

        if match.confidence >= 0.70:
            matched_count += 1
        if match.confidence >= 0.85:
            high_confidence_count += 1
        if match.verdict == "NEW_PATTERN":
            new_patterns_count += 1

    match_rate = (matched_count / total_facts * 100) if total_facts > 0 else 0
    high_confidence_rate = (high_confidence_count / total_facts * 100) if total_facts > 0 else 0

    # Get metadata from run
    metadata = run.metadata_json or {}
    identify_results = metadata.get('identify_results', {})

    return {
        "run_id": run_id,
        "spec_version": run.spec_version,
        "message_root": run.message_root,
        "statistics": {
            "total_node_facts": total_facts,
            "matched_facts": matched_count,
            "high_confidence_matches": high_confidence_count,
            "new_patterns": new_patterns_count,
            "unmatched_facts": total_facts - matched_count,
            "match_rate": round(match_rate, 2),
            "high_confidence_rate": round(high_confidence_rate, 2)
        },
        "verdict_breakdown": verdict_breakdown,
        "generated_at": run.finished_at.isoformat() if run.finished_at else None
    }


@router.get("/{run_id}/new-patterns")
async def get_new_patterns(
    run_id: str,
    db: Session = Depends(get_db_session)
):
    """
    Get list of new patterns discovered in an identify run.

    Returns NodeFacts that didn't match any existing patterns.
    """
    logger.info(f"Getting new patterns for run: {run_id}")

    # Query pattern matches with verdict=NEW_PATTERN
    new_pattern_matches = db.query(PatternMatch).filter(
        PatternMatch.run_id == run_id,
        PatternMatch.verdict == "NEW_PATTERN"
    ).all()

    results = []
    for match in new_pattern_matches:
        # Get NodeFact details
        node_fact = db.query(NodeFact).filter(NodeFact.id == match.node_fact_id).first()

        if node_fact:
            results.append({
                "node_fact_id": node_fact.id,
                "node_type": node_fact.node_type,
                "section_path": node_fact.section_path,
                "fact_structure": node_fact.fact_json,
                "spec_version": node_fact.spec_version,
                "message_root": node_fact.message_root
            })

    return {
        "run_id": run_id,
        "new_patterns_count": len(results),
        "new_patterns": results
    }
