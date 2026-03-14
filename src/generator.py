"""
MCP Server Code Generator

Generates complete MCP server code from API documentation using Jinja2 templates.
"""

import shlex
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar

import jinja2
import structlog
import yaml

from src.parser import ApiSpec, parse_api_docs

PREFIX_CONFIG = {
    "dx": {
        "name": "xbridge_mcp",
        "display_name": "XBridge",
        "client_class_name": "AsyncXBridgeClient",
        "doc_path": "blocknet-api-docs/source/includes/_xbridge.md",
        "env_prefix": "XBRIDGE_MCP",
    },
    "xr": {
        "name": "xrouter_mcp",
        "display_name": "XRouter",
        "client_class_name": "AsyncXRouterClient",
        "doc_path": "blocknet-api-docs/source/includes/_xrouter.md",
        "env_prefix": "XROUTER_MCP",
    },
}

# Fallback hardcoded list (used if YAML config is missing)
_DEFAULT_WRITE_PROTECTED = {
    "dx": [
        "dxMakeOrder",
        "dxMakePartialOrder",
        "dxTakeOrder",
        "dxCancelOrder",
        "dxSplitAddress",
        "dxSplitInputs",
        "dxLoadXBridgeConf",
    ],
    "xr": [],
}


def _load_write_protected_config() -> dict[str, list[str]]:
    """Load write-protected RPC methods from YAML config.
    Falls back to hardcoded defaults if YAML not found or invalid.
    """
    config_path = Path(__file__).parent / "write_protected.yaml"
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict):
                    dx_val = data.get("dx")
                    xr_val = data.get("xr")
                    # Validate that both values are lists
                    if isinstance(dx_val, list) and isinstance(xr_val, list):
                        return {"dx": dx_val, "xr": xr_val}
                    else:
                        structlog.get_logger().warning("write_protected.yaml values for 'dx' and 'xr' must be lists, using defaults")
                else:
                    structlog.get_logger().warning("Invalid write_protected.yaml format, using defaults")
        except Exception as e:
            structlog.get_logger().warning("Failed to load write_protected.yaml", error=str(e))
    # Fallback
    return _DEFAULT_WRITE_PROTECTED


WRITE_PROTECTED = _load_write_protected_config()


class Generator:
    """Generates MCP server code from API specifications"""

    # Test generation constants (extracted from _generate_tests)
    PLACEHOLDERS: ClassVar[dict[str, str]] = {
        "maker": "MAKER",
        "token": "MAKER",
        "asset": "MAKER",
        "taker": "TAKER",
        "token2": "TAKER",
        "blockchain": "BLOCKCHAIN",
        "chain": "BLOCKCHAIN",
        "uuid": "LAST_UUID",
        "id": "FIRST_ORDER_ID",
        "order_id": "FIRST_ORDER_ID",
        "block_number": "HEIGHT",
        "height": "HEIGHT",
        "block_hash": "HASH",
        "hash": "HASH",
        "start_time": "EPOCH_1D_AGO",
        "end_time": "EPOCH_NOW",
        "timestamp": "EPOCH_NOW",
        "tx_hex": "TX_HEX",
        "tx_id": "TX_ID",
        "tx_ids": "TX_IDS",
    }

    DEFAULTS: ClassVar[dict[str, Any]] = {
        "detail": 1,
        "max_orders": 100,
        "node_count": 2,
        "combines": False,
        "dryrun": True,
        "include_used": False,
        "with_inverse": False,
        "limit": 10,
        "blocks": 1440,
        "errors": False,
        "ageMillis": 86400000,
        "repost": False,
        "submit": False,
        "show_rawtx": False,
        "order_ids": False,
        "granularity": 60,
    }

    PLACEHOLDER_TO_DEPENDENCY: ClassVar[dict[str, str]] = {
        "FIRST_ORDER_ID": "order_ids",
        "HEIGHT": "block_height",
        "HASH": "block_hash",
        "TX_HEX": "tx_hex",
        "LAST_UUID": "last_uuid",
    }

    DEPENDENCY_TO_CONDITION: ClassVar[dict[str, str]] = {
        "order_ids": "not test_context.order_ids",
        "block_height": "not test_context.block_height",
        "block_hash": "not test_context.block_hash",
        "tx_hex": "not test_context.tx_hex",
        "last_uuid": "not test_context.last_uuid",
    }

    PRIORITY_DEPENDENCIES: ClassVar[list[str]] = ["order_ids", "block_height", "block_hash", "tx_hex", "last_uuid"]

    def __init__(
        self,
        doc_path: str,
        prefix: str,
        output_dir: str,
    ):
        self.doc_path = Path(doc_path)
        self.prefix = prefix.lower()
        self.output_dir = Path(output_dir).resolve()
        self.spec: ApiSpec | None = None

        self._config = PREFIX_CONFIG.get(self.prefix, {})

    def load_spec(self) -> ApiSpec:
        """Load and parse API documentation"""
        self.spec = parse_api_docs(str(self.doc_path), self.prefix)
        self.spec.name = self._config.get("name", self.prefix)
        self._validate_write_protected_config()
        return self.spec

    def _validate_write_protected_config(self) -> None:
        """Warn about write-protected RPC methods that don't exist in the API spec."""
        if not self.spec:
            return

        protected_methods = WRITE_PROTECTED.get(self.prefix, [])
        known_methods = set(self.spec.endpoints.keys())
        unknown = [m for m in protected_methods if m not in known_methods]

        if unknown:
            logger = structlog.get_logger()
            logger.warning(
                "write_protected.yaml contains unknown RPC methods",
                prefix=self.prefix,
                unknown_methods=unknown,
                known_methods_count=len(known_methods),
            )

    def generate(self) -> None:
        """Generate MCP server code"""
        if not self.spec:
            self.load_spec()

        output_dir = self.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        (output_dir / "rpc").mkdir(exist_ok=True)
        (output_dir / "generated").mkdir(exist_ok=True)
        (output_dir / "rpc" / "__init__.py").touch(exist_ok=True)

        self._write_file(output_dir / "__init__.py", '"""Generated MCP server package"""\n')

        env = self._get_template_env()
        server_config = self._build_server_config()

        self._generate_main(env, server_config, output_dir)
        self._generate_config(env, server_config, output_dir)
        self._generate_rpc_client(env, server_config, output_dir)
        self._generate_exceptions(output_dir)
        self._generate_security(env, server_config, output_dir)
        self._generate_logging(env, server_config, output_dir)
        self._generate_tools(env, output_dir)
        self._generate_generated_init(output_dir)
        self._generate_specs(output_dir)

        generated_tests_dir = Path("generated") / "tests"
        self._generate_tests(env, server_config, generated_tests_dir)

        print(f"Generated MCP server in {output_dir}")

    def _get_template_env(self) -> jinja2.Environment:
        """Get Jinja2 template environment"""
        template_dir = Path(__file__).parent / "templates"
        loader = jinja2.FileSystemLoader(str(template_dir))
        env = jinja2.Environment(loader=loader, autoescape=False)
        return env

    def _build_server_config(self) -> dict[str, Any]:
        """Build server configuration"""
        pkg_name = self._config.get("name", self.prefix)
        return {
            "display_name": self._config.get("display_name", self.prefix.upper()),
            "server_name": f"{self._config.get('display_name', self.prefix.upper())} MCP Server",
            "env_prefix": pkg_name.upper(),
            "package_name": pkg_name,
            "client_class_name": f"Async{self._config.get('display_name', self.prefix.upper())}Client",
            "tool_prefix": self.prefix,
            "rpc_prefix": self.prefix,
        }

    def _generate_main(self, env: jinja2.Environment, config: dict, output_dir: Path) -> None:
        template = env.get_template("server/main.py.jinja")
        content = template.render(
            server=config,
            rpc={"client_class_name": config["client_class_name"], "prefix": config["rpc_prefix"]},
        )
        self._write_file(output_dir / "main.py", content)

    def _generate_config(self, env: jinja2.Environment, config: dict, output_dir: Path) -> None:
        template = env.get_template("server/config.py.jinja")
        content = template.render(server=config, rpc={"client_class_name": config["client_class_name"]})
        self._write_file(output_dir / "config.py", content)

    def _generate_rpc_client(self, env: jinja2.Environment, config: dict, output_dir: Path) -> None:
        template = env.get_template("server/rpc_client.py.jinja")
        content = template.render(server=config, rpc={"client_class_name": config["client_class_name"]})
        self._write_file(output_dir / "rpc" / "client.py", content)

    def _generate_exceptions(self, output_dir: Path) -> None:
        client_class = self._config.get("client_class_name", f"Async{self.prefix.upper()}Client")
        content = EXCEPTIONS_TEMPLATE.format(client_name=client_class)
        self._write_file(output_dir / "rpc" / "exceptions.py", content)

    def _generate_security(self, env: jinja2.Environment, config: dict, output_dir: Path) -> None:
        template = env.get_template("server/security.py.jinja")
        content = template.render(server=config)
        self._write_file(output_dir / "security.py", content)

    def _generate_logging(self, env: jinja2.Environment, config: dict, output_dir: Path) -> None:
        template = env.get_template("server/logging_config.py.jinja")
        content = template.render(server=config)
        self._write_file(output_dir / "logging_config.py", content)

    def _generate_tools(self, env: jinja2.Environment, output_dir: Path) -> None:
        template = env.get_template("tools/tools.py.jinja")
        write_protected = set(WRITE_PROTECTED.get(self.prefix, []))
        config = self._build_server_config()
        content = template.render(
            server=config,
            generated_timestamp=datetime.now().isoformat(),
            tool_prefix=self.prefix,
            endpoints=self.spec.endpoints,
            write_protected_tools=write_protected,
            decorator_for=self._make_decorator_for(),
            format_params=self._make_format_params(),
        )
        self._write_file(output_dir / "generated" / "tools.py", content)

    def _generate_generated_init(self, output_dir: Path) -> None:
        template = self._get_template_env().get_template("tools/__init__.py.jinja")
        config = self._build_server_config()
        content = template.render(server=config)
        self._write_file(output_dir / "generated" / "__init__.py", content)

    def _generate_specs(self, output_dir: Path) -> None:
        lines = [
            '"""Generated API Specifications',
            "",
            "DO NOT EDIT MANUALLY - This file is generated from API documentation",
            '"""',
            "",
            "from dataclasses import dataclass",
            "",
            "@dataclass",
            "class EndpointSpec:",
            "    rpc_method: str",
            "    tool_name: str",
            "    description: str",
            "    params: list[dict]",
            "",
            "ERROR_CODES = {",
        ]

        for code, meaning in self.spec.error_codes.items():
            lines.append(f'    {code}: "{meaning}",')

        lines.extend(["}", ""])
        lines.append("ENDPOINTS = {")

        for rpc_method, endpoint in self.spec.endpoints.items():
            lines.append(f'    "{rpc_method}": EndpointSpec(')
            lines.append(f'        rpc_method="{endpoint.rpc_method}",')
            lines.append(f'        tool_name="{endpoint.tool_name}",')
            desc = endpoint.description.replace('"', '\\"')
            lines.append(f'        description="{desc}",')
            param_dicts = [{p.name: p.python_type} for p in endpoint.params]
            lines.append(f"        params={param_dicts},")
            lines.append("    ),")

        lines.append("}")
        self._write_file(output_dir / "generated" / "specs.py", "\n".join(lines))

    def _parse_sample_params(self, endpoint) -> list:
        """Parse sample_request CLI string to extract param values with proper types"""
        sample = endpoint.sample_request
        if not sample:
            return []

        parts = shlex.split(sample)
        if len(parts) <= 2:
            return []

        params = parts[2:]

        converted = []
        for value in params:
            # Convert to appropriate Python type (return actual Python objects)
            if value.lower() == "true":
                converted.append(True)
            elif value.lower() == "false":
                converted.append(False)
            elif value.isdigit():
                converted.append(int(value))
            elif value.replace(".", "", 1).replace("-", "", 1).isdigit():
                converted.append(float(value))
            else:
                # It's a string
                converted.append(value)

        return converted

    def _generate_tests(self, env: jinja2.Environment, server_config: dict, tests_dir: Path) -> None:
        """Generate integration tests for the MCP server"""
        tests_dir.mkdir(parents=True, exist_ok=True)

        if not self.spec:
            self.load_spec()

        prefix_name = self._config.get("name", self.prefix)
        write_protected = set(WRITE_PROTECTED.get(self.prefix, []))

        endpoints_config = self._collect_endpoints_test_config(write_protected)
        self._render_test_templates(env, server_config, tests_dir, prefix_name, endpoints_config)

    def _collect_endpoints_test_config(self, write_protected: set[str]) -> list[dict]:
        """Collect test configurations for all non-write-protected endpoints"""
        configs = []
        for ep in self.spec.endpoints.values():
            config = self._create_endpoint_test_config(ep, write_protected)
            if config:
                configs.append(config)
        return configs

    def _create_endpoint_test_config(self, endpoint, write_protected: set[str]) -> dict | None:
        """Create test configuration for a single endpoint, or None if should be skipped"""
        if endpoint.tool_name in write_protected:
            return None

        param_template, invalid_template, dependencies = self._build_parameter_templates(endpoint)
        if param_template is None:
            return None

        skip_condition = self._determine_skip_condition(dependencies)
        expected_type = endpoint.response_type if endpoint.response_type in ("dict", "list") else "dict"
        param_names = [p.name for p in endpoint.params]
        param_types = {p.name: p.python_type for p in endpoint.params}

        return {
            "tool_name": endpoint.tool_name,
            "rpc_method": endpoint.rpc_method,
            "description": endpoint.description or "",
            "param_names": param_names,
            "param_template": str(param_template),
            "invalid_param_template": str(invalid_template),
            "expected_type": expected_type,
            "skip_condition": skip_condition,
            "error_codes": list(endpoint.error_codes) if endpoint.error_codes else [],
            "param_types": param_types,
            "has_params": len(param_names) > 0,
            "skip": False,
        }

    def _build_parameter_templates(self, endpoint) -> tuple[dict | None, dict | None, set[str]]:
        """Build valid parameter template and invalid template for an endpoint"""
        sample_vals = self._parse_sample_params(endpoint)
        param_template = {}
        invalid_template = {}
        dependencies = set()

        for i, param in enumerate(endpoint.params):
            value, dep, ok = self._resolve_param_value(param, i, sample_vals)
            if not ok:
                return None, None, set()
            param_template[param.name] = value
            if dep:
                dependencies.add(dep)
            invalid_template[param.name] = self._get_invalid_value(param.python_type)

        return param_template, invalid_template, dependencies

    def _resolve_param_value(self, param, index: int, sample_vals: list) -> tuple[Any, str | None, bool]:
        """Resolve a single parameter's value, dependency, and success flag"""
        name = param.name
        lname = name.lower()

        # Check placeholder patterns
        for pattern, placeholder in self.PLACEHOLDERS.items():
            if pattern in lname:
                if pattern in ("id", "order_id") and lname == "order_ids":
                    continue
                dep = self.PLACEHOLDER_TO_DEPENDENCY.get(placeholder)
                return placeholder, dep, True

        # Use sample value if available
        if index < len(sample_vals):
            return sample_vals[index], None, True

        # Fall back to default
        default = self.DEFAULTS.get(lname)
        if default is not None:
            return default, None, True

        return None, None, False

    def _get_invalid_value(self, python_type: str) -> Any:
        """Get an invalid value for a given Python type (for error testing)"""
        if python_type == "str":
            return 0
        elif python_type == "int":
            return "invalid"
        elif python_type == "bool":
            return 0
        elif python_type == "float":
            return "invalid"
        else:
            return None

    def _determine_skip_condition(self, dependencies: set[str]) -> str | None:
        """Determine skip condition based on required test context dependencies"""
        for dep in self.PRIORITY_DEPENDENCIES:
            if dep in dependencies:
                return self.DEPENDENCY_TO_CONDITION[dep]
        return None

    def _render_test_templates(self, env, server_config, tests_dir: Path, prefix_name: str, endpoints_config: list[dict]) -> None:
        """Render conftest.py and integration test file"""
        conftest_template = env.get_template("tests/conftest.py.jinja")
        conftest_content = conftest_template.render(
            server=server_config,
            prefix=self.prefix,
            prefix_name=prefix_name,
        )
        self._write_file(tests_dir / "conftest.py", conftest_content)

        integration_template = env.get_template("tests/integration.py.jinja")
        documented_codes = set(self.spec.error_codes.keys()) if self.spec else set()
        supplemental_codes = {-1, -3, 1035}
        all_error_codes = documented_codes | supplemental_codes

        integration_content = integration_template.render(
            server=server_config,
            prefix=self.prefix,
            prefix_name=prefix_name,
            endpoints=endpoints_config,
            global_error_codes=sorted(all_error_codes),
            generated_timestamp=datetime.now().isoformat(),
        )
        test_file_name = f"test_{prefix_name}_integration.py"
        self._write_file(tests_dir / test_file_name, integration_content)

    def _write_file(self, path: Path, content: str) -> None:
        """Write file to disk"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(content)

        try:
            rel_path = path.relative_to(Path.cwd())
            print(f"  Generated: {rel_path}")
        except ValueError:
            print(f"  Generated: {path}")

    def _make_decorator_for(self):
        def decorator_for(tool_name, write_protected_tools):
            is_protected = tool_name in write_protected_tools
            if is_protected:
                return "@mcp_tool()\n@write_protected"
            return "@mcp_tool()"

        return decorator_for

    def _format_default_literal(self, param) -> str:
        """Convert a default value string to a Python literal for code generation."""
        if not param.default_value:
            return "None"

        value = param.default_value
        py_type = param.python_type

        # Boolean: convert to True/False
        if py_type == "bool":
            lower = value.lower()
            if lower in ("true", "1"):
                return "True"
            elif lower in ("false", "0"):
                return "False"
            # Fallback: keep original (shouldn't happen)
            return value

        # Numeric types: keep as string representation (int, float)
        if py_type in ("int", "int64", "float", "float64"):
            return value

        # String types: quote as string literal
        if py_type.startswith("str"):
            # Use repr for proper escaping and quotes
            return repr(value)

        # Fallback: treat as string literal
        return repr(value)

    def _make_format_params(self):
        def format_params(params):
            if not params:
                return ""

            lines = []
            for i, param in enumerate(params):
                py_type = param.python_type
                if param.required:
                    type_str = py_type
                    default = ""
                else:
                    if param.default_value:
                        type_str = py_type
                        default = f" = {self._format_default_literal(param)}"
                    else:
                        # Optional without documented default -> can be None
                        type_str = f"{py_type} | None"
                        default = " = None"
                comma = "," if i < len(params) - 1 else ""
                lines.append(f"    {param.name}: {type_str}{default}{comma}")

            return "\n".join(lines)

        return format_params


EXCEPTIONS_TEMPLATE = '''"""RPC Exceptions"""


class {client_name}RPCError(Exception):
    """Base RPC error"""
    def __init__(self, message: str, code: int = None, method: str = None):
        self.message = message
        self.code = code
        self.method = method
        super().__init__(self.message)


class {client_name}ConnectionError({client_name}RPCError):
    """Connection error"""
    pass


class {client_name}AuthError({client_name}RPCError):
    """Authentication error"""
    pass


class {client_name}TimeoutError({client_name}RPCError):
    """Timeout error"""
    pass


def parse_rpc_error(error_info: dict, method: str) -> {client_name}RPCError:
    """Parse RPC error response"""
    if isinstance(error_info, dict):
        message = error_info.get("message", str(error_info))
        code = error_info.get("code", -1)
        name = error_info.get("name", method)
        return {client_name}RPCError(message, code, name)
    return {client_name}RPCError(str(error_info), method=method)
'''


def generate(doc_path: str, prefix: str, output_dir: str) -> None:
    """Convenience function to generate MCP code"""
    gen = Generator(doc_path, prefix, output_dir)
    gen.generate()
