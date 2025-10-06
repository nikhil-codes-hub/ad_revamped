"""
Node configuration endpoints for AssistedDiscovery.

Handles BA-managed node extraction rules and reference configurations.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from lxml import etree
import logging

from app.services.database import get_db_session
from app.models.database import NodeConfiguration
from app.services.xml_parser import detect_ndc_version_fast

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/analyze")
async def analyze_xml_structure(
    file: UploadFile = File(...),
    db: Session = Depends(get_db_session)
):
    """
    Analyze uploaded XML to discover all node types and their paths.

    Returns a list of discovered nodes that can be configured.
    """
    logger.info(f"Analyzing XML structure from file: {file.filename}")

    try:
        # Read XML content
        content = await file.read()

        # Detect version
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(delete=False, suffix='.xml') as tmp_file:
            tmp_file.write(content)
            tmp_file_path = tmp_file.name

        try:
            version_info = detect_ndc_version_fast(tmp_file_path)

            if not version_info or not version_info.spec_version:
                raise HTTPException(status_code=400, detail="Could not detect NDC version from XML")

            # Parse XML to extract all node paths
            parser = etree.XMLParser(recover=True)
            tree = etree.parse(tmp_file_path, parser)
            root = tree.getroot()

            # Recursively discover all nodes
            discovered_nodes = []

            def extract_nodes(element, path=""):
                # Remove namespace
                tag = element.tag.split('}')[-1] if '}' in element.tag else element.tag

                current_path = f"{path}/{tag}" if path else tag

                # Add this node
                discovered_nodes.append({
                    "node_type": tag,
                    "section_path": current_path,
                    "has_children": len(element) > 0,
                    "has_attributes": len(element.attrib) > 0,
                    "child_count": len(element)
                })

                # Recursively process children
                for child in element:
                    extract_nodes(child, current_path)

            extract_nodes(root)

            # Get existing configurations
            existing_configs = db.query(NodeConfiguration).filter(
                NodeConfiguration.spec_version == version_info.spec_version,
                NodeConfiguration.message_root == version_info.message_root
            ).all()

            existing_paths = {config.section_path: config for config in existing_configs}

            # Merge discovered nodes with existing configs
            result_nodes = []
            seen_paths = set()

            for node in discovered_nodes:
                path = node['section_path']
                if path in seen_paths:
                    continue
                seen_paths.add(path)

                # Check if config exists
                if path in existing_paths:
                    config = existing_paths[path]
                    result_nodes.append({
                        **node,
                        "config_id": config.id,
                        "enabled": config.enabled,
                        "expected_references": config.expected_references or [],
                        "ba_remarks": config.ba_remarks,
                        "is_configured": True
                    })
                else:
                    result_nodes.append({
                        **node,
                        "config_id": None,
                        "enabled": False,  # Default to disabled
                        "expected_references": [],
                        "ba_remarks": "",
                        "is_configured": False
                    })

            return {
                "spec_version": version_info.spec_version,
                "message_root": version_info.message_root,
                "airline_code": version_info.airline_code,
                "total_nodes": len(result_nodes),
                "configured_nodes": len(existing_paths),
                "nodes": result_nodes
            }

        finally:
            os.unlink(tmp_file_path)

    except Exception as e:
        logger.error(f"Error analyzing XML: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error analyzing XML: {str(e)}")


@router.get("/")
async def list_node_configurations(
    spec_version: Optional[str] = Query(None),
    message_root: Optional[str] = Query(None),
    airline_code: Optional[str] = Query(None),
    enabled_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db_session)
):
    """
    List all node configurations with optional filtering.
    """
    logger.info("Listing node configurations")

    query = db.query(NodeConfiguration)

    if spec_version:
        query = query.filter(NodeConfiguration.spec_version == spec_version)
    if message_root:
        query = query.filter(NodeConfiguration.message_root == message_root)
    if airline_code:
        query = query.filter(NodeConfiguration.airline_code == airline_code)
    if enabled_only:
        query = query.filter(NodeConfiguration.enabled == True)

    total = query.count()
    configs = query.order_by(NodeConfiguration.section_path).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "configurations": [
            {
                "id": config.id,
                "spec_version": config.spec_version,
                "message_root": config.message_root,
                "airline_code": config.airline_code,
                "node_type": config.node_type,
                "section_path": config.section_path,
                "enabled": config.enabled,
                "expected_references": config.expected_references or [],
                "ba_remarks": config.ba_remarks,
                "created_at": config.created_at.isoformat() if config.created_at else None,
                "updated_at": config.updated_at.isoformat() if config.updated_at else None,
                "created_by": config.created_by
            }
            for config in configs
        ]
    }


@router.post("/")
async def create_node_configuration(
    spec_version: str,
    message_root: str,
    node_type: str,
    section_path: str,
    airline_code: Optional[str] = None,
    enabled: bool = True,
    expected_references: Optional[List[str]] = None,
    ba_remarks: Optional[str] = None,
    created_by: Optional[str] = None,
    db: Session = Depends(get_db_session)
):
    """
    Create a new node configuration.
    """
    logger.info(f"Creating node configuration for {section_path}")

    # Check if already exists
    existing = db.query(NodeConfiguration).filter(
        NodeConfiguration.spec_version == spec_version,
        NodeConfiguration.message_root == message_root,
        NodeConfiguration.airline_code == airline_code,
        NodeConfiguration.section_path == section_path
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Configuration already exists for this node")

    config = NodeConfiguration(
        spec_version=spec_version,
        message_root=message_root,
        airline_code=airline_code,
        node_type=node_type,
        section_path=section_path,
        enabled=enabled,
        expected_references=expected_references,
        ba_remarks=ba_remarks,
        created_by=created_by
    )

    db.add(config)
    db.commit()
    db.refresh(config)

    return {
        "success": True,
        "config_id": config.id,
        "message": "Node configuration created successfully"
    }


@router.put("/{config_id}")
async def update_node_configuration(
    config_id: int,
    enabled: Optional[bool] = None,
    expected_references: Optional[List[str]] = None,
    ba_remarks: Optional[str] = None,
    created_by: Optional[str] = None,
    db: Session = Depends(get_db_session)
):
    """
    Update an existing node configuration.
    """
    logger.info(f"Updating node configuration {config_id}")

    config = db.query(NodeConfiguration).filter(NodeConfiguration.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    if enabled is not None:
        config.enabled = enabled
    if expected_references is not None:
        config.expected_references = expected_references
    if ba_remarks is not None:
        config.ba_remarks = ba_remarks
    if created_by is not None:
        config.created_by = created_by

    db.commit()
    db.refresh(config)

    return {
        "success": True,
        "config_id": config.id,
        "message": "Node configuration updated successfully"
    }


@router.delete("/{config_id}")
async def delete_node_configuration(
    config_id: int,
    db: Session = Depends(get_db_session)
):
    """
    Delete a node configuration.
    """
    logger.info(f"Deleting node configuration {config_id}")

    config = db.query(NodeConfiguration).filter(NodeConfiguration.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    db.delete(config)
    db.commit()

    return {
        "success": True,
        "message": "Node configuration deleted successfully"
    }


@router.post("/copy-to-versions")
async def copy_configurations_to_versions(
    source_spec_version: str,
    source_message_root: str,
    target_versions: List[str],
    source_airline_code: Optional[str] = None,
    target_airline_code: Optional[str] = None,
    db: Session = Depends(get_db_session)
):
    """
    Copy configurations from one version to multiple other versions.

    Useful for applying 18.1 configurations to all other NDC versions.
    """
    logger.info(f"Copying configs from {source_spec_version}/{source_message_root} to versions: {target_versions}")

    # Get source configurations
    source_configs_query = db.query(NodeConfiguration).filter(
        NodeConfiguration.spec_version == source_spec_version,
        NodeConfiguration.message_root == source_message_root
    )

    if source_airline_code:
        # Specific airline requested
        source_configs_query = source_configs_query.filter(NodeConfiguration.airline_code == source_airline_code)
        source_configs = source_configs_query.all()

        if not source_configs:
            raise HTTPException(
                status_code=404,
                detail=f"No configurations found for {source_spec_version}/{source_message_root}/{source_airline_code}"
            )
    else:
        # No airline specified - try to find configs intelligently
        # Priority 1: Global configs (airline_code = NULL)
        global_configs = source_configs_query.filter(NodeConfiguration.airline_code == None).all()

        if global_configs:
            source_configs = global_configs
            logger.info(f"Using {len(global_configs)} global configurations (airline_code=NULL)")
        else:
            # Priority 2: Get configs from first available airline
            all_configs = source_configs_query.all()
            if all_configs:
                # Group by airline and pick first
                first_airline = all_configs[0].airline_code
                source_configs = [c for c in all_configs if c.airline_code == first_airline]
                logger.info(f"Using {len(source_configs)} configurations from airline: {first_airline}")
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"No configurations found for {source_spec_version}/{source_message_root}"
                )

    created_count = 0
    skipped_count = 0
    errors = []

    for target_version in target_versions:
        for source_config in source_configs:
            try:
                # Check if config already exists for target version
                existing = db.query(NodeConfiguration).filter(
                    NodeConfiguration.spec_version == target_version,
                    NodeConfiguration.message_root == source_message_root,
                    NodeConfiguration.airline_code == (target_airline_code if target_airline_code is not None else source_config.airline_code),
                    NodeConfiguration.section_path == source_config.section_path
                ).first()

                if existing:
                    skipped_count += 1
                    continue

                # Create new config for target version
                new_config = NodeConfiguration(
                    spec_version=target_version,
                    message_root=source_message_root,
                    airline_code=target_airline_code if target_airline_code is not None else source_config.airline_code,
                    node_type=source_config.node_type,
                    section_path=source_config.section_path,
                    enabled=source_config.enabled,
                    expected_references=source_config.expected_references,
                    ba_remarks=source_config.ba_remarks,
                    created_by=source_config.created_by
                )
                db.add(new_config)
                created_count += 1

            except Exception as e:
                errors.append(f"Error copying {source_config.section_path} to {target_version}: {str(e)}")

    db.commit()

    return {
        "success": len(errors) == 0,
        "source_version": source_spec_version,
        "target_versions": target_versions,
        "source_configs": len(source_configs),
        "created": created_count,
        "skipped": skipped_count,
        "errors": errors
    }


@router.post("/bulk-update")
async def bulk_update_configurations(
    configurations: List[dict],
    db: Session = Depends(get_db_session)
):
    """
    Bulk update multiple node configurations.

    Useful for saving changes from the editable table in the UI.
    """
    logger.info(f"Bulk updating {len(configurations)} configurations")

    updated_count = 0
    created_count = 0
    errors = []

    for config_data in configurations:
        try:
            config_id = config_data.get('config_id')

            if config_id:
                # Update existing
                config = db.query(NodeConfiguration).filter(NodeConfiguration.id == config_id).first()
                if config:
                    config.enabled = config_data.get('enabled', config.enabled)
                    config.expected_references = config_data.get('expected_references', config.expected_references)
                    config.ba_remarks = config_data.get('ba_remarks', config.ba_remarks)
                    updated_count += 1
            else:
                # Create new
                config = NodeConfiguration(
                    spec_version=config_data['spec_version'],
                    message_root=config_data['message_root'],
                    airline_code=config_data.get('airline_code'),
                    node_type=config_data['node_type'],
                    section_path=config_data['section_path'],
                    enabled=config_data.get('enabled', True),
                    expected_references=config_data.get('expected_references', []),
                    ba_remarks=config_data.get('ba_remarks', ''),
                    created_by=config_data.get('created_by')
                )
                db.add(config)
                created_count += 1
        except Exception as e:
            errors.append(f"Error processing config for {config_data.get('section_path')}: {str(e)}")

    db.commit()

    return {
        "success": len(errors) == 0,
        "updated": updated_count,
        "created": created_count,
        "errors": errors
    }
