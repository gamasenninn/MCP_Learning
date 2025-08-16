#!/usr/bin/env python3
"""
計算式評価ツールのテスト
"""

import asyncio
import sys
import os

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

from fastmcp import Client

async def test_evaluator():
    """評価ツールのテスト"""
    print("計算式評価ツールのテスト")
    print("=" * 60)
    
    # 評価サーバーに直接接続
    server_path = "C:\\MCP_Learning\\chapter10\\calc_evaluator.py"
    
    async with Client(server_path) as client:
        print("評価サーバーに接続しました")
        
        # 利用可能なツールを確認
        tools = await client.list_tools()
        print(f"利用可能なツール数: {len(tools)}")
        for tool in tools:
            print(f"  - {tool.name}")
        
        print("\n計算テスト:")
        
        # テストケース
        test_expressions = [
            "100 + 200 + 4 * 50",
            "(100 + 200) * 2",
            "2 ** 8",
            "1000 / 5 - 50",
            "(10 + 20) * (30 - 20)"
        ]
        
        for expr in test_expressions:
            print(f"\n式: {expr}")
            
            # 単純評価
            result = await client.call_tool("evaluate_expression", {"expression": expr})
            print(f"結果: {result}")
            
            # ステップ付き評価
            detailed = await client.call_tool("evaluate_with_steps", {"expression": expr})
            print(f"詳細: {detailed}")
    
    print("\n評価ツールテスト完了")

if __name__ == "__main__":
    asyncio.run(test_evaluator())