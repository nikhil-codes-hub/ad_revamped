#!/usr/bin/env python3
"""
Test script for LLM-based NodeFacts extractor.
Tests with sample NDC XML content to verify extraction works.
"""

import os
import sys
import asyncio
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.services.llm_extractor import get_llm_extractor
from app.services.xml_parser import XmlSubtree, XmlElement


def create_test_subtree() -> XmlSubtree:
    """Create a test XML subtree for testing."""
    xml_content = """<ContactInfo ContactInfoType="CustSup" ContactRef="CTC1">
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
</ContactInfo>"""

    xml_element = XmlElement(
        tag="ContactInfo",
        text=None,
        attributes={"ContactInfoType": "CustSup", "ContactRef": "CTC1"},
        path="/OrderViewRS/Response/DataLists/ContactList/ContactInfo",
        namespace_uri="http://www.iata.org/IATA/EDIST/2017.2"
    )

    return XmlSubtree(
        root_element=xml_element,
        xml_content=xml_content,
        size_bytes=len(xml_content.encode('utf-8')),
        path="/OrderViewRS/Response/DataLists/ContactList/ContactInfo",
        node_count=8
    )


async def test_llm_extraction():
    """Test LLM extraction with sample data."""
    print("🧪 Testing LLM-based NodeFacts extraction...")

    # Get LLM extractor
    llm_extractor = get_llm_extractor()

    if not llm_extractor.client:
        print("⚠️  LLM client not available - skipping test")
        print("   Set OPENAI_API_KEY or AZURE_OPENAI_KEY environment variable")
        return

    print(f"✅ LLM client initialized: {llm_extractor.model}")

    # Create test subtree
    test_subtree = create_test_subtree()
    print(f"📄 Test XML subtree: {test_subtree.path}")
    print(f"   Size: {test_subtree.size_bytes} bytes")
    print(f"   Content preview: {test_subtree.xml_content[:100]}...")

    # Extract facts
    try:
        print("\n🔍 Extracting facts with LLM...")
        result = await llm_extractor.extract_from_subtree(test_subtree)

        print(f"✅ Extraction completed!")
        print(f"   Facts found: {len(result.node_facts)}")
        print(f"   Confidence: {result.confidence_score:.2f}")
        print(f"   Processing time: {result.processing_time_ms}ms")
        print(f"   Tokens used: {result.tokens_used}")
        print(f"   Model: {result.model_used}")

        # Display extracted facts
        if result.node_facts:
            print("\n📋 Extracted Facts:")
            for i, fact in enumerate(result.node_facts, 1):
                print(f"   {i}. {fact['node_type']} (confidence: {fact.get('confidence', 'N/A')})")
                print(f"      Attributes: {fact.get('attributes', {})}")
                if fact.get('snippet'):
                    print(f"      Snippet: {fact['snippet'][:80]}...")
                print()
        else:
            print("⚠️  No facts extracted")

    except Exception as e:
        print(f"❌ Extraction failed: {e}")
        import traceback
        traceback.print_exc()


def test_llm_extraction_sync():
    """Synchronous wrapper for testing."""
    try:
        # Try to get existing event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create new loop for testing
            import threading
            result = None
            exception = None

            def run_test():
                nonlocal result, exception
                try:
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    result = new_loop.run_until_complete(test_llm_extraction())
                    new_loop.close()
                except Exception as e:
                    exception = e

            thread = threading.Thread(target=run_test)
            thread.start()
            thread.join()

            if exception:
                raise exception
            return result
        else:
            return loop.run_until_complete(test_llm_extraction())
    except RuntimeError:
        # No event loop
        return asyncio.run(test_llm_extraction())


if __name__ == "__main__":
    print("🚀 AssistedDiscovery LLM Extractor Test")
    print("=" * 50)

    # Check environment
    has_openai = bool(os.getenv('OPENAI_API_KEY'))
    has_azure = bool(os.getenv('AZURE_OPENAI_KEY'))

    print(f"Environment:")
    print(f"  OPENAI_API_KEY: {'✅' if has_openai else '❌'}")
    print(f"  AZURE_OPENAI_KEY: {'✅' if has_azure else '❌'}")

    if not (has_openai or has_azure):
        print("\n⚠️  No LLM API keys found. Set one of:")
        print("     export OPENAI_API_KEY='your-key'")
        print("     export AZURE_OPENAI_KEY='your-key'")
        print("     export AZURE_OPENAI_ENDPOINT='your-endpoint'")
        print("\n🏃 Running test anyway (will show graceful fallback)...")

    print("\n" + "=" * 50)
    test_llm_extraction_sync()
    print("=" * 50)
    print("✅ Test completed!")