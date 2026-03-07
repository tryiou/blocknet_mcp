"""Integration tests for Generator - end-to-end code generation"""

from scripts.generate.generator import Generator


def test_generator_xbridge(tmp_path):
    """Test full generation of XBridge MCP server"""
    output_dir = tmp_path / "xbridge_mcp"

    gen = Generator(doc_path="blocknet-api-docs/source/includes/_xbridge.md", prefix="dx", output_dir=str(output_dir))

    gen.generate()

    # Verify spec loaded correctly
    assert gen.spec is not None
    assert gen.spec.name == "xbridge_mcp"
    assert len(gen.spec.endpoints) > 0

    # Verify parser fixes: error codes should be populated
    assert len(gen.spec.error_codes) > 0, "Error codes should be parsed"

    # Check specific endpoints that had issues
    # dxGetOrderBook should have 4 params
    orderbook = gen.spec.endpoints.get("dxGetOrderBook")
    assert orderbook is not None
    assert len(orderbook.params) == 4, f"dxGetOrderBook should have 4 params, got {len(orderbook.params)}"

    # dxGetOrders should have 0 params and clean description
    orders = gen.spec.endpoints.get("dxGetOrders")
    assert orders is not None
    assert len(orders.params) == 0
    assert "This call is used to retrieve all orders" in orders.description
    assert "<aside" not in orders.description
    assert "Key | Type" not in orders.description

    # dxSplitInputs should have several params (duplicate heading fix)
    split_inputs = gen.spec.endpoints.get("dxSplitInputs")
    assert split_inputs is not None
    assert len(split_inputs.params) == 7, f"dxSplitInputs should have 7 params, got {len(split_inputs.params)}"

    # dxGetLocalTokens (duplicate heading) should have 0 params (correct section)
    local_tokens = gen.spec.endpoints.get("dxGetLocalTokens")
    assert local_tokens is not None
    assert len(local_tokens.params) == 0, f"dxGetLocalTokens should have 0 params, got {len(local_tokens.params)}"

    # Verify key output files exist
    assert (output_dir / "main.py").exists()
    assert (output_dir / "config.py").exists()
    assert (output_dir / "generated" / "tools.py").exists()
    assert (output_dir / "generated" / "specs.py").exists()
    assert (output_dir / "rpc" / "client.py").exists()


def test_generator_xrouter(tmp_path):
    """Test full generation of XRouter MCP server"""
    output_dir = tmp_path / "xrouter_mcp"

    gen = Generator(doc_path="blocknet-api-docs/source/includes/_xrouter.md", prefix="xr", output_dir=str(output_dir))

    gen.generate()

    assert gen.spec is not None
    assert gen.spec.name == "xrouter_mcp"
    assert len(gen.spec.endpoints) > 0

    assert (output_dir / "main.py").exists()
    assert (output_dir / "config.py").exists()
    assert (output_dir / "generated" / "tools.py").exists()
    assert (output_dir / "generated" / "specs.py").exists()
    assert (output_dir / "rpc" / "client.py").exists()
