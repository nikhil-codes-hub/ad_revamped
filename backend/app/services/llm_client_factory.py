"""
LLM Client Factory

Centralized factory for creating Azure OpenAI and OpenAI clients with support for:
- BDP (Azure AD) authentication
- API Key authentication
- Both async and sync clients
"""

from typing import Optional, Tuple
import structlog
from openai import AsyncAzureOpenAI, AzureOpenAI, AsyncOpenAI, OpenAI
import httpx

from app.core.config import settings
from app.services.bdp_authenticator import get_bdp_authenticator

logger = structlog.get_logger(__name__)


class LLMClientFactory:
    """Factory for creating LLM clients with unified authentication logic."""

    @staticmethod
    def create_async_client(
        timeout: float = 120.0,
        verify_ssl: bool = False
    ) -> Tuple[Optional[AsyncAzureOpenAI | AsyncOpenAI], str]:
        """
        Create an async LLM client based on configuration.

        Args:
            timeout: Request timeout in seconds (default: 120)
            verify_ssl: Whether to verify SSL certificates (default: False for corporate proxies)

        Returns:
            Tuple of (client, model_name) or (None, "") if initialization fails
        """
        try:
            if settings.LLM_PROVIDER == "azure":
                return LLMClientFactory._create_azure_async_client(timeout, verify_ssl)
            elif settings.OPENAI_API_KEY:
                return LLMClientFactory._create_openai_async_client()
            else:
                logger.error("❌ LLM INITIALIZATION FAILED: No API keys found!")
                logger.error("  Please set either:")
                logger.error("    - AZURE_AUTH_METHOD + credentials (for Azure)")
                logger.error("    - OPENAI_API_KEY (for OpenAI)")
                logger.warning("⚠️ LLM operations are DISABLED!")
                return None, ""

        except Exception as e:
            logger.error(f"❌ CRITICAL: Failed to initialize async LLM client: {type(e).__name__}: {str(e)}")
            logger.error(f"  Provider: {settings.LLM_PROVIDER}")
            logger.error(f"  Endpoint: {settings.AZURE_OPENAI_ENDPOINT if settings.LLM_PROVIDER == 'azure' else 'N/A'}")
            import traceback
            logger.error(f"  Traceback:\n{traceback.format_exc()}")
            return None, ""

    @staticmethod
    def create_sync_client(
        timeout: float = 60.0,
        verify_ssl: bool = False
    ) -> Tuple[Optional[AzureOpenAI | OpenAI], str]:
        """
        Create a sync LLM client based on configuration.

        Args:
            timeout: Request timeout in seconds (default: 60)
            verify_ssl: Whether to verify SSL certificates (default: False for corporate proxies)

        Returns:
            Tuple of (client, model_name) or (None, "") if initialization fails
        """
        try:
            if settings.LLM_PROVIDER == "azure":
                return LLMClientFactory._create_azure_sync_client(timeout, verify_ssl)
            elif settings.OPENAI_API_KEY:
                return LLMClientFactory._create_openai_sync_client()
            else:
                logger.error("❌ LLM INITIALIZATION FAILED: No API keys found!")
                logger.error("  Please set either:")
                logger.error("    - AZURE_AUTH_METHOD + credentials (for Azure)")
                logger.error("    - OPENAI_API_KEY (for OpenAI)")
                logger.warning("⚠️ LLM operations are DISABLED!")
                return None, ""

        except Exception as e:
            logger.error(f"❌ CRITICAL: Failed to initialize sync LLM client: {type(e).__name__}: {str(e)}")
            logger.error(f"  Provider: {settings.LLM_PROVIDER}")
            logger.error(f"  Endpoint: {settings.AZURE_OPENAI_ENDPOINT if settings.LLM_PROVIDER == 'azure' else 'N/A'}")
            import traceback
            logger.error(f"  Traceback:\n{traceback.format_exc()}")
            return None, ""

    @staticmethod
    def _create_azure_async_client(
        timeout: float,
        verify_ssl: bool
    ) -> Tuple[AsyncAzureOpenAI, str]:
        """Create an async Azure OpenAI client with BDP or API key authentication."""
        auth_method = getattr(settings, 'AZURE_AUTH_METHOD', 'api_key').lower()

        if auth_method == "bdp":
            # Use BDP (Azure AD) authentication
            logger.info("Initializing Azure OpenAI (async) client with BDP authentication...")
            logger.info(f"  Endpoint: {settings.AZURE_OPENAI_ENDPOINT}")
            logger.info(f"  API Version: {settings.AZURE_API_VERSION}")
            logger.info(f"  Model Deployment: {settings.MODEL_DEPLOYMENT_NAME}")
            logger.info(f"  Auth Method: BDP (Azure AD)")

            bdp_auth = get_bdp_authenticator()
            client = bdp_auth.create_async_client(
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                api_version=settings.AZURE_API_VERSION,
                timeout=timeout,
                verify_ssl=verify_ssl
            )
            model = settings.MODEL_DEPLOYMENT_NAME
            logger.info(f"✅ Async Azure OpenAI client initialized with BDP: {model}")
            return client, model

        elif auth_method == "api_key" and settings.AZURE_OPENAI_KEY:
            # Use API Key authentication (legacy/testing)
            logger.info("Initializing Azure OpenAI (async) client with API Key...")
            logger.info(f"  Endpoint: {settings.AZURE_OPENAI_ENDPOINT}")
            logger.info(f"  API Version: {settings.AZURE_API_VERSION}")
            logger.info(f"  Model Deployment: {settings.MODEL_DEPLOYMENT_NAME}")
            logger.info(f"  Auth Method: API Key")

            http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(timeout, connect=10.0),
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
                follow_redirects=True,
                verify=verify_ssl
            )

            client = AsyncAzureOpenAI(
                api_key=settings.AZURE_OPENAI_KEY,
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                api_version=settings.AZURE_API_VERSION,
                http_client=http_client
            )
            model = settings.MODEL_DEPLOYMENT_NAME
            logger.info(f"✅ Async Azure OpenAI client initialized with API Key: {model}")
            return client, model

        else:
            logger.error("❌ Azure authentication not configured!")
            logger.error(f"  Auth method: {auth_method}")
            logger.error("  Please set either:")
            logger.error("    - AZURE_AUTH_METHOD=bdp with AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET")
            logger.error("    - AZURE_AUTH_METHOD=api_key with AZURE_OPENAI_KEY")
            raise ValueError(f"Azure authentication not configured (method: {auth_method})")

    @staticmethod
    def _create_azure_sync_client(
        timeout: float,
        verify_ssl: bool
    ) -> Tuple[AzureOpenAI, str]:
        """Create a sync Azure OpenAI client with BDP or API key authentication."""
        auth_method = getattr(settings, 'AZURE_AUTH_METHOD', 'api_key').lower()

        if auth_method == "bdp":
            # Use BDP (Azure AD) authentication
            logger.info("Initializing Azure OpenAI (sync) client with BDP authentication...")
            logger.info(f"  Endpoint: {settings.AZURE_OPENAI_ENDPOINT}")
            logger.info(f"  API Version: {settings.AZURE_API_VERSION}")
            logger.info(f"  Model Deployment: {settings.MODEL_DEPLOYMENT_NAME}")
            logger.info(f"  Auth Method: BDP (Azure AD)")

            bdp_auth = get_bdp_authenticator()
            client = bdp_auth.create_sync_client(
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                api_version=settings.AZURE_API_VERSION,
                timeout=timeout,
                verify_ssl=verify_ssl
            )
            model = settings.MODEL_DEPLOYMENT_NAME
            logger.info(f"✅ Sync Azure OpenAI client initialized with BDP: {model}")
            return client, model

        elif auth_method == "api_key" and settings.AZURE_OPENAI_KEY:
            # Use API Key authentication (legacy/testing)
            logger.info("Initializing Azure OpenAI (sync) client with API Key...")
            logger.info(f"  Endpoint: {settings.AZURE_OPENAI_ENDPOINT}")
            logger.info(f"  API Version: {settings.AZURE_API_VERSION}")
            logger.info(f"  Model Deployment: {settings.MODEL_DEPLOYMENT_NAME}")
            logger.info(f"  Auth Method: API Key")

            http_client = httpx.Client(
                timeout=httpx.Timeout(timeout, connect=10.0),
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
                follow_redirects=True,
                verify=verify_ssl
            )

            client = AzureOpenAI(
                api_key=settings.AZURE_OPENAI_KEY,
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                api_version=settings.AZURE_API_VERSION,
                http_client=http_client
            )
            model = settings.MODEL_DEPLOYMENT_NAME
            logger.info(f"✅ Sync Azure OpenAI client initialized with API Key: {model}")
            return client, model

        else:
            logger.error("❌ Azure authentication not configured!")
            logger.error(f"  Auth method: {auth_method}")
            logger.error("  Please set either:")
            logger.error("    - AZURE_AUTH_METHOD=bdp with AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET")
            logger.error("    - AZURE_AUTH_METHOD=api_key with AZURE_OPENAI_KEY")
            raise ValueError(f"Azure authentication not configured (method: {auth_method})")

    @staticmethod
    def _create_openai_async_client() -> Tuple[AsyncOpenAI, str]:
        """Create an async OpenAI client."""
        logger.info("Initializing OpenAI (async) client...")
        logger.info(f"  Model: {settings.LLM_MODEL}")

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        model = settings.LLM_MODEL
        logger.info(f"✅ Async OpenAI client initialized: {model}")
        return client, model

    @staticmethod
    def _create_openai_sync_client() -> Tuple[OpenAI, str]:
        """Create a sync OpenAI client."""
        logger.info("Initializing OpenAI (sync) client...")
        logger.info(f"  Model: {settings.LLM_MODEL}")

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        model = settings.LLM_MODEL
        logger.info(f"✅ Sync OpenAI client initialized: {model}")
        return client, model
