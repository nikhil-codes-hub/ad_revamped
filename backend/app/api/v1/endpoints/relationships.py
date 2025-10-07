"""
Relationship endpoints for AssistedDiscovery.

Provides API access to discovered node relationships.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
import structlog

from app.models.schemas import RelationshipResponse, RelationshipStatsResponse
from app.core.logging import get_logger
from app.services.database import get_db_session
from app.models.database import NodeRelationship, Run

router = APIRouter()
logger = get_logger(__name__)


@router.get("/", response_model=List[RelationshipResponse])
async def list_relationships(
    run_id: Optional[str] = Query(None, description="Filter by run ID"),
    reference_type: Optional[str] = Query(None, description="Filter by reference type (e.g., pax_reference)"),
    is_valid: Optional[bool] = Query(None, description="Filter by validity (true=valid, false=broken)"),
    was_expected: Optional[bool] = Query(None, description="Filter by expected vs discovered"),
    source_node_type: Optional[str] = Query(None, description="Filter by source node type"),
    target_node_type: Optional[str] = Query(None, description="Filter by target node type"),
    limit: int = Query(default=100, ge=1, le=500, description="Maximum number of relationships to return"),
    offset: int = Query(default=0, ge=0, description="Number of relationships to skip"),
    db: Session = Depends(get_db_session)
) -> List[RelationshipResponse]:
    """
    List discovered relationships with filtering and pagination.

    - **run_id**: Filter by Discovery run
    - **reference_type**: Filter by type (pax_reference, segment_reference, etc.)
    - **is_valid**: Show only valid or broken references
    - **was_expected**: Show expected (true) or discovered (false) references
    - **source_node_type**: Filter by source node type
    - **target_node_type**: Filter by target node type
    """
    logger.info("Listing relationships",
                run_id=run_id,
                reference_type=reference_type,
                is_valid=is_valid,
                was_expected=was_expected,
                limit=limit,
                offset=offset)

    query = db.query(NodeRelationship)

    # Apply filters
    if run_id:
        query = query.filter(NodeRelationship.run_id == run_id)
    if reference_type:
        query = query.filter(NodeRelationship.reference_type == reference_type)
    if is_valid is not None:
        query = query.filter(NodeRelationship.is_valid == is_valid)
    if was_expected is not None:
        query = query.filter(NodeRelationship.was_expected == was_expected)
    if source_node_type:
        query = query.filter(NodeRelationship.source_node_type == source_node_type)
    if target_node_type:
        query = query.filter(NodeRelationship.target_node_type == target_node_type)

    # Order by created_at descending
    query = query.order_by(NodeRelationship.created_at.desc())

    # Pagination
    query = query.offset(offset).limit(limit)

    relationships = query.all()

    logger.info(f"Retrieved {len(relationships)} relationships")

    return [
        RelationshipResponse(
            id=r.id,
            run_id=r.run_id,
            source_node_type=r.source_node_type,
            source_section_path=r.source_section_path,
            target_node_type=r.target_node_type,
            target_section_path=r.target_section_path,
            reference_type=r.reference_type,
            reference_field=r.reference_field,
            reference_value=r.reference_value,
            is_valid=r.is_valid,
            was_expected=r.was_expected,
            confidence=float(r.confidence) if r.confidence else None,
            discovered_by=r.discovered_by,
            model_used=r.model_used,
            created_at=r.created_at.isoformat() if r.created_at else None
        )
        for r in relationships
    ]


@router.get("/stats", response_model=RelationshipStatsResponse)
async def get_relationship_stats(
    run_id: Optional[str] = Query(None, description="Filter by run ID"),
    db: Session = Depends(get_db_session)
) -> RelationshipStatsResponse:
    """
    Get statistics about discovered relationships.

    Provides counts of:
    - Total relationships
    - Valid vs broken
    - Expected vs discovered
    - Breakdown by reference type
    """
    logger.info("Getting relationship statistics", run_id=run_id)

    query = db.query(NodeRelationship)
    if run_id:
        query = query.filter(NodeRelationship.run_id == run_id)

    # Total counts
    total = query.count()
    valid = query.filter(NodeRelationship.is_valid == True).count()
    broken = query.filter(NodeRelationship.is_valid == False).count()
    expected = query.filter(NodeRelationship.was_expected == True).count()
    discovered = query.filter(NodeRelationship.was_expected == False).count()

    # Breakdown by reference type
    type_breakdown = {}
    type_counts = db.query(
        NodeRelationship.reference_type,
        func.count(NodeRelationship.id).label('count')
    )
    if run_id:
        type_counts = type_counts.filter(NodeRelationship.run_id == run_id)

    type_counts = type_counts.group_by(NodeRelationship.reference_type).all()

    for ref_type, count in type_counts:
        type_breakdown[ref_type] = count

    # Most common reference types
    top_types = sorted(type_breakdown.items(), key=lambda x: x[1], reverse=True)[:10]

    return RelationshipStatsResponse(
        total_relationships=total,
        valid_relationships=valid,
        broken_relationships=broken,
        expected_relationships=expected,
        discovered_relationships=discovered,
        reference_type_breakdown=type_breakdown,
        top_reference_types=[{"type": t, "count": c} for t, c in top_types]
    )


@router.get("/run/{run_id}/summary")
async def get_run_relationship_summary(
    run_id: str,
    db: Session = Depends(get_db_session)
):
    """
    Get a comprehensive relationship summary for a specific run.

    Includes:
    - Overall statistics
    - Reference type breakdown
    - List of broken references
    - List of unexpected discoveries
    """
    logger.info("Getting relationship summary for run", run_id=run_id)

    # Verify run exists
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    # Get all relationships for this run
    relationships = db.query(NodeRelationship).filter(
        NodeRelationship.run_id == run_id
    ).all()

    if not relationships:
        return {
            "run_id": run_id,
            "total_relationships": 0,
            "message": "No relationships analyzed yet"
        }

    # Calculate statistics
    total = len(relationships)
    valid = sum(1 for r in relationships if r.is_valid)
    broken = sum(1 for r in relationships if not r.is_valid)
    expected = sum(1 for r in relationships if r.was_expected)
    discovered = sum(1 for r in relationships if not r.was_expected)

    # Group by reference type
    type_groups = {}
    for r in relationships:
        if r.reference_type not in type_groups:
            type_groups[r.reference_type] = {
                'total': 0,
                'valid': 0,
                'broken': 0,
                'expected': 0,
                'discovered': 0
            }
        type_groups[r.reference_type]['total'] += 1
        if r.is_valid:
            type_groups[r.reference_type]['valid'] += 1
        else:
            type_groups[r.reference_type]['broken'] += 1
        if r.was_expected:
            type_groups[r.reference_type]['expected'] += 1
        else:
            type_groups[r.reference_type]['discovered'] += 1

    # Get broken references
    broken_refs = [
        {
            "source": r.source_node_type,
            "target": r.target_node_type,
            "reference_type": r.reference_type,
            "reference_field": r.reference_field,
            "reference_value": r.reference_value,
            "was_expected": r.was_expected
        }
        for r in relationships if not r.is_valid
    ]

    # Get unexpected discoveries
    discoveries = [
        {
            "source": r.source_node_type,
            "target": r.target_node_type,
            "reference_type": r.reference_type,
            "reference_field": r.reference_field,
            "confidence": float(r.confidence) if r.confidence else None,
            "is_valid": r.is_valid
        }
        for r in relationships if not r.was_expected
    ]

    return {
        "run_id": run_id,
        "spec_version": run.spec_version,
        "message_root": run.message_root,
        "airline_code": run.airline_code,
        "statistics": {
            "total_relationships": total,
            "valid_relationships": valid,
            "broken_relationships": broken,
            "expected_relationships": expected,
            "discovered_relationships": discovered,
            "validation_rate": round((valid / total * 100), 2) if total > 0 else 0
        },
        "reference_types": type_groups,
        "broken_references": broken_refs,
        "unexpected_discoveries": discoveries
    }


@router.get("/types")
async def get_reference_types(
    db: Session = Depends(get_db_session)
):
    """
    Get list of all discovered reference types across all runs.

    Useful for understanding what types of relationships exist in the system.
    """
    types = db.query(
        NodeRelationship.reference_type,
        func.count(NodeRelationship.id).label('count'),
        func.avg(NodeRelationship.confidence).label('avg_confidence')
    ).group_by(NodeRelationship.reference_type).all()

    return [
        {
            "reference_type": ref_type,
            "total_count": count,
            "average_confidence": round(float(avg_conf), 2) if avg_conf else None
        }
        for ref_type, count, avg_conf in types
    ]
