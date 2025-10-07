"""
Identify results endpoints for AssistedDiscovery.

Retrieves pattern matching results and gap analysis from identify runs.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.services.database import get_db_session
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

        # Extract quick explanation from match metadata
        match_metadata = match.match_metadata or {}
        quick_explanation = match_metadata.get('quick_explanation', '')

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


@router.post("/matches/{match_id}/explain")
async def generate_detailed_explanation(
    match_id: int,
    db: Session = Depends(get_db_session)
):
    """
    Generate detailed LLM-powered explanation for a pattern match.

    Uses caching - only generates once, then stores in match_metadata.
    """
    logger.info(f"Generating detailed explanation for match: {match_id}")

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
            is_mismatch = match.confidence < 0.95

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

                # Get a small XML snippet from the actual data for illustration
                xml_snippet = node_structure.get('snippet', '')
                if xml_snippet and len(xml_snippet) > 500:
                    xml_snippet = xml_snippet[:500] + '...'

                prompt = f"""You are a validator for airline {pattern.airline_code or 'N/A'} data.

**Element**: {actual_type}
**Confidence**: {match.confidence * 100:.0f}%
{relationship_glossary if relationship_glossary else ""}

**Specific Differences Found**:
{f"• Missing required fields: {', '.join(missing_attrs)}" if missing_attrs else ""}
{f"• Extra unexpected fields: {', '.join(extra_attrs)}" if extra_attrs else ""}
{f"• Expected child elements: {', '.join(expected_child_types)} but found: {', '.join(actual_child_types)}" if expected_child_types != actual_child_types else ""}
{relationship_details if relationship_details else ""}

**Current XML structure**:
```xml
{xml_snippet}
```

Using the specific differences listed above, provide a clear explanation:

1. Explain what the missing relationship/fields mean using the glossary
2. State the specific difference (expected vs found). If "child_references" is missing, list the SPECIFIC expected fields shown above
3. IMPORTANT:
   - Use ONLY the actual XML structure shown above
   - If the expected fields are reference fields (like "infant", "contact_info"), explain these are OPTIONAL reference fields that were in the training data but may not be required
   - Do NOT invent fake XML elements like <ParentReference>
   - Only suggest adding elements if they are standard NDC elements that are actually missing

Keep it concise - 3-5 sentences maximum.
IMPORTANT: For "child_references", note that this often indicates the pattern was trained on XML with optional references. The current XML may be valid even without them.
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
