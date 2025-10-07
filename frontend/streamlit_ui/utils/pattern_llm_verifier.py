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
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
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
        return f"""Verify if the following XML matches the pattern definition.

**PATTERN DEFINITION:**
{pattern_prompt}

**TEST XML:**
```xml
{test_xml}
```

**TASK:**
Analyze if the XML matches the pattern requirements. Return a JSON object with:

{{
  "is_match": true/false,
  "confidence": 0.0-1.0,
  "summary": "Brief summary of verification (1-2 sentences)",
  "findings": [
    {{"aspect": "node_type", "expected": "...", "found": "...", "match": true/false}},
    {{"aspect": "attributes", "expected": "...", "found": "...", "match": true/false}},
    {{"aspect": "children", "expected": "...", "found": "...", "match": true/false}}
  ],
  "issues": ["List of specific issues found, if any"],
  "recommendations": ["Suggestions if pattern doesn't match"]
}}

Focus on:
1. Node type/name matching
2. Required attributes present
3. Child structure (if specified)
4. Data types and formats

Return ONLY valid JSON, no additional text."""


def get_verifier() -> PatternLLMVerifier:
    """Get a PatternLLMVerifier instance."""
    return PatternLLMVerifier()
