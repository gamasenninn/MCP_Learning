#!/usr/bin/env python3
"""
計算機能のテスト
シンプルな計算が正しく動作するか確認
"""

import asyncio
import sys
import os

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

from mcp_agent import MCPAgent

async def test_calculations():
    """計算機能のテスト"""
    print("計算機能テスト開始\n")
    
    agent = MCPAgent(verbose=False)  # 詳細出力を抑制
    await agent.initialize()
    
    # テストケース
    test_cases = [
        "100 + 200を計算して",
        "50 * 3を計算して", 
        "1000 / 5を計算して",
        "100 - 25を計算して",
        "2の8乗を計算して"
    ]
    
    print("=" * 60)
    for query in test_cases:
        print(f"Q: {query}")
        response = await agent.process_query(query)
        # 結果の最初の部分だけ表示
        if len(response) > 100:
            print(f"A: {response[:100]}...")
        else:
            print(f"A: {response}")
        print("-" * 40)
    
    await agent.cleanup()
    print("\n計算テスト完了")

if __name__ == "__main__":
    asyncio.run(test_calculations())