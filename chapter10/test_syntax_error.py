#!/usr/bin/env python3
"""
構文エラーのリトライテスト
セミコロン記法エラーが自動修正されるかテスト
"""

import asyncio
from mcp_agent import MCPAgent

async def test_syntax_error():
    """構文エラーのテストを実行"""
    agent = MCPAgent()
    
    try:
        # エージェントを初期化
        await agent.initialize()
        
        print("=== 構文エラーリトライテスト開始 ===")
        
        print("\n1. セミコロン記法でフィボナッチ数列を要求")
        response = await agent.process_request("def fibonacci(n): a, b = 0, 1; result = []; for i in range(n): result.append(a); a, b = b, a + b; return result; print(fibonacci(10))をPythonで実行して")
        print(f"結果: {response}")
        
        print("=== テスト完了 ===")
        
    except Exception as e:
        print(f"テストエラー: {e}")

if __name__ == "__main__":
    asyncio.run(test_syntax_error())