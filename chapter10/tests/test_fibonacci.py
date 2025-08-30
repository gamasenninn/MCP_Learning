#!/usr/bin/env python3
"""
フィボナッチ数列のエラーリトライテスト
修正されたエラーハンドラーが動作するかテスト
"""

import asyncio
from mcp_agent import MCPAgent

async def test_fibonacci():
    """フィボナッチ数列のテストを実行"""
    agent = MCPAgent()
    
    try:
        # エージェントを初期化
        await agent.initialize()
        
        print("=== フィボナッチ数列エラーリトライテスト開始 ===")
        
        print("\n1. フィボナッチ数列をリクエスト")
        response = await agent.process_request("フィボナッチ数列を20個表示")
        print(f"結果: {response}")
        
        print("=== テスト完了 ===")
        
    except Exception as e:
        print(f"テストエラー: {e}")

if __name__ == "__main__":
    asyncio.run(test_fibonacci())