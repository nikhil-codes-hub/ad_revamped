"""
LLM extraction test endpoints for AssistedDiscovery.

Provides endpoints to test LLM-based NodeFacts extraction.
"""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import structlog

from app.services.llm_extractor import get_llm_extractor
from app.services.xml_parser import XmlSubtree, XmlElement
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


class LLMTestRequest(BaseModel):
    """Request model for LLM extraction test."""
    xml_content: str
    section_path: str = "/test/path"


class LLMTestResponse(BaseModel):
    """Response model for LLM extraction test."""
    success: bool
    facts_extracted: int
    confidence_score: float
    processing_time_ms: int
    tokens_used: int
    model_used: str
    error_message: str = None
    facts: list = None


@router.post("/test", response_model=LLMTestResponse)
async def test_llm_extraction(request: LLMTestRequest) -> LLMTestResponse:
    """
    Test LLM extraction with provided XML content.

    - **xml_content**: XML content to extract facts from
    - **section_path**: Optional section path for context
    """
    logger.info("Testing LLM extraction",
                content_length=len(request.xml_content),
                section_path=request.section_path)

    try:
        # Create test subtree
        xml_element = XmlElement(
            tag="TestElement",
            text=None,
            attributes={},
            path=request.section_path,
            namespace_uri="http://test.example.com"
        )

        subtree = XmlSubtree(
            root_element=xml_element,
            xml_content=request.xml_content,
            size_bytes=len(request.xml_content.encode('utf-8')),
            path=request.section_path,
            node_count=1
        )

        # Get LLM extractor and test
        llm_extractor = get_llm_extractor()

        if not llm_extractor.client:
            raise HTTPException(
                status_code=503,
                detail="LLM service not available. Check API key configuration."
            )

        # Extract facts
        result = await llm_extractor.extract_from_subtree(subtree)

        logger.info("LLM extraction completed",
                    facts_extracted=len(result.node_facts),
                    confidence_score=result.confidence_score,
                    processing_time_ms=result.processing_time_ms)

        return LLMTestResponse(
            success=True,
            facts_extracted=len(result.node_facts),
            confidence_score=result.confidence_score,
            processing_time_ms=result.processing_time_ms,
            tokens_used=result.tokens_used,
            model_used=result.model_used,
            facts=result.node_facts
        )

    except Exception as e:
        error_msg = str(e)
        logger.error("LLM extraction test failed", error=error_msg)

        return LLMTestResponse(
            success=False,
            facts_extracted=0,
            confidence_score=0.0,
            processing_time_ms=0,
            tokens_used=0,
            model_used="error",
            error_message=error_msg
        )


@router.get("/sample-xml")
async def get_sample_xml() -> Dict[str, Any]:
    """
    Get sample NDC XML content for testing LLM extraction.
    """
    return {
        "contact_info": {
            "xml_content": """<ContactInfo ContactInfoType="CustSup" ContactRef="CTC1">
    <OtherContactInfo>
        <ContactInfoText>
            <TypeInfo>
                <ContactInfoTypeCode>PHONE</ContactInfoTypeCode>
            </TypeInfo>
            <ContactInfoValue>+65-6223-8888</ContactInfoValue>
        </ContactInfoText>
    </OtherContactInfo>
    <EmailAddress>
        <EmailAddressText>customer.support@singaporeair.com</EmailAddressText>
    </EmailAddress>
</ContactInfo>""",
            "section_path": "/OrderViewRS/Response/DataLists/ContactList/ContactInfo"
        },
        "baggage_allowance": {
            "xml_content": """<BaggageAllowanceRef>
    <BaggageAllowanceID>BAG1</BaggageAllowanceID>
    <BaggageFlightAssociations>
        <PaxSegmentRefID>PS1</PaxSegmentRefID>
    </BaggageFlightAssociations>
    <PassengerRef>
        <PassengerRefID>PAX1</PassengerRefID>
    </PassengerRef>
    <BaggageAllowanceList>
        <BaggageAllowance>
            <BaggageCategory>Checked</BaggageCategory>
            <AllowanceDescription BaggageDescID="BDESC1">
                <ApplicableParty>Traveler</ApplicableParty>
                <Descriptions>
                    <Description>
                        <Text>Checked Baggage</Text>
                    </Description>
                </Descriptions>
            </AllowanceDescription>
            <PieceAllowance>
                <TotalQuantity>2</TotalQuantity>
                <PieceMeasurements Quantity="1">
                    <Dimension type="Weight">
                        <Value>23</Value>
                        <UOM>KG</UOM>
                    </Dimension>
                </PieceMeasurements>
            </PieceAllowance>
        </BaggageAllowance>
    </BaggageAllowanceList>
</BaggageAllowanceRef>""",
            "section_path": "/OrderViewRS/Response/DataLists/BaggageAllowanceList/BaggageAllowanceRef"
        }
    }