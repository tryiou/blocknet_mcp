# AGENTS.md

## Project Overview

Python MCP Server Generator for Blocknet. Generates XBridge and XRouter MCP servers from API documentation. Entry:
`main.py`. Core: `scripts/generate/`. Tests: `tests/unit`, `tests/integration`.

## Commands

### Setup

```bash
./.venv/bin/python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

### Generate

```bash
./.venv/bin/python main.py dx              # XBridge
./.venv/bin/python main.py xr              # XRouter
./.venv/bin/python main.py ALL             # Both
./.venv/bin/python main.py dx --doc path   # Custom doc
```

### Test

```bash
./.venv/bin/pytest                         # All tests
./.venv/bin/pytest -v                      # Verbose
./.venv/bin/pytest tests/unit              # Unit only
./.venv/bin/pytest tests/integration       # Integration only

# Single test
./.venv/bin/pytest tests/unit/test_generator.py                        # File
./.venv/bin/pytest tests/unit/test_generator.py::TestGeneratorInit     # Class
./.venv/bin/pytest tests/unit/test_generator.py:42                     # By line
./.venv/bin/pytest tests/unit/test_generator.py::TestGeneratorInit::test_generator_init_with_xbridge  # Method
./.venv/bin/pytest generated/tests/ -vv --tb=long -s # Verbose
# Coverage
pytest --cov=scripts --cov-report=html
```

### Lint/Format (Ruff)

```bash
ruff check .           # Lint all
ruff check --fix .     # Auto-fix
ruff format .          # Format
```

### Live Testing

```bash
cp .env.example .env  # Add RPC credentials
./.venv/bin/python test_mcp_servers.py  # Requires live node
```

## Style Guide

### Imports (isort)

```python
# 1. Std lib
import argparse
from pathlib import Path

# 2. Third-party
import pydantic
from mcp import ClientSession

# 3. Local
from scripts.generate.generator import Generator
```

### Formatting

- Line length: 150
- 4 spaces, no tabs
- Double quotes (Ruff)
- Trailing commas in multi-line collections
- 2 blank lines between top-level definitions, 1 between methods

### Type Hints (Required)

- Use `|` for unions (Python 3.10+)
- Built-in types: `list`, `dict`, `str`, `int`, `bool`, `float`
- From typing: `Optional`, `List`, `Dict`, `Any`, `Callable`

```python
def func(arg: str, opt: int | None = None) -> bool:
```

### Naming

- Modules/packages: `snake_case`
- Classes: `PascalCase`
- Functions/methods/vars: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private: `_leading_underscore`
- Tests: `test_*.py`, `Test*`, `test_*`

### Error Handling

- Explicit exceptions with messages
- Specific types: `ValueError`, `FileNotFoundError`, `TypeError`, `KeyError`
- No bare `except:`
- Raise on invalid input (don't return None silently)

```python
if not Path(file).exists():
    raise FileNotFoundError(f"Not found: {file}")
```

### Async/Await

- `async def` for I/O-bound (MCP tools, HTTP)
- Always `await` coroutine calls
- pytest-asyncio: use `async def test_...`
- `asyncio.run()` only at top-level entry

### Pydantic v2

- `pydantic.BaseModel` for validation
- Explicit field types
- Use `Field(description=...)` for clarity

```python
class Config(BaseModel):
    host: str = Field(default="localhost", description="RPC host")
```

### Logging

- Use `structlog.get_logger()`
- Levels: `debug`, `info`, `warning`, `error`

```python
logger = structlog.get_logger()
logger.info("Event", key=value)
```

### Docstrings (Required)

- Triple double-quotes
- Google or NumPy style (consistent per file)
- Include: summary, Args (types), Returns (type), Raises

```python
def generate_server(prefix: str, doc_path: str | None = None) -> None:
    """Generate MCP server
    
    Args:
        prefix: 'dx' or 'xr'
        doc_path: Optional custom doc path
        
    Raises:
        FileNotFoundError: If doc_path missing
        ValueError: If prefix invalid
    """
```

### Constants & Organization

- Constants: ALL_CAPS at module level
- No magic numbers/strings
- One top-level class/function per file (< 500 lines)
- Test files mirror source structure

## Testing

### Structure

- `tests/unit/` - isolated components
- `tests/integration/` - end-to-end
- `conftest.py` - shared fixtures
- Use `tmp_path` for temp files

### Practices

- Arrange-Act-Assert (blank lines between phases)
- Mock external deps (HTTP, RPC) in unit tests
- Integration: safe/readonly if hitting real services
- Descriptive assertion messages

## Project

```
blocknet_mcp/
├── main.py                     # CLI entry
├── requirements.txt            # Dependencies
├── .ruff.toml                  # Lint/format config
├── scripts/generate/
│   ├── parser.py               # Parse API docs → ApiSpec
│   ├── generator.py            # Generate MCP servers
│   └── templates/              # Jinja2 templates
├── generated/                  # Gitignored output
├── tests/
│   ├── conftest.py             # Shared fixtures
│   ├── unit/
│   └── integration/
└── blocknet-api-docs/          # Source documentation
```

## Important

- `.env` contains RPC credentials (RPC_HOST, RPC_PORT, RPC_USER, RPC_PASSWORD). Never commit.
- `MCP_ALLOW_WRITE="false"` for read-only testing.
- Generated code in `generated/` is **never edited manually**; edit templates/generator instead.
- Python 3.10+ required.
- All deps in `requirements.txt`; no new deps without discussion.
- `.venv/` is the current python venv ; always use venv when running commands.
- Validate all inputs in generator/parser.
- Use read-only RPC accounts when possible.
