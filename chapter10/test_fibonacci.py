#!/usr/bin/env python3
"""
フィボナッチ数列テスト - AGENT.md改善効果の検証
"""

import asyncio
from mcp_agent import MCPAgent

async def test_fibonacci():
    """フィボナッチ数列生成でAGENT.md改善効果をテスト"""
    print("AGENT.md改善効果テスト: フィボナッチ数列")
    print("=" * 50)
    
    agent = MCPAgent()
    await agent.initialize()
    
    # フィボナッチ数列リクエスト
    query = "フィボナッチ数列を10個表示してください"
    print(f"リクエスト: {query}")
    print("-" * 30)
    
    try:
        result = await agent.process_query(query)
        print(f"結果: {result}")
        
        # AGENT.mdの効果を確認
        # print()文が含まれていることを期待
        if "print(" in result or "結果:" in result:
            print("\n[SUCCESS] AGENT.mdの改善が機能しています!")
            print("- コードにprint()文が含まれている、または結果が表示されている")
        else:
            print("\n[WARNING] AGENT.mdの改善効果が不十分かもしれません")
            
    except Exception as e:
        print(f"エラー: {e}")
        # エラー統計を表示
        stats = agent.error_handler.get_error_statistics()
        print(f"エラー統計: {stats}")
    
    await agent.close()

if __name__ == "__main__":
    asyncio.run(test_fibonacci())