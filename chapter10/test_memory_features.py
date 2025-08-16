#!/usr/bin/env python3
"""
会話記憶機能のテスト
エージェントが前の会話を覚えているか確認
"""

import asyncio
import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

# .envファイルから環境変数を読み込む
load_dotenv()

from integrated_mcp_agent import IntegratedMCPAgent

async def test_conversation_memory():
    """シンプル化された会話履歴機能のテスト"""
    
    print("\n" + "=" * 70)
    print(" 会話記憶機能テスト")
    print("=" * 70)
    
    # テスト用のセッションファイル
    test_session_file = "test_memory_session.json"
    
    # 既存のセッションファイルを削除
    if Path(test_session_file).exists():
        os.remove(test_session_file)
    
    # エージェントの初期化
    agent = IntegratedMCPAgent(
        use_ai=True,
        enable_learning=True,
        verbose=True
    )
    
    await agent.initialize()
    
    print("\n[テスト1] 名前の設定と記憶")
    print("-" * 40)
    
    # エージェント名を設定
    await agent.process_request("君の名前はガーコです")
    
    # 名前を確認
    result = await agent.process_request("君の名前を言ってみて", interpret_result=False)
    print(f"\n応答: {result['result']}")
    
    print("\n[テスト2] 計算結果の記憶")
    print("-" * 40)
    
    # 計算を実行
    await agent.process_request("100と200を足して")
    
    # 前の結果を参照
    result = await agent.process_request("さっきの計算結果は何だった？", interpret_result=False)
    print(f"\n応答: {result['result']}")
    
    print("\n[テスト3] セッションの保存と復元")
    print("-" * 40)
    
    # セッションを保存
    agent.save_session(test_session_file)
    
    # クリーンアップ
    await agent.cleanup()
    
    print("\n新しいエージェントインスタンスで復元...")
    
    # 新しいエージェントインスタンス
    new_agent = IntegratedMCPAgent(
        use_ai=True,
        enable_learning=True,
        verbose=False  # 簡潔な出力
    )
    
    await new_agent.initialize()
    
    # セッションを読み込み
    new_agent.load_session(test_session_file)
    
    # 記憶が復元されているか確認
    print("\n記憶の確認:")
    
    # エージェント名を確認
    result = await new_agent.process_request("君の名前は？", interpret_result=False)
    print(f"  名前の記憶: {result['result']}")
    
    # 前の計算結果を確認（会話履歴から）
    result = await new_agent.process_request("さっきの計算結果は？", interpret_result=False)
    print(f"  計算結果の記憶: {result['result']}")
    
    await new_agent.cleanup()
    
    # テストファイルをクリーンアップ
    if Path(test_session_file).exists():
        os.remove(test_session_file)
    
    print("\n" + "=" * 70)
    print(" テスト完了")
    print("=" * 70)

async def test_context_aware_conversation():
    """文脈を考慮した会話のテスト"""
    
    print("\n" + "=" * 70)
    print(" 文脈認識テスト")
    print("=" * 70)
    
    agent = IntegratedMCPAgent(
        use_ai=True,
        enable_learning=True,
        verbose=False
    )
    
    await agent.initialize()
    
    # 会話のシナリオ
    conversation = [
        ("私の名前は太郎です", "名前の設定"),
        ("こんにちは", "挨拶"),
        ("100と200を足してください", "計算依頼"),
        ("ありがとう", "感謝"),
        ("私の名前を覚えてる？", "名前の確認"),
        ("さっきの計算結果をもう一度教えて", "結果の確認")
    ]
    
    print("\n[文脈を考慮した会話]")
    print("-" * 40)
    
    for query, description in conversation:
        print(f"\n【{description}】")
        print(f"ユーザー: {query}")
        
        result = await agent.process_request(query, interpret_result=False)
        
        if result["success"]:
            print(f"エージェント: {result['result']}")
        else:
            print(f"エラー: {result['error']}")
    
    # 会話履歴の状態を表示
    print("\n\n[会話履歴の状態]")
    print("-" * 40)
    
    history = agent.conversation_history
    
    if history:
        print(f"  会話履歴: {len(history)}件")
        print("\n  最近の会話:")
        for entry in history[-5:]:
            role = "ユーザー" if entry["role"] == "user" else "エージェント"
            msg = entry["message"][:50] + "..." if len(entry["message"]) > 50 else entry["message"]
            print(f"    [{role}] {msg}")
    
    await agent.cleanup()
    
    print("\n" + "=" * 70)
    print(" テスト完了")
    print("=" * 70)

async def test_memory_persistence():
    """記憶の永続性テスト"""
    
    print("\n" + "=" * 70)
    print(" 記憶永続性テスト")
    print("=" * 70)
    
    session_file = "persistent_memory_test.json"
    
    # Phase 1: 情報を設定
    print("\n[Phase 1] 情報の設定")
    print("-" * 40)
    
    agent1 = IntegratedMCPAgent(use_ai=True, verbose=False)
    await agent1.initialize()
    
    # 複数の情報を設定
    await agent1.process_request("君の名前はアシスタントAIです")
    await agent1.process_request("私の名前は山田太郎です")
    await agent1.process_request("1000と2000を足して")
    await agent1.process_request("その結果を2で割って")
    
    # セッションを保存
    agent1.save_session(session_file)
    await agent1.cleanup()
    
    print("セッションを保存しました")
    
    # Phase 2: 別のインスタンスで復元
    print("\n[Phase 2] 別インスタンスでの復元")
    print("-" * 40)
    
    agent2 = IntegratedMCPAgent(use_ai=True, verbose=False)
    await agent2.initialize()
    
    # セッションを読み込み
    agent2.load_session(session_file)
    
    # 記憶を確認
    queries = [
        "君の名前は何？",
        "私の名前を覚えてる？",
        "前に計算した結果を教えて"
    ]
    
    for query in queries:
        print(f"\nQ: {query}")
        result = await agent2.process_request(query, interpret_result=False)
        print(f"A: {result['result']}")
    
    await agent2.cleanup()
    
    # クリーンアップ
    if Path(session_file).exists():
        os.remove(session_file)
    
    print("\n" + "=" * 70)
    print(" テスト完了")
    print("=" * 70)

if __name__ == "__main__":
    # 基本的な記憶機能テスト
    asyncio.run(test_conversation_memory())
    
    # 文脈を考慮した会話テスト
    asyncio.run(test_context_aware_conversation())
    
    # 記憶の永続性テスト
    asyncio.run(test_memory_persistence())