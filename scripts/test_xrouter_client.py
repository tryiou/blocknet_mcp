#!/usr/bin/env python3
"""Experiment script to call XRouter MCP server in Docker."""

import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

__test__ = False  # Prevent pytest from collecting this standalone test script

async def main():
    url = "http://127.0.0.1:8082/mcp"

    async with streamable_http_client(url) as (read, write, _get_session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # tools = await session.list_tools()
            # print("=== Available tools ===")
            # for tool in tools.tools:
            #     print(f"  {tool.name}")
            # print()

            # result = await session.call_tool("xrGetNetworkServices", {})
            # for item in result.content:
            #     if hasattr(item, "text"):
            #         print("=== xrGetNetworkServices ===")
            #         print(item.text)

            result = await session.call_tool("xrService", {"service": "ping"})
            print("\n=== xrService ping ===")
            for item in result.content:
                print(item.text)

            result = await session.call_tool("xrService", {"service": "getblockcount", "paramN": "LTC"})
            print("\n=== xrService getblockcount LTC ===")
            for item in result.content:
                print(item.text)

            result = await session.call_tool("xrService", {"service": "cg_coins_data", "paramN": "bitcoin"})
            print("\n=== xrService cg_coins_data bitcoin ===")
            for item in result.content:
                print(item.text)

            result = await session.call_tool("xrService", {"service": "cg_coins_data", "paramN": "bitcoin litecoin ethereum"})
            print("\n=== xrService cg_coins_data [bitcoin, litecoin, ethereum] ===")
            for item in result.content:
                print(item.text)


if __name__ == "__main__":
    asyncio.run(main())
