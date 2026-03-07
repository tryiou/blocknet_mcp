#!/usr/bin/env python3
"""
MCP Server Generator - Entry Point

Generates MCP servers from Blocknet API documentation.

Usage:
    python main.py <doc_path> <prefix>
    python main.py --doc <path> --prefix <dx|xr|ALL>

Examples:
    python main.py blocknet-api-docs/source/includes/_xbridge.md dx
    python main.py blocknet-api-docs/source/includes/_xrouter.md xr
    python main.py --doc blocknet-api-docs/source/includes --prefix ALL
"""

import argparse
from pathlib import Path
import sys
import traceback

from scripts.generate.generator import WRITE_PROTECTED, Generator

PREFIX_MAP = {
    "dx": {
        "name": "xbridge",
        "default_doc": "blocknet-api-docs/source/includes/_xbridge.md",
    },
    "xr": {
        "name": "xrouter",
        "default_doc": "blocknet-api-docs/source/includes/_xrouter.md",
    },
}


def get_doc_path(prefix: str, doc_path: str | None = None) -> str:
    """Resolve document path for given prefix"""
    if doc_path:
        return doc_path

    default = PREFIX_MAP.get(prefix, {}).get("default_doc")
    if default and Path(default).exists():
        return default

    raise ValueError(f"No doc path specified for prefix '{prefix}'")


def generate_server(prefix: str, doc_path: str | None = None) -> None:
    """Generate a single MCP server"""
    resolved_doc = get_doc_path(prefix, doc_path)

    if not Path(resolved_doc).exists():
        raise FileNotFoundError(f"Doc file not found: {resolved_doc}")

    pkg_name = PREFIX_MAP.get(prefix, {}).get("name", prefix)
    output_dir = Path("generated") / f"{pkg_name}_mcp"

    print(f"Generating {prefix.upper()} MCP server...")
    print(f"  Doc: {resolved_doc}")
    print(f"  Output: {output_dir}")
    print()

    Generator(resolved_doc, prefix, str(output_dir)).generate()


def generate_all(doc_path: str | None = None) -> None:
    """Generate all MCP servers (dx + xr)"""
    print("Generating ALL MCP servers (dx + xr)...")
    print()

    for prefix in ["dx", "xr"]:
        print(f"--- {prefix.upper()} ---")
        try:
            generate_server(prefix, doc_path)
            print()
        except Exception as e:
            print(f"  Error generating {prefix}: {e}")
            print()

    print("Done! Generated dx_mcp and xr_mcp in ./generated/")


def list_all_protected():
    """Print all write-protected RPC methods from YAML config"""
    print("Write-Protected RPC Methods (from write_protected.yaml)")
    print("=" * 60)
    print()
    print("XBridge:")
    for method in sorted(WRITE_PROTECTED.get("dx", [])):
        print(f"  - {method}")
    print()
    print("XRouter:")
    for method in sorted(WRITE_PROTECTED.get("xr", [])):
        print(f"  - {method}")
    print()
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Generate MCP servers from Blocknet API documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py dx                    # Generate XBridge server
  python main.py xr                    # Generate XRouter server  
  python main.py ALL                   # Generate combined server
  python main.py dx --doc custom.md    # Generate with custom doc
  python main.py --prefix xr --doc path/to/_xrouter.md
        """,
    )

    parser.add_argument(
        "prefix",
        nargs="?",
        choices=["dx", "xr", "ALL", "all"],
        help="Prefix: dx (XBridge), xr (XRouter), ALL (combined)",
    )

    parser.add_argument(
        "--doc",
        "-d",
        help="Path to API documentation markdown file (or directory for ALL)",
    )

    parser.add_argument(
        "--prefix",
        "-p",
        dest="prefix_opt",
        choices=["dx", "xr", "ALL", "all"],
        help="Prefix (alternative to positional arg)",
    )

    parser.add_argument(
        "--list-protected",
        action="store_true",
        help="List all write-protected RPC methods and exit",
    )

    args = parser.parse_args()

    # Handle --list-protected flag first (doesn't require prefix)
    if args.list_protected:
        list_all_protected()
        sys.exit(0)

    prefix = args.prefix or args.prefix_opt
    doc_path = args.doc

    if not prefix:
        parser.print_help()
        sys.exit(1)

    prefix = prefix.lower()

    try:
        if prefix == "all":
            generate_all(doc_path)
        else:
            generate_server(prefix, doc_path)

        print()
        print("Done!")

    except Exception as e:
        print(f"Error: {e}")

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
