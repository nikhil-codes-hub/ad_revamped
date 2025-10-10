"""
Template extractor engine for AssistedDiscovery.

Extracts structured data from XML subtrees using predefined templates
for known NDC patterns. Designed for deterministic, efficient extraction
from well-structured sections like booking references and passenger lists.
"""

import logging
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element

from app.services.xml_parser import XmlSubtree, XmlElement
from app.services.pii_masking import mask_dictionary, MaskingResult

logger = logging.getLogger(__name__)


class ExtractionResult(str, Enum):
    """Extraction result status."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    NO_TEMPLATE = "no_template"


@dataclass
class NodeFact:
    """Structured fact extracted from XML node."""
    node_type: str
    node_ordinal: int
    section_path: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    text_content: Optional[str] = None
    child_elements: List[str] = field(default_factory=list)
    references: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'node_type': self.node_type,
            'node_ordinal': self.node_ordinal,
            'section_path': self.section_path,
            'attributes': self.attributes,
            'text_content': self.text_content,
            'child_elements': self.child_elements,
            'references': self.references
        }


@dataclass
class ExtractionTemplate:
    """Template for extracting data from specific XML sections."""
    template_key: str
    node_type: str
    xpath_selector: str
    extractor_function: Callable[[Element], List[NodeFact]]
    required_elements: List[str] = field(default_factory=list)
    optional_elements: List[str] = field(default_factory=list)
    description: str = ""

    def extract(self, xml_element: Element, section_path: str) -> List[NodeFact]:
        """Extract facts using this template."""
        try:
            return self.extractor_function(xml_element, section_path)
        except Exception as e:
            logger.error(f"Template extraction failed for {self.template_key}: {e}")
            return []


class TemplateExtractorEngine:
    """Engine for template-based data extraction from XML subtrees."""

    def __init__(self):
        """Initialize template extractor with predefined templates."""
        self.templates: Dict[str, ExtractionTemplate] = {}
        self._register_builtin_templates()

    def _register_builtin_templates(self):
        """Register built-in extraction templates for common NDC patterns."""

        # Booking Reference template
        self.register_template(ExtractionTemplate(
            template_key="booking_reference",
            node_type="BookingReference",
            xpath_selector=".//BookingReference",
            extractor_function=self._extract_booking_reference,
            required_elements=["ID"],
            description="Extract booking reference information"
        ))

        # Passenger template
        self.register_template(ExtractionTemplate(
            template_key="passenger",
            node_type="Passenger",
            xpath_selector=".//Passenger",
            extractor_function=self._extract_passenger,
            required_elements=["PassengerID"],
            optional_elements=["GivenName", "Surname", "Birthdate"],
            description="Extract passenger information"
        ))

        # Contact template - Fixed for NDC structure
        self.register_template(ExtractionTemplate(
            template_key="contact",
            node_type="ContactInfo",
            xpath_selector=".//ContactInfo",
            extractor_function=self._extract_contact,
            optional_elements=["EmailAddress", "Phone"],
            description="Extract contact information from NDC ContactInfo"
        ))

        # Order template
        self.register_template(ExtractionTemplate(
            template_key="order",
            node_type="Order",
            xpath_selector=".//Order",
            extractor_function=self._extract_order,
            required_elements=["OrderID"],
            optional_elements=["TotalOrderPrice", "TimeLimits"],
            description="Extract main order information"
        ))

        # Flight segment template
        self.register_template(ExtractionTemplate(
            template_key="flight_segment",
            node_type="FlightSegment",
            xpath_selector=".//FlightSegment",
            extractor_function=self._extract_flight_segment,
            required_elements=["SegmentKey"],
            optional_elements=["Departure", "Arrival", "FlightDetail"],
            description="Extract flight segment details"
        ))

        # Origin destination template
        self.register_template(ExtractionTemplate(
            template_key="origin_destination",
            node_type="OriginDestination",
            xpath_selector=".//OriginDestination",
            extractor_function=self._extract_origin_destination,
            required_elements=["OriginDestinationKey"],
            optional_elements=["DepartureCode", "ArrivalCode"],
            description="Extract origin and destination information"
        ))

        # Baggage allowance template - for NDC structure
        self.register_template(ExtractionTemplate(
            template_key="baggage_allowance",
            node_type="BaggageAllowance",
            xpath_selector=".//BaggageAllowance",
            extractor_function=self._extract_baggage_allowance,
            required_elements=["BaggageAllowanceID"],
            optional_elements=["TypeCode", "WeightAllowance"],
            description="Extract baggage allowance information from NDC"
        ))

        logger.info(f"Registered {len(self.templates)} built-in templates")

    def register_template(self, template: ExtractionTemplate):
        """Register a new extraction template."""
        self.templates[template.template_key] = template
        logger.debug(f"Registered template: {template.template_key}")

    def get_template(self, template_key: str) -> Optional[ExtractionTemplate]:
        """Get template by key."""
        return self.templates.get(template_key)

    def get_available_templates(self) -> List[str]:
        """Get list of available template keys."""
        return list(self.templates.keys())

    def _extract_booking_reference(self, element: Element, section_path: str) -> List[NodeFact]:
        """Extract booking reference information."""
        facts = []
        booking_refs = element.findall(".//BookingReference")

        for idx, ref_elem in enumerate(booking_refs):
            fact = NodeFact(
                node_type="BookingReference",
                node_ordinal=idx + 1,
                section_path=section_path
            )

            # Extract ID
            id_elem = ref_elem.find(".//ID")
            if id_elem is not None and id_elem.text:
                fact.attributes["booking_id"] = id_elem.text.strip()

            # Extract type/source
            type_elem = ref_elem.find(".//Type")
            if type_elem is not None and type_elem.text:
                fact.attributes["reference_type"] = type_elem.text.strip()

            # Extract any other attributes
            for attr_name, attr_value in ref_elem.attrib.items():
                fact.attributes[f"attr_{attr_name}"] = attr_value

            # Extract text content if present
            if ref_elem.text and ref_elem.text.strip():
                fact.text_content = ref_elem.text.strip()

            # List child elements
            fact.child_elements = [child.tag for child in ref_elem]

            facts.append(fact)

        return facts

    def _extract_passenger(self, element: Element, section_path: str) -> List[NodeFact]:
        """Extract passenger information."""
        facts = []
        passengers = []
        for candidate in element.iter():
            local_name = candidate.tag.split('}')[-1] if '}' in candidate.tag else candidate.tag
            if local_name in {"Passenger", "Pax"}:
                passengers.append(candidate)

        for idx, pax_elem in enumerate(passengers):
            fact = NodeFact(
                node_type="Passenger",
                node_ordinal=idx + 1,
                section_path=section_path
            )

            # Extract passenger ID
            id_elem = None
            for child in pax_elem.iter():
                if child is pax_elem:
                    continue
                local_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                if local_name in {"PassengerID", "PaxID"}:
                    id_elem = child
                    break
            if id_elem is not None and id_elem.text:
                fact.attributes["passenger_id"] = id_elem.text.strip()

            # Extract name information
            given_name = None
            surname = None
            for child in pax_elem.iter():
                if child is pax_elem:
                    continue
                local_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                if local_name == "GivenName" and given_name is None:
                    given_name = child
                elif local_name == "Surname" and surname is None:
                    surname = child
                if given_name is not None and surname is not None:
                    break

            if given_name is not None and given_name.text:
                fact.attributes["given_name"] = given_name.text.strip()

            if surname is not None and surname.text:
                fact.attributes["surname"] = surname.text.strip()

            # Extract birth date
            birthdate = None
            for child in pax_elem.iter():
                if child is pax_elem:
                    continue
                local_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                if local_name == "Birthdate":
                    birthdate = child
                    break

            if birthdate is not None and birthdate.text:
                fact.attributes["birth_date"] = birthdate.text.strip()

            # Extract passenger type
            pax_type = None
            for child in pax_elem.iter():
                if child is pax_elem:
                    continue
                local_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                if local_name == "PTC":
                    pax_type = child
                    break
            if pax_type is not None and pax_type.text:
                fact.attributes["passenger_type"] = pax_type.text.strip()

            # Extract any references/IDs
            for ref_elem in pax_elem.iter():
                if not ref_elem.attrib:
                    continue
                local_name = ref_elem.tag.split('}')[-1] if '}' in ref_elem.tag else ref_elem.tag
                for attr_name, attr_value in ref_elem.attrib.items():
                    if "ref" in attr_name.lower() or "id" in attr_name.lower():
                        fact.references[f"{local_name}_{attr_name}"] = attr_value

            fact.child_elements = [
                child.tag.split('}')[-1] if '}' in child.tag else child.tag
                for child in pax_elem
            ]
            facts.append(fact)

        return facts

    def _extract_contact(self, element: Element, section_path: str) -> List[NodeFact]:
        """Extract contact information from NDC ContactInfo structure."""
        facts = []
        contacts = element.findall(".//ContactInfo")

        for idx, contact_elem in enumerate(contacts):
            fact = NodeFact(
                node_type="ContactInfo",
                node_ordinal=idx + 1,
                section_path=section_path
            )

            # Extract ContactInfoID
            contact_id = contact_elem.find(".//ContactInfoID")
            if contact_id is not None and contact_id.text:
                fact.attributes["contact_id"] = contact_id.text.strip()

            # Extract email from EmailAddress/EmailAddressText
            email_address = contact_elem.find(".//EmailAddress/EmailAddressText")
            if email_address is not None and email_address.text:
                fact.attributes["email"] = email_address.text.strip()

            # Extract phone information
            phone = contact_elem.find(".//Phone")
            if phone is not None:
                phone_number = phone.find(".//PhoneNumber")
                if phone_number is not None and phone_number.text:
                    fact.attributes["phone_number"] = phone_number.text.strip()

                country_code = phone.find(".//CountryDialingCode")
                if country_code is not None and country_code.text:
                    fact.attributes["country_code"] = country_code.text.strip()

                label = phone.find(".//LabelText")
                if label is not None and label.text:
                    fact.attributes["phone_label"] = label.text.strip()

            # Extract contact type
            contact_type = contact_elem.find(".//ContactTypeText")
            if contact_type is not None and contact_type.text:
                fact.attributes["contact_type"] = contact_type.text.strip()

            # Extract individual reference
            individual_ref = contact_elem.find(".//IndividualRef")
            if individual_ref is not None and individual_ref.text:
                fact.attributes["individual_ref"] = individual_ref.text.strip()

            fact.child_elements = [child.tag for child in contact_elem]
            facts.append(fact)

        return facts

    def _extract_order(self, element: Element, section_path: str) -> List[NodeFact]:
        """Extract order information."""
        facts = []
        orders = element.findall(".//Order")

        for idx, order_elem in enumerate(orders):
            fact = NodeFact(
                node_type="Order",
                node_ordinal=idx + 1,
                section_path=section_path
            )

            # Extract order ID
            order_id = order_elem.find(".//OrderID")
            if order_id is not None and order_id.text:
                fact.attributes["order_id"] = order_id.text.strip()

            # Extract total price
            total_price = order_elem.find(".//TotalOrderPrice")
            if total_price is not None:
                amount = total_price.find(".//SimpleCurrencyPrice")
                if amount is not None and amount.text:
                    fact.attributes["total_amount"] = amount.text.strip()

                currency = total_price.find(".//Code")
                if currency is not None and currency.text:
                    fact.attributes["currency"] = currency.text.strip()

            # Extract time limits
            time_limits = order_elem.find(".//TimeLimits")
            if time_limits is not None:
                payment_time = time_limits.find(".//PaymentTimeLimit")
                if payment_time is not None and payment_time.text:
                    fact.attributes["payment_deadline"] = payment_time.text.strip()

            fact.child_elements = [child.tag for child in order_elem]
            facts.append(fact)

        return facts

    def _extract_flight_segment(self, element: Element, section_path: str) -> List[NodeFact]:
        """Extract flight segment information."""
        facts = []
        segments = element.findall(".//FlightSegment")

        for idx, seg_elem in enumerate(segments):
            fact = NodeFact(
                node_type="FlightSegment",
                node_ordinal=idx + 1,
                section_path=section_path
            )

            # Extract segment key
            seg_key = seg_elem.get("SegmentKey")
            if seg_key:
                fact.attributes["segment_key"] = seg_key

            # Extract departure info
            departure = seg_elem.find(".//Departure")
            if departure is not None:
                dep_airport = departure.find(".//AirportCode")
                if dep_airport is not None and dep_airport.text:
                    fact.attributes["departure_airport"] = dep_airport.text.strip()

                dep_date = departure.find(".//Date")
                if dep_date is not None and dep_date.text:
                    fact.attributes["departure_date"] = dep_date.text.strip()

            # Extract arrival info
            arrival = seg_elem.find(".//Arrival")
            if arrival is not None:
                arr_airport = arrival.find(".//AirportCode")
                if arr_airport is not None and arr_airport.text:
                    fact.attributes["arrival_airport"] = arr_airport.text.strip()

                arr_date = arrival.find(".//Date")
                if arr_date is not None and arr_date.text:
                    fact.attributes["arrival_date"] = arr_date.text.strip()

            # Extract flight details
            flight_detail = seg_elem.find(".//FlightDetail")
            if flight_detail is not None:
                flight_num = flight_detail.find(".//FlightNumber")
                if flight_num is not None and flight_num.text:
                    fact.attributes["flight_number"] = flight_num.text.strip()

                airline = flight_detail.find(".//AirlineID")
                if airline is not None and airline.text:
                    fact.attributes["airline_code"] = airline.text.strip()

            fact.child_elements = [child.tag for child in seg_elem]
            facts.append(fact)

        return facts

    def _extract_origin_destination(self, element: Element, section_path: str) -> List[NodeFact]:
        """Extract origin and destination information."""
        facts = []
        od_pairs = element.findall(".//OriginDestination")

        for idx, od_elem in enumerate(od_pairs):
            fact = NodeFact(
                node_type="OriginDestination",
                node_ordinal=idx + 1,
                section_path=section_path
            )

            # Extract OD key
            od_key = od_elem.get("OriginDestinationKey")
            if od_key:
                fact.attributes["od_key"] = od_key

            # Extract departure code
            dep_code = od_elem.find(".//DepartureCode")
            if dep_code is not None and dep_code.text:
                fact.attributes["departure_code"] = dep_code.text.strip()

            # Extract arrival code
            arr_code = od_elem.find(".//ArrivalCode")
            if arr_code is not None and arr_code.text:
                fact.attributes["arrival_code"] = arr_code.text.strip()

            fact.child_elements = [child.tag for child in od_elem]
            facts.append(fact)

        return facts

    def _extract_baggage_allowance(self, element: Element, section_path: str) -> List[NodeFact]:
        """Extract baggage allowance information from NDC structure."""
        facts = []
        baggage_allowances = element.findall(".//BaggageAllowance")

        for idx, baggage_elem in enumerate(baggage_allowances):
            fact = NodeFact(
                node_type="BaggageAllowance",
                node_ordinal=idx + 1,
                section_path=section_path
            )

            # Extract BaggageAllowanceID
            allowance_id = baggage_elem.find(".//BaggageAllowanceID")
            if allowance_id is not None and allowance_id.text:
                fact.attributes["allowance_id"] = allowance_id.text.strip()

            # Extract TypeCode
            type_code = baggage_elem.find(".//TypeCode")
            if type_code is not None and type_code.text:
                fact.attributes["type_code"] = type_code.text.strip()

            # Extract weight allowance information
            weight_allowance = baggage_elem.find(".//WeightAllowance")
            if weight_allowance is not None:
                max_weight = weight_allowance.find(".//MaximumWeightMeasure")
                if max_weight is not None:
                    if max_weight.text:
                        fact.attributes["max_weight"] = max_weight.text.strip()
                    if max_weight.get("UnitCode"):
                        fact.attributes["weight_unit"] = max_weight.get("UnitCode")

                applicable_party = weight_allowance.find(".//ApplicablePartyText")
                if applicable_party is not None and applicable_party.text:
                    fact.attributes["applicable_party"] = applicable_party.text.strip()

            fact.child_elements = [child.tag for child in baggage_elem]
            facts.append(fact)

        return facts

    def extract_from_subtree(self, subtree: XmlSubtree, template_keys: List[str]) -> Dict[str, Any]:
        """Extract facts from XML subtree using specified templates."""
        results = {
            'subtree_path': subtree.path,
            'subtree_size_bytes': subtree.size_bytes,
            'node_count': subtree.node_count,
            'extraction_results': {},
            'total_facts_extracted': 0,
            'extraction_status': ExtractionResult.SUCCESS
        }

        try:
            # Parse XML content
            root = ET.fromstring(subtree.xml_content)

            all_facts = []

            for template_key in template_keys:
                template = self.get_template(template_key)
                if not template:
                    logger.warning(f"Template not found: {template_key}")
                    results['extraction_results'][template_key] = {
                        'status': ExtractionResult.NO_TEMPLATE,
                        'facts': []
                    }
                    continue

                # Extract facts using template
                facts = template.extract(root, subtree.path)

                # Apply PII masking to facts
                masked_facts = []
                for fact in facts:
                    fact_dict = fact.to_dict()
                    masked_fact_dict = mask_dictionary(fact_dict)
                    masked_facts.append(masked_fact_dict)

                results['extraction_results'][template_key] = {
                    'status': ExtractionResult.SUCCESS if facts else ExtractionResult.FAILED,
                    'facts': masked_facts,
                    'count': len(facts)
                }

                all_facts.extend(facts)

            results['total_facts_extracted'] = len(all_facts)

            # Determine overall status
            if results['total_facts_extracted'] == 0:
                results['extraction_status'] = ExtractionResult.FAILED
            elif any(r['status'] == ExtractionResult.FAILED
                    for r in results['extraction_results'].values()):
                results['extraction_status'] = ExtractionResult.PARTIAL

        except ET.ParseError as e:
            logger.error(f"XML parsing error during extraction: {e}")
            results['extraction_status'] = ExtractionResult.FAILED
            results['error'] = f"XML parsing error: {str(e)}"

        except Exception as e:
            logger.error(f"Extraction error: {e}")
            results['extraction_status'] = ExtractionResult.FAILED
            results['error'] = str(e)

        return results


# Global template extractor instance
template_extractor = TemplateExtractorEngine()
