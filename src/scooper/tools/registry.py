"""Tool registry for managing and executing agent tools.

This module provides a registry for registering, discovering, and executing
tools that agents can use to perform actions.
"""

import asyncio
import logging

from scooper.exceptions import (
    ToolExecutionError,
    ToolNotFoundError,
    ToolValidationError,
)
from scooper.tools.base import Tool, ToolInput, ToolResult

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for managing and executing agent tools.

    The registry provides:
    - Tool registration with unique names
    - Tool lookup and discovery
    - Validated tool execution with timeout support
    - Execution error handling

    Example:
        >>> registry = ToolRegistry()
        >>> registry.register(my_tool)
        >>> result = await registry.execute("my_tool", tool_input)
    """

    def __init__(self, default_timeout: float = 30.0):
        """Initialize the tool registry.

        Args:
            default_timeout: Default execution timeout in seconds (default: 30.0)
        """
        self._tools: dict[str, Tool] = {}
        self.default_timeout = default_timeout
        logger.debug(f"Initialized ToolRegistry with timeout={default_timeout}s")

    def register(self, tool: Tool) -> None:
        """Register a tool in the registry.

        Args:
            tool: The tool to register

        Raises:
            ValueError: If a tool with the same name is already registered
        """
        tool_name = tool.name
        if tool_name in self._tools:
            raise ValueError(
                f"Tool '{tool_name}' is already registered. "
                f"Use a unique name or unregister the existing tool first."
            )

        self._tools[tool_name] = tool
        logger.info(f"Registered tool: {tool_name}")

    def unregister(self, tool_name: str) -> None:
        """Unregister a tool from the registry.

        Args:
            tool_name: Name of the tool to unregister

        Raises:
            ToolNotFoundError: If the tool is not found
        """
        if tool_name not in self._tools:
            raise ToolNotFoundError(f"Tool '{tool_name}' not found in registry")

        del self._tools[tool_name]
        logger.info(f"Unregistered tool: {tool_name}")

    def get(self, tool_name: str) -> Tool:
        """Get a registered tool by name.

        Args:
            tool_name: Name of the tool to retrieve

        Returns:
            The registered tool

        Raises:
            ToolNotFoundError: If the tool is not found
        """
        if tool_name not in self._tools:
            available = ", ".join(sorted(self._tools.keys())) if self._tools else "none"
            raise ToolNotFoundError(
                f"Tool '{tool_name}' not found in registry. Available tools: {available}"
            )

        return self._tools[tool_name]

    def list_tools(self) -> list[str]:
        """List all registered tool names in alphabetical order.

        Returns:
            Sorted list of registered tool names
        """
        return sorted(self._tools.keys())

    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool is registered.

        Args:
            tool_name: Name of the tool to check

        Returns:
            True if the tool is registered, False otherwise
        """
        return tool_name in self._tools

    async def execute(
        self,
        tool_name: str,
        tool_input: ToolInput,
        timeout: float | None = None,
    ) -> ToolResult:
        """Execute a registered tool with the given input.

        The method performs:
        1. Tool lookup
        2. Input validation
        3. Async execution with timeout
        4. Error handling and structured results

        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters for the tool
            timeout: Execution timeout in seconds (uses default if None)

        Returns:
            ToolResult with execution outcome

        Raises:
            ToolNotFoundError: If the tool is not found
            ToolValidationError: If input validation fails
            ToolExecutionError: If execution fails
        """
        # Lookup tool
        tool = self.get(tool_name)

        # Validate input
        try:
            tool.validate_input(tool_input)
        except ToolValidationError:
            raise
        except Exception as e:
            raise ToolValidationError(f"Input validation failed for tool '{tool_name}': {e}") from e

        # Execute with timeout
        execution_timeout = timeout if timeout is not None else self.default_timeout

        try:
            logger.debug(f"Executing tool '{tool_name}' with timeout={execution_timeout}s")

            result = await asyncio.wait_for(
                tool.execute(tool_input),
                timeout=execution_timeout,
            )

            logger.debug(f"Tool '{tool_name}' completed: success={result.success}")
            return result

        except asyncio.TimeoutError:
            error_msg = f"Tool '{tool_name}' execution exceeded timeout of {execution_timeout}s"
            logger.error(error_msg)
            raise ToolExecutionError(error_msg) from None

        except ToolExecutionError:
            raise

        except Exception as e:
            error_msg = f"Tool '{tool_name}' execution failed: {e}"
            logger.error(error_msg)
            raise ToolExecutionError(error_msg) from e

    def clear(self) -> None:
        """Remove all registered tools from the registry.

        Useful for testing or reinitializing the registry.
        """
        count = len(self._tools)
        self._tools.clear()
        logger.info(f"Cleared {count} tool(s) from registry")

    def __len__(self) -> int:
        """Return the number of registered tools."""
        return len(self._tools)

    def __contains__(self, tool_name: str) -> bool:
        """Check if a tool name is registered (supports 'in' operator)."""
        return tool_name in self._tools

    def __repr__(self) -> str:
        """String representation of the registry."""
        tool_count = len(self._tools)
        return f"ToolRegistry(tools={tool_count}, timeout={self.default_timeout}s)"
