#!/usr/bin/env python3
"""
修正版の会話記憶テスト（シンプルバージョン）
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

load_dotenv()

from integrated_mcp_agent import IntegratedMCPAgent

async def test_simple_memory():
    """シンプルな会話記憶テスト"""
    
    print("\n" + "=" * 70)
    print(" シンプル会話記憶テスト")
    print("=" * 70)
    
    # テスト用のセッションファイル
    test_session_file = "test_session_simple.json"
    
    # 既存のセッションファイルを削除
    if Path(test_session_file).exists():
        os.remove(test_session_file)
    
    # Phase 1: エージェント1で会話
    print("\n[Phase 1] 会話の記録")
    print("-" * 40)
    
    agent1 = IntegratedMCPAgent(
        use_ai=True,
        enable_learning=True,
        verbose=False
    )
    
    await agent1.initialize()
    
    # 会話を実行
    conversations = [
        ("君の名前はガーコです", "名前設定"),
        ("100と200を足して", "計算")
    ]
    
    for query, desc in conversations:
        print(f"\n[{desc}] {query}")
        result = await agent1.process_request(query, interpret_result=False)
        response = str(result['result'])
        print(f"応答: {response[:50]}{'...' if len(response) > 50 else ''}")
    
    # セッションを保存
    agent1.save_session(test_session_file)
    print(f"\n会話履歴: {len(agent1.conversation_history)}件を保存")
    
    await agent1.cleanup()
    
    # Phase 2: エージェント2で復元
    print("\n[Phase 2] セッションの復元")
    print("-" * 40)
    
    agent2 = IntegratedMCPAgent(
        use_ai=True,
        enable_learning=True,
        verbose=False
    )
    
    await agent2.initialize()
    
    # セッションを読み込み
    agent2.load_session(test_session_file)
    print(f"会話履歴: {len(agent2.conversation_history)}件を復元")
    
    # 記憶を確認
    tests = [
        ("君の名前は？", "エージェント名確認"),
        ("さっきの計算結果は？", "計算結果確認")
    ]
    
    for query, desc in tests:
        print(f"\n[{desc}] {query}")
        result = await agent2.process_request(query, interpret_result=False)
        print(f"応答: {result['result']}")
    
    # 会話履歴を表示
    print("\n[会話履歴の内容]")
    print("-" * 40)
    for i, entry in enumerate(agent2.conversation_history[-5:], 1):
        role = "U" if entry["role"] == "user" else "A"
        msg = entry["message"][:40] + "..." if len(entry["message"]) > 40 else entry["message"]
        print(f"{i}. [{role}] {msg}")
    
    await agent2.cleanup()
    
    # クリーンアップ
    if Path(test_session_file).exists():
        os.remove(test_session_file)
    
    print("\n" + "=" * 70)
    print(" テスト完了")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(test_simple_memory())