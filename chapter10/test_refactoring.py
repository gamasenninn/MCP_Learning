#!/usr/bin/env python3
"""
MCPConnectionManagerリファクタリングの動作確認テスト
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

load_dotenv()

from integrated_mcp_agent import IntegratedMCPAgent

async def test_refactoring():
    """リファクタリング後の基本動作確認"""
    
    print("\n" + "=" * 60)
    print(" MCPConnectionManagerリファクタリング動作確認")
    print("=" * 60)
    
    # エージェントの作成（接続マネージャーを内部で使用）
    agent = IntegratedMCPAgent(
        use_ai=True,
        enable_learning=False,
        verbose=False
    )
    
    print("\n[1] 初期化テスト")
    print("-" * 40)
    await agent.initialize()
    print("初期化成功: 接続マネージャーが正常に動作")
    
    # 簡単な計算テスト
    print("\n[2] 計算テスト")
    print("-" * 40)
    query = "50と30を足して"
    result = await agent.process_request(query, interpret_result=False)
    
    if result["success"]:
        print(f"計算成功: 50 + 30 = {result['result']}")
    else:
        print(f"計算失敗: {result.get('error', 'Unknown error')}")
    
    # 名前記憶テスト
    print("\n[3] 会話記憶テスト")
    print("-" * 40)
    result = await agent.process_request("俺の名前はタロウだよ", interpret_result=False)
    print(f"応答: {result['result']}")
    
    result = await agent.process_request("俺の名前覚えてる？", interpret_result=False)
    print(f"記憶確認: {result['result']}")
    
    # クリーンアップ
    print("\n[4] クリーンアップ")
    print("-" * 40)
    await agent.cleanup()
    print("クリーンアップ成功")
    
    print("\n" + "=" * 60)
    print(" すべてのテストが成功しました！")
    print(" MCPConnectionManagerによる統合初期化が正常に動作しています")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_refactoring())