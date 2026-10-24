"""Ollama model provider implementation.

This module provides integration with Ollama, allowing Scooper to use
local LLMs through the Ollama API for agent execution.
"""

import json
import logging
from typing import Any

import httpx

from scooper.config import ModelProviderConfig
from scooper.exceptions import (
    ModelProviderConnectionError,
    ModelProviderError,
    ModelProviderResponseError,
)
from scooper.models.base import (
    Message,
    ModelProvider,
    ModelRequest,
    ModelResponse,
    ToolCall,
)

logger = logging.getLogger(__name__)


class OllamaModelProvider(ModelProvider):
    """Ollama model provider for local LLM execution.

    This provider connects to a local or remote Ollama instance and supports:
    - Text generation with conversation history
    - Tool calling (if supported by the model)
    - Configurable timeouts and model selection
    - Health checking

    Attributes:
        config: Provider configuration with base_url and model_name
        client: Async HTTP client for API requests
    """

    def __init__(self, config: ModelProviderConfig):
        """Initialize the Ollama provider.

        Args:
            config: Provider configuration including base_url and model_name
        """
        self.config = config
        self.client = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=httpx.Timeout(config.timeout_seconds),
        )
        logger.info(f"Initialized OllamaModelProvider with model={config.model_name}")

    async def generate(self, request: ModelRequest) -> ModelResponse:
        """Generate a response from Ollama.

        Converts Scooper's ModelRequest into Ollama's chat API format,
        handles tool calls if supported, and returns a structured response.

        Args:
            request: The model request with prompt or messages

        Returns:
            ModelResponse with text or tool calls

        Raises:
            ModelProviderConnectionError: If connection to Ollama fails
            ModelProviderResponseError: If response is invalid
            ModelProviderError: For other provider errors
        """
        try:
            # Convert request to Ollama format
            ollama_request = self._convert_request(request)

            logger.debug(f"Sending request to Ollama: model={self.config.model_name}")

            # Make API request
            response = await self.client.post("/api/chat", json=ollama_request)
            response.raise_for_status()

            # Parse response
            response_data = response.json()

            # Convert to ModelResponse
            return self._convert_response(response_data)

        except httpx.TimeoutException as e:
            error_msg = f"Request to Ollama timed out after {self.config.timeout_seconds}s"
            logger.error(error_msg)
            raise ModelProviderConnectionError(error_msg) from e

        except httpx.HTTPStatusError as e:
            error_msg = f"Ollama returned HTTP {e.response.status_code}: {e.response.text}"
            logger.error(error_msg)
            raise ModelProviderConnectionError(error_msg) from e

        except httpx.ConnectError as e:
            error_msg = f"Failed to connect to Ollama at {self.config.base_url}. Is Ollama running?"
            logger.error(error_msg)
            raise ModelProviderConnectionError(error_msg) from e

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            error_msg = f"Invalid response from Ollama: {e}"
            logger.error(error_msg)
            raise ModelProviderResponseError(error_msg) from e

        except Exception as e:
            error_msg = f"Unexpected error calling Ollama: {e}"
            logger.error(error_msg)
            raise ModelProviderError(error_msg) from e

    async def health_check(self) -> bool:
        """Check if Ollama is available and healthy.

        Returns:
            True if Ollama is reachable and responsive, False otherwise
        """
        try:
            logger.debug("Performing Ollama health check")
            response = await self.client.get("/api/tags", timeout=5.0)
            response.raise_for_status()
            logger.debug("Ollama health check passed")
            return True
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False

    async def __aenter__(self) -> "OllamaModelProvider":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit - close HTTP client."""
        await self.client.aclose()

    def _convert_request(self, request: ModelRequest) -> dict[str, Any]:
        """Convert Scooper ModelRequest to Ollama chat format.

        Args:
            request: Scooper ModelRequest

        Returns:
            Dict in Ollama API format
        """
        ollama_messages = []

        # Convert messages or prompt
        if request.messages:
            for msg in request.messages:
                ollama_msg = self._convert_message(msg)
                if ollama_msg:
                    ollama_messages.append(ollama_msg)
        elif request.prompt:
            # Simple prompt becomes a user message
            ollama_messages.append({"role": "user", "content": request.prompt})

        # Build request
        ollama_request = {
            "model": self.config.model_name,
            "messages": ollama_messages,
            "stream": False,  # Non-streaming for simplicity
        }

        # Add optional parameters
        options: dict[str, Any] = {}
        if request.temperature is not None:
            options["temperature"] = request.temperature

        # Note: Ollama uses num_predict for max tokens
        if request.max_tokens:
            options["num_predict"] = request.max_tokens

        if request.stop_sequences:
            options["stop"] = request.stop_sequences

        if options:
            ollama_request["options"] = options

        return ollama_request

    def _convert_message(self, message: Message) -> dict[str, Any] | None:
        """Convert Scooper Message to Ollama message format.

        Args:
            message: Scooper Message

        Returns:
            Ollama message dict or None if not convertible
        """
        if message.role == "user":
            return {"role": "user", "content": message.content or ""}

        elif message.role == "assistant":
            ollama_msg: dict[str, Any] = {"role": "assistant", "content": message.content or ""}

            # Handle tool calls if present
            if message.tool_calls:
                # Ollama supports tool calls in newer versions
                # Format: {"role": "assistant", "content": "", "tool_calls": [...]}
                tool_calls_data: list[dict[str, Any]] = []
                for tc in message.tool_calls:
                    tool_calls_data.append(
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.name, "arguments": tc.arguments},
                        }
                    )
                ollama_msg["tool_calls"] = tool_calls_data

            return ollama_msg

        elif message.role == "tool":
            # Tool results are returned as tool messages
            return {
                "role": "tool",
                "content": message.content or "",
                "tool_call_id": message.tool_call_id,
            }

        return None

    def _convert_response(self, response_data: dict[str, Any]) -> ModelResponse:
        """Convert Ollama response to Scooper ModelResponse.

        Args:
            response_data: Ollama API response data

        Returns:
            Scooper ModelResponse

        Raises:
            ModelProviderResponseError: If response format is invalid
        """
        try:
            message = response_data["message"]

            # Check for tool calls
            tool_calls_data = message.get("tool_calls")
            if tool_calls_data:
                # Parse tool calls
                tool_calls = []
                for tc_data in tool_calls_data:
                    function = tc_data.get("function", {})
                    tool_calls.append(
                        ToolCall(
                            id=tc_data.get("id", ""),
                            name=function.get("name", ""),
                            arguments=function.get("arguments", {}),
                        )
                    )

                return ModelResponse(
                    response_type="tool_calls",
                    content=message.get("content"),
                    tool_calls=tool_calls,
                    finish_reason="tool_calls",
                    metadata={
                        "model": response_data.get("model"),
                        "created_at": response_data.get("created_at"),
                        "done": response_data.get("done"),
                    },
                )

            # Regular text response
            content = message.get("content", "")

            # Determine finish reason
            done = response_data.get("done", False)
            done_reason = response_data.get("done_reason", "")

            finish_reason = "completed"
            if done_reason == "length":
                finish_reason = "length"
            elif done_reason == "stop":
                finish_reason = "stop"
            elif not done:
                finish_reason = "incomplete"

            return ModelResponse(
                response_type="text",
                content=content,
                finish_reason=finish_reason,
                metadata={
                    "model": response_data.get("model"),
                    "created_at": response_data.get("created_at"),
                    "done": done,
                    "done_reason": done_reason,
                    "total_duration": response_data.get("total_duration"),
                    "prompt_eval_count": response_data.get("prompt_eval_count"),
                    "eval_count": response_data.get("eval_count"),
                },
            )

        except KeyError as e:
            raise ModelProviderResponseError(f"Missing required field in response: {e}") from e
