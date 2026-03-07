#!/usr/bin/env bash
#
# Blocknet MCP Server Generator - Build Script
#
# This script prepares the environment and generates XBridge and XRouter MCP servers.
#
# PREREQUISITE: You must have a .env file with RPC credentials configured.
# Copy .env.example to .env and edit before running this script.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Blocknet MCP Server Generator - Build"
echo "=========================================="
echo

# 1. Check Python version (require 3.10+)
echo "[1/7] Checking Python version..."
PYTHON_CMD=""
if command -v python3 &>/dev/null; then
	PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
	PYTHON_CMD="python"
else
	echo "ERROR: Python not found. Install Python 3.10 or higher."
	exit 1
fi

PY_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]); then
	echo "ERROR: Python 3.10+ required. Found: $PY_VERSION"
	exit 1
fi

echo "  ✓ Python $PY_VERSION detected"
echo

# 2. Create virtual environment if missing
echo "[2/7] Setting up virtual environment..."
if [ ! -d ".venv" ]; then
	echo "  Creating venv..."
	$PYTHON_CMD -m venv .venv
	echo "  ✓ Virtual environment created"
else
	echo "  ✓ Virtual environment already exists"
fi
echo

# 3. Install dependencies
echo "[3/7] Installing dependencies..."
ACTIVATE_VENV=". .venv/bin/activate"
if [ -f ".venv/bin/activate" ]; then
	source .venv/bin/activate
	pip install --upgrade pip >/dev/null 2>&1
	pip install -r requirements.txt
	echo "  ✓ Dependencies installed"
else
	echo "ERROR: venv activation script not found. Expected .venv/bin/activate"
	exit 1
fi
echo

# 4. Clone or update blocknet-api-docs
echo "[4/7] Preparing API documentation..."
if [ ! -d "blocknet-api-docs" ]; then
	echo "  Cloning blocknetdx/api-docs..."
	git clone https://github.com/blocknetdx/api-docs blocknet-api-docs
	echo "  ✓ API docs cloned"
else
	echo "  Updating existing API docs..."
	cd blocknet-api-docs
	git pull --rebase
	cd ..
	echo "  ✓ API docs updated"
fi
echo

# 5. Check for .env file
echo "[5/7] Checking configuration..."
if [ ! -f ".env" ]; then
	echo "ERROR: .env file not found!"
	echo
	echo "Please create a .env file with your RPC credentials:"
	echo "  cp .env.example .env"
	echo "  # Edit .env and set RPC_HOST, RPC_PORT, RPC_USER, RPC_PASSWORD"
	echo
	exit 1
fi
echo "  ✓ .env file found"
echo

# 6. Clean generated directory
echo "[6/7] Cleaning previous build..."
if [ -d "generated" ]; then
	rm -rf generated
	echo "  ✓ Removed generated/"
else
	echo "  ✓ No previous build to clean"
fi
echo

# 7. Generate servers
echo "[7/7] Generating MCP servers..."
python main.py ALL
echo
echo "=========================================="
echo "Build Complete!"
echo "=========================================="
echo
echo "Generated servers:"
echo "  - generated/xbridge_mcp/"
echo "  - generated/xrouter_mcp/"
echo
echo "To run a server:"
echo "  python -m generated.xbridge_mcp.main"
echo "  python -m generated.xrouter_mcp.main"
echo
echo "Make sure your .env credentials are correct and the node is running."
echo
