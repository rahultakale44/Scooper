"""Safe tool registry with permission enforcement.

This module provides a wrapper around ToolRegistry that enforces
permission policies and approval workflows before tool execution.
"""

import logging

from scooper.exceptions import ExecutionLimitExceededError
from scooper.tools.base import ToolInput, ToolResult
from scooper.tools.permissions import (
    ToolPermissionLevel,
    ToolPermissionPolicy,
)
from scooper.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class SafeToolRegistry:
    """Tool registry with safety and permission enforcement.

    This registry wraps a standard ToolRegistry and enforces:
    - Permission policies (allowlist/denylist)
    - Approval workflows for sensitive tools
    - Per-execution tool call limits
    - All safety checks before tool execution

    The model never has authority to grant itself permissions.
    All checks are enforced in Python before tool functions execute.

    **IMPORTANT**: The tool call counter (_tool_calls_made) persists across
    executions when reusing the same SafeToolRegistry instance. Call
    reset_call_count() before starting a new independent execution to ensure
    limits are enforced correctly.

    For session resumption, consider creating a new SafeToolRegistry instance
    or explicitly resetting the counter.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        policy: ToolPermissionPolicy | None = None,
        max_tool_calls_per_execution: int | None = None,
        session_id: str | None = None,
    ):
        """Initialize the safe tool registry.

        Args:
            registry: Underlying tool registry
            policy: Optional permission policy
            max_tool_calls_per_execution: Maximum tool calls allowed per execution.
                **IMPORTANT**: This limit persists across multiple execute() calls.
                Call reset_call_count() between independent executions.
            session_id: Optional session identifier for approval context
        """
        self._registry = registry
        self._policy = policy
        self._max_tool_calls = max_tool_calls_per_execution
        self._session_id = session_id
        self._tool_calls_made = 0

        logger.info(
            f"Initialized SafeToolRegistry: "
            f"policy={'configured' if policy else 'none'}, "
            f"max_calls={max_tool_calls_per_execution or 'unlimited'}, "
            f"session={session_id or 'none'}"
        )

    async def execute(
        self,
        tool_name: str,
        tool_input: ToolInput,
        timeout: float | None = None,
    ) -> ToolResult:
        """Execute a tool with full safety enforcement.

        Enforcement order:
        1. Check tool call limits
        2. Lookup tool (fails if not registered)
        3. Check permission policy
        4. Request approval if required
        5. Execute tool via underlying registry

        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters for the tool
            timeout: Execution timeout in seconds

        Returns:
            ToolResult with execution outcome

        Raises:
            ExecutionLimitExceededError: If tool call limit exceeded
            ToolPermissionDeniedError: If tool is denied by policy
            ToolApprovalRequiredError: If approval required but not configured
            ToolApprovalDeniedError: If approval is denied
            ToolNotFoundError: If tool is not found
            ToolValidationError: If input validation fails
            ToolExecutionError: If execution fails
        """
        # 1. Check execution limits
        if self._max_tool_calls is not None and self._tool_calls_made >= self._max_tool_calls:
            logger.error(
                f"Tool call limit exceeded: {self._tool_calls_made}/{self._max_tool_calls}"
            )
            raise ExecutionLimitExceededError(
                f"Maximum tool calls per execution ({self._max_tool_calls}) exceeded"
            )

        # 2. Lookup tool (validates registration)
        tool = self._registry.get(tool_name)

        # 3. Check permission policy
        if self._policy:
            self._policy.check_permission(tool_name)

        # 4. Request approval if required
        if tool.permission_level == ToolPermissionLevel.REQUIRES_APPROVAL:
            if self._policy:
                await self._policy.request_approval(tool_name, tool_input, self._session_id)
            else:
                # No policy means no approval mechanism - fail closed
                from scooper.exceptions import ToolApprovalRequiredError

                raise ToolApprovalRequiredError(
                    f"Tool '{tool_name}' requires approval but no policy is configured"
                )

        # 5. Execute via underlying registry
        logger.info(f"Executing tool '{tool_name}' (call {self._tool_calls_made + 1})")
        self._tool_calls_made += 1

        return await self._registry.execute(tool_name, tool_input, timeout)

    def reset_call_count(self) -> None:
        """Reset the tool call counter.

        Used when starting a new execution with the same registry.
        """
        logger.debug(f"Resetting tool call count (was {self._tool_calls_made})")
        self._tool_calls_made = 0

    @property
    def tool_calls_made(self) -> int:
        """Get the number of tool calls made."""
        return self._tool_calls_made

    @property
    def registry(self) -> ToolRegistry:
        """Get the underlying tool registry."""
        return self._registry

    @property
    def policy(self) -> ToolPermissionPolicy | None:
        """Get the permission policy."""
        return self._policy

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"SafeToolRegistry("
            f"tools={len(self._registry)}, "
            f"policy={'yes' if self._policy else 'no'}, "
            f"calls={self._tool_calls_made}/{self._max_tool_calls or '∞'}"
            f")"
        )

