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

Scooper is currently in Phase 1 of development. The foundation is being established with core contracts, interfaces, and minimal working implementations.

### Implemented ✅
- Python package structure and development tooling
- Core configuration and exception handling
- Model provider interface contracts
- Tool system foundation
- Minimal agent runtime architecture
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

For a complete working example, see [`examples/basic_usage.py`](examples/basic_usage.py).

Here's a minimal example of what's currently available:

```python
from scooper import __version__
from scooper.config import ScooperConfig

# Create configuration
config = ScooperConfig(log_level="INFO", max_iterations=10, timeout_seconds=300)

print(f"Scooper v{__version__} initialized")
print(f"Max iterations: {config.max_iterations}")
```

To run the full working example with agent execution:

```bash
python examples/basic_usage.py
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
