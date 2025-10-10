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
from app.services.workspace_db import get_workspace_db
from app.services.pattern_generator import create_pattern_generator
from app.models.database import Pattern
import httpx

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
                description=p.description,
                signature_hash=p.signature_hash,
                times_seen=p.times_seen,
                created_by_model=p.created_by_model,
                examples=p.examples or [],
                created_at=p.created_at.isoformat() if p.created_at else None,
                last_seen_at=p.last_seen_at.isoformat() if p.last_seen_at else None
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
                "node_facts_analyzed": results.get('node_facts_analyzed', 0),
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


@router.post("/{pattern_id}/modify")
async def modify_pattern(
    pattern_id: int,
    payload: dict,
    workspace: str = Query("default", description="Workspace name")
):
    """
    Modify a pattern using LLM based on additional requirements.

    Takes current pattern description, decision rule, and additional requirements,
    then uses LLM to generate updated description and decision rule.

    - **pattern_id**: Pattern ID to modify
    - **payload**: Contains current_description, current_decision_rule, additional_requirements, section_path, spec_version, message_root
    """
    from app.services.llm_extractor import get_llm_extractor
    from app.core.config import settings
    from openai import AzureOpenAI, OpenAI
    from datetime import datetime
    import json

    logger.info("Modifying pattern with LLM", pattern_id=pattern_id, workspace=workspace)

    db_generator = get_workspace_db(workspace)
    db = next(db_generator)

    try:
        # Get the pattern from database
        pattern = db.query(Pattern).filter(Pattern.id == pattern_id).first()

        if not pattern:
            raise HTTPException(status_code=404, detail=f"Pattern {pattern_id} not found")

        # Extract payload data
        current_description = payload.get('current_description', '')
        current_decision_rule = payload.get('current_decision_rule', {})
        additional_requirements = payload.get('additional_requirements', '')
        section_path = payload.get('section_path', '')
        spec_version = payload.get('spec_version', '')
        message_root = payload.get('message_root', '')

        # Get LLM client
        llm_extractor = get_llm_extractor()
        sync_client = None
        model_name = settings.LLM_MODEL

        if settings.LLM_PROVIDER == "azure" and settings.AZURE_OPENAI_KEY:
            http_client = httpx.Client(
                    timeout=httpx.Timeout(60.0, connect=10.0),
                    limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
                    follow_redirects=True,
                    verify=False  # Disable SSL verification for corporate proxies
            )
            sync_client = AzureOpenAI(
                api_key=settings.AZURE_OPENAI_KEY,
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                api_version=settings.AZURE_API_VERSION,
                http_client=http_client
            )
            model_name = settings.MODEL_DEPLOYMENT_NAME
        elif settings.OPENAI_API_KEY:
            sync_client = OpenAI(api_key=settings.OPENAI_API_KEY)
            model_name = settings.LLM_MODEL
        elif llm_extractor.client:
            sync_client = llm_extractor.client

        if not sync_client:
            raise HTTPException(status_code=503, detail="LLM client not available")

        # Prepare LLM prompt
        node_type = current_decision_rule.get('node_type', 'Unknown')
        must_have_attrs = current_decision_rule.get('must_have_attributes', [])
        optional_attrs = current_decision_rule.get('optional_attributes', [])
        child_structure = current_decision_rule.get('child_structure', {})
        reference_patterns = current_decision_rule.get('reference_patterns', [])

        prompt = f"""You are an NDC XML pattern expert. You need to modify a pattern definition based on additional business requirements.

**Current Pattern:**
- Location: {section_path}
- Node Type: {node_type}
- Version: {spec_version} / {message_root}
- Current Description: {current_description or 'Not provided'}

**Current Decision Rule:**
```json
{json.dumps(current_decision_rule, indent=2)}
```

**Additional Requirements from User:**
{additional_requirements}

**Your Task:**
1. Update the business description to reflect the additional requirements in simple, non-technical language
2. Modify the decision rule to incorporate the new requirements:
   - Add new required attributes if needed
   - Update optional attributes
   - Modify child structure if needed
   - Add or update reference patterns
   - Update business intelligence schema if applicable

**Important Guidelines:**
- Keep the node_type unchanged unless explicitly requested
- Maintain backward compatibility when possible
- Use clear, business-friendly language in the description
- Ensure the decision rule is technically accurate for XML pattern matching

**Output Format (JSON only, no additional text):**
```json
{{
  "new_description": "Updated 1-2 sentence business description",
  "new_decision_rule": {{
    "node_type": "{node_type}",
    "must_have_attributes": ["attr1", "attr2"],
    "optional_attributes": ["opt1"],
    "child_structure": {{}},
    "reference_patterns": [],
    "business_intelligence_schema": {{}}
  }},
  "modification_summary": "Brief summary of what was changed"
}}
```"""

        # Call LLM
        if hasattr(sync_client, "chat"):
            response = sync_client.chat.completions.create(
                model=model_name,
                max_tokens=2000,
                temperature=0.3,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            result_text = response.choices[0].message.content.strip()
        else:
            import asyncio

            async def _async_call():
                resp = await sync_client.chat.completions.create(
                    model=model_name,
                    max_tokens=2000,
                    temperature=0.3,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )
                return resp.choices[0].message.content.strip()

            result_text = asyncio.run(_async_call())

        # Parse LLM response (extract JSON from markdown code blocks if present)
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()

        result = json.loads(result_text)

        new_description = result.get('new_description', current_description)
        new_decision_rule = result.get('new_decision_rule', current_decision_rule)
        modification_summary = result.get('modification_summary', 'Pattern modified via LLM')

        # Update pattern in database
        pattern.description = new_description
        pattern.decision_rule = new_decision_rule
        pattern.last_seen_at = datetime.utcnow()

        # Add modification history to metadata (if examples field can be repurposed)
        # Or we could add a modification_log field to the pattern
        db.commit()

        logger.info(f"Pattern {pattern_id} modified successfully", modification_summary=modification_summary)

        return {
            "success": True,
            "pattern_id": pattern_id,
            "new_description": new_description,
            "new_decision_rule": new_decision_rule,
            "modification_summary": modification_summary,
            "updated_at": datetime.utcnow().isoformat()
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to parse LLM response: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to modify pattern: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to modify pattern: {str(e)}")
    finally:
        try:
            next(db_generator)
        except StopIteration:
            pass
