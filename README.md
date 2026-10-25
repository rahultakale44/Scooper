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
- Deterministic unit testing infrastructure

### Planned 🎯
- Additional model providers (OpenAI, Anthropic, etc.)
- Advanced planning and multi-step orchestration
- Human approval workflows
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
```

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
