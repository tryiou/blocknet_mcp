# Blocknet MCP Server Generator

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP Protocol](https://img.shields.io/badge/MCP-Model_Context_Protocol-green.svg)](https://modelcontextprotocol.io)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)

A code generator that creates Model Context Protocol (MCP) servers for Blocknet's XBridge and XRouter APIs from markdown
documentation.

## Overview

This tool generates fully-functional MCP servers that expose Blocknet's decentralized exchange (XBridge) and routing (
XRouter) functionality to AI assistants and other MCP clients. It parses Blocknet's API documentation and automatically
generates:

- Type-safe Python MCP servers using FastMCP
- Async RPC clients with proper error handling
- Comprehensive integration tests
- Configuration and logging infrastructure

## Features

- **Automatic Code Generation**: Parse markdown API docs and generate complete MCP servers
- **Type Safety**: Full Pydantic v2 validation and type hints
- **Async/Await**: Built on asyncio for high-performance I/O
- **Write Protection**: Sensitive operations are flagged and can be disabled via `MCP_ALLOW_WRITE`. The list of
  protected RPC methods is defined in `scripts/generate/write_protected.yaml` and can be customized.
- **Structured Logging**: Uses structlog for observability
- **Test Generation**: Auto-generates integration tests from sample requests
- **Security First**: No hardcoded credentials, environment-based config

## Quick Start

### One-Command Build

The `build.sh` script automates everything:

```bash
# Prerequisite: configure .env first (see below)
./build.sh
```

The script will:
- Verify Python 3.10+
- Create and set up a virtual environment
- Install dependencies
- Clone or update the Blocknet API docs
- Generate both XBridge and XRouter MCP servers

**Important**: You must have a `.env` file with valid RPC credentials before running `build.sh`.

### Manual Setup

```bash
# 1. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Generate MCP servers
python main.py dx    # Generate XBridge MCP server
python main.py xr    # Generate XRouter MCP server
python main.py ALL   # Generate both XBridge and XRouter (separate servers)

# 4. Configure credentials
cp .env.example .env
# Edit .env with your RPC credentials
```

## Prerequisites

- Python 3.10 or higher
- Access to a Blocknet node with RPC enabled
- Basic understanding of MCP protocol (see [MCP documentation](https://modelcontextprotocol.io))

## Installation

Clone the repository and set up the environment:

```bash
git clone <repository-url>
cd blocknet-mcp-server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

### Generate Servers

```bash
# Generate XBridge server (default documentation)
python main.py dx

# Generate XRouter server
python main.py xr

# Generate both servers (runs dx and xr separately)
python main.py ALL

# Use custom documentation file
python main.py dx --doc path/to/custom_xbridge.md

**Note**: When using `ALL`, the `--doc` path applies to both APIs. Typically you'll omit it to use each API's default documentation.

Generated code is placed in the `generated/` directory:


generated/
├── xbridge_mcp/ # XBridge MCP server
│ ├── main.py
│ ├── config.py
│ ├── security.py
│ ├── logging_config.py
│ ├── rpc/
│ │ ├── client.py
│ │ └── exceptions.py
│ └── generated/
│ ├── tools.py
│ ├── specs.py
│ └── __init__.py
└── xrouter_mcp/ # XRouter MCP server (same structure)

# Note: 'ALL' generates both directories independently, not a combined server

```

### Run Generated Servers

```bash
# Run XBridge server
python -m generated.xbridge_mcp.main

# Run XRouter server
python -m generated.xrouter_mcp.main

# Both run via stdio, connect with MCP client
```

### Command-Line Options

```
python main.py [dx|xr|ALL] [--doc PATH] [--prefix dx|xr|ALL] [--list-protected]

Positional:
  prefix                Server to generate: dx (XBridge), xr (XRouter), or ALL (both, separately)

Options:
  --doc PATH, -d PATH   Path to API documentation markdown file. For dx/xr: specific file. For ALL: same file used for both (default: each API's default doc)
  --prefix PREFIX, -p PREFIX  Alternative to positional arg
  --list-protected      List all write-protected RPC methods and exit
  --help                Show help message
```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
 # RPC Connection (required)
 RPC_HOST=localhost
 RPC_PORT=41414
 RPC_USER=your_rpc_username
 RPC_PASSWORD=your_rpc_password
 RPC_TIMEOUT=30

 # Blockchain data directory (volume mount for Docker blocknet-core container)
 BLOCKNET_CHAINDIR=~/.blocknet/

 # MCP Server Configuration
 MCP_LOG_LEVEL=INFO
 MCP_ALLOW_WRITE=false  # Set to true only for trusted environments
```

### Generated Server Configuration

Each generated server includes its own `config.py` that loads settings from environment variables. The server name,
port, and other parameters can be customized by editing the generated config or setting the appropriate environment
variables.

**Important Security Note**: `MCP_ALLOW_WRITE=false` prevents write operations (orders, transactions, config changes).
Enable only when you understand the risks.

### Write-Protected Methods

The generator uses `scripts/generate/write_protected.yaml` to define which RPC methods are considered write-protected.
These methods will be decorated with `@write_protected` in the generated server and require `MCP_ALLOW_WRITE=true` to
execute.

To list the current protected methods:

```bash
python main.py --list-protected
```

To customize, edit `scripts/generate/write_protected.yaml`. The YAML file should contain a mapping of prefixes (`dx`,
`xr`) to lists of RPC method names. If the file is missing or invalid, the generator falls back to built-in defaults.
Unknown method names (typos, outdated docs) will trigger a warning during generation.

## Architecture

### Code Generation Flow

```
API Documentation (Markdown)
         ↓
    [Parser] ← parser.py
         ↓
    ApiSpec (dataclasses)
         ↓
    [Generator] ← generator.py
         ↓
    Jinja2 Templates (templates/)
         ↓
    Generated MCP Server (generated/)
```

### Key Components

- **`parser.py`**: Generic markdown parser that extracts endpoints, parameters, and error codes from Blocknet-style
  documentation
- **`generator.py`**: Orchestrates code generation, builds configuration, and writes files
- **`templates/`**: Jinja2 templates for server components:
    - `server/main.py.jinja` - Entry point with MCP server setup
    - `server/config.py.jinja` - Configuration management
    - `server/rpc_client.py.jinja` - Async RPC client
    - `server/security.py.jinja` - Write protection decorator
    - `server/logging_config.py.jinja` - Structured logging
    - `tools/tools.py.jinja` - MCP tool functions
    - `tests/` - Test templates

### Data Models

```python
# From parser.py
@dataclass
class ParamSpec:
    name: str
    param_type: str
    required: bool
    description: str
    default_value: str | None


@dataclass
class EndpointSpec:
    rpc_method: str
    tool_name: str
    description: str
    params: list[ParamSpec]
    response_type: str
    error_codes: list[int]


@dataclass
class ApiSpec:
    name: str
    endpoints: dict[str, EndpointSpec]
    error_codes: dict[int, str]
```

## Project Structure

```
blocknet-mcp-server/
├── main.py                 # CLI entry point
├── requirements.txt        # Python dependencies
├── .ruff.toml             # Lint/format configuration
├── AGENTS.md              # Development guidelines
├── .env.example           # Environment template
├── blocknet-api-docs/     # Source API documentation (included)
│   └── source/includes/
│       ├── _xbridge.md   # XBridge API spec
│       └── _xrouter.md   # XRouter API spec
├── scripts/
│   └── generate/
│       ├── parser.py     # Markdown → ApiSpec
│       ├── generator.py  # Code generator
│       └── templates/    # Jinja2 templates
├── generated/             # Generated output (gitignored)
│   ├── xbridge_mcp/
│   ├── xrouter_mcp/
│   └── tests/            # AUTO-GENERATED test scaffolding
│       ├── conftest.py
│       ├── test_xbridge_mcp_integration.py
│       └── test_xrouter_mcp_integration.py
├── tests/                # Repository test files
│   ├── conftest.py       # Pytest fixtures
│   ├── unit/
│   │   ├── test_parser.py
│   │   └── test_generator.py
│   └── integration/
│       └── test_generator.py  # Generator E2E tests
└── test_mcp_servers.py   # Live integration test suite (root)
```

## Testing

### Unit Tests

```bash
pytest tests/unit              # Run unit tests only
pytest tests/unit -v           # Verbose output
pytest tests/unit/test_parser.py::TestParamSpec::test_python_type_string  # Specific test
```

Unit tests cover:

- Parser logic (type conversion, table parsing, error extraction)
- Generator initialization and configuration
- Template rendering

### Integration Tests

```bash
pytest tests/integration
```

Integration tests verify generated code structure and basic functionality without a live node.

### Live Testing

The `test_mcp_servers.py` script performs end-to-end tests against a real Blocknet node:

```bash
python test_mcp_servers.py
```

**Requirements**:

- Running Blocknet node with RPC access
- `.env` file with valid credentials
- `MCP_ALLOW_WRITE=false` (default) for read-only tests

The script:

1. Starts the generated MCP server as a subprocess
2. Connects via MCP client protocol
3. Discovers available tokens, orders, block data
4. Executes read-only tools and validates responses
5. Prints detailed summary with pass/fail/skip counts

### Coverage

```bash
pytest --cov=scripts --cov-report=html
```

## Development

### Code Style

This project uses **Ruff** for linting and formatting:

```bash
ruff check .              # Lint only
ruff check --fix .        # Auto-fix issues
ruff format .             # Format code
```

Configuration is in `.ruff.toml`. Key rules:

- Line length: 150 characters
- Python 3.10+ syntax
- Import sorting with isort
- Double quotes for strings

### Type Hints

All functions must have complete type hints. Use `|` for unions (Python 3.10+):

```python
def process(value: str, count: int | None = None) -> list[str]:
    ...
```

### Error Handling

- Raise explicit exceptions with descriptive messages
- Use specific exception types: `ValueError`, `FileNotFoundError`, `KeyError`, etc.
- Never use bare `except:`

### Docstrings

All public functions, classes, and methods require docstrings (Google or NumPy style):

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

### Adding New API Endpoints

1. Update the appropriate markdown file in `blocknet-api-docs/source/includes/`:
    - `_xbridge.md` for XBridge endpoints
    - `_xrouter.md` for XRouter endpoints
2. Follow the existing format: `## MethodName`, description, `### Request Parameters` table, samples
3. Regenerate: `python main.py dx` (or `xr`)
4. Review generated code in `generated/`
5. Run tests: `pytest` and `python test_mcp_servers.py`

### Regenerating After Documentation Changes

```bash
# Clean previous output (optional)
rm -rf generated/

# Regenerate
python main.py ALL

# Verify
pytest
```

## Security Considerations

### Write Protection

Write operations are guarded by the `@write_protected` decorator. The generated server checks `MCP_ALLOW_WRITE` at
runtime:

```python
# In generated/security.py
def write_protected(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        if not settings.allow_write:
            raise PermissionError("Write operations disabled (MCP_ALLOW_WRITE=false)")
        return await func(*args, **kwargs)

    return wrapper
```

Protected tools include:

**XBridge**: `dxMakeOrder`, `dxMakePartialOrder`, `dxTakeOrder`, `dxCancelOrder`, `dxFlushCancelledOrders`,
`dxSplitAddress`, `dxSplitInputs`, `dxLoadXBridgeConf`

**XRouter**: `xrUpdateNetworkServices`, `xrConnect`, `xrSendTransaction`, `xrService`, `xrServiceConsensus`,
`xrReloadConfigs`

### Credential Management

- Never commit `.env` file (included in `.gitignore`)
- Use environment variables or `.env` file (loaded via `python-dotenv`)
- Generated servers read credentials at startup, not at generation time
- RPC passwords are never logged

### Read-Only Testing

Always test with `MCP_ALLOW_WRITE=false` unless explicitly testing write operations in a safe environment.

## Troubleshooting

### "RPC client not initialized"

**Cause**: Server started without proper RPC configuration.

**Solution**: Check `.env` file exists and contains `RPC_USER` and `RPC_PASSWORD`. The server validates these on
startup.

### "Connection error" or timeout

**Cause**: Node not running, wrong host/port, or firewall blocking.

**Solution**:

- Verify node is running: `curl http://RPC_USER:RPC_PASSWORD@RPC_HOST:RPC_PORT/`
- Check `RPC_HOST` and `RPC_PORT` in `.env`
- Ensure RPC server is enabled in node config (`server=1`)

### Parser fails to extract parameters

**Cause**: Documentation format doesn't match expected pattern.

**Solution**: Ensure the markdown table follows the format:

```
Parameter | Type | Description
--- | --- | ---
param1 | string | Description text
```

The parser expects `### Request Parameters` section with a table.

### Generated tools not appearing

**Cause**: Tool function names must start with the prefix (`dx` or `xr`).

**Solution**: Check that the markdown method names start with the correct prefix (e.g., `dxGetOrders`). The parser
filters endpoints by prefix.

### Tests fail with "Expected dict, got str"

**Cause**: The RPC returned an error message instead of expected data.

**Solution**: Check RPC credentials have permission for that endpoint. Some RPC methods require specific account
balances or node configuration.

### Import errors when running generated server

**Cause**: Python path issues.

**Solution**: The generated server includes `sys.path.insert(0, str(Path(__file__).parent.parent))` to handle package
imports. Run from the project root or ensure the package structure is intact.

## Contributing

Contributions welcome! Please follow these guidelines:

1. **Code Style**: Run `ruff format .` and `ruff check .` before committing
2. **Tests**: Add unit tests for parser/generator changes; integration tests for new endpoints
3. **Documentation**: Update README if user-facing behavior changes
4. **Type Hints**: Complete type annotations required
5. **Docstrings**: All public APIs must be documented

### Development Workflow

```bash
# Create feature branch
git checkout -b feature/new-endpoint

# Make changes, then format and lint
ruff format .
ruff check .

# Run tests
pytest

# Live test (if applicable)
MCP_ALLOW_WRITE=false python test_mcp_servers.py

# Commit and push
git add .
git commit -m "Add support for dxNewFeature"
git push origin feature/new-endpoint
```

## License

MIT License - see LICENSE file for details.

## Related Links

- [Model Context Protocol](https://modelcontextprotocol.io) - MCP specification and documentation
- [Blocknet Documentation](https://docs.blocknet.org) 
- [Blocknet API Reference](https://api.blocknet.org)
- [FastMCP](https://github.com/modelcontextprotocol/python-sdk) - Python MCP SDK
- [Blocknet GitHub](https://github.com/BlocknetDX) - Blocknet source code

## Support

- **Issues**: Report bugs and request features via GitHub Issues
- **Discussions**: Join the conversation via GitHub Discussions
- **Blocknet Community**: [Discord](https://discord.gg/F3h327UQ) 

---

**Note**: This is an unofficial MCP integration for Blocknet. It is not affiliated with or endorsed by the Blocknet
team. Use at your own risk. Always test in a safe environment before using with mainnet funds.
