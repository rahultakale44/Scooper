"""Test tool system abstractions."""

import pytest

from scooper.exceptions import ToolExecutionError, ToolValidationError
from scooper.tools import Tool, ToolInput, ToolResult


class TestToolInput:
    """Test ToolInput validation."""

    def test_minimal_input(self):
        """Test creating input with minimal parameters."""
        tool_input = ToolInput()
        assert tool_input.metadata is None

    def test_input_with_metadata(self):
        """Test creating input with metadata."""
        tool_input = ToolInput(metadata={"key": "value"})
        assert tool_input.metadata == {"key": "value"}

    def test_input_allows_extra_fields(self):
        """Test that tool input allows extra fields for tool-specific params."""
        tool_input = ToolInput(custom_param="value", another_param=123)
        assert tool_input.custom_param == "value"
        assert tool_input.another_param == 123


class TestToolResult:
    """Test ToolResult validation."""

    def test_success_result(self):
        """Test creating a successful result."""
        result = ToolResult(success=True, output="Success output")
        assert result.success is True
        assert result.output == "Success output"
        assert result.error is None

    def test_failure_result(self):
        """Test creating a failure result."""
        result = ToolResult(success=False, error="Something went wrong")
        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.output is None

    def test_result_with_metadata(self):
        """Test result with metadata."""
        result = ToolResult(
            success=True,
            output="data",
            metadata={"execution_time": 0.5},
        )
        assert result.metadata == {"execution_time": 0.5}

    def test_result_immutable(self):
        """Test that result is immutable."""
        result = ToolResult(success=True, output="test")
        with pytest.raises(Exception):  # Pydantic ValidationError
            result.success = False


class SimpleTool(Tool):
    """A simple test tool implementation."""

    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.execution_count = 0

    @property
    def name(self) -> str:
        return "simple_tool"

    @property
    def description(self) -> str:
        return "A simple tool for testing"

    async def execute(self, tool_input: ToolInput) -> ToolResult:
        self.execution_count += 1

        if self.should_fail:
            raise ToolExecutionError("Tool execution failed")

        return ToolResult(
            success=True,
            output=f"Executed successfully (count: {self.execution_count})",
            metadata={"execution_count": self.execution_count},
        )

    def validate_input(self, tool_input: ToolInput) -> bool:
        if not isinstance(tool_input, ToolInput):
            raise ToolValidationError("Invalid input type")
        return True


class TestToolAbstraction:
    """Test the Tool abstraction with a concrete implementation."""

    def test_tool_properties(self):
        """Test that tool properties are accessible."""
        tool = SimpleTool()
        assert tool.name == "simple_tool"
        assert tool.description == "A simple tool for testing"

    @pytest.mark.asyncio
    async def test_successful_execution(self):
        """Test successful tool execution."""
        tool = SimpleTool()
        tool_input = ToolInput()

        result = await tool.execute(tool_input)

        assert result.success is True
        assert "Executed successfully" in result.output
        assert result.error is None

    @pytest.mark.asyncio
    async def test_failed_execution(self):
        """Test failed tool execution."""
        tool = SimpleTool(should_fail=True)
        tool_input = ToolInput()

        with pytest.raises(ToolExecutionError) as exc_info:
            await tool.execute(tool_input)

        assert "Tool execution failed" in str(exc_info.value)

    def test_input_validation(self):
        """Test input validation."""
        tool = SimpleTool()
        tool_input = ToolInput()

        is_valid = tool.validate_input(tool_input)
        assert is_valid is True

    def test_input_validation_failure(self):
        """Test input validation failure."""
        tool = SimpleTool()

        with pytest.raises(ToolValidationError):
            tool.validate_input("invalid input")

    @pytest.mark.asyncio
    async def test_multiple_executions(self):
        """Test that tool can be executed multiple times."""
        tool = SimpleTool()

        result1 = await tool.execute(ToolInput())
        result2 = await tool.execute(ToolInput())

        assert result1.metadata["execution_count"] == 1
        assert result2.metadata["execution_count"] == 2
