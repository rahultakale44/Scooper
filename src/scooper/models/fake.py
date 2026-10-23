"""Fake model provider for deterministic testing.

This provider returns predictable responses without making any network calls,
enabling reliable unit tests and development without external dependencies.
"""

from scooper.models.base import ModelProvider, ModelRequest, ModelResponse


class FakeModelProvider(ModelProvider):
    """A fake model provider that returns deterministic responses.

    This provider is designed for testing and does not make real API calls.
    It returns predictable responses based on the input prompt.

    Attributes:
        response_content: The content to return in responses
        fail_health_check: If True, health_check returns False
    """

    def __init__(
        self,
        response_content: str = "This is a fake response.",
        fail_health_check: bool = False,
    ):
        """Initialize the fake provider.

        Args:
            response_content: Content to return in all responses
            fail_health_check: If True, health checks will fail
        """
        self.response_content = response_content
        self.fail_health_check = fail_health_check

    async def generate(self, request: ModelRequest) -> ModelResponse:
        """Generate a deterministic fake response.

        Args:
            request: The model request (prompt is echoed in metadata)

        Returns:
            A ModelResponse with the configured response content
        """
        return ModelResponse(
            content=self.response_content,
            finish_reason="completed",
            token_count=len(self.response_content.split()),
            metadata={
                "provider": "fake",
                "prompt_length": len(request.prompt),
                "temperature": request.temperature,
            },
        )

    async def health_check(self) -> bool:
        """Check fake provider health.

        Returns:
            True unless fail_health_check is True
        """
        return not self.fail_health_check
