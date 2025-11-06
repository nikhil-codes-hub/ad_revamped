"""
Run management endpoints for AssistedDiscovery.

Handles creation and monitoring of Pattern Extractor and Discovery runs.
"""

import tempfile
import os
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.models.schemas import RunCreate, RunResponse, RunStatus, ConflictDetectionResponse, ConflictResolution
from app.services.workspace_db import get_workspace_db
from app.services.pattern_extractor_workflow import create_pattern_extractor_workflow
from app.services.discovery_workflow import create_discovery_workflow
from app.services.conflict_detector import create_conflict_detector
from app.models.database import Run, RunKind, RunStatus as DbRunStatus
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=RunResponse)
async def create_run(
    kind: str = Query(..., regex="^(pattern_extractor|discovery)$", description="Type of run: pattern_extractor or discovery"),
    file: UploadFile = File(...),
    workspace: str = Query("default", description="Workspace name (e.g., default, SQ, LATAM)"),
    target_version: Optional[str] = Query(None, description="Target NDC version for discovery (not used - kept for backwards compatibility)"),
    target_message_root: Optional[str] = Query(None, description="Target message root for discovery (not used - kept for backwards compatibility)"),
    target_airline_code: Optional[str] = Query(None, description="Target airline code for discovery (not used - kept for backwards compatibility)"),
    allow_cross_airline: bool = Query(True, description="Enable cross-airline pattern matching for discovery (always enabled)"),
    conflict_resolution: Optional[str] = Query(None, regex="^(replace|keep_both|merge)$", description="How to resolve pattern conflicts (pattern_extractor only)")
) -> RunResponse:
    """
    Create a new Pattern Extractor or Discovery run.

    - **kind**: Type of run - 'pattern_extractor' for pattern learning, 'discovery' for pattern matching
    - **file**: XML file to process (OrderViewRS format)
    - **target_version**: (Not used - kept for backwards compatibility)
    - **target_message_root**: (Not used - kept for backwards compatibility)
    - **target_airline_code**: (Not used - kept for backwards compatibility)
    - **allow_cross_airline**: (Always enabled - kept for backwards compatibility)
    - **conflict_resolution**: (Pattern Extractor only) How to handle pattern conflicts:
        - 'replace': Delete existing conflicting patterns (recommended)
        - 'keep_both': Keep both old and new patterns (may cause ambiguous matches)
        - 'merge': Mark old patterns as superseded by new ones

    **Note**: Discovery now matches across ALL airlines, ALL NDC versions, and ALL message types for maximum coverage.
    """
    logger.info(f"Creating new {kind} run: {file.filename}")

    # Validate file type
    if not file.filename.lower().endswith('.xml'):
        raise HTTPException(status_code=400, detail="File must be an XML file")

    # Validate file size (basic check)
    if file.size and file.size > 100 * 1024 * 1024:  # 100MB limit
        raise HTTPException(status_code=400, detail="File too large (max 100MB)")

    logger.info(f"Creating {kind} run in workspace: {workspace}, file: {file.filename}")

    # Get workspace database session
    db_generator = get_workspace_db(workspace)
    db = next(db_generator)

    try:
        # Create temporary file for processing
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xml') as temp_file:
            # Read and save uploaded content
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name

        try:
            # Run appropriate workflow based on kind
            if kind == "pattern_extractor":
                workflow = create_pattern_extractor_workflow(db)
                results = workflow.run_discovery(
                    temp_file_path,
                    conflict_resolution=conflict_resolution
                )
            elif kind == "discovery":
                workflow = create_discovery_workflow(db)
                results = workflow.run_identify(
                    temp_file_path,
                    target_version=None,  # Cross-version matching always enabled
                    target_message_root=None,  # Cross-message matching always enabled
                    target_airline_code=None,  # Cross-airline matching always enabled
                    allow_cross_airline=True  # Always enabled
                )
            else:
                raise HTTPException(status_code=400, detail=f"Invalid run kind: {kind}")

            # Convert status to API enum
            api_status = RunStatus.STARTED
            if results['status'] == 'completed':
                api_status = RunStatus.COMPLETED
            elif results['status'] == 'failed':
                api_status = RunStatus.FAILED

            return RunResponse(
                id=results['run_id'],
                kind=kind,
                status=api_status,
                filename=file.filename,
                file_size_bytes=results.get('file_size_bytes'),
                created_at=results['started_at'],
                finished_at=results.get('finished_at'),
                duration_seconds=results.get('duration_seconds'),
                elements_analyzed=results.get('node_facts_extracted', 0),
                subtrees_processed=results.get('subtrees_processed', 0),
                spec_version=results.get('version_info', {}).get('spec_version') if results.get('version_info') else None,
                message_root=results.get('version_info', {}).get('message_root') if results.get('version_info') else None,
                airline_code=results.get('version_info', {}).get('airline_code') if results.get('version_info') else None,
                airline_name=results.get('version_info', {}).get('airline_name') if results.get('version_info') else None,
                error_details=results.get('error_details'),
                warning=results.get('warning')
            )

        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_file_path)
            except OSError:
                pass

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create run: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        # Clean up database session
        try:
            next(db_generator)
        except StopIteration:
            pass


@router.get("/{run_id}", response_model=RunResponse)
async def get_run_status(
    run_id: str,
    workspace: str = Query("default", description="Workspace name")
) -> RunResponse:
    """
    Get the status and details of a specific run.

    - **run_id**: Unique identifier for the run
    - **workspace**: Workspace name (default: 'default')
    """
    logger.info(f"Getting run status: {run_id} from workspace: {workspace}")

    # Get workspace database session
    db_generator = get_workspace_db(workspace)
    db = next(db_generator)

    try:
        # Get run from database using PatternExtractorWorkflow (has get_run_summary method)
        workflow = create_pattern_extractor_workflow(db)
        run_summary = workflow.get_run_summary(run_id)
    finally:
        try:
            next(db_generator)
        except StopIteration:
            pass

    if not run_summary:
        raise HTTPException(status_code=404, detail="Run not found")

    # Convert database status to API enum
    api_status = RunStatus.STARTED
    if run_summary['status'] == 'completed':
        api_status = RunStatus.COMPLETED
    elif run_summary['status'] == 'failed':
        api_status = RunStatus.FAILED
    elif run_summary['status'] == 'in_progress':
        api_status = RunStatus.IN_PROGRESS

    return RunResponse(
        id=run_summary['run_id'],
        kind=run_summary['kind'],
        status=api_status,
        filename=run_summary['filename'],
        file_size_bytes=run_summary['file_size_bytes'],
        created_at=run_summary['started_at'],
        finished_at=run_summary['finished_at'],
        elements_analyzed=run_summary['node_facts_count'],
        duration_seconds=run_summary['duration_seconds'],
        spec_version=run_summary['spec_version'],
        message_root=run_summary['message_root'],
        airline_code=run_summary.get('airline_code'),
        airline_name=run_summary.get('airline_name'),
        error_details=run_summary['error_details']
    )


@router.get("/{run_id}/report")
async def get_run_report(run_id: str):
    """
    Get the detailed report for a completed run.

    For Discovery runs: Returns discovered patterns and statistics
    For Identify runs: Returns gap analysis and coverage metrics
    """
    logger.info("Getting run report", run_id=run_id)

    # TODO: Implement report generation
    # 1. Query run details
    # 2. Generate appropriate report based on run kind
    # 3. Include coverage metrics, patterns, gaps, etc.

    # Placeholder response
    return JSONResponse(
        content={
            "run_id": run_id,
            "report_type": "discovery",
            "summary": {
                "patterns_discovered": 25,
                "nodes_processed": 450,
                "coverage_percentage": 85.2
            },
            "patterns": [],
            "generated_at": "2025-09-26T11:50:00Z"
        }
    )


@router.get("/", response_model=List[RunResponse])
async def list_runs(
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    kind: Optional[str] = Query(default=None, regex="^(pattern_extractor|discovery)$"),
    workspace: str = Query("default", description="Workspace name")
) -> List[RunResponse]:
    """
    List recent runs with pagination.

    - **limit**: Maximum number of runs to return (1-100)
    - **offset**: Number of runs to skip for pagination
    - **kind**: Filter by run type (pattern_extractor or discovery) (optional)
    - **workspace**: Workspace name (default: 'default')
    """
    logger.info(f"Listing runs from workspace: {workspace}, limit={limit}, offset={offset}, kind={kind}")

    # Get workspace database session
    db_generator = get_workspace_db(workspace)
    db = next(db_generator)

    try:
        # Query database for runs
        query = db.query(Run).order_by(Run.started_at.desc())

        # Apply kind filter if specified
        if kind:
            query = query.filter(Run.kind == kind)

        # Apply pagination
        runs = query.offset(offset).limit(limit).all()

        # Convert to response format
        response_runs = []
        for run in runs:
            # Convert database status to API enum
            api_status = RunStatus.STARTED
            if run.status == 'completed':
                api_status = RunStatus.COMPLETED
            elif run.status == 'failed':
                api_status = RunStatus.FAILED
            elif run.status == 'in_progress':
                api_status = RunStatus.IN_PROGRESS

            response_runs.append(RunResponse(
                id=run.id,
                kind=run.kind,
                status=api_status,
                filename=run.filename,
                file_size_bytes=run.file_size_bytes,
                created_at=run.started_at.isoformat() if run.started_at else None,
                finished_at=run.finished_at.isoformat() if run.finished_at else None,
                duration_seconds=run.duration_seconds,
                node_facts_count=0,  # We'd need to count these if required
                spec_version=run.spec_version,
                message_root=run.message_root,
                error_details=run.error_details
            ))

        return response_runs
    finally:
        try:
            next(db_generator)
        except StopIteration:
            pass


@router.post("/preflight-check", response_model=ConflictDetectionResponse)
async def check_pattern_conflicts(
    workspace: str = Query("default", description="Workspace name"),
    spec_version: Optional[str] = Query(None, description="NDC spec version (e.g., 21.3)"),
    message_root: Optional[str] = Query(None, description="Message root (e.g., AirShoppingRS)"),
    airline_code: Optional[str] = Query(None, description="Airline code (e.g., AS)"),
    node_paths: List[str] = Query(..., description="List of node paths to extract (e.g., /PaxList)")
) -> ConflictDetectionResponse:
    """
    Check for pattern conflicts before running extraction.

    Detects conflicts when:
    - Extracting a parent node when child patterns already exist (e.g., extracting /PaxList when /PaxList/Pax exists)
    - Extracting a child node when parent pattern already exists (e.g., extracting /Pax when /PaxList exists)

    Returns a list of conflicts with recommendations for resolution.
    """
    logger.info(f"Preflight check for {len(node_paths)} paths in workspace: {workspace}")

    if not node_paths:
        raise HTTPException(status_code=400, detail="No node paths provided")

    if not spec_version or not message_root:
        raise HTTPException(
            status_code=400,
            detail="spec_version and message_root are required for conflict detection"
        )

    # Get workspace database session
    db_generator = get_workspace_db(workspace)
    db = next(db_generator)

    try:
        # Create conflict detector
        detector = create_conflict_detector(db)

        # Check for conflicts
        result = detector.check_conflicts(
            extracting_paths=node_paths,
            spec_version=spec_version,
            message_root=message_root,
            airline_code=airline_code
        )

        logger.info(f"Preflight check complete: {len(result.conflicts)} conflicts detected")
        return result

    except Exception as e:
        logger.error(f"Error during preflight check: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Preflight check failed: {str(e)}")

    finally:
        try:
            next(db_generator)
        except StopIteration:
            pass