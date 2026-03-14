"""Unit tests for the MarkdownParser module"""

from src.parser import (
    ApiSpec,
    EndpointSpec,
    MarkdownParser,
    ParamSpec,
    parse_api_docs,
)
from tests.conftest import TEST_XBRIDGE_DOC, TEST_XROUTER_DOC


class TestParamSpec:
    """Tests for ParamSpec dataclass"""

    def test_python_type_string(self):
        param = ParamSpec(name="address", param_type="string")
        assert param.python_type == "str"

    def test_python_type_int(self):
        param = ParamSpec(name="count", param_type="int")
        assert param.python_type == "int"

    def test_python_type_bool(self):
        param = ParamSpec(name="enabled", param_type="bool")
        assert param.python_type == "bool"

    def test_python_type_array(self):
        param = ParamSpec(name="tokens", param_type="array")
        assert param.python_type == "list"

    def test_python_type_object(self):
        param = ParamSpec(name="data", param_type="object")
        assert param.python_type == "dict"

    def test_python_type_float(self):
        param = ParamSpec(name="amount", param_type="float")
        assert param.python_type == "float"

    def test_python_type_unknown(self):
        param = ParamSpec(name="unknown", param_type="unknown_type")
        assert param.python_type == "str"

    def test_python_default_required(self):
        param = ParamSpec(name="required_param", param_type="string", required=True)
        assert param.python_default is None

    def test_python_default_optional(self):
        param = ParamSpec(name="optional_param", param_type="string", required=False)
        assert param.python_default == "None"

    def test_python_default_with_value(self):
        param = ParamSpec(
            name="param",
            param_type="string",
            required=False,
            default_value='"default"',
        )
        assert param.python_default == '"default"'


class TestEndpointSpec:
    """Tests for EndpointSpec dataclass"""

    def test_required_params(self):
        params = [
            ParamSpec(name="req1", param_type="string", required=True),
            ParamSpec(name="opt1", param_type="string", required=False),
            ParamSpec(name="req2", param_type="int", required=True),
        ]
        endpoint = EndpointSpec(rpc_method="testMethod", tool_name="test_method", params=params)

        required = endpoint.required_params
        assert len(required) == 2
        assert required[0].name == "req1"
        assert required[1].name == "req2"

    def test_optional_params(self):
        params = [
            ParamSpec(name="req1", param_type="string", required=True),
            ParamSpec(name="opt1", param_type="string", required=False),
            ParamSpec(name="opt2", param_type="int", required=False),
        ]
        endpoint = EndpointSpec(rpc_method="testMethod", tool_name="test_method", params=params)

        optional = endpoint.optional_params
        assert len(optional) == 2
        assert optional[0].name == "opt1"
        assert optional[1].name == "opt2"


class TestMarkdownParser:
    """Tests for MarkdownParser class"""

    def test_parser_initialization(self):
        parser = MarkdownParser(str(TEST_XBRIDGE_DOC), "dx")
        assert parser.doc_path == TEST_XBRIDGE_DOC
        assert parser.rpc_prefix == "dx"

    def test_parser_load(self):
        parser = MarkdownParser(str(TEST_XBRIDGE_DOC), "dx")
        parser.load()
        assert len(parser.content) > 0
        assert "dxGetLocalTokens" in parser.content

    def test_parse_xbridge(self):
        parser = MarkdownParser(str(TEST_XBRIDGE_DOC), "dx")
        parser.load()
        spec = parser.parse()

        assert isinstance(spec, ApiSpec)
        assert len(spec.endpoints) > 0

    def test_parse_xrouter(self):
        parser = MarkdownParser(str(TEST_XROUTER_DOC), "xr")
        parser.load()
        spec = parser.parse()

        assert isinstance(spec, ApiSpec)
        assert len(spec.endpoints) > 0

    def test_extract_endpoint_sections(self):
        parser = MarkdownParser(str(TEST_XBRIDGE_DOC), "dx")
        parser.load()
        sections = parser._extract_endpoint_sections()

        assert len(sections) > 0
        assert any("dxGetLocalTokens" in s for s in sections)


class TestParseApiDocs:
    """Tests for parse_api_docs convenience function"""

    def test_parse_xbridge_docs(self):
        spec = parse_api_docs(str(TEST_XBRIDGE_DOC), "dx")

        assert isinstance(spec, ApiSpec)
        assert "dxGetLocalTokens" in spec.endpoints
        assert "dxGetNetworkTokens" in spec.endpoints
        assert "dxMakeOrder" in spec.endpoints

    def test_endpoint_has_tool_name(self):
        spec = parse_api_docs(str(TEST_XBRIDGE_DOC), "dx")

        endpoint = spec.endpoints["dxGetLocalTokens"]
        assert endpoint.tool_name == "dxGetLocalTokens"

    def test_endpoint_has_params(self):
        spec = parse_api_docs(str(TEST_XBRIDGE_DOC), "dx")

        endpoint = spec.endpoints["dxMakeOrder"]
        assert len(endpoint.params) > 0

    def test_endpoint_params_have_types(self):
        spec = parse_api_docs(str(TEST_XBRIDGE_DOC), "dx")

        endpoint = spec.endpoints["dxMakeOrder"]
        param_types = {p.name: p.python_type for p in endpoint.params}
        assert all(t in ["str", "int", "float", "bool", "list", "dict"] for t in param_types.values())

    def test_duplicate_headings_resolved(self):
        """Test that duplicate headings (dxSplitInputs) use the last (complete) section"""
        spec = parse_api_docs(str(TEST_XBRIDGE_DOC), "dx")
        # dxSplitInputs should have parameters (7 parameters)
        ep = spec.endpoints.get("dxSplitInputs")
        assert ep is not None
        assert len(ep.params) == 7, f"Expected 7 params, got {len(ep.params)}"
        # Verify it has the expected params: asset, split_amount, address, include_fees, show_rawtx, submit, utxos
        param_names = {p.name for p in ep.params}
        expected = {"asset", "split_amount", "address", "include_fees", "show_rawtx", "submit", "utxos"}
        assert param_names == expected, f"Param mismatch: got {param_names}, expected {expected}"

    def test_key_header_in_request_params(self):
        """Test that endpoints using 'Key | Type | Description' table are parsed"""
        spec = parse_api_docs(str(TEST_XBRIDGE_DOC), "dx")
        # dxGetOrderBook should have 4 params: detail, maker, taker, max_orders
        ep = spec.endpoints.get("dxGetOrderBook")
        assert ep is not None
        assert len(ep.params) == 4
        param_names = {p.name for p in ep.params}
        assert {"detail", "maker", "taker", "max_orders"}.issubset(param_names)

    def test_endpoints_with_no_params(self):
        """Test endpoints that explicitly have no parameters"""
        spec = parse_api_docs(str(TEST_XBRIDGE_DOC), "dx")
        # dxGetOrders has no parameters
        ep = spec.endpoints.get("dxGetOrders")
        assert ep is not None
        assert len(ep.params) == 0
        # Description should be clean, not contain table headers or HTML
        assert "This call is used to retrieve all orders" in ep.description
        assert "<aside" not in ep.description
        assert "Key | Type" not in ep.description

        # dxGetMyOrders
        ep2 = spec.endpoints.get("dxGetMyOrders")
        assert ep2 is not None
        assert len(ep2.params) == 0

        # dxGetTokenBalances
        ep3 = spec.endpoints.get("dxGetTokenBalances")
        assert ep3 is not None
        assert len(ep3.params) == 0

    def test_error_codes_parsed(self):
        """Test that global error codes are properly extracted from XBridge docs"""
        spec = parse_api_docs(str(TEST_XBRIDGE_DOC), "dx")
        # Should have many error codes
        assert len(spec.error_codes) > 0, "Error codes should not be empty"
        # Spot-check some known codes
        assert 1004 in spec.error_codes
        assert spec.error_codes[1004] == "Bad request"
        assert 1011 in spec.error_codes
        assert "Invalid maker symbol" in spec.error_codes[1011]
        assert 1025 in spec.error_codes
        # Error messages should not be truncated or mangled
        assert " " in spec.error_codes[1025]  # Should contain spaces (e.g., "Invalid parameters")

    def test_description_cleanliness(self):
        """Test that descriptions don't contain HTML, tables, or code blocks"""
        spec = parse_api_docs(str(TEST_XBRIDGE_DOC), "dx")
        for name, ep in spec.endpoints.items():
            if ep.description:
                assert "<aside" not in ep.description, f"{name} has aside tag"
                assert "Key | Type" not in ep.description, f"{name} has table header"
                assert "Parameter | Type" not in ep.description, f"{name} has Parameter table header"
                assert "```" not in ep.description, f"{name} has code fence"
                assert not ep.description.startswith("|"), f"{name} description starts with pipe"

    def test_dxgetlocaltokens_duplicate_handling(self):
        """Test that dxGetLocalTokens (which appears twice) uses the last occurrence"""
        spec = parse_api_docs(str(TEST_XBRIDGE_DOC), "dx")
        ep = spec.endpoints.get("dxGetLocalTokens")
        assert ep is not None
        # The second (last) occurrence is correct and has no parameters.
        # The first occurrence is mislabeled content (actually dxGetTradingData).
        # Our fix should keep the last occurrence which correctly has 0 params.
        assert len(ep.params) == 0, f"Expected 0 params, got {len(ep.params)}"


class TestDefaultValueParsing:
    """Tests for default value extraction from parameter descriptions"""

    def test_dxmakepartialorder_repost_default(self):
        """dxMakePartialOrder: repost parameter has default 'true'"""
        spec = parse_api_docs(str(TEST_XBRIDGE_DOC), "dx")
        ep = spec.endpoints.get("dxMakePartialOrder")
        assert ep is not None
        # Find the repost parameter
        repost = next((p for p in ep.params if p.name == "repost"), None)
        assert repost is not None, "repost parameter should exist"
        assert not repost.required, "repost should be optional"
        assert repost.default_value == "true", f"Expected default 'true', got {repost.default_value}"

    def test_dxmakepartialorder_dryrun_optional_no_default(self):
        """dxMakePartialOrder: dryrun is optional but no explicit default"""
        spec = parse_api_docs(str(TEST_XBRIDGE_DOC), "dx")
        ep = spec.endpoints.get("dxMakePartialOrder")
        dryrun = next((p for p in ep.params if p.name == "dryrun"), None)
        assert dryrun is not None, "dryrun parameter should exist"
        assert not dryrun.required, "dryrun should be optional"
        assert dryrun.default_value is None, f"dryrun should have no default, got {dryrun.default_value}"

    def test_xrupdatenetworkservices_node_count_default(self):
        """xrUpdateNetworkServices: node_count has default '1'"""
        spec = parse_api_docs(str(TEST_XROUTER_DOC), "xr")
        ep = spec.endpoints.get("xrUpdateNetworkServices")
        assert ep is not None
        # xrUpdateNetworkServices has optional node_count default 1
        node_count = next((p for p in ep.params if p.name == "node_count"), None)
        assert node_count is not None, "node_count parameter should exist"
        assert not node_count.required, "node_count should be optional"
        assert node_count.default_value == "1", f"Expected default '1', got {node_count.default_value}"

    def test_default_true_false_booleans(self):
        """Verify boolean defaults are captured correctly"""
        spec = parse_api_docs(str(TEST_XBRIDGE_DOC), "dx")
        # dxGetOrderFills has combines optional default true
        ep = spec.endpoints.get("dxGetOrderFills")
        assert ep is not None
        combines = next((p for p in ep.params if p.name == "combines"), None)
        assert combines is not None
        assert not combines.required
        assert combines.default_value == "true"

    def test_optional_without_default_dxmakeorder_dryrun(self):
        """dxMakeOrder: dryrun is optional but has no documented default"""
        spec = parse_api_docs(str(TEST_XBRIDGE_DOC), "dx")
        ep = spec.endpoints.get("dxMakeOrder")
        assert ep is not None
        dryrun = next((p for p in ep.params if p.name == "dryrun"), None)
        assert dryrun is not None, "dryrun parameter should exist"
        assert not dryrun.required
        assert dryrun.default_value is None, "dryrun should have no default value"


class TestResponseTypeInference:
    """Tests for scalar response type inference from sample responses"""

    def test_xrupdatenetworkservices_response_type_is_bool(self):
        xrouter = parse_api_docs("blocknet-api-docs/source/includes/_xrouter.md", "xr")
        ep = xrouter.endpoints.get("xrUpdateNetworkServices")
        assert ep is not None
        assert ep.response_type == "bool", f"Expected 'bool', got '{ep.response_type}'"

    def test_xrreloadconfigs_response_type_is_bool(self):
        xrouter = parse_api_docs("blocknet-api-docs/source/includes/_xrouter.md", "xr")
        ep = xrouter.endpoints.get("xrReloadConfigs")
        assert ep is not None
        assert ep.response_type == "bool", f"Expected 'bool', got '{ep.response_type}'"


class TestPreservedEndpoints:
    """Tests for preserving endpoints from HTML comments"""

    def test_multi_endpoint_comment_block(self, tmp_path):
        """Test extraction of multiple endpoints in the same comment block"""
        doc_content = """# XRouter API

## xrNormalEndpoint

> Sample Request

```shell
blocknet-cli xrNormalEndpoint
```

This is a normal endpoint.

## <!--
## xrService

> Sample Request

```shell
blocknet-cli xrService BTC
```

This is a preserved service.

## xrServiceConsensus

> Sample Request

```shell
blocknet-cli xrServiceConsensus 1 BTC
```

This is a preserved consensus service.
-->
"""
        doc_path = tmp_path / "test.md"
        doc_path.write_text(doc_content)

        parser = MarkdownParser(str(doc_path), "xr")
        with open(doc_path, encoding="utf-8") as f:
            parser.content = f.read()

        preserved = parser._extract_preserved_endpoints(["xrService", "xrServiceConsensus"])

        assert "xrService" in preserved
        assert "xrServiceConsensus" in preserved
        assert "This is a preserved service." in preserved["xrService"]
        assert "This is a preserved consensus service." in preserved["xrServiceConsensus"]

    def test_same_line_comment_start(self, tmp_path):
        """Test extraction when <!-- is on the same line as ## endpoint"""
        doc_content = """# XRouter API

## <!-- ## xrService

> Sample Request

```shell
blocknet-cli xrService BTC
```

This is a preserved service.

-->
"""
        doc_path = tmp_path / "test.md"
        doc_path.write_text(doc_content)

        parser = MarkdownParser(str(doc_path), "xr")
        with open(doc_path, encoding="utf-8") as f:
            parser.content = f.read()

        preserved = parser._extract_preserved_endpoints(["xrService"])

        assert "xrService" in preserved
        assert "This is a preserved service." in preserved["xrService"]

    def test_single_endpoint_comment_block(self, tmp_path):
        """Test extraction of a single endpoint in a comment block"""
        doc_content = """# XRouter API

## xrNormalEndpoint

> Sample Request

```shell
blocknet-cli xrNormalEndpoint
```

This is a normal endpoint.

## <!--
## xrService

> Sample Request

```shell
blocknet-cli xrService BTC
```

This is a preserved service.
-->
"""
        doc_path = tmp_path / "test.md"
        doc_path.write_text(doc_content)

        parser = MarkdownParser(str(doc_path), "xr")
        with open(doc_path, encoding="utf-8") as f:
            parser.content = f.read()

        preserved = parser._extract_preserved_endpoints(["xrService"])

        assert "xrService" in preserved
        assert "This is a preserved service." in preserved["xrService"]

    def test_whitespace_variations(self, tmp_path):
        """Test extraction with different whitespace patterns after <!--"""
        doc_content = """# XRouter API

## <!--  ## xrService

> Sample Request

```shell
blocknet-cli xrService BTC
```

This is preserved with extra whitespace.

-->
"""
        doc_path = tmp_path / "test.md"
        doc_path.write_text(doc_content)

        parser = MarkdownParser(str(doc_path), "xr")
        with open(doc_path, encoding="utf-8") as f:
            parser.content = f.read()

        preserved = parser._extract_preserved_endpoints(["xrService"])

        assert "xrService" in preserved
        assert "This is preserved with extra whitespace." in preserved["xrService"]

    def test_filter_non_preserved_endpoints(self, tmp_path):
        """Test that only specified endpoints are preserved"""
        doc_content = """# XRouter API

## <!--
## xrService

> Sample Request

```shell
blocknet-cli xrService BTC
```

Service content.

## xrServiceConsensus

> Sample Request

```shell
blocknet-cli xrServiceConsensus 1 BTC
```

Consensus content.

## xrOtherEndpoint

> Sample Request

```shell
blocknet-cli xrOtherEndpoint
```

Other endpoint content.
-->
"""
        doc_path = tmp_path / "test.md"
        doc_path.write_text(doc_content)

        parser = MarkdownParser(str(doc_path), "xr")
        with open(doc_path, encoding="utf-8") as f:
            parser.content = f.read()

        preserved = parser._extract_preserved_endpoints(["xrService"])

        assert "xrService" in preserved
        assert "xrServiceConsensus" not in preserved
        assert "xrOtherEndpoint" not in preserved

    def test_no_comment_blocks(self, tmp_path):
        """Test extraction when there are no comment blocks"""
        doc_content = """# XRouter API

## xrNormalEndpoint

> Sample Request

```shell
blocknet-cli xrNormalEndpoint
```

This is a normal endpoint.
"""
        doc_path = tmp_path / "test.md"
        doc_path.write_text(doc_content)

        parser = MarkdownParser(str(doc_path), "xr")
        with open(doc_path, encoding="utf-8") as f:
            parser.content = f.read()

        preserved = parser._extract_preserved_endpoints(["xrService"])

        assert len(preserved) == 0

    def test_insert_preserved_endpoints(self, tmp_path):
        """Test that preserved endpoints are correctly inserted into content"""
        doc_content = """# XRouter API

## xrNormalEndpoint

> Sample Request

```shell
blocknet-cli xrNormalEndpoint
```

This is a normal endpoint.
"""
        doc_path = tmp_path / "test.md"
        doc_path.write_text(doc_content)

        parser = MarkdownParser(str(doc_path), "xr")
        with open(doc_path, encoding="utf-8") as f:
            parser.content = f.read()

        preserved_sections = {
            "xrService": "This is preserved content.\n\n### Params\n\nparam1 | string",
        }
        parser._insert_preserved_endpoints(preserved_sections)

        assert "## xrService" in parser.content
        assert "This is preserved content." in parser.content

    def test_actual_xrouter_docs_preservation(self):
        """Test preservation works with actual XRouter documentation"""
        parser = MarkdownParser("blocknet-api-docs/source/includes/_xrouter.md", "xr")
        with open("blocknet-api-docs/source/includes/_xrouter.md", encoding="utf-8") as f:
            parser.content = f.read()

        preserved = parser._extract_preserved_endpoints(["xrService", "xrServiceConsensus"])

        assert "xrService" in preserved
        assert "xrServiceConsensus" in preserved
        assert "XCloud" in preserved["xrService"]
        assert "XCloud" in preserved["xrServiceConsensus"]

    def test_full_parse_with_preserved_endpoints(self):
        """Test full parse includes preserved endpoints"""
        spec = parse_api_docs("blocknet-api-docs/source/includes/_xrouter.md", "xr")

        assert "xrService" in spec.endpoints
        assert "xrServiceConsensus" in spec.endpoints

        ep_service = spec.endpoints["xrService"]
        assert "XCloud" in ep_service.description
        assert len(ep_service.params) > 0

        ep_consensus = spec.endpoints["xrServiceConsensus"]
        assert "XCloud" in ep_consensus.description
        assert len(ep_consensus.params) > 0
