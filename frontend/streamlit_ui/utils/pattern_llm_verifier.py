"""
LLM-based Pattern Verification

Uses Azure OpenAI to verify if XML samples match pattern definitions.
"""

import json
import os
from typing import Dict, Any, Optional
from pathlib import Path
from openai import AzureOpenAI
from dotenv import load_dotenv
import httpx

# Load environment variables
env_path = Path(__file__).parent.parent.parent.parent / ".env"
load_dotenv(env_path)


class PatternLLMVerifier:
    """LLM-based pattern verification using Azure OpenAI."""

    def __init__(self):
        """Initialize Azure OpenAI client."""
        self.client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_KEY"),
            api_version=os.getenv("AZURE_API_VERSION", "2025-01-01-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            http_client=httpx.Client(verify=False)
        )
        self.model = os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-4o")
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.1"))

    def verify_pattern(self, pattern_prompt: str, test_xml: str) -> Dict[str, Any]:
        """
        Verify if test XML matches the pattern.

        Args:
            pattern_prompt: Pattern validation rules
            test_xml: XML snippet to test

        Returns:
            Dict with verification results
        """
        prompt = self._build_verification_prompt(pattern_prompt, test_xml)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an XML pattern validation expert. Analyze XML against patterns and return structured JSON results."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=self.temperature,
                max_tokens=1000,
                response_format={"type": "json_object"}
            )

            result_text = response.choices[0].message.content
            result = json.loads(result_text)

            # Add token usage
            result['tokens_used'] = response.usage.total_tokens
            result['tokens_prompt'] = response.usage.prompt_tokens
            result['tokens_completion'] = response.usage.completion_tokens

            return result

        except Exception as e:
            return {
                'is_match': False,
                'confidence': 0.0,
                'summary': f"Verification failed: {str(e)}",
                'findings': [],
                'error': str(e)
            }

    def _build_verification_prompt(self, pattern_prompt: str, test_xml: str) -> str:
        """Build the LLM prompt for verification."""
        return f"""Verify if the following XML matches the pattern definition with STRICT validation.

**PATTERN DEFINITION:**
{pattern_prompt}

**TEST XML:**
```xml
{test_xml}
```

**CRITICAL TERMINOLOGY CLARIFICATION:**
⚠️ In this pattern definition, "Required Attributes" actually means "Required Child Elements"
- When the pattern says "Required Attributes: PaxID, PTC", it means the XML must have child elements <PaxID> and <PTC>
- These are NOT XML attributes (like @PaxID="value" in the opening tag)
- These ARE child elements (like <PaxID>value</PaxID> inside the element)
- This is a naming convention used internally - treat all "required attributes" as child elements

**CRITICAL VALIDATION RULES:**
1. **ONLY** check requirements EXPLICITLY stated in the pattern definition above
2. DO NOT infer or assume additional requirements beyond what is explicitly listed
3. If a child element is listed as required (e.g., <Desc>), just verify that element EXISTS
4. DO NOT validate the internal structure of child elements UNLESS the pattern explicitly specifies what should be inside them
5. If ANY explicitly required element is missing → is_match = false
6. If node type doesn't match → is_match = false
7. Check EVERY EXPLICITLY STATED requirement and report findings
8. **IMPORTANT:** Use ONLY the EXACT element names listed in the pattern definition above
   - DO NOT invent, guess, or suggest alternative element names
   - DO NOT use semantic equivalents (e.g., if pattern says "id", don't say "PaxSegmentID")
   - Report missing elements using the EXACT names from the pattern definition

**Example:** If pattern says "Each Disclosure must have: <Desc>, <DisclosureID>", then:
- ✓ Check that Disclosure has <Desc> element (exists)
- ✓ Check that Disclosure has <DisclosureID> element (exists)
- ✗ DO NOT check what's inside <Desc> unless pattern explicitly defines it

**TASK:**
Perform STRICT validation and return a JSON object with:

{{
  "is_match": true/false,  // Only true if ALL requirements are met
  "confidence": 0.0-1.0,
  "summary": "Brief summary of verification (1-2 sentences)",
  "findings": [
    {{"aspect": "node_type", "expected": "...", "found": "...", "match": true/false}},
    {{"aspect": "required_child_elements", "expected": "list of required child elements", "found": "list of found child elements", "match": true/false}},
    {{"aspect": "required_children", "expected": "list of required child types", "found": "list of found child types", "match": true/false}},
    {{"aspect": "child_count", "expected": "min/max if specified", "found": "actual count", "match": true/false}}
  ],
  "issues": ["List EVERY specific issue found using EXACT element names from pattern definition"],
  "recommendations": ["Specific suggestions to fix the XML to match the pattern"]
}}

**VALIDATION CHECKLIST:**
✓ Node type matches exactly
✓ EVERY required child element is present (remember: pattern "attributes" = XML child elements)
✓ EVERY required child type is present
✓ Child count meets min/max requirements (if specified)
✓ All data types and formats are correct

Return ONLY valid JSON, no additional text.

**REMEMBER:** Be STRICT. Even one missing required element means is_match = false.
**REMEMBER:** "Required Attributes" in the pattern = "Required Child Elements" in the XML!
"""


def get_verifier() -> PatternLLMVerifier:
    """Get a PatternLLMVerifier instance."""
    return PatternLLMVerifier()
