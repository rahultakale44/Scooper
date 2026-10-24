"""Fake model provider for deterministic testing.

This provider returns predictable responses without making any network calls,
enabling reliable unit tests and development without external dependencies.
"""

from scooper.models.base import (
    ModelProvider,
    ModelRequest,
    ModelResponse,
)


class FakeModelProvider(ModelProvider):
    """A fake model provider that returns deterministic responses.

    This provider is designed for testing and does not make real API calls.
    It returns predictable responses based on the input prompt or can be
    scripted to return specific responses including tool calls.

    Attributes:
        response_content: The default content to return in text responses
        fail_health_check: If True, health_check returns False
        scripted_responses: List of responses to return in sequence (overrides response_content)
        response_index: Current index in scripted_responses
    """

    def __init__(
        self,
        response_content: str = "This is a fake response.",
        fail_health_check: bool = False,
        scripted_responses: list[ModelResponse] | None = None,
    ):
        """Initialize the fake provider.

        Args:
            response_content: Default content to return in text responses
            fail_health_check: If True, health checks will fail
            scripted_responses: Optional list of responses to return in sequence
        """
        self.response_content = response_content
        self.fail_health_check = fail_health_check
        self.scripted_responses = scripted_responses or []
        self.response_index = 0

    async def generate(self, request: ModelRequest) -> ModelResponse:
        """Generate a deterministic fake response.

        If scripted_responses is set, returns responses from that list in sequence.
        Otherwise, returns a text response with the configured response_content.

        Args:
            request: The model request

        Returns:
            A ModelResponse (either text or tool_calls type)
        """
        # If we have scripted responses, use them
        if self.scripted_responses and self.response_index < len(self.scripted_responses):
            response = self.scripted_responses[self.response_index]
            self.response_index += 1
            return response

        # Otherwise return default text response
        prompt_text = ""
        if request.prompt:
            prompt_text = request.prompt
        elif request.messages:
            # Get the last user message for context
            user_msgs = [m for m in request.messages if m.role == "user"]
            if user_msgs:
                prompt_text = user_msgs[-1].content or ""

        return ModelResponse(
            response_type="text",
            content=self.response_content,
            finish_reason="completed",
            token_count=len(self.response_content.split()),
            metadata={
                "provider": "fake",
                "prompt_length": len(prompt_text),
                "temperature": request.temperature,
            },
        )

    async def health_check(self) -> bool:
        """Check fake provider health.

        Returns:
            True unless fail_health_check is True
        """
        return not self.fail_health_check
