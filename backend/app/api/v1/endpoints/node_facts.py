"""
Node facts endpoints for AssistedDiscovery.

Handles retrieval and querying of extracted node facts.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
import structlog
import json
from sqlalchemy.orm import Session

from app.models.schemas import NodeFactResponse
from app.models.database import NodeFact
from app.services.workspace_db import get_workspace_db
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/", response_model=List[NodeFactResponse])
async def list_node_facts(
    run_id: Optional[str] = Query(None, description="Filter by specific run ID"),
    section_path: Optional[str] = Query(None, description="Filter by section path"),
    node_type: Optional[str] = Query(None, description="Filter by node type"),
    spec_version: Optional[str] = Query(None, description="Filter by NDC version"),
    message_root: Optional[str] = Query(None, description="Filter by message root"),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum node facts to return"),
    offset: int = Query(default=0, ge=0, description="Number of node facts to skip for pagination"),
    workspace: str = Query("default", description="Workspace name")
) -> List[NodeFactResponse]:
    """
    List extracted node facts with filtering and pagination.

    - **run_id**: Filter by specific processing run
    - **section_path**: Filter by XML section path
    - **node_type**: Filter by node type (e.g., 'ContactInfo', 'BaggageAllowance')
    - **spec_version**: Filter by NDC version
    - **message_root**: Filter by message type
    - **limit**: Maximum facts to return (1-200)
    - **offset**: Skip facts for pagination
    """
    logger.info("Listing node facts",
                run_id=run_id,
                section_path=section_path,
                node_type=node_type,
                limit=limit,
                offset=offset,
                workspace=workspace)

    db_generator = get_workspace_db(workspace)
    db = next(db_generator)

    try:
        # Build query with filters
        query = db.query(NodeFact).order_by(NodeFact.created_at.desc())

        if run_id:
            query = query.filter(NodeFact.run_id == run_id)
        if section_path:
            query = query.filter(NodeFact.section_path.ilike(f"%{section_path}%"))
        if node_type:
            query = query.filter(NodeFact.node_type == node_type)
        if spec_version:
            query = query.filter(NodeFact.spec_version == spec_version)
        if message_root:
            query = query.filter(NodeFact.message_root == message_root)

        # Apply pagination
        node_facts = query.offset(offset).limit(limit).all()

        # Convert to response format
        results = []
        for nf in node_facts:
            # Parse fact_json from string to dict
            try:
                fact_json = json.loads(nf.fact_json) if isinstance(nf.fact_json, str) else nf.fact_json
            except (json.JSONDecodeError, TypeError):
                fact_json = {}

            results.append(NodeFactResponse(
                id=nf.id,
                run_id=nf.run_id,
                spec_version=nf.spec_version,
                message_root=nf.message_root,
                section_path=nf.section_path,
                node_type=nf.node_type,
                node_ordinal=nf.node_ordinal,
                fact_json=fact_json,
                pii_masked=bool(nf.pii_masked),
                created_at=nf.created_at.isoformat() if nf.created_at else ""
            ))

        logger.info(f"Retrieved {len(results)} node facts")
        return results
    finally:
        try:
            next(db_generator)
        except StopIteration:
            pass


@router.get("/{node_fact_id}", response_model=NodeFactResponse)
async def get_node_fact(node_fact_id: int) -> NodeFactResponse:
    """
    Get details of a specific node fact.

    - **node_fact_id**: Unique identifier for the node fact
    """
    logger.info("Getting node fact details", node_fact_id=node_fact_id)

    # TODO: Implement node fact retrieval
    # 1. Query database for node fact details
    # 2. Include associated run information
    # 3. Handle not found cases
    # 4. Ensure PII remains masked

    # Placeholder response
    return NodeFactResponse(
        id=node_fact_id,
        run_id="run_001",
        spec_version="17.2",
        message_root="OrderViewRS",
        section_path="/OrderViewRS/Response/DataLists/PassengerList",
        node_type="Passenger",
        node_ordinal=1,
        fact_json={
            "children": ["PTC", "Birthdate", "Individual", "ContactInfoRef"],
            "attrs": ["PassengerID"],
            "code_values": {"PTC": "ADT"},
            "ids": {"PassengerID": "T1"},
            "refs": {},
            "snippet": "<Passenger PassengerID=T1> PTC=ADT Birthdate=1990-**-**",
            "values": {"PTC": "ADT", "Birthdate": "1990-**-**", "Gender": "Male"}
        },
        pii_masked=True,
        created_at="2025-09-26T11:30:00Z"
    )


@router.get("/{node_fact_id}/associations")
async def get_node_fact_associations(node_fact_id: int):
    """
    Get associations (relationships) for a specific node fact.

    Shows ID references and relationships to other nodes in the same run.
    """
    logger.info("Getting node fact associations", node_fact_id=node_fact_id)

    # TODO: Implement association retrieval
    # 1. Query association_facts table for relationships
    # 2. Include both incoming and outgoing relationships
    # 3. Show relationship types and reference keys

    return {
        "element_id": node_fact_id,
        "outgoing_associations": [],
        "incoming_associations": [],
        "total_associations": 0
    }


@router.get("/stats/summary")
async def get_node_facts_summary(
    run_id: Optional[str] = Query(None, description="Filter by specific run ID"),
    spec_version: Optional[str] = Query(None, description="Filter by NDC version"),
    message_root: Optional[str] = Query(None, description="Filter by message type")
):
    """
    Get summary statistics for node facts.

    Provides counts by node type, section, and other dimensions.
    """
    logger.info("Getting node facts summary",
                run_id=run_id,
                spec_version=spec_version,
                message_root=message_root)

    # TODO: Implement summary statistics
    # 1. Count node facts by various dimensions
    # 2. Calculate PII masking statistics
    # 3. Show distribution by sections and types

    return {
        "filters": {
            "run_id": run_id,
            "spec_version": spec_version,
            "message_root": message_root
        },
        "total_node_facts": 0,
        "node_facts_by_type": {},
        "node_facts_by_section": {},
        "pii_masking_stats": {
            "total_processed": 0,
            "pii_masked": 0,
            "pii_masking_rate": 0.0
        },
        "generated_at": "2025-09-26T11:45:00Z"
    }