"""
PII masking utilities for AssistedDiscovery.

Masks personally identifiable information in XML content and extracted data
to ensure privacy compliance while preserving structure for pattern learning.
"""

import re
import logging
from typing import Dict, Any, Optional, List, Pattern
from dataclasses import dataclass
from enum import Enum

from app.core.config import settings

logger = logging.getLogger(__name__)


class PiiType(str, Enum):
    """Types of PII that can be detected and masked."""
    EMAIL = "email"
    PHONE = "phone"
    CREDIT_CARD = "credit_card"
    SSN = "ssn"
    PASSPORT = "passport"
    NAME = "name"
    ADDRESS = "address"
    DATE_OF_BIRTH = "date_of_birth"
    IP_ADDRESS = "ip_address"
    URL = "url"


@dataclass
class PiiPattern:
    """Pattern definition for PII detection."""
    pii_type: PiiType
    pattern: Pattern[str]
    mask_template: str
    confidence: float = 1.0
    description: str = ""


@dataclass
class MaskingResult:
    """Result of PII masking operation."""
    original_text: str
    masked_text: str
    pii_found: List[Dict[str, Any]]
    masking_applied: bool

    @property
    def pii_count(self) -> int:
        """Get count of PII instances found."""
        return len(self.pii_found)


class PiiMaskingEngine:
    """Engine for detecting and masking PII in text content."""

    def __init__(self):
        """Initialize PII masking engine with patterns."""
        self.patterns = self._build_pii_patterns()
        self.enabled = settings.PII_MASKING_ENABLED

    def _build_pii_patterns(self) -> List[PiiPattern]:
        """Build comprehensive PII detection patterns."""
        patterns = []

        # Email patterns
        patterns.append(PiiPattern(
            pii_type=PiiType.EMAIL,
            pattern=re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            mask_template="[EMAIL_MASKED]",
            description="Email addresses"
        ))

        # Phone patterns (various formats)
        patterns.append(PiiPattern(
            pii_type=PiiType.PHONE,
            pattern=re.compile(r'(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'),
            mask_template="[PHONE_MASKED]",
            description="Phone numbers (US format)"
        ))

        patterns.append(PiiPattern(
            pii_type=PiiType.PHONE,
            pattern=re.compile(r'\+\d{1,3}[-.\s]?\d{1,14}'),
            mask_template="[PHONE_MASKED]",
            description="International phone numbers"
        ))

        # Credit card patterns
        patterns.append(PiiPattern(
            pii_type=PiiType.CREDIT_CARD,
            pattern=re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
            mask_template="[CARD_MASKED]",
            description="Credit card numbers"
        ))

        # SSN patterns
        patterns.append(PiiPattern(
            pii_type=PiiType.SSN,
            pattern=re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
            mask_template="[SSN_MASKED]",
            description="Social Security Numbers"
        ))

        patterns.append(PiiPattern(
            pii_type=PiiType.SSN,
            pattern=re.compile(r'\b\d{9}\b'),
            mask_template="[SSN_MASKED]",
            confidence=0.7,
            description="9-digit numbers (possible SSN)"
        ))

        # Passport patterns
        patterns.append(PiiPattern(
            pii_type=PiiType.PASSPORT,
            pattern=re.compile(r'\b[A-Z]{2}\d{7}\b'),
            mask_template="[PASSPORT_MASKED]",
            description="Passport numbers (US format)"
        ))

        # Date of birth patterns
        patterns.append(PiiPattern(
            pii_type=PiiType.DATE_OF_BIRTH,
            pattern=re.compile(r'\b\d{1,2}/\d{1,2}/\d{4}\b'),
            mask_template="[DOB_MASKED]",
            confidence=0.8,
            description="Date patterns (MM/DD/YYYY)"
        ))

        patterns.append(PiiPattern(
            pii_type=PiiType.DATE_OF_BIRTH,
            pattern=re.compile(r'\b\d{4}-\d{2}-\d{2}\b'),
            mask_template="[DOB_MASKED]",
            confidence=0.8,
            description="Date patterns (YYYY-MM-DD)"
        ))

        # IP Address patterns
        patterns.append(PiiPattern(
            pii_type=PiiType.IP_ADDRESS,
            pattern=re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
            mask_template="[IP_MASKED]",
            description="IPv4 addresses"
        ))

        # URL patterns
        patterns.append(PiiPattern(
            pii_type=PiiType.URL,
            pattern=re.compile(r'https?://[^\s<>"\']+'),
            mask_template="[URL_MASKED]",
            description="HTTP/HTTPS URLs"
        ))

        # Name patterns (common titles + capitalized words)
        patterns.append(PiiPattern(
            pii_type=PiiType.NAME,
            pattern=re.compile(r'\b(?:Mr|Mrs|Ms|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'),
            mask_template="[NAME_MASKED]",
            confidence=0.9,
            description="Names with titles"
        ))

        logger.info(f"Built {len(patterns)} PII detection patterns")
        return patterns

    def _detect_pii_in_text(self, text: str) -> List[Dict[str, Any]]:
        """Detect PII instances in text."""
        if not text or not self.enabled:
            return []

        pii_instances = []

        for pattern_def in self.patterns:
            matches = pattern_def.pattern.finditer(text)

            for match in matches:
                pii_instance = {
                    'type': pattern_def.pii_type.value,
                    'original_text': match.group(),
                    'start_pos': match.start(),
                    'end_pos': match.end(),
                    'confidence': pattern_def.confidence,
                    'description': pattern_def.description,
                    'mask_template': pattern_def.mask_template
                }
                pii_instances.append(pii_instance)

        # Sort by position for consistent masking
        pii_instances.sort(key=lambda x: x['start_pos'])

        return pii_instances

    def _apply_masking(self, text: str, pii_instances: List[Dict[str, Any]]) -> str:
        """Apply masking to text based on detected PII."""
        if not pii_instances:
            return text

        masked_text = text
        offset = 0  # Track offset from replacements

        for pii in pii_instances:
            start_pos = pii['start_pos'] + offset
            end_pos = pii['end_pos'] + offset
            original = pii['original_text']
            mask = pii['mask_template']

            # Replace original text with mask
            masked_text = masked_text[:start_pos] + mask + masked_text[end_pos:]

            # Update offset for next replacement
            offset += len(mask) - len(original)

        return masked_text

    def mask_text(self, text: str) -> MaskingResult:
        """Mask PII in text content."""
        if not text:
            return MaskingResult(
                original_text=text,
                masked_text=text,
                pii_found=[],
                masking_applied=False
            )

        # Detect PII instances
        pii_instances = self._detect_pii_in_text(text)

        # Apply masking if PII found
        masked_text = self._apply_masking(text, pii_instances) if pii_instances else text

        result = MaskingResult(
            original_text=text,
            masked_text=masked_text,
            pii_found=pii_instances,
            masking_applied=len(pii_instances) > 0
        )

        if result.masking_applied:
            logger.debug(f"Masked {len(pii_instances)} PII instances in text")

        return result

    def mask_xml_content(self, xml_content: str) -> MaskingResult:
        """Mask PII in XML content while preserving structure."""
        # For XML, we need to be careful not to mask XML tags/attributes
        # Extract text content from XML and mask only that

        import xml.etree.ElementTree as ET

        try:
            # Parse XML to extract text content
            root = ET.fromstring(xml_content)

            # Collect all text content
            text_contents = []

            def extract_text(element):
                if element.text and element.text.strip():
                    text_contents.append(element.text.strip())
                for child in element:
                    extract_text(child)
                    if child.tail and child.tail.strip():
                        text_contents.append(child.tail.strip())

            extract_text(root)

            # Mask each text content
            all_pii = []
            masked_xml = xml_content

            for text_content in text_contents:
                if len(text_content) > 3:  # Skip very short text
                    masking_result = self.mask_text(text_content)
                    if masking_result.masking_applied:
                        all_pii.extend(masking_result.pii_found)
                        # Replace in XML content
                        masked_xml = masked_xml.replace(text_content, masking_result.masked_text)

            return MaskingResult(
                original_text=xml_content,
                masked_text=masked_xml,
                pii_found=all_pii,
                masking_applied=len(all_pii) > 0
            )

        except ET.ParseError:
            # If XML parsing fails, fall back to text masking
            logger.warning("XML parsing failed, falling back to text masking")
            return self.mask_text(xml_content)

    def mask_dictionary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Mask PII in dictionary values recursively."""
        masked_data = {}

        for key, value in data.items():
            if isinstance(value, str):
                masking_result = self.mask_text(value)
                masked_data[key] = masking_result.masked_text
            elif isinstance(value, dict):
                masked_data[key] = self.mask_dictionary(value)
            elif isinstance(value, list):
                masked_data[key] = [
                    self.mask_dictionary(item) if isinstance(item, dict)
                    else self.mask_text(item).masked_text if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                masked_data[key] = value

        return masked_data

    def get_masking_stats(self, text: str) -> Dict[str, int]:
        """Get statistics about PII types found in text."""
        pii_instances = self._detect_pii_in_text(text)

        stats = {}
        for pii in pii_instances:
            pii_type = pii['type']
            stats[pii_type] = stats.get(pii_type, 0) + 1

        return stats


# Global PII masking engine instance
pii_engine = PiiMaskingEngine()


def mask_text(text: str) -> MaskingResult:
    """Convenience function to mask PII in text."""
    return pii_engine.mask_text(text)


def mask_xml_content(xml_content: str) -> MaskingResult:
    """Convenience function to mask PII in XML content."""
    return pii_engine.mask_xml_content(xml_content)


def mask_dictionary(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function to mask PII in dictionary."""
    return pii_engine.mask_dictionary(data)