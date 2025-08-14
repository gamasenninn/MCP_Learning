#!/usr/bin/env python3
"""
シンプルな接続テスト
"""

import asyncio
from fastmcp import Client

async def test_server(server_path, server_name):
    """サーバーへの接続をテスト"""
    print(f"\n=== {server_name} ===")
    print(f"パス: {server_path}")
    
    try:
        client = Client(server_path)
        
        async with client:
            await client.ping()
            print("✅ 接続成功")
            
            tools = await client.list_tools()
            print(f"📋 ツール数: {len(tools)}")
            
            if tools:
                print(f"   最初のツール: {tools[0].name}")
                
    except Exception as e:
        print(f"❌ エラー: {e}")
        # エラーの詳細を表示
        import traceback
        print("\n詳細なエラー情報:")
        traceback.print_exc()

async def main():
    # 計算サーバー（動作確認用）
    await test_server(
        r"C:\MCP_Learning\chapter03\calculator_server.py",
        "計算サーバー"
    )
    
    # 汎用ツールサーバー（問題のあるサーバー）
    await test_server(
        r"C:\MCP_Learning\chapter08\universal_tools_server.py",
        "汎用ツールサーバー"
    )

if __name__ == "__main__":
    print("FastMCP接続テスト")
    print("=" * 50)
    asyncio.run(main())