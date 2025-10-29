# LLM Prompts

This directory contains all prompt templates used by the AssistedDiscovery system for LLM-based operations including extraction, relationship discovery, and pattern description.

## Extraction Prompts

### `system.txt`
System-level prompt that defines the LLM's role and behavior. Used in all extraction requests.

**Used by:** `llm_extractor.py`

### `container_extraction.txt`
Prompt template for extracting container/collection elements (e.g., `BaggageAllowanceList`, `ContactInfoList`).

**When used:** When the XML structure analysis detects:
- Repeating child elements (max_repetition > 1)
- Element name ends with "List"
- Element name is plural and all children have same tag

**Output format:** One container fact with nested children array.

**Used by:** `llm_extractor.py`

### `item_extraction.txt`
Prompt template for extracting individual item elements (e.g., single `Order`, `Passenger`).

**When used:** When the element is not detected as a container.

**Output format:** One or more individual facts.

**Used by:** `llm_extractor.py`

## Relationship Analysis Prompts

### `relationship_system.txt`
System-level prompt for relationship discovery that defines the LLM's role as an XML relationship analysis expert.

**Used by:** `relationship_analyzer.py`

**Content:** Instructs the LLM to identify reference fields linking XML elements and return consistent JSON responses.

### `relationship_discovery.txt`
Prompt template for discovering relationships between XML nodes by analyzing reference fields.

**When used:** When analyzing if a SOURCE node contains reference fields pointing to a TARGET node.

**Output format:** JSON with structure:
```json
{
  "has_references": boolean,
  "references": [
    {
      "reference_type": "string",
      "reference_field": "string",
      "reference_value": "string",
      "confidence": number
    }
  ],
  "discovery_notes": "string"
}
```

**Used by:** `relationship_analyzer.py`

## Pattern Description Prompts

### `pattern_description.txt`
Prompt template for generating plain English business descriptions of XML patterns.

**When used:** After pattern generation to create human-readable descriptions for business analysts.

**Output format:** 1-2 sentence plain English description focusing on business meaning.

**Used by:** `pattern_generator.py`

## Variables

### Container Prompt Variables
- `{section_path}` - Full XPath to the element
- `{element_name}` - Name of the container element
- `{child_count}` - Total number of children
- `{repeating_tag}` - Name of the repeating child element
- `{max_repetition}` - Count of most common child element
- `{xml_content}` - The XML content to extract from

### Item Prompt Variables
- `{section_path}` - Full XPath to the element
- `{xml_content}` - The XML content to extract from

### Relationship Discovery Variables
- `{source_type}` - Name of the source node type
- `{source_xml}` - XML snippet of the source node
- `{target_type}` - Name of the target node type
- `{target_xml}` - XML snippet of the target node

### Pattern Description Variables
- `{node_type}` - Type of the node
- `{section_path}` - Full XPath to the element
- `{must_have_attributes}` - Comma-separated list of required attributes
- `{has_children}` - "Yes" or "No"
- `{child_elements}` - Comma-separated list of child element types
- `{references}` - Comma-separated list of reference types

## Modifying Prompts

1. Edit the `.txt` files directly
2. Use `{variable_name}` syntax for template variables
3. Changes take effect immediately (no restart needed)
4. Test changes with real XML to ensure proper JSON output

## Structure Detection Logic

The extractor automatically detects whether to use container or item prompt based on:

```python
is_container = (
    max_repetition > 1 or  # Has repeating children
    (element_name.endswith('List') and total_children > 0) or
    (element_name.endswith('s') and max_repetition == total_children)
)
```

This logic is implemented in `llm_extractor.py:_analyze_xml_structure()`.

## Usage

All prompts are loaded via helper functions in `__init__.py`:

```python
from app.prompts import (
    get_system_prompt,
    get_container_prompt,
    get_item_prompt,
    get_relationship_system_prompt,
    get_relationship_discovery_prompt,
    get_pattern_description_prompt
)

# Example: Load relationship discovery prompt
prompt = get_relationship_discovery_prompt(
    source_type="PaxSegment",
    source_xml="<PaxSegment>...</PaxSegment>",
    target_type="Pax",
    target_xml="<Pax>...</Pax>"
)
```

## Benefits of File-Based Prompts

1. **Easy Editing**: Modify prompts without changing code
2. **Version Control**: Track prompt changes in git
3. **Testing**: Quickly test different prompt variations
4. **Collaboration**: Non-developers can improve prompts
5. **Separation of Concerns**: Business logic separate from prompt engineering
