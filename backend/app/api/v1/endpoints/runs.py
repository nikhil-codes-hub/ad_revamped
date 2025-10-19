"""
Run management endpoints for AssistedDiscovery.

Handles creation and monitoring of Discovery and Identify runs.
"""

import tempfile
import os
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.models.schemas import RunCreate, RunResponse, RunStatus
from app.services.workspace_db import get_workspace_db
from app.services.discovery_workflow import create_discovery_workflow
from app.services.identify_workflow import create_identify_workflow
from app.models.database import Run, RunKind, RunStatus as DbRunStatus
from app.repositories.interfaces import IUnitOfWork
from app.repositories.sqlalchemy.unit_of_work import SQLAlchemyUnitOfWork
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=RunResponse)
async def create_run(
    kind: str = Query(..., regex="^(discovery|identify)$", description="Type of run: discovery or identify"),
    file: UploadFile = File(...),
    workspace: str = Query("default", description="Workspace name (e.g., default, SQ, LATAM)"),
    target_version: Optional[str] = Query(None, description="Target NDC version for identify (e.g., 18.1)"),
    target_message_root: Optional[str] = Query(None, description="Target message root for identify (e.g., OrderViewRS)"),
    target_airline_code: Optional[str] = Query(None, description="Target airline code for identify (e.g., SQ, AF)")
) -> RunResponse:
    """
    Create a new Discovery or Identify run.

    - **kind**: Type of run - 'discovery' for pattern learning, 'identify' for pattern matching
    - **file**: XML file to process (OrderViewRS format)
    - **target_version**: (Identify only) Specific NDC version to match against
    - **target_message_root**: (Identify only) Specific message root to match against
    - **target_airline_code**: (Identify only) Specific airline code to match against
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
            # Create Unit of Work from database session
            uow = SQLAlchemyUnitOfWork(db)

            # Run appropriate workflow based on kind
            if kind == "discovery":
                workflow = create_discovery_workflow(uow)
                results = workflow.run_discovery(temp_file_path)
            elif kind == "identify":
                workflow = create_identify_workflow(uow)
                results = workflow.run_identify(
                    temp_file_path,
                    target_version=target_version,
                    target_message_root=target_message_root,
                    target_airline_code=target_airline_code
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
                node_facts_count=results.get('node_facts_extracted', 0),
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
        # Create Unit of Work from database session
        uow = SQLAlchemyUnitOfWork(db)

        # Get run from database
        workflow = create_discovery_workflow(uow)
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
        node_facts_count=run_summary['node_facts_count'],
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
    kind: Optional[str] = Query(default=None, regex="^(discovery|identify)$"),
    workspace: str = Query("default", description="Workspace name")
) -> List[RunResponse]:
    """
    List recent runs with pagination.

    - **limit**: Maximum number of runs to return (1-100)
    - **offset**: Number of runs to skip for pagination
    - **kind**: Filter by run type (optional)
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