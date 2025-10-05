"""
XML streaming parser for AssistedDiscovery.

Memory-efficient XML processing using lxml.iterparse with path-trie matching
for target section detection. Designed for large NDC XML files.
"""

import logging
from typing import Dict, List, Optional, Iterator, Tuple, Set
from pathlib import Path
from dataclasses import dataclass, field
from lxml import etree
import hashlib

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class XmlElement:
    """Represents an XML element with its context."""
    tag: str
    text: Optional[str]
    attributes: Dict[str, str]
    path: str
    namespace_uri: Optional[str] = None
    namespace_prefix: Optional[str] = None

    @property
    def local_name(self) -> str:
        """Get local name without namespace prefix."""
        if '}' in self.tag:
            return self.tag.split('}')[1]
        return self.tag


@dataclass
class XmlSubtree:
    """Represents an extracted XML subtree."""
    root_element: XmlElement
    xml_content: str
    size_bytes: int
    path: str
    node_count: int = 0


@dataclass
class NdcVersionInfo:
    """NDC version information extracted from XML."""
    spec_version: Optional[str] = None
    message_root: Optional[str] = None
    namespace_uri: Optional[str] = None
    schema_location: Optional[str] = None
    airline_code: Optional[str] = None
    airline_name: Optional[str] = None


class PathTrieNode:
    """Node in the path matching trie for efficient target detection."""

    def __init__(self):
        self.children: Dict[str, 'PathTrieNode'] = {}
        self.is_target: bool = False
        self.target_info: Optional[Dict] = None

    def add_path(self, path_parts: List[str], target_info: Dict):
        """Add a target path to the trie."""
        current = self
        for part in path_parts:
            if part not in current.children:
                current.children[part] = PathTrieNode()
            current = current.children[part]
        current.is_target = True
        current.target_info = target_info

    def match_path(self, path_parts: List[str]) -> Optional[Dict]:
        """Check if path matches any target and return target info."""
        current = self
        for part in path_parts:
            if part not in current.children:
                return None
            current = current.children[part]
        return current.target_info if current.is_target else None


class XmlStreamingParser:
    """Memory-efficient XML streaming parser with target detection."""

    def __init__(self, target_paths: List[Dict]):
        """Initialize parser with target paths."""
        self.target_paths = target_paths
        self.path_trie = PathTrieNode()
        self.version_info = NdcVersionInfo()
        self._build_path_trie()

    def _build_path_trie(self):
        """Build path matching trie from target paths."""
        for target in self.target_paths:
            path_local = target.get('path_local', '')
            if path_local.startswith('/'):
                path_local = path_local[1:]  # Remove leading slash

            path_parts = path_local.split('/') if path_local else []
            if path_parts:
                self.path_trie.add_path(path_parts, target)

        logger.info(f"Built path trie with {len(self.target_paths)} target paths")

    def _extract_version_info(self, element: etree.Element) -> bool:
        """Extract NDC version info from root element. Returns True if found."""
        import re

        tag = element.tag

        # Extract namespace URI
        if '}' in tag:
            namespace_uri, local_name = tag.split('}', 1)
            namespace_uri = namespace_uri[1:]  # Remove leading {
            self.version_info.namespace_uri = namespace_uri
        else:
            local_name = tag

        # Set message root (normalize IATA_ prefixes)
        if local_name.startswith('IATA_'):
            self.version_info.message_root = local_name[5:]  # Remove IATA_ prefix
        else:
            self.version_info.message_root = local_name

        # Version detection strategy (in order of preference)
        detected_version = None
        detection_source = None

        # 1. Extract from namespace URI (highest priority)
        if self.version_info.namespace_uri:
            # Pattern 1: YYYY.M format (e.g., 2018.2, 2019.2)
            version_match = re.search(r'(\d{4}\.\d+)', self.version_info.namespace_uri)
            if version_match:
                year_version = version_match.group(1)
                # Convert YYYY.M to YY.M format (2018.2 -> 18.2)
                year = int(year_version.split('.')[0])
                minor = year_version.split('.')[1]
                detected_version = f"{year - 2000}.{minor}"
                detection_source = "namespace (YYYY.M format)"
            else:
                # Pattern 2: Standard NN.M format (e.g., 17.2, 18.1)
                version_match = re.search(r'(\d+\.\d+)', self.version_info.namespace_uri)
                if version_match:
                    detected_version = version_match.group(1)
                    detection_source = "namespace (NN.M format)"

            # Special case: Map known namespace patterns
            if '2017.2' in self.version_info.namespace_uri:
                detected_version = '17.2'
                detection_source = "namespace (mapped 2017.2)"

        # 2. Check attributes for version info
        if not detected_version:
            for attr_name, attr_value in element.attrib.items():
                if 'version' in attr_name.lower():
                    # Handle special cases for version attributes
                    if attr_value == '5.000':
                        # Iberia case - version 5.000 with 2017.2 namespace should be 17.2
                        if self.version_info.namespace_uri and '2017.2' in self.version_info.namespace_uri:
                            detected_version = '17.2'
                            detection_source = f"attribute ({attr_name}) with namespace correction"
                        else:
                            detected_version = '17.2'  # Default mapping for 5.000
                            detection_source = f"attribute ({attr_name}) mapped"
                    else:
                        detected_version = attr_value
                        detection_source = f"attribute ({attr_name})"
                    break
                elif 'schemalocation' in attr_name.lower():
                    self.version_info.schema_location = attr_value

        # 3. Look for PayloadAttributes/Version element
        if not detected_version:
            payload_attrs = element.find('.//PayloadAttributes/Version')
            if payload_attrs is not None and payload_attrs.text:
                detected_version = payload_attrs.text.strip()
                detection_source = "PayloadAttributes/Version"

        # 4. Check for Version element directly under root
        if not detected_version:
            version_elem = element.find('./Version')
            if version_elem is not None and version_elem.text:
                detected_version = version_elem.text.strip()
                detection_source = "direct Version element"

        # 5. Fallback strategies for files without explicit versions
        if not detected_version:
            # Try to infer from namespace patterns
            if self.version_info.namespace_uri:
                if 'IATA/2015' in self.version_info.namespace_uri:
                    # Newer IATA format, assume latest supported version
                    detected_version = '21.3'
                    detection_source = "fallback (IATA/2015 namespace)"
                elif 'EDIST' in self.version_info.namespace_uri:
                    # NDC EDIST format, assume 17.2 if no other version found
                    detected_version = '17.2'
                    detection_source = "fallback (EDIST namespace)"

        # 6. Final fallback for recognized message types
        if not detected_version and self.version_info.message_root in ['OrderViewRS', 'OrderCreateRQ', 'OrderChangeRQ']:
            detected_version = '17.2'  # Most common baseline version
            detection_source = "fallback (recognized NDC message type)"

        # Set the detected version
        self.version_info.spec_version = detected_version

        # Log version detection with source
        if detected_version:
            logger.info(f"Detected NDC version: {detected_version} via {detection_source}, "
                       f"message root: {self.version_info.message_root}")
        else:
            logger.warning(f"No version detected for message root: {self.version_info.message_root}")

        return bool(self.version_info.spec_version and self.version_info.message_root)

    def _extract_airline_info(self, element: etree.Element) -> bool:
        """Extract airline information from root element. Returns True if found."""

        # Strategy 1: Check Order/@Owner attribute
        order_elem = element.find('.//{*}Order')
        if order_elem is not None:
            owner = order_elem.get('Owner')
            if owner:
                self.version_info.airline_code = owner
                logger.info(f"Detected airline from Order/@Owner: {owner}")
                return True

        # Strategy 2: Check OwnerCode element
        owner_code_elem = element.find('.//{*}OwnerCode')
        if owner_code_elem is not None and owner_code_elem.text:
            self.version_info.airline_code = owner_code_elem.text.strip()
            logger.info(f"Detected airline from OwnerCode: {self.version_info.airline_code}")
            return True

        # Strategy 3: Check BookingReference/AirlineID
        airline_id_elem = element.find('.//{*}BookingReference/{*}AirlineID')
        if airline_id_elem is not None:
            airline_code = airline_id_elem.text.strip() if airline_id_elem.text else None
            airline_name = airline_id_elem.get('Name')

            if airline_code:
                self.version_info.airline_code = airline_code
                if airline_name:
                    self.version_info.airline_name = airline_name
                logger.info(f"Detected airline from BookingReference/AirlineID: {airline_code} ({airline_name or 'N/A'})")
                return True

        # Strategy 4: Check PaxSegment/MarketingCarrierInfo
        marketing_carrier = element.find('.//{*}PaxSegment/{*}MarketingCarrierInfo')
        if marketing_carrier is not None:
            carrier_code_elem = marketing_carrier.find('{*}CarrierDesigCode')
            carrier_name_elem = marketing_carrier.find('{*}CarrierName')

            if carrier_code_elem is not None and carrier_code_elem.text:
                self.version_info.airline_code = carrier_code_elem.text.strip()
                if carrier_name_elem is not None and carrier_name_elem.text:
                    self.version_info.airline_name = carrier_name_elem.text.strip()
                logger.info(f"Detected airline from MarketingCarrierInfo: {self.version_info.airline_code} ({self.version_info.airline_name or 'N/A'})")
                return True

        # Strategy 5: Check PaxSegment/OperatingCarrierInfo (fallback)
        operating_carrier = element.find('.//{*}PaxSegment/{*}OperatingCarrierInfo')
        if operating_carrier is not None:
            carrier_code_elem = operating_carrier.find('{*}CarrierDesigCode')
            carrier_name_elem = operating_carrier.find('{*}CarrierName')

            if carrier_code_elem is not None and carrier_code_elem.text:
                self.version_info.airline_code = carrier_code_elem.text.strip()
                if carrier_name_elem is not None and carrier_name_elem.text:
                    self.version_info.airline_name = carrier_name_elem.text.strip()
                logger.info(f"Detected airline from OperatingCarrierInfo: {self.version_info.airline_code} ({self.version_info.airline_name or 'N/A'})")
                return True

        logger.warning("No airline information detected in XML")
        return False

    def _build_element_path(self, element_stack: List[str]) -> str:
        """Build element path from stack."""
        return '/' + '/'.join(element_stack) if element_stack else '/'

    def _is_potential_target_ancestor(self, element_stack: List[str]) -> bool:
        """
        Check if current element path is part of or ancestor of any target path.
        This prevents premature clearing of elements that might be part of target subtrees.
        """
        if not element_stack:
            return False

        current_path_parts = [part for part in element_stack if part]

        for target in self.target_paths:
            target_path = target.get('path_local', '')
            if target_path.startswith('/'):
                target_path = target_path[1:]

            target_parts = target_path.split('/') if target_path else []

            # Case 1: Current path is a prefix of target (ancestor)
            # Example: /OrderViewRS/Response is ancestor of /OrderViewRS/Response/DataLists/BaggageAllowanceList
            if len(current_path_parts) <= len(target_parts):
                is_prefix = all(
                    current_path_parts[i] == target_parts[i]
                    for i in range(len(current_path_parts))
                )
                if is_prefix:
                    return True

            # Case 2: Target path is a prefix of current path (child/descendant of target)
            # Example: /OrderViewRS/Response/DataLists/BaggageAllowanceList/BaggageAllowance
            # is a child of target /OrderViewRS/Response/DataLists/BaggageAllowanceList
            if len(target_parts) <= len(current_path_parts):
                is_child = all(
                    target_parts[i] == current_path_parts[i]
                    for i in range(len(target_parts))
                )
                if is_child:
                    return True

        return False

    def _element_to_string(self, element: etree.Element) -> str:
        """Convert element and its subtree to string."""
        return etree.tostring(element, encoding='unicode', pretty_print=True)

    def _calculate_subtree_size(self, xml_content: str) -> int:
        """Calculate subtree size in bytes."""
        return len(xml_content.encode('utf-8'))

    def _count_nodes(self, element: etree.Element) -> int:
        """Count total nodes in subtree."""
        count = 1  # Current element
        for child in element:
            count += self._count_nodes(child)
        return count

    def parse_stream(self, xml_file_path: str) -> Iterator[XmlSubtree]:
        """
        Parse XML file as stream, yielding target subtrees.

        Args:
            xml_file_path: Path to XML file to parse

        Yields:
            XmlSubtree: Target subtrees found during parsing
        """
        file_path = Path(xml_file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"XML file not found: {xml_file_path}")

        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > settings.MAX_XML_SIZE_MB:
            raise ValueError(f"XML file too large: {file_size_mb:.1f}MB > {settings.MAX_XML_SIZE_MB}MB")

        logger.info(f"Starting XML stream parsing: {xml_file_path} ({file_size_mb:.1f}MB)")

        element_stack: List[str] = []
        subtrees_found = 0
        version_detected = False

        try:
            # Use iterparse for memory-efficient streaming with recovery mode
            # recover=True allows parsing files with trailing garbage/EDIFACT content
            context = etree.iterparse(xml_file_path, events=('start', 'end'), recover=True)

            for event, element in context:
                if event == 'start':
                    local_name = element.tag.split('}')[1] if '}' in element.tag else element.tag
                    element_stack.append(local_name)

                    # Detect version info from root element
                    if len(element_stack) == 1 and not version_detected:
                        version_detected = self._extract_version_info(element)
                        # Note: Airline detection happens in detect_ndc_version_fast() before streaming

                elif event == 'end':
                    if element_stack:
                        current_path = self._build_element_path(element_stack)

                        # Check if current path matches any target
                        path_parts = [part for part in element_stack if part]
                        target_info = self.path_trie.match_path(path_parts)

                        if target_info:
                            # Extract subtree
                            xml_content = self._element_to_string(element)
                            subtree_size = self._calculate_subtree_size(xml_content)

                            # Check size limit
                            if subtree_size <= settings.MAX_SUBTREE_SIZE_KB * 1024:
                                node_count = self._count_nodes(element)

                                xml_element = XmlElement(
                                    tag=element.tag,
                                    text=element.text.strip() if element.text else None,
                                    attributes=dict(element.attrib),
                                    path=current_path,
                                    namespace_uri=self.version_info.namespace_uri
                                )

                                subtree = XmlSubtree(
                                    root_element=xml_element,
                                    xml_content=xml_content,
                                    size_bytes=subtree_size,
                                    path=current_path,
                                    node_count=node_count
                                )

                                subtrees_found += 1
                                logger.debug(f"Found target subtree: {current_path} "
                                           f"({subtree_size} bytes, {node_count} nodes)")
                                yield subtree
                            else:
                                logger.warning(f"Subtree too large, skipping: {current_path} "
                                             f"({subtree_size} bytes > {settings.MAX_SUBTREE_SIZE_KB * 1024})")

                            # After extracting target, always clear it
                            element.clear()
                            while element.getprevious() is not None:
                                del element.getparent()[0]
                        else:
                            # Check if this element is part of a potential target path
                            # Only clear if not in a potential target path
                            should_clear = not self._is_potential_target_ancestor(element_stack)

                            if should_clear:
                                # Clean up processed element to free memory
                                element.clear()
                                while element.getprevious() is not None:
                                    del element.getparent()[0]

                        # Pop from stack
                        element_stack.pop()

        except etree.XMLSyntaxError as e:
            logger.error(f"XML syntax error in {xml_file_path}: {e}")
            raise ValueError(f"Invalid XML syntax: {e}")
        except Exception as e:
            logger.error(f"Error parsing XML file {xml_file_path}: {e}")
            raise

        logger.info(f"Completed XML parsing: {subtrees_found} target subtrees found")

    def get_version_info(self) -> NdcVersionInfo:
        """Get detected NDC version information."""
        return self.version_info

    def get_target_paths_for_version(self, spec_version: str, message_root: str) -> List[Dict]:
        """Get target paths that match the detected version."""
        matching_paths = []
        for target in self.target_paths:
            if (target.get('spec_version') == spec_version and
                target.get('message_root') == message_root):
                matching_paths.append(target)
        return matching_paths


def detect_ndc_version_fast(xml_file_path: str) -> Optional[NdcVersionInfo]:
    """
    Fast version detection by parsing only the root element.

    Args:
        xml_file_path: Path to XML file

    Returns:
        NdcVersionInfo if detected, None if detection fails
    """
    file_path = Path(xml_file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"XML file not found: {xml_file_path}")

    logger.info(f"Fast version detection: {xml_file_path}")

    try:
        # Parse the XML to get the full tree (needed for airline detection in nested elements)
        # Use XMLParser with recover=True to handle malformed XML (like unescaped & characters)
        parser = etree.XMLParser(recover=True)
        tree = etree.parse(xml_file_path, parser)
        root_element = tree.getroot()

        # Create temporary parser to use existing version detection logic
        temp_parser = XmlStreamingParser([])  # Empty target paths for detection only
        version_detected = temp_parser._extract_version_info(root_element)
        # Also extract airline information
        temp_parser._extract_airline_info(root_element)

        if version_detected:
            logger.info(f"Fast detection successful: {temp_parser.version_info.spec_version}/"
                       f"{temp_parser.version_info.message_root} - "
                       f"Airline: {temp_parser.version_info.airline_code or 'N/A'}")
            return temp_parser.version_info
        else:
            logger.warning(f"Fast version detection failed for: {xml_file_path}")
            return None

    except etree.XMLSyntaxError as e:
        logger.error(f"XML syntax error in {xml_file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error in fast version detection {xml_file_path}: {e}")
        return None


def create_parser_for_version(spec_version: str, message_root: str,
                            all_target_paths: List[Dict]) -> XmlStreamingParser:
    """Create parser configured for specific NDC version."""
    # Filter target paths for this version
    matching_paths = [
        path for path in all_target_paths
        if (path.get('spec_version') == spec_version and
            path.get('message_root') == message_root)
    ]

    if not matching_paths:
        logger.warning(f"No target paths found for {spec_version}/{message_root}")

    return XmlStreamingParser(matching_paths)