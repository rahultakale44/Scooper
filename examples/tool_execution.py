"""
Tool execution example for Scooper.

This example demonstrates how to:
- Create custom tools
- Register tools in a registry
- Execute tools with validation
- Handle tool execution results
"""

import asyncio

from scooper.exceptions import ToolExecutionError, ToolValidationError
from scooper.tools import Tool, ToolInput, ToolRegistry, ToolResult


class GreetingTool(Tool):
    """A simple tool that generates personalized greetings."""

    @property
    def name(self) -> str:
        return "greeting"

    @property
    def description(self) -> str:
        return "Generates a personalized greeting message"

    def validate_input(self, tool_input: ToolInput) -> bool:
        """Validate that a name parameter is provided."""
        if not hasattr(tool_input, "name"):
            raise ToolValidationError("Missing required parameter: name")
        if not tool_input.name or not tool_input.name.strip():
            raise ToolValidationError("Parameter 'name' cannot be empty")
        return True

    async def execute(self, tool_input: ToolInput) -> ToolResult:
        """Generate a greeting."""
        name = tool_input.name.strip()
        greeting_style = getattr(tool_input, "style", "formal")

        if greeting_style == "formal":
            message = f"Good day, {name}. How may I assist you?"
        elif greeting_style == "casual":
            message = f"Hey {name}! What's up?"
        elif greeting_style == "enthusiastic":
            message = f"Hello {name}! It's wonderful to see you!"
        else:
            message = f"Hello, {name}."

        return ToolResult(
            success=True,
            output=message,
            metadata={"name": name, "style": greeting_style},
        )


class CalculatorTool(Tool):
    """A calculator tool that performs basic arithmetic."""

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return "Performs basic arithmetic operations (add, subtract, multiply, divide)"

    def validate_input(self, tool_input: ToolInput) -> bool:
        """Validate calculator input."""
        required = ["operation", "a", "b"]
        for param in required:
            if not hasattr(tool_input, param):
                raise ToolValidationError(f"Missing required parameter: {param}")

        valid_ops = ["add", "subtract", "multiply", "divide"]
        if tool_input.operation not in valid_ops:
            raise ToolValidationError(
                f"Invalid operation '{tool_input.operation}'. "
                f"Must be one of: {', '.join(valid_ops)}"
            )

        return True

    async def execute(self, tool_input: ToolInput) -> ToolResult:
        """Execute the calculation."""
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
                    raise ToolExecutionError("Cannot divide by zero")
                result = a / b

            return ToolResult(
                success=True,
                output=result,
                metadata={"operation": op, "operands": [a, b]},
            )

        except ToolExecutionError:
            raise
        except Exception as e:
            raise ToolExecutionError(f"Calculation failed: {e}") from e


async def main() -> None:
    """Run tool execution examples."""
    print("=" * 70)
    print("SCOOPER TOOL EXECUTION EXAMPLE")
    print("=" * 70)
    print()

    # Create a tool registry
    registry = ToolRegistry(default_timeout=5.0)
    print(f"✓ Created tool registry: {registry}")
    print()

    # Register tools
    greeting_tool = GreetingTool()
    calculator_tool = CalculatorTool()

    registry.register(greeting_tool)
    registry.register(calculator_tool)
    print(f"✓ Registered {len(registry)} tools")
    print(f"  Available tools: {', '.join(registry.list_tools())}")
    print()

    # Example 1: Execute greeting tool
    print("=" * 70)
    print("Example 1: Greeting Tool")
    print("=" * 70)

    print("\n→ Formal greeting:")
    result = await registry.execute("greeting", ToolInput(name="Alice", style="formal"))
    print(f"  Success: {result.success}")
    print(f"  Output: {result.output}")

    print("\n→ Casual greeting:")
    result = await registry.execute("greeting", ToolInput(name="Bob", style="casual"))
    print(f"  Output: {result.output}")

    print("\n→ Enthusiastic greeting:")
    result = await registry.execute("greeting", ToolInput(name="Charlie", style="enthusiastic"))
    print(f"  Output: {result.output}")

    # Example 2: Execute calculator tool
    print("\n" + "=" * 70)
    print("Example 2: Calculator Tool")
    print("=" * 70)

    operations = [
        ("add", 15, 7),
        ("subtract", 20, 8),
        ("multiply", 6, 7),
        ("divide", 100, 4),
    ]

    for op, a, b in operations:
        result = await registry.execute("calculator", ToolInput(operation=op, a=a, b=b))
        print(f"\n→ {a} {op} {b} = {result.output}")

    # Example 3: Error handling
    print("\n" + "=" * 70)
    print("Example 3: Error Handling")
    print("=" * 70)

    # Missing parameter
    print("\n→ Test missing parameter:")
    try:
        await registry.execute("greeting", ToolInput())
    except ToolValidationError as e:
        print(f"  ✗ Validation Error: {e}")

    # Invalid operation
    print("\n→ Test invalid operation:")
    try:
        await registry.execute("calculator", ToolInput(operation="power", a=2, b=3))
    except ToolValidationError as e:
        print(f"  ✗ Validation Error: {e}")

    # Division by zero
    print("\n→ Test division by zero:")
    try:
        await registry.execute("calculator", ToolInput(operation="divide", a=10, b=0))
    except ToolExecutionError as e:
        print(f"  ✗ Execution Error: {e}")

    # Tool not found
    print("\n→ Test unknown tool:")
    try:
        await registry.execute("unknown_tool", ToolInput())
    except Exception as e:
        print(f"  ✗ Error: {e}")

    # Example 4: Registry management
    print("\n" + "=" * 70)
    print("Example 4: Registry Management")
    print("=" * 70)

    print(f"\n→ Current tools: {registry.list_tools()}")
    print(f"  Total: {len(registry)} tools")

    print("\n→ Check tool existence:")
    print(f"  'calculator' exists: {registry.has_tool('calculator')}")
    print(f"  'unknown' exists: {registry.has_tool('unknown')}")

    print("\n→ Unregister greeting tool:")
    registry.unregister("greeting")
    print(f"  Remaining tools: {registry.list_tools()}")

    print()
    print("=" * 70)
    print("EXAMPLE COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
