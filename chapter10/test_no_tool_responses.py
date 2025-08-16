#!/usr/bin/env python3
"""
ツール不要な応答のテスト
挨拶、感謝、雑談などに適切に応答できるか確認
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

# .envファイルから環境変数を読み込む
load_dotenv()

from integrated_mcp_agent import IntegratedMCPAgent

async def test_no_tool_responses():
    """ツール不要な応答のテスト"""
    
    print("\n" + "=" * 70)
    print(" ツール不要な応答テスト")
    print("=" * 70)
    
    # エージェントの初期化
    agent = IntegratedMCPAgent(
        use_ai=True,
        enable_learning=True,
        verbose=False  # 簡潔な出力
    )
    
    await agent.initialize()
    
    # テスト用の入力（ツール不要）
    test_queries = [
        "こんにちは",
        "ありがとう",
        "君はすごいね",
        "お疲れさま",
        "今日はいい天気だね",
        "元気？",
        "さようなら"
    ]
    
    print("\n[ツール不要な質問への応答テスト]")
    print("-" * 40)
    
    for query in test_queries:
        print(f"\nユーザー: {query}")
        result = await agent.process_request(query, interpret_result=False)
        
        if result["success"]:
            print(f"エージェント: {result['result']}")
        else:
            print(f"エラー: {result['error']}")
    
    # ツールが必要な質問との比較
    print("\n\n[ツールが必要な質問との比較]")
    print("-" * 40)
    
    tool_queries = [
        "100と200を足して",
        "2の8乗を計算して"
    ]
    
    for query in tool_queries:
        print(f"\nユーザー: {query}")
        result = await agent.process_request(query, interpret_result=True)
        
        if result["success"]:
            if "interpretation" in result:
                print(f"エージェント: {result['interpretation']}")
            else:
                print(f"エージェント: 結果は {result['result']} です")
        else:
            print(f"エラー: {result['error']}")
    
    await agent.cleanup()
    print("\n" + "=" * 70)
    print(" テスト完了")
    print("=" * 70)

async def test_mixed_conversation():
    """混在する会話のテスト"""
    
    print("\n" + "=" * 70)
    print(" 自然な会話フローのテスト")
    print("=" * 70)
    
    agent = IntegratedMCPAgent(
        use_ai=True,
        enable_learning=True,
        verbose=False
    )
    
    await agent.initialize()
    
    # 自然な会話の流れ
    conversation = [
        "こんにちは！",
        "100と200を足してください",
        "ありがとう！助かりました",
        "2の10乗も計算してもらえる？",
        "すごい！君は本当に賢いね",
        "さようなら"
    ]
    
    print("\n[自然な会話]")
    print("-" * 40)
    
    for query in conversation:
        print(f"\nユーザー: {query}")
        result = await agent.process_request(query, interpret_result=True)
        
        if result["success"]:
            if "interpretation" in result:
                print(f"エージェント: {result['interpretation']}")
            else:
                print(f"エージェント: {result['result']}")
    
    # セッション統計
    stats = agent.session.get_stats()
    print("\n\n[セッション統計]")
    print(f"  総リクエスト: {stats['total_requests']}")
    print(f"  成功タスク: {stats['successful_tasks']}")
    print(f"  成功率: {stats['success_rate']:.1f}%")
    
    await agent.cleanup()

if __name__ == "__main__":
    # 基本テスト
    asyncio.run(test_no_tool_responses())
    
    # 自然な会話テスト
    asyncio.run(test_mixed_conversation())