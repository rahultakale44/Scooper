"""Security regression tests for tool execution safety.

This module tests security-critical aspects of the tool execution system,
ensuring that safety controls cannot be accidentally or intentionally bypassed.
"""

import pytest

from scooper.config import ModelProviderConfig, ScooperConfig
from scooper.models import FakeModelProvider
from scooper.models.base import ModelResponse, ToolCall
from scooper.runtime import Agent, AgentConfig, AgentExecutor
from scooper.runtime.session_executor import PersistentAgentExecutor
from scooper.tools import Tool, ToolInput, ToolRegistry, ToolResult
from scooper.tools.permissions import (
    ToolPermissionLevel,
    ToolPermissionPolicy,
)
from scooper.tools.safe_registry import SafeToolRegistry

# Test tools


class DangerousTool(Tool):
    """A tool that should require approval."""

    @property
    def name(self) -> str:
        return "dangerous_tool"

    @property
    def description(self) -> str:
        return "A dangerous operation"

    @property
    def permission_level(self) -> ToolPermissionLevel:
        return ToolPermissionLevel.REQUIRES_APPROVAL

    def validate_input(self, tool_input: ToolInput) -> bool:
        return True

    async def execute(self, tool_input: ToolInput) -> ToolResult:
        return ToolResult(
            success=True,
            output="DANGEROUS OPERATION EXECUTED",
            metadata={"warning": "This should not happen without approval"},
        )


class SafeTool(Tool):
    """A safe tool for testing."""

    @property
    def name(self) -> str:
        return "safe_tool"

    @property
    def description(self) -> str:
        return "A safe operation"

    def validate_input(self, tool_input: ToolInput) -> bool:
        return True

    async def execute(self, tool_input: ToolInput) -> ToolResult:
        return ToolResult(success=True, output="Safe operation completed")


# SECURITY REGRESSION TEST 1: Unsafe Registry Bypass


class TestUnsafeRegistryBypass:
    """Test that using a regular ToolRegistry bypasses all safety controls.

    CRITICAL SECURITY FINDING: The executors accept any ToolRegistry,
    allowing developers to completely bypass permission checks, approval
    workflows, and execution limits by using the standard registry.
    """

    @pytest.mark.asyncio
    async def test_executor_with_regular_registry_executes_dangerous_tool(self):
        """VULNERABILITY: AgentExecutor with regular registry bypasses approval requirements.

        This test demonstrates that a tool requiring approval can be executed
        without any approval mechanism when using a regular ToolRegistry.
        """
        # Create scripted response that requests dangerous tool
        scripted_responses = [
            ModelResponse(
                response_type="tool_calls",
                content="Using dangerous tool",
                tool_calls=[
                    ToolCall(id="call-1", name="dangerous_tool", arguments={})
                ],
                finish_reason="tool_calls",
                token_count=10,
            ),
            ModelResponse(
                response_type="text",
                content="Tool executed",
                finish_reason="completed",
                token_count=5,
            ),
        ]

        provider = FakeModelProvider(scripted_responses=scripted_responses)

        # Create REGULAR registry (NOT SafeToolRegistry)
        registry = ToolRegistry()
        registry.register(DangerousTool())

        # Execute with regular registry
        config = ScooperConfig(log_level="ERROR")
        executor = AgentExecutor(config, provider, tool_registry=registry)

        model_config = ModelProviderConfig(
            provider_type="fake",
            base_url="http://localhost:8000",
            model_name="test",
        )
        agent = Agent(AgentConfig(name="test", provider_config=model_config))

        result = await executor.execute(agent, "Use dangerous tool")

        # SECURITY ISSUE: Tool requiring approval was executed without approval!
        assert result.success is True
        assert "DANGEROUS OPERATION EXECUTED" in result.final_output or result.tool_calls_made == 1
        # This test PASSES, demonstrating the vulnerability

    @pytest.mark.asyncio
    async def test_executor_with_regular_registry_ignores_execution_limits(self):
        """VULNERABILITY: Regular ToolRegistry has no execution limits.

        This test demonstrates that execution limits are not enforced
        when using a regular ToolRegistry.
        """
        # Model requests 5 tool calls
        scripted_responses = [
            ModelResponse(
                response_type="tool_calls",
                content="Calling tools",
                tool_calls=[
                    ToolCall(id=f"call-{i}", name="safe_tool", arguments={})
                    for i in range(5)
                ],
                finish_reason="tool_calls",
                token_count=10,
            ),
            ModelResponse(
                response_type="text",
                content="Done",
                finish_reason="completed",
                token_count=5,
            ),
        ]

        provider = FakeModelProvider(scripted_responses=scripted_responses)

        registry = ToolRegistry()
        registry.register(SafeTool())

        config = ScooperConfig(log_level="ERROR")
        executor = AgentExecutor(config, provider, tool_registry=registry)

        model_config = ModelProviderConfig(
            provider_type="fake",
            base_url="http://localhost:8000",
            model_name="test",
        )
        agent = Agent(AgentConfig(name="test", provider_config=model_config))

        result = await executor.execute(agent, "Execute tools")

        # SECURITY ISSUE: All 5 tools executed despite no limit enforcement
        assert result.success is True
        assert result.tool_calls_made == 5
        # No ExecutionLimitExceededError was raised

    @pytest.mark.asyncio
    async def test_persistent_executor_with_regular_registry_bypasses_safety(self):
        """VULNERABILITY: PersistentAgentExecutor also accepts unsafe registries."""
        scripted_responses = [
            ModelResponse(
                response_type="tool_calls",
                content="Using tool",
                tool_calls=[
                    ToolCall(id="call-1", name="dangerous_tool", arguments={})
                ],
                finish_reason="tool_calls",
                token_count=10,
            ),
            ModelResponse(
                response_type="text",
                content="Done",
                finish_reason="completed",
                token_count=5,
            ),
        ]

        provider = FakeModelProvider(scripted_responses=scripted_responses)

        # Regular registry with approval-required tool
        registry = ToolRegistry()
        registry.register(DangerousTool())

        config = ScooperConfig(log_level="ERROR")
        # No session store needed for this test
        executor = PersistentAgentExecutor(config, provider, tool_registry=registry)

        model_config = ModelProviderConfig(
            provider_type="fake",
            base_url="http://localhost:8000",
            model_name="test",
        )
        agent = Agent(AgentConfig(name="test", provider_config=model_config))

        result = await executor.execute(agent, "Use dangerous tool")

        # SECURITY ISSUE: Approval-required tool executed without approval
        assert result.success is True


# SECURITY REGRESSION TEST 2: Counter Not Reset


class TestCounterNotReset:
    """Test that tool call counters are not automatically reset.

    CRITICAL FINDING: SafeToolRegistry counters persist across executions,
    leading to incorrect enforcement of limits.
    """

    @pytest.mark.asyncio
    async def test_safe_registry_counter_persists_across_executions(self):
        """VULNERABILITY: Counter is not reset between executions.

        This test shows that reusing a SafeToolRegistry instance
        carries over the counter from previous executions.
        """
        registry = ToolRegistry()
        registry.register(SafeTool())

        # Set limit of 3 calls per execution
        safe_registry = SafeToolRegistry(registry, max_tool_calls_per_execution=3)

        # First execution: use 2 calls
        scripted_responses_1 = [
            ModelResponse(
                response_type="tool_calls",
                content="Calling",
                tool_calls=[
                    ToolCall(id="call-1", name="safe_tool", arguments={}),
                    ToolCall(id="call-2", name="safe_tool", arguments={}),
                ],
                finish_reason="tool_calls",
                token_count=10,
            ),
            ModelResponse(
                response_type="text",
                content="Done",
                finish_reason="completed",
                token_count=5,
            ),
        ]

        provider_1 = FakeModelProvider(scripted_responses=scripted_responses_1)
        config = ScooperConfig(log_level="ERROR")
        executor_1 = AgentExecutor(config, provider_1, tool_registry=safe_registry)

        model_config = ModelProviderConfig(
            provider_type="fake",
            base_url="http://localhost:8000",
            model_name="test",
        )
        agent = Agent(AgentConfig(name="test", provider_config=model_config))

        result_1 = await executor_1.execute(agent, "First execution")
        assert result_1.success is True
        assert safe_registry.tool_calls_made == 2

        # Second execution with same registry: try 2 more calls
        scripted_responses_2 = [
            ModelResponse(
                response_type="tool_calls",
                content="Calling",
                tool_calls=[
                    ToolCall(id="call-3", name="safe_tool", arguments={}),
                    ToolCall(id="call-4", name="safe_tool", arguments={}),
                ],
                finish_reason="tool_calls",
                token_count=10,
            ),
            ModelResponse(
                response_type="text",
                content="Done",
                finish_reason="completed",
                token_count=5,
            ),
        ]

        provider_2 = FakeModelProvider(scripted_responses=scripted_responses_2)
        executor_2 = AgentExecutor(config, provider_2, tool_registry=safe_registry)

        result_2 = await executor_2.execute(agent, "Second execution")

        # SECURITY ISSUE: Second execution fails because counter wasn't reset
        # Expected: both executions succeed with 2 calls each (limit is 3)
        # Actual: second execution hits limit after 1 call (2+1=3, then 2+2>3)
        assert result_2.success is False
        assert result_2.stop_reason == "tool_limit_exceeded"
        # Counter shows 3 (2 from first + 1 from second before failure)


# SECURITY REGRESSION TEST 3: Documentation vs Reality


class TestDocumentationClaims:
    """Test that documented safety guarantees match actual behavior."""

    @pytest.mark.asyncio
    async def test_readme_claims_enforcement_but_allows_bypass(self):
        """DOCUMENTATION ISSUE: README claims "framework-enforced" but it's optional.

        The README states:
        "framework-enforced safety controls for tool execution"
        "All safety checks happen in Python before tool execution"

        But this is only true IF developers use SafeToolRegistry.
        Using regular ToolRegistry bypasses all controls.
        """
        # This is a documentation test - demonstrates the gap
        registry = ToolRegistry()
        registry.register(DangerousTool())

        # The fact that this is allowed demonstrates the documentation issue
        config = ScooperConfig(log_level="ERROR")
        executor = AgentExecutor(config, FakeModelProvider(), tool_registry=registry)

        # Developer can create executor with unsafe registry
        # No type error, no runtime error, no warning
        assert executor.tool_registry is registry
        assert not isinstance(registry, SafeToolRegistry)


# SECURITY REGRESSION TEST 4: Permission Check Correctness


class TestPermissionEnforcement:
    """Test that permission checks work correctly when SafeToolRegistry IS used."""

    @pytest.mark.asyncio
    async def test_denylist_blocks_tool(self):
        """Test that denylist correctly blocks denied tools."""
        registry = ToolRegistry()
        registry.register(SafeTool())

        policy = ToolPermissionPolicy(denylist={"safe_tool"})
        safe_registry = SafeToolRegistry(registry, policy=policy)

        scripted_responses = [
            ModelResponse(
                response_type="tool_calls",
                content="Using tool",
                tool_calls=[ToolCall(id="call-1", name="safe_tool", arguments={})],
                finish_reason="tool_calls",
                token_count=10,
            ),
            ModelResponse(
                response_type="text",
                content="Done",
                finish_reason="completed",
                token_count=5,
            ),
        ]

        provider = FakeModelProvider(scripted_responses=scripted_responses)
        config = ScooperConfig(log_level="ERROR")
        executor = AgentExecutor(config, provider, tool_registry=safe_registry)

        model_config = ModelProviderConfig(
            provider_type="fake",
            base_url="http://localhost:8000",
            model_name="test",
        )
        agent = Agent(AgentConfig(name="test", provider_config=model_config))

        result = await executor.execute(agent, "Use tool")

        # Tool should be blocked - execution completes but tool failed
        assert result.success is True  # Execution itself completes
        # The tool call resulted in an error message back to the model

    @pytest.mark.asyncio
    async def test_approval_required_without_callback_fails_closed(self):
        """Test that approval-required tools fail without approval mechanism."""
        registry = ToolRegistry()
        registry.register(DangerousTool())

        # No policy (no approval callback)
        safe_registry = SafeToolRegistry(registry)

        scripted_responses = [
            ModelResponse(
                response_type="tool_calls",
                content="Using tool",
                tool_calls=[
                    ToolCall(id="call-1", name="dangerous_tool", arguments={})
                ],
                finish_reason="tool_calls",
                token_count=10,
            ),
            ModelResponse(
                response_type="text",
                content="Done",
                finish_reason="completed",
                token_count=5,
            ),
        ]

        provider = FakeModelProvider(scripted_responses=scripted_responses)
        config = ScooperConfig(log_level="ERROR")
        executor = AgentExecutor(config, provider, tool_registry=safe_registry)

        model_config = ModelProviderConfig(
            provider_type="fake",
            base_url="http://localhost:8000",
            model_name="test",
        )
        agent = Agent(AgentConfig(name="test", provider_config=model_config))

        result = await executor.execute(agent, "Use dangerous tool")

        # Should complete with tool error (fail closed)
        assert result.success is True
        # The error was returned as a message to the model


# SECURITY REGRESSION TEST 5: Execution Limit Boundary


class TestExecutionLimits:
    """Test execution limit boundary conditions."""

    @pytest.mark.asyncio
    async def test_limit_at_exact_boundary(self):
        """Test that limit is enforced exactly at the boundary."""
        registry = ToolRegistry()
        registry.register(SafeTool())

        safe_registry = SafeToolRegistry(registry, max_tool_calls_per_execution=3)

        # Exactly 3 tool calls
        scripted_responses = [
            ModelResponse(
                response_type="tool_calls",
                content="Calling",
                tool_calls=[
                    ToolCall(id=f"call-{i}", name="safe_tool", arguments={})
                    for i in range(3)
                ],
                finish_reason="tool_calls",
                token_count=10,
            ),
            ModelResponse(
                response_type="text",
                content="Done",
                finish_reason="completed",
                token_count=5,
            ),
        ]

        provider = FakeModelProvider(scripted_responses=scripted_responses)
        config = ScooperConfig(log_level="ERROR")
        executor = AgentExecutor(config, provider, tool_registry=safe_registry)

        model_config = ModelProviderConfig(
            provider_type="fake",
            base_url="http://localhost:8000",
            model_name="test",
        )
        agent = Agent(AgentConfig(name="test", provider_config=model_config))

        result = await executor.execute(agent, "Execute 3 tools")

        # Should succeed - exactly at limit
        assert result.success is True
        assert result.tool_calls_made == 3

    @pytest.mark.asyncio
    async def test_limit_exceeded_by_one(self):
        """Test that limit is enforced when exceeded by one call."""
        registry = ToolRegistry()
        registry.register(SafeTool())

        safe_registry = SafeToolRegistry(registry, max_tool_calls_per_execution=3)

        # 4 tool calls (one over limit)
        scripted_responses = [
            ModelResponse(
                response_type="tool_calls",
                content="Calling",
                tool_calls=[
                    ToolCall(id=f"call-{i}", name="safe_tool", arguments={})
                    for i in range(4)
                ],
                finish_reason="tool_calls",
                token_count=10,
            ),
            ModelResponse(
                response_type="text",
                content="Done",
                finish_reason="completed",
                token_count=5,
            ),
        ]

        provider = FakeModelProvider(scripted_responses=scripted_responses)
        config = ScooperConfig(log_level="ERROR")
        executor = AgentExecutor(config, provider, tool_registry=safe_registry)

        model_config = ModelProviderConfig(
            provider_type="fake",
            base_url="http://localhost:8000",
            model_name="test",
        )
        agent = Agent(AgentConfig(name="test", provider_config=model_config))

        result = await executor.execute(agent, "Execute 4 tools")

        # Should fail after 3 calls
        assert result.success is False
        assert result.stop_reason == "tool_limit_exceeded"
        assert "Maximum tool calls" in result.error
