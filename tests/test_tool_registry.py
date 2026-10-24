"""Tests for tool registry and execution."""

import asyncio

import pytest

from scooper.exceptions import (
    ToolExecutionError,
    ToolNotFoundError,
    ToolValidationError,
)
from scooper.tools import Tool, ToolInput, ToolResult, ToolRegistry


class CalculatorTool(Tool):
    """A simple calculator tool for testing."""

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return "Performs basic arithmetic operations"

    def validate_input(self, tool_input: ToolInput) -> bool:
        """Validate calculator input."""
        if not hasattr(tool_input, "operation"):
            raise ToolValidationError("Missing required parameter: operation")
        if not hasattr(tool_input, "a"):
            raise ToolValidationError("Missing required parameter: a")
        if not hasattr(tool_input, "b"):
            raise ToolValidationError("Missing required parameter: b")

        valid_ops = ["add", "subtract", "multiply", "divide"]
        if tool_input.operation not in valid_ops:
            raise ToolValidationError(
                f"Invalid operation. Must be one of: {', '.join(valid_ops)}"
            )
        return True

    async def execute(self, tool_input: ToolInput) -> ToolResult:
        """Execute calculator operation."""
        a = tool_input.a
        b = tool_input.b
        op = tool_input.operation

        try:
            if op == "add":
                result = a + b
            elif op == "subtract":
                result = a - b
            elif op == "multiply":
                result = a * b
            elif op == "divide":
                if b == 0:
                    raise ToolExecutionError("Division by zero")
                result = a / b
            else:
                raise ToolExecutionError(f"Unknown operation: {op}")

            return ToolResult(
                success=True,
                output=result,
                metadata={"operation": op, "a": a, "b": b},
            )
        except ToolExecutionError:
            raise
        except Exception as e:
            raise ToolExecutionError(f"Calculation failed: {e}") from e


class SlowTool(Tool):
    """A tool that takes time to execute, for timeout testing."""

    def __init__(self, delay: float = 1.0):
        self.delay = delay

    @property
    def name(self) -> str:
        return "slow_tool"

    @property
    def description(self) -> str:
        return "A tool that sleeps for a specified duration"

    def validate_input(self, tool_input: ToolInput) -> bool:
        return True

    async def execute(self, tool_input: ToolInput) -> ToolResult:
        """Execute with delay."""
        await asyncio.sleep(self.delay)
        return ToolResult(success=True, output=f"Slept for {self.delay}s")


class FailingTool(Tool):
    """A tool that always fails, for error testing."""

    @property
    def name(self) -> str:
        return "failing_tool"

    @property
    def description(self) -> str:
        return "A tool that always raises an error"

    def validate_input(self, tool_input: ToolInput) -> bool:
        return True

    async def execute(self, tool_input: ToolInput) -> ToolResult:
        """Always fails."""
        raise ToolExecutionError("This tool always fails")


class TestToolRegistry:
    """Test ToolRegistry functionality."""

    def test_registry_initialization(self):
        """Test creating a registry."""
        registry = ToolRegistry()
        assert len(registry) == 0
        assert registry.default_timeout == 30.0

        registry_custom = ToolRegistry(default_timeout=60.0)
        assert registry_custom.default_timeout == 60.0

    def test_register_tool(self):
        """Test registering a tool."""
        registry = ToolRegistry()
        tool = CalculatorTool()

        registry.register(tool)
        assert len(registry) == 1
        assert registry.has_tool("calculator")
        assert "calculator" in registry

    def test_register_duplicate_tool(self):
        """Test that duplicate registration raises an error."""
        registry = ToolRegistry()
        tool1 = CalculatorTool()
        tool2 = CalculatorTool()

        registry.register(tool1)
        with pytest.raises(ValueError) as exc_info:
            registry.register(tool2)

        assert "already registered" in str(exc_info.value)

    def test_get_tool(self):
        """Test getting a registered tool."""
        registry = ToolRegistry()
        tool = CalculatorTool()
        registry.register(tool)

        retrieved = registry.get("calculator")
        assert retrieved is tool
        assert retrieved.name == "calculator"

    def test_get_nonexistent_tool(self):
        """Test getting a tool that doesn't exist."""
        registry = ToolRegistry()

        with pytest.raises(ToolNotFoundError) as exc_info:
            registry.get("nonexistent")

        assert "not found" in str(exc_info.value)
        assert "Available tools: none" in str(exc_info.value)

    def test_get_nonexistent_tool_with_suggestions(self):
        """Test error message includes available tools."""
        registry = ToolRegistry()
        registry.register(CalculatorTool())

        with pytest.raises(ToolNotFoundError) as exc_info:
            registry.get("missing")

        assert "calculator" in str(exc_info.value)

    def test_unregister_tool(self):
        """Test unregistering a tool."""
        registry = ToolRegistry()
        tool = CalculatorTool()
        registry.register(tool)

        assert len(registry) == 1
        registry.unregister("calculator")
        assert len(registry) == 0
        assert not registry.has_tool("calculator")

    def test_unregister_nonexistent_tool(self):
        """Test unregistering a tool that doesn't exist."""
        registry = ToolRegistry()

        with pytest.raises(ToolNotFoundError):
            registry.unregister("nonexistent")

    def test_list_tools(self):
        """Test listing registered tools."""
        registry = ToolRegistry()
        assert registry.list_tools() == []

        registry.register(CalculatorTool())
        registry.register(SlowTool())

        tools = registry.list_tools()
        assert tools == ["calculator", "slow_tool"]  # Alphabetically sorted
        assert len(tools) == 2

    def test_has_tool(self):
        """Test checking if a tool exists."""
        registry = ToolRegistry()
        assert not registry.has_tool("calculator")

        registry.register(CalculatorTool())
        assert registry.has_tool("calculator")
        assert not registry.has_tool("missing")

    def test_clear_registry(self):
        """Test clearing all tools."""
        registry = ToolRegistry()
        registry.register(CalculatorTool())
        registry.register(SlowTool())

        assert len(registry) == 2
        registry.clear()
        assert len(registry) == 0
        assert registry.list_tools() == []

    def test_registry_repr(self):
        """Test string representation."""
        registry = ToolRegistry()
        repr_str = repr(registry)

        assert "ToolRegistry" in repr_str
        assert "tools=0" in repr_str
        assert "30.0s" in repr_str

    @pytest.mark.asyncio
    async def test_execute_successful_tool(self):
        """Test executing a tool successfully."""
        registry = ToolRegistry()
        registry.register(CalculatorTool())

        tool_input = ToolInput(operation="add", a=5, b=3)
        result = await registry.execute("calculator", tool_input)

        assert result.success is True
        assert result.output == 8
        assert result.error is None
        assert result.metadata["operation"] == "add"

    @pytest.mark.asyncio
    async def test_execute_various_operations(self):
        """Test different calculator operations."""
        registry = ToolRegistry()
        registry.register(CalculatorTool())

        # Addition
        result = await registry.execute("calculator", ToolInput(operation="add", a=10, b=5))
        assert result.output == 15

        # Subtraction
        result = await registry.execute(
            "calculator", ToolInput(operation="subtract", a=10, b=5)
        )
        assert result.output == 5

        # Multiplication
        result = await registry.execute(
            "calculator", ToolInput(operation="multiply", a=10, b=5)
        )
        assert result.output == 50

        # Division
        result = await registry.execute(
            "calculator", ToolInput(operation="divide", a=10, b=5)
        )
        assert result.output == 2.0

    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool(self):
        """Test executing a tool that doesn't exist."""
        registry = ToolRegistry()

        with pytest.raises(ToolNotFoundError):
            await registry.execute("missing", ToolInput())

    @pytest.mark.asyncio
    async def test_execute_with_validation_error(self):
        """Test execution fails when validation fails."""
        registry = ToolRegistry()
        registry.register(CalculatorTool())

        # Missing required parameters
        with pytest.raises(ToolValidationError) as exc_info:
            await registry.execute("calculator", ToolInput())

        assert "Missing required parameter" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_with_invalid_operation(self):
        """Test validation catches invalid operation."""
        registry = ToolRegistry()
        registry.register(CalculatorTool())

        with pytest.raises(ToolValidationError) as exc_info:
            await registry.execute(
                "calculator", ToolInput(operation="invalid", a=1, b=2)
            )

        assert "Invalid operation" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_with_tool_error(self):
        """Test execution handles tool execution errors."""
        registry = ToolRegistry()
        registry.register(CalculatorTool())

        # Division by zero
        with pytest.raises(ToolExecutionError) as exc_info:
            await registry.execute(
                "calculator", ToolInput(operation="divide", a=10, b=0)
            )

        assert "Division by zero" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self):
        """Test execution timeout."""
        registry = ToolRegistry(default_timeout=0.5)
        registry.register(SlowTool(delay=2.0))

        with pytest.raises(ToolExecutionError) as exc_info:
            await registry.execute("slow_tool", ToolInput())

        assert "exceeded timeout" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_with_custom_timeout(self):
        """Test execution with custom timeout."""
        registry = ToolRegistry(default_timeout=0.1)
        registry.register(SlowTool(delay=0.3))

        # Should timeout with default
        with pytest.raises(ToolExecutionError):
            await registry.execute("slow_tool", ToolInput())

        # Should succeed with longer timeout
        result = await registry.execute("slow_tool", ToolInput(), timeout=1.0)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_failing_tool(self):
        """Test execution handles tool that always fails."""
        registry = ToolRegistry()
        registry.register(FailingTool())

        with pytest.raises(ToolExecutionError) as exc_info:
            await registry.execute("failing_tool", ToolInput())

        assert "always fails" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_multiple_executions(self):
        """Test executing multiple tools sequentially."""
        registry = ToolRegistry()
        registry.register(CalculatorTool())

        result1 = await registry.execute("calculator", ToolInput(operation="add", a=1, b=2))
        result2 = await registry.execute(
            "calculator", ToolInput(operation="multiply", a=3, b=4)
        )

        assert result1.output == 3
        assert result2.output == 12

    def test_registry_isolation(self):
        """Test that separate registries are independent."""
        registry1 = ToolRegistry()
        registry2 = ToolRegistry()

        registry1.register(CalculatorTool())

        assert len(registry1) == 1
        assert len(registry2) == 0
        assert registry1.has_tool("calculator")
        assert not registry2.has_tool("calculator")
