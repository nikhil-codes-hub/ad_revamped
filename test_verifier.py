"""Test script for pattern verifier."""
import sys
sys.path.insert(0, 'frontend/streamlit_ui/utils')
from pattern_llm_verifier import get_verifier

# Initialize verifier
verifier = get_verifier()
print("✅ Verifier initialized successfully")

# Test pattern prompt
pattern_prompt = """**STRICT PATTERN VALIDATION REQUIREMENTS:**

The XML MUST match ALL of the following requirements exactly:

1. **Node Type:** Must be exactly 'PaxSegment'

2. **Required Attributes (ALL must be present):**
   None specified

3. **Child Structure:** MUST have children
   **Required Child Types (ALL must be present):**
   - DatedMarketingSegmentRefId (REQUIRED)
   - PaxSegmentID (REQUIRED)

**Pattern Context:**
- Section: DataLists/PaxSegmentList
- Version: 21.3
- Description: Passenger segment with marketing segment reference

**IMPORTANT:** The XML must match ALL requirements listed above. If ANY required attribute or child type is missing, the verification should FAIL.
"""

# Test XML
test_xml = """<PaxSegment>
    <DatedMarketingSegmentRefId>seg-001</DatedMarketingSegmentRefId>
    <PaxSegmentID>paxseg-001</PaxSegmentID>
</PaxSegment>"""

print("\n🔄 Testing pattern verification...")
print(f"Pattern: {pattern_prompt[:100]}...")
print(f"XML: {test_xml[:100]}...")

try:
    result = verifier.verify_pattern(pattern_prompt, test_xml)
    print("\n✅ Verification completed successfully!")
    print(f"Result: {result}")
except Exception as e:
    print(f"\n❌ Verification failed: {str(e)}")
    import traceback
    traceback.print_exc()
