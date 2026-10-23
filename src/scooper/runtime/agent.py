"""Agent configuration and definition.

This module defines the Agent entity and its configuration,
separating agent identity from execution logic.
"""

from pydantic import BaseModel, Field

from scooper.config import ModelProviderConfig


class AgentConfig(BaseModel):
    """Configuration for an agent.

    Attributes:
        name: Unique identifier for the agent
        description: Human-readable description of the agent's purpose
        model_config: Configuration for the model provider
        system_prompt: System-level instructions for the agent
        max_iterations: Maximum execution iterations (overrides global config)
    """

    name: str = Field(
        description="Unique identifier for the agent",
    )

    description: str = Field(
        default="",
        description="Description of the agent's purpose and capabilities",
    )

    model_config_data: ModelProviderConfig = Field(
        description="Model provider configuration",
        alias="model_config",
    )

    system_prompt: str = Field(
        default="You are a helpful AI agent.",
        description="System-level instructions for the agent",
    )

    max_iterations: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="Max iterations for this agent (overrides global config)",
    )

    model_config = {
        "frozen": True,
        "populate_by_name": True,
    }


class Agent:
    """An AI agent with specific configuration and identity.

    Agents are stateless definitions that can be executed by the runtime.
    The actual execution state is managed separately by AgentExecutor.

    Attributes:
        config: The agent's configuration
    """

    def __init__(self, config: AgentConfig):
        """Initialize an agent with configuration.

        Args:
            config: Agent configuration
        """
        self.config = config

    @property
    def name(self) -> str:
        """Get the agent's name."""
        return self.config.name

    @property
    def description(self) -> str:
        """Get the agent's description."""
        return self.config.description

    @property
    def system_prompt(self) -> str:
        """Get the agent's system prompt."""
        return self.config.system_prompt

    def __repr__(self) -> str:
        """String representation of the agent."""
        return f"Agent(name='{self.name}', description='{self.description}')"
