"""Tool permission and approval system.

This module provides framework-enforced safety controls for tool execution,
including permission policies, approval workflows, and execution limits.
"""

import logging
from enum import Enum
from typing import Any, Protocol

from pydantic import BaseModel, Field

from scooper.exceptions import (
    ToolApprovalDeniedError,
    ToolApprovalRequiredError,
    ToolPermissionDeniedError,
)
from scooper.tools.base import ToolInput

logger = logging.getLogger(__name__)


class ToolPermissionLevel(str, Enum):
    """Permission level required for tool execution.

    Attributes:
        ALLOWED: Tool can execute without additional approval
        REQUIRES_APPROVAL: Tool requires explicit approval before execution
    """

    ALLOWED = "allowed"
    REQUIRES_APPROVAL = "requires_approval"


class ApprovalRequest(BaseModel):
    """Request for tool execution approval.

    Attributes:
        tool_name: Canonical name of the tool requesting approval
        arguments: Validated tool arguments
        session_id: Optional session identifier for context
        metadata: Additional context for approval decision
    """

    tool_name: str = Field(
        description="Canonical tool name",
    )

    arguments: dict[str, Any] = Field(
        description="Validated tool arguments",
    )

    session_id: str | None = Field(
        default=None,
        description="Optional session identifier",
    )

    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional approval context",
    )

    model_config = {
        "frozen": True,
    }


class ApprovalCallback(Protocol):
    """Protocol for tool approval callbacks.

    Approval callbacks must be async and return a boolean indicating
    whether the tool execution is approved.
    """

    async def __call__(self, request: ApprovalRequest) -> bool:
        """Request approval for tool execution.

        Args:
            request: Approval request with tool details

        Returns:
            True if approved, False if denied

        Raises:
            Exception: Approval errors should be propagated
        """
        ...


class ToolPermissionPolicy:
    """Permission policy for controlling tool execution.

    The policy enforces:
    - Allowlist: Tools must be explicitly permitted
    - Denylist: Tools are explicitly forbidden (overrides allowlist)
    - Approval workflow: Tools requiring approval must be approved before execution

    Policy semantics:
    1. If a tool is on the denylist, it is always denied
    2. If an allowlist is configured and tool is not on it, it is denied
    3. If no allowlist is configured, tools are allowed by default (unless denied)
    4. Tools requiring approval must be approved before execution
    """

    def __init__(
        self,
        allowlist: set[str] | None = None,
        denylist: set[str] | None = None,
        approval_callback: ApprovalCallback | None = None,
    ):
        """Initialize the permission policy.

        Args:
            allowlist: Set of permitted tool names (None = allow all)
            denylist: Set of forbidden tool names (overrides allowlist)
            approval_callback: Callback for approval requests
        """
        self.allowlist = allowlist
        self.denylist = denylist or set()
        self.approval_callback = approval_callback

        logger.info(
            f"Initialized ToolPermissionPolicy: "
            f"allowlist={'enabled' if allowlist else 'disabled'}, "
            f"denylist={len(self.denylist)} tool(s), "
            f"approval_callback={'configured' if approval_callback else 'none'}"
        )

    def check_permission(self, tool_name: str) -> None:
        """Check if a tool is permitted by policy.

        Args:
            tool_name: Canonical tool name to check

        Raises:
            ToolPermissionDeniedError: If tool is denied by policy
        """
        # Denylist always takes precedence
        if tool_name in self.denylist:
            logger.warning(f"Tool '{tool_name}' denied by denylist")
            raise ToolPermissionDeniedError(
                f"Tool '{tool_name}' is denied by permission policy (denylist)"
            )

        # If allowlist is configured, tool must be on it
        if self.allowlist is not None and tool_name not in self.allowlist:
            logger.warning(f"Tool '{tool_name}' not in allowlist")
            raise ToolPermissionDeniedError(
                f"Tool '{tool_name}' is not in the allowed tools list"
            )

        logger.debug(f"Tool '{tool_name}' permitted by policy")

    async def request_approval(
        self,
        tool_name: str,
        tool_input: ToolInput,
        session_id: str | None = None,
    ) -> None:
        """Request approval for tool execution.

        Args:
            tool_name: Canonical tool name
            tool_input: Validated tool arguments
            session_id: Optional session identifier

        Raises:
            ToolApprovalRequiredError: If approval is required but no callback is configured
            ToolApprovalDeniedError: If approval is explicitly denied
        """
        if not self.approval_callback:
            logger.error(f"Tool '{tool_name}' requires approval but no callback is configured")
            raise ToolApprovalRequiredError(
                f"Tool '{tool_name}' requires approval but no approval handler is configured"
            )

        # Create approval request
        request = ApprovalRequest(
            tool_name=tool_name,
            arguments=tool_input.model_dump(),
            session_id=session_id,
            metadata=tool_input.metadata,
        )

        try:
            logger.info(f"Requesting approval for tool '{tool_name}'")
            approved = await self.approval_callback(request)

            if not approved:
                logger.warning(f"Tool '{tool_name}' approval denied")
                raise ToolApprovalDeniedError(f"Tool '{tool_name}' execution was not approved")

            logger.info(f"Tool '{tool_name}' approval granted")

        except (ToolApprovalDeniedError, ToolApprovalRequiredError):
            raise
        except Exception as e:
            # Fail closed on approval errors
            logger.error(f"Tool '{tool_name}' approval failed: {e}")
            raise ToolApprovalDeniedError(
                f"Tool '{tool_name}' approval failed due to error: {e}"
            ) from e

    def is_allowed(self, tool_name: str) -> bool:
        """Check if a tool is allowed without raising exceptions.

        Args:
            tool_name: Tool name to check

        Returns:
            True if allowed, False if denied
        """
        if tool_name in self.denylist:
            return False

        return not (self.allowlist is not None and tool_name not in self.allowlist)

