#!/usr/bin/env python3
"""
シンプル化された会話記憶の簡単なテスト
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

load_dotenv()

from integrated_mcp_agent import IntegratedMCPAgent

async def quick_test():
    """基本的な名前記憶テスト"""
    
    print("\n[簡単なテスト]")
    print("-" * 40)
    
    agent = IntegratedMCPAgent(
        use_ai=True,
        enable_learning=True,
        verbose=False
    )
    
    await agent.initialize()
    
    # テスト会話
    tests = [
        "俺の名前はサトシだよ",
        "君の名前はガーコね",
        "100と200を足して",
        "俺の名前覚えてる？",
        "君の名前を言ってみて",
        "さっきの計算結果は？"
    ]
    
    for query in tests:
        print(f"\nユーザー: {query}")
        result = await agent.process_request(query, interpret_result=False)
        if result["success"]:
            print(f"エージェント: {result['result']}")
        else:
            print(f"エラー: {result.get('error', 'Unknown error')}")
    
    # 会話履歴の確認
    print(f"\n\n会話履歴: {len(agent.conversation_history)}件")
    
    await agent.cleanup()
    print("\nテスト完了")

if __name__ == "__main__":
    asyncio.run(quick_test())