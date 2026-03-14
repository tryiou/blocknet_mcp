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
import sys
import traceback
from pathlib import Path

from src.generator import WRITE_PROTECTED, Generator

FILENAME_MAP = {
    "dx": "_xbridge.md",
    "xr": "_xrouter.md",
}

PREFIX_MAP = {
    "dx": {
        "name": "xbridge",
        "default_doc": "blocknet-api-docs",
    },
    "xr": {
        "name": "xrouter",
        "default_doc": "blocknet-api-docs",
    },
}


def get_doc_path(prefix: str, doc_path: str | None = None) -> str:
    """Resolve document path for given prefix.

    The doc_path should be the root of the cloned api-docs repo.
    We then look for source/includes/_xbridge.md or _xrouter.md inside.
    """
    if prefix not in FILENAME_MAP:
        raise ValueError(f"Invalid prefix: {prefix}")

    filename = FILENAME_MAP[prefix]

    # Determine base directory (provided or default)
    if doc_path:
        base = Path(doc_path)
        if base.is_file():
            raise ValueError(f"--doc-path must be a directory, not a file: {doc_path}")
    else:
        base = Path(PREFIX_MAP[prefix]["default_doc"])

    # Resolve to the specific markdown file
    resolved = base / "source/includes" / filename

    if not resolved.exists():
        raise FileNotFoundError(f"Documentation file not found: {resolved}")

    return str(resolved)


def generate_server(prefix: str, doc_path: str | None = None) -> None:
    """Generate a single MCP server"""
    resolved_doc = get_doc_path(prefix, doc_path)

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

    errors = []
    for prefix in ["dx", "xr"]:
        print(f"--- {prefix.upper()} ---")
        try:
            generate_server(prefix, doc_path)
            print()
        except FileNotFoundError as e:
            error_msg = f"Documentation not found for {prefix}: {e}"
            errors.append(error_msg)
            print(f"  Error: {error_msg}")
            print()
        except Exception as e:
            error_msg = f"Unexpected error generating {prefix}: {e}"
            errors.append(error_msg)
            print(f"  {error_msg}")
            print()

    if errors:
        print("Generation completed with errors.")
        # If all errors are FileNotFoundError, re-raise the first one to trigger helpful hints
        if all("Documentation not found" in err for err in errors):
            raise FileNotFoundError(errors[0].split(": ", 1)[1])
    else:
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
  python main.py dx                    # Generate XBridge server (default docs)
  python main.py xr                    # Generate XRouter server (default docs)
  python main.py ALL                   # Generate both servers
  python main.py dx --doc-path /path/to/blocknet-api-docs   # Custom docs location
  python main.py xr --doc-path ./blocknet-api-docs
        """,
    )

    parser.add_argument(
        "prefix",
        nargs="?",
        choices=["dx", "xr", "ALL", "all"],
        help="Prefix: dx (XBridge), xr (XRouter), ALL (combined)",
    )

    parser.add_argument(
        "--doc-path",
        "-d",
        help="Path to Blocknet API docs repository root (containing source/includes/). Default: blocknet-api-docs",
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
    doc_path_arg = args.doc_path

    if not prefix:
        parser.print_help()
        sys.exit(1)

    prefix = prefix.lower()

    try:
        if prefix == "all":
            generate_all(doc_path_arg)
        else:
            generate_server(prefix, doc_path_arg)

        print()
        print("Done!")

    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("\nHint: The Blocknet API documentation is required to generate MCP servers.")
        print("You can obtain it by:")
        print("  1. Running: ./build-local.sh (automatically clones docs)")
        print("  2. Manually: git clone https://github.com/blocknetdx/api-docs blocknet-api-docs")
        print("  3. Or specify a custom path with: --doc-path /path/to/docs")
        sys.exit(1)

    except Exception as e:
        print(f"Unexpected error: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
