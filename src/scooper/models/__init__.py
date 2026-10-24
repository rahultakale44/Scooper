"""Model provider abstractions and implementations."""

from scooper.models.base import (
    Message,
    ModelProvider,
    ModelRequest,
    ModelResponse,
    ToolCall,
)
from scooper.models.fake import FakeModelProvider

__all__ = [
    "Message",
    "ModelProvider",
    "ModelRequest",
    "ModelResponse",
    "ToolCall",
    "FakeModelProvider",
]
