"""Base abstractions for model providers.

This module defines the core protocol and data models that all model
providers must implement, enabling provider-independent agent execution.
"""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class ModelRequest(BaseModel):
    """Request sent to a model provider.

    Attributes:
        prompt: The input prompt or message for the model
        max_tokens: Maximum number of tokens to generate
        temperature: Sampling temperature (0.0 to 2.0)
        stop_sequences: Optional sequences that stop generation
        metadata: Additional provider-specific parameters
    """

    prompt: str = Field(
        description="Input prompt or message for the model",
    )

    max_tokens: int = Field(
        default=1024,
        ge=1,
        le=100000,
        description="Maximum number of tokens to generate",
    )

    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for generation",
    )

    stop_sequences: list[str] | None = Field(
        default=None,
        description="Sequences that stop generation when encountered",
    )

    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional provider-specific parameters",
    )

    model_config = {
        "frozen": True,
    }


class ModelResponse(BaseModel):
    """Response received from a model provider.

    Attributes:
        content: The generated text content
        finish_reason: Why generation stopped (completed, length, stop, error)
        token_count: Number of tokens in the response
        metadata: Additional provider-specific response data
    """

    content: str = Field(
        description="Generated text content from the model",
    )

    finish_reason: str = Field(
        description="Reason generation stopped (completed, length, stop, error)",
    )

    token_count: int | None = Field(
        default=None,
        description="Number of tokens in the response",
    )

    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional provider-specific response data",
    )

    model_config = {
        "frozen": True,
    }


class ModelProvider(ABC):
    """Abstract base class for model providers.

    All model provider implementations must inherit from this class
    and implement the generate method for async text generation.
    """

    @abstractmethod
    async def generate(self, request: ModelRequest) -> ModelResponse:
        """Generate a response from the model.

        Args:
            request: The model request containing prompt and parameters

        Returns:
            ModelResponse containing the generated content

        Raises:
            ModelProviderError: If generation fails
            ModelProviderConnectionError: If connection to provider fails
            ModelProviderResponseError: If response is invalid
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is available and healthy.

        Returns:
            True if the provider is healthy, False otherwise
        """
        pass
