"""Example: Resumable Agent Sessions

This example demonstrates the complete workflow for resumable agent sessions:
1. Create a new session and execute an agent task
2. Close the application (simulated)
3. Reopen and load the previous session
4. Continue the conversation with full history

This is a real framework capability, not just documentation.

Prerequisites:
- Install Scooper: pip install .
- No external dependencies needed (uses FakeModelProvider)
"""

import asyncio
from pathlib import Path

from scooper.config import ModelProviderConfig, ScooperConfig
from scooper.models import FakeModelProvider
from scooper.persistence import SessionStore
from scooper.runtime import Agent, AgentConfig, PersistentAgentExecutor


async def example_1_create_and_execute() -> None:
    """Example 1: Create a new session and execute a task."""
    print("\n" + "=" * 70)
    print("Example 1: Creating New Session")
    print("=" * 70 + "\n")

    # Setup
    db_path = Path("resumable_demo.db")
    config = ScooperConfig(log_level="INFO", max_iterations=10)

    agent_config = AgentConfig(
        name="chat-assistant",
        description="A helpful chat assistant",
        provider_config=ModelProviderConfig(
            provider_type="fake",
            base_url="http://fake",
            model_name="fake",
        ),
        system_prompt="You are a helpful AI assistant. Remember our conversation.",
    )

    agent = Agent(agent_config)

    # Create session store and executor
    store = SessionStore(db_path=db_path)
    provider = FakeModelProvider(
        response_content="Hello! I'm your AI assistant. How can I help you today?"
    )
    executor = PersistentAgentExecutor(
        config=config,
        model_provider=provider,
        session_store=store,
    )

    # Execute first task with new session
    print("🤖 Starting new conversation session...")
    result, session = await executor.execute_with_session(
        agent=agent,
        task="Hi! I'm starting a new conversation.",
        session_id="demo-session-001",
        resume=False,  # Create new session
    )

    print(f"\n✓ Session created: {session.session_id}")
    print(f"  Agent: {session.agent_name}")
    print(f"  Created: {session.created_at[:19]}")
    print("\n💬 User: Hi! I'm starting a new conversation.")
    print(f"🤖 Assistant: {result.final_output}")
    print(f"\n📊 Execution: {result.iterations} iteration(s), success={result.success}")

    # Verify messages were saved
    messages = await store.load_messages("demo-session-001")
    print(f"\n💾 Saved {len(messages)} messages to database")

    store.close()
    print("\n✓ Database closed. Application would exit here.\n")


async def example_2_resume_session() -> None:
    """Example 2: Resume from existing session (simulating app restart)."""
    print("\n" + "=" * 70)
    print("Example 2: Resuming Session (After Restart)")
    print("=" * 70 + "\n")

    # Setup (as if starting fresh)
    db_path = Path("resumable_demo.db")
    config = ScooperConfig(log_level="INFO", max_iterations=10)

    agent_config = AgentConfig(
        name="chat-assistant",
        description="A helpful chat assistant",
        provider_config=ModelProviderConfig(
            provider_type="fake",
            base_url="http://fake",
            model_name="fake",
        ),
        system_prompt="You are a helpful AI assistant. Remember our conversation.",
    )

    agent = Agent(agent_config)

    # Reopen session store
    print("🔄 Application restarted. Loading previous session...")
    store = SessionStore(db_path=db_path)

    # Verify session exists
    session = await store.get_session("demo-session-001")
    print(f"\n✓ Session found: {session.session_id}")
    print(f"  Last updated: {session.updated_at[:19]}")

    # Load conversation history
    history = await store.load_messages("demo-session-001")
    print(f"\n📜 Loaded conversation history ({len(history)} messages):")
    for i, msg in enumerate(history, 1):
        role_emoji = "👤" if msg.role == "user" else "🤖"
        content = (
            (msg.content or "")[:60] + "..."
            if msg.content and len(msg.content) > 60
            else (msg.content or "")
        )
        print(f"  {i}. {role_emoji} {msg.role}: {content}")

    # Continue conversation with new provider
    provider = FakeModelProvider(
        response_content="Yes, I remember our earlier conversation. What would you like to discuss?"
    )
    executor = PersistentAgentExecutor(
        config=config,
        model_provider=provider,
        session_store=store,
    )

    # Resume and continue
    print("\n💬 User: Do you remember our conversation?")
    result, _ = await executor.execute_with_session(
        agent=agent,
        task="Do you remember our conversation?",
        session_id="demo-session-001",
        resume=True,  # Resume existing session
    )

    print(f"🤖 Assistant: {result.final_output}")
    print(f"\n📊 Execution: {result.iterations} iteration(s), success={result.success}")

    # Check updated history
    updated_history = await store.load_messages("demo-session-001")
    print(f"\n💾 Conversation now has {len(updated_history)} messages")
    print("  (previous history + new exchange)")

    store.close()
    print("\n✓ Database closed.\n")


async def example_3_multi_turn_conversation() -> None:
    """Example 3: Multi-turn conversation with multiple resumes."""
    print("\n" + "=" * 70)
    print("Example 3: Multi-Turn Conversation")
    print("=" * 70 + "\n")

    db_path = Path("resumable_demo.db")
    config = ScooperConfig(log_level="ERROR", max_iterations=10)

    agent_config = AgentConfig(
        name="math-tutor",
        description="A patient math tutor",
        provider_config=ModelProviderConfig(
            provider_type="fake",
            base_url="http://fake",
            model_name="fake",
        ),
        system_prompt="You are a patient math tutor. Build on previous topics.",
    )

    agent = Agent(agent_config)
    store = SessionStore(db_path=db_path)

    # Simulate multiple conversation turns
    turns = [
        (
            "What is algebra?",
            "Algebra is a branch of mathematics dealing with symbols and rules for manipulating those symbols.",
        ),
        (
            "Can you give me an example?",
            "Sure! For example, x + 5 = 10. We can solve for x by subtracting 5 from both sides: x = 5.",
        ),
        (
            "What about quadratic equations?",
            "A quadratic equation is of the form ax² + bx + c = 0. We can solve it using the quadratic formula.",
        ),
    ]

    print("🎓 Starting math tutoring session...")

    for i, (user_input, assistant_response) in enumerate(turns):
        # Create provider with scripted response
        provider = FakeModelProvider(response_content=assistant_response)
        executor = PersistentAgentExecutor(
            config=config,
            model_provider=provider,
            session_store=store,
        )

        # First turn creates session, rest resume
        is_first = i == 0
        result, _ = await executor.execute_with_session(
            agent=agent,
            task=user_input,
            session_id="math-session",
            resume=not is_first,
        )

        print(f"\n{'📚 Turn ' + str(i + 1)}")
        print(f"💬 Student: {user_input}")
        print(f"🎓 Tutor: {result.final_output}")

        # Simulate "closing app" between turns
        if i < len(turns) - 1:
            store.close()
            store = SessionStore(db_path=db_path)

    # Show final conversation
    messages = await store.load_messages("math-session")
    print(f"\n✓ Complete conversation saved ({len(messages)} messages)")
    print("\nFull conversation history:")
    for msg in messages:
        role = "Student" if msg.role == "user" else "Tutor"
        if msg.content:
            print(f"  {role}: {msg.content[:80]}...")

    store.close()
    print("\n✓ Session persisted and can be resumed anytime.\n")


async def example_4_session_management() -> None:
    """Example 4: Managing multiple sessions."""
    print("\n" + "=" * 70)
    print("Example 4: Managing Multiple Sessions")
    print("=" * 70 + "\n")

    db_path = Path("resumable_demo.db")
    store = SessionStore(db_path=db_path)

    # List all sessions
    print("📋 All sessions in database:\n")
    sessions = await store.list_sessions()

    for session in sessions:
        messages = await store.load_messages(session.session_id)
        print(f"  • {session.session_id}")
        print(f"    Agent: {session.agent_name}")
        print(f"    Created: {session.created_at[:19]}")
        print(f"    Messages: {len(messages)}")
        print(f"    Last updated: {session.updated_at[:19]}")
        print()

    print(f"Total: {len(sessions)} session(s)")

    store.close()
    print("\n✓ Session management complete.\n")


async def example_5_cleanup() -> None:
    """Example 5: Cleanup demo database."""
    print("\n" + "=" * 70)
    print("Example 5: Cleanup")
    print("=" * 70 + "\n")

    db_path = Path("resumable_demo.db")

    if db_path.exists():
        print(f"🗑️  Deleting demo database: {db_path}")
        db_path.unlink()
        print("✓ Cleanup complete")
    else:
        print("No demo database to clean up")

    print()


async def main() -> None:
    """Run all examples demonstrating resumable sessions."""
    print("\n" + "=" * 70)
    print("Resumable Agent Sessions - Complete Workflow Demo")
    print("=" * 70)

    # Example 1: Create new session
    await example_1_create_and_execute()

    # Pause to simulate app restart
    print("⏸️  [Simulating application restart...]\n")
    await asyncio.sleep(0.5)

    # Example 2: Resume session
    await example_2_resume_session()

    # Example 3: Multi-turn conversation
    await example_3_multi_turn_conversation()

    # Example 4: Session management
    await example_4_session_management()

    # Example 5: Cleanup
    await example_5_cleanup()

    # Summary
    print("=" * 70)
    print("Key Takeaways")
    print("=" * 70)
    print("""
✅ Sessions persist across application restarts
✅ Conversation history is fully preserved
✅ Messages include system prompt, user input, and assistant responses
✅ Tool calls and results are correctly stored
✅ Multiple sessions can be managed independently
✅ Resume picks up exactly where you left off
✅ Backward compatible - works without sessions too

This is a real framework capability. You can:
- Create a session once and resume it many times
- Close and reopen your application
- Load conversation history and continue naturally
- Manage multiple concurrent sessions
- Access full message history for context

Try integrating this into your application!
    """)


if __name__ == "__main__":
    asyncio.run(main())
