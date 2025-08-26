#!/usr/bin/env python3
"""
cleanup() メソッドがないエラーを修正するテストファイル
"""

import asyncio
from mcp_agent import MCPAgent

async def test_simple():
    """簡単なテスト"""
    
    # エージェント初期化
    agent = MCPAgent('config.yaml')
    await agent.initialize()
    
    print("=== LLM完全信頼テスト ===")
    
    result = await agent.process_request("calculate 100 + 200, then multiply by 2")
    print(f"結果: {result}")
    
    print("=== テスト完了 ===")
    
    # cleanup()を呼び出さずに終了

if __name__ == "__main__":
    asyncio.run(test_simple())