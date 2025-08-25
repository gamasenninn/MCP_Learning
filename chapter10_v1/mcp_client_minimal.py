#!/usr/bin/env python3
"""
FastMCPを使った最小限のMCPクライアント V2（StdioTransport対応版）
わずか20行でMCPサーバーと通信！

V2の主要変更点：
- StdioTransportを使用した接続
- 設定可能な実行方式への対応
- 第9章と同様の接続方式に統一
"""

import asyncio
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

async def main():
    # V2: StdioTransportを使用して接続（第9章と同じ方式）
    # uvコマンドでcalculator_serverを実行
    transport = StdioTransport(
        command="uv",
        args=["--directory", r"C:\MCP_Learning\chapter03", "run", "python", "calculator_server.py"]
    )
    client = Client(transport)
    
    async with client:
        # サーバーに接続確認
        await client.ping()
        print("[OK] サーバーに接続しました")
        
        # 利用可能なツールを取得
        tools = await client.list_tools()
        print(f"\n[LIST] 利用可能なツール: {[t.name for t in tools]}")
        
        # ツールを呼び出す
        result = await client.call_tool("add", {"a": 100, "b": 200})
        print(f"\n[計算] 100 + 200 = {result}")

if __name__ == "__main__":
    asyncio.run(main())