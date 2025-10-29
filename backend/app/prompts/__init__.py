"""
Prompt templates for LLM-based extraction.

This module contains all prompt templates used by the LLM extractor
for extracting structured facts from NDC XML documents.
"""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent


def load_prompt(filename: str) -> str:
    """Load a prompt template from file."""
    prompt_path = PROMPTS_DIR / filename
    with open(prompt_path, 'r', encoding='utf-8') as f:
        return f.read()


def get_container_prompt(xml_content: str, section_path: str,
                        element_name: str, child_count: int,
                        repeating_tag: str, max_repetition: int) -> str:
    """Get container extraction prompt with variables filled in."""
    template = load_prompt('container_extraction.txt')
    return template.format(
        section_path=section_path,
        element_name=element_name,
        child_count=child_count,
        repeating_tag=repeating_tag or 'ChildElement',
        max_repetition=max_repetition,
        xml_content=xml_content
    )


def get_item_prompt(xml_content: str, section_path: str) -> str:
    """Get item extraction prompt with variables filled in."""
    template = load_prompt('item_extraction.txt')
    return template.format(
        section_path=section_path,
        xml_content=xml_content
    )


def get_system_prompt() -> str:
    """Get the system prompt for the LLM."""
    return load_prompt('system.txt')


def get_relationship_discovery_prompt(source_type: str, source_xml: str,
                                      target_type: str, target_xml: str) -> str:
    """Get relationship discovery prompt with variables filled in."""
    template = load_prompt('relationship_discovery.txt')
    return template.format(
        source_type=source_type,
        source_xml=source_xml,
        target_type=target_type,
        target_xml=target_xml
    )


def get_relationship_system_prompt() -> str:
    """Get the system prompt for relationship analysis."""
    return load_prompt('relationship_system.txt')


def get_pattern_description_prompt(node_type: str, section_path: str,
                                   must_have_attributes: str, has_children: str,
                                   child_elements: str, references: str) -> str:
    """Get pattern description prompt with variables filled in."""
    template = load_prompt('pattern_description.txt')
    return template.format(
        node_type=node_type,
        section_path=section_path,
        must_have_attributes=must_have_attributes,
        has_children=has_children,
        child_elements=child_elements,
        references=references
    )
