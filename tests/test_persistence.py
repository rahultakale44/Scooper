"""Tests for SQLite session persistence."""

import tempfile
from pathlib import Path

import pytest

from scooper.exceptions import SessionError, SessionNotFoundError
from scooper.models.base import Message, ToolCall
from scooper.persistence import Session, SessionStore
from scooper.runtime.executor import ExecutionResult


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
async def store(temp_db: Path) -> SessionStore:
    """Create a session store with temporary database."""
    store = SessionStore(db_path=temp_db)
    yield store
    store.close()


class TestSessionStore:
    """Test SessionStore operations."""

    @pytest.mark.asyncio
    async def test_create_session(self, store: SessionStore) -> None:
        """Test creating a new session."""
        session = await store.create_session(
            session_id="test-session-1",
            agent_name="test-agent",
            metadata={"key": "value"},
        )

        assert session.session_id == "test-session-1"
        assert session.agent_name == "test-agent"
        assert session.metadata == {"key": "value"}
        assert session.created_at is not None
        assert session.updated_at is not None

    @pytest.mark.asyncio
    async def test_create_duplicate_session_fails(self, store: SessionStore) -> None:
        """Test that creating a duplicate session raises an error."""
        await store.create_session(
            session_id="duplicate",
            agent_name="agent-1",
        )

        with pytest.raises(SessionError, match="already exists"):
            await store.create_session(
                session_id="duplicate",
                agent_name="agent-2",
            )

    @pytest.mark.asyncio
    async def test_get_session(self, store: SessionStore) -> None:
        """Test retrieving a session by ID."""
        created = await store.create_session(
            session_id="get-test",
            agent_name="test-agent",
            metadata={"test": True},
        )

        retrieved = await store.get_session("get-test")

        assert retrieved.session_id == created.session_id
        assert retrieved.agent_name == created.agent_name
        assert retrieved.metadata == created.metadata
        assert retrieved.created_at == created.created_at

    @pytest.mark.asyncio
    async def test_get_nonexistent_session_fails(self, store: SessionStore) -> None:
        """Test that getting a non-existent session raises an error."""
        with pytest.raises(SessionNotFoundError, match="not found"):
            await store.get_session("nonexistent")

    @pytest.mark.asyncio
    async def test_list_sessions_empty(self, store: SessionStore) -> None:
        """Test listing sessions when none exist."""
        sessions = await store.list_sessions()
        assert sessions == []

    @pytest.mark.asyncio
    async def test_list_sessions(self, store: SessionStore) -> None:
        """Test listing all sessions."""
        await store.create_session("session-1", "agent-a")
        await store.create_session("session-2", "agent-b")
        await store.create_session("session-3", "agent-a")

        all_sessions = await store.list_sessions()
        assert len(all_sessions) == 3

        # Test filtering by agent name
        agent_a_sessions = await store.list_sessions(agent_name="agent-a")
        assert len(agent_a_sessions) == 2
        assert all(s.agent_name == "agent-a" for s in agent_a_sessions)

    @pytest.mark.asyncio
    async def test_delete_session(self, store: SessionStore) -> None:
        """Test deleting a session."""
        await store.create_session("delete-me", "agent")

        await store.delete_session("delete-me")

        with pytest.raises(SessionNotFoundError):
            await store.get_session("delete-me")

    @pytest.mark.asyncio
    async def test_delete_nonexistent_session_fails(self, store: SessionStore) -> None:
        """Test that deleting a non-existent session raises an error."""
        with pytest.raises(SessionNotFoundError, match="not found"):
            await store.delete_session("nonexistent")

    @pytest.mark.asyncio
    async def test_save_and_load_messages(self, store: SessionStore) -> None:
        """Test saving and loading conversation messages."""
        await store.create_session("msg-test", "agent")

        # Save multiple messages
        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there!"),
            Message(role="user", content="How are you?"),
            Message(role="assistant", content="I'm doing well!"),
        ]

        for msg in messages:
            await store.save_message("msg-test", msg)

        # Load messages
        loaded = await store.load_messages("msg-test")

        assert len(loaded) == 4
        assert loaded[0].role == "user"
        assert loaded[0].content == "Hello"
        assert loaded[1].role == "assistant"
        assert loaded[1].content == "Hi there!"
        assert loaded[2].role == "user"
        assert loaded[3].role == "assistant"

    @pytest.mark.asyncio
    async def test_save_message_with_tool_calls(self, store: SessionStore) -> None:
        """Test saving and loading messages with tool calls."""
        await store.create_session("tool-test", "agent")

        # Save message with tool calls
        tool_calls = [
            ToolCall(id="call-1", name="get_weather", arguments={"city": "NYC"}),
            ToolCall(id="call-2", name="get_time", arguments={"timezone": "EST"}),
        ]

        message = Message(
            role="assistant",
            content="Let me check that for you",
            tool_calls=tool_calls,
        )

        await store.save_message("tool-test", message)

        # Load and verify
        loaded = await store.load_messages("tool-test")

        assert len(loaded) == 1
        assert loaded[0].role == "assistant"
        assert loaded[0].content == "Let me check that for you"
        assert loaded[0].tool_calls is not None
        assert len(loaded[0].tool_calls) == 2
        assert loaded[0].tool_calls[0].id == "call-1"
        assert loaded[0].tool_calls[0].name == "get_weather"
        assert loaded[0].tool_calls[0].arguments == {"city": "NYC"}

    @pytest.mark.asyncio
    async def test_save_tool_result_message(self, store: SessionStore) -> None:
        """Test saving and loading tool result messages."""
        await store.create_session("tool-result-test", "agent")

        # Save tool result message
        tool_message = Message(
            role="tool",
            content="The weather in NYC is sunny, 72°F",
            tool_call_id="call-1",
            name="get_weather",
        )

        await store.save_message("tool-result-test", tool_message)

        # Load and verify
        loaded = await store.load_messages("tool-result-test")

        assert len(loaded) == 1
        assert loaded[0].role == "tool"
        assert loaded[0].content == "The weather in NYC is sunny, 72°F"
        assert loaded[0].tool_call_id == "call-1"
        assert loaded[0].name == "get_weather"

    @pytest.mark.asyncio
    async def test_load_messages_empty_session(self, store: SessionStore) -> None:
        """Test loading messages from a session with no messages."""
        await store.create_session("empty", "agent")

        messages = await store.load_messages("empty")
        assert messages == []

    @pytest.mark.asyncio
    async def test_load_messages_nonexistent_session_fails(self, store: SessionStore) -> None:
        """Test that loading messages from non-existent session fails."""
        with pytest.raises(SessionNotFoundError):
            await store.load_messages("nonexistent")

    @pytest.mark.asyncio
    async def test_save_message_nonexistent_session_fails(self, store: SessionStore) -> None:
        """Test that saving a message to non-existent session fails."""
        message = Message(role="user", content="Hello")

        with pytest.raises(SessionNotFoundError):
            await store.save_message("nonexistent", message)

    @pytest.mark.asyncio
    async def test_save_execution_result(self, store: SessionStore) -> None:
        """Test saving execution results."""
        await store.create_session("exec-test", "agent")

        result = ExecutionResult(
            success=True,
            final_output="Task completed successfully",
            iterations=3,
            stop_reason="completed",
            tool_calls_made=2,
            metadata={"duration": 1.5},
        )

        # Should not raise
        await store.save_execution("exec-test", result)

    @pytest.mark.asyncio
    async def test_save_execution_with_error(self, store: SessionStore) -> None:
        """Test saving execution results with error."""
        await store.create_session("exec-error-test", "agent")

        result = ExecutionResult(
            success=False,
            final_output=None,
            iterations=1,
            stop_reason="error",
            error="Something went wrong",
        )

        # Should not raise
        await store.save_execution("exec-error-test", result)

    @pytest.mark.asyncio
    async def test_save_execution_nonexistent_session_fails(self, store: SessionStore) -> None:
        """Test that saving execution to non-existent session fails."""
        result = ExecutionResult(
            success=True,
            final_output="Done",
            iterations=1,
            stop_reason="completed",
        )

        with pytest.raises(SessionNotFoundError):
            await store.save_execution("nonexistent", result)

    @pytest.mark.asyncio
    async def test_message_ordering(self, store: SessionStore) -> None:
        """Test that messages are loaded in correct chronological order."""
        await store.create_session("order-test", "agent")

        # Save messages in specific order
        for i in range(10):
            message = Message(role="user", content=f"Message {i}")
            await store.save_message("order-test", message)

        # Load and verify order
        loaded = await store.load_messages("order-test")

        assert len(loaded) == 10
        for i, msg in enumerate(loaded):
            assert msg.content == f"Message {i}"

    @pytest.mark.asyncio
    async def test_delete_cascade(self, store: SessionStore) -> None:
        """Test that deleting session cascades to messages and executions."""
        await store.create_session("cascade-test", "agent")

        # Add messages
        await store.save_message("cascade-test", Message(role="user", content="Hello"))
        await store.save_message("cascade-test", Message(role="assistant", content="Hi"))

        # Add execution
        result = ExecutionResult(
            success=True,
            final_output="Done",
            iterations=1,
            stop_reason="completed",
        )
        await store.save_execution("cascade-test", result)

        # Delete session
        await store.delete_session("cascade-test")

        # Verify session and messages are gone
        with pytest.raises(SessionNotFoundError):
            await store.get_session("cascade-test")

    @pytest.mark.asyncio
    async def test_schema_initialization_idempotent(self, temp_db: Path) -> None:
        """Test that schema initialization can be called multiple times safely."""
        # Create first store and initialize schema
        store1 = SessionStore(db_path=temp_db)
        await store1.create_session("test", "agent")
        store1.close()

        # Create second store with same database
        store2 = SessionStore(db_path=temp_db)
        session = await store2.get_session("test")
        assert session.session_id == "test"
        store2.close()

    @pytest.mark.asyncio
    async def test_context_manager(self, temp_db: Path) -> None:
        """Test using SessionStore as a context manager."""
        with SessionStore(db_path=temp_db) as store:
            await store.create_session("context-test", "agent")
            session = await store.get_session("context-test")
            assert session.session_id == "context-test"

        # Store should be closed after context
        # Verify by creating new store and checking session exists
        with SessionStore(db_path=temp_db) as store2:
            session = await store2.get_session("context-test")
            assert session.session_id == "context-test"

    @pytest.mark.asyncio
    async def test_async_context_manager(self, temp_db: Path) -> None:
        """Test using SessionStore as an async context manager."""
        async with SessionStore(db_path=temp_db) as store:
            await store.create_session("async-context-test", "agent")
            session = await store.get_session("async-context-test")
            assert session.session_id == "async-context-test"

        # Verify session persisted
        async with SessionStore(db_path=temp_db) as store2:
            session = await store2.get_session("async-context-test")
            assert session.session_id == "async-context-test"

    @pytest.mark.asyncio
    async def test_session_isolation(self, temp_db: Path) -> None:
        """Test that different session stores don't leak state."""
        # Create two separate stores with same database
        store1 = SessionStore(db_path=temp_db)
        store2 = SessionStore(db_path=temp_db)

        # Create session in store1
        await store1.create_session("isolated", "agent")

        # Should be visible in store2
        session = await store2.get_session("isolated")
        assert session.session_id == "isolated"

        store1.close()
        store2.close()

    @pytest.mark.asyncio
    async def test_complete_conversation_flow(self, store: SessionStore) -> None:
        """Test a complete conversation flow with multi-turn interaction."""
        # Create session
        await store.create_session("complete-flow", "assistant-agent")

        # Simulate multi-turn conversation with tool use
        conversation = [
            Message(role="user", content="What's the weather in NYC?"),
            Message(
                role="assistant",
                content="Let me check that",
                tool_calls=[ToolCall(id="call-1", name="get_weather", arguments={"city": "NYC"})],
            ),
            Message(
                role="tool",
                content="Sunny, 72°F",
                tool_call_id="call-1",
                name="get_weather",
            ),
            Message(
                role="assistant",
                content="The weather in NYC is sunny with a temperature of 72°F.",
            ),
            Message(role="user", content="Thank you!"),
            Message(role="assistant", content="You're welcome!"),
        ]

        # Save all messages
        for msg in conversation:
            await store.save_message("complete-flow", msg)

        # Save execution result
        result = ExecutionResult(
            success=True,
            final_output="You're welcome!",
            iterations=2,
            stop_reason="completed",
            tool_calls_made=1,
            metadata={"agent_name": "assistant-agent"},
        )
        await store.save_execution("complete-flow", result)

        # Load and verify
        loaded_messages = await store.load_messages("complete-flow")
        assert len(loaded_messages) == 6
        assert loaded_messages[0].content == "What's the weather in NYC?"
        assert loaded_messages[1].tool_calls is not None
        assert loaded_messages[2].role == "tool"
        assert loaded_messages[5].content == "You're welcome!"


class TestSession:
    """Test Session model."""

    def test_session_immutable(self) -> None:
        """Test that Session is immutable."""
        session = Session(
            session_id="test",
            agent_name="agent",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )

        with pytest.raises(ValueError):  # Pydantic raises ValidationError on frozen models
            session.session_id = "new-id"  # type: ignore

    def test_session_with_metadata(self) -> None:
        """Test Session with metadata."""
        metadata = {"version": "1.0", "environment": "test"}
        session = Session(
            session_id="test",
            agent_name="agent",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            metadata=metadata,
        )

        assert session.metadata == metadata
