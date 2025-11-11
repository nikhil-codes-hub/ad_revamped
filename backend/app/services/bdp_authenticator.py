"""
BDP (Azure AD) Authentication for Azure OpenAI.

Provides ClientSecretCredential-based authentication for corporate Azure OpenAI endpoints.
Supports both synchronous and asynchronous Azure OpenAI clients.
"""

import logging
from typing import Callable, Optional
from azure.identity import ClientSecretCredential
from openai import AzureOpenAI, AsyncAzureOpenAI
import httpx

logger = logging.getLogger(__name__)


class BdpAuthenticator:
    """
    BDP (Azure AD) authentication provider for Azure OpenAI.

    Uses Azure Active Directory credentials (tenant_id, client_id, client_secret)
    instead of API keys for corporate authentication requirements.
    """

    def __init__(self,
                 tenant_id: Optional[str] = None,
                 client_id: Optional[str] = None,
                 client_secret: Optional[str] = None):
        """
        Initialize BDP authenticator.

        Args:
            tenant_id: Azure AD tenant ID (defaults to settings.AZURE_TENANT_ID from .env)
            client_id: Azure AD client ID (defaults to settings.AZURE_CLIENT_ID from .env)
            client_secret: Azure AD client secret (defaults to settings.AZURE_CLIENT_SECRET from .env)
        """
        # Import settings here to avoid circular imports
        from app.core.config import settings

        self.tenant_id = tenant_id or settings.AZURE_TENANT_ID
        self.client_id = client_id or settings.AZURE_CLIENT_ID
        self.client_secret = client_secret or settings.AZURE_CLIENT_SECRET

        # Validate credentials
        missing_creds = []
        if not self.tenant_id:
            missing_creds.append("AZURE_TENANT_ID")
        if not self.client_id:
            missing_creds.append("AZURE_CLIENT_ID")
        if not self.client_secret:
            missing_creds.append("AZURE_CLIENT_SECRET")

        if missing_creds:
            error_msg = (
                f"BDP authentication requires the following environment variables in .env file: "
                f"{', '.join(missing_creds)}. "
                f"Please ensure your .env file is in the project root and contains these values."
            )
            logger.error(f"❌ {error_msg}")
            logger.error(f"   Current .env location checked: backend/.env, ../.env, ../../.env, ../../../.env")
            raise ValueError(error_msg)

        # Create credential object
        self.credential = ClientSecretCredential(
            tenant_id=self.tenant_id,
            client_id=self.client_id,
            client_secret=self.client_secret
        )

        logger.info("✅ BDP authenticator initialized successfully")
        logger.info(f"   Tenant ID: {self.tenant_id}")
        logger.info(f"   Client ID: {self.client_id[:8] if len(self.client_id) >= 8 else self.client_id}...")

    def get_token_provider(self) -> Callable[[], str]:
        """
        Create an Azure AD token provider for authentication.

        Returns a function that provides fresh tokens when needed.
        This function is called automatically by Azure OpenAI client to get tokens.

        Returns:
            Callable that returns fresh access tokens
        """
        def token_provider():
            """Get a fresh token from Azure AD."""
            try:
                token = self.credential.get_token("https://cognitiveservices.azure.com/.default")
                return token.token
            except Exception as e:
                logger.error(f"❌ Failed to get BDP token: {e}")
                raise

        return token_provider

    def create_async_client(self,
                           azure_endpoint: str,
                           api_version: str,
                           timeout: float = 120.0,
                           verify_ssl: bool = False) -> AsyncAzureOpenAI:
        """
        Create an async Azure OpenAI client with BDP authentication.

        Args:
            azure_endpoint: Azure OpenAI endpoint URL
            api_version: Azure OpenAI API version
            timeout: Request timeout in seconds (default: 120)
            verify_ssl: Whether to verify SSL certificates (default: False for corporate proxies)

        Returns:
            AsyncAzureOpenAI client instance
        """
        logger.info("Creating async Azure OpenAI client with BDP auth...")
        logger.info(f"   Endpoint: {azure_endpoint}")
        logger.info(f"   API Version: {api_version}")

        # Create HTTP client with custom settings
        http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            follow_redirects=True,
            verify=verify_ssl
        )

        client = AsyncAzureOpenAI(
            azure_endpoint=azure_endpoint,
            azure_ad_token_provider=self.get_token_provider(),
            api_version=api_version,
            http_client=http_client
        )

        logger.info("✅ Async Azure OpenAI client created with BDP authentication")
        return client

    def create_sync_client(self,
                          azure_endpoint: str,
                          api_version: str,
                          timeout: float = 120.0,
                          verify_ssl: bool = False) -> AzureOpenAI:
        """
        Create a sync Azure OpenAI client with BDP authentication.

        Args:
            azure_endpoint: Azure OpenAI endpoint URL
            api_version: Azure OpenAI API version
            timeout: Request timeout in seconds (default: 120)
            verify_ssl: Whether to verify SSL certificates (default: False for corporate proxies)

        Returns:
            AzureOpenAI client instance
        """
        logger.info("Creating sync Azure OpenAI client with BDP auth...")
        logger.info(f"   Endpoint: {azure_endpoint}")
        logger.info(f"   API Version: {api_version}")

        # Create HTTP client with custom settings
        http_client = httpx.Client(
            timeout=httpx.Timeout(timeout, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            follow_redirects=True,
            verify=verify_ssl
        )

        client = AzureOpenAI(
            azure_endpoint=azure_endpoint,
            azure_ad_token_provider=self.get_token_provider(),
            api_version=api_version,
            http_client=http_client
        )

        logger.info("✅ Sync Azure OpenAI client created with BDP authentication")
        return client


def get_bdp_authenticator(tenant_id: Optional[str] = None,
                          client_id: Optional[str] = None,
                          client_secret: Optional[str] = None) -> BdpAuthenticator:
    """
    Get a BDP authenticator instance.

    Args:
        tenant_id: Azure AD tenant ID (optional, reads from env)
        client_id: Azure AD client ID (optional, reads from env)
        client_secret: Azure AD client secret (optional, reads from env)

    Returns:
        BdpAuthenticator instance
    """
    return BdpAuthenticator(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret
    )
