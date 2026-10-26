"""Tool system for agent actions."""

from scooper.tools.base import Tool, ToolInput, ToolResult
from scooper.tools.permissions import (
    ApprovalCallback,
    ApprovalRequest,
    ToolPermissionLevel,
    ToolPermissionPolicy,
)
from scooper.tools.registry import ToolRegistry
from scooper.tools.safe_registry import SafeToolRegistry

__all__ = [
    "Tool",
    "ToolInput",
    "ToolResult",
    "ToolRegistry",
    "SafeToolRegistry",
    "ToolPermissionLevel",
    "ToolPermissionPolicy",
    "ApprovalCallback",
    "ApprovalRequest",
]
