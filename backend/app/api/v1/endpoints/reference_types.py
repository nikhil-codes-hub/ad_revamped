"""
Reference Types management endpoints for AssistedDiscovery.

Manages the glossary of reference types used in NDC XML node relationships.
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.orm import Session

from app.services.workspace_db import get_workspace_db
from app.models.database import ReferenceType

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/")
async def list_reference_types(
    category: Optional[str] = Query(None, description="Filter by category"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    workspace: str = Query("default", description="Workspace name")
):
    """
    Get list of reference types with optional filtering.

    Categories: passenger, segment, journey, baggage, price, service, order
    """
    logger.info(f"Listing reference types: category={category}, is_active={is_active}, workspace={workspace}")

    db_generator = get_workspace_db(workspace)
    db = next(db_generator)

    try:
        query = db.query(ReferenceType)

        if category:
            query = query.filter(ReferenceType.category == category)
        if is_active is not None:
            query = query.filter(ReferenceType.is_active == is_active)

        reference_types = query.order_by(ReferenceType.category, ReferenceType.display_name).all()

        results = []
        for ref_type in reference_types:
            results.append({
                'id': ref_type.id,
                'reference_type': ref_type.reference_type,
                'display_name': ref_type.display_name,
                'description': ref_type.description,
                'example': ref_type.example,
                'category': ref_type.category,
                'is_active': ref_type.is_active,
                'created_at': ref_type.created_at.isoformat() if ref_type.created_at else None,
                'created_by': ref_type.created_by
            })

        return {
            'total': len(results),
            'reference_types': results
        }
    finally:
        try:
            next(db_generator)
        except StopIteration:
            pass


@router.get("/{ref_type_id}")
async def get_reference_type(
    ref_type_id: int,
    workspace: str = Query("default", description="Workspace name")
):
    """Get a specific reference type by ID."""
    logger.info(f"Getting reference type: {ref_type_id}, workspace: {workspace}")

    db_generator = get_workspace_db(workspace)
    db = next(db_generator)

    try:
        ref_type = db.query(ReferenceType).filter(ReferenceType.id == ref_type_id).first()

        if not ref_type:
            raise HTTPException(status_code=404, detail=f"Reference type {ref_type_id} not found")

        return {
            'id': ref_type.id,
            'reference_type': ref_type.reference_type,
            'display_name': ref_type.display_name,
            'description': ref_type.description,
            'example': ref_type.example,
            'category': ref_type.category,
            'is_active': ref_type.is_active,
            'created_at': ref_type.created_at.isoformat() if ref_type.created_at else None,
            'updated_at': ref_type.updated_at.isoformat() if ref_type.updated_at else None,
            'created_by': ref_type.created_by
        }
    finally:
        try:
            next(db_generator)
        except StopIteration:
            pass


@router.post("/")
async def create_reference_type(
    reference_type: str = Query(..., description="Unique reference type identifier (e.g., infant_parent)"),
    display_name: str = Query(..., description="Human-readable display name"),
    description: str = Query(..., description="Description of what this reference represents"),
    example: Optional[str] = Query(None, description="Example of this reference type"),
    category: Optional[str] = Query(None, description="Category: passenger, segment, journey, baggage, price, service"),
    created_by: Optional[str] = Query(None, description="User creating this reference type"),
    workspace: str = Query("default", description="Workspace name")
):
    """
    Create a new reference type.

    The reference_type must be unique and will be used as the identifier
    in node configurations.
    """
    logger.info(f"Creating reference type: {reference_type}, workspace: {workspace}")

    db_generator = get_workspace_db(workspace)
    db = next(db_generator)

    try:
        # Check if already exists
        existing = db.query(ReferenceType).filter(
            ReferenceType.reference_type == reference_type
        ).first()

        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Reference type '{reference_type}' already exists"
            )

        # Create new reference type
        new_ref_type = ReferenceType(
            reference_type=reference_type,
            display_name=display_name,
            description=description,
            example=example,
            category=category,
            is_active=True,
            created_by=created_by or "user"
        )

        db.add(new_ref_type)
        db.commit()
        db.refresh(new_ref_type)

        logger.info(f"Created reference type: {new_ref_type.id} - {reference_type}")

        return {
            'success': True,
            'id': new_ref_type.id,
            'reference_type': new_ref_type.reference_type,
            'message': f"Reference type '{reference_type}' created successfully"
        }
    finally:
        try:
            next(db_generator)
        except StopIteration:
            pass


@router.put("/{ref_type_id}")
async def update_reference_type(
    ref_type_id: int,
    display_name: Optional[str] = Query(None),
    description: Optional[str] = Query(None),
    example: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    workspace: str = Query("default", description="Workspace name")
):
    """Update an existing reference type."""
    logger.info(f"Updating reference type: {ref_type_id}, workspace: {workspace}")

    db_generator = get_workspace_db(workspace)
    db = next(db_generator)

    try:
        ref_type = db.query(ReferenceType).filter(ReferenceType.id == ref_type_id).first()

        if not ref_type:
            raise HTTPException(status_code=404, detail=f"Reference type {ref_type_id} not found")

        # Update fields
        if display_name is not None:
            ref_type.display_name = display_name
        if description is not None:
            ref_type.description = description
        if example is not None:
            ref_type.example = example
        if category is not None:
            ref_type.category = category
        if is_active is not None:
            ref_type.is_active = is_active

        db.commit()
        db.refresh(ref_type)

        logger.info(f"Updated reference type: {ref_type_id}")

        return {
            'success': True,
            'id': ref_type.id,
            'reference_type': ref_type.reference_type,
            'message': f"Reference type '{ref_type.reference_type}' updated successfully"
        }
    finally:
        try:
            next(db_generator)
        except StopIteration:
            pass


@router.delete("/{ref_type_id}")
async def delete_reference_type(
    ref_type_id: int,
    workspace: str = Query("default", description="Workspace name")
):
    """
    Delete a reference type.

    Note: This will fail if the reference type is currently being used
    in any node configurations.
    """
    logger.info(f"Deleting reference type: {ref_type_id}, workspace: {workspace}")

    db_generator = get_workspace_db(workspace)
    db = next(db_generator)

    try:
        ref_type = db.query(ReferenceType).filter(ReferenceType.id == ref_type_id).first()

        if not ref_type:
            raise HTTPException(status_code=404, detail=f"Reference type {ref_type_id} not found")

        # Check if it's a system reference type
        if ref_type.created_by == 'system':
            raise HTTPException(
                status_code=400,
                detail="Cannot delete system reference types. Set is_active=False instead."
            )

        db.delete(ref_type)
        db.commit()

        logger.info(f"Deleted reference type: {ref_type_id} - {ref_type.reference_type}")

        return {
            'success': True,
            'message': f"Reference type '{ref_type.reference_type}' deleted successfully"
        }
    finally:
        try:
            next(db_generator)
        except StopIteration:
            pass


@router.get("/categories/list")
async def list_categories(workspace: str = Query("default", description="Workspace name")):
    """Get list of all categories in use."""
    db_generator = get_workspace_db(workspace)
    db = next(db_generator)

    try:
        categories = db.query(ReferenceType.category).distinct().all()
        return {
            'categories': [cat[0] for cat in categories if cat[0]]
        }
    finally:
        try:
            next(db_generator)
        except StopIteration:
            pass
