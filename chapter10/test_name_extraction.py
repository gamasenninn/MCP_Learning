#!/usr/bin/env python3
"""
名前抽出機能のテスト
さまざまなパターンで名前を正しく抽出できるか確認
"""

import re
import asyncio
import os
import sys
from dotenv import load_dotenv

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

load_dotenv()

def test_name_patterns():
    """名前抽出パターンのテスト"""
    
    print("\n" + "=" * 70)
    print(" 名前抽出パターンテスト")
    print("=" * 70)
    
    # ユーザー名のテストケース
    user_test_cases = [
        ("俺の名前はサトシだよ", "サトシ"),
        ("私の名前は太郎です", "太郎"),
        ("僕の名前は健太だ", "健太"),
        ("俺の名前は山田太郎", "山田太郎"),
        ("私の名前は佐藤花子です", "佐藤花子"),
        ("俺の名前はタロウ", "タロウ"),
    ]
    
    # エージェント名のテストケース
    agent_test_cases = [
        ("君の名前はガーコだよ", "ガーコ"),
        ("あなたの名前はアシスタントです", "アシスタント"),
        ("お前の名前はAIだ", "AI"),
        ("君の名前はヘルパー", "ヘルパー"),
    ]
    
    print("\n[ユーザー名の抽出テスト]")
    print("-" * 40)
    
    # ユーザー名抽出パターン
    user_pattern = r'(?:私の名前は|俺の名前は|僕の名前は)(\S+?)(?:だ|です|よ|$)'
    
    for text, expected in user_test_cases:
        match = re.search(user_pattern, text)
        if match:
            extracted = match.group(1)
            status = "[OK]" if extracted == expected else "[NG]"
            print(f"{status} 入力: '{text}'")
            print(f"   期待値: '{expected}', 抽出値: '{extracted}'")
        else:
            print(f"[NG] 入力: '{text}'")
            print(f"   期待値: '{expected}', 抽出失敗")
    
    print("\n[エージェント名の抽出テスト]")
    print("-" * 40)
    
    # エージェント名抽出パターン
    agent_pattern = r'(?:君の名前は|あなたの名前は|お前の名前は)(\S+?)(?:だ|です|よ|$)'
    
    for text, expected in agent_test_cases:
        match = re.search(agent_pattern, text)
        if match:
            extracted = match.group(1)
            status = "[OK]" if extracted == expected else "[NG]"
            print(f"{status} 入力: '{text}'")
            print(f"   期待値: '{expected}', 抽出値: '{extracted}'")
        else:
            print(f"[NG] 入力: '{text}'")
            print(f"   期待値: '{expected}', 抽出失敗")

async def test_with_agent():
    """実際のエージェントでテスト"""
    from integrated_mcp_agent import IntegratedMCPAgent
    
    print("\n" + "=" * 70)
    print(" エージェントでの名前記憶テスト")
    print("=" * 70)
    
    agent = IntegratedMCPAgent(
        use_ai=True,
        enable_learning=True,
        verbose=False
    )
    
    await agent.initialize()
    
    # テストケース
    test_inputs = [
        "俺の名前はサトシだよ",
        "君の名前はガーコだ",
        "俺の名前を覚えてる？",
        "君の名前を言ってみて"
    ]
    
    print("\n[対話テスト]")
    print("-" * 40)
    
    for input_text in test_inputs:
        print(f"\nユーザー: {input_text}")
        
        # 名前抽出のテスト（verboseモードで記憶の設定を確認）
        agent.verbose = True if "名前は" in input_text else False
        
        result = await agent.process_request(input_text, interpret_result=False)
        
        if result["success"]:
            print(f"エージェント: {result['result']}")
    
    # 記憶の状態を確認
    print("\n\n[記憶の状態]")
    print("-" * 40)
    print(f"ユーザー名: {agent.conversation_memory.get('user_name', '未設定')}")
    print(f"エージェント名: {agent.conversation_memory.get('agent_name', '未設定')}")
    
    await agent.cleanup()
    
    print("\n" + "=" * 70)
    print(" テスト完了")
    print("=" * 70)

if __name__ == "__main__":
    # パターンテスト
    test_name_patterns()
    
    # エージェントテスト
    asyncio.run(test_with_agent())