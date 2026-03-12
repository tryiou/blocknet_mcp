"""Unit tests for the Generator module"""

from pathlib import Path
from unittest.mock import MagicMock

from src import generator
from src.generator import PREFIX_CONFIG, WRITE_PROTECTED, Generator
from src.parser import ApiSpec, ParamSpec, parse_api_docs


class TestGeneratorInit:
    """Tests for Generator initialization"""

    def test_generator_init_with_xbridge(self):
        gen = Generator("blocknet-api-docs/source/includes/_xbridge.md", "dx", "/tmp/output")
        assert gen.doc_path == Path("blocknet-api-docs/source/includes/_xbridge.md")
        assert gen.prefix == "dx"
        assert gen.output_dir == Path("/tmp/output")

    def test_generator_init_with_xrouter(self):
        gen = Generator("blocknet-api-docs/source/includes/_xrouter.md", "xr", "/tmp/output")
        assert gen.doc_path == Path("blocknet-api-docs/source/includes/_xrouter.md")
        assert gen.prefix == "xr"
        assert gen.output_dir == Path("/tmp/output")

    def test_prefix_config_loaded_dx(self):
        gen = Generator("path/to/docs.md", "dx", "/tmp/output")
        assert gen._config["name"] == "xbridge_mcp"
        assert gen._config["display_name"] == "XBridge"
        assert gen._config["client_class_name"] == "AsyncXBridgeClient"

    def test_prefix_config_loaded_xr(self):
        gen = Generator("path/to/docs.md", "xr", "/tmp/output")
        assert gen._config["name"] == "xrouter_mcp"
        assert gen._config["display_name"] == "XRouter"
        assert gen._config["client_class_name"] == "AsyncXRouterClient"

    def test_prefix_normalized_to_lowercase(self):
        gen = Generator("path/to/docs.md", "DX", "/tmp/output")
        assert gen.prefix == "dx"


class TestBuildServerConfig:
    """Tests for _build_server_config method"""

    def test_build_server_config_dx(self):
        gen = Generator("path/to/docs.md", "dx", "/tmp/output")
        config = gen._build_server_config()

        assert config["display_name"] == "XBridge"
        assert config["server_name"] == "XBridge MCP Server"
        assert config["env_prefix"] == "XBRIDGE_MCP"
        assert config["package_name"] == "xbridge_mcp"
        assert config["client_class_name"] == "AsyncXBridgeClient"
        assert config["tool_prefix"] == "dx"
        assert config["rpc_prefix"] == "dx"
        assert config["host"] == "localhost"
        assert config["port"] == 41414

    def test_build_server_config_xr(self):
        gen = Generator("path/to/docs.md", "xr", "/tmp/output")
        config = gen._build_server_config()

        assert config["display_name"] == "XRouter"
        assert config["server_name"] == "XRouter MCP Server"
        assert config["env_prefix"] == "XROUTER_MCP"
        assert config["package_name"] == "xrouter_mcp"
        assert config["client_class_name"] == "AsyncXRouterClient"
        assert config["tool_prefix"] == "xr"
        assert config["rpc_prefix"] == "xr"


class TestParseSampleParams:
    """Tests for _parse_sample_params method - type conversion fix"""

    def test_parse_true_boolean(self):
        gen = Generator("path/to/docs.md", "dx", "/tmp/output")
        endpoint = type("obj", (object,), {"sample_request": "xrGetTransaction TICKER true"})()
        result = gen._parse_sample_params(endpoint)
        assert result == [True]

    def test_parse_false_boolean(self):
        gen = Generator("path/to/docs.md", "dx", "/tmp/output")
        endpoint = type("obj", (object,), {"sample_request": "xrGetTransaction TICKER false"})()
        result = gen._parse_sample_params(endpoint)
        assert result == [False]

    def test_parse_integer(self):
        gen = Generator("path/to/docs.md", "dx", "/tmp/output")
        endpoint = type("obj", (object,), {"sample_request": "dxGetOrderBook TICKER 1 2"})()
        result = gen._parse_sample_params(endpoint)
        assert result == [1, 2]
        assert isinstance(result[0], int)
        assert isinstance(result[1], int)

    def test_parse_float(self):
        gen = Generator("path/to/docs.md", "dx", "/tmp/output")
        endpoint = type("obj", (object,), {"sample_request": "blocknet-cli dxGetTradingData 1.5"})()
        result = gen._parse_sample_params(endpoint)
        assert result == [1.5]
        assert isinstance(result[0], float)

    def test_parse_negative_number(self):
        gen = Generator("path/to/docs.md", "dx", "/tmp/output")
        endpoint = type("obj", (object,), {"sample_request": "blocknet-cli dxGetTradingData -10"})()
        result = gen._parse_sample_params(endpoint)
        assert result == [-10]
        assert isinstance(result[0], float)  # Generator converts all numbers to float

    def test_parse_string_ticker(self):
        gen = Generator("path/to/docs.md", "dx", "/tmp/output")
        endpoint = type("obj", (object,), {"sample_request": "blocknet-cli dxGetLocalTokens TICKER"})()
        result = gen._parse_sample_params(endpoint)
        assert result == ["TICKER"]

    def test_parse_single_param(self):
        gen = Generator("path/to/docs.md", "dx", "/tmp/output")
        endpoint = type("obj", (object,), {"sample_request": "blocknet-cli dxGetTrades TICKER"})()
        result = gen._parse_sample_params(endpoint)
        assert result == ["TICKER"]

    def test_parse_multiple_params_mixed_types(self):
        gen = Generator("path/to/docs.md", "dx", "/tmp/output")
        endpoint = type("obj", (object,), {"sample_request": "blocknet-cli dxGetOrderBook TICKER1 TICKER2 1440 true 10"})()
        result = gen._parse_sample_params(endpoint)
        assert result == ["TICKER1", "TICKER2", 1440, True, 10]
        assert isinstance(result[2], int)
        assert isinstance(result[3], bool)
        assert isinstance(result[4], int)

    def test_parse_real_dxmakeorder_sample(self):
        """Test with actual dxMakeOrder sample from docs - backward compatibility check"""
        gen = Generator("path/to/docs.md", "dx", "/tmp/output")
        sample = "blocknet-cli dxMakeOrder SYS 0.100 SVTbaYZ8oApVn3uNyimst3GKyvvfzXQgdK LTC 0.01 LVvFhzRoMRGTtGihHp7jVew3YoZRX8y35Z exact"
        endpoint = type("obj", (object,), {"sample_request": sample})()
        result = gen._parse_sample_params(endpoint)
        # Numbers are converted to appropriate types (float for decimal, int for whole)
        assert result == ["SYS", 0.1, "SVTbaYZ8oApVn3uNyimst3GKyvvfzXQgdK", "LTC", 0.01, "LVvFhzRoMRGTtGihHp7jVew3YoZRX8y35Z", "exact"]

    def test_parse_real_dxflushcancelledorders_sample(self):
        """Test with actual dxFlushCancelledOrders sample"""
        gen = Generator("path/to/docs.md", "dx", "/tmp/output")
        sample = "blocknet-cli dxFlushCancelledOrders 600000"
        endpoint = type("obj", (object,), {"sample_request": sample})()
        result = gen._parse_sample_params(endpoint)
        assert result == [600000]
        assert isinstance(result[0], int)

    def test_parse_real_xrsendtransaction_sample(self):
        """Test with actual xrSendTransaction sample"""
        gen = Generator("path/to/docs.md", "xr", "/tmp/xr_output")
        sample = "blocknet-cli xrSendTransaction SYS 0200000001ce2faed018f4776b41245f78695fdabcc68567b64d13851a7f8277693a23f3e0000000006b483045022100d6e0f7c193e0ae5168e0e8c87a29837f4b8be5c5cdcfa2826a8ddc7cf6cbf43802207ddaa377bc042f9df63eb6f755d23170b9109cb05c18c7ce2fe9993e65434c8b01210323f7e071df863cf20ce13613c68579cdedb6d7c6cf3912f26dac53ec4309c777ffffffff0120a10700000000001976a914eff8cb97723237fe3059774d2a66d02f936e1f1188ac00000000"  # noqa: E501
        endpoint = type("obj", (object,), {"sample_request": sample})()
        result = gen._parse_sample_params(endpoint)
        assert result == [
            "SYS",
            "0200000001ce2faed018f4776b41245f78695fdabcc68567b64d13851a7f8277693a23f3e0000000006b483045022100d6e0f7c193e0ae5168e0e8c87a29837f4b8be5c5cdcfa2826a8ddc7cf6cbf43802207ddaa377bc042f9df63eb6f755d23170b9109cb05c18c7ce2fe9993e65434c8b01210323f7e071df863cf20ce13613c68579cdedb6d7c6cf3912f26dac53ec4309c777ffffffff0120a10700000000001976a914eff8cb97723237fe3059774d2a66d02f936e1f1188ac00000000",
        ]

    def test_parse_with_quoted_string(self):
        """Test shlex.split handles quoted strings correctly (future-proof)"""
        gen = Generator("path/to/docs.md", "dx", "/tmp/output")
        # Suppose a future doc has quoted argument with spaces
        sample = 'blocknet-cli dxCustom "some value with spaces" 123'
        endpoint = type("obj", (object,), {"sample_request": sample})()
        result = gen._parse_sample_params(endpoint)
        assert result == ["some value with spaces", 123]


class TestPrefixConfig:
    """Tests for PREFIX_CONFIG constant"""

    def test_prefix_config_has_dx(self):
        assert "dx" in PREFIX_CONFIG
        assert PREFIX_CONFIG["dx"]["name"] == "xbridge_mcp"

    def test_prefix_config_has_xr(self):
        assert "xr" in PREFIX_CONFIG
        assert PREFIX_CONFIG["xr"]["name"] == "xrouter_mcp"

    def test_prefix_config_all_have_required_fields(self):
        for prefix, config in PREFIX_CONFIG.items():
            assert "name" in config
            assert "display_name" in config
            assert "client_class_name" in config
            assert "doc_path" in config


class TestWriteProtected:
    """Tests for write-protected endpoint filtering"""

    def test_write_protected_has_required_keys(self):
        """Verify YAML loads with correct structure - both dx and xr keys exist"""
        assert "dx" in WRITE_PROTECTED
        assert "xr" in WRITE_PROTECTED

    def test_write_protected_values_are_lists(self):
        """Verify values are lists regardless of content - handles empty or populated"""
        assert isinstance(WRITE_PROTECTED["dx"], list)
        assert isinstance(WRITE_PROTECTED["xr"], list)

    def test_write_protected_items_are_strings(self):
        """Verify all items in the lists are strings (type validation)."""
        for prefix in ["dx", "xr"]:
            for method in WRITE_PROTECTED[prefix]:
                assert isinstance(method, str), f"{prefix}: {method!r} is not a string"

    def test_write_protected_methods_follow_naming_convention(self):
        """Verify methods follow expected naming pattern (prefix + CamelCase)."""
        for prefix in ["dx", "xr"]:
            for method in WRITE_PROTECTED[prefix]:
                assert method.startswith(prefix), f"{method} should start with '{prefix}'"
                assert method[len(prefix)].isupper(), f"{method} should be CamelCase after prefix"

    def test_validation_warns_on_unknown_methods(self, monkeypatch):
        """Test that unknown RPC methods in YAML trigger a warning during generation."""

        # Temporarily modify WRITE_PROTECTED to include a fake method
        original = generator.WRITE_PROTECTED.copy()
        generator.WRITE_PROTECTED = {
            "dx": original["dx"] + ["dxFakeMethod123"],
            "xr": original["xr"],
        }
        try:
            # Mock the logger's warning method to capture calls
            mock_logger = MagicMock()
            monkeypatch.setattr(generator.structlog, "get_logger", lambda: mock_logger)
            gen = Generator(doc_path="blocknet-api-docs/source/includes/_xbridge.md", prefix="dx", output_dir="/tmp/output")
            gen.load_spec()
            # Check that warning was called
            assert mock_logger.warning.called, "logger.warning was not called"
            args, kwargs = mock_logger.warning.call_args
            message = args[0] if args else kwargs.get("event", "")
            assert "write_protected.yaml contains unknown RPC methods" in message
            # Also check that the fake method appears somewhere in the call args
            if "dxFakeMethod123" not in message:
                all_str = str(mock_logger.warning.call_args)
                assert "dxFakeMethod123" in all_str
        finally:
            generator.WRITE_PROTECTED = original


class TestGeneratorLoadSpec:
    """Tests for load_spec method"""

    def test_load_spec_returns_apispec(self):
        gen = Generator("blocknet-api-docs/source/includes/_xbridge.md", "dx", "/tmp/output")
        spec = gen.load_spec()

        assert isinstance(spec, ApiSpec)
        assert len(spec.endpoints) > 0
        assert spec.name == "xbridge_mcp"

    def test_load_spec_xrouter(self):
        gen = Generator("blocknet-api-docs/source/includes/_xrouter.md", "xr", "/tmp/output")
        spec = gen.load_spec()

        assert isinstance(spec, ApiSpec)
        assert len(spec.endpoints) > 0
        assert spec.name == "xrouter_mcp"

    def test_loaded_spec_stores_in_instance(self):
        gen = Generator("blocknet-api-docs/source/includes/_xbridge.md", "dx", "/tmp/output")
        spec = gen.load_spec()
        assert gen.spec is spec


class TestGeneratorHelpers:
    """Tests for helper methods"""

    def test_to_tool_name_via_spec(self):
        spec = parse_api_docs("blocknet-api-docs/source/includes/_xbridge.md", "dx")
        endpoint = spec.endpoints.get("dxGetLocalTokens")
        assert endpoint is not None
        assert endpoint.tool_name == "dxGetLocalTokens"

    def test_endpoint_params_have_python_types(self):
        spec = parse_api_docs("blocknet-api-docs/source/includes/_xbridge.md", "dx")
        endpoint = spec.endpoints.get("dxMakeOrder")
        assert endpoint is not None

        param_types = {p.name: p.python_type for p in endpoint.params}
        assert "maker" in param_types
        assert "taker" in param_types
        assert param_types["maker"] == "str"
        assert param_types["taker"] == "str"

    def test_error_codes_parsed_xr(self):
        spec = parse_api_docs("blocknet-api-docs/source/includes/_xrouter.md", "xr")
        # XRouter doc has no global error section, should load from _errors.md
        assert len(spec.error_codes) > 0, "Should have error codes from global _errors.md"
        # Spot-check some known codes
        assert 1004 in spec.error_codes  # Bad request
        assert 1025 in spec.error_codes  # Invalid parameters


class TestFormatDefaultLiteral:
    """Tests for _format_default_literal helper"""

    def _make_param(self, name: str, param_type: str, required: bool = False, default_value: str | None = None):
        """Helper to create a ParamSpec-like object"""
        return ParamSpec(name=name, param_type=param_type, required=required, default_value=default_value)

    def test_boolean_true_default(self):
        gen = Generator("path/to/docs.md", "dx", "/tmp/output")
        param = self._make_param("repost", "bool", required=False, default_value="true")
        assert gen._format_default_literal(param) == "True"

    def test_boolean_false_default(self):
        gen = Generator("path/to/docs.md", "dx", "/tmp/output")
        param = self._make_param("combines", "bool", required=False, default_value="false")
        assert gen._format_default_literal(param) == "False"

    def test_integer_default(self):
        gen = Generator("path/to/docs.md", "xr", "/tmp/output")
        param = self._make_param("node_count", "int", required=False, default_value="1")
        assert gen._format_default_literal(param) == "1"

    def test_float_default(self):
        gen = Generator("path/to/docs.md", "dx", "/tmp/output")
        param = self._make_param("some_float", "float", required=False, default_value="3.14")
        assert gen._format_default_literal(param) == "3.14"

    def test_string_default(self):
        gen = Generator("path/to/docs.md", "dx", "/tmp/output")
        param = self._make_param("mode", "string", required=False, default_value="at_start")
        # Should return a quoted string literal
        result = gen._format_default_literal(param)
        assert result in ("'at_start'", '"at_start"'), f"Got {result}"

    def test_no_default_returns_none(self):
        gen = Generator("path/to/docs.md", "dx", "/tmp/output")
        param = self._make_param("dryrun", "string", required=False, default_value=None)
        assert gen._format_default_literal(param) == "None"


class TestFormatParams:
    """Tests for _make_format_params signature generation"""

    def test_required_params_only(self):
        gen = Generator("path/to/docs.md", "dx", "/tmp/output")
        params = [
            ParamSpec(name="maker", param_type="str", required=True),
            ParamSpec(name="taker", param_type="str", required=True),
        ]
        format_params = gen._make_format_params()
        result = format_params(params)
        assert "maker: str" in result
        assert "taker: str" in result
        assert "=" not in result  # no defaults

    def test_optional_with_default(self):
        gen = Generator("path/to/docs.md", "dx", "/tmp/output")
        params = [
            ParamSpec(name="maker", param_type="str", required=True),
            ParamSpec(name="dryrun", param_type="str", required=False, default_value=None),
            ParamSpec(name="node_count", param_type="int", required=False, default_value="1"),
        ]
        format_params = gen._make_format_params()
        result = format_params(params)
        # dryrun: optional without documented default -> = None
        assert "dryrun: str | None = None" in result
        # node_count: optional with documented default -> = 1 (no | None)
        assert "node_count: int = 1" in result

    def test_mixed_params_ordering(self):
        gen = Generator("path/to/docs.md", "dx", "/tmp/output")
        params = [
            ParamSpec(name="a", param_type="str", required=True),
            ParamSpec(name="b", param_type="int", required=False, default_value="2"),
            ParamSpec(name="c", param_type="bool", required=False),
        ]
        format_params = gen._make_format_params()
        result = format_params(params)
        lines = result.split("\n")
        # Check order matches input
        assert any("a: str" in line for line in lines)
        assert any("b: int = 2" in line for line in lines)
        assert any("c: bool | None = None" in line for line in lines)
