"""Test exception hierarchy."""

import pytest

from scooper.exceptions import (
    ConfigurationError,
    ModelProviderConnectionError,
    ModelProviderError,
    ModelProviderResponseError,
    RuntimeError,
    RuntimeMaxIterationsError,
    RuntimeTimeoutError,
    ScooperError,
    SessionError,
    SessionNotFoundError,
    ToolError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolValidationError,
)


def test_base_exception():
    """Test that ScooperError is the base exception."""
    error = ScooperError("test error")
    assert isinstance(error, Exception)
    assert str(error) == "test error"


def test_configuration_error_inheritance():
    """Test ConfigurationError inherits from ScooperError."""
    error = ConfigurationError("config error")
    assert isinstance(error, ScooperError)
    assert isinstance(error, Exception)


def test_model_provider_errors():
    """Test model provider exception hierarchy."""
    base_error = ModelProviderError("base error")
    assert isinstance(base_error, ScooperError)

    conn_error = ModelProviderConnectionError("connection failed")
    assert isinstance(conn_error, ModelProviderError)
    assert isinstance(conn_error, ScooperError)

    resp_error = ModelProviderResponseError("invalid response")
    assert isinstance(resp_error, ModelProviderError)
    assert isinstance(resp_error, ScooperError)


def test_tool_errors():
    """Test tool exception hierarchy."""
    base_error = ToolError("base error")
    assert isinstance(base_error, ScooperError)

    not_found = ToolNotFoundError("tool not found")
    assert isinstance(not_found, ToolError)

    execution_error = ToolExecutionError("execution failed")
    assert isinstance(execution_error, ToolError)

    validation_error = ToolValidationError("validation failed")
    assert isinstance(validation_error, ToolError)


def test_runtime_errors():
    """Test runtime exception hierarchy."""
    base_error = RuntimeError("base error")
    assert isinstance(base_error, ScooperError)

    max_iter_error = RuntimeMaxIterationsError("max iterations reached")
    assert isinstance(max_iter_error, RuntimeError)

    timeout_error = RuntimeTimeoutError("timeout exceeded")
    assert isinstance(timeout_error, RuntimeError)


def test_session_errors():
    """Test session exception hierarchy."""
    base_error = SessionError("base error")
    assert isinstance(base_error, ScooperError)

    not_found = SessionNotFoundError("session not found")
    assert isinstance(not_found, SessionError)


def test_exception_messages():
    """Test that exception messages are preserved."""
    message = "This is a test error message"
    error = ScooperError(message)
    assert str(error) == message
    assert error.args[0] == message
