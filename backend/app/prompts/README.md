# LLM Extraction Prompts

This directory contains all prompt templates used by the LLM extractor for extracting structured facts from NDC XML documents.

## Prompt Files

### `system.txt`
System-level prompt that defines the LLM's role and behavior. Used in all extraction requests.

### `container_extraction.txt`
Prompt template for extracting container/collection elements (e.g., `BaggageAllowanceList`, `ContactInfoList`).

**When used:** When the XML structure analysis detects:
- Repeating child elements (max_repetition > 1)
- Element name ends with "List"
- Element name is plural and all children have same tag

**Output format:** One container fact with nested children array.

### `item_extraction.txt`
Prompt template for extracting individual item elements (e.g., single `Order`, `Passenger`).

**When used:** When the element is not detected as a container.

**Output format:** One or more individual facts.

## Variables

### Container Prompt Variables:
- `{section_path}` - Full XPath to the element
- `{element_name}` - Name of the container element
- `{child_count}` - Total number of children
- `{repeating_tag}` - Name of the repeating child element
- `{max_repetition}` - Count of most common child element
- `{xml_content}` - The XML content to extract from

### Item Prompt Variables:
- `{section_path}` - Full XPath to the element
- `{xml_content}` - The XML content to extract from

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
