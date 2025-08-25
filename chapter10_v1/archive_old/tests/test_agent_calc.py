#!/usr/bin/env python3
"""
MCPエージェントの計算機能テスト
"""

import asyncio
import sys
import os

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

from mcp_agent import MCPAgent

async def test_agent_calculations():
    """エージェント経由での計算テスト"""
    print("MCPエージェント 計算機能テスト")
    print("=" * 60)
    
    agent = MCPAgent(verbose=False)
    await agent.initialize()
    
    # テストケース
    test_cases = [
        "123 + 456を計算して",
        "1000から250を引いて",
        "42に7を掛けて",
        "100を4で割って",
    ]
    
    for query in test_cases:
        print(f"\nQ: {query}")
        try:
            response = await agent.process_query(query)
            print(f"A: {response}")
        except Exception as e:
            print(f"エラー: {e}")
        print("-" * 40)
    
    # 統計表示
    print("\n[統計情報]")
    print(f"ツール呼び出し: {agent.context['tool_calls']}回")
    print(f"エラー発生: {agent.error_handler.error_stats['total']}回")
    
    await agent.cleanup()

if __name__ == "__main__":
    asyncio.run(test_agent_calculations())