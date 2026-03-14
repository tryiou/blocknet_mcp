#!/usr/bin/env python3
"""Health check and info script for Blocknet MCP Docker containers."""

import json
import subprocess
import sys

try:
    import httpx
    import yaml
except ImportError:
    print("Error: Required packages missing. Run: pip install httpx pyyaml", file=sys.stderr)
    sys.exit(1)


# Write-protected tools from write_protected.yaml
WRITE_PROTECTED_TOOLS = {
    "dx": [
        "dxMakeOrder",
        "dxMakePartialOrder",
        "dxTakeOrder",
        "dxCancelOrder",
        "dxFlushCancelledOrders",
        "dxSplitAddress",
        "dxSplitInputs",
        "dxLoadXBridgeConf",
    ],
    "xr": ["xrUpdateNetworkServices", "xrConnect", "xrSendTransaction", "xrService", "xrServiceConsensus", "xrReloadConfigs"],
}


def print_header(text):
    """Print a formatted header."""
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}\n")


def run_cmd(cmd):
    """Run a shell command and return output."""
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    return result.returncode == 0, result.stdout, result.stderr


def get_ports_from_compose(compose_path="docker-compose.yml"):
    """Extract XBRIDGE_MCP_PORT and XROUTER_MCP_PORT values from docker-compose.yml."""
    ports = {}

    try:
        with open(compose_path) as f:
            compose = yaml.safe_load(f)

        services = compose.get("services", {})

        # XBridge
        xbridge = services.get("xbridge-mcp", {})
        env = xbridge.get("environment", [])
        for var in env:
            if isinstance(var, str) and var.startswith("XBRIDGE_MCP_PORT="):
                ports["xbridge"] = int(var.split("=", 1)[1])
                break

        # XRouter
        xrouter = services.get("xrouter-mcp", {})
        env = xrouter.get("environment", [])
        for var in env:
            if isinstance(var, str) and var.startswith("XROUTER_MCP_PORT="):
                ports["xrouter"] = int(var.split("=", 1)[1])
                break

    except Exception as e:
        print(f"   ⚠️  Could not read docker-compose.yml: {e}")

    return ports


def check_docker_containers():
    """Check if required containers are running."""
    print("1. Docker Container Status")

    success, stdout, _ = run_cmd("docker ps --format '{{.Names}}\t{{.Status}}'")

    if not success:
        print("   ❌ Failed to run docker ps")
        return {}

    containers = {}
    for line in stdout.strip().split("\n"):
        if line:
            parts = line.split("\t")
            if len(parts) >= 2:
                name, status = parts[0], parts[1]
                containers[name] = status

    required = ["xbridge-mcp", "xrouter-mcp", "blocknet-core"]
    all_ok = True

    for name in required:
        if name in containers:
            status = containers[name]
            # Simple health indicator
            health_icon = "✅" if "healthy" in status or "Up" in status else "⚠️"
            print(f"   {health_icon} {name}: {status}")
        else:
            print(f"   ❌ {name}: NOT RUNNING")
            all_ok = False

    print()
    return {"containers": containers, "all_running": all_ok}


def get_mcp_tools(url):
    """Fetch list of available tools from MCP server."""
    try:
        resp = httpx.post(
            url,
            headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "healthcheck", "version": "1.0"}},
            },
            timeout=10.0,
        )

        if resp.status_code != 200:
            return None, None

        session_id = resp.headers.get("mcp-session-id")
        if not session_id:
            return None, None

        # Get tools list
        list_resp = httpx.post(
            url,
            headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream", "mcp-session-id": session_id},
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            timeout=10.0,
        )

        if list_resp.status_code != 200:
            return session_id, None

        lines = list_resp.text.strip().split("\n")
        for line in lines:
            if line.startswith("data:"):
                try:
                    payload = json.loads(line.split(":", 1)[1].strip())
                    tools = payload.get("result", {}).get("tools", [])
                    tool_names = [t["name"] for t in tools]
                    return session_id, tool_names
                except Exception:
                    break

        return session_id, None

    except Exception:
        return None, None


def analyze_tools(url, server_name):
    """Get and analyze tools from a server."""
    print(f"\n3. {server_name} MCP Server")
    print(f"   Endpoint: {url}")

    session_id, tools = get_mcp_tools(url)

    if not session_id:
        print("   ❌ Failed to connect")
        return None, None

    if tools is None:
        print("   ❌ Failed to retrieve tools")
        return None, None

    print(f"   ✅ Connected (session: {session_id[:16]}...)")
    print(f"   ✅ Total tools available: {len(tools)}")

    # Categorize tools
    prefix = "dx" if server_name == "XBridge" else "xr"
    protected = set(WRITE_PROTECTED_TOOLS.get(prefix, []))
    available_protected = [t for t in tools if t in protected]
    available_readonly = [t for t in tools if t not in protected]

    print(f"   ✅ Write-protected tools: {len(available_protected)}")
    print(f"   ✅ Read-only tools: {len(available_readonly)}")

    # Show protected tools if any
    if available_protected:
        print(f"\n   Protected tools ({len(available_protected)}):")
        for tool in sorted(available_protected):
            print(f"      • {tool}")

    # Show read-only tools summary
    if available_readonly:
        print(f"\n   Read-only tools ({len(available_readonly)}):")
        for tool in sorted(available_readonly):
            print(f"      • {tool}")

    return tools, available_protected


def main():
    """Run health checks and show tool info."""
    print_header("Blocknet MCP Container Health Check")

    # Get ports from docker-compose.yml
    ports = get_ports_from_compose()
    xbridge_port = ports.get("xbridge", 8081)
    xrouter_port = ports.get("xrouter", 8082)

    print(f"Using ports from docker-compose.yml: XBridge={xbridge_port}, XRouter={xrouter_port}\n")

    # 1. Check Docker containers
    docker_status = check_docker_containers()

    if not docker_status.get("all_running"):
        print("\n⚠️  Some containers are not running. Check with: docker ps")
        return 1

    # 2. Analyze XBridge
    xb_tools, xb_protected = analyze_tools(f"http://localhost:{xbridge_port}/mcp", "XBridge")

    # 3. Analyze XRouter
    xr_tools, xr_protected = analyze_tools(f"http://localhost:{xrouter_port}/mcp", "XRouter")

    # Summary
    print_header("Summary")

    print("Container Status:")
    for name in ["xbridge-mcp", "xrouter-mcp", "blocknet-core"]:
        emoji = "✅" if name in docker_status["containers"] else "❌"
        print(f"  {emoji} {name}")

    print("\nMCP Server Status:")
    if xb_tools:
        print(f"  ✅ XBridge MCP - {len(xb_tools)} tools ({len(xb_protected or [])} protected)")
    else:
        print("  ❌ XBridge MCP - Not responding")

    if xr_tools:
        print(f"  ✅ XRouter MCP - {len(xr_tools)} tools ({len(xr_protected or [])} protected)")
    else:
        print("  ❌ XRouter MCP - Not responding")

    print()

    if xb_tools and xr_tools:
        print("✅ All services healthy!")
        return 0
    else:
        print("❌ Some services failed health check!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
