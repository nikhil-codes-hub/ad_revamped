"""
LLM Configuration endpoints for AssistedDiscovery.

Allows reading and updating LLM provider configuration in .env file.
"""

import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()
logger = logging.getLogger(__name__)


class LLMConfig(BaseModel):
    """LLM Configuration model."""
    provider: str = Field(default="azure", description="LLM provider: azure, openai, gemini")

    # Azure OpenAI
    azure_openai_endpoint: Optional[str] = Field(default=None, description="Azure OpenAI endpoint")
    azure_openai_key: Optional[str] = Field(default=None, description="Azure OpenAI API key")
    azure_api_version: Optional[str] = Field(default="2025-01-01-preview", description="Azure API version")
    model_deployment_name: Optional[str] = Field(default="gpt-4o", description="Azure model deployment")
    fallback_model_deployment_name: Optional[str] = Field(default="gpt-4o-mini", description="Fallback model")

    # OpenAI
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    llm_model: Optional[str] = Field(default="gpt-4o-mini", description="OpenAI model name")

    # Google Gemini
    gemini_api_key: Optional[str] = Field(default=None, description="Google Gemini API key")
    gemini_model: Optional[str] = Field(default="gemini-1.5-pro", description="Gemini model name")

    # Common settings
    max_tokens: int = Field(default=4000, description="Max tokens per request")
    temperature: float = Field(default=0.1, description="Temperature")
    top_p: float = Field(default=0.0, description="Top P")


def get_env_file_path() -> Path:
    """
    Get the path to the .env file.

    For portable builds: uses .env in same directory as the application
    For development: uses .env in project root
    """
    # Calculate paths
    backend_dir = Path(__file__).parent.parent.parent.parent.parent  # Points to /ad/backend
    project_root = backend_dir.parent  # Points to /ad

    # Check if this is a portable build (has setup.sh/setup.bat in current dir)
    cwd = Path.cwd()
    is_portable = (cwd / "setup.sh").exists() or (cwd / "setup.bat").exists()

    if is_portable:
        # Portable build: use .env in current working directory
        env_file = cwd / ".env"
        logger.info(f"Portable build detected - using .env at: {env_file}")
    else:
        # Development: use .env in project root (/ad/.env)
        env_file = project_root / ".env"
        logger.info(f"Development mode - using .env at: {env_file}")

    return env_file


def read_env_file() -> Dict[str, str]:
    """Read .env file and return key-value pairs."""
    env_path = get_env_file_path()
    env_vars = {}

    if not env_path.exists():
        logger.warning(f".env file not found at {env_path}")
        return env_vars

    try:
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    except Exception as e:
        logger.error(f"Error reading .env file: {e}")

    return env_vars


def write_env_file(env_vars: Dict[str, str]):
    """Write key-value pairs to .env file."""
    env_path = get_env_file_path()

    try:
        # Read existing file to preserve comments and structure
        existing_lines = []
        if env_path.exists():
            with open(env_path, 'r') as f:
                existing_lines = f.readlines()

        # Update existing keys or append new ones
        updated_keys = set()
        new_lines = []

        for line in existing_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and '=' in stripped:
                key = stripped.split('=', 1)[0].strip()
                if key in env_vars:
                    new_lines.append(f"{key}={env_vars[key]}\n")
                    updated_keys.add(key)
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)

        # Add new keys that weren't in the file
        for key, value in env_vars.items():
            if key not in updated_keys:
                new_lines.append(f"{key}={value}\n")

        # Write to file
        with open(env_path, 'w') as f:
            f.writelines(new_lines)

        logger.info(f"Updated .env file at {env_path}")
    except Exception as e:
        logger.error(f"Error writing .env file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to write .env file: {str(e)}")


def mask_sensitive_value(value: str) -> str:
    """Mask sensitive values for display."""
    if not value or len(value) < 8:
        return "••••••••"
    return value[:4] + "••••" + value[-4:]


@router.get("/config")
async def get_llm_config():
    """
    Get current LLM configuration from .env file.

    Sensitive values (API keys) are masked for security.
    """
    logger.info("Getting LLM configuration")

    env_vars = read_env_file()

    # Also check environment variables (they override .env)
    provider = os.getenv("LLM_PROVIDER", env_vars.get("LLM_PROVIDER", "azure"))

    # Azure OpenAI
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", env_vars.get("AZURE_OPENAI_ENDPOINT", ""))
    azure_key = os.getenv("AZURE_OPENAI_KEY", env_vars.get("AZURE_OPENAI_KEY", ""))
    azure_api_version = os.getenv("AZURE_API_VERSION", env_vars.get("AZURE_API_VERSION", "2025-01-01-preview"))
    model_deployment = os.getenv("MODEL_DEPLOYMENT_NAME", env_vars.get("MODEL_DEPLOYMENT_NAME", "gpt-4o"))
    fallback_model = os.getenv("FALLBACK_MODEL_DEPLOYMENT_NAME", env_vars.get("FALLBACK_MODEL_DEPLOYMENT_NAME", "gpt-4o-mini"))

    # OpenAI
    openai_key = os.getenv("OPENAI_API_KEY", env_vars.get("OPENAI_API_KEY", ""))
    llm_model = os.getenv("LLM_MODEL", env_vars.get("LLM_MODEL", "gpt-4o-mini"))

    # Gemini
    gemini_key = os.getenv("GEMINI_API_KEY", env_vars.get("GEMINI_API_KEY", ""))
    gemini_model = os.getenv("GEMINI_MODEL", env_vars.get("GEMINI_MODEL", "gemini-1.5-pro"))

    # Common
    max_tokens = int(os.getenv("MAX_TOKENS_PER_REQUEST", env_vars.get("MAX_TOKENS_PER_REQUEST", "4000")))
    temperature = float(os.getenv("LLM_TEMPERATURE", env_vars.get("LLM_TEMPERATURE", "0.1")))
    top_p = float(os.getenv("LLM_TOP_P", env_vars.get("LLM_TOP_P", "0.0")))

    return {
        "provider": provider,
        "azure_openai_endpoint": azure_endpoint,
        "azure_openai_key": mask_sensitive_value(azure_key) if azure_key else "",
        "azure_openai_key_set": bool(azure_key),
        "azure_api_version": azure_api_version,
        "model_deployment_name": model_deployment,
        "fallback_model_deployment_name": fallback_model,
        "openai_api_key": mask_sensitive_value(openai_key) if openai_key else "",
        "openai_api_key_set": bool(openai_key),
        "llm_model": llm_model,
        "gemini_api_key": mask_sensitive_value(gemini_key) if gemini_key else "",
        "gemini_api_key_set": bool(gemini_key),
        "gemini_model": gemini_model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
    }


@router.post("/config")
async def update_llm_config(config: LLMConfig):
    """
    Update LLM configuration in .env file.

    Only updates provided values. Empty/None values are ignored unless explicitly set.
    """
    logger.info(f"Updating LLM configuration for provider: {config.provider}")

    env_vars = read_env_file()
    updates = {}

    # Update provider
    if config.provider:
        updates["LLM_PROVIDER"] = config.provider

    # Azure OpenAI
    if config.azure_openai_endpoint is not None:
        updates["AZURE_OPENAI_ENDPOINT"] = config.azure_openai_endpoint
    if config.azure_openai_key is not None and not config.azure_openai_key.startswith("••••"):
        # Only update if not masked
        updates["AZURE_OPENAI_KEY"] = config.azure_openai_key
    if config.azure_api_version is not None:
        updates["AZURE_API_VERSION"] = config.azure_api_version
    if config.model_deployment_name is not None:
        updates["MODEL_DEPLOYMENT_NAME"] = config.model_deployment_name
    if config.fallback_model_deployment_name is not None:
        updates["FALLBACK_MODEL_DEPLOYMENT_NAME"] = config.fallback_model_deployment_name

    # OpenAI
    if config.openai_api_key is not None and not config.openai_api_key.startswith("••••"):
        updates["OPENAI_API_KEY"] = config.openai_api_key
    if config.llm_model is not None:
        updates["LLM_MODEL"] = config.llm_model

    # Gemini
    if config.gemini_api_key is not None and not config.gemini_api_key.startswith("••••"):
        updates["GEMINI_API_KEY"] = config.gemini_api_key
    if config.gemini_model is not None:
        updates["GEMINI_MODEL"] = config.gemini_model

    # Common settings
    if config.max_tokens is not None:
        updates["MAX_TOKENS_PER_REQUEST"] = str(config.max_tokens)
    if config.temperature is not None:
        updates["LLM_TEMPERATURE"] = str(config.temperature)
    if config.top_p is not None:
        updates["LLM_TOP_P"] = str(config.top_p)

    # Merge with existing env_vars
    env_vars.update(updates)

    # Write to .env file
    write_env_file(env_vars)

    return {
        "status": "success",
        "message": "LLM configuration updated successfully. Please restart the backend for changes to take effect.",
        "updated_fields": list(updates.keys())
    }


@router.post("/config/test")
async def test_llm_connection():
    """
    Test LLM connection with current configuration.

    Attempts a simple API call to verify credentials and connectivity.
    """
    logger.info("Testing LLM connection")

    try:
        from app.services.llm_extractor import get_llm_extractor

        llm = get_llm_extractor()

        # Simple test prompt
        test_response = await llm.generate_explanation_async("Respond with 'OK' if you can read this.")

        if test_response and len(test_response) > 0:
            return {
                "status": "success",
                "message": "LLM connection successful",
                "provider": os.getenv("LLM_PROVIDER", "azure"),
                "response_preview": test_response[:100]
            }
        else:
            return {
                "status": "error",
                "message": "LLM returned empty response"
            }

    except Exception as e:
        logger.error(f"LLM connection test failed: {str(e)}")
        return {
            "status": "error",
            "message": f"LLM connection failed: {str(e)}"
        }
