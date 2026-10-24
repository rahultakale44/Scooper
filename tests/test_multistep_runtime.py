"""Tests for multi-step agent runtime with tool integration."""

import pytest

from scooper.config import ModelProviderConfig, ScooperConfig
from scooper.models import (
    FakeModelProvider,
    ModelResponse,
    ToolCall,
)
from scooper.runtime import Agent, AgentConfig, AgentExecutor
from scooper.tools import Tool, ToolInput, ToolRegistry, ToolResult


class CounterTool(Tool):
    """A simple counter tool for testing."""

    def __init__(self):
        self.call_count = 0

    @property
    def name(self) -> str:
        return "counter"

    @property
    def description(self) -> str:
        return "Increments and returns a counter"

    def validate_input(self, tool_input: ToolInput) -> bool:
        return True

    async def execute(self, tool_input: ToolInput) -> ToolResult:
        """Increment counter and return result."""
        self.call_count += 1
        return ToolResult(
            success=True,
            output=f"Counter: {self.call_count}",
            metadata={"count": self.call_count},
        )


class EchoTool(Tool):
    """A tool that echoes its input."""

    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echoes the input message"

    def validate_input(self, tool_input: ToolInput) -> bool:
        if not hasattr(tool_input, "message"):
            from scooper.exceptions import ToolValidationError

            raise ToolValidationError("Missing required parameter: message")
        return True

    async def execute(self, tool_input: ToolInput) -> ToolResult:
        """Echo the input message."""
        return ToolResult(
            success=True,
            output=f"Echo: {tool_input.message}",
        )


class FailingTool(Tool):
    """A tool that always fails."""

    @property
    def name(self) -> str:
        return "failing"

    @property
    def description(self) -> str:
        return "A tool that always fails"

    def validate_input(self, tool_input: ToolInput) -> bool:
        return True

    async def execute(self, tool_input: ToolInput) -> ToolResult:
        """Always fails."""
        from scooper.exceptions import ToolExecutionError

        raise ToolExecutionError("This tool always fails")


@pytest.fixture
def config():
    """Create a test config."""
    return ScooperConfig(log_level="ERROR", max_iterations=5)


@pytest.fixture
def agent_config():
    """Create a test agent config."""
    return AgentConfig(
        name="test_agent",
        description="Test agent",
        provider_config=ModelProviderConfig(
            provider_type="fake",
            base_url="http://localhost",
            model_name="test-model",
        ),
        system_prompt="You are a test agent.",
    )


@pytest.fixture
def tool_registry():
    """Create a test tool registry."""
    registry = ToolRegistry()
    registry.register(CounterTool())
    registry.register(EchoTool())
    return registry


class TestMultiStepExecution:
    """Test multi-step execution with tool integration."""

    @pytest.mark.asyncio
    async def test_immediate_text_response(self, config, agent_config):
        """Test execution that returns text immediately without tool calls."""
        provider = FakeModelProvider(response_content="Task completed successfully")
        executor = AgentExecutor(config, provider)
        agent = Agent(agent_config)

        result = await executor.execute(agent, "Complete this task")

        assert result.success is True
        assert result.final_output == "Task completed successfully"
        assert result.iterations == 1
        assert result.stop_reason == "completed"
        assert result.tool_calls_made == 0

    @pytest.mark.asyncio
    async def test_single_tool_call_then_response(self, config, agent_config, tool_registry):
        """Test execution with one tool call followed by final response."""
        # Script: tool call -> text response
        scripted_responses = [
            ModelResponse(
                response_type="tool_calls",
                content=None,
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="counter",
                        arguments={},
                    )
                ],
                finish_reason="tool_calls",
            ),
            ModelResponse(
                response_type="text",
                content="Counter was incremented. Task done.",
                tool_calls=None,
                finish_reason="completed",
            ),
        ]

        provider = FakeModelProvider(scripted_responses=scripted_responses)
        executor = AgentExecutor(config, provider, tool_registry)
        agent = Agent(agent_config)

        result = await executor.execute(agent, "Use the counter")

        assert result.success is True
        assert result.final_output == "Counter was incremented. Task done."
        assert result.iterations == 2
        assert result.stop_reason == "completed"
        assert result.tool_calls_made == 1

    @pytest.mark.asyncio
    async def test_multiple_tool_calls(self, config, agent_config, tool_registry):
        """Test execution with multiple sequential tool calls."""
        scripted_responses = [
            # First: call counter
            ModelResponse(
                response_type="tool_calls",
                content=None,
                tool_calls=[
                    ToolCall(id="call_1", name="counter", arguments={}),
                ],
                finish_reason="tool_calls",
            ),
            # Second: call echo
            ModelResponse(
                response_type="tool_calls",
                content=None,
                tool_calls=[
                    ToolCall(id="call_2", name="echo", arguments={"message": "hello"}),
                ],
                finish_reason="tool_calls",
            ),
            # Final: text response
            ModelResponse(
                response_type="text",
                content="All tools executed successfully",
                tool_calls=None,
                finish_reason="completed",
            ),
        ]

        provider = FakeModelProvider(scripted_responses=scripted_responses)
        executor = AgentExecutor(config, provider, tool_registry)
        agent = Agent(agent_config)

        result = await executor.execute(agent, "Use counter and echo")

        assert result.success is True
        assert result.final_output == "All tools executed successfully"
        assert result.iterations == 3
        assert result.stop_reason == "completed"
        assert result.tool_calls_made == 2

    @pytest.mark.asyncio
    async def test_multiple_tools_in_one_call(self, config, agent_config, tool_registry):
        """Test execution with multiple tools called in parallel."""
        scripted_responses = [
            ModelResponse(
                response_type="tool_calls",
                content=None,
                tool_calls=[
                    ToolCall(id="call_1", name="counter", arguments={}),
                    ToolCall(id="call_2", name="echo", arguments={"message": "test"}),
                ],
                finish_reason="tool_calls",
            ),
            ModelResponse(
                response_type="text",
                content="Both tools executed",
                tool_calls=None,
                finish_reason="completed",
            ),
        ]

        provider = FakeModelProvider(scripted_responses=scripted_responses)
        executor = AgentExecutor(config, provider, tool_registry)
        agent = Agent(agent_config)

        result = await executor.execute(agent, "Run tools")

        assert result.success is True
        assert result.iterations == 2
        assert result.tool_calls_made == 2

    @pytest.mark.asyncio
    async def test_tool_call_without_registry(self, config, agent_config):
        """Test that tool calls fail gracefully when no registry is configured."""
        scripted_responses = [
            ModelResponse(
                response_type="tool_calls",
                content=None,
                tool_calls=[
                    ToolCall(id="call_1", name="counter", arguments={}),
                ],
                finish_reason="tool_calls",
            ),
        ]

        provider = FakeModelProvider(scripted_responses=scripted_responses)
        executor = AgentExecutor(config, provider, tool_registry=None)
        agent = Agent(agent_config)

        result = await executor.execute(agent, "Use a tool")

        assert result.success is False
        assert result.stop_reason == "no_tool_registry"
        assert "no tool registry is configured" in result.error.lower()
        assert result.iterations == 1
        assert result.tool_calls_made == 0

    @pytest.mark.asyncio
    async def test_unknown_tool_call(self, config, agent_config, tool_registry):
        """Test execution when model requests an unknown tool."""
        scripted_responses = [
            ModelResponse(
                response_type="tool_calls",
                content=None,
                tool_calls=[
                    ToolCall(id="call_1", name="unknown_tool", arguments={}),
                ],
                finish_reason="tool_calls",
            ),
            ModelResponse(
                response_type="text",
                content="Handled the error and completed",
                tool_calls=None,
                finish_reason="completed",
            ),
        ]

        provider = FakeModelProvider(scripted_responses=scripted_responses)
        executor = AgentExecutor(config, provider, tool_registry)
        agent = Agent(agent_config)

        result = await executor.execute(agent, "Use unknown tool")

        # Tool error is returned as a message, execution continues
        assert result.success is True
        assert result.iterations == 2
        assert result.tool_calls_made == 1  # Attempted

    @pytest.mark.asyncio
    async def test_tool_validation_error(self, config, agent_config, tool_registry):
        """Test execution when tool input validation fails."""
        scripted_responses = [
            ModelResponse(
                response_type="tool_calls",
                content=None,
                tool_calls=[
                    ToolCall(id="call_1", name="echo", arguments={}),  # Missing 'message'
                ],
                finish_reason="tool_calls",
            ),
            ModelResponse(
                response_type="text",
                content="Handled validation error",
                tool_calls=None,
                finish_reason="completed",
            ),
        ]

        provider = FakeModelProvider(scripted_responses=scripted_responses)
        executor = AgentExecutor(config, provider, tool_registry)
        agent = Agent(agent_config)

        result = await executor.execute(agent, "Echo without message")

        # Validation error is returned as a message, execution continues
        assert result.success is True
        assert result.iterations == 2
        assert result.tool_calls_made == 1

    @pytest.mark.asyncio
    async def test_tool_execution_error(self, config, agent_config):
        """Test execution when tool execution fails."""
        registry = ToolRegistry()
        registry.register(FailingTool())

        scripted_responses = [
            ModelResponse(
                response_type="tool_calls",
                content=None,
                tool_calls=[
                    ToolCall(id="call_1", name="failing", arguments={}),
                ],
                finish_reason="tool_calls",
            ),
            ModelResponse(
                response_type="text",
                content="Handled execution error",
                tool_calls=None,
                finish_reason="completed",
            ),
        ]

        provider = FakeModelProvider(scripted_responses=scripted_responses)
        executor = AgentExecutor(config, provider, registry)
        agent = Agent(agent_config)

        result = await executor.execute(agent, "Use failing tool")

        # Execution error is returned as a message, execution continues
        assert result.success is True
        assert result.iterations == 2
        assert result.tool_calls_made == 1

    @pytest.mark.asyncio
    async def test_max_iterations_exceeded(self, config, agent_config, tool_registry):
        """Test that execution stops when max iterations is reached."""
        # Create responses that never complete (always tool calls)
        scripted_responses = [
            ModelResponse(
                response_type="tool_calls",
                content=None,
                tool_calls=[ToolCall(id=f"call_{i}", name="counter", arguments={})],
                finish_reason="tool_calls",
            )
            for i in range(10)  # More than max_iterations (5)
        ]

        provider = FakeModelProvider(scripted_responses=scripted_responses)
        executor = AgentExecutor(config, provider, tool_registry)
        agent = Agent(agent_config)

        result = await executor.execute(agent, "Never stop")

        assert result.success is False
        assert result.stop_reason == "max_iterations"
        assert "maximum iterations" in result.error.lower()
        assert result.iterations == config.max_iterations
        assert result.tool_calls_made == config.max_iterations

    @pytest.mark.asyncio
    async def test_agent_level_max_iterations(self, config, tool_registry):
        """Test that agent-level max_iterations overrides global config."""
        agent_config = AgentConfig(
            name="test_agent",
            description="Test agent",
            provider_config=ModelProviderConfig(
                provider_type="fake",
                base_url="http://localhost",
                model_name="test-model",
            ),
            system_prompt="You are a test agent.",
            max_iterations=2,  # Override global (5)
        )

        # Create responses that never complete
        scripted_responses = [
            ModelResponse(
                response_type="tool_calls",
                content=None,
                tool_calls=[ToolCall(id=f"call_{i}", name="counter", arguments={})],
                finish_reason="tool_calls",
            )
            for i in range(10)
        ]

        provider = FakeModelProvider(scripted_responses=scripted_responses)
        executor = AgentExecutor(config, provider, tool_registry)
        agent = Agent(agent_config)

        result = await executor.execute(agent, "Never stop")

        assert result.success is False
        assert result.stop_reason == "max_iterations"
        assert result.iterations == 2  # Agent level override

    @pytest.mark.asyncio
    async def test_conversation_history_building(self, config, agent_config, tool_registry):
        """Test that conversation history is built correctly."""
        counter_tool = CounterTool()
        registry = ToolRegistry()
        registry.register(counter_tool)

        scripted_responses = [
            ModelResponse(
                response_type="tool_calls",
                content=None,
                tool_calls=[ToolCall(id="call_1", name="counter", arguments={})],
                finish_reason="tool_calls",
            ),
            ModelResponse(
                response_type="text",
                content="Final answer",
                tool_calls=None,
                finish_reason="completed",
            ),
        ]

        provider = FakeModelProvider(scripted_responses=scripted_responses)
        executor = AgentExecutor(config, provider, registry)
        agent = Agent(agent_config)

        result = await executor.execute(agent, "Test")

        assert result.success is True
        # Verify counter was actually called
        assert counter_tool.call_count == 1

    @pytest.mark.asyncio
    async def test_unhealthy_provider(self, config, agent_config, tool_registry):
        """Test execution with unhealthy provider."""
        provider = FakeModelProvider(fail_health_check=True)
        executor = AgentExecutor(config, provider, tool_registry)
        agent = Agent(agent_config)

        result = await executor.execute(agent, "Test")

        assert result.success is False
        assert result.stop_reason == "provider_unhealthy"
        assert result.iterations == 0
        assert result.tool_calls_made == 0

    @pytest.mark.asyncio
    async def test_state_isolation_between_runs(self, config, agent_config, tool_registry):
        """Test that separate executions don't share state."""
        scripted_responses = [
            ModelResponse(
                response_type="text",
                content="Run 1",
                tool_calls=None,
                finish_reason="completed",
            ),
        ]

        provider = FakeModelProvider(scripted_responses=scripted_responses)
        executor = AgentExecutor(config, provider, tool_registry)
        agent = Agent(agent_config)

        # Run 1
        result1 = await executor.execute(agent, "Task 1")
        assert result1.success is True

        # Reset provider for run 2
        provider.response_index = 0

        # Run 2
        result2 = await executor.execute(agent, "Task 2")
        assert result2.success is True

        # Both runs should be independent
        assert result1.iterations == 1
        assert result2.iterations == 1


class TestToolCallConversation:
    """Test conversation message formatting with tool calls."""

    @pytest.mark.asyncio
    async def test_tool_message_format(self, config, agent_config, tool_registry):
        """Test that tool messages are formatted correctly."""
        scripted_responses = [
            ModelResponse(
                response_type="tool_calls",
                content=None,
                tool_calls=[
                    ToolCall(id="call_123", name="echo", arguments={"message": "test"}),
                ],
                finish_reason="tool_calls",
            ),
            ModelResponse(
                response_type="text",
                content="Done",
                tool_calls=None,
                finish_reason="completed",
            ),
        ]

        provider = FakeModelProvider(scripted_responses=scripted_responses)
        executor = AgentExecutor(config, provider, tool_registry)
        agent = Agent(agent_config)

        result = await executor.execute(agent, "Echo test")

        assert result.success is True
        assert result.tool_calls_made == 1
