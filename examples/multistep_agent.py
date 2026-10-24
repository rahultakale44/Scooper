"""
Multi-step agent execution with tool integration example.

This example demonstrates:
- Multi-step agent execution loop
- Tool calls and results
- Scripted model responses for predictable behavior
- Multiple sequential tool calls
- Error handling (unknown tools, validation errors)
"""

import asyncio

from scooper.config import ModelProviderConfig, ScooperConfig
from scooper.models import FakeModelProvider, ModelResponse, ToolCall
from scooper.runtime import Agent, AgentConfig, AgentExecutor
from scooper.tools import Tool, ToolInput, ToolRegistry, ToolResult


class SearchTool(Tool):
    """A simulated search tool."""

    @property
    def name(self) -> str:
        return "search"

    @property
    def description(self) -> str:
        return "Search for information on a given query"

    def validate_input(self, tool_input: ToolInput) -> bool:
        """Validate search input."""
        if not hasattr(tool_input, "query"):
            from scooper.exceptions import ToolValidationError

            raise ToolValidationError("Missing required parameter: query")
        return True

    async def execute(self, tool_input: ToolInput) -> ToolResult:
        """Execute search (simulated)."""
        query = tool_input.query
        # Simulate search results
        results = {
            "python": "Python is a high-level programming language known for its simplicity.",
            "ai": "Artificial Intelligence refers to the simulation of human intelligence in machines.",
            "agents": "AI agents are autonomous programs that can perform tasks on behalf of users.",
        }

        result = results.get(query.lower(), f"No results found for '{query}'")

        return ToolResult(
            success=True,
            output=result,
            metadata={"query": query, "source": "simulated_search"},
        )


class CalculatorTool(Tool):
    """A simple calculator tool."""

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return "Perform arithmetic calculations"

    def validate_input(self, tool_input: ToolInput) -> bool:
        """Validate calculator input."""
        required = ["operation", "a", "b"]
        for param in required:
            if not hasattr(tool_input, param):
                from scooper.exceptions import ToolValidationError

                raise ToolValidationError(f"Missing required parameter: {param}")

        valid_ops = ["add", "subtract", "multiply", "divide"]
        if tool_input.operation not in valid_ops:
            from scooper.exceptions import ToolValidationError

            raise ToolValidationError(f"Invalid operation. Must be one of: {', '.join(valid_ops)}")
        return True

    async def execute(self, tool_input: ToolInput) -> ToolResult:
        """Execute calculation."""
        op = tool_input.operation
        a = tool_input.a
        b = tool_input.b

        try:
            if op == "add":
                result = a + b
            elif op == "subtract":
                result = a - b
            elif op == "multiply":
                result = a * b
            elif op == "divide":
                if b == 0:
                    from scooper.exceptions import ToolExecutionError

                    raise ToolExecutionError("Division by zero")
                result = a / b

            return ToolResult(
                success=True,
                output=result,
                metadata={"operation": op, "operands": [a, b]},
            )
        except Exception as e:
            from scooper.exceptions import ToolExecutionError

            raise ToolExecutionError(f"Calculation failed: {e}") from e


async def example_immediate_completion():
    """Example: Agent completes task immediately without tools."""
    print("=" * 70)
    print("EXAMPLE 1: Immediate Completion")
    print("=" * 70)
    print("Task: Agent answers directly without needing tools\n")

    # Configure
    config = ScooperConfig(log_level="ERROR", max_iterations=5)
    provider_config = ModelProviderConfig(
        provider_type="fake",
        base_url="http://localhost",
        model_name="test-model",
    )

    # Create agent
    agent_config = AgentConfig(
        name="assistant",
        description="A helpful assistant",
        provider_config=provider_config,
        system_prompt="You are a helpful AI assistant.",
    )
    agent = Agent(agent_config)

    # Script a direct response
    provider = FakeModelProvider(response_content="Hello! I'm here to help you.")
    executor = AgentExecutor(config, provider)

    # Execute
    result = await executor.execute(agent, "Introduce yourself")

    print(f"✓ Success: {result.success}")
    print(f"  Output: {result.final_output}")
    print(f"  Iterations: {result.iterations}")
    print(f"  Tool calls: {result.tool_calls_made}")
    print(f"  Stop reason: {result.stop_reason}")
    print()


async def example_single_tool_call():
    """Example: Agent uses one tool then completes."""
    print("=" * 70)
    print("EXAMPLE 2: Single Tool Call")
    print("=" * 70)
    print("Task: Search for information and provide answer\n")

    # Configure
    config = ScooperConfig(log_level="ERROR", max_iterations=5)
    provider_config = ModelProviderConfig(
        provider_type="fake",
        base_url="http://localhost",
        model_name="test-model",
    )

    # Create agent with tools
    agent_config = AgentConfig(
        name="research_agent",
        description="An agent that can search for information",
        provider_config=provider_config,
        system_prompt="You are a research assistant with access to search tools.",
    )
    agent = Agent(agent_config)

    # Register tools
    registry = ToolRegistry()
    registry.register(SearchTool())

    # Script the conversation:
    # 1. Agent decides to use search tool
    # 2. Agent provides final answer after seeing results
    scripted_responses = [
        ModelResponse(
            response_type="tool_calls",
            content=None,
            tool_calls=[
                ToolCall(
                    id="call_1",
                    name="search",
                    arguments={"query": "python"},
                )
            ],
            finish_reason="tool_calls",
        ),
        ModelResponse(
            response_type="text",
            content="Python is a high-level programming language known for its simplicity. "
            "It's widely used for web development, data science, and automation.",
            tool_calls=None,
            finish_reason="completed",
        ),
    ]

    provider = FakeModelProvider(scripted_responses=scripted_responses)
    executor = AgentExecutor(config, provider, registry)

    # Execute
    result = await executor.execute(agent, "What is Python?")

    print(f"✓ Success: {result.success}")
    print(f"  Output: {result.final_output}")
    print(f"  Iterations: {result.iterations}")
    print(f"  Tool calls: {result.tool_calls_made}")
    print(f"  Stop reason: {result.stop_reason}")
    print()


async def example_multiple_tool_calls():
    """Example: Agent uses multiple tools in sequence."""
    print("=" * 70)
    print("EXAMPLE 3: Multiple Tool Calls")
    print("=" * 70)
    print("Task: Search and calculate in multiple steps\n")

    # Configure
    config = ScooperConfig(log_level="ERROR", max_iterations=10)
    provider_config = ModelProviderConfig(
        provider_type="fake",
        base_url="http://localhost",
        model_name="test-model",
    )

    # Create agent
    agent_config = AgentConfig(
        name="multi_tool_agent",
        description="An agent that uses multiple tools",
        provider_config=provider_config,
        system_prompt="You are an agent with search and calculation capabilities.",
    )
    agent = Agent(agent_config)

    # Register multiple tools
    registry = ToolRegistry()
    registry.register(SearchTool())
    registry.register(CalculatorTool())

    # Script a multi-step conversation
    scripted_responses = [
        # Step 1: Search for AI
        ModelResponse(
            response_type="tool_calls",
            content=None,
            tool_calls=[ToolCall(id="call_1", name="search", arguments={"query": "ai"})],
            finish_reason="tool_calls",
        ),
        # Step 2: Do a calculation
        ModelResponse(
            response_type="tool_calls",
            content=None,
            tool_calls=[
                ToolCall(
                    id="call_2",
                    name="calculator",
                    arguments={"operation": "multiply", "a": 7, "b": 6},
                )
            ],
            finish_reason="tool_calls",
        ),
        # Step 3: Search for agents
        ModelResponse(
            response_type="tool_calls",
            content=None,
            tool_calls=[ToolCall(id="call_3", name="search", arguments={"query": "agents"})],
            finish_reason="tool_calls",
        ),
        # Final: Provide complete answer
        ModelResponse(
            response_type="text",
            content="AI (Artificial Intelligence) refers to machine intelligence. "
            "AI agents are autonomous programs. By the way, 7 × 6 = 42!",
            tool_calls=None,
            finish_reason="completed",
        ),
    ]

    provider = FakeModelProvider(scripted_responses=scripted_responses)
    executor = AgentExecutor(config, provider, registry)

    # Execute
    result = await executor.execute(agent, "Tell me about AI agents and calculate 7 × 6")

    print(f"✓ Success: {result.success}")
    print(f"  Output: {result.final_output}")
    print(f"  Iterations: {result.iterations}")
    print(f"  Tool calls: {result.tool_calls_made}")
    print(f"  Stop reason: {result.stop_reason}")
    print()


async def example_tool_errors():
    """Example: Handling tool errors gracefully."""
    print("=" * 70)
    print("EXAMPLE 4: Tool Error Handling")
    print("=" * 70)
    print("Task: Agent handles unknown tools and validation errors\n")

    # Configure
    config = ScooperConfig(log_level="ERROR", max_iterations=5)
    provider_config = ModelProviderConfig(
        provider_type="fake",
        base_url="http://localhost",
        model_name="test-model",
    )

    # Create agent
    agent_config = AgentConfig(
        name="error_handling_agent",
        description="An agent that handles tool errors",
        provider_config=provider_config,
        system_prompt="You are an agent that can handle tool errors.",
    )
    agent = Agent(agent_config)

    # Register only calculator tool
    registry = ToolRegistry()
    registry.register(CalculatorTool())

    # Script scenarios with errors
    scripted_responses = [
        # Attempt to use unknown tool
        ModelResponse(
            response_type="tool_calls",
            content=None,
            tool_calls=[ToolCall(id="call_1", name="unknown_tool", arguments={})],
            finish_reason="tool_calls",
        ),
        # Attempt calculation with invalid arguments
        ModelResponse(
            response_type="tool_calls",
            content=None,
            tool_calls=[
                ToolCall(
                    id="call_2",
                    name="calculator",
                    arguments={"operation": "divide", "a": 10},  # Missing 'b'
                )
            ],
            finish_reason="tool_calls",
        ),
        # Attempt division by zero
        ModelResponse(
            response_type="tool_calls",
            content=None,
            tool_calls=[
                ToolCall(
                    id="call_3",
                    name="calculator",
                    arguments={"operation": "divide", "a": 10, "b": 0},
                )
            ],
            finish_reason="tool_calls",
        ),
        # Final response acknowledging errors
        ModelResponse(
            response_type="text",
            content="I encountered several errors with the tools, but I handled them gracefully. "
            "The unknown tool wasn't found, validation failed, and division by zero occurred.",
            tool_calls=None,
            finish_reason="completed",
        ),
    ]

    provider = FakeModelProvider(scripted_responses=scripted_responses)
    executor = AgentExecutor(config, provider, registry)

    # Execute
    result = await executor.execute(agent, "Try various tool operations")

    print(f"✓ Success: {result.success}")
    print(f"  Output: {result.final_output}")
    print(f"  Iterations: {result.iterations}")
    print(f"  Tool calls attempted: {result.tool_calls_made}")
    print(f"  Stop reason: {result.stop_reason}")
    print(f"  Note: All {result.tool_calls_made} tool calls had errors but were handled")
    print()


async def example_max_iterations():
    """Example: Execution stops at max iterations."""
    print("=" * 70)
    print("EXAMPLE 5: Max Iterations Limit")
    print("=" * 70)
    print("Task: Agent exceeds maximum allowed iterations\n")

    # Configure with low max iterations
    config = ScooperConfig(log_level="ERROR", max_iterations=3)
    provider_config = ModelProviderConfig(
        provider_type="fake",
        base_url="http://localhost",
        model_name="test-model",
    )

    # Create agent
    agent_config = AgentConfig(
        name="limited_agent",
        description="An agent with iteration limit",
        provider_config=provider_config,
        system_prompt="You are an agent with limited iterations.",
    )
    agent = Agent(agent_config)

    # Register tool
    registry = ToolRegistry()
    registry.register(SearchTool())

    # Script many tool calls (more than max_iterations allows)
    scripted_responses = [
        ModelResponse(
            response_type="tool_calls",
            content=None,
            tool_calls=[ToolCall(id=f"call_{i}", name="search", arguments={"query": "test"})],
            finish_reason="tool_calls",
        )
        for i in range(10)  # More than max_iterations
    ]

    provider = FakeModelProvider(scripted_responses=scripted_responses)
    executor = AgentExecutor(config, provider, registry)

    # Execute
    result = await executor.execute(agent, "Search repeatedly")

    print(f"✗ Success: {result.success}")
    print(f"  Error: {result.error}")
    print(f"  Iterations: {result.iterations} (limit: {config.max_iterations})")
    print(f"  Tool calls made: {result.tool_calls_made}")
    print(f"  Stop reason: {result.stop_reason}")
    print()


async def main():
    """Run all examples."""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "MULTI-STEP AGENT EXECUTION EXAMPLES" + " " * 18 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    await example_immediate_completion()
    await example_single_tool_call()
    await example_multiple_tool_calls()
    await example_tool_errors()
    await example_max_iterations()

    print("=" * 70)
    print("ALL EXAMPLES COMPLETE")
    print("=" * 70)
    print()
    print("Key Takeaways:")
    print("• Agents can complete tasks immediately or use tools iteratively")
    print("• Tool errors are captured and returned to the agent as messages")
    print("• Max iteration limits prevent infinite loops")
    print("• Multi-step execution enables complex task decomposition")
    print()


if __name__ == "__main__":
    asyncio.run(main())
