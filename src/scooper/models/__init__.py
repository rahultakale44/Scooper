"""Model provider abstractions and implementations."""

from scooper.models.base import (
    Message,
    ModelProvider,
    ModelRequest,
    ModelResponse,
    ToolCall,
)
from scooper.models.fake import FakeModelProvider
from scooper.models.ollama import OllamaModelProvider

__all__ = [
    "Message",
    "ModelProvider",
    "ModelRequest",
    "ModelResponse",
    "ToolCall",
    "FakeModelProvider",
    "OllamaModelProvider",
]
