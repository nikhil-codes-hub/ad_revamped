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
