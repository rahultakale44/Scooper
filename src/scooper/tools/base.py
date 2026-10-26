"""Base abstractions for the tool system.

This module defines the core protocol for tools that agents can execute,
including input validation, execution contracts, and result handling.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from scooper.tools.permissions import ToolPermissionLevel


class ToolInput(BaseModel):
    """Input parameters for tool execution.

    This base model can be extended by specific tools to define
    their required and optional parameters with type validation.

    Attributes:
        metadata: Optional additional context for tool execution
    """

    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Optional metadata for the tool execution context",
    )

    model_config = {
        "extra": "allow",  # Allow tool-specific parameters
    }


class ToolResult(BaseModel):
    """Result of tool execution.

    Attributes:
        success: Whether the tool executed successfully
        output: The primary output data from the tool
        error: Error message if execution failed
        metadata: Additional result metadata
    """

    success: bool = Field(
        description="Whether the tool executed successfully",
    )

    output: Any = Field(
        default=None,
        description="The primary output data from the tool",
    )

    error: str | None = Field(
        default=None,
        description="Error message if execution failed",
    )

    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional metadata about the execution",
    )

    model_config = {
        "frozen": True,
    }


class Tool(ABC):
    """Abstract base class for agent tools.

    Tools are actions that agents can execute to interact with
    external systems, perform computations, or gather information.

    Each tool must have a unique name and provide a description
    of its functionality and required parameters.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this tool."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this tool does."""
        pass

    @property
    def permission_level(self) -> "ToolPermissionLevel":
        """Permission level required for this tool.

        Returns:
            ToolPermissionLevel.ALLOWED by default
        """
        from scooper.tools.permissions import ToolPermissionLevel

        return ToolPermissionLevel.ALLOWED

    @abstractmethod
    async def execute(self, tool_input: ToolInput) -> ToolResult:
        """Execute the tool with the given input.

        Args:
            tool_input: Validated input parameters for the tool

        Returns:
            ToolResult indicating success or failure with output data

        Raises:
            ToolValidationError: If input validation fails
            ToolExecutionError: If execution fails
        """
        pass

    @abstractmethod
    def validate_input(self, tool_input: ToolInput) -> bool:
        """Validate that the input parameters are correct for this tool.

        Args:
            tool_input: Input parameters to validate

        Returns:
            True if input is valid

        Raises:
            ToolValidationError: If validation fails with details
        """
        pass
