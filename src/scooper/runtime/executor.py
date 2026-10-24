"""Agent execution engine.

This module implements the core execution loop for agents,
managing the interaction between agents, models, and tools.
"""

import logging
from typing import Any

from pydantic import BaseModel, Field

from scooper.config import ScooperConfig
from scooper.exceptions import (
    RuntimeMaxIterationsError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolValidationError,
)
from scooper.models.base import Message, ModelProvider, ModelRequest, ModelResponse, ToolCall
from scooper.runtime.agent import Agent
from scooper.tools.base import ToolInput
from scooper.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class ExecutionResult(BaseModel):
    """Result of agent execution.

    Attributes:
        success: Whether execution completed successfully
        final_output: The final output from the agent
        iterations: Number of iterations executed
        stop_reason: Why execution stopped (completed, max_iterations, error)
        tool_calls_made: Number of tool calls executed during the run
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

    stop_reason: str = Field(
        description="Why execution stopped (completed, max_iterations, error)",
    )

    tool_calls_made: int = Field(
        default=0,
        description="Number of tool calls executed during the run",
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
    """Executes agents with configured model providers and tools.

    The executor manages the multi-step execution lifecycle, coordinating
    between the agent, model provider, and tool registry. It enforces iteration
    limits and handles tool execution with proper error handling.

    Attributes:
        config: Global Scooper configuration
        model_provider: Model provider for generating responses
        tool_registry: Optional tool registry for tool execution
    """

    def __init__(
        self,
        config: ScooperConfig,
        model_provider: ModelProvider,
        tool_registry: ToolRegistry | None = None,
    ):
        """Initialize the executor.

        Args:
            config: Global Scooper configuration
            model_provider: Model provider for generation
            tool_registry: Optional tool registry for tool execution
        """
        self.config = config
        self.model_provider = model_provider
        self.tool_registry = tool_registry

        # Configure logging
        logging.basicConfig(
            level=getattr(logging, config.log_level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    async def execute(self, agent: Agent, task: str) -> ExecutionResult:
        """Execute an agent on a given task with multi-step tool integration.

        The executor runs a bounded loop where:
        1. The model generates a response (text or tool calls)
        2. If text response, execution completes successfully
        3. If tool calls, execute them via the registry
        4. Feed tool results back to the model
        5. Repeat until completion or max iterations

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

        # Track execution state
        iteration_count = 0
        tool_calls_made = 0
        conversation: list[Message] = []

        try:
            # Check provider health
            is_healthy = await self.model_provider.health_check()
            if not is_healthy:
                logger.error("Model provider health check failed")
                return ExecutionResult(
                    success=False,
                    iterations=0,
                    stop_reason="provider_unhealthy",
                    error="Model provider is not available",
                )

            # Initialize conversation with system prompt and user task
            conversation.append(
                Message(role="user", content=f"{agent.system_prompt}\n\nTask: {task}")
            )

            # Main execution loop
            for iteration in range(max_iterations):
                iteration_count = iteration + 1
                logger.debug(f"Iteration {iteration_count}/{max_iterations}")

                # Generate model response
                request = ModelRequest(
                    messages=conversation,
                    max_tokens=1024,
                    temperature=0.7,
                )

                response: ModelResponse = await self.model_provider.generate(request)

                # Handle text response (final answer)
                if response.response_type == "text":
                    logger.info(
                        f"Execution completed successfully in {iteration_count} iteration(s), "
                        f"{tool_calls_made} tool call(s)"
                    )

                    return ExecutionResult(
                        success=True,
                        final_output=response.content,
                        iterations=iteration_count,
                        stop_reason="completed",
                        tool_calls_made=tool_calls_made,
                        metadata={
                            "agent_name": agent.name,
                            "finish_reason": response.finish_reason,
                            "token_count": response.token_count,
                        },
                    )

                # Handle tool calls
                elif response.response_type == "tool_calls" and response.tool_calls:
                    if not self.tool_registry:
                        error_msg = "Model requested tool calls but no tool registry is configured"
                        logger.error(error_msg)
                        return ExecutionResult(
                            success=False,
                            iterations=iteration_count,
                            stop_reason="no_tool_registry",
                            tool_calls_made=tool_calls_made,
                            error=error_msg,
                        )

                    # Add assistant message with tool calls to conversation
                    conversation.append(
                        Message(
                            role="assistant",
                            content=response.content,
                            tool_calls=response.tool_calls,
                        )
                    )

                    # Execute each requested tool
                    for tool_call in response.tool_calls:
                        tool_calls_made += 1
                        tool_result_message = await self._execute_tool_call(tool_call)
                        conversation.append(tool_result_message)

                    # Continue to next iteration to process tool results
                    continue

                else:
                    # Unexpected response format
                    error_msg = f"Unexpected model response format: {response.response_type}"
                    logger.error(error_msg)
                    return ExecutionResult(
                        success=False,
                        iterations=iteration_count,
                        stop_reason="invalid_response",
                        tool_calls_made=tool_calls_made,
                        error=error_msg,
                    )

            # Exceeded max iterations
            logger.error(f"Max iterations ({max_iterations}) exceeded")
            raise RuntimeMaxIterationsError(
                f"Execution exceeded maximum iterations ({max_iterations})"
            )

        except RuntimeMaxIterationsError:
            return ExecutionResult(
                success=False,
                iterations=iteration_count,
                stop_reason="max_iterations",
                tool_calls_made=tool_calls_made,
                error=f"Maximum iterations ({max_iterations}) exceeded",
            )

        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return ExecutionResult(
                success=False,
                iterations=iteration_count,
                stop_reason="error",
                tool_calls_made=tool_calls_made,
                error=str(e),
            )

    async def _execute_tool_call(self, tool_call: ToolCall) -> Message:
        """Execute a single tool call and return the result as a message.

        This method handles tool lookup, validation, execution, and error handling,
        returning a structured tool message for the conversation history.

        Args:
            tool_call: The tool call to execute

        Returns:
            Message containing the tool execution result
        """
        logger.debug(f"Executing tool call: {tool_call.name} (id={tool_call.id})")

        # Type guard: this method should only be called when registry is not None
        assert self.tool_registry is not None, "Tool registry must not be None"

        try:
            # Convert arguments dict to ToolInput
            tool_input = ToolInput(**tool_call.arguments)

            # Execute tool via registry
            result = await self.tool_registry.execute(
                tool_name=tool_call.name,
                tool_input=tool_input,
            )

            if result.success:
                logger.debug(f"Tool {tool_call.name} succeeded: {str(result.output)[:100]}")
                content = (
                    str(result.output)
                    if result.output is not None
                    else "Tool executed successfully"
                )
            else:
                logger.warning(f"Tool {tool_call.name} failed: {result.error}")
                content = f"Tool execution failed: {result.error}"

            return Message(
                role="tool",
                content=content,
                tool_call_id=tool_call.id,
                name=tool_call.name,
            )

        except ToolNotFoundError as e:
            logger.error(f"Tool not found: {tool_call.name}")
            return Message(
                role="tool",
                content=f"Error: Tool '{tool_call.name}' not found. {str(e)}",
                tool_call_id=tool_call.id,
                name=tool_call.name,
            )

        except ToolValidationError as e:
            logger.error(f"Tool validation failed for {tool_call.name}: {e}")
            return Message(
                role="tool",
                content=f"Error: Invalid arguments for tool '{tool_call.name}'. {str(e)}",
                tool_call_id=tool_call.id,
                name=tool_call.name,
            )

        except ToolExecutionError as e:
            logger.error(f"Tool execution failed for {tool_call.name}: {e}")
            return Message(
                role="tool",
                content=f"Error: Tool execution failed. {str(e)}",
                tool_call_id=tool_call.id,
                name=tool_call.name,
            )

        except Exception as e:
            logger.error(f"Unexpected error executing tool {tool_call.name}: {e}")
            return Message(
                role="tool",
                content=f"Error: Unexpected error during tool execution. {str(e)}",
                tool_call_id=tool_call.id,
                name=tool_call.name,
            )
