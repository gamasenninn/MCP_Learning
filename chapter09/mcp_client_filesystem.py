#!/usr/bin/env python3
import asyncio
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

async def main():

    # StdioTransport にコマンドと引数を分けて渡す
    transport = StdioTransport(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", r"C:\MCP_Learning\chapter09"],
    )

    client = Client(transport)

    async with client:
        await client.ping()
        print("[OK] filesystem サーバーに接続しました")

        # 利用可能なツール一覧
        tools = await client.list_tools()
        print("[ツール一覧]", [t.name for t in tools])

if __name__ == "__main__":
    asyncio.run(main())
