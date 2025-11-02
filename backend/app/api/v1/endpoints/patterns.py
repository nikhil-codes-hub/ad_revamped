"""
Pattern management endpoints for AssistedDiscovery.

Handles retrieval and querying of discovered patterns.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel
import structlog

from app.models.schemas import PatternResponse
from app.core.logging import get_logger
from app.services.workspace_db import get_workspace_db
from app.services.pattern_generator import create_pattern_generator
from app.models.database import Pattern
from app.services.llm_extractor import get_llm_extractor

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
    workspace: str = Query("default", description="Workspace name")
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
                offset=offset,
                workspace=workspace)

    db_generator = get_workspace_db(workspace)
    db = next(db_generator)

    try:
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
                last_seen_at=p.last_seen_at.isoformat() if p.last_seen_at else None,
                description=p.description,
                superseded_by=p.superseded_by
            )
            for p in patterns
        ]
    finally:
        try:
            next(db_generator)
        except StopIteration:
            pass


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
        last_seen_at="2025-09-26T11:45:00Z",
        superseded_by=None
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
    workspace: str = Query("default", description="Workspace name")
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
                message_root=message_root,
                workspace=workspace)

    db_generator = get_workspace_db(workspace)
    db = next(db_generator)

    try:
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
                "elements_analyzed": results.get('node_facts_analyzed', 0),
                "pattern_groups": results.get('pattern_groups', 0),
                "patterns_created": results.get('patterns_created', 0),
                "patterns_updated": results.get('patterns_updated', 0)
            },
            "errors": results.get('errors', [])
        }
    finally:
        try:
            next(db_generator)
        except StopIteration:
            pass


class ModifyPatternRequest(BaseModel):
    """Request model for pattern modification."""
    pattern_id: int
    current_description: str
    current_decision_rule: Dict[str, Any]
    additional_requirements: str
    section_path: str
    spec_version: str
    message_root: str


@router.post("/{pattern_id}/modify")
async def modify_pattern(
    pattern_id: int,
    request: ModifyPatternRequest = Body(...),
    workspace: str = Query("default", description="Workspace name")
):
    """
    Modify a pattern using LLM to incorporate additional requirements.

    - **pattern_id**: ID of the pattern to modify
    - **additional_requirements**: User-provided requirements to incorporate
    """
    logger.info("Modifying pattern", pattern_id=pattern_id, workspace=workspace)

    db_generator = get_workspace_db(workspace)
    db = next(db_generator)

    try:
        # Get the pattern from database
        pattern = db.query(Pattern).filter(Pattern.id == pattern_id).first()
        if not pattern:
            raise HTTPException(status_code=404, detail=f"Pattern {pattern_id} not found")

        # Build LLM prompt for pattern modification
        llm_extractor = get_llm_extractor()

        if not llm_extractor.client:
            raise HTTPException(status_code=500, detail="LLM client not initialized. Check API keys configuration.")

        prompt = f"""You are an XML pattern expert. Modify the following pattern to incorporate the user's additional requirements.

**Current Pattern:**
- Section: {request.section_path}
- Specification Version: {request.spec_version}
- Message Root: {request.message_root}
- Description: {request.current_description}

**Current Decision Rule:**
```json
{request.current_decision_rule}
```

**User's Additional Requirements:**
{request.additional_requirements}

**Task:**
1. Analyze the current pattern and the additional requirements
2. Update the decision_rule to incorporate the new requirements
3. Update the description to reflect the changes
4. Provide a brief modification summary

Return a JSON object with:
{{
  "new_description": "Updated description including the new requirements",
  "new_decision_rule": {{ ... updated decision rule ... }},
  "modification_summary": "Brief summary of what changed (2-3 sentences)"
}}

**Important:**
- Preserve the existing structure (node_type, must_have_attributes, child_structure, etc.)
- Only add/modify fields that are affected by the new requirements
- Keep the decision_rule consistent with the pattern schema
- If adding attributes, add them to must_have_attributes or optional_attributes
- If adding child elements, update child_structure accordingly
"""

        try:
            # Call LLM asynchronously
            response = await llm_extractor.client.chat.completions.create(
                model=llm_extractor.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an XML pattern modification expert. Analyze patterns and incorporate new requirements while maintaining structural consistency."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )

            import json
            result = json.loads(response.choices[0].message.content)

            # Update the pattern in database
            pattern.description = result.get('new_description', pattern.description)
            pattern.decision_rule = result.get('new_decision_rule', pattern.decision_rule)

            db.commit()
            db.refresh(pattern)

            logger.info("Pattern modified successfully", pattern_id=pattern_id)

            return {
                "success": True,
                "pattern_id": pattern_id,
                "new_description": result.get('new_description'),
                "new_decision_rule": result.get('new_decision_rule'),
                "modification_summary": result.get('modification_summary'),
                "tokens_used": response.usage.total_tokens
            }

        except Exception as e:
            logger.error("LLM modification failed", error=str(e))
            raise HTTPException(status_code=500, detail=f"LLM modification failed: {str(e)}")

    finally:
        try:
            next(db_generator)
        except StopIteration:
            pass


@router.delete("/{pattern_id}")
async def delete_pattern(
    pattern_id: int,
    workspace: str = Query("default", description="Workspace name")
) -> Dict[str, Any]:
    """
    Delete a pattern by ID.

    **WARNING**: This permanently deletes the pattern and all associated matches.
    Use with caution.

    - **pattern_id**: ID of the pattern to delete
    - **workspace**: Workspace name (default: 'default')

    Returns:
        Success message with deleted pattern information
    """
    logger.info(f"Deleting pattern {pattern_id} from workspace: {workspace}")

    # Get workspace database session
    db_generator = get_workspace_db(workspace)
    db = next(db_generator)

    try:
        # Find the pattern
        pattern = db.query(Pattern).filter(Pattern.id == pattern_id).first()

        if not pattern:
            raise HTTPException(status_code=404, detail=f"Pattern {pattern_id} not found")

        # Store pattern info for response before deletion
        deleted_info = {
            "pattern_id": pattern.id,
            "section_path": pattern.section_path,
            "spec_version": pattern.spec_version,
            "message_root": pattern.message_root,
            "airline_code": pattern.airline_code,
            "node_type": pattern.decision_rule.get('node_type', 'Unknown') if pattern.decision_rule else 'Unknown',
            "times_seen": pattern.times_seen,
            "created_at": pattern.created_at.isoformat() if pattern.created_at else None
        }

        # Delete the pattern (CASCADE will delete associated pattern_matches)
        db.delete(pattern)
        db.commit()

        logger.info(f"Pattern {pattern_id} deleted successfully", deleted_info=deleted_info)

        return {
            "success": True,
            "message": f"Pattern {pattern_id} deleted successfully",
            "deleted_pattern": deleted_info
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete pattern {pattern_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to delete pattern: {str(e)}")

    finally:
        try:
            next(db_generator)
        except StopIteration:
            pass


@router.delete("/bulk")
async def delete_patterns_bulk(
    pattern_ids: List[int] = Body(..., description="List of pattern IDs to delete"),
    workspace: str = Query("default", description="Workspace name")
) -> Dict[str, Any]:
    """
    Delete multiple patterns at once.

    **WARNING**: This permanently deletes the patterns and all associated matches.
    Use with caution.

    - **pattern_ids**: List of pattern IDs to delete
    - **workspace**: Workspace name (default: 'default')

    Returns:
        Success message with deletion statistics
    """
    logger.info(f"Bulk deleting {len(pattern_ids)} patterns from workspace: {workspace}")

    if not pattern_ids:
        raise HTTPException(status_code=400, detail="No pattern IDs provided")

    # Get workspace database session
    db_generator = get_workspace_db(workspace)
    db = next(db_generator)

    try:
        # Find all patterns
        patterns = db.query(Pattern).filter(Pattern.id.in_(pattern_ids)).all()

        if not patterns:
            raise HTTPException(status_code=404, detail="No patterns found with provided IDs")

        found_ids = {p.id for p in patterns}
        missing_ids = set(pattern_ids) - found_ids

        # Store pattern info for response
        deleted_patterns = [
            {
                "pattern_id": p.id,
                "section_path": p.section_path,
                "node_type": p.decision_rule.get('node_type', 'Unknown') if p.decision_rule else 'Unknown'
            }
            for p in patterns
        ]

        # Delete all patterns (CASCADE will delete associated pattern_matches)
        deleted_count = db.query(Pattern).filter(Pattern.id.in_(found_ids)).delete(synchronize_session=False)
        db.commit()

        logger.info(f"Bulk deletion complete: {deleted_count} patterns deleted")

        return {
            "success": True,
            "message": f"Successfully deleted {deleted_count} patterns",
            "deleted_count": deleted_count,
            "deleted_patterns": deleted_patterns,
            "missing_ids": list(missing_ids) if missing_ids else []
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to bulk delete patterns: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to bulk delete patterns: {str(e)}")

    finally:
        try:
            next(db_generator)
        except StopIteration:
            pass