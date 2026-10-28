"""Session-aware agent execution with resumable conversations.

This module extends the base AgentExecutor with session persistence capabilities,
enabling conversations to be saved, loaded, and resumed across program runs.
"""

import logging

from scooper.config import ScooperConfig
from scooper.exceptions import ExecutionLimitExceededError, SessionError
from scooper.models.base import Message, ModelProvider
from scooper.persistence.session_store import Session, SessionStore
from scooper.runtime.agent import Agent
from scooper.runtime.executor import AgentExecutor, ExecutionResult
from scooper.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class PersistentAgentExecutor(AgentExecutor):
    """Agent executor with session persistence and resumable conversations.

    This executor extends AgentExecutor to automatically persist conversation
    history and execution results to a SessionStore. It supports:
    - Creating new persisted sessions
    - Resuming from existing session history
    - Automatic message and execution persistence
    - Optional persistence (can be disabled)

    The executor maintains backward compatibility: it can be used without
    a session_store, in which case it behaves exactly like AgentExecutor.

    **SECURITY WARNING**: Like AgentExecutor, this class accepts ANY ToolRegistry.
    For production use, wrap tools in SafeToolRegistry with appropriate policies.
    See AgentExecutor docstring for security considerations.

    Attributes:
        config: Global Scooper configuration
        model_provider: Model provider for generating responses
        tool_registry: Optional tool registry for tool execution
        session_store: Optional session store for persistence
    """

    def __init__(
        self,
        config: ScooperConfig,
        model_provider: ModelProvider,
        tool_registry: ToolRegistry | None = None,
        session_store: SessionStore | None = None,
    ):
        """Initialize the persistent executor.

        Args:
            config: Global Scooper configuration
            model_provider: Model provider for generation
            tool_registry: Optional tool registry for tool execution.
                **SECURITY**: Use SafeToolRegistry for production to enforce
                permission policies and limits.
            session_store: Optional session store for persistence
        """
        super().__init__(config, model_provider, tool_registry)
        self.session_store = session_store

    async def execute_with_session(
        self,
        agent: Agent,
        task: str,
        session_id: str,
        resume: bool = False,
    ) -> tuple[ExecutionResult, Session]:
        """Execute an agent task with session persistence.

        This method creates or resumes a session, executes the agent,
        and persists all messages and execution results.

        Args:
            agent: The agent to execute
            task: The task or prompt for the agent
            session_id: Unique identifier for the session
            resume: If True, resume from existing session history

        Returns:
            Tuple of (ExecutionResult, Session)

        Raises:
            SessionError: If session_store is not configured
            SessionNotFoundError: If resume=True but session doesn't exist
        """
        if not self.session_store:
            raise SessionError("SessionStore is required for execute_with_session")

        # Handle session creation or retrieval
        if resume:
            # Load existing session
            session = await self.session_store.get_session(session_id)
            logger.info(f"Resuming session {session_id} for agent '{agent.name}'")

            # Verify agent name matches
            if session.agent_name != agent.name:
                logger.warning(
                    f"Session agent '{session.agent_name}' != current agent '{agent.name}'"
                )

            # Load conversation history
            conversation_history = await self.session_store.load_messages(session_id)
            logger.info(f"Loaded {len(conversation_history)} messages from session")

        else:
            # Create new session
            session = await self.session_store.create_session(
                session_id=session_id,
                agent_name=agent.name,
                metadata={"description": agent.description},
            )
            logger.info(f"Created new session {session_id} for agent '{agent.name}'")
            conversation_history = []

        # Execute agent with conversation history
        result = await self._execute_with_history(
            agent=agent,
            task=task,
            session_id=session_id,
            conversation_history=conversation_history,
        )

        # Persist execution result
        await self.session_store.save_execution(session_id, result)
        logger.debug(f"Saved execution result to session {session_id}")

        return result, session

    async def _execute_with_history(
        self,
        agent: Agent,
        task: str,
        session_id: str,
        conversation_history: list[Message],
    ) -> ExecutionResult:
        """Execute agent with existing conversation history.

        This is a modified version of AgentExecutor.execute() that:
        1. Starts with provided conversation history
        2. Adds the new user task
        3. Persists all new messages as they're created
        4. Returns the execution result

        Args:
            agent: The agent to execute
            task: The new task/prompt
            session_id: Session ID for persistence
            conversation_history: Existing conversation history

        Returns:
            ExecutionResult with the execution outcome
        """
        logger.info(f"Starting execution for agent '{agent.name}' on task: {task}")

        # Determine max iterations
        max_iterations = agent.config.max_iterations or self.config.max_iterations

        # Track execution state
        iteration_count = 0
        tool_calls_made = 0

        # Start with existing conversation history
        conversation = list(conversation_history)  # Copy to avoid mutation
        messages_before = len(conversation)

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

            # Add new user message
            # If this is the first message, include system prompt
            if len(conversation) == 0:
                user_message = Message(
                    role="user", content=f"{agent.system_prompt}\n\nTask: {task}"
                )
            else:
                # For resumed conversations, just add the task
                user_message = Message(role="user", content=task)

            conversation.append(user_message)
            await self._save_message_if_new(session_id, user_message)

            # Main execution loop (same as base executor)
            for iteration in range(max_iterations):
                iteration_count = iteration + 1
                logger.debug(f"Iteration {iteration_count}/{max_iterations}")

                # Generate model response
                from scooper.models.base import ModelRequest

                request = ModelRequest(
                    messages=conversation,
                    max_tokens=1024,
                    temperature=0.7,
                )

                response = await self.model_provider.generate(request)

                # Handle text response (final answer)
                if response.response_type == "text":
                    # Add assistant response to conversation
                    assistant_message = Message(
                        role="assistant",
                        content=response.content,
                    )
                    conversation.append(assistant_message)
                    await self._save_message_if_new(session_id, assistant_message)

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
                            "resumed": messages_before > 0,
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

                    # Add assistant message with tool calls
                    assistant_message = Message(
                        role="assistant",
                        content=response.content,
                        tool_calls=response.tool_calls,
                    )
                    conversation.append(assistant_message)
                    await self._save_message_if_new(session_id, assistant_message)

                    # Execute each requested tool
                    for tool_call in response.tool_calls:
                        tool_calls_made += 1
                        tool_result_message = await self._execute_tool_call(tool_call)
                        conversation.append(tool_result_message)
                        await self._save_message_if_new(session_id, tool_result_message)

                    # Continue to next iteration
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
            from scooper.exceptions import RuntimeMaxIterationsError

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

        except ExecutionLimitExceededError as e:
            logger.error(f"Execution limit exceeded: {e}")
            return ExecutionResult(
                success=False,
                iterations=iteration_count,
                stop_reason="tool_limit_exceeded",
                tool_calls_made=tool_calls_made,
                error=str(e),
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

    async def _save_message_if_new(self, session_id: str, message: Message) -> None:
        """Save a message to the session.

        Args:
            session_id: Session identifier
            message: Message to save
        """
        if not self.session_store:
            return

        try:
            await self.session_store.save_message(session_id, message)
        except Exception as e:
            # Log but don't fail execution on persistence errors
            logger.warning(f"Failed to persist message: {e}")
