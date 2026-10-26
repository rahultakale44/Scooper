"""Tests for tool permission system and safe registry."""

import pytest

from scooper.config import ModelProviderConfig, ScooperConfig
from scooper.exceptions import (
    ExecutionLimitExceededError,
    ToolApprovalDeniedError,
    ToolApprovalRequiredError,
    ToolPermissionDeniedError,
)
from scooper.models import FakeModelProvider
from scooper.models.base import ToolCall
from scooper.runtime import Agent, AgentConfig, AgentExecutor
from scooper.tools import Tool, ToolInput, ToolRegistry, ToolResult
from scooper.tools.permissions import (
    ApprovalRequest,
    ToolPermissionLevel,
    ToolPermissionPolicy,
)
from scooper.tools.safe_registry import SafeToolRegistry

# Test tools with different permission levels


class SafeTool(Tool):
    """A safe tool that doesn't require approval."""

    @property
    def name(self) -> str:
        return "safe_tool"

    @property
    def description(self) -> str:
        return "A safe tool that doesn't require approval"

    @property
    def permission_level(self) -> ToolPermissionLevel:
        return ToolPermissionLevel.ALLOWED

    def validate_input(self, tool_input: ToolInput) -> bool:
        return True

    async def execute(self, tool_input: ToolInput) -> ToolResult:
        return ToolResult(
            success=True,
            output="Safe tool executed",
            metadata={"permission": "allowed"},
        )


class DangerousTool(Tool):
    """A tool that requires approval before execution."""

    @property
    def name(self) -> str:
        return "dangerous_tool"

    @property
    def description(self) -> str:
        return "A dangerous tool that requires approval"

    @property
    def permission_level(self) -> ToolPermissionLevel:
        return ToolPermissionLevel.REQUIRES_APPROVAL

    def validate_input(self, tool_input: ToolInput) -> bool:
        return True

    async def execute(self, tool_input: ToolInput) -> ToolResult:
        return ToolResult(
            success=True,
            output="Dangerous tool executed",
            metadata={"permission": "requires_approval"},
        )


class CalculatorTool(Tool):
    """Calculator tool for testing allowlists."""

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return "Basic calculator"

    def validate_input(self, tool_input: ToolInput) -> bool:
        return True

    async def execute(self, tool_input: ToolInput) -> ToolResult:
        return ToolResult(success=True, output="42")


# Test fixtures


@pytest.fixture
def basic_registry():
    """Create a basic tool registry with test tools."""
    registry = ToolRegistry()
    registry.register(SafeTool())
    registry.register(DangerousTool())
    registry.register(CalculatorTool())
    return registry


@pytest.fixture
def basic_tool_input():
    """Create a basic tool input."""
    return ToolInput(test_param="value")


# Test ToolPermissionPolicy


class TestToolPermissionPolicy:
    """Test permission policy enforcement."""

    def test_policy_no_restrictions(self):
        """Test policy with no allowlist or denylist."""
        policy = ToolPermissionPolicy()

        # All tools should be allowed
        policy.check_permission("any_tool")
        policy.check_permission("another_tool")

        assert policy.is_allowed("any_tool")
        assert policy.is_allowed("another_tool")

    def test_policy_with_allowlist(self):
        """Test policy with allowlist."""
        policy = ToolPermissionPolicy(allowlist={"calculator", "safe_tool"})

        # Allowed tools should pass
        policy.check_permission("calculator")
        policy.check_permission("safe_tool")

        # Tools not on allowlist should fail
        with pytest.raises(ToolPermissionDeniedError) as exc_info:
            policy.check_permission("dangerous_tool")
        assert "not in the allowed tools list" in str(exc_info.value)

        assert policy.is_allowed("calculator")
        assert not policy.is_allowed("dangerous_tool")

    def test_policy_with_denylist(self):
        """Test policy with denylist."""
        policy = ToolPermissionPolicy(denylist={"dangerous_tool", "risky_tool"})

        # Non-denied tools should pass
        policy.check_permission("safe_tool")
        policy.check_permission("calculator")

        # Denied tools should fail
        with pytest.raises(ToolPermissionDeniedError) as exc_info:
            policy.check_permission("dangerous_tool")
        assert "denied by permission policy (denylist)" in str(exc_info.value)

        assert policy.is_allowed("safe_tool")
        assert not policy.is_allowed("dangerous_tool")

    def test_denylist_overrides_allowlist(self):
        """Test that denylist takes precedence over allowlist."""
        policy = ToolPermissionPolicy(
            allowlist={"calculator", "dangerous_tool"},
            denylist={"dangerous_tool"},
        )

        # Calculator is allowed
        policy.check_permission("calculator")

        # Dangerous tool is denied despite being on allowlist
        with pytest.raises(ToolPermissionDeniedError) as exc_info:
            policy.check_permission("dangerous_tool")
        assert "denylist" in str(exc_info.value)

        assert not policy.is_allowed("dangerous_tool")

    def test_empty_allowlist(self):
        """Test behavior with empty allowlist."""
        policy = ToolPermissionPolicy(allowlist=set())

        # No tools should be allowed
        with pytest.raises(ToolPermissionDeniedError):
            policy.check_permission("any_tool")

        assert not policy.is_allowed("any_tool")

    @pytest.mark.asyncio
    async def test_approval_without_callback(self):
        """Test that approval fails if no callback is configured."""
        policy = ToolPermissionPolicy()

        with pytest.raises(ToolApprovalRequiredError) as exc_info:
            await policy.request_approval("tool", ToolInput(), None)
        assert "no approval handler is configured" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_approval_with_callback_approved(self):
        """Test approval workflow when approved."""

        async def approve_callback(request: ApprovalRequest) -> bool:
            return True

        policy = ToolPermissionPolicy(approval_callback=approve_callback)

        # Should not raise
        await policy.request_approval("dangerous_tool", ToolInput(), "session-123")

    @pytest.mark.asyncio
    async def test_approval_with_callback_denied(self):
        """Test approval workflow when denied."""

        async def deny_callback(request: ApprovalRequest) -> bool:
            return False

        policy = ToolPermissionPolicy(approval_callback=deny_callback)

        with pytest.raises(ToolApprovalDeniedError) as exc_info:
            await policy.request_approval("dangerous_tool", ToolInput(), "session-123")
        assert "was not approved" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_approval_callback_receives_context(self):
        """Test that approval callback receives full context."""
        received_requests = []

        async def capture_callback(request: ApprovalRequest) -> bool:
            received_requests.append(request)
            return True

        policy = ToolPermissionPolicy(approval_callback=capture_callback)

        tool_input = ToolInput(action="delete", target="database")
        await policy.request_approval("dangerous_tool", tool_input, "session-456")

        assert len(received_requests) == 1
        request = received_requests[0]
        assert request.tool_name == "dangerous_tool"
        assert request.arguments["action"] == "delete"
        assert request.session_id == "session-456"

    @pytest.mark.asyncio
    async def test_approval_callback_exception(self):
        """Test that approval fails closed on callback exceptions."""

        async def failing_callback(request: ApprovalRequest) -> bool:
            raise RuntimeError("Approval system unavailable")

        policy = ToolPermissionPolicy(approval_callback=failing_callback)

        # Should fail closed
        with pytest.raises(ToolApprovalDeniedError) as exc_info:
            await policy.request_approval("tool", ToolInput(), None)
        assert "approval failed due to error" in str(exc_info.value)


# Test SafeToolRegistry


class TestSafeToolRegistry:
    """Test safe tool registry with enforcement."""

    @pytest.mark.asyncio
    async def test_safe_registry_basic_execution(self, basic_registry, basic_tool_input):
        """Test basic tool execution through safe registry."""
        safe_registry = SafeToolRegistry(basic_registry)

        result = await safe_registry.execute("safe_tool", basic_tool_input)

        assert result.success is True
        assert "Safe tool executed" in result.output
        assert safe_registry.tool_calls_made == 1

    @pytest.mark.asyncio
    async def test_safe_registry_with_allowlist(self, basic_registry, basic_tool_input):
        """Test safe registry with allowlist enforcement."""
        policy = ToolPermissionPolicy(allowlist={"safe_tool", "calculator"})
        safe_registry = SafeToolRegistry(basic_registry, policy=policy)

        # Allowed tool should work
        result = await safe_registry.execute("safe_tool", basic_tool_input)
        assert result.success is True

        # Denied tool should fail
        with pytest.raises(ToolPermissionDeniedError):
            await safe_registry.execute("dangerous_tool", basic_tool_input)

    @pytest.mark.asyncio
    async def test_safe_registry_with_denylist(self, basic_registry, basic_tool_input):
        """Test safe registry with denylist enforcement."""
        policy = ToolPermissionPolicy(denylist={"dangerous_tool"})
        safe_registry = SafeToolRegistry(basic_registry, policy=policy)

        # Non-denied tool should work
        result = await safe_registry.execute("safe_tool", basic_tool_input)
        assert result.success is True

        # Denied tool should fail before execution
        with pytest.raises(ToolPermissionDeniedError):
            await safe_registry.execute("dangerous_tool", basic_tool_input)

    @pytest.mark.asyncio
    async def test_safe_registry_approval_required_without_policy(
        self, basic_registry, basic_tool_input
    ):
        """Test that approval-required tools fail without policy."""
        safe_registry = SafeToolRegistry(basic_registry)

        # Tool requiring approval should fail without policy
        with pytest.raises(ToolApprovalRequiredError) as exc_info:
            await safe_registry.execute("dangerous_tool", basic_tool_input)
        assert "no policy is configured" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_safe_registry_approval_workflow(self, basic_registry, basic_tool_input):
        """Test approval workflow for approval-required tools."""

        async def approval_callback(request: ApprovalRequest) -> bool:
            # Approve dangerous_tool
            return request.tool_name == "dangerous_tool"

        policy = ToolPermissionPolicy(approval_callback=approval_callback)
        safe_registry = SafeToolRegistry(basic_registry, policy=policy)

        # Should succeed with approval
        result = await safe_registry.execute("dangerous_tool", basic_tool_input)
        assert result.success is True
        assert "Dangerous tool executed" in result.output

    @pytest.mark.asyncio
    async def test_safe_registry_approval_denied(self, basic_registry, basic_tool_input):
        """Test approval workflow when approval is denied."""

        async def deny_callback(request: ApprovalRequest) -> bool:
            return False

        policy = ToolPermissionPolicy(approval_callback=deny_callback)
        safe_registry = SafeToolRegistry(basic_registry, policy=policy)

        with pytest.raises(ToolApprovalDeniedError):
            await safe_registry.execute("dangerous_tool", basic_tool_input)

    @pytest.mark.asyncio
    async def test_safe_registry_call_limit(self, basic_registry, basic_tool_input):
        """Test execution call limit enforcement."""
        safe_registry = SafeToolRegistry(basic_registry, max_tool_calls_per_execution=2)

        # First call should succeed
        await safe_registry.execute("safe_tool", basic_tool_input)
        assert safe_registry.tool_calls_made == 1

        # Second call should succeed
        await safe_registry.execute("calculator", basic_tool_input)
        assert safe_registry.tool_calls_made == 2

        # Third call should fail
        with pytest.raises(ExecutionLimitExceededError) as exc_info:
            await safe_registry.execute("safe_tool", basic_tool_input)
        assert "Maximum tool calls" in str(exc_info.value)
        assert safe_registry.tool_calls_made == 2

    @pytest.mark.asyncio
    async def test_safe_registry_reset_call_count(self, basic_registry, basic_tool_input):
        """Test resetting call counter."""
        safe_registry = SafeToolRegistry(basic_registry, max_tool_calls_per_execution=2)

        await safe_registry.execute("safe_tool", basic_tool_input)
        await safe_registry.execute("calculator", basic_tool_input)
        assert safe_registry.tool_calls_made == 2

        # Reset counter
        safe_registry.reset_call_count()
        assert safe_registry.tool_calls_made == 0

        # Should be able to make more calls
        await safe_registry.execute("safe_tool", basic_tool_input)
        assert safe_registry.tool_calls_made == 1

    @pytest.mark.asyncio
    async def test_safe_registry_enforcement_order(self, basic_registry, basic_tool_input):
        """Test that enforcement happens in correct order: limits -> lookup -> permission -> approval."""

        async def approval_callback(request: ApprovalRequest) -> bool:
            return True

        policy = ToolPermissionPolicy(
            allowlist={"dangerous_tool"},
            approval_callback=approval_callback,
        )
        safe_registry = SafeToolRegistry(
            basic_registry,
            policy=policy,
            max_tool_calls_per_execution=1,
        )

        # First call: goes through all checks
        await safe_registry.execute("dangerous_tool", basic_tool_input)
        assert safe_registry.tool_calls_made == 1

        # Second call: should fail at limit check before others
        with pytest.raises(ExecutionLimitExceededError):
            await safe_registry.execute("dangerous_tool", basic_tool_input)

    def test_safe_registry_properties(self, basic_registry):
        """Test safe registry property access."""
        policy = ToolPermissionPolicy(allowlist={"safe_tool"})
        safe_registry = SafeToolRegistry(
            basic_registry,
            policy=policy,
            max_tool_calls_per_execution=5,
            session_id="test-session",
        )

        assert safe_registry.registry is basic_registry
        assert safe_registry.policy is policy
        assert safe_registry.tool_calls_made == 0

    def test_safe_registry_repr(self, basic_registry):
        """Test safe registry string representation."""
        safe_registry = SafeToolRegistry(basic_registry, max_tool_calls_per_execution=10)

        repr_str = repr(safe_registry)
        assert "SafeToolRegistry" in repr_str
        assert "tools=3" in repr_str
        assert "calls=0/10" in repr_str


# Integration tests with AgentExecutor


class TestSafeToolIntegration:
    """Test safe tool registry integration with agent runtime."""

    @pytest.mark.asyncio
    async def test_executor_with_safe_registry(self):
        """Test using safe registry with agent executor."""
        from scooper.models.base import ModelResponse

        # Create scripted responses: first tool call, then text response
        scripted_responses = [
            ModelResponse(
                response_type="tool_calls",
                content="I'll use the safe tool",
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        name="safe_tool",
                        arguments={"test": "value"},
                    )
                ],
                finish_reason="tool_calls",
                token_count=10,
            ),
            ModelResponse(
                response_type="text",
                content="Tool executed successfully",
                finish_reason="completed",
                token_count=5,
            ),
        ]

        provider = FakeModelProvider(scripted_responses=scripted_responses)

        # Create safe registry
        registry = ToolRegistry()
        registry.register(SafeTool())

        policy = ToolPermissionPolicy(allowlist={"safe_tool"})
        safe_registry = SafeToolRegistry(registry, policy=policy)

        # Create executor with safe registry
        config = ScooperConfig(log_level="ERROR", max_iterations=5)
        executor = AgentExecutor(config=config, model_provider=provider, tool_registry=safe_registry)

        # Create agent
        model_config = ModelProviderConfig(
            provider_type="fake",
            base_url="http://localhost:8000",
            model_name="test-model",
        )
        agent_config = AgentConfig(name="test-agent", provider_config=model_config)
        agent = Agent(config=agent_config)

        # Execute
        result = await executor.execute(agent, "Use the safe tool")

        assert result.success is True
        assert result.tool_calls_made == 1

    @pytest.mark.asyncio
    async def test_executor_with_denied_tool(self):
        """Test that denied tools are blocked during execution."""
        from scooper.models.base import ModelResponse

        # Provider tries to use denied tool, then gets error back and responds
        scripted_responses = [
            ModelResponse(
                response_type="tool_calls",
                content="I'll use the dangerous tool",
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        name="dangerous_tool",
                        arguments={},
                    )
                ],
                finish_reason="tool_calls",
                token_count=10,
            ),
            ModelResponse(
                response_type="text",
                content="I understand the tool was denied",
                finish_reason="completed",
                token_count=5,
            ),
        ]

        provider = FakeModelProvider(scripted_responses=scripted_responses)

        registry = ToolRegistry()
        registry.register(DangerousTool())

        # Deny the tool
        policy = ToolPermissionPolicy(denylist={"dangerous_tool"})
        safe_registry = SafeToolRegistry(registry, policy=policy)

        config = ScooperConfig(log_level="ERROR", max_iterations=5)
        executor = AgentExecutor(config=config, model_provider=provider, tool_registry=safe_registry)

        model_config = ModelProviderConfig(
            provider_type="fake",
            base_url="http://localhost:8000",
            model_name="test-model",
        )
        agent_config = AgentConfig(name="test-agent", provider_config=model_config)
        agent = Agent(config=agent_config)

        # Execute - tool call should fail
        result = await executor.execute(agent, "Use dangerous tool")

        # Execution should complete but with tool error
        assert result.success is True  # Execution completes
        # Tool error is returned as message to the model

    @pytest.mark.asyncio
    async def test_executor_exceeds_tool_limit(self):
        """Test that executor respects tool call limits."""
        from scooper.models.base import ModelResponse

        # Provider makes multiple tool calls
        scripted_responses = [
            ModelResponse(
                response_type="tool_calls",
                content="I'll use tools",
                tool_calls=[
                    ToolCall(id="call-1", name="safe_tool", arguments={}),
                    ToolCall(id="call-2", name="safe_tool", arguments={}),
                    ToolCall(id="call-3", name="safe_tool", arguments={}),
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

        # Limit to 2 calls
        safe_registry = SafeToolRegistry(registry, max_tool_calls_per_execution=2)

        config = ScooperConfig(log_level="ERROR", max_iterations=5)
        executor = AgentExecutor(config=config, model_provider=provider, tool_registry=safe_registry)

        model_config = ModelProviderConfig(
            provider_type="fake",
            base_url="http://localhost:8000",
            model_name="test-model",
        )
        agent_config = AgentConfig(name="test-agent", provider_config=model_config)
        agent = Agent(config=agent_config)

        result = await executor.execute(agent, "Execute tools")

        # Should fail with tool_limit_exceeded
        assert result.success is False
        assert result.stop_reason == "tool_limit_exceeded"
        assert "Maximum tool calls" in result.error


# Boundary and edge cases


class TestBoundaryConditions:
    """Test boundary conditions and edge cases."""

    def test_policy_with_none_allowlist(self):
        """Test that None allowlist allows all tools."""
        policy = ToolPermissionPolicy(allowlist=None)

        policy.check_permission("any_tool")
        assert policy.is_allowed("any_tool")

    def test_policy_with_empty_denylist(self):
        """Test that empty denylist allows all tools."""
        policy = ToolPermissionPolicy(denylist=set())

        policy.check_permission("any_tool")
        assert policy.is_allowed("any_tool")

    @pytest.mark.asyncio
    async def test_zero_tool_limit(self, basic_registry, basic_tool_input):
        """Test registry with zero tool call limit."""
        safe_registry = SafeToolRegistry(basic_registry, max_tool_calls_per_execution=0)

        # First call should immediately fail
        with pytest.raises(ExecutionLimitExceededError):
            await safe_registry.execute("safe_tool", basic_tool_input)

    @pytest.mark.asyncio
    async def test_unlimited_tool_calls(self, basic_registry, basic_tool_input):
        """Test registry with no call limit."""
        safe_registry = SafeToolRegistry(basic_registry, max_tool_calls_per_execution=None)

        # Should be able to make many calls
        for _ in range(100):
            await safe_registry.execute("safe_tool", basic_tool_input)

        assert safe_registry.tool_calls_made == 100

    def test_approval_request_immutable(self):
        """Test that ApprovalRequest is immutable."""
        from pydantic import ValidationError

        request = ApprovalRequest(
            tool_name="test",
            arguments={"key": "value"},
        )

        with pytest.raises(ValidationError):
            request.tool_name = "modified"
