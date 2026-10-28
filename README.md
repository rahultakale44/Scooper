# Scooper

**An extensible, open-source Agentic AI framework for Python**

[![CI](https://github.com/rahultakale44/Scooper/actions/workflows/ci.yml/badge.svg)](https://github.com/rahultakale44/Scooper/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

## What is Scooper?

Scooper is a Python framework designed for developers who need to create, execute, control, and evaluate AI agents in a structured and maintainable way. Unlike simple chatbot wrappers, Scooper provides:

- **Extensible Architecture**: Provider-independent model integrations, pluggable tools, and modular components
- **Control and Safety**: Execution policies, human approval workflows, and structured error handling
- **Observability**: Built-in logging, tracing foundation, and execution monitoring
- **Local-First Design**: Primary support for local models through Ollama, with optional hosted providers
- **Professional Tooling**: Type-safe APIs, async execution, comprehensive testing infrastructure

## Project Status

🚧 **Under Active Development**

Scooper is currently in Phase 2 of development, implementing multi-step agent execution with tool integration.

### Implemented ✅
- Python package structure and development tooling
- Core configuration and exception handling
- Model provider interface contracts with tool-call support
- **Ollama integration** with chat API and tool calling support
- Tool system foundation with validation and execution
- Tool registry with timeout support
- Multi-step agent execution loop
- Agent-tool integration with error handling
- Conversation history and message types
- **SQLite session persistence** with conversation history and execution records
- **Resumable agent sessions** with full conversation context across restarts
- **Tool safety and permissions** with allowlist/denylist, approval workflows, and execution limits
- Deterministic unit testing infrastructure

### Planned 🎯
- Additional model providers (OpenAI, Anthropic, etc.)
- Advanced planning and multi-step orchestration
- Checkpointing and recovery
- Tracing and evaluation framework
- Command-line interface (Typer)
- Optional FastAPI server
- MCP (Model Context Protocol) integration

## Requirements

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- **For Ollama**: [Ollama](https://ollama.ai) installed and running (optional)

## Installation

### For Development

```bash
# Clone the repository
git clone https://github.com/rahultakale44/Scooper.git
cd Scooper

# Create a virtual environment and install with uv
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"
```

### For Use (Future)

```bash
pip install scooper
```

*Note: Scooper is not yet published to PyPI*

## Quick Start

Scooper implements multi-step agent execution with tool integration and supports local LLMs via Ollama.

### Working Examples

- **Basic Agent**: [`examples/basic_usage.py`](examples/basic_usage.py) - Simple agent setup and execution
- **Tool Registry**: [`examples/tool_execution.py`](examples/tool_execution.py) - Tool registration and execution
- **Multi-Step Agent**: [`examples/multistep_agent.py`](examples/multistep_agent.py) - Multi-step execution with tools
- **Ollama Integration**: [`examples/ollama_local_agent.py`](examples/ollama_local_agent.py) - Using local Ollama models
- **Persistent Sessions**: [`examples/persistent_session.py`](examples/persistent_session.py) - SQLite session persistence
- **Resumable Sessions**: [`examples/resumable_sessions.py`](examples/resumable_sessions.py) - Complete resumable conversation workflow
- **Safe Tool Execution**: [`examples/safe_tool_execution.py`](examples/safe_tool_execution.py) - Permission policies, approval workflows, and execution limits

### Ollama Agent Example

```python
from scooper.config import ModelProviderConfig, ScooperConfig
from scooper.models import OllamaModelProvider
from scooper.runtime import Agent, AgentConfig, AgentExecutor

# Configure Ollama provider
provider_config = ModelProviderConfig(
    provider_type="ollama",
    base_url="http://localhost:11434",
    model_name="llama2",
    timeout_seconds=60,
)

# Create agent
agent_config = AgentConfig(
    name="assistant",
    provider_config=provider_config,
    system_prompt="You are a helpful assistant.",
)

agent = Agent(agent_config)
config = ScooperConfig(log_level="INFO", max_iterations=5)

# Execute with Ollama
async with OllamaModelProvider(provider_config) as provider:
    executor = AgentExecutor(config, provider)
    result = await executor.execute(agent, "What is Python?")
    print(result.final_output)
```

### Prerequisites for Ollama

1. Install Ollama: https://ollama.ai
2. Start Ollama: `ollama serve` (or use Ollama desktop app)
3. Pull a model: `ollama pull llama2`
4. Ensure accessible at: http://localhost:11434

### Multi-Step Agent Example (Testing)

For testing without Ollama, use the FakeModelProvider:

```python
from scooper.config import ModelProviderConfig, ScooperConfig
from scooper.models import FakeModelProvider, ModelResponse, ToolCall
from scooper.runtime import Agent, AgentConfig, AgentExecutor
from scooper.tools import ToolRegistry

# Configure
config = ScooperConfig(log_level="INFO", max_iterations=10)
agent_config = AgentConfig(
    name="assistant",
    provider_config=ModelProviderConfig(...),
    system_prompt="You are a helpful assistant.",
)

# Create agent with tools
agent = Agent(agent_config)
registry = ToolRegistry()
registry.register(my_tool)

# Script multi-step responses
scripted_responses = [
    ModelResponse(
        response_type="tool_calls",
        tool_calls=[ToolCall(id="1", name="search", arguments={"query": "python"})],
        finish_reason="tool_calls",
    ),
    ModelResponse(
        response_type="text",
        content="Based on search results, Python is...",
        finish_reason="completed",
    ),
]

provider = FakeModelProvider(scripted_responses=scripted_responses)
executor = AgentExecutor(config, provider, registry)

# Execute with tool integration
result = await executor.execute(agent, "What is Python?")
print(f"Result: {result.final_output}")
print(f"Tool calls made: {result.tool_calls_made}")
```

Run the examples:

```bash
# Basic agent
python examples/basic_usage.py

# Tool execution
python examples/tool_execution.py

# Multi-step agent with tools
python examples/multistep_agent.py

# Persistent sessions
python examples/persistent_session.py

# Resumable sessions (complete workflow)
python examples/resumable_sessions.py
```

## Resumable Sessions

Scooper supports **resumable agent sessions** - a real framework capability for maintaining conversation context across application restarts.

### How It Works

1. **Create a session**: Start a new persisted conversation
2. **Execute agent task**: Messages and results are automatically saved
3. **Close application**: Session data persists in SQLite
4. **Reopen application**: Load session and conversation history
5. **Continue conversation**: Agent has full context from previous interactions

### Basic Usage

```python
from scooper.config import ScooperConfig, ModelProviderConfig
from scooper.models import FakeModelProvider
from scooper.persistence import SessionStore
from scooper.runtime import Agent, AgentConfig, PersistentAgentExecutor

# Setup
config = ScooperConfig()
agent_config = AgentConfig(
    name="assistant",
    provider_config=ModelProviderConfig(...),
)
agent = Agent(agent_config)

# Create persistent executor with session store
store = SessionStore(db_path="my_sessions.db")
provider = FakeModelProvider(response_content="Hello!")
executor = PersistentAgentExecutor(
    config=config,
    model_provider=provider,
    session_store=store,
)

# First conversation - create new session
result1, session = await executor.execute_with_session(
    agent=agent,
    task="Hi, I'm starting a new conversation",
    session_id="user-123",
    resume=False,  # Create new
)

# Close application (session persists in database)
store.close()

# --- Application restart ---

# Reopen and resume
store = SessionStore(db_path="my_sessions.db")
executor = PersistentAgentExecutor(config, provider, session_store=store)

result2, session = await executor.execute_with_session(
    agent=agent,
    task="Do you remember what we discussed?",
    session_id="user-123",
    resume=True,  # Resume existing
)
# Agent has full conversation history!
```

### Key Features

- ✅ **Full history preservation**: All messages, tool calls, and results persist
- ✅ **Automatic persistence**: Messages saved as conversation progresses
- ✅ **Cross-restart continuity**: Close and reopen without losing context
- ✅ **Multiple sessions**: Manage concurrent conversations independently
- ✅ **Tool call preservation**: Tool calls and results correctly restored
- ✅ **Backward compatible**: Works with or without persistence
- ✅ **No replays**: Historical tool calls aren't re-executed on resume

### Use Cases

- **Chat applications**: Maintain conversation context across sessions
- **Long-running tasks**: Resume interrupted agent workflows
- **Multi-session agents**: Handle multiple concurrent conversations
- **Debugging**: Review complete conversation history and execution flow
- **Context building**: Agents build understanding over multiple interactions

See [`examples/resumable_sessions.py`](examples/resumable_sessions.py) for a complete working demonstration.

## Tool Safety & Permissions

Scooper provides **opt-in safety controls** for tool execution. When using `SafeToolRegistry`, permission checks are enforced in Python before tool execution, ensuring models cannot grant themselves permissions.

**IMPORTANT SECURITY NOTE**: Safety controls are **opt-in**, not automatic. Using the standard `ToolRegistry` provides **NO** permission enforcement, approval workflows, or execution limits. For production systems with untrusted models or sensitive tools, you **MUST** use `SafeToolRegistry`.

### Safety Principles

- 🔒 **Model is never the authority**: When using SafeToolRegistry, all permission checks are enforced in Python
- 🚫 **Fail closed**: Approval-required tools fail without approval mechanism
- ⚡ **Pre-execution enforcement**: Checks run before side effects occur (with SafeToolRegistry)
- 📊 **Execution limits**: Prevent runaway tool usage (with SafeToolRegistry)
- 🎯 **Explicit policies**: Allowlist/denylist with clear precedence rules
- ⚠️ **Opt-in by design**: Regular `ToolRegistry` has NO safety controls - use `SafeToolRegistry`

### Permission Levels

Tools can declare their permission requirements:

```python
from scooper.tools import Tool, ToolPermissionLevel

class ReadTool(Tool):
    @property
    def permission_level(self) -> ToolPermissionLevel:
        return ToolPermissionLevel.ALLOWED  # No approval needed

class DeleteTool(Tool):
    @property
    def permission_level(self) -> ToolPermissionLevel:
        return ToolPermissionLevel.REQUIRES_APPROVAL  # Must be approved
```

### Permission Policies

Configure allowlists, denylists, and approval workflows:

```python
from scooper.tools import ToolRegistry, SafeToolRegistry
from scooper.tools.permissions import ToolPermissionPolicy

# Register tools
registry = ToolRegistry()
registry.register(ReadTool())
registry.register(WriteTool())
registry.register(DeleteTool())

# Option 1: Allowlist only specific tools
policy = ToolPermissionPolicy(
    allowlist={"read_tool", "write_tool"}  # Only these allowed
)

# Option 2: Deny dangerous tools
policy = ToolPermissionPolicy(
    denylist={"delete_tool", "execute_command"}  # Always denied
)

# Option 3: Combined (denylist overrides allowlist)
policy = ToolPermissionPolicy(
    allowlist={"read_tool", "write_tool", "delete_tool"},
    denylist={"delete_tool"}  # Denied even though on allowlist
)

# Wrap registry with policy
safe_registry = SafeToolRegistry(registry, policy=policy)
```

### Approval Workflows

Require human approval for sensitive operations:

```python
from scooper.tools.permissions import ApprovalRequest

async def approval_callback(request: ApprovalRequest) -> bool:
    """Custom approval logic - could show UI, log audit trail, etc."""
    print(f"Tool: {request.tool_name}")
    print(f"Arguments: {request.arguments}")
    print(f"Session: {request.session_id}")
    
    # Implement your approval logic
    if request.tool_name == "delete_tool":
        return False  # Deny deletes
    return True  # Approve others

policy = ToolPermissionPolicy(approval_callback=approval_callback)
safe_registry = SafeToolRegistry(registry, policy=policy)

# Tool requiring approval will trigger callback
result = await safe_registry.execute("delete_tool", tool_input)
# Raises ToolApprovalDeniedError if denied
```

### Execution Limits

Prevent runaway tool usage with per-execution limits:

```python
# Limit to 5 tool calls per execution
safe_registry = SafeToolRegistry(
    registry,
    max_tool_calls_per_execution=5
)

# Use with executor
executor = AgentExecutor(config, model_provider, tool_registry=safe_registry)
result = await executor.execute(agent, task)

# Execution stops with ExecutionLimitExceededError if limit reached
# result.stop_reason == "tool_limit_exceeded"
```

### Policy Semantics

1. **Denylist always takes precedence** over allowlist
2. **If allowlist configured**, tool must be on it (unless denied)
3. **No allowlist** = allow all (unless denied)
4. **Approval required** = fails closed without approval handler
5. **Enforcement order**: limits → lookup → permission → approval → execution

### Error Handling

All permission errors can be caught and handled:

```python
from scooper.exceptions import (
    ToolPermissionDeniedError,     # Policy denied tool
    ToolApprovalRequiredError,     # Needs approval but no handler
    ToolApprovalDeniedError,       # Approval explicitly denied
    ExecutionLimitExceededError,   # Hit call limit
)

try:
    result = await safe_registry.execute("risky_tool", tool_input)
except ToolPermissionDeniedError as e:
    print(f"Blocked by policy: {e}")
except ToolApprovalDeniedError as e:
    print(f"User denied approval: {e}")
except ExecutionLimitExceededError as e:
    print(f"Hit execution limit: {e}")
```

### Integration with Agent Runtime

**CRITICAL**: SafeToolRegistry must be explicitly used. The executors accept any ToolRegistry:

```python
# ⚠️ UNSAFE: Regular registry has NO safety controls
unsafe_registry = ToolRegistry()
unsafe_registry.register(DangerousTool())
executor = AgentExecutor(config, provider, tool_registry=unsafe_registry)
# Tool executes WITHOUT permission checks, approval, or limits!

# ✅ SAFE: Use SafeToolRegistry with policy
registry = ToolRegistry()
registry.register(DangerousTool())
policy = ToolPermissionPolicy(denylist={"dangerous_tool"})
safe_registry = SafeToolRegistry(registry, policy=policy)
executor = AgentExecutor(config, provider, tool_registry=safe_registry)
# Tool execution is now controlled by policy
```

SafeToolRegistry works with both executors:

```python
# With standard executor
executor = AgentExecutor(
    config=config,
    model_provider=provider,
    tool_registry=safe_registry  # Use safe registry
)

# With persistent executor (resumable sessions)
executor = PersistentAgentExecutor(
    config=config,
    model_provider=provider,
    tool_registry=safe_registry,
    session_store=store,
)

result = await executor.execute(agent, task)
# All tool calls enforced by policy
```

**Counter Reset**: When reusing a SafeToolRegistry across multiple executions:

```python
safe_registry = SafeToolRegistry(registry, max_tool_calls_per_execution=5)

# First execution
result1 = await executor1.execute(agent, task1)

# Reset counter before second execution
safe_registry.reset_call_count()

# Second execution with fresh limit
result2 = await executor2.execute(agent, task2)
```

### Security Best Practices

1. **Always use SafeToolRegistry in production**: Don't rely on models to respect boundaries
2. **Deny by default**: Use allowlists for sensitive environments
3. **Require approval**: Mark destructive operations as REQUIRES_APPROVAL
4. **Set execution limits**: Prevent infinite tool call loops
5. **Reset counters**: Call `reset_call_count()` between independent executions
6. **Log approval requests**: Maintain audit trails for compliance
7. **Validate arguments**: Don't log sensitive data in approval callbacks
8. **Test policies**: Verify denials work as expected
9. **Never use ToolRegistry directly in production**: It provides NO safety controls

### Security Limitations

- **Safety is opt-in**: Developers must explicitly use SafeToolRegistry
- **No automatic enforcement**: AgentExecutor accepts regular ToolRegistry
- **Counter persistence**: Tool call counters persist across executions
- **Type system doesn't prevent bypass**: Python's type system allows any registry
- **Documentation critical**: Developers must understand the security model

### Example: Production-Safe Configuration

```python
# Comprehensive safety configuration
policy = ToolPermissionPolicy(
    # Only allow necessary tools
    allowlist={"read_file", "search_docs", "calculate"},
    
    # Explicitly deny dangerous operations
    denylist={"execute_command", "delete_file", "write_system"},
    
    # Require approval for writes
    approval_callback=audit_and_approve_callback,
)

safe_registry = SafeToolRegistry(
    registry,
    policy=policy,
    max_tool_calls_per_execution=10,  # Reasonable limit
    session_id=user_session_id,  # For approval context
)

executor = AgentExecutor(config, provider, safe_registry)
```

### Complete Example

See [`examples/safe_tool_execution.py`](examples/safe_tool_execution.py) for a working demonstration of:
- Allowlist and denylist enforcement
- Approval workflows with callbacks
- Execution limits
- Combined policies
- Error handling
- Integration with executors

## Session Persistence

Scooper includes SQLite-based session persistence for storing conversation history and execution records across runs.

### Features

- **Session Management**: Create, retrieve, list, and delete sessions
- **Conversation History**: Persist all messages (user, assistant, tool) in chronological order
- **Tool Call Preservation**: Serialize and deserialize tool calls with arguments
- **Execution Records**: Track execution status, iterations, and results
- **Schema Versioning**: Built-in migration support for database evolution
- **Async-Compatible**: Non-blocking interface suitable for async workflows

### Basic Usage

```python
from scooper.persistence import SessionStore, Session
from scooper.models import Message, ToolCall

# Create a session store
store = SessionStore(db_path="my_sessions.db")

# Create a session
session = await store.create_session(
    session_id="user-123-session",
    agent_name="assistant",
    metadata={"user_id": "123", "context": "support"},
)

# Save conversation messages
await store.save_message(
    session.session_id, Message(role="user", content="Hello, can you help me?")
)

await store.save_message(
    session.session_id, Message(role="assistant", content="Of course! What do you need?")
)

# Load conversation history
messages = await store.load_messages(session.session_id)
for msg in messages:
    print(f"[{msg.role}] {msg.content}")

# Save execution result
from scooper.runtime import ExecutionResult

result = ExecutionResult(
    success=True, final_output="Task completed", iterations=2, stop_reason="completed"
)
await store.save_execution(session.session_id, result)

# List all sessions
sessions = await store.list_sessions()
for s in sessions:
    print(f"{s.session_id}: {s.agent_name}")

# Clean up
store.close()
```

### Context Manager Support

```python
# Automatic cleanup with context manager
async with SessionStore(db_path="sessions.db") as store:
    session = await store.create_session("session-1", "agent")
    # ... use store ...
# Connection automatically closed
```

### Database Schema

The persistence layer uses three main tables:

- **sessions**: Session metadata (ID, agent name, timestamps, metadata)
- **messages**: Conversation messages with sequence ordering
- **executions**: Execution records with status and results

Foreign key constraints ensure referential integrity, and cascading deletes clean up related data.

### Important Notes

- Persistence is **optional** - existing code works without a database
- Sessions are **isolated** - multiple stores can access the same database
- The store uses **parameterized queries** to prevent SQL injection
- Database path defaults to `scooper_sessions.db` in the current directory
- Schema version is tracked for future migrations

See [`examples/persistent_session.py`](examples/persistent_session.py) for comprehensive examples.

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=scooper --cov-report=html
```

### Code Quality

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Type checking
mypy src/scooper
```

## Architecture Overview

Scooper is designed with clear separation of concerns:

```
scooper/
├── agents/       # Agent definitions and configurations
├── runtime/      # Execution engine and lifecycle management
├── models/       # Model provider abstractions and adapters
├── tools/        # Tool registry and execution framework
├── persistence/  # Session storage and conversation history
├── sessions/     # Session and memory management (planned)
└── observability/# Logging, tracing, and evaluation
```

The architecture prioritizes:
- **Modularity**: Components can be swapped or extended independently
- **Type Safety**: Comprehensive type hints and Pydantic validation
- **Testability**: Dependency injection and deterministic testing
- **Async-First**: Built on asyncio for efficient execution

## Roadmap

### Phase 1: Foundation (Current)
- Core architecture and contracts
- Development infrastructure
- Basic runtime implementation

### Phase 2: Core Functionality
- Ollama integration ✅
- SQLite persistence ✅
- Tool execution with validation ✅
- Session management
- Additional model providers

### Phase 3: Advanced Features
- Planning and orchestration
- Human approval workflows
- Advanced observability
- CLI and optional API

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Security

For security concerns, please see [SECURITY.md](SECURITY.md).

## License

Apache License 2.0 - See [LICENSE](LICENSE) for details.

## Why "Scooper"?

The name reflects the framework's purpose: to help you scope, orchestrate, and operationalize AI agents with precision and control.

---

**Status**: Alpha | **Stability**: Experimental | **API**: Subject to change
