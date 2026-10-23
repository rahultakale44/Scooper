"""Test agent runtime and execution."""

import pytest
from pydantic import ValidationError

from scooper.config import ModelProviderConfig, ScooperConfig
from scooper.models import FakeModelProvider
from scooper.runtime import Agent, AgentConfig, AgentExecutor, ExecutionResult


class TestAgentConfig:
    """Test AgentConfig validation."""

    def test_minimal_config(self):
        """Test creating config with minimal parameters."""
        model_config = ModelProviderConfig(
            provider_type="fake",
            base_url="http://localhost:8000",
            model_name="test-model",
        )

        config = AgentConfig(
            name="test-agent",
            model_config=model_config,
        )

        assert config.name == "test-agent"
        assert config.description == ""
        assert config.system_prompt == "You are a helpful AI agent."
        assert config.max_iterations is None

    def test_full_config(self):
        """Test creating config with all parameters."""
        model_config = ModelProviderConfig(
            provider_type="fake",
            base_url="http://localhost:8000",
            model_name="test-model",
        )

        config = AgentConfig(
            name="custom-agent",
            description="A custom test agent",
            model_config=model_config,
            system_prompt="You are a specialized agent.",
            max_iterations=5,
        )

        assert config.name == "custom-agent"
        assert config.description == "A custom test agent"
        assert config.system_prompt == "You are a specialized agent."
        assert config.max_iterations == 5

    def test_config_immutable(self):
        """Test that config is immutable."""
        model_config = ModelProviderConfig(
            provider_type="fake",
            base_url="http://localhost:8000",
            model_name="test-model",
        )

        config = AgentConfig(name="test", model_config=model_config)

        with pytest.raises(ValidationError):
            config.name = "new-name"

    def test_max_iterations_bounds(self):
        """Test max_iterations validation."""
        model_config = ModelProviderConfig(
            provider_type="fake",
            base_url="http://localhost:8000",
            model_name="test-model",
        )

        # Valid values
        AgentConfig(name="test", model_config=model_config, max_iterations=1)
        AgentConfig(name="test", model_config=model_config, max_iterations=100)

        # Invalid values
        with pytest.raises(ValidationError):
            AgentConfig(name="test", model_config=model_config, max_iterations=0)

        with pytest.raises(ValidationError):
            AgentConfig(name="test", model_config=model_config, max_iterations=101)


class TestAgent:
    """Test Agent class."""

    def test_agent_creation(self):
        """Test creating an agent."""
        model_config = ModelProviderConfig(
            provider_type="fake",
            base_url="http://localhost:8000",
            model_name="test-model",
        )

        agent_config = AgentConfig(
            name="test-agent",
            description="Test description",
            model_config=model_config,
        )

        agent = Agent(config=agent_config)

        assert agent.name == "test-agent"
        assert agent.description == "Test description"
        assert agent.system_prompt == "You are a helpful AI agent."

    def test_agent_properties(self):
        """Test agent property access."""
        model_config = ModelProviderConfig(
            provider_type="fake",
            base_url="http://localhost:8000",
            model_name="test-model",
        )

        agent_config = AgentConfig(
            name="prop-agent",
            description="Property test",
            model_config=model_config,
            system_prompt="Custom prompt",
        )

        agent = Agent(config=agent_config)

        assert agent.name == "prop-agent"
        assert agent.description == "Property test"
        assert agent.system_prompt == "Custom prompt"

    def test_agent_repr(self):
        """Test agent string representation."""
        model_config = ModelProviderConfig(
            provider_type="fake",
            base_url="http://localhost:8000",
            model_name="test-model",
        )

        agent_config = AgentConfig(
            name="repr-agent",
            description="Repr test",
            model_config=model_config,
        )

        agent = Agent(config=agent_config)
        repr_str = repr(agent)

        assert "Agent" in repr_str
        assert "repr-agent" in repr_str
        assert "Repr test" in repr_str


class TestExecutionResult:
    """Test ExecutionResult model."""

    def test_success_result(self):
        """Test successful execution result."""
        result = ExecutionResult(
            success=True,
            final_output="Task completed",
            iterations=1,
        )

        assert result.success is True
        assert result.final_output == "Task completed"
        assert result.iterations == 1
        assert result.error is None

    def test_failure_result(self):
        """Test failed execution result."""
        result = ExecutionResult(
            success=False,
            iterations=0,
            error="Execution failed",
        )

        assert result.success is False
        assert result.error == "Execution failed"
        assert result.final_output is None

    def test_result_with_metadata(self):
        """Test result with metadata."""
        result = ExecutionResult(
            success=True,
            final_output="Output",
            iterations=2,
            metadata={"agent_name": "test"},
        )

        assert result.metadata == {"agent_name": "test"}


class TestAgentExecutor:
    """Test AgentExecutor."""

    def test_executor_creation(self):
        """Test creating an executor."""
        config = ScooperConfig()
        provider = FakeModelProvider()

        executor = AgentExecutor(config=config, model_provider=provider)

        assert executor.config == config
        assert executor.model_provider == provider

    @pytest.mark.asyncio
    async def test_simple_execution(self):
        """Test executing a simple agent task."""
        config = ScooperConfig(log_level="ERROR")  # Reduce test output
        provider = FakeModelProvider(response_content="Task completed successfully")

        model_config = ModelProviderConfig(
            provider_type="fake",
            base_url="http://localhost:8000",
            model_name="test-model",
        )

        agent_config = AgentConfig(
            name="test-agent",
            model_config=model_config,
        )

        agent = Agent(config=agent_config)
        executor = AgentExecutor(config=config, model_provider=provider)

        result = await executor.execute(agent, "Complete this task")

        assert result.success is True
        assert result.final_output == "Task completed successfully"
        assert result.iterations == 1
        assert result.error is None

    @pytest.mark.asyncio
    async def test_execution_with_unhealthy_provider(self):
        """Test execution when provider health check fails."""
        config = ScooperConfig(log_level="ERROR")
        provider = FakeModelProvider(fail_health_check=True)

        model_config = ModelProviderConfig(
            provider_type="fake",
            base_url="http://localhost:8000",
            model_name="test-model",
        )

        agent_config = AgentConfig(name="test-agent", model_config=model_config)
        agent = Agent(config=agent_config)
        executor = AgentExecutor(config=config, model_provider=provider)

        result = await executor.execute(agent, "Test task")

        assert result.success is False
        assert "not available" in result.error
        assert result.iterations == 0

    @pytest.mark.asyncio
    async def test_execution_metadata(self):
        """Test that execution result includes metadata."""
        config = ScooperConfig(log_level="ERROR")
        provider = FakeModelProvider()

        model_config = ModelProviderConfig(
            provider_type="fake",
            base_url="http://localhost:8000",
            model_name="test-model",
        )

        agent_config = AgentConfig(
            name="metadata-agent",
            model_config=model_config,
        )

        agent = Agent(config=agent_config)
        executor = AgentExecutor(config=config, model_provider=provider)

        result = await executor.execute(agent, "Test task")

        assert result.metadata is not None
        assert result.metadata["agent_name"] == "metadata-agent"
        assert "finish_reason" in result.metadata

    @pytest.mark.asyncio
    async def test_agent_level_max_iterations(self):
        """Test that agent-level max_iterations overrides global config."""
        config = ScooperConfig(max_iterations=10, log_level="ERROR")
        provider = FakeModelProvider()

        model_config = ModelProviderConfig(
            provider_type="fake",
            base_url="http://localhost:8000",
            model_name="test-model",
        )

        # Agent with custom max_iterations
        agent_config = AgentConfig(
            name="test-agent",
            model_config=model_config,
            max_iterations=5,
        )

        agent = Agent(config=agent_config)
        executor = AgentExecutor(config=config, model_provider=provider)

        result = await executor.execute(agent, "Test")

        assert result.success is True
        # In Phase 1, we complete after 1 iteration
        assert result.iterations == 1
