# LLM Pattern Verification Guide

## Overview

AI-powered pattern verification using Azure OpenAI to validate if XML samples match pattern definitions.

## How It Works

```
Pattern Definition + Test XML → Azure OpenAI → Structured Verification Results
```

The LLM analyzes:
- **Node type/name** - Does the XML element match expected type?
- **Required attributes** - Are all required attributes present?
- **Child structure** - Do children match expectations?
- **Data formats** - Are values in correct format?

## Usage

### 1. Export Patterns to Workspace

```
🎨 Pattern Manager → 📤 Export Tab
  └─ Select backend patterns
  └─ Export to workspace
```

### 2. Verify Pattern

```
🎨 Pattern Manager → ✅ Verify Tab
  └─ Select pattern from workspace
  └─ Paste sample XML
  └─ Click "🚀 Verify Pattern"
  └─ AI analyzes and returns results
```

## Example

### Pattern Definition (from Export):
```
Validate that the XML node matches:
- Node Type: PaxSegment
- Must Have Attributes: PaxSegmentID, DepartureCode, ArrivalCode
- Must Have Children: Yes
- Expected Child Types: Cabin, ClassOfService
```

### Test XML:
```xml
<PaxSegment PaxSegmentID="SEG1" DepartureCode="SIN" ArrivalCode="LHR">
  <Cabin>Y</Cabin>
  <ClassOfService>Economy</ClassOfService>
</PaxSegment>
```

### AI Verification Results:

**Match Status**: ✅ **MATCH**
**Confidence**: 95%
**Tokens Used**: 234

**Summary:**
✅ This PaxSegment node perfectly matches the expected pattern. All required attributes are present and child structure is correct.

**Detailed Findings:**
- ✅ **Node Type**: Expected `PaxSegment`, Found `PaxSegment` ✓
- ✅ **Attributes**: All required attributes present (PaxSegmentID, DepartureCode, ArrivalCode) ✓
- ✅ **Children**: Expected child types `Cabin, ClassOfService` found ✓

## Verification Response Format

```json
{
  "is_match": true,
  "confidence": 0.95,
  "summary": "Pattern matches perfectly",
  "findings": [
    {
      "aspect": "node_type",
      "expected": "PaxSegment",
      "found": "PaxSegment",
      "match": true
    },
    {
      "aspect": "attributes",
      "expected": "PaxSegmentID, DepartureCode, ArrivalCode",
      "found": "PaxSegmentID, DepartureCode, ArrivalCode",
      "match": true
    }
  ],
  "issues": [],
  "recommendations": [],
  "tokens_used": 234
}
```

## When Patterns Don't Match

If XML doesn't match the pattern:

**Match Status**: ❌ **NO MATCH**
**Confidence**: 40%

**Summary:**
⚠️ Missing required attribute 'PaxSegmentID'. Found 'SegmentID' instead which doesn't match the pattern requirement.

**Issues Found:**
- ⚠️ Required attribute 'PaxSegmentID' not found
- ⚠️ Unexpected attribute 'SegmentID' present

**Recommendations:**
- 💡 Rename 'SegmentID' to 'PaxSegmentID' to match pattern
- 💡 Verify the XML schema version matches the pattern version

## Configuration

LLM verification uses environment variables from `.env`:

```env
# Azure OpenAI Configuration
AZURE_OPENAI_KEY=your-key-here
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_API_VERSION=2025-01-01-preview
MODEL_DEPLOYMENT_NAME=gpt-4o
LLM_TEMPERATURE=0.1
```

## Token Usage

Each verification consumes tokens:
- **Simple patterns**: ~150-300 tokens
- **Complex patterns**: ~300-500 tokens
- **Very detailed patterns**: ~500-1000 tokens

Token usage is displayed after each verification.

## Best Practices

### 1. Write Clear Pattern Definitions
Good:
```
- Node Type: PaxSegment
- Must Have Attributes: PaxSegmentID, DepartureCode, ArrivalCode
- Must Have Children: Cabin, ClassOfService
```

Bad:
```
- Check if PaxSegment has stuff
```

### 2. Use Representative XML Samples
- Include all required attributes
- Include typical child elements
- Use realistic data values

### 3. Verify Critical Patterns
Focus verification on:
- High-impact patterns (used frequently)
- Complex patterns (many rules)
- New patterns (never tested)
- Edge cases (unusual structures)

### 4. Iterate Based on Results
If verification fails:
1. Check if XML is correct (maybe pattern is wrong)
2. Check if pattern is too strict
3. Update pattern definition or XML as needed
4. Re-verify until confident

## Error Handling

### "LLM verifier not available"
- Install openai package: `pip install openai`
- Restart Streamlit

### "Verification failed: API key error"
- Check `.env` has correct `AZURE_OPENAI_KEY`
- Verify key is active in Azure portal

### "Timeout error"
- XML might be too large
- Try smaller XML snippet
- Check network connection

## Implementation Details

**File**: `frontend/streamlit_ui/utils/pattern_llm_verifier.py`

```python
class PatternLLMVerifier:
    """LLM-based pattern verification using Azure OpenAI."""

    def verify_pattern(self, pattern_prompt: str, test_xml: str) -> Dict[str, Any]:
        # Builds prompt
        # Calls Azure OpenAI
        # Returns structured results
```

**Integration**: `frontend/streamlit_ui/pattern_manager.py`
- `_render_verify_tab()` - UI for verification
- `_process_verification()` - Calls LLM verifier
- `_display_verification_results()` - Shows results

## Future Enhancements

🚧 **Coming Soon:**
- Batch verification (multiple patterns at once)
- Verification history/logging
- Pattern quality scoring
- Auto-fix suggestions
- Regex pattern testing
- XPath validation
