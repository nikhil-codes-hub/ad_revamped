"""
Utility functions for handling pattern variations.

Supports both legacy single-pattern format and new variations format.
"""

from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


def is_variations_format(decision_rule: Dict[str, Any]) -> bool:
    """
    Check if a decision_rule uses the new variations format.

    Args:
        decision_rule: Pattern decision rule dict

    Returns:
        True if using variations format, False if legacy format
    """
    return 'variations' in decision_rule


def get_variations(decision_rule: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Get all variations from a decision_rule (handles both formats).

    Args:
        decision_rule: Pattern decision rule dict

    Returns:
        List of variation dicts
    """
    if is_variations_format(decision_rule):
        return decision_rule.get('variations', [])
    else:
        # Legacy format: treat entire rule as single variation
        return [decision_rule]


def get_variation_count(decision_rule: Dict[str, Any]) -> int:
    """Get the number of variations in a pattern."""
    return len(get_variations(decision_rule))


def add_variation(decision_rule: Dict[str, Any], new_variation: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add a new variation to a pattern's decision_rule.

    Args:
        decision_rule: Existing pattern decision rule
        new_variation: New variation to add

    Returns:
        Updated decision_rule with new variation added
    """
    # Get node_type from existing rule or new variation
    node_type = decision_rule.get('node_type') or new_variation.get('node_type')

    if is_variations_format(decision_rule):
        # Already in variations format, just append
        variations = decision_rule['variations'].copy()

        # Assign variation_id
        max_id = max((v.get('variation_id', 0) for v in variations), default=0)
        new_variation['variation_id'] = max_id + 1

        variations.append(new_variation)

        return {
            'node_type': node_type,
            'variations': variations
        }
    else:
        # Convert from legacy format to variations format
        # Existing rule becomes variation 1
        variation_1 = decision_rule.copy()
        variation_1['variation_id'] = 1

        # New variation becomes variation 2
        variation_2 = new_variation.copy()
        variation_2['variation_id'] = 2

        return {
            'node_type': node_type,
            'variations': [variation_1, variation_2]
        }


def create_variation_from_node(node_structure: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a variation dict from a node structure.

    Args:
        node_structure: Node structure from NodeFact

    Returns:
        Variation dict suitable for adding to decision_rule
    """
    # Extract attributes, filtering out metadata
    METADATA_FIELDS = {'summary', 'child_count', 'confidence', 'node_ordinal', 'missing_elements'}
    all_attrs = set(node_structure.get('attributes', {}).keys())
    attributes = sorted(list(all_attrs - METADATA_FIELDS))

    # Build variation
    variation = {
        'node_type': node_structure.get('node_type'),
        'must_have_attributes': attributes,
        'optional_attributes': []
    }

    # Handle children if present
    children = node_structure.get('children', [])
    if children:
        # Normalize children
        if isinstance(children, str):
            import json
            try:
                children = json.loads(children)
            except:
                children = []
        elif isinstance(children, dict):
            children = [children]

        if children:
            # Build child structures
            child_structures = []
            child_types = set()

            for child in children:
                if not isinstance(child, dict):
                    continue

                child_type = child.get('node_type', 'Unknown')
                child_types.add(child_type)

                child_attrs = child.get('attributes', {})
                child_attrs_filtered = {k: v for k, v in child_attrs.items() if k not in METADATA_FIELDS}

                child_structures.append({
                    'node_type': child_type,
                    'required_attributes': sorted(list(child_attrs_filtered.keys())),
                    'reference_fields': []  # Can be populated by LLM later
                })

            variation['child_structure'] = {
                'has_children': True,
                'is_container': True,
                'child_types': sorted(list(child_types)),
                'child_structures': child_structures
            }

    return variation


def generate_variation_descriptions(variations: List[Dict[str, Any]], node_type: str, section_path: str, llm_client=None) -> List[Dict[str, Any]]:
    """
    Generate business-friendly descriptions for each variation using LLM.

    Args:
        variations: List of variation dicts
        node_type: The node type these variations belong to
        section_path: The XML path for context
        llm_client: Optional LLM client (if None, descriptions won't be generated)

    Returns:
        List of variations with 'description' field added
    """
    if not llm_client or len(variations) <= 1:
        # No need for descriptions if only one variation
        return variations

    try:
        # Build comparison prompt with detailed child structure information
        variation_summaries = []
        for idx, var in enumerate(variations, 1):
            var_id = var.get('variation_id', idx)
            attrs = var.get('must_have_attributes', [])
            has_children = var.get('child_structure', {}).get('has_children', False)
            child_structures = var.get('child_structure', {}).get('child_structures', [])

            summary = f"Variation {var_id}:\n"
            summary += f"  - Parent Attributes: {', '.join(attrs) if attrs else 'None'}\n"

            if has_children and child_structures:
                # Group children by type and collect all unique attributes
                child_attrs_by_type = {}
                for child_struct in child_structures:
                    child_type = child_struct.get('node_type', 'Unknown')
                    child_attrs = child_struct.get('required_attributes', [])
                    if child_type not in child_attrs_by_type:
                        child_attrs_by_type[child_type] = set()
                    child_attrs_by_type[child_type].update(child_attrs)

                summary += f"  - Children:\n"
                for child_type, child_attrs in child_attrs_by_type.items():
                    summary += f"    • {child_type}: {', '.join(sorted(child_attrs))}\n"
            elif has_children:
                summary += f"  - Has children but no specific structure defined\n"
            else:
                summary += f"  - No children\n"

            variation_summaries.append(summary)

        prompt = f"""You are analyzing different variations of the same XML node type in airline passenger booking data.

Node Type: {node_type}
XML Path: {section_path}

We have discovered {len(variations)} different structural variations for this node. Each variation represents a different way this node appears in real XML files, based on different business scenarios or data requirements.

Here are the variations with their detailed structure:

{chr(10).join(variation_summaries)}

IMPORTANT: Look carefully at the DIFFERENCES in attributes and child structures between the variations.

For EACH variation, write a clear, specific 1-2 sentence description that:
1. Explains what is UNIQUE or DIFFERENT about this variation (e.g., "includes passport information", "has infant-parent connections", "contains loyalty program data")
2. States the business scenario where this structure would appear (e.g., "international flights requiring passport data", "family bookings with infants", "frequent flyer enrollments")

DO NOT write vague descriptions like "straightforward manner" or "slightly different context".
DO write specific descriptions that reference the actual data fields present.

Example good descriptions:
- "This variation includes passport information (passport_info field), used for international flights where travel document details must be captured."
- "This variation contains loyalty program membership data (frequent_flyer_number), appearing when passengers link their airline rewards accounts to bookings."

Respond in JSON format:
{{
  "variation_descriptions": [
    {{"variation_id": 1, "description": "..."}},
    {{"variation_id": 2, "description": "..."}}
  ]
}}"""

        logger.info(f"Sending variation description prompt to LLM:\n{prompt}")

        # Wrap async call - run in a separate thread to avoid event loop conflicts
        import asyncio
        import concurrent.futures

        async def _async_generate():
            response = await llm_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            return response.choices[0].message.content

        def _run_in_thread():
            """Run async function in a new thread with its own event loop."""
            return asyncio.run(_async_generate())

        # Run in a thread pool to avoid event loop conflicts
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(_run_in_thread)
            result_json = future.result(timeout=30)  # 30 second timeout

        import json
        result = json.loads(result_json)
        descriptions_map = {
            item['variation_id']: item['description']
            for item in result.get('variation_descriptions', [])
        }

        # Add descriptions to variations
        for var in variations:
            var_id = var.get('variation_id', 0)
            if var_id in descriptions_map:
                var['description'] = descriptions_map[var_id]
                logger.info(f"Generated description for variation {var_id}: {var['description']}")

    except Exception as e:
        logger.warning(f"Failed to generate variation descriptions: {e}")
        # Continue without descriptions

    return variations


def match_node_to_variation(node_structure: Dict[str, Any], variation: Dict[str, Any]) -> tuple[bool, float, Dict[str, Any]]:
    """
    Check if a node matches a specific variation.

    Args:
        node_structure: Node structure from NodeFact
        variation: Variation dict from pattern

    Returns:
        Tuple of (matches, confidence, details)
        - matches: True if node satisfies this variation
        - confidence: 0.0-1.0 match confidence
        - details: Dict with match details
    """
    METADATA_FIELDS = {'summary', 'child_count', 'confidence', 'node_ordinal', 'missing_elements'}

    # Check node type
    if node_structure.get('node_type') != variation.get('node_type'):
        return False, 0.0, {'reason': 'node_type_mismatch'}

    # Check attributes
    node_attrs = set(node_structure.get('attributes', {}).keys()) - METADATA_FIELDS
    required_attrs = set(variation.get('must_have_attributes', []))
    optional_attrs = set(variation.get('optional_attributes', []))

    missing_required = required_attrs - node_attrs
    extra_attrs = node_attrs - required_attrs - optional_attrs

    # Parent-level match
    if missing_required:
        confidence = 1.0 - (len(missing_required) / len(required_attrs)) if required_attrs else 0.0
        return False, confidence, {
            'reason': 'missing_required_attributes',
            'missing': list(missing_required)
        }

    # Check child structures
    node_children = node_structure.get('children', [])
    variation_child_structure = variation.get('child_structure', {})

    if variation_child_structure.get('has_children'):
        expected_child_structures = variation_child_structure.get('child_structures', [])

        if not node_children:
            return False, 0.5, {'reason': 'missing_children'}

        # Normalize children
        if isinstance(node_children, str):
            import json
            try:
                node_children = json.loads(node_children)
            except:
                node_children = []
        elif isinstance(node_children, dict):
            node_children = [node_children]

        # Check if children match expected structures
        # For each expected child structure, check if at least one actual child matches
        child_match_score = 0
        total_child_checks = 0

        for expected_child_struct in expected_child_structures:
            expected_child_type = expected_child_struct.get('node_type')
            expected_child_attrs = set(expected_child_struct.get('required_attributes', []))

            # Find children of this type
            matching_children = [c for c in node_children if isinstance(c, dict) and c.get('node_type') == expected_child_type]

            if not matching_children:
                total_child_checks += 1
                continue

            # Check if any child of this type has all required attributes
            for child in matching_children:
                total_child_checks += 1
                child_attrs = set(child.get('attributes', {}).keys()) - METADATA_FIELDS
                missing_child_attrs = expected_child_attrs - child_attrs

                if not missing_child_attrs:
                    child_match_score += 1
                else:
                    # Partial match
                    child_match_score += 1.0 - (len(missing_child_attrs) / len(expected_child_attrs)) if expected_child_attrs else 0

        # Calculate overall confidence
        if total_child_checks > 0:
            child_confidence = child_match_score / total_child_checks
        else:
            child_confidence = 1.0

        # Overall confidence is average of parent and child confidence
        overall_confidence = (1.0 + child_confidence) / 2.0

        if child_confidence < 1.0:
            return False, overall_confidence, {
                'reason': 'child_attribute_mismatch',
                'child_confidence': child_confidence
            }

    # Perfect match
    return True, 1.0, {'reason': 'exact_match'}
