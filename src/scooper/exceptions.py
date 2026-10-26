"""Exception hierarchy for Scooper.

This module defines the core exception types used throughout Scooper,
enabling structured error handling and clear error propagation.
"""


class ScooperError(Exception):
    """Base exception for all Scooper-related errors."""

    pass


class ConfigurationError(ScooperError):
    """Raised when configuration is invalid or incomplete."""

    pass


class ModelProviderError(ScooperError):
    """Base exception for model provider-related errors."""

    pass


class ModelProviderConnectionError(ModelProviderError):
    """Raised when connection to a model provider fails."""

    pass


class ModelProviderResponseError(ModelProviderError):
    """Raised when a model provider returns an invalid or unexpected response."""

    pass


class ToolError(ScooperError):
    """Base exception for tool-related errors."""

    pass


class ToolNotFoundError(ToolError):
    """Raised when a requested tool is not found in the registry."""

    pass


class ToolExecutionError(ToolError):
    """Raised when tool execution fails."""

    pass


class ToolValidationError(ToolError):
    """Raised when tool input validation fails."""

    pass


class RuntimeError(ScooperError):
    """Base exception for runtime execution errors."""

    pass


class RuntimeMaxIterationsError(RuntimeError):
    """Raised when the maximum number of iterations is exceeded."""

    pass


class RuntimeTimeoutError(RuntimeError):
    """Raised when execution exceeds the configured timeout."""

    pass


class SessionError(ScooperError):
    """Base exception for session-related errors."""

    pass


class SessionNotFoundError(SessionError):
    """Raised when a requested session is not found."""

    pass


class ToolPermissionError(ToolError):
    """Base exception for tool permission-related errors."""

    pass


class ToolPermissionDeniedError(ToolPermissionError):
    """Raised when a tool execution is denied by permission policy."""

    pass


class ToolApprovalRequiredError(ToolPermissionError):
    """Raised when a tool requires approval but no approval handler is configured."""

    pass


class ToolApprovalDeniedError(ToolPermissionError):
    """Raised when tool approval is explicitly denied."""

    pass


class ExecutionLimitExceededError(RuntimeError):
    """Raised when an execution limit is exceeded."""

    pass
