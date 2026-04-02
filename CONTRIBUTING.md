# Contributing to MCP Router

Thank you for your interest in contributing to MCP Router!

## How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes
4. Run the test suite (`python -m pytest tests/ -v`)
5. Commit your changes (`git commit -m 'Add your feature'`)
6. Push to your branch (`git push origin feature/your-feature`)
7. Open a Pull Request

## Development Setup

```bash
uv venv .venv --python 3.12
uv pip install -e ".[dev]" --python .venv/bin/python
```

## Running Tests

```bash
.venv/bin/python -m pytest tests/ -v
```

## Code Standards

- Python 3.12+
- Type hints where practical
- Tests for new features
- Keep dependencies minimal

## Reporting Issues

Use the GitHub issue templates for bug reports and feature requests.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
