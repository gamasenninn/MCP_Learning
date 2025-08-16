#!/usr/bin/env python3
"""
簡単な計算のダイレクトテスト
"""

import asyncio
import sys
import os

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

from fastmcp import Client

async def test_direct_calculation():
    """計算サーバーに直接接続してテスト"""
    print("直接計算テスト開始\n")
    
    # 計算サーバーに直接接続
    server_path = "C:\\MCP_Learning\\chapter03\\calculator_server.py"
    
    async with Client(server_path) as client:
        print("計算サーバーに接続しました")
        
        # 利用可能なツールを確認
        tools = await client.list_tools()
        print(f"利用可能なツール数: {len(tools)}")
        for tool in tools:
            print(f"  - {tool.name}")
        
        print("\n計算テスト:")
        
        # 加算
        result = await client.call_tool("add", {"a": 100, "b": 200})
        print(f"100 + 200 = {result}")
        
        # 減算
        result = await client.call_tool("subtract", {"a": 100, "b": 25})
        print(f"100 - 25 = {result}")
        
        # 乗算
        result = await client.call_tool("multiply", {"a": 50, "b": 3})
        print(f"50 * 3 = {result}")
        
        # 除算
        result = await client.call_tool("divide", {"a": 1000, "b": 5})
        print(f"1000 / 5 = {result}")
        
        # べき乗
        result = await client.call_tool("power", {"base": 2, "exponent": 8})
        print(f"2^8 = {result}")
    
    print("\n直接計算テスト完了")

if __name__ == "__main__":
    asyncio.run(test_direct_calculation())