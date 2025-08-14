#!/usr/bin/env python3
"""
FastMCPを使った最小限のMCPクライアント
わずか20行でMCPサーバーと通信！
"""

import asyncio
from fastmcp import Client

async def main():
    # 1行でクライアントを作成（サーバーのパスを指定）
    client = Client(r"C:\MCP_Learning\chapter03\calculator_server.py")
    
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