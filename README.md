# marimo + uv Starter Template

A starter template for [marimo](https://marimo.io) notebooks using [uv](https://github.com/astral-sh/uv) for dependency and project management. This template provides a modern Python development setup with best practices for notebook development.

## Features

- 🚀 Python 3.12 and 3.13 support
- 📦 Fast dependency management with `uv`
- 🧪 Testing setup with pytest
- 🎯 Code quality with Ruff (linting + formatting)
- 👷 CI/CD with GitHub Actions
- 📓 Interactive notebook development with marimo

## Prerequisites

- Python 3.12 or 3.13
- [uv](https://github.com/astral-sh/uv) installed

## Getting Started

1. Clone this repository:

   ```bash
   git clone https://github.com/yourusername/marimo-uv-starter-template
   cd marimo-uv-starter-template
   ```

2. Run the marimo editor:

   ```bash
   uv run marimo edit
   ```

If you already created `.venv` with Python 3.14, recreate it with a supported interpreter before running the project again:

```bash
uv sync --python 3.13 --dev
```

## Development

### Running Tests

```bash
# Run testing in your regular python files
uv run pytest tests
# Running testing in your marimo notebooks
uv run pytest notebooks
```

### Linting and formatting

```bash
uv run ruff check .
uv run ruff format .
```

## Project Structure

```markdown
├── .github/            # GitHub Actions workflows
├── src/               # Source code
│   └── app.py        # Sample marimo notebook
├── tests/            # Test files
├── pyproject.toml    # Project configuration
└── uv.lock           # Dependency lock file
```

## License

MIT
