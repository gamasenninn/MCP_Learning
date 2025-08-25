#!/usr/bin/env python3
"""
複雑な計算のテスト
"""

import asyncio
import sys
import os

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

from mcp_agent import MCPAgent

async def test_complex_calculations():
    """複雑な計算のテスト"""
    print("複雑な計算テスト")
    print("=" * 60)
    
    agent = MCPAgent(verbose=True)
    await agent.initialize()
    
    # テストケース
    test_cases = [
        # シンプルな式として処理されるべき
        "100 + 200 + 4 * 50を計算して",
        
        # タスク分解が必要な複雑な処理
        "まず100と200を足して、その結果から50を引いて、最後に2で割って"
    ]
    
    for query in test_cases:
        print(f"\n{'='*60}")
        print(f"Q: {query}")
        print("-" * 60)
        
        try:
            response = await agent.process_query(query)
            print(f"\n最終結果: {response}")
        except Exception as e:
            print(f"エラー: {e}")
    
    # 統計表示
    print("\n" + "=" * 60)
    print("[統計情報]")
    print(f"ツール呼び出し: {agent.context['tool_calls']}回")
    print(f"タスク完了: {agent.context['tasks_completed']}個")
    print(f"エラー発生: {agent.error_handler.error_stats['total']}回")
    
    await agent.cleanup()

if __name__ == "__main__":
    asyncio.run(test_complex_calculations())