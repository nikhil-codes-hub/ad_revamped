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

**CRITICAL VALIDATION RULES:**
1. **ALL** requirements must be satisfied for a match
2. If ANY required attribute is missing → is_match = false
3. If ANY required child type is missing → is_match = false
4. If node type doesn't match → is_match = false
5. Check EVERY requirement individually and report each finding
6. **IMPORTANT:** Use ONLY the EXACT attribute names listed in the pattern definition above
   - DO NOT invent, guess, or suggest alternative attribute names
   - DO NOT use semantic equivalents (e.g., if pattern says "id", don't say "PaxSegmentID")
   - Report missing attributes using the EXACT names from the pattern definition

**TASK:**
Perform STRICT validation and return a JSON object with:

{{
  "is_match": true/false,  // Only true if ALL requirements are met
  "confidence": 0.0-1.0,
  "summary": "Brief summary of verification (1-2 sentences)",
  "findings": [
    {{"aspect": "node_type", "expected": "...", "found": "...", "match": true/false}},
    {{"aspect": "required_attributes", "expected": "list of required attrs", "found": "list of found attrs", "match": true/false}},
    {{"aspect": "required_children", "expected": "list of required child types", "found": "list of found child types", "match": true/false}},
    {{"aspect": "child_count", "expected": "min/max if specified", "found": "actual count", "match": true/false}}
  ],
  "issues": ["List EVERY specific issue found using EXACT attribute/element names from pattern definition"],
  "recommendations": ["Specific suggestions to fix the XML to match the pattern"]
}}

**VALIDATION CHECKLIST:**
✓ Node type matches exactly
✓ EVERY required attribute is present
✓ EVERY required child type is present
✓ Child count meets min/max requirements (if specified)
✓ All data types and formats are correct

Return ONLY valid JSON, no additional text.

**REMEMBER:** Be STRICT. Even one missing required element means is_match = false.
"""


def get_verifier() -> PatternLLMVerifier:
    """Get a PatternLLMVerifier instance."""
    return PatternLLMVerifier()
