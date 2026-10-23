"""Agent execution engine.

This module implements the core execution loop for agents,
managing the interaction between agents, models, and tools.
"""

import logging
from typing import Any

from pydantic import BaseModel, Field

from scooper.config import ScooperConfig
from scooper.exceptions import RuntimeMaxIterationsError
from scooper.models.base import ModelProvider, ModelRequest, ModelResponse
from scooper.runtime.agent import Agent

logger = logging.getLogger(__name__)


class ExecutionResult(BaseModel):
    """Result of agent execution.

    Attributes:
        success: Whether execution completed successfully
        final_output: The final output from the agent
        iterations: Number of iterations executed
        error: Error message if execution failed
        metadata: Additional execution metadata
    """

    success: bool = Field(
        description="Whether execution completed successfully",
    )

    final_output: str | None = Field(
        default=None,
        description="Final output from the agent",
    )

    iterations: int = Field(
        description="Number of iterations executed",
    )

    error: str | None = Field(
        default=None,
        description="Error message if execution failed",
    )

    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional execution metadata",
    )

    model_config = {
        "frozen": True,
    }


class AgentExecutor:
    """Executes agents with configured model providers.

    The executor manages the execution lifecycle, enforcing iteration
    limits and coordinating between the agent and model provider.

    Attributes:
        config: Global Scooper configuration
        model_provider: Model provider for generating responses
    """

    def __init__(
        self,
        config: ScooperConfig,
        model_provider: ModelProvider,
    ):
        """Initialize the executor.

        Args:
            config: Global Scooper configuration
            model_provider: Model provider for generation
        """
        self.config = config
        self.model_provider = model_provider

        # Configure logging
        logging.basicConfig(
            level=getattr(logging, config.log_level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    async def execute(self, agent: Agent, task: str) -> ExecutionResult:
        """Execute an agent on a given task.

        This is a minimal implementation that demonstrates the execution
        pattern. Future versions will support tool calls, planning, and
        multi-step orchestration.

        Args:
            agent: The agent to execute
            task: The task or prompt for the agent

        Returns:
            ExecutionResult with the execution outcome

        Raises:
            RuntimeMaxIterationsError: If max iterations exceeded
        """
        logger.info(f"Starting execution for agent '{agent.name}' on task: {task}")

        # Determine max iterations
        max_iterations = agent.config.max_iterations or self.config.max_iterations

        try:
            # Check provider health
            is_healthy = await self.model_provider.health_check()
            if not is_healthy:
                logger.error("Model provider health check failed")
                return ExecutionResult(
                    success=False,
                    iterations=0,
                    error="Model provider is not available",
                )

            # For Phase 1, we do a simple single-iteration execution
            # Future phases will implement the full execution loop
            iteration_count = 0
            combined_prompt = f"{agent.system_prompt}\n\nTask: {task}"

            for _iteration in range(max_iterations):
                iteration_count += 1
                logger.debug(f"Iteration {iteration_count}/{max_iterations}")

                # Generate response
                request = ModelRequest(
                    prompt=combined_prompt,
                    max_tokens=1024,
                    temperature=0.7,
                )

                response: ModelResponse = await self.model_provider.generate(request)
                logger.debug(f"Model response: {response.content[:100]}...")

                # For Phase 1, we complete after first iteration
                # Future versions will check for tool calls and continue loop
                logger.info(f"Execution completed in {iteration_count} iteration(s)")

                return ExecutionResult(
                    success=True,
                    final_output=response.content,
                    iterations=iteration_count,
                    metadata={
                        "agent_name": agent.name,
                        "finish_reason": response.finish_reason,
                        "token_count": response.token_count,
                    },
                )

            # Should not reach here in Phase 1, but included for completeness
            raise RuntimeMaxIterationsError(f"Maximum iterations ({max_iterations}) exceeded")

        except RuntimeMaxIterationsError:
            logger.error(f"Max iterations ({max_iterations}) exceeded")
            raise

        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return ExecutionResult(
                success=False,
                iterations=iteration_count if "iteration_count" in locals() else 0,
                error=str(e),
            )
