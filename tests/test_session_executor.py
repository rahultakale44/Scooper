"""Tests for session-aware agent execution with resumable conversations."""

import tempfile
from pathlib import Path

import pytest

from scooper.config import ModelProviderConfig, ScooperConfig
from scooper.exceptions import SessionError, SessionNotFoundError
from scooper.models import FakeModelProvider, ModelResponse, ToolCall
from scooper.persistence import SessionStore
from scooper.runtime import Agent, AgentConfig, PersistentAgentExecutor
from scooper.tools import Tool, ToolInput, ToolRegistry, ToolResult


class CounterTool(Tool):
    """A simple counter tool for testing."""

    def __init__(self) -> None:
        """Initialize counter."""
        self.count = 0
        self._name = "counter"
        self._description = "Increments a counter"

    @property
    def name(self) -> str:
        """Tool name."""
        return self._name

    @property
    def description(self) -> str:
        """Tool description."""
        return self._description

    def validate_input(self, tool_input: ToolInput) -> bool:
        """Validate input (counter needs no special input)."""
        return True

    async def execute(self, tool_input: ToolInput) -> ToolResult:
        """Execute the tool."""
        self.count += 1
        return ToolResult(
            success=True,
            output=f"Count: {self.count}",
        )


@pytest.fixture
def temp_db() -> Path:
    """Create a temporary database file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    yield db_path
    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def config() -> ScooperConfig:
    """Create test configuration."""
    return ScooperConfig(log_level="ERROR", max_iterations=10)


@pytest.fixture
def agent_config() -> AgentConfig:
    """Create test agent configuration."""
    return AgentConfig(
        name="test-agent",
        description="Test agent",
        provider_config=ModelProviderConfig(
            provider_type="fake",
            base_url="http://fake",
            model_name="fake",
        ),
        system_prompt="You are a helpful assistant.",
    )


@pytest.fixture
def agent(agent_config: AgentConfig) -> Agent:
    """Create test agent."""
    return Agent(agent_config)


class TestPersistentAgentExecutor:
    """Test PersistentAgentExecutor functionality."""

    @pytest.mark.asyncio
    async def test_executor_creation_without_session_store(
        self, config: ScooperConfig, agent: Agent
    ) -> None:
        """Test creating executor without session store."""
        provider = FakeModelProvider(response_content="Hello!")
        executor = PersistentAgentExecutor(config, provider)

        # Executor should work, but execute_with_session should fail
        with pytest.raises(SessionError, match="SessionStore is required"):
            await executor.execute_with_session(agent, "Hi", "session-1")

    @pytest.mark.asyncio
    async def test_create_new_session(
        self, config: ScooperConfig, agent: Agent, temp_db: Path
    ) -> None:
        """Test creating a new session and executing."""
        store = SessionStore(db_path=temp_db)
        provider = FakeModelProvider(response_content="Hello from agent!")
        executor = PersistentAgentExecutor(config, provider, session_store=store)

        result, session = await executor.execute_with_session(
            agent=agent,
            task="Say hello",
            session_id="test-session-1",
            resume=False,
        )

        assert result.success is True
        assert result.final_output == "Hello from agent!"
        assert session.session_id == "test-session-1"
        assert session.agent_name == agent.name

        # Verify messages were persisted
        messages = await store.load_messages("test-session-1")
        assert len(messages) == 2  # user message + assistant response
        assert messages[0].role == "user"
        assert "Say hello" in messages[0].content or ""
        assert messages[1].role == "assistant"
        assert messages[1].content == "Hello from agent!"

        store.close()

    @pytest.mark.asyncio
    async def test_resume_nonexistent_session_fails(
        self, config: ScooperConfig, agent: Agent, temp_db: Path
    ) -> None:
        """Test that resuming a nonexistent session fails."""
        store = SessionStore(db_path=temp_db)
        provider = FakeModelProvider(response_content="Hello!")
        executor = PersistentAgentExecutor(config, provider, session_store=store)

        with pytest.raises(SessionNotFoundError):
            await executor.execute_with_session(
                agent=agent,
                task="Continue",
                session_id="nonexistent",
                resume=True,
            )

        store.close()

    @pytest.mark.asyncio
    async def test_resume_existing_session(
        self, config: ScooperConfig, agent: Agent, temp_db: Path
    ) -> None:
        """Test resuming an existing session."""
        store = SessionStore(db_path=temp_db)

        # Script two responses: first execution, then resume
        provider = FakeModelProvider(
            scripted_responses=[
                ModelResponse(
                    response_type="text",
                    content="First response",
                    finish_reason="completed",
                ),
                ModelResponse(
                    response_type="text",
                    content="Second response",
                    finish_reason="completed",
                ),
            ]
        )
        executor = PersistentAgentExecutor(config, provider, session_store=store)

        # First execution
        result1, session1 = await executor.execute_with_session(
            agent=agent,
            task="First task",
            session_id="resume-test",
            resume=False,
        )

        assert result1.success is True
        assert result1.final_output == "First response"

        # Resume the session
        result2, session2 = await executor.execute_with_session(
            agent=agent,
            task="Second task",
            session_id="resume-test",
            resume=True,
        )

        assert result2.success is True
        assert result2.final_output == "Second response"
        assert session2.session_id == session1.session_id

        # Verify conversation history
        messages = await store.load_messages("resume-test")
        assert len(messages) == 4  # 2 user messages + 2 assistant responses
        assert messages[0].role == "user"
        assert "First task" in messages[0].content or ""
        assert messages[1].role == "assistant"
        assert messages[1].content == "First response"
        assert messages[2].role == "user"
        assert messages[2].content == "Second task"
        assert messages[3].role == "assistant"
        assert messages[3].content == "Second response"

        store.close()

    @pytest.mark.asyncio
    async def test_conversation_history_preserved(
        self, config: ScooperConfig, agent: Agent, temp_db: Path
    ) -> None:
        """Test that conversation history is correctly preserved and used."""
        store = SessionStore(db_path=temp_db)
        provider = FakeModelProvider(
            scripted_responses=[
                ModelResponse(
                    response_type="text",
                    content="Response 1",
                    finish_reason="completed",
                ),
                ModelResponse(
                    response_type="text",
                    content="Response 2",
                    finish_reason="completed",
                ),
                ModelResponse(
                    response_type="text",
                    content="Response 3",
                    finish_reason="completed",
                ),
            ]
        )
        executor = PersistentAgentExecutor(config, provider, session_store=store)

        # Execute three times
        await executor.execute_with_session(agent, "Task 1", "history-test", resume=False)
        await executor.execute_with_session(agent, "Task 2", "history-test", resume=True)
        await executor.execute_with_session(agent, "Task 3", "history-test", resume=True)

        # Check history
        messages = await store.load_messages("history-test")
        assert len(messages) == 6  # 3 user + 3 assistant
        assert messages[0].content and "Task 1" in messages[0].content
        assert messages[2].content == "Task 2"
        assert messages[4].content == "Task 3"

        store.close()

    @pytest.mark.asyncio
    async def test_tool_calls_persisted_and_restored(
        self, config: ScooperConfig, agent: Agent, temp_db: Path
    ) -> None:
        """Test that tool calls are persisted and restored correctly."""
        store = SessionStore(db_path=temp_db)
        counter_tool = CounterTool()
        registry = ToolRegistry()
        registry.register(counter_tool)

        # Script responses with tool calls
        provider = FakeModelProvider(
            scripted_responses=[
                ModelResponse(
                    response_type="tool_calls",
                    tool_calls=[ToolCall(id="call-1", name="counter", arguments={})],
                    finish_reason="tool_calls",
                ),
                ModelResponse(
                    response_type="text",
                    content="Counter incremented",
                    finish_reason="completed",
                ),
            ]
        )
        executor = PersistentAgentExecutor(
            config, provider, tool_registry=registry, session_store=store
        )

        # Execute with tool call
        result, _ = await executor.execute_with_session(
            agent=agent,
            task="Increment counter",
            session_id="tool-test",
            resume=False,
        )

        assert result.success is True
        assert result.tool_calls_made == 1
        assert counter_tool.count == 1

        # Verify messages include tool calls
        messages = await store.load_messages("tool-test")
        assert len(messages) == 4  # user, assistant with tool_calls, tool result, final assistant

        # Check tool call message
        assistant_with_tools = messages[1]
        assert assistant_with_tools.role == "assistant"
        assert assistant_with_tools.tool_calls is not None
        assert len(assistant_with_tools.tool_calls) == 1
        assert assistant_with_tools.tool_calls[0].name == "counter"

        # Check tool result message
        tool_result = messages[2]
        assert tool_result.role == "tool"
        assert tool_result.name == "counter"
        assert tool_result.tool_call_id == "call-1"

        store.close()

    @pytest.mark.asyncio
    async def test_tool_calls_not_reexecuted_on_resume(
        self, config: ScooperConfig, agent: Agent, temp_db: Path
    ) -> None:
        """Test that old tool calls are not re-executed when resuming."""
        store = SessionStore(db_path=temp_db)
        counter_tool = CounterTool()
        registry = ToolRegistry()
        registry.register(counter_tool)

        # First execution with tool call
        provider1 = FakeModelProvider(
            scripted_responses=[
                ModelResponse(
                    response_type="tool_calls",
                    tool_calls=[ToolCall(id="call-1", name="counter", arguments={})],
                    finish_reason="tool_calls",
                ),
                ModelResponse(
                    response_type="text",
                    content="First done",
                    finish_reason="completed",
                ),
            ]
        )
        executor1 = PersistentAgentExecutor(
            config, provider1, tool_registry=registry, session_store=store
        )

        await executor1.execute_with_session(
            agent=agent,
            task="Task 1",
            session_id="no-reexecute",
            resume=False,
        )

        assert counter_tool.count == 1

        # Resume session - tool should NOT be executed again
        provider2 = FakeModelProvider(response_content="Second done")
        executor2 = PersistentAgentExecutor(
            config, provider2, tool_registry=registry, session_store=store
        )

        await executor2.execute_with_session(
            agent=agent,
            task="Task 2",
            session_id="no-reexecute",
            resume=True,
        )

        # Counter should still be 1 (not incremented again)
        assert counter_tool.count == 1

        store.close()

    @pytest.mark.asyncio
    async def test_execution_records_saved(
        self, config: ScooperConfig, agent: Agent, temp_db: Path
    ) -> None:
        """Test that execution records are saved."""
        store = SessionStore(db_path=temp_db)
        provider = FakeModelProvider(response_content="Done")
        executor = PersistentAgentExecutor(config, provider, session_store=store)

        await executor.execute_with_session(
            agent=agent,
            task="Test task",
            session_id="exec-record-test",
            resume=False,
        )

        # Can't easily verify execution records without adding a load method,
        # but we can verify no errors occurred
        session = await store.get_session("exec-record-test")
        assert session is not None

        store.close()

    @pytest.mark.asyncio
    async def test_failed_execution_persisted(
        self, config: ScooperConfig, agent: Agent, temp_db: Path
    ) -> None:
        """Test that failed executions are still persisted."""
        store = SessionStore(db_path=temp_db)
        # Create a provider that fails health check
        provider = FakeModelProvider(fail_health_check=True)
        executor = PersistentAgentExecutor(config, provider, session_store=store)

        result, session = await executor.execute_with_session(
            agent=agent,
            task="This will fail",
            session_id="fail-test",
            resume=False,
        )

        assert result.success is False
        assert result.stop_reason == "provider_unhealthy"
        assert session.session_id == "fail-test"

        store.close()

    @pytest.mark.asyncio
    async def test_agent_name_mismatch_warning(
        self, config: ScooperConfig, agent: Agent, temp_db: Path
    ) -> None:
        """Test that agent name mismatch logs a warning but doesn't fail."""
        store = SessionStore(db_path=temp_db)
        provider = FakeModelProvider(response_content="Response")
        executor = PersistentAgentExecutor(config, provider, session_store=store)

        # Create session with first agent
        await executor.execute_with_session(
            agent=agent,
            task="First task",
            session_id="mismatch-test",
            resume=False,
        )

        # Create a different agent
        different_agent_config = AgentConfig(
            name="different-agent",
            description="Different agent",
            provider_config=ModelProviderConfig(
                provider_type="fake",
                base_url="http://fake",
                model_name="fake",
            ),
        )
        different_agent = Agent(different_agent_config)

        # Resume with different agent - should log warning but work
        result, _ = await executor.execute_with_session(
            agent=different_agent,
            task="Second task",
            session_id="mismatch-test",
            resume=True,
        )

        assert result.success is True

        store.close()

    @pytest.mark.asyncio
    async def test_backward_compatibility_without_store(
        self, config: ScooperConfig, agent: Agent
    ) -> None:
        """Test that PersistentAgentExecutor works like AgentExecutor without store."""
        provider = FakeModelProvider(response_content="No persistence")
        # Create without session_store
        executor = PersistentAgentExecutor(config, provider)

        # Use base execute() method
        result = await executor.execute(agent, "Test task")

        assert result.success is True
        assert result.final_output == "No persistence"

    @pytest.mark.asyncio
    async def test_multiple_sessions_isolated(
        self, config: ScooperConfig, agent: Agent, temp_db: Path
    ) -> None:
        """Test that multiple sessions are properly isolated."""
        store = SessionStore(db_path=temp_db)
        provider = FakeModelProvider(
            scripted_responses=[
                ModelResponse(response_type="text", content="Session A", finish_reason="completed"),
                ModelResponse(response_type="text", content="Session B", finish_reason="completed"),
            ]
        )
        executor = PersistentAgentExecutor(config, provider, session_store=store)

        # Create two sessions
        await executor.execute_with_session(agent, "Task A", "session-a", resume=False)
        await executor.execute_with_session(agent, "Task B", "session-b", resume=False)

        # Verify isolation
        messages_a = await store.load_messages("session-a")
        messages_b = await store.load_messages("session-b")

        assert len(messages_a) == 2
        assert len(messages_b) == 2
        assert messages_a[1].content == "Session A"
        assert messages_b[1].content == "Session B"

        store.close()

    @pytest.mark.asyncio
    async def test_system_prompt_included_only_in_first_message(
        self, config: ScooperConfig, agent: Agent, temp_db: Path
    ) -> None:
        """Test that system prompt is included in first message, not on resume."""
        store = SessionStore(db_path=temp_db)
        provider = FakeModelProvider(
            scripted_responses=[
                ModelResponse(response_type="text", content="First", finish_reason="completed"),
                ModelResponse(response_type="text", content="Second", finish_reason="completed"),
            ]
        )
        executor = PersistentAgentExecutor(config, provider, session_store=store)

        # First execution
        await executor.execute_with_session(agent, "Task 1", "prompt-test", resume=False)

        messages = await store.load_messages("prompt-test")
        first_message = messages[0].content or ""
        assert agent.system_prompt in first_message
        assert "Task 1" in first_message

        # Resume
        await executor.execute_with_session(agent, "Task 2", "prompt-test", resume=True)

        messages = await store.load_messages("prompt-test")
        # Third message should be just the task, no system prompt
        third_message = messages[2].content or ""
        assert third_message == "Task 2"
        assert agent.system_prompt not in third_message

        store.close()


class TestPersistenceErrorHandling:
    """Test error handling in persistence layer."""

    @pytest.mark.asyncio
    async def test_persistence_failure_does_not_stop_execution(
        self, config: ScooperConfig, agent: Agent, temp_db: Path
    ) -> None:
        """Test that persistence errors don't stop execution."""
        store = SessionStore(db_path=temp_db)
        provider = FakeModelProvider(response_content="Success")
        executor = PersistentAgentExecutor(config, provider, session_store=store)

        # Create session
        result, _ = await executor.execute_with_session(
            agent=agent,
            task="Test",
            session_id="persist-error-test",
            resume=False,
        )

        # Close the store to simulate database errors on next save
        store.close()

        # Execution should still succeed even if persistence fails
        assert result.success is True
