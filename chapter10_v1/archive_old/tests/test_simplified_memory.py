#!/usr/bin/env python3
"""
シンプル化された会話履歴機能のテスト
LLMが会話の文脈を自然に理解できるか確認
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

async def test_natural_conversation():
    """自然な会話の流れをテスト"""
    
    print("\n" + "=" * 70)
    print(" 自然な会話テスト")
    print("=" * 70)
    
    agent = IntegratedMCPAgent(
        use_ai=True,
        enable_learning=True,
        verbose=False
    )
    
    await agent.initialize()
    
    # さまざまなパターンの会話
    conversations = [
        # 自己紹介のパターン
        ("俺サトシっていうんだ", "名前の自然な紹介"),
        ("君の名前はガーコでお願い", "エージェント名の設定"),
        ("こんにちは！", "挨拶"),
        
        # 計算と参照
        ("100と200を足してくれる？", "計算依頼"),
        ("ありがとう！", "感謝"),
        ("さっきの結果なんだっけ？", "前の結果を参照"),
        
        # 名前の確認
        ("俺の名前覚えてる？", "ユーザー名の確認"),
        ("君の名前は？", "エージェント名の確認"),
        
        # 複数の計算と参照
        ("じゃあその結果を2で割って", "前の結果を使った計算"),
        ("今までの計算を振り返ると？", "会話の要約")
    ]
    
    print("\n[自然な会話の流れ]")
    print("-" * 40)
    
    for query, description in conversations:
        print(f"\n【{description}】")
        print(f"ユーザー: {query}")
        
        result = await agent.process_request(query, interpret_result=True)
        
        if result["success"]:
            # 解釈があればそれを、なければ結果を表示
            response = result.get("interpretation", result["result"])
            print(f"エージェント: {response}")
        else:
            print(f"エラー: {result['error']}")
    
    # 会話履歴の確認
    print("\n\n[会話履歴の状態]")
    print("-" * 40)
    print(f"保存された会話数: {len(agent.conversation_history)}件")
    
    # 最後の5件を表示
    if agent.conversation_history:
        print("\n最近の会話:")
        for entry in agent.conversation_history[-5:]:
            role = "U" if entry["role"] == "user" else "A"
            msg = entry["message"][:50] + "..." if len(entry["message"]) > 50 else entry["message"]
            print(f"  [{role}] {msg}")
    
    await agent.cleanup()
    
    print("\n" + "=" * 70)
    print(" テスト完了")
    print("=" * 70)

async def test_context_understanding():
    """文脈理解のテスト"""
    
    print("\n" + "=" * 70)
    print(" 文脈理解テスト")
    print("=" * 70)
    
    agent = IntegratedMCPAgent(
        use_ai=True,
        enable_learning=True,
        verbose=False
    )
    
    await agent.initialize()
    
    # 文脈を必要とする会話
    context_tests = [
        ("私は山田太郎と申します", "フォーマルな自己紹介"),
        ("東京に住んでいます", "場所の情報"),
        ("趣味はプログラミングです", "趣味の情報"),
        ("1000円持っています", "所持金の情報"),
        ("コーヒーを3杯買いたいんだけど、1杯300円だといくら？", "計算依頼"),
        ("お金は足りる？", "文脈を考慮した質問"),
        ("私について何を知ってる？", "記憶の確認")
    ]
    
    print("\n[文脈を考慮した対話]")
    print("-" * 40)
    
    for query, description in context_tests:
        print(f"\n【{description}】")
        print(f"ユーザー: {query}")
        
        result = await agent.process_request(query, interpret_result=False)
        
        if result["success"]:
            print(f"エージェント: {result['result']}")
    
    await agent.cleanup()
    
    print("\n" + "=" * 70)
    print(" テスト完了")
    print("=" * 70)

async def test_session_persistence():
    """セッションの永続性テスト"""
    
    print("\n" + "=" * 70)
    print(" セッション永続性テスト")
    print("=" * 70)
    
    session_file = "test_simplified_session.json"
    
    # Phase 1: 会話を記録
    print("\n[Phase 1] 会話の記録")
    print("-" * 40)
    
    agent1 = IntegratedMCPAgent(use_ai=True, verbose=False)
    await agent1.initialize()
    
    initial_conversations = [
        "私の名前は鈴木です",
        "君の名前はアシスタントAIにするよ",
        "500と700を足して",
        "結果を覚えておいて"
    ]
    
    for query in initial_conversations:
        print(f"ユーザー: {query}")
        result = await agent1.process_request(query, interpret_result=False)
        if result["success"]:
            print(f"エージェント: {result['result'][:80]}...")
    
    # セッションを保存
    agent1.save_session(session_file)
    history_count = len(agent1.conversation_history)
    await agent1.cleanup()
    
    print(f"\n{history_count}件の会話を保存しました")
    
    # Phase 2: 別のインスタンスで復元
    print("\n[Phase 2] セッションの復元")
    print("-" * 40)
    
    agent2 = IntegratedMCPAgent(use_ai=True, verbose=False)
    await agent2.initialize()
    
    # セッションを読み込み
    agent2.load_session(session_file)
    
    # 文脈を理解しているか確認
    test_queries = [
        "私の名前を覚えてる？",
        "君の名前は？",
        "さっき計算した結果は？"
    ]
    
    for query in test_queries:
        print(f"\nユーザー: {query}")
        result = await agent2.process_request(query, interpret_result=False)
        print(f"エージェント: {result['result']}")
    
    await agent2.cleanup()
    
    # クリーンアップ
    if Path(session_file).exists():
        os.remove(session_file)
    
    print("\n" + "=" * 70)
    print(" テスト完了")
    print("=" * 70)

async def test_various_name_patterns():
    """さまざまな名前の言い方をテスト"""
    
    print("\n" + "=" * 70)
    print(" 多様な表現パターンテスト")
    print("=" * 70)
    
    agent = IntegratedMCPAgent(use_ai=True, verbose=False)
    await agent.initialize()
    
    # さまざまな自己紹介パターン
    patterns = [
        "僕、健太っていいます",
        "私、花子よ",
        "俺の名前？ジョンだよ",
        "田中と申します",
        "あ、私マリアです",
        "名前は太郎",
        "呼んでもらうときは「社長」でお願い"
    ]
    
    print("\n[多様な自己紹介への対応]")
    print("-" * 40)
    
    for i, pattern in enumerate(patterns):
        # 新しいエージェントで各パターンをテスト
        agent = IntegratedMCPAgent(use_ai=True, verbose=False)
        await agent.initialize()
        
        print(f"\nテスト{i+1}: {pattern}")
        await agent.process_request(pattern, interpret_result=False)
        
        # 名前を覚えているか確認
        result = await agent.process_request("私のこと何て呼ぶ？", interpret_result=False)
        print(f"応答: {result['result']}")
        
        await agent.cleanup()
    
    print("\n" + "=" * 70)
    print(" テスト完了")
    print("=" * 70)

if __name__ == "__main__":
    # 基本的な自然な会話テスト
    asyncio.run(test_natural_conversation())
    
    # 文脈理解テスト
    asyncio.run(test_context_understanding())
    
    # セッション永続性テスト
    asyncio.run(test_session_persistence())
    
    # 多様な表現パターンテスト
    asyncio.run(test_various_name_patterns())