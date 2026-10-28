# Contributing to Sentinel Software Factory

Thank you for your interest in contributing! We welcome contributions from the community.

## Code of Conduct

This project adheres to a [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## How to Contribute

### Reporting Bugs
- Use the GitHub issue tracker
- Include steps to reproduce, expected vs actual behavior
- Include relevant logs and environment details

### Suggesting Features
- Open a GitHub issue with the "enhancement" label
- Describe the use case and expected behavior
- Consider implementation complexity

### Pull Requests
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run tests: `pytest`
5. Ensure code quality: `ruff check . && mypy factory/`
6. Submit a PR with clear description

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR-USERNAME/sentinel-software-factory.git
cd sentinel-software-factory

# Install dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Start dev environment
./scripts/dev.sh
```

## Code Standards

- **Python**: Ruff for linting, MyPy for type checking, Black for formatting
- **TypeScript/React**: ESLint + Prettier
- **Commits**: Conventional Commits format (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`)
- **Tests**: Write tests for new functionality

## Running Tests

```bash
# All tests
pytest

# Specific test types
pytest tests/unit -v
pytest tests/integration -v

# With coverage
pytest --cov=factory --cov-report=html
```

## Adding Agents/Tools/Gates

See [Agent Guide](docs/agent-guide.md) for detailed instructions.

### Quick Reference

| Extension | Location | Registration |
|-----------|----------|--------------|
| Agent | `factory/agents/` | `AGENT_REGISTRY` in `agents/__init__.py` |
| Tool | `factory/tools/registry.py` | `_register_builtin_tools()` |
| Gate | `factory/validation/gates.py` | `get_gate_registry().register()` |
| Stage | `factory/config/stages.yaml` | Add to stages list |

## Architecture Principles

When contributing, keep these principles in mind:

1. **Local-first** — No mandatory cloud dependencies
2. **Governed autonomy** — Agents execute; policy retains control
3. **Engineering over hype** — Measurable outcomes, concrete workflows
4. **Transparent operations** — Surface run status, costs, gate results
5. **Security by default** — Secrets never in context, least privilege

## Security

- Never commit secrets, API keys, or credentials
- Report security vulnerabilities privately via GitHub Security Advisories
- See [SECURITY_AUDIT.md](SECURITY_AUDIT.md) for security posture

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for helping make Sentinel Software Factory better! 🛡️