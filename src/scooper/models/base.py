"""Base abstractions for model providers.

This module defines the core protocol and data models that all model
providers must implement, enabling provider-independent agent execution.
"""

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """Represents a tool call request from the model.

    Attributes:
        id: Unique identifier for this tool call
        name: Name of the tool to execute
        arguments: Arguments to pass to the tool (JSON-serializable dict)
    """

    id: str = Field(
        description="Unique identifier for this tool call",
    )

    name: str = Field(
        description="Name of the tool to execute",
    )

    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments to pass to the tool",
    )

    model_config = {
        "frozen": True,
    }


class Message(BaseModel):
    """Represents a message in the conversation history.

    Messages track the interaction between user, assistant, and tools,
    enabling multi-step conversations with tool use.

    Attributes:
        role: The role of the message sender (user, assistant, tool)
        content: Text content of the message
        tool_calls: Tool calls made by the assistant (for assistant messages)
        tool_call_id: ID of the tool call this message responds to (for tool messages)
        name: Name of the tool that produced this message (for tool messages)
    """

    role: Literal["user", "assistant", "tool"] = Field(
        description="Role of the message sender",
    )

    content: str | None = Field(
        default=None,
        description="Text content of the message",
    )

    tool_calls: list[ToolCall] | None = Field(
        default=None,
        description="Tool calls made by the assistant",
    )

    tool_call_id: str | None = Field(
        default=None,
        description="ID of the tool call this message responds to",
    )

    name: str | None = Field(
        default=None,
        description="Name of the tool that produced this message",
    )

    model_config = {
        "frozen": True,
    }


class ModelRequest(BaseModel):
    """Request sent to a model provider.

    The request can contain either a simple prompt (legacy) or a full
    conversation history with messages (for multi-turn interactions).

    Attributes:
        prompt: Simple text prompt (for single-turn requests)
        messages: Conversation history (for multi-turn requests with tools)
        max_tokens: Maximum number of tokens to generate
        temperature: Sampling temperature (0.0 to 2.0)
        stop_sequences: Optional sequences that stop generation
        metadata: Additional provider-specific parameters
    """

    prompt: str | None = Field(
        default=None,
        description="Simple text prompt for single-turn requests",
    )

    messages: list[Message] | None = Field(
        default=None,
        description="Conversation history for multi-turn requests",
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

    The response can either be a final text response or a request for tool calls.
    The response_type field indicates which type of response this is.

    Attributes:
        response_type: Type of response - "text" for final answer, "tool_calls" for tool requests
        content: The generated text content (for text responses)
        tool_calls: List of tool calls requested by the model (for tool_calls responses)
        finish_reason: Why generation stopped (completed, length, stop, error, tool_calls)
        token_count: Number of tokens in the response
        metadata: Additional provider-specific response data
    """

    response_type: Literal["text", "tool_calls"] = Field(
        default="text",
        description="Type of response - 'text' for final answer, 'tool_calls' for tool requests",
    )

    content: str | None = Field(
        default=None,
        description="Generated text content from the model (for text responses)",
    )

    tool_calls: list[ToolCall] | None = Field(
        default=None,
        description="List of tool calls requested by the model (for tool_calls responses)",
    )

    finish_reason: str = Field(
        description="Reason generation stopped (completed, length, stop, error, tool_calls)",
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
