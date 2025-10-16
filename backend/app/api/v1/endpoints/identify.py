"""
Identify results endpoints for AssistedDiscovery.

Retrieves pattern matching results and gap analysis from identify runs.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from app.services.workspace_db import workspace_session
from app.models.database import Run, PatternMatch, NodeFact, Pattern, RunKind
from app.services.llm_extractor import get_llm_extractor
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
    workspace: str = Query("default", description="Workspace name")
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

    with workspace_session(workspace) as db:
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

            # Extract quick explanation from match metadata
            match_metadata = match.match_metadata or {}
            quick_explanation = match_metadata.get('quick_explanation', '')
            quality_checks = match_metadata.get('quality_checks', {})
            quality_status = str(quality_checks.get('status', 'ok')).lower() if isinstance(quality_checks, dict) else 'ok'
            match_percentage = None
            if isinstance(quality_checks, dict):
                match_percentage = quality_checks.get('match_percentage')

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
                    "airline_code": pattern.airline_code if pattern else None,
                    "decision_rule": pattern.decision_rule if pattern else {},
                    "times_seen": pattern.times_seen if pattern else 0
                } if pattern else None,
                "confidence": match.confidence,
                "verdict": match.verdict,
                "quick_explanation": quick_explanation,
                "quality_checks": quality_checks,
                "quality_status": quality_status,
                "match_percentage": match_percentage,
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
    workspace: str = Query("default", description="Workspace name")
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

    with workspace_session(workspace) as db:
        # Verify run exists
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        if run.kind != RunKind.IDENTIFY:
            raise HTTPException(status_code=400, detail="Run is not an identify run")

        # Get all matches for this run
        all_matches = db.query(PatternMatch).filter(PatternMatch.run_id == run_id).all()

        total_facts = len(all_matches)
        node_facts = {
            nf.id: nf
            for nf in db.query(NodeFact).filter(NodeFact.run_id == run_id).all()
        }

        # Calculate statistics
        matched_count = 0
        high_confidence_count = 0
        new_patterns_count = 0
        quality_breaks = 0
        quality_coverage_total = 0.0
        quality_alerts = []

        verdict_breakdown = {
            "EXACT_MATCH": 0,
            "HIGH_MATCH": 0,
            "PARTIAL_MATCH": 0,
            "LOW_MATCH": 0,
            "NO_MATCH": 0,
            "NEW_PATTERN": 0,
            "QUALITY_BREAK": 0
        }

        for match in all_matches:
            if match.verdict:
                verdict_breakdown[match.verdict] = verdict_breakdown.get(match.verdict, 0) + 1

            confidence_value = float(match.confidence) if match.confidence is not None else 0.0
            if confidence_value >= 0.70 and match.verdict not in {"NEW_PATTERN", "QUALITY_BREAK"}:
                matched_count += 1
            if confidence_value >= 0.85 and match.verdict not in {"NEW_PATTERN", "QUALITY_BREAK"}:
                high_confidence_count += 1
            if match.verdict == "NEW_PATTERN":
                new_patterns_count += 1
            if match.verdict == "QUALITY_BREAK":
                quality_breaks += 1

            match_metadata = match.match_metadata or {}
            quality_checks = match_metadata.get('quality_checks', {})
            if isinstance(quality_checks, dict):
                status = str(quality_checks.get('status', 'ok')).lower()
                match_percentage = quality_checks.get('match_percentage')
                try:
                    match_percentage_value = float(match_percentage)
                except (TypeError, ValueError):
                    match_percentage_value = 0.0 if status == 'error' else 100.0
                quality_coverage_total += match_percentage_value

                if status == 'error':
                    node_fact = node_facts.get(match.node_fact_id)
                    quality_alerts.append({
                        "node_fact_id": match.node_fact_id,
                        "node_type": node_fact.node_type if node_fact else None,
                        "section_path": node_fact.section_path if node_fact else None,
                        "match_percentage": match_percentage_value,
                        "quality_checks": quality_checks
                    })
            else:
                quality_coverage_total += 100.0

        confidence_match_rate = (matched_count / total_facts * 100) if total_facts > 0 else 0
        quality_match_rate = (quality_coverage_total / total_facts) if total_facts > 0 else 0
        coverage_trigger = quality_breaks > 0 or len(quality_alerts) > 0
        match_rate = quality_match_rate if coverage_trigger else confidence_match_rate
        high_confidence_rate = (high_confidence_count / total_facts * 100) if total_facts > 0 else 0

        return {
            "run_id": run_id,
            "spec_version": run.spec_version,
            "message_root": run.message_root,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "duration_seconds": run.duration_seconds,
            "statistics": {
                "total_node_facts": total_facts,
                "matched_facts": matched_count,
                "high_confidence_matches": high_confidence_count,
                "new_patterns": new_patterns_count,
                "unmatched_facts": total_facts - matched_count,
                "match_rate": round(match_rate, 2),
                "confidence_match_rate": round(confidence_match_rate, 2),
                "quality_match_rate": round(quality_match_rate, 2),
                "quality_breaks": quality_breaks,
                "high_confidence_rate": round(high_confidence_rate, 2)
            },
            "verdict_breakdown": verdict_breakdown,
            "quality_alerts": quality_alerts,
            "generated_at": run.finished_at.isoformat() if run.finished_at else None
        }


@router.get("/{run_id}/new-patterns")
async def get_new_patterns(
    run_id: str,
    workspace: str = Query("default", description="Workspace name")
):
    """
    Get list of new patterns discovered in an identify run.

    Returns NodeFacts that didn't match any existing patterns.
    """
    logger.info(f"Getting new patterns for run: {run_id}")

    with workspace_session(workspace) as db:
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


@router.post("/matches/{match_id}/explain")
async def generate_detailed_explanation(
    match_id: int,
    workspace: str = Query("default", description="Workspace name")
):
    """
    Generate detailed LLM-powered explanation for a pattern match.

    Uses caching - only generates once, then stores in match_metadata.
    """
    logger.info(f"Generating detailed explanation for match: {match_id}")

    with workspace_session(workspace) as db:
        # Get the pattern match
        match = db.query(PatternMatch).filter(PatternMatch.id == match_id).first()
        if not match:
            raise HTTPException(status_code=404, detail="Pattern match not found")

        # Check if explanation already exists (cache)
        match_metadata = match.match_metadata or {}
        if 'detailed_explanation' in match_metadata:
            logger.info(f"Using cached explanation for match {match_id}")
            return {
                "match_id": match_id,
                "detailed_explanation": match_metadata['detailed_explanation'],
                "cached": True
            }

        # Get associated NodeFact and Pattern
        node_fact = db.query(NodeFact).filter(NodeFact.id == match.node_fact_id).first()
        if not node_fact:
            raise HTTPException(status_code=404, detail="NodeFact not found")

        pattern = None
        if match.pattern_id:
            pattern = db.query(Pattern).filter(Pattern.id == match.pattern_id).first()

        # Generate detailed explanation using LLM
        try:
            llm = get_llm_extractor()

            # Build context for LLM
            node_structure = node_fact.fact_json
            pattern_rule = pattern.decision_rule if pattern else None

            # Defensive check: ensure JSON fields are dicts, not strings
            if isinstance(node_structure, str):
                logger.error(f"node_structure is a string, not a dict: {node_structure[:100]}")
                import json
                node_structure = json.loads(node_structure)

            if isinstance(pattern_rule, str):
                logger.error(f"pattern_rule is a string, not a dict: {pattern_rule[:100]}")
                import json
                pattern_rule = json.loads(pattern_rule)

            if pattern:
                # Determine if this is a mismatch
                is_mismatch = float(match.confidence or 0) < 0.95

                if is_mismatch:
                    # Extract business-relevant differences only
                    expected_type = pattern_rule.get('node_type', 'Unknown')
                    actual_type = node_structure.get('node_type', 'Unknown')

                    expected_attrs = set(pattern_rule.get('must_have_attributes', []))

                    # Filter out metadata fields added during extraction (not real XML attributes)
                    METADATA_FIELDS = {'summary', 'child_count', 'confidence', 'node_ordinal'}
                    all_actual_attrs = set(node_structure.get('attributes', {}).keys())
                    actual_attrs = all_actual_attrs - METADATA_FIELDS

                    missing_attrs = expected_attrs - actual_attrs
                    extra_attrs = actual_attrs - expected_attrs - set(pattern_rule.get('optional_attributes', []))

                    expected_children = pattern_rule.get('child_structure', {})
                    actual_children = node_structure.get('children', [])

                    # Normalize children entries to dict structures before comparison
                    if isinstance(actual_children, str):
                        try:
                            import json
                            actual_children = json.loads(actual_children)
                        except json.JSONDecodeError:
                            actual_children = []
                    elif isinstance(actual_children, dict):
                        actual_children = [actual_children]

                    normalized_children = []
                    for child in actual_children or []:
                        if isinstance(child, str):
                            try:
                                import json
                                child = json.loads(child)
                            except json.JSONDecodeError:
                                child = None
                        if isinstance(child, dict):
                            normalized_children.append(child)
                    actual_children = normalized_children

                    expected_child_types = set(expected_children.get('child_types', []))
                    actual_child_types = set(child.get('node_type', '') for child in actual_children) if actual_children else set()
                    missing_child_types = expected_child_types - actual_child_types
                    extra_child_types = actual_child_types - expected_child_types

                    # Get reference patterns with details
                    expected_refs = pattern_rule.get('reference_patterns', [])
                    actual_refs = node_structure.get('relationships', [])

                    # Extract relationship types for comparison
                    expected_ref_types = set(ref.get('type', '') for ref in expected_refs)
                    actual_ref_types = set(ref.get('type', '') for ref in actual_refs)
                    missing_ref_types = expected_ref_types - actual_ref_types
                    extra_ref_types = actual_ref_types - expected_ref_types

                    # For child_references, extract the specific fields
                    expected_fields_detail = ""
                    for ref in expected_refs:
                        if ref.get('type') == 'child_references' and 'fields' in ref:
                            expected_fields_detail = f"\n  Expected reference fields in child elements: {', '.join(ref['fields'])}"

                    # Build detailed relationship info
                    relationship_details = ""
                    relationship_glossary = ""
                    if missing_ref_types or extra_ref_types or (expected_ref_types and not actual_ref_types):
                        # Build glossary for relationship types
                        unique_refs = expected_ref_types | actual_ref_types
                        if unique_refs:
                            relationship_glossary = "\n**What these relationships mean**:\n"
                            ref_meanings = {
                                'infant_parent': 'Links infant passengers to their accompanying adult guardian',
                                'segment_reference': 'Links passenger journeys to specific flight segments',
                                'pax_reference': 'Links data elements (baggage, services) to specific passengers',
                                'baggage_reference': 'Links baggage items to passenger records',
                                'journey_reference': 'Links segments to passenger journey records',
                                'service_reference': 'Links ancillary services to passengers or segments',
                                'child_references': 'Reference fields expected within child elements (e.g., InfantRef, ContactRef within each PaxSegment). NOTE: This may indicate the pattern was trained on XML with optional references that your XML doesn\'t have.'
                            }
                            for ref_type in unique_refs:
                                if ref_type in ref_meanings:
                                    relationship_glossary += f"• {ref_type}: {ref_meanings[ref_type]}\n"
                                else:
                                    relationship_glossary += f"• {ref_type}: Links related data elements\n"

                        relationship_details = f"\n**Relationship/Reference Differences**:\n"
                        if expected_ref_types:
                            relationship_details += f"• Expected: {', '.join(expected_ref_types)}{expected_fields_detail}\n"
                        if actual_ref_types:
                            relationship_details += f"• Found: {', '.join(actual_ref_types)}\n"
                        else:
                            relationship_details += f"• Found: None\n"
                        if missing_ref_types:
                            relationship_details += f"• Missing: {', '.join(missing_ref_types)}\n"

                    # Get quality check details with specific instance information
                    quality_checks = match_metadata.get('quality_checks', {})
                    missing_elements = quality_checks.get('missing_elements', [])
                    match_percentage = quality_checks.get('match_percentage', 100.0)

                    # Build detailed missing elements summary
                    missing_details = ""
                    if missing_elements:
                        missing_details = "\n**Specific Missing Elements (Instance-by-Instance)**:\n"
                        for item in missing_elements[:10]:  # Show up to 10 instances
                            if isinstance(item, dict):
                                path = item.get('path', 'unknown')
                                reason = item.get('reason', 'unspecified')
                                missing_details += f"• {path}: {reason}\n"

                    # Get a small XML snippet from the actual data for illustration
                    xml_snippet = node_structure.get('snippet', '')
                    if xml_snippet and len(xml_snippet) > 500:
                        xml_snippet = xml_snippet[:500] + '...'

                    prompt = f"""You are a data quality validator for airline {pattern.airline_code or 'N/A'}.

**Element Being Validated**: {actual_type}
**Quality Coverage**: {match_percentage:.1f}% (Based on actual data inspection)
**Pattern Confidence**: {float(match.confidence or 0) * 100:.0f}%
{relationship_glossary if relationship_glossary else ""}

**Quality Issues Detected**:
{f"• Missing required attributes: {', '.join(missing_attrs)}" if missing_attrs else ""}
{f"• Unexpected extra attributes: {', '.join(extra_attrs)}" if extra_attrs else ""}
{f"• Child element mismatch - Expected: {', '.join(expected_child_types)} | Found: {', '.join(actual_child_types)}" if expected_child_types != actual_child_types else ""}
{relationship_details if relationship_details else ""}
{missing_details if missing_details else ""}

**Current XML Sample**:
```xml
{xml_snippet}
```

Provide a CLEAR, ACTIONABLE explanation in 3-4 sentences using the format below:

**The Problem**: State EXACTLY what is wrong using the specific instance information above. Be precise - if "PaxList[1]/Pax[1]/PTC" is missing, say "Passenger #1 in the PaxList is missing the required PTC (Passenger Type Code) field." Calculate the percentage from the number of missing instances shown above.

**Impact**: Explain why this specific missing data matters for airline operations or data processing. Be concrete - for PTC, mention how ADT (adult), CHD (child), INF (infant) classification is needed for pricing, boarding, and regulatory compliance.

**Action**: Give a direct recommendation. If required data is missing, say "Fix the source system to ensure all passengers include PTC." If it's optional reference data, say "This reference field is optional and the XML remains valid."

Be DIRECT and SPECIFIC. Use exact numbers and instance paths from the data above. Do NOT use vague phrases like "typically", "may not be required", or "some instances". Format with bold headings as shown above.
"""
                else:
                    # Perfect match - keep it simple
                    prompt = f"""You are a validator checking airline data.

**Data Element**: {node_structure.get('node_type', 'Unknown')} for airline {pattern.airline_code or 'N/A'}

This matches perfectly. Write 1 sentence: "This [what it represents] matches the expected format. No action needed."
"""
            else:
                # New pattern case
                prompt = f"""You are a validator checking airline data.

**New Data Element**: {node_structure.get('node_type', 'Unknown')}

This data structure has NEVER been seen before in our pattern library.

Explain in 2-3 sentences:
1. What this likely represents based on the element name
2. Why it might have appeared (e.g., new airline-specific extension, API version change, new NDC feature)

Be factual and concise. Format as a paragraph, NOT bullet points.
"""

            # Call LLM (async)
            detailed_explanation = await llm.generate_explanation_async(prompt)

            # Store in match_metadata (cache for future requests)
            match_metadata['detailed_explanation'] = detailed_explanation
            match.match_metadata = match_metadata
            db.add(match)
            db.commit()

            logger.info(f"Generated and cached explanation for match {match_id}")

            return {
                "match_id": match_id,
                "detailed_explanation": detailed_explanation,
                "cached": False
            }

        except Exception as e:
            import traceback
            logger.error(f"Error generating explanation: {str(e)}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Failed to generate explanation: {str(e)}")
