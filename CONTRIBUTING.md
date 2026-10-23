# Contributing to Scooper

Thank you for your interest in contributing to Scooper! We welcome contributions from the community.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/Scooper.git
   cd Scooper
   ```
3. **Set up your development environment**:
   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install -e ".[dev]"
   ```

## Development Workflow

### Before Making Changes

1. Create a new branch for your work:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make sure all tests pass:
   ```bash
   pytest
   ```

### Making Changes

1. Write clear, maintainable code that follows the project's style
2. Add type hints to all public functions and methods
3. Write or update tests for your changes
4. Update documentation as needed
5. Follow the existing code organization and naming conventions

### Code Quality

Before submitting your changes, ensure they pass all quality checks:

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Run tests
pytest

# Run tests with coverage
pytest --cov=scooper --cov-report=html

# Type checking (if mypy is configured)
mypy src/scooper
```

### Commit Guidelines

We follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation changes
- `test:` Test additions or modifications
- `refactor:` Code refactoring
- `chore:` Maintenance tasks
- `ci:` CI/CD changes

Example:
```bash
git commit -m "feat: add Ollama model provider integration"
```

### Submitting Changes

1. Push your branch to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

2. Open a Pull Request on GitHub
3. Provide a clear description of:
   - What problem your PR solves
   - How you tested your changes
   - Any breaking changes or limitations

### Pull Request Guidelines

- Keep PRs focused on a single feature or fix
- Include tests for new functionality
- Update documentation for user-facing changes
- Ensure CI passes before requesting review
- Respond to review feedback promptly

## Code Style

- Follow PEP 8 (enforced by Ruff)
- Use type hints for function parameters and return values
- Keep functions small and focused
- Write docstrings for public APIs
- Prefer composition over inheritance
- Avoid global mutable state

## Testing

- Write unit tests for all new functionality
- Use pytest fixtures for common setup
- Mock external dependencies (APIs, file systems, etc.)
- Aim for high test coverage, but prioritize meaningful tests
- Test both success and error paths

## Documentation

- Update README.md for user-facing features
- Add docstrings to public functions and classes
- Update CHANGELOG.md following Keep a Changelog format
- Include code examples where helpful

## Need Help?

- Open an issue for bugs or feature requests
- Start a discussion for questions or ideas
- Check existing issues before creating new ones

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers and help them learn
- Focus on constructive feedback
- Assume good intentions

## License

By contributing to Scooper, you agree that your contributions will be licensed under the Apache License 2.0.
