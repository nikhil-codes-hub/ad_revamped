"""
LLM-based NodeFacts extractor for AssistedDiscovery.

Intelligent extraction of structured facts from NDC XML using Large Language Models.
Replaces brittle template-based extraction with adaptive AI understanding.
"""

import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from datetime import datetime
import openai
from openai import AsyncOpenAI, AsyncAzureOpenAI
from lxml import etree

from app.core.config import settings
from app.services.xml_parser import XmlSubtree
from app.services.pii_masking import pii_engine
from app.services.business_intelligence import get_bi_enricher
from app.prompts import get_container_prompt, get_item_prompt, get_system_prompt

logger = logging.getLogger(__name__)


@dataclass
class LLMExtractionResult:
    """Result from LLM extraction."""
    node_facts: List[Dict[str, Any]]
    confidence_score: float
    processing_time_ms: int
    tokens_used: int
    model_used: str
    extraction_method: str = "llm"


class LLMNodeFactsExtractor:
    """LLM-powered NodeFacts extractor for NDC XML."""

    def __init__(self):
        """Initialize LLM extractor."""
        self.client = None
        self.model = settings.LLM_MODEL
        self.max_tokens = settings.MAX_TOKENS_PER_REQUEST
        self.temperature = settings.LLM_TEMPERATURE
        self.provider = settings.LLM_PROVIDER
        self._init_client()

    def _init_client(self):
        """Initialize LLM client (Azure OpenAI or OpenAI)."""
        try:
            if self.provider == "azure" and settings.AZURE_OPENAI_KEY:
                # Initialize Azure OpenAI client
                logger.info(f"Initializing Azure OpenAI client...")
                logger.info(f"  Endpoint: {settings.AZURE_OPENAI_ENDPOINT}")
                logger.info(f"  API Version: {settings.AZURE_API_VERSION}")
                logger.info(f"  Model Deployment: {settings.MODEL_DEPLOYMENT_NAME}")

                self.client = AsyncAzureOpenAI(
                    api_key=settings.AZURE_OPENAI_KEY,
                    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                    api_version=settings.AZURE_API_VERSION
                )
                self.model = settings.MODEL_DEPLOYMENT_NAME
                logger.info(f"✅ LLM extractor initialized successfully with Azure OpenAI: {self.model}")

            elif settings.OPENAI_API_KEY:
                # Fallback to OpenAI
                logger.info(f"Initializing OpenAI client...")
                logger.info(f"  Model: {settings.LLM_MODEL}")

                self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                self.model = settings.LLM_MODEL
                logger.info(f"✅ LLM extractor initialized successfully with OpenAI: {self.model}")

            else:
                logger.error("❌ LLM INITIALIZATION FAILED: No API keys found!")
                logger.error("  Please set either:")
                logger.error("    - AZURE_OPENAI_KEY + AZURE_OPENAI_ENDPOINT (for Azure)")
                logger.error("    - OPENAI_API_KEY (for OpenAI)")
                logger.warning("⚠️ LLM extraction is DISABLED - Discovery will fail!")

        except Exception as e:
            logger.error(f"❌ CRITICAL: Failed to initialize LLM client: {type(e).__name__}: {str(e)}")
            logger.error(f"  Provider: {self.provider}")
            logger.error(f"  Endpoint: {settings.AZURE_OPENAI_ENDPOINT if self.provider == 'azure' else 'N/A'}")
            logger.error(f"  This will cause Discovery to fail!")
            import traceback
            logger.error(f"  Traceback:\n{traceback.format_exc()}")

    def _analyze_xml_structure(self, xml_content: str, section_path: str) -> Dict[str, Any]:
        """
        Analyze XML structure to determine if it's a container or item element.

        Returns dict with:
        - is_container: bool (True if has repeating children)
        - element_name: str (name of the element)
        - child_tags: Dict[str, int] (count of each child tag)
        - total_children: int
        - max_repetition: int (max count of any single child tag)
        """
        try:
            root = etree.fromstring(xml_content.encode('utf-8'))
            element_name = section_path.split('/')[-1]

            # Count direct children by tag name
            child_tags = {}
            for child in root:
                # Extract local name without namespace
                tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                child_tags[tag] = child_tags.get(tag, 0) + 1

            max_repetition = max(child_tags.values()) if child_tags else 0
            total_children = len(root)

            # Determine if this is a container
            # Container if: has repeating children OR element name suggests plural
            is_container = (
                max_repetition > 1 or  # Has repeating child elements
                (element_name.endswith('List') and total_children > 0) or
                (element_name.endswith('s') and total_children > 0 and max_repetition == total_children)
            )

            result = {
                'is_container': is_container,
                'element_name': element_name,
                'child_tags': child_tags,
                'total_children': total_children,
                'max_repetition': max_repetition,
                'repeating_tag': max(child_tags.items(), key=lambda x: x[1])[0] if child_tags else None
            }

            logger.info(f"Structure analysis for {element_name}: "
                       f"container={is_container}, children={total_children}, "
                       f"max_repetition={max_repetition}, tags={list(child_tags.keys())}")

            return result

        except Exception as e:
            logger.warning(f"Failed to analyze XML structure: {e}")
            # Fallback to item extraction
            return {
                'is_container': False,
                'element_name': section_path.split('/')[-1],
                'child_tags': {},
                'total_children': 0,
                'max_repetition': 0,
                'repeating_tag': None
            }

    def _create_extraction_prompt(self, xml_content: str, section_path: str) -> str:
        """
        Create prompt for LLM extraction.
        Delegates to container or item prompt based on structure analysis.
        """
        structure = self._analyze_xml_structure(xml_content, section_path)

        if structure['is_container']:
            return self._create_container_extraction_prompt(xml_content, section_path, structure)
        else:
            return self._create_item_extraction_prompt(xml_content, section_path)

    def _create_container_extraction_prompt(self, xml_content: str, section_path: str,
                                           structure: Dict[str, Any]) -> str:
        """Create prompt for extracting container/collection elements."""
        return get_container_prompt(
            xml_content=xml_content,
            section_path=section_path,
            element_name=structure['element_name'],
            child_count=structure['total_children'],
            repeating_tag=structure['repeating_tag'],
            max_repetition=structure['max_repetition']
        )

    def _create_item_extraction_prompt(self, xml_content: str, section_path: str) -> str:
        """Create prompt for extracting individual item elements."""
        return get_item_prompt(xml_content=xml_content, section_path=section_path)

    async def _call_llm(self, prompt: str) -> Dict[str, Any]:
        """Call LLM API for extraction."""
        if not self.client:
            error_msg = "LLM client not initialized - check API keys in .env file"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)

        start_time = datetime.now()

        try:
            logger.info(f"Calling LLM API (model: {self.model}, max_tokens: {self.max_tokens})...")

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": get_system_prompt()
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )

            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

            content = response.choices[0].message.content
            logger.info(f"✅ LLM API call successful ({len(content)} chars, {processing_time}ms)")
            logger.debug(f"   Response preview: {content[:200]}...")

            return {
                "content": content,
                "tokens_used": response.usage.total_tokens,
                "processing_time_ms": processing_time,
                "model": response.model
            }

        except openai.AuthenticationError as e:
            logger.error(f"❌ LLM AUTHENTICATION FAILED: Invalid API key")
            logger.error(f"   Provider: {self.provider}")
            logger.error(f"   Error: {str(e)}")
            raise ValueError(f"LLM Authentication Failed: Check your API keys in .env file")

        except openai.RateLimitError as e:
            logger.error(f"❌ LLM RATE LIMIT EXCEEDED")
            logger.error(f"   Error: {str(e)}")
            raise ValueError(f"LLM Rate Limit Exceeded: Please try again later")

        except openai.APIConnectionError as e:
            logger.error(f"❌ LLM CONNECTION ERROR: Cannot reach API endpoint")
            logger.error(f"   Endpoint: {settings.AZURE_OPENAI_ENDPOINT if self.provider == 'azure' else 'OpenAI'}")
            logger.error(f"   Error: {str(e)}")
            raise ValueError(f"LLM Connection Error: Check network and endpoint configuration")

        except openai.APITimeoutError as e:
            logger.error(f"❌ LLM TIMEOUT: Request took too long")
            logger.error(f"   Error: {str(e)}")
            raise ValueError(f"LLM Timeout: Request took too long, try with smaller XML")

        except Exception as e:
            logger.error(f"❌ LLM API CALL FAILED: {type(e).__name__}: {str(e)}")
            logger.error(f"   Model: {self.model}")
            logger.error(f"   Provider: {self.provider}")
            import traceback
            logger.error(f"   Traceback:\n{traceback.format_exc()}")
            raise ValueError(f"LLM API Error: {type(e).__name__}: {str(e)}")

    def _parse_llm_response(self, llm_response: str) -> List[Dict[str, Any]]:
        """Parse and validate LLM response."""
        try:
            response_content = llm_response.strip()

            # Handle empty or invalid response
            if not response_content:
                logger.warning("Empty LLM response received")
                return []

            logger.info(f"Parsing LLM response, first 200 chars: {response_content[:200]}...")

            # Try to extract JSON from markdown code blocks if present
            if '```json' in response_content:
                start = response_content.find('```json') + 7
                end = response_content.find('```', start)
                if end != -1:
                    response_content = response_content[start:end].strip()

            # Try direct JSON parsing
            facts = []
            try:
                # Handle both direct JSON array and wrapped JSON object
                if response_content.startswith('['):
                    facts = json.loads(response_content)
                elif response_content.startswith('{'):
                    parsed = json.loads(response_content)
                    if isinstance(parsed, dict):
                        # Look for facts in common keys
                        facts = parsed.get('facts', parsed.get('results', parsed.get('node_facts', [])))
                    else:
                        facts = parsed
                else:
                    # Try to find JSON array in the response
                    start_bracket = response_content.find('[')
                    end_bracket = response_content.rfind(']')
                    if start_bracket != -1 and end_bracket != -1:
                        json_content = response_content[start_bracket:end_bracket+1]
                        facts = json.loads(json_content)
                    else:
                        logger.warning(f"No JSON array found in response: {response_content[:100]}...")
                        return []

            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing failed: {e}")
                logger.debug(f"Content that failed: {response_content[:200]}...")
                return []

            if not isinstance(facts, list):
                logger.warning(f"LLM returned non-list response: {type(facts)}")
                return []

            # Validate and clean each fact
            validated_facts = []
            logger.info(f"Validating {len(facts)} raw facts from LLM")
            for i, fact in enumerate(facts):
                if self._validate_fact(fact):
                    cleaned = self._clean_fact(fact)
                    validated_facts.append(cleaned)
                    logger.info(f"Fact {i+1} validated: {fact.get('node_type', 'Unknown')}")
                else:
                    logger.warning(f"Invalid fact {i+1} structure: {fact}")

            logger.info(f"Final validated facts: {len(validated_facts)}")
            return validated_facts

        except Exception as e:
            logger.error(f"Error processing LLM response: {e}")
            logger.debug(f"Raw response: {llm_response}")
            return []

    def _validate_fact(self, fact: Dict[str, Any]) -> bool:
        """Validate fact structure."""
        required_fields = ['node_type']
        return (
            isinstance(fact, dict) and
            all(field in fact for field in required_fields) and
            isinstance(fact.get('attributes', {}), dict)
        )

    def _clean_fact(self, fact: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and standardize fact structure with BI enrichment."""
        children = fact.get('children', [])

        # Handle two types of children:
        # 1. Simple list of child element names (old format): ["PTC", "Birthdate", "Individual"]
        # 2. Nested objects with full child data (new container format): [{"node_type": "BaggageAllowance", ...}]
        cleaned_children = []
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    # Nested child object - clean it recursively
                    cleaned_child = {
                        'node_type': str(child.get('node_type', 'Unknown')),
                        'ordinal': int(child.get('ordinal', child.get('node_ordinal', 1))),
                        'attributes': child.get('attributes', {}),
                        'references': child.get('references', {}),  # NEW: references field
                        'snippet': child.get('snippet', ''),
                        'confidence': float(child.get('confidence', 0.8))
                    }
                    # Apply PII masking to child attributes
                    if settings.PII_MASKING_ENABLED:
                        cleaned_child['attributes'] = pii_engine.mask_dictionary(cleaned_child['attributes'])
                    cleaned_children.append(cleaned_child)
                else:
                    # Simple string - keep as is
                    cleaned_children.append(child)

        cleaned = {
            'node_type': str(fact['node_type']),
            'node_ordinal': int(fact.get('node_ordinal', 1)),
            'attributes': fact.get('attributes', {}),
            'children': cleaned_children,
            'refs': fact.get('refs', {}),
            'snippet': fact.get('snippet', ''),
            'confidence': float(fact.get('confidence', 0.8)),
            # NEW: Business intelligence fields
            'business_intelligence': fact.get('business_intelligence', {}),
            'relationships': fact.get('relationships', []),
            'cross_references': fact.get('cross_references', {})
        }

        # Apply PII masking to parent attributes
        if settings.PII_MASKING_ENABLED:
            cleaned['attributes'] = pii_engine.mask_dictionary(cleaned['attributes'])

        # Apply business intelligence enrichment
        bi_enricher = get_bi_enricher()
        cleaned = bi_enricher.enrich_fact(cleaned)

        return cleaned

    async def extract_from_subtree(self, subtree: XmlSubtree,
                                 context: Optional[Dict[str, Any]] = None) -> LLMExtractionResult:
        """
        Extract NodeFacts from XML subtree using LLM.

        Args:
            subtree: XML subtree to extract facts from
            context: Additional context (run info, version, etc.)

        Returns:
            LLMExtractionResult with extracted facts and metadata
        """
        logger.info(f"LLM extraction from subtree: {subtree.path}")

        if not self.client:
            logger.error("LLM client not available - falling back to empty result")
            return LLMExtractionResult(
                node_facts=[],
                confidence_score=0.0,
                processing_time_ms=0,
                tokens_used=0,
                model_used="none",
                extraction_method="llm_unavailable"
            )

        start_time = datetime.now()

        try:
            # Create extraction prompt
            prompt = self._create_extraction_prompt(subtree.xml_content, subtree.path)

            # Call LLM
            llm_response = await self._call_llm(prompt)

            # Parse response
            node_facts = self._parse_llm_response(llm_response["content"])

            # Calculate confidence score
            confidence_scores = [fact.get('confidence', 0.8) for fact in node_facts]
            avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0

            total_time = int((datetime.now() - start_time).total_seconds() * 1000)

            logger.info(f"LLM extracted {len(node_facts)} facts from {subtree.path} "
                       f"(confidence: {avg_confidence:.2f}, time: {total_time}ms)")

            return LLMExtractionResult(
                node_facts=node_facts,
                confidence_score=avg_confidence,
                processing_time_ms=total_time,
                tokens_used=llm_response["tokens_used"],
                model_used=llm_response["model"],
                extraction_method="llm"
            )

        except ValueError as e:
            # These are our custom error messages - re-raise them
            logger.error(f"❌ LLM extraction failed for {subtree.path}: {str(e)}")
            raise

        except Exception as e:
            logger.error(f"❌ UNEXPECTED ERROR in LLM extraction for {subtree.path}")
            logger.error(f"   Error type: {type(e).__name__}")
            logger.error(f"   Error message: {str(e)}")
            import traceback
            logger.error(f"   Traceback:\n{traceback.format_exc()}")

            raise ValueError(f"LLM Extraction Error: {type(e).__name__}: {str(e)}")

    def extract_from_subtree_sync(self, subtree: XmlSubtree,
                                context: Optional[Dict[str, Any]] = None) -> LLMExtractionResult:
        """Synchronous wrapper for extract_from_subtree."""
        try:
            # Try to get the current running loop
            loop = asyncio.get_running_loop()
            # If we're in a running loop, we need to create a task
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(self._run_in_new_loop, subtree, context)
                return future.result()

        except RuntimeError:
            # No event loop running, create new one
            return asyncio.run(self.extract_from_subtree(subtree, context))

    def _run_in_new_loop(self, subtree: XmlSubtree, context: Optional[Dict[str, Any]] = None) -> LLMExtractionResult:
        """Run extraction in a new event loop."""
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            return new_loop.run_until_complete(self.extract_from_subtree(subtree, context))
        finally:
            new_loop.close()

    async def generate_explanation_async(self, prompt: str) -> str:
        """
        Generate a text explanation using LLM.

        Args:
            prompt: The prompt to send to the LLM

        Returns:
            The LLM's text response
        """
        if not self.client:
            raise ValueError("LLM client not initialized")

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,  # Lower temperature for more consistent explanations
                max_tokens=300  # Limit to keep explanations concise
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"LLM explanation generation failed: {e}")
            raise

    def generate_explanation(self, prompt: str) -> str:
        """Synchronous wrapper for generate_explanation_async."""
        try:
            # Try to get the current running loop
            loop = asyncio.get_running_loop()
            # If we're in a running loop, we need to create a task
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(self._run_explanation_in_new_loop, prompt)
                return future.result()

        except RuntimeError:
            # No event loop running, create new one
            return asyncio.run(self.generate_explanation_async(prompt))

    def _run_explanation_in_new_loop(self, prompt: str) -> str:
        """Run explanation generation in a new event loop."""
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            return new_loop.run_until_complete(self.generate_explanation_async(prompt))
        finally:
            new_loop.close()


# Global instance
llm_extractor = LLMNodeFactsExtractor()


def get_llm_extractor() -> LLMNodeFactsExtractor:
    """Get LLM extractor instance."""
    return llm_extractor