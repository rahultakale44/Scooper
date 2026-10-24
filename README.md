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
- Tool system foundation with validation and execution
- Tool registry with timeout support
- Multi-step agent execution loop
- Agent-tool integration with error handling
- Conversation history and message types
- Deterministic unit testing infrastructure

### Planned 🎯
- SQLite-based session persistence
- Full Ollama integration
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

Scooper implements multi-step agent execution with tool integration.

### Working Examples

- **Basic Agent**: [`examples/basic_usage.py`](examples/basic_usage.py) - Simple agent setup and execution
- **Tool Registry**: [`examples/tool_execution.py`](examples/tool_execution.py) - Tool registration and execution
- **Multi-Step Agent**: [`examples/multistep_agent.py`](examples/multistep_agent.py) - Multi-step execution with tools

### Multi-Step Agent Example

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
```

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
├── sessions/     # Session and memory management
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
- Ollama integration
- SQLite persistence
- Tool execution with validation
- Session management

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
