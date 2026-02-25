# Code Formatting with Ruff

Dead simple one-tool solution for code formatting and cleanup.

## Quick Start

### 1. Update environment (one time):
```bash
conda env update -f environment.yml
```

### 2. Format your code:
```bash
ruff check --fix src/ tests/
ruff format src/ tests/
```

Done! ✨

## What is Ruff?

**Ruff** is an extremely fast Python linter and formatter that replaces Black, isort, flake8, and more with a single tool.

## Commands

```bash
# Fix and format everything (USE THIS!)
ruff check --fix src/ tests/
ruff format src/ tests/

# Just check without changing files
ruff check src/ tests/
ruff format --check src/ tests/
```

## What Gets Fixed?

- ✅ Code formatting (spacing, indentation, line length)
- ✅ Import sorting
- ✅ Unused imports and variables
- ✅ Undefined names
- ✅ Basic syntax issues

## Configuration

Settings are in `pyproject.toml`:
- Line length: 120 characters
- Auto-fixes enabled
- Excludes: site/, sessions/, outputs/

## Learn More

Ruff documentation: https://docs.astral.sh/ruff/
