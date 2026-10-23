"""
Basic usage example for Scooper.

This example demonstrates the core concepts:
- Creating configuration
- Initializing an agent
- Executing a simple task with a fake provider
"""

import asyncio

from scooper import __version__
from scooper.config import ModelProviderConfig, ScooperConfig
from scooper.models import FakeModelProvider
from scooper.runtime import Agent, AgentConfig, AgentExecutor


async def main() -> None:
    """Run a simple agent execution example."""
    print(f"Scooper v{__version__} - Basic Usage Example\n")

    # Configure Scooper
    config = ScooperConfig(
        log_level="INFO",
        max_iterations=10,
        timeout_seconds=300,
    )
    print("✓ Created Scooper configuration")

    # Configure the model provider
    model_config = ModelProviderConfig(
        provider_type="fake",
        base_url="http://localhost:8000",
        model_name="test-model",
    )
    print("✓ Configured model provider")

    # Create a fake model provider for demonstration
    # In production, this would be an Ollama or other real provider
    provider = FakeModelProvider(
        response_content="I have analyzed your request and here is my response: "
        "The task has been completed successfully."
    )
    print("✓ Initialized model provider")

    # Configure the agent
    agent_config = AgentConfig(
        name="example-agent",
        description="A simple example agent for demonstration",
        provider_config=model_config,
        system_prompt="You are a helpful AI assistant. Analyze tasks and provide clear responses.",
        max_iterations=5,
    )

    # Create the agent
    agent = Agent(config=agent_config)
    print(f"✓ Created agent: {agent.name}\n")

    # Create the executor
    executor = AgentExecutor(config=config, model_provider=provider)
    print("Starting agent execution...\n")

    # Execute the agent on a task
    task = "Analyze the current state of AI agents and provide a brief summary"
    result = await executor.execute(agent, task)

    # Display results
    print("=" * 60)
    print("EXECUTION RESULTS")
    print("=" * 60)
    print(f"Status: {'✓ SUCCESS' if result.success else '✗ FAILED'}")
    print(f"Iterations: {result.iterations}")
    print(f"\nOutput:\n{result.final_output}")

    if result.metadata:
        print("\nMetadata:")
        for key, value in result.metadata.items():
            print(f"  {key}: {value}")

    if result.error:
        print(f"\nError: {result.error}")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
