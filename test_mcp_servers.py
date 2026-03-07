#!/usr/bin/env python3
"""Comprehensive test suite for MCP servers against live Blocknet node."""

import asyncio
from dataclasses import dataclass, field
import json
import os
import sys
import time
import traceback

import dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

__test__ = False  # Prevent pytest from collecting this standalone test script
# Load environment variables
dotenv.load_dotenv()

RPC_HOST = os.getenv("RPC_HOST", "localhost")
RPC_PORT = os.getenv("RPC_PORT", "41414")
RPC_USER = os.getenv("RPC_USER")
RPC_PASSWORD = os.getenv("RPC_PASSWORD")


@dataclass
class TestContext:
    """Shared context for discovered runtime data."""
    tokens: list[str] = field(default_factory=list)
    maker: str = "BLOCK"
    taker: str = "LTC"
    order_ids: list[str] = field(default_factory=list)
    block_chain: str = "BLOCK"
    block_height: int | None = None
    block_hash: str | None = None
    utxos: list[dict] = field(default_factory=list)
    address: str | None = None
    errors: list[str] = field(default_factory=list)


def extract_result_data(result):
    """Extract actual data from CallToolResult, handling FastMCP's output format."""
    if not result.content:
        return None

    texts = []
    for item in result.content:
        if hasattr(item, 'text'):
            texts.append(item.text)

    if not texts:
        return None

    if len(texts) == 1:
        try:
            return json.loads(texts[0])
        except json.JSONDecodeError:
            return texts[0]

    data = []
    for text in texts:
        try:
            data.append(json.loads(text))
        except json.JSONDecodeError:
            data.append(text)
    return data


async def safe_call(session, tool_name, params, expected_type):
    """
    Safely call a tool and validate response type.
    Returns (success, data, error_message).
    """
    try:
        result = await session.call_tool(tool_name, params)

        # DEBUG: Print raw result
        print(f"    DEBUG: {tool_name} raw content: {result.content}")

        data = extract_result_data(result)

        print(f"    DEBUG: {tool_name} extracted data: {data} (type: {type(data).__name__})")

        if data is None:
            return False, None, "Empty response"

        # Type validation (dict, list, or any)
        if expected_type == "dict" and not isinstance(data, dict):
            return False, data, f"Expected dict, got {type(data).__name__}"
        if expected_type == "list" and not isinstance(data, list):
            return False, data, f"Expected list, got {type(data).__name__}"

        return True, data, None
    except Exception as e:
        return False, None, str(e)


async def discover_tokens(session, context):
    """Discover available tokens from dxGetLocalTokens."""
    success, data, error = await safe_call(session, "dxGetLocalTokens", {}, "list")
    if success and isinstance(data, list) and len(data) > 0:
        context.tokens = data
        # Select maker/taker from available tokens
        maker = None
        taker = None
        for token in ["BLOCK", "LTC"]:
            if token in data:
                if maker is None:
                    maker = token
                elif taker is None and token != maker:
                    taker = token
        if maker:
            context.maker = maker
        if taker:
            context.taker = taker
        if maker and taker:
            context.block_chain = maker
        return True
    context.errors.append(f"Failed to discover tokens: {error or 'no data'}")
    return False


async def discover_orders(session, context):
    """Discover order IDs from dxGetOrders."""
    success, data, _ = await safe_call(session, "dxGetOrders", {}, "list")
    if success and isinstance(data, list):
        # Extract order IDs - could be dicts with 'id' key or list of IDs
        order_ids = []
        for item in data:
            if isinstance(item, dict):
                if 'id' in item:
                    order_ids.append(item['id'])
                elif 'order_id' in item:
                    order_ids.append(item['order_id'])
            elif isinstance(item, str):
                order_ids.append(item)
        context.order_ids = order_ids[:10]  # Keep up to 10 for testing
        return True
    # Not critical - many nodes may have no orders
    return False


async def discover_block_data(session, context):
    """Discover block height and hash for the blockchain."""
    if not context.block_chain:
        return False

    # Get block count
    success, data, _ = await safe_call(session, "xrGetBlockCount",
                                           {"blockchain": context.block_chain}, "dict")
    if success and isinstance(data, dict):
        # Try common keys for block height
        height = data.get('height') or data.get('block_count') or data.get('count')
        if height:
            context.block_height = int(height)

            # Get block hash for that height
            success2, data2, _ = await safe_call(session, "xrGetBlockHash",
                                                      {"blockchain": context.block_chain,
                                                       "block_number": str(height)},
                                                      "dict")
            if success2 and isinstance(data2, dict):
                block_hash = data2.get('hash') or data2.get('block_hash')
                if block_hash:
                    context.block_hash = block_hash
                    return True
    return False


async def discover_utxos(session, context):
    """Discover UTXOs for the maker asset."""
    success, data, _ = await safe_call(session, "dxGetUtxos",
                                           {"asset": context.maker}, "list")
    if success and isinstance(data, list):
        context.utxos = data[:5]  # Keep up to 5 UTXOs
        return True
    return False


async def run_discovery(session, context):
    """Run discovery phase to populate context."""
    print("  Discovery phase...")

    # Set address from RPC_USER
    context.address = RPC_USER

    # Discover tokens (most important)
    await discover_tokens(session, context)

    if not context.tokens:
        print("    Warning: No tokens discovered, using defaults BLOCK/LTC")

    print(f"    Using tokens: maker={context.maker}, taker={context.taker}")
    print(f"    Blockchain: {context.block_chain}")

    # Discover orders (optional)
    await discover_orders(session, context)
    if context.order_ids:
        print(f"    Discovered {len(context.order_ids)} orders")
    else:
        print("    No orders found (node may have no orders)")

    # Discover block data (optional)
    await discover_block_data(session, context)
    if context.block_height:
        print(f"    Block height: {context.block_height}, hash: {context.block_hash[:16]}...")

    # Discover UTXOs (optional)
    await discover_utxos(session, context)
    if context.utxos:
        print(f"    Discovered {len(context.utxos)} UTXOs for {context.maker}")

    return True


# XBridge test specifications (read-only tools only)
XBRIDGE_TESTS = [
    # No-param tools
    {"tool": "dxGetOrders", "params": {}, "type": "list"},
    {"tool": "dxGetMyOrders", "params": {}, "type": "list"},
    {"tool": "dxGetLocalTokens", "params": {}, "type": "list"},
    {"tool": "dxGetNetworkTokens", "params": {}, "type": "list"},
    {"tool": "dxGetTokenBalances", "params": {}, "type": "dict"},
    {"tool": "dxGetTradingData", "params": {}, "type": "list"},
    {"tool": "dxLoadXBridgeConf", "params": {}, "type": "dict"},

    # Tools with required parameters
    {"tool": "dxGetOrder", "params": {"id": "FIRST_ORDER_ID"}, "type": "dict", "requires": "order_ids"},
    {"tool": "dxGetOrderBook", "params": {"detail": 1, "maker": "MAKER", "taker": "TAKER"}, "type": "dict"},
    {"tool": "dxGetOrderFills", "params": {"maker": "MAKER", "taker": "TAKER"}, "type": "list"},
    {"tool": "dxGetOrderHistory", "params": {
        "maker": "MAKER", "taker": "TAKER",
        "start_time": "EPOCH_1D_AGO", "end_time": "EPOCH_NOW",
        "granularity": 86400
    }, "type": "list"},
    {"tool": "dxGetNewTokenAddress", "params": {"asset": "MAKER"}, "type": "list"},
    {"tool": "dxGetUtxos", "params": {"asset": "MAKER"}, "type": "list"},
]

# XRouter test specifications (read-only tools only)
XROUTER_TESTS = [
    # No-param tools
    {"tool": "xrGetNetworkServices", "params": {}, "type": "dict"},
    {"tool": "xrConnectedNodes", "params": {}, "type": "dict"},
    {"tool": "xrStatus", "params": {}, "type": "dict"},
    {"tool": "xrShowConfigs", "params": {}, "type": "list"},

    # Tools with required parameters
    {"tool": "xrGetBlockCount", "params": {"blockchain": "BLOCKCHAIN"}, "type": "dict"},
    {"tool": "xrGetBlockHash", "params": {"blockchain": "BLOCKCHAIN", "block_number": "HEIGHT"}, "type": "dict",
     "requires": "block_height"},
    {"tool": "xrGetBlock", "params": {"blockchain": "BLOCKCHAIN", "block_hash": "HASH"}, "type": "dict",
     "requires": "block_hash"},
    {"tool": "xrGetBlocks", "params": {"blockchain": "BLOCKCHAIN", "block_hashes": "HASH"}, "type": "dict",
     "requires": "block_hash"},
    {"tool": "xrDecodeRawTransaction", "params": {"blockchain": "BLOCKCHAIN", "tx_hex": "DUMMY"}, "type": "dict"},
    {"tool": "xrGetTransaction", "params": {"blockchain": "BLOCKCHAIN", "tx_id": "DUMMY"}, "type": "dict"},
    {"tool": "xrGetTransactions", "params": {"blockchain": "BLOCKCHAIN", "tx_ids": "DUMMY"}, "type": "dict"},
    {"tool": "xrGetReply", "params": {"uuid": "00000000-0000-0000-0000-000000000000"}, "type": "dict"},
]


def resolve_params(param_template, context):
    """Resolve placeholders in parameter template using context."""
    resolved = {}
    now = int(time.time())
    one_day_ago = now - 86400

    for key, value in param_template.items():
        if value == "MAKER":
            resolved[key] = context.maker
        elif value == "TAKER":
            resolved[key] = context.taker
        elif value == "BLOCKCHAIN":
            resolved[key] = context.block_chain
        elif value == "FIRST_ORDER_ID":
            resolved[key] = context.order_ids[0] if context.order_ids else None
        elif value == "HEIGHT":
            resolved[key] = str(context.block_height) if context.block_height else None
        elif value == "HASH":
            resolved[key] = context.block_hash if context.block_hash else None
        elif value == "EPOCH_NOW":
            resolved[key] = now
        elif value == "EPOCH_1D_AGO":
            resolved[key] = one_day_ago
        elif value == "DUMMY":
            # Use placeholder values that will likely fail but test the tool exists
            if key == "tx_hex":
                resolved[key] = "0200000001" + "0" * 56 + "00000000"
            elif key == "tx_id":
                resolved[key] = "0" * 64
            elif key == "tx_ids":
                resolved[key] = "0" * 64
        else:
            resolved[key] = value

    return resolved


async def run_xbridge_tests(session, context):
    """Run all XBridge read-only tests."""
    print("\nXBridge MCP Server Tests")
    print("=" * 60)

    results = []
    for test_spec in XBRIDGE_TESTS:
        tool = test_spec["tool"]
        param_template = test_spec["params"]
        expected_type = test_spec["type"]
        requires = test_spec.get("requires")

        # Check dependencies
        if requires:
            if requires == "order_ids" and not context.order_ids:
                print(f"  {tool}: SKIP (no orders discovered)")
                results.append((tool, None, "skipped", "No orders available"))
                continue
            elif requires == "block_height" and not context.block_height:
                print(f"  {tool}: SKIP (no block data)")
                results.append((tool, None, "skipped", "No block height"))
                continue
            elif requires == "block_hash" and not context.block_hash:
                print(f"  {tool}: SKIP (no block hash)")
                results.append((tool, None, "skipped", "No block hash"))
                continue

        # Resolve parameters
        params = resolve_params(param_template, context)

        # Run test
        success, data, error = await safe_call(session, tool, params, expected_type)

        if success:
            print(f"  {tool}: ✓ PASS")
            if isinstance(data, list):
                print(f"    Returned {len(data)} items")
            elif isinstance(data, dict):
                keys = list(data.keys())[:5]
                print(f"    Returned dict with keys: {', '.join(keys)}")
        else:
            print(f"  {tool}: ✗ FAIL")
            print(f"    Error: {error}")

        results.append((tool, params, "pass" if success else "fail", error or ""))

    return results


async def run_xrouter_tests(session, context):
    """Run all XRouter read-only tests."""
    print("\nXRouter MCP Server Tests")
    print("=" * 60)

    results = []
    for test_spec in XROUTER_TESTS:
        tool = test_spec["tool"]
        param_template = test_spec["params"]
        expected_type = test_spec["type"]
        requires = test_spec.get("requires")

        # Check dependencies
        if requires:
            if requires == "order_ids" and not context.order_ids:
                print(f"  {tool}: SKIP (no orders)")
                results.append((tool, None, "skipped", "No orders"))
                continue
            elif requires == "block_height" and not context.block_height:
                print(f"  {tool}: SKIP (no block height)")
                results.append((tool, None, "skipped", "No block height"))
                continue
            elif requires == "block_hash" and not context.block_hash:
                print(f"  {tool}: SKIP (no block hash)")
                results.append((tool, None, "skipped", "No block hash"))
                continue

        # Resolve parameters
        params = resolve_params(param_template, context)

        # Run test
        success, data, error = await safe_call(session, tool, params, expected_type)

        if success:
            print(f"  {tool}: ✓ PASS")
            if isinstance(data, list):
                print(f"    Returned {len(data)} items")
            elif isinstance(data, dict):
                keys = list(data.keys())[:5]
                print(f"    Returned dict with keys: {', '.join(keys)}")
        else:
            print(f"  {tool}: ✗ FAIL")
            print(f"    Error: {error}")

        results.append((tool, params, "pass" if success else "fail", error or ""))

    return results


def print_summary(xbridge_results, xrouter_results):
    """Print test summary."""
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    xb_pass = sum(1 for _, _, status, _ in xbridge_results if status == "pass")
    xb_fail = sum(1 for _, _, status, _ in xbridge_results if status == "fail")
    xb_skip = sum(1 for _, _, status, _ in xbridge_results if status == "skipped")
    xb_total = len(xbridge_results)

    xr_pass = sum(1 for _, _, status, _ in xrouter_results if status == "pass")
    xr_fail = sum(1 for _, _, status, _ in xrouter_results if status == "fail")
    xr_skip = sum(1 for _, _, status, _ in xrouter_results if status == "skipped")
    xr_total = len(xrouter_results)

    total_pass = xb_pass + xr_pass
    total_fail = xb_fail + xr_fail
    total_skip = xb_skip + xr_skip
    total = xb_total + xr_total

    print("\nXBridge MCP Server:")
    print(f"  Total tools: {xb_total}")
    print(f"  Passed: {xb_pass}")
    print(f"  Failed: {xb_fail}")
    print(f"  Skipped: {xb_skip}")

    print("\nXRouter MCP Server:")
    print(f"  Total tools: {xr_total}")
    print(f"  Passed: {xr_pass}")
    print(f"  Failed: {xr_fail}")
    print(f"  Skipped: {xr_skip}")

    print("\nOVERALL:")
    print(f"  Total: {total}")
    print(f"  Passed: {total_pass} ({100 * total_pass / total:.1f}%)")
    print(f"  Failed: {total_fail}")
    print(f"  Skipped: {total_skip}")

    if total_fail > 0:
        print("\nFailed tools:")
        for tool, params, status, error in xbridge_results + xrouter_results:
            if status == "fail":
                print(f"  - {tool}: {error}")


async def test_xbridge_server():
    """Comprehensive test of XBridge MCP server."""
    print("Testing XBridge MCP Server...")

    env = {k: v for k, v in {
        "RPC_HOST": RPC_HOST,
        "RPC_PORT": RPC_PORT,
        "RPC_USER": RPC_USER,
        "RPC_PASSWORD": RPC_PASSWORD,
        "MCP_ALLOW_WRITE": "false"
    }.items() if v is not None}

    server_params = StdioServerParameters(
        command="python",
        args=["-m", "generated.xbridge_mcp.main"],
        env=env
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Get list of tools
            tools = await session.list_tools()
            print(f"  Available tools: {len(tools.tools)}")

            # Discovery phase
            context = TestContext(address=RPC_USER)
            await run_discovery(session, context)

            # Run tests
            results = await run_xbridge_tests(session, context)

    print("XBridge tests complete")
    return results


async def test_xrouter_server():
    """Comprehensive test of XRouter MCP server."""
    print("\nTesting XRouter MCP Server...")

    env = {k: v for k, v in {
        "RPC_HOST": RPC_HOST,
        "RPC_PORT": RPC_PORT,
        "RPC_USER": RPC_USER,
        "RPC_PASSWORD": RPC_PASSWORD,
        "MCP_ALLOW_WRITE": "false"
    }.items() if v is not None}

    server_params = StdioServerParameters(
        command="python",
        args=["-m", "generated.xrouter_mcp.main"],
        env=env
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Get list of tools
            tools = await session.list_tools()
            print(f"  Available tools: {len(tools.tools)}")

            # Discovery phase (reuse context from XBridge if available)
            context = TestContext(address=RPC_USER, block_chain="BLOCK")
            # For XRouter, we need block data; try to get it
            await discover_block_data(session, context)
            if context.block_height:
                print(f"  Using blockchain: {context.block_chain}, height: {context.block_height}")

            # Run tests
            results = await run_xrouter_tests(session, context)

    print("XRouter tests complete")
    return results


async def main():
    """Run comprehensive test suite."""
    if not all([RPC_USER, RPC_PASSWORD]):
        print("Error: RPC credentials not set in .env", file=sys.stderr)
        sys.exit(1)

    try:
        xbridge_results = await test_xbridge_server()
        xrouter_results = await test_xrouter_server()

        print_summary(xbridge_results, xrouter_results)

        total_fail = sum(1 for _, _, status, _ in xbridge_results + xrouter_results if status == "fail")
        if total_fail > 0:
            sys.exit(1)

        print("\nAll tests completed successfully!")
    except Exception as e:
        print(f"Test failed: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
