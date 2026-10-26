"""Configuration management for Scooper.

This module provides validated configuration models using Pydantic,
ensuring type safety and early validation of configuration errors.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from scooper.exceptions import ConfigurationError


class ScooperConfig(BaseModel):
    """Main configuration for Scooper.

    Attributes:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        max_iterations: Maximum number of agent execution iterations
        timeout_seconds: Maximum execution time in seconds (0 = no timeout)
        max_tool_calls_per_execution: Maximum tool calls per execution (0 = unlimited)
    """

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level for Scooper operations",
    )

    max_iterations: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of agent iterations before stopping",
    )

    timeout_seconds: int = Field(
        default=300,
        ge=0,
        description="Maximum execution time in seconds (0 = no timeout)",
    )

    max_tool_calls_per_execution: int = Field(
        default=0,
        ge=0,
        description="Maximum tool calls per execution (0 = unlimited)",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Ensure log level is valid."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v not in valid_levels:
            raise ConfigurationError(
                f"Invalid log level '{v}'. Must be one of: {', '.join(valid_levels)}"
            )
        return v

    model_config = {
        "frozen": True,  # Make config immutable after creation
        "extra": "forbid",  # Reject unknown fields
    }


class ModelProviderConfig(BaseModel):
    """Configuration for a model provider.

    Attributes:
        provider_type: Type of provider (ollama, openai, anthropic, etc.)
        base_url: Base URL for the provider API
        api_key: Optional API key for authentication
        model_name: Name of the model to use
        timeout_seconds: Request timeout in seconds
    """

    provider_type: str = Field(
        description="Type of model provider (e.g., 'ollama', 'openai')",
    )

    base_url: str = Field(
        description="Base URL for the provider API",
    )

    api_key: str | None = Field(
        default=None,
        description="API key for authentication (if required)",
    )

    model_name: str = Field(
        description="Name of the model to use",
    )

    timeout_seconds: int = Field(
        default=30,
        ge=1,
        description="Request timeout in seconds",
    )

    @field_validator("provider_type")
    @classmethod
    def validate_provider_type(cls, v: str) -> str:
        """Ensure provider type is not empty."""
        if not v or not v.strip():
            raise ConfigurationError("provider_type cannot be empty")
        return v.strip()

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Ensure base URL is valid."""
        if not v or not v.strip():
            raise ConfigurationError("base_url cannot be empty")
        url = v.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            raise ConfigurationError("base_url must start with http:// or https://")
        return url

    @field_validator("model_name")
    @classmethod
    def validate_model_name(cls, v: str) -> str:
        """Ensure model name is not empty."""
        if not v or not v.strip():
            raise ConfigurationError("model_name cannot be empty")
        return v.strip()

    model_config = {
        "frozen": True,
        "extra": "forbid",
    }
