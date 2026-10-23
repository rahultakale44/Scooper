"""Test model provider abstractions."""

import pytest
from pydantic import ValidationError

from scooper.models import FakeModelProvider, ModelRequest, ModelResponse


class TestModelRequest:
    """Test ModelRequest validation."""

    def test_minimal_request(self):
        """Test creating request with minimal parameters."""
        request = ModelRequest(prompt="Hello, world!")
        assert request.prompt == "Hello, world!"
        assert request.max_tokens == 1024
        assert request.temperature == 0.7
        assert request.stop_sequences is None
        assert request.metadata is None

    def test_custom_request(self):
        """Test creating request with custom parameters."""
        request = ModelRequest(
            prompt="Test prompt",
            max_tokens=500,
            temperature=0.9,
            stop_sequences=["END", "STOP"],
            metadata={"user_id": "123"},
        )
        assert request.prompt == "Test prompt"
        assert request.max_tokens == 500
        assert request.temperature == 0.9
        assert request.stop_sequences == ["END", "STOP"]
        assert request.metadata == {"user_id": "123"}

    def test_max_tokens_bounds(self):
        """Test max_tokens validation."""
        # Valid values
        ModelRequest(prompt="test", max_tokens=1)
        ModelRequest(prompt="test", max_tokens=100000)

        # Invalid values
        with pytest.raises(ValidationError):
            ModelRequest(prompt="test", max_tokens=0)

        with pytest.raises(ValidationError):
            ModelRequest(prompt="test", max_tokens=100001)

    def test_temperature_bounds(self):
        """Test temperature validation."""
        # Valid values
        ModelRequest(prompt="test", temperature=0.0)
        ModelRequest(prompt="test", temperature=1.0)
        ModelRequest(prompt="test", temperature=2.0)

        # Invalid values
        with pytest.raises(ValidationError):
            ModelRequest(prompt="test", temperature=-0.1)

        with pytest.raises(ValidationError):
            ModelRequest(prompt="test", temperature=2.1)

    def test_request_immutable(self):
        """Test that request is immutable."""
        request = ModelRequest(prompt="test")
        with pytest.raises(ValidationError):
            request.prompt = "new prompt"


class TestModelResponse:
    """Test ModelResponse validation."""

    def test_minimal_response(self):
        """Test creating response with minimal parameters."""
        response = ModelResponse(
            content="Generated text",
            finish_reason="completed",
        )
        assert response.content == "Generated text"
        assert response.finish_reason == "completed"
        assert response.token_count is None
        assert response.metadata is None

    def test_full_response(self):
        """Test creating response with all parameters."""
        response = ModelResponse(
            content="Generated text",
            finish_reason="length",
            token_count=150,
            metadata={"model": "test-model"},
        )
        assert response.content == "Generated text"
        assert response.finish_reason == "length"
        assert response.token_count == 150
        assert response.metadata == {"model": "test-model"}

    def test_response_immutable(self):
        """Test that response is immutable."""
        response = ModelResponse(content="test", finish_reason="completed")
        with pytest.raises(ValidationError):
            response.content = "new content"


class TestFakeModelProvider:
    """Test the fake model provider."""

    @pytest.mark.asyncio
    async def test_default_fake_provider(self):
        """Test fake provider with default configuration."""
        provider = FakeModelProvider()
        request = ModelRequest(prompt="Test prompt")

        response = await provider.generate(request)

        assert response.content == "This is a fake response."
        assert response.finish_reason == "completed"
        assert response.token_count == 5  # "This is a fake response." = 5 words
        assert response.metadata["provider"] == "fake"
        assert response.metadata["prompt_length"] == len("Test prompt")

    @pytest.mark.asyncio
    async def test_custom_fake_provider(self):
        """Test fake provider with custom response."""
        custom_response = "Custom fake response content"
        provider = FakeModelProvider(response_content=custom_response)
        request = ModelRequest(prompt="Test")

        response = await provider.generate(request)

        assert response.content == custom_response
        assert response.finish_reason == "completed"

    @pytest.mark.asyncio
    async def test_fake_provider_respects_temperature(self):
        """Test that fake provider includes temperature in metadata."""
        provider = FakeModelProvider()
        request = ModelRequest(prompt="Test", temperature=0.5)

        response = await provider.generate(request)

        assert response.metadata["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check."""
        provider = FakeModelProvider()
        is_healthy = await provider.health_check()
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test failed health check."""
        provider = FakeModelProvider(fail_health_check=True)
        is_healthy = await provider.health_check()
        assert is_healthy is False

    @pytest.mark.asyncio
    async def test_multiple_requests(self):
        """Test that provider can handle multiple requests."""
        provider = FakeModelProvider(response_content="Response")

        response1 = await provider.generate(ModelRequest(prompt="First"))
        response2 = await provider.generate(ModelRequest(prompt="Second"))

        assert response1.content == "Response"
        assert response2.content == "Response"
        assert response1.metadata["prompt_length"] == len("First")
        assert response2.metadata["prompt_length"] == len("Second")
