"""
Ollama local agent example.

This example demonstrates using Scooper with a local Ollama instance.

PREREQUISITES:
1. Install Ollama from https://ollama.ai
2. Start Ollama: `ollama serve` (or Ollama desktop app)
3. Pull a model: `ollama pull llama2` (or your preferred model)
4. Ensure Ollama is running on http://localhost:11434

IMPORTANT: This example requires a running Ollama instance with a downloaded model.
           The tests do NOT require Ollama - they use mocked HTTP responses.
"""

import asyncio

from scooper.config import ModelProviderConfig, ScooperConfig
from scooper.models import OllamaModelProvider
from scooper.runtime import Agent, AgentConfig, AgentExecutor
from scooper.tools import Tool, ToolInput, ToolRegistry, ToolResult


class WeatherTool(Tool):
    """A simulated weather tool for demonstration."""

    @property
    def name(self) -> str:
        return "get_weather"

    @property
    def description(self) -> str:
        return "Get current weather for a location"

    def validate_input(self, tool_input: ToolInput) -> bool:
        """Validate weather tool input."""
        if not hasattr(tool_input, "location"):
            from scooper.exceptions import ToolValidationError

            raise ToolValidationError("Missing required parameter: location")
        return True

    async def execute(self, tool_input: ToolInput) -> ToolResult:
        """Simulate getting weather (no real API call)."""
        location = tool_input.location

        # Simulated weather data
        weather_data = {
            "san francisco": "Sunny, 72°F",
            "new york": "Cloudy, 65°F",
            "london": "Rainy, 58°F",
            "tokyo": "Clear, 68°F",
        }

        weather = weather_data.get(
            location.lower(), f"Weather data not available for {location}"
        )

        return ToolResult(
            success=True,
            output=weather,
            metadata={"location": location, "source": "simulated"},
        )


async def example_simple_chat():
    """Example: Simple chat with Ollama (no tools)."""
    print("=" * 70)
    print("EXAMPLE 1: Simple Chat with Ollama")
    print("=" * 70)
    print()

    # Configure Ollama provider
    provider_config = ModelProviderConfig(
        provider_type="ollama",
        base_url="http://localhost:11434",
        model_name="llama2",  # Change to your downloaded model
        timeout_seconds=60,
    )

    # Create agent
    agent_config = AgentConfig(
        name="chat_assistant",
        description="A helpful chat assistant",
        provider_config=provider_config,
        system_prompt="You are a helpful AI assistant. Answer questions concisely.",
    )

    agent = Agent(agent_config)
    config = ScooperConfig(log_level="INFO", max_iterations=3)

    # Initialize Ollama provider
    async with OllamaModelProvider(provider_config) as provider:
        # Check health
        print("→ Checking Ollama health...")
        is_healthy = await provider.health_check()
        print(f"  Ollama status: {'✓ Available' if is_healthy else '✗ Unavailable'}")
        print()

        if not is_healthy:
            print("ERROR: Ollama is not running or not responding.")
            print("Please ensure:")
            print("  1. Ollama is installed and running")
            print("  2. Model is downloaded: `ollama pull llama2`")
            print("  3. Ollama is accessible at http://localhost:11434")
            return

        # Create executor and run
        executor = AgentExecutor(config, provider)
        print("→ Asking: What is Python?")
        print()

        result = await executor.execute(agent, "What is Python? Answer in 2-3 sentences.")

        print(f"✓ Response received in {result.iterations} iteration(s):")
        print(f"  {result.final_output}")
        print()


async def example_with_tools():
    """Example: Ollama with tool integration."""
    print("=" * 70)
    print("EXAMPLE 2: Ollama with Tools")
    print("=" * 70)
    print()
    print("NOTE: This example demonstrates the framework setup.")
    print("Tool calling requires models that support function calling.")
    print("Most Ollama models currently return text responses.")
    print()

    # Configure
    provider_config = ModelProviderConfig(
        provider_type="ollama",
        base_url="http://localhost:11434",
        model_name="llama2",
        timeout_seconds=60,
    )

    agent_config = AgentConfig(
        name="tool_agent",
        description="An agent with tool access",
        provider_config=provider_config,
        system_prompt="You are a helpful assistant with access to tools.",
    )

    agent = Agent(agent_config)
    config = ScooperConfig(log_level="INFO", max_iterations=5)

    # Register tool
    registry = ToolRegistry()
    registry.register(WeatherTool())
    print(f"✓ Registered tools: {registry.list_tools()}")
    print()

    # Initialize provider
    async with OllamaModelProvider(provider_config) as provider:
        is_healthy = await provider.health_check()
        if not is_healthy:
            print("ERROR: Ollama not available")
            return

        executor = AgentExecutor(config, provider, registry)
        print("→ Asking: What's the weather in San Francisco?")
        print()

        result = await executor.execute(
            agent, "What's the weather in San Francisco? Answer briefly."
        )

        print(f"✓ Response (iterations={result.iterations}, tools={result.tool_calls_made}):")
        print(f"  {result.final_output}")
        print()

        if result.tool_calls_made == 0:
            print("NOTE: Model did not use tools. This is expected for most Ollama models.")
            print("      Tool calling support varies by model and requires specific formatting.")
        print()


async def example_configuration():
    """Example: Different Ollama configurations."""
    print("=" * 70)
    print("EXAMPLE 3: Configuration Options")
    print("=" * 70)
    print()

    # Custom configuration examples
    configs = [
        {
            "name": "Fast response (low temp)",
            "temperature": 0.3,
            "max_tokens": 512,
        },
        {
            "name": "Creative response (high temp)",
            "temperature": 1.2,
            "max_tokens": 1024,
        },
    ]

    for config_example in configs:
        print(f"→ Configuration: {config_example['name']}")
        print(f"  Temperature: {config_example['temperature']}")
        print(f"  Max tokens: {config_example['max_tokens']}")
        print()


async def main():
    """Run Ollama examples."""
    print()
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 20 + "OLLAMA LOCAL AGENT EXAMPLE" + " " * 22 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    print("PREREQUISITES:")
    print("  • Ollama installed and running (https://ollama.ai)")
    print("  • Model downloaded: ollama pull llama2")
    print("  • Ollama accessible at: http://localhost:11434")
    print()

    try:
        await example_simple_chat()
        await example_with_tools()
        await example_configuration()

        print("=" * 70)
        print("EXAMPLES COMPLETE")
        print("=" * 70)
        print()
        print("Next steps:")
        print("  • Try different models: ollama pull mistral, codellama, etc.")
        print("  • Adjust temperature and max_tokens for different behaviors")
        print("  • Create custom tools for your specific use cases")
        print("  • Experiment with system prompts for task-specific agents")
        print()

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n\nERROR: {e}")
        print("\nTroubleshooting:")
        print("  1. Ensure Ollama is running: `ollama serve`")
        print("  2. Check Ollama status: `ollama list`")
        print("  3. Verify model is downloaded: `ollama pull llama2`")
        print("  4. Test Ollama: `curl http://localhost:11434/api/tags`")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("WARNING: This example requires a running Ollama instance!")
    print("=" * 70)

    asyncio.run(main())
