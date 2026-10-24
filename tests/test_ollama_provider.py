"""Tests for Ollama model provider."""

import json

import pytest
from httpx import ConnectError, Response, TimeoutException

from scooper.config import ModelProviderConfig
from scooper.exceptions import (
    ModelProviderConnectionError,
    ModelProviderError,
    ModelProviderResponseError,
)
from scooper.models import (
    Message,
    ModelRequest,
    OllamaModelProvider,
    ToolCall,
)


@pytest.fixture
def ollama_config():
    """Create Ollama provider configuration."""
    return ModelProviderConfig(
        provider_type="ollama",
        base_url="http://localhost:11434",
        model_name="llama2",
        timeout_seconds=30,
    )


@pytest.fixture
def ollama_provider(ollama_config):
    """Create Ollama provider instance."""
    return OllamaModelProvider(ollama_config)


class TestOllamaProviderInit:
    """Test Ollama provider initialization."""

    def test_provider_initialization(self, ollama_config):
        """Test provider initializes correctly."""
        provider = OllamaModelProvider(ollama_config)

        assert provider.config == ollama_config
        assert provider.client is not None
        assert provider.client.base_url == "http://localhost:11434"

    def test_provider_custom_timeout(self):
        """Test provider with custom timeout."""
        config = ModelProviderConfig(
            provider_type="ollama",
            base_url="http://localhost:11434",
            model_name="llama2",
            timeout_seconds=60,
        )
        provider = OllamaModelProvider(config)

        assert provider.client.timeout.read == 60.0


class TestOllamaRequestConversion:
    """Test request conversion to Ollama format."""

    def test_convert_simple_prompt(self, ollama_provider):
        """Test converting simple prompt to Ollama format."""
        request = ModelRequest(prompt="Hello, world!")

        ollama_request = ollama_provider._convert_request(request)

        assert ollama_request["model"] == "llama2"
        assert ollama_request["stream"] is False
        assert len(ollama_request["messages"]) == 1
        assert ollama_request["messages"][0] == {"role": "user", "content": "Hello, world!"}

    def test_convert_messages(self, ollama_provider):
        """Test converting message history to Ollama format."""
        messages = [
            Message(role="user", content="What is Python?"),
            Message(role="assistant", content="Python is a programming language."),
            Message(role="user", content="Tell me more."),
        ]
        request = ModelRequest(messages=messages)

        ollama_request = ollama_provider._convert_request(request)

        assert len(ollama_request["messages"]) == 3
        assert ollama_request["messages"][0]["role"] == "user"
        assert ollama_request["messages"][1]["role"] == "assistant"
        assert ollama_request["messages"][2]["role"] == "user"

    def test_convert_with_tool_calls(self, ollama_provider):
        """Test converting messages with tool calls."""
        tool_calls = [
            ToolCall(id="call_1", name="search", arguments={"query": "python"}),
        ]
        messages = [
            Message(role="user", content="Search for Python"),
            Message(role="assistant", content="", tool_calls=tool_calls),
        ]
        request = ModelRequest(messages=messages)

        ollama_request = ollama_provider._convert_request(request)

        assert len(ollama_request["messages"]) == 2
        assistant_msg = ollama_request["messages"][1]
        assert "tool_calls" in assistant_msg
        assert len(assistant_msg["tool_calls"]) == 1
        assert assistant_msg["tool_calls"][0]["function"]["name"] == "search"

    def test_convert_with_tool_results(self, ollama_provider):
        """Test converting tool result messages."""
        messages = [
            Message(role="tool", content="Search results...", tool_call_id="call_1", name="search"),
        ]
        request = ModelRequest(messages=messages)

        ollama_request = ollama_provider._convert_request(request)

        assert len(ollama_request["messages"]) == 1
        tool_msg = ollama_request["messages"][0]
        assert tool_msg["role"] == "tool"
        assert tool_msg["content"] == "Search results..."
        assert tool_msg["tool_call_id"] == "call_1"

    def test_convert_with_options(self, ollama_provider):
        """Test converting request with temperature and max_tokens."""
        request = ModelRequest(
            prompt="Test",
            temperature=0.8,
            max_tokens=2048,
            stop_sequences=["STOP", "END"],
        )

        ollama_request = ollama_provider._convert_request(request)

        assert ollama_request["options"]["temperature"] == 0.8
        assert ollama_request["options"]["num_predict"] == 2048
        assert ollama_request["options"]["stop"] == ["STOP", "END"]


class TestOllamaResponseConversion:
    """Test response conversion from Ollama format."""

    def test_convert_text_response(self, ollama_provider):
        """Test converting successful text response."""
        ollama_response = {
            "model": "llama2",
            "created_at": "2023-08-04T19:22:45.499127Z",
            "message": {"role": "assistant", "content": "Hello! How can I help you?"},
            "done": True,
            "total_duration": 5589157167,
            "prompt_eval_count": 26,
            "eval_count": 298,
        }

        response = ollama_provider._convert_response(ollama_response)

        assert response.response_type == "text"
        assert response.content == "Hello! How can I help you?"
        assert response.finish_reason == "completed"
        assert response.metadata["model"] == "llama2"
        assert response.metadata["done"] is True

    def test_convert_response_with_tool_calls(self, ollama_provider):
        """Test converting response with tool calls."""
        ollama_response = {
            "model": "llama2",
            "created_at": "2023-08-04T19:22:45.499127Z",
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_abc123",
                        "type": "function",
                        "function": {"name": "search", "arguments": {"query": "python"}},
                    }
                ],
            },
            "done": True,
        }

        response = ollama_provider._convert_response(ollama_response)

        assert response.response_type == "tool_calls"
        assert response.finish_reason == "tool_calls"
        assert response.tool_calls is not None
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].id == "call_abc123"
        assert response.tool_calls[0].name == "search"
        assert response.tool_calls[0].arguments == {"query": "python"}

    def test_convert_response_length_stop(self, ollama_provider):
        """Test converting response that stopped due to length."""
        ollama_response = {
            "model": "llama2",
            "created_at": "2023-08-04T19:22:45.499127Z",
            "message": {"role": "assistant", "content": "This is a truncated..."},
            "done": True,
            "done_reason": "length",
        }

        response = ollama_provider._convert_response(ollama_response)

        assert response.finish_reason == "length"

    def test_convert_invalid_response(self, ollama_provider):
        """Test converting response with missing required fields."""
        ollama_response = {"model": "llama2"}  # Missing 'message' field

        with pytest.raises(ModelProviderResponseError) as exc_info:
            ollama_provider._convert_response(ollama_response)

        assert "Missing required field" in str(exc_info.value)


class TestOllamaGeneration:
    """Test Ollama generation with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_successful_generation(self, ollama_provider, monkeypatch):
        """Test successful text generation."""
        mock_response_data = {
            "model": "llama2",
            "created_at": "2023-08-04T19:22:45.499127Z",
            "message": {"role": "assistant", "content": "Generated response"},
            "done": True,
        }

        class MockResponse:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return mock_response_data

        async def mock_post(url, **kwargs):
            return MockResponse()

        monkeypatch.setattr(ollama_provider.client, "post", mock_post)

        request = ModelRequest(prompt="Test prompt")
        response = await ollama_provider.generate(request)

        assert response.response_type == "text"
        assert response.content == "Generated response"
        assert response.finish_reason == "completed"

    @pytest.mark.asyncio
    async def test_generation_with_tool_calls(self, ollama_provider, monkeypatch):
        """Test generation that returns tool calls."""
        mock_response_data = {
            "model": "llama2",
            "created_at": "2023-08-04T19:22:45.499127Z",
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "calculator", "arguments": {"a": 5, "b": 3}},
                    }
                ],
            },
            "done": True,
        }

        class MockResponse:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return mock_response_data

        async def mock_post(url, **kwargs):
            return MockResponse()

        monkeypatch.setattr(ollama_provider.client, "post", mock_post)

        request = ModelRequest(prompt="Calculate 5+3")
        response = await ollama_provider.generate(request)

        assert response.response_type == "tool_calls"
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].name == "calculator"

    @pytest.mark.asyncio
    async def test_connection_error(self, ollama_provider, monkeypatch):
        """Test handling of connection errors."""

        async def mock_post(url, **kwargs):
            raise ConnectError("Connection refused")

        monkeypatch.setattr(ollama_provider.client, "post", mock_post)

        request = ModelRequest(prompt="Test")

        with pytest.raises(ModelProviderConnectionError) as exc_info:
            await ollama_provider.generate(request)

        assert "Failed to connect" in str(exc_info.value)
        assert "Is Ollama running?" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_timeout_error(self, ollama_provider, monkeypatch):
        """Test handling of timeout errors."""

        async def mock_post(url, **kwargs):
            raise TimeoutException("Request timed out")

        monkeypatch.setattr(ollama_provider.client, "post", mock_post)

        request = ModelRequest(prompt="Test")

        with pytest.raises(ModelProviderConnectionError) as exc_info:
            await ollama_provider.generate(request)

        assert "timed out" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_http_error(self, ollama_provider, monkeypatch):
        """Test handling of HTTP errors."""
        from httpx import HTTPStatusError, Request

        async def mock_post(url, **kwargs):
            req = Request("POST", "http://localhost:11434/api/chat")
            response = Response(500, text="Internal Server Error", request=req)
            raise HTTPStatusError("Server error", request=req, response=response)

        monkeypatch.setattr(ollama_provider.client, "post", mock_post)

        request = ModelRequest(prompt="Test")

        with pytest.raises(ModelProviderConnectionError) as exc_info:
            await ollama_provider.generate(request)

        assert "HTTP 500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_json_response(self, ollama_provider, monkeypatch):
        """Test handling of invalid JSON responses."""

        class MockResponse:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                raise json.JSONDecodeError("Invalid JSON", "", 0)

        async def mock_post(url, **kwargs):
            return MockResponse()

        monkeypatch.setattr(ollama_provider.client, "post", mock_post)

        request = ModelRequest(prompt="Test")

        with pytest.raises(ModelProviderResponseError) as exc_info:
            await ollama_provider.generate(request)

        assert "Invalid response" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_unexpected_error(self, ollama_provider, monkeypatch):
        """Test handling of unexpected errors."""

        async def mock_post(url, **kwargs):
            raise RuntimeError("Unexpected error")

        monkeypatch.setattr(ollama_provider.client, "post", mock_post)

        request = ModelRequest(prompt="Test")

        with pytest.raises(ModelProviderError) as exc_info:
            await ollama_provider.generate(request)

        assert "Unexpected error" in str(exc_info.value)


class TestOllamaHealthCheck:
    """Test Ollama health check functionality."""

    @pytest.mark.asyncio
    async def test_healthy_provider(self, ollama_provider, monkeypatch):
        """Test health check with healthy provider."""

        class MockResponse:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {"models": []}

        async def mock_get(url, **kwargs):
            return MockResponse()

        monkeypatch.setattr(ollama_provider.client, "get", mock_get)

        is_healthy = await ollama_provider.health_check()

        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_unhealthy_provider(self, ollama_provider, monkeypatch):
        """Test health check with connection failure."""

        async def mock_get(url, **kwargs):
            raise ConnectError("Connection refused")

        monkeypatch.setattr(ollama_provider.client, "get", mock_get)

        is_healthy = await ollama_provider.health_check()

        assert is_healthy is False

    @pytest.mark.asyncio
    async def test_health_check_http_error(self, ollama_provider, monkeypatch):
        """Test health check with HTTP error."""
        from httpx import HTTPStatusError, Request

        async def mock_get(url, **kwargs):
            req = Request("GET", "http://localhost:11434/api/tags")
            response = Response(500, text="Server error", request=req)
            raise HTTPStatusError("Server error", request=req, response=response)

        monkeypatch.setattr(ollama_provider.client, "get", mock_get)

        is_healthy = await ollama_provider.health_check()

        assert is_healthy is False


class TestOllamaContextManager:
    """Test async context manager functionality."""

    @pytest.mark.asyncio
    async def test_context_manager(self, ollama_config):
        """Test provider can be used as async context manager."""
        async with OllamaModelProvider(ollama_config) as provider:
            assert provider.client is not None

        # Client should be closed after exiting context
        assert provider.client.is_closed
