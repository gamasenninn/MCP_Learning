#!/usr/bin/env python3
"""
サーバーを直接起動してテスト
"""

import asyncio
from pathlib import Path
from fastmcp import Client

async def test_calculator():
    """計算サーバーをテスト"""
    print("=== 計算サーバーのテスト ===")
    server_path = r"C:\MCP_Learning\chapter03\calculator_server.py"
    
    if not Path(server_path).exists():
        print(f"❌ サーバーファイルが存在しません: {server_path}")
        return
    
    try:
        # uvコマンドを使ってサーバーを起動
        client = Client(
            server_command=["uv", "run", "python", server_path]
        )
        
        async with client:
            await client.ping()
            print("✅ 計算サーバーに接続成功")
            
            # ツール一覧を取得
            tools = await client.list_tools()
            print(f"📋 利用可能なツール数: {len(tools)}")
            
            # 計算を実行
            result = await client.call_tool("add", {"a": 100, "b": 200})
            print(f"🧮 100 + 200 = {result}")
            
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()

async def test_universal():
    """汎用ツールサーバーをテスト"""
    print("\n=== 汎用ツールサーバーのテスト ===")
    server_path = r"C:\MCP_Learning\chapter08\universal_tools_server.py"
    
    if not Path(server_path).exists():
        print(f"❌ サーバーファイルが存在しません: {server_path}")
        return
    
    try:
        # uvコマンドを使ってサーバーを起動
        client = Client(
            server_command=["uv", "run", "python", server_path]
        )
        
        async with client:
            await client.ping()
            print("✅ 汎用ツールサーバーに接続成功")
            
            # ツール一覧を取得
            tools = await client.list_tools()
            print(f"📋 利用可能なツール数: {len(tools)}")
            
            # コードを実行
            result = await client.call_tool(
                "execute_python", 
                {"code": "print('Hello from test!')"}
            )
            print(f"🖥️ 実行結果: {result}")
            
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()

async def main():
    # 計算サーバーをテスト
    await test_calculator()
    
    # 汎用ツールサーバーをテスト
    await test_universal()

if __name__ == "__main__":
    asyncio.run(main())