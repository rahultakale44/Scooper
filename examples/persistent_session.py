"""Example: Persistent Agent Sessions with SQLite

This example demonstrates how to use SessionStore to persist agent conversations
and recover them across program runs. The session history is stored in SQLite
and can be loaded later to continue conversations or review past interactions.

Features demonstrated:
- Creating a persistent session
- Saving conversation messages as they occur
- Storing execution results
- Closing and reopening the database
- Loading conversation history from a previous session
- Listing all sessions

Prerequisites:
- Install Scooper: pip install .
- No external dependencies needed (uses Python's built-in sqlite3)
"""

import asyncio
import uuid
from pathlib import Path

from scooper.config import ModelProviderConfig, ScooperConfig
from scooper.models.base import Message, ToolCall
from scooper.models.fake import FakeModelProvider
from scooper.persistence import SessionStore
from scooper.runtime.agent import Agent, AgentConfig
from scooper.runtime.executor import AgentExecutor, ExecutionResult


async def example_create_persistent_session() -> None:
    """Example 1: Create a session and persist a conversation."""
    print("\n=== Example 1: Creating a Persistent Session ===\n")

    # Create a session store with a specific database file
    db_path = Path("example_sessions.db")
    store = SessionStore(db_path=db_path)

    try:
        # Create a new session with a unique ID
        session_id = f"session-{uuid.uuid4().hex[:8]}"
        session = await store.create_session(
            session_id=session_id,
            agent_name="assistant",
            metadata={
                "user": "demo_user",
                "purpose": "example_conversation",
            },
        )

        print(f"Created session: {session.session_id}")
        print(f"Agent: {session.agent_name}")
        print(f"Metadata: {session.metadata}")

        # Simulate a conversation
        messages = [
            Message(role="user", content="Hello! Can you help me with Python?"),
            Message(role="assistant", content="Of course! What do you need help with?"),
            Message(role="user", content="How do I read a file?"),
            Message(
                role="assistant",
                content="You can use the open() function. Let me show you an example.",
            ),
        ]

        # Save each message
        for msg in messages:
            await store.save_message(session_id, msg)
            print(f"Saved: [{msg.role}] {msg.content}")

        # Simulate execution result
        result = ExecutionResult(
            success=True,
            final_output="You can use the open() function. Let me show you an example.",
            iterations=2,
            stop_reason="completed",
            tool_calls_made=0,
        )
        await store.save_execution(session_id, result)
        print(f"\nSaved execution result (success={result.success})")

        print(f"\n✓ Session {session_id} persisted to {db_path}")

    finally:
        store.close()


async def example_load_and_resume_session() -> None:
    """Example 2: Load conversation history from a previous session."""
    print("\n=== Example 2: Loading Session History ===\n")

    db_path = Path("example_sessions.db")
    store = SessionStore(db_path=db_path)

    try:
        # List all sessions
        sessions = await store.list_sessions()

        if not sessions:
            print("No sessions found. Run example 1 first.")
            return

        # Get the most recent session
        latest_session = sessions[0]
        print(f"Loading session: {latest_session.session_id}")
        print(f"Created: {latest_session.created_at}")
        print(f"Updated: {latest_session.updated_at}")

        # Load conversation history
        messages = await store.load_messages(latest_session.session_id)
        print(f"\nLoaded {len(messages)} messages:\n")

        for i, msg in enumerate(messages, 1):
            print(f"{i}. [{msg.role}] {msg.content}")

        print("\n✓ Successfully recovered conversation from database")

    finally:
        store.close()


async def example_conversation_with_tools() -> None:
    """Example 3: Persist a conversation with tool calls."""
    print("\n=== Example 3: Conversation with Tool Calls ===\n")

    db_path = Path("example_sessions.db")
    store = SessionStore(db_path=db_path)

    try:
        # Create session
        session_id = f"tool-session-{uuid.uuid4().hex[:8]}"
        await store.create_session(
            session_id=session_id,
            agent_name="tool-agent",
            metadata={"has_tools": True},
        )

        print(f"Created session with tools: {session_id}\n")

        # Simulate a conversation with tool calls
        conversation = [
            Message(role="user", content="What's the weather in San Francisco?"),
            Message(
                role="assistant",
                content="Let me check that for you.",
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        name="get_weather",
                        arguments={"city": "San Francisco", "units": "celsius"},
                    )
                ],
            ),
            Message(
                role="tool",
                content="Temperature: 18°C, Condition: Partly Cloudy",
                tool_call_id="call-1",
                name="get_weather",
            ),
            Message(
                role="assistant",
                content="The weather in San Francisco is partly cloudy with a temperature of 18°C.",
            ),
        ]

        # Save conversation
        for msg in conversation:
            await store.save_message(session_id, msg)

            if msg.role == "user":
                print(f"User: {msg.content}")
            elif msg.role == "assistant":
                if msg.tool_calls:
                    print(f"Assistant: {msg.content}")
                    for tc in msg.tool_calls:
                        print(f"  → Tool call: {tc.name}({tc.arguments})")
                else:
                    print(f"Assistant: {msg.content}")
            elif msg.role == "tool":
                print(f"  ← Tool result: {msg.content}")

        # Save execution
        result = ExecutionResult(
            success=True,
            final_output=conversation[-1].content,
            iterations=2,
            stop_reason="completed",
            tool_calls_made=1,
        )
        await store.save_execution(session_id, result)

        print("\n✓ Tool conversation persisted")

        # Reload and verify tool calls are preserved
        loaded_messages = await store.load_messages(session_id)
        assistant_msg = loaded_messages[1]

        print("\n✓ Verified: Tool calls correctly serialized/deserialized")
        print(f"   Tool calls in message: {len(assistant_msg.tool_calls or [])}")

    finally:
        store.close()


async def example_integrated_with_executor() -> None:
    """Example 4: Using persistence with AgentExecutor (manual integration)."""
    print("\n=== Example 4: Integration with AgentExecutor ===\n")

    db_path = Path("example_sessions.db")
    store = SessionStore(db_path=db_path)

    try:
        # Setup agent and executor
        config = ScooperConfig(max_iterations=5)
        provider_config = ModelProviderConfig(
            provider_type="fake",
            base_url="http://fake",
            model_name="fake-model",
        )
        agent_config = AgentConfig(
            name="persistent-agent",
            description="Agent with persistent memory",
            provider_config=provider_config,
            system_prompt="You are a helpful assistant that remembers conversations.",
        )

        agent = Agent(config=agent_config)
        model_provider = FakeModelProvider(response_content="I'll help you with that!")
        executor = AgentExecutor(config, model_provider)

        # Create a session
        session_id = f"exec-session-{uuid.uuid4().hex[:8]}"
        await store.create_session(
            session_id=session_id,
            agent_name=agent.name,
            metadata={"executor_example": True},
        )

        print(f"Created session: {session_id}")

        # Execute task
        task = "Help me understand Python decorators"
        print(f"Task: {task}\n")

        result = await executor.execute(agent, task)

        print("Execution completed:")
        print(f"  Success: {result.success}")
        print(f"  Iterations: {result.iterations}")
        print(f"  Output: {result.final_output}")

        # Manually persist the result
        # Note: In a production system, you might extend AgentExecutor to do this automatically
        user_message = Message(role="user", content=task)
        await store.save_message(session_id, user_message)

        if result.final_output:
            assistant_message = Message(role="assistant", content=result.final_output)
            await store.save_message(session_id, assistant_message)

        await store.save_execution(session_id, result)

        print("\n✓ Execution result saved to session")

    finally:
        store.close()


async def example_list_and_manage_sessions() -> None:
    """Example 5: List and manage multiple sessions."""
    print("\n=== Example 5: Managing Multiple Sessions ===\n")

    db_path = Path("example_sessions.db")
    store = SessionStore(db_path=db_path)

    try:
        # List all sessions
        all_sessions = await store.list_sessions()
        print(f"Total sessions: {len(all_sessions)}\n")

        # Group by agent
        agents = {}
        for session in all_sessions:
            if session.agent_name not in agents:
                agents[session.agent_name] = []
            agents[session.agent_name].append(session)

        # Display grouped sessions
        for agent_name, sessions in agents.items():
            print(f"Agent '{agent_name}': {len(sessions)} session(s)")
            for session in sessions[:3]:  # Show first 3
                print(f"  - {session.session_id} (created: {session.created_at[:19]})")

        # Filter by specific agent
        if agents:
            first_agent = list(agents.keys())[0]
            agent_sessions = await store.list_sessions(agent_name=first_agent)
            print(f"\nFiltered by agent '{first_agent}': {len(agent_sessions)} session(s)")

    finally:
        store.close()


async def example_cleanup() -> None:
    """Example 6: Cleanup - delete old sessions."""
    print("\n=== Example 6: Cleanup ===\n")

    db_path = Path("example_sessions.db")
    store = SessionStore(db_path=db_path)

    try:
        sessions = await store.list_sessions()
        print(f"Current sessions: {len(sessions)}")

        # Optionally delete example sessions (commented out by default)
        # Uncomment to actually delete:
        # for session in sessions:
        #     await store.delete_session(session.session_id)
        #     print(f"Deleted: {session.session_id}")

        print("\nTo delete sessions, uncomment the deletion code in this example.")
        print(f"Database file: {db_path.absolute()}")

    finally:
        store.close()


async def main() -> None:
    """Run all examples."""
    print("=" * 60)
    print("Scooper Persistent Session Examples")
    print("=" * 60)

    # Run examples in sequence
    await example_create_persistent_session()
    await example_load_and_resume_session()
    await example_conversation_with_tools()
    await example_integrated_with_executor()
    await example_list_and_manage_sessions()
    await example_cleanup()

    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)
    print("\nKey takeaways:")
    print("- Sessions persist across program runs")
    print("- All message types (user, assistant, tool) are preserved")
    print("- Tool calls and their arguments are correctly serialized")
    print("- You can query sessions by agent name or list all sessions")
    print("- Use context managers to ensure proper cleanup")
    print("\nNext steps:")
    print("- Integrate SessionStore with your agent workflow")
    print("- Add custom metadata to track session context")
    print("- Implement session resume logic to continue conversations")


if __name__ == "__main__":
    asyncio.run(main())
