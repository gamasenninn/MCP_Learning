#!/usr/bin/env python3
"""
基本的なエージェントのデモ
第10章の実践例
"""

import asyncio
import os
import sys

# 親ディレクトリをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from practical_mcp_agent import PracticalMCPAgent

async def basic_demo():
    """基本的なデモ"""
    print("="*60)
    print("MCPエージェント - 基本デモ")
    print("="*60)
    
    # エージェントを初期化
    agent = PracticalMCPAgent()
    await agent.initialize()
    
    # デモタスクのリスト
    demo_tasks = [
        "55と45を足してください",
        "100を3で割って、その結果を2倍にしてください",
        "1から10までの数字を合計してください"
    ]
    
    for i, task in enumerate(demo_tasks, 1):
        print(f"\n[デモ {i}]")
        result = await agent.execute(task, auto_approve=True)
        print(f"結果: {result['result']}")
        print("-"*40)

async def planning_demo():
    """タスクプランニングのデモ"""
    print("="*60)
    print("MCPエージェント - タスクプランニングデモ")
    print("="*60)
    
    agent = PracticalMCPAgent()
    await agent.initialize()
    
    # 複雑なタスク
    complex_task = """
    以下の処理を順番に実行してください：
    1. データファイルを読み込む
    2. データを分析する
    3. レポートを生成する
    4. 結果を保存する
    """
    
    print("\n[タスク]")
    print(complex_task)
    
    # 計画を作成して表示（自動承認はしない）
    result = await agent.execute(complex_task, auto_approve=False)
    
    if result['status'] != 'cancelled':
        print(f"\n[完了]")
        print(f"ステータス: {result['status']}")
        print(f"完了ステップ: {result['completed_steps']}/{result['total_steps']}")

async def error_handling_demo():
    """エラーハンドリングのデモ"""
    print("="*60)
    print("MCPエージェント - エラーハンドリングデモ")
    print("="*60)
    
    agent = PracticalMCPAgent()
    await agent.initialize()
    
    # エラーが起きそうなタスク
    error_prone_task = "存在しないファイル 'missing_data.csv' を読み込んで分析してください"
    
    print(f"\n[タスク] {error_prone_task}")
    print("\n※ エラーが発生しますが、リトライ機能が動作します")
    
    result = await agent.execute(error_prone_task, auto_approve=True)
    
    print(f"\n[結果]")
    print(f"ステータス: {result['status']}")
    print(f"メッセージ: {result['result']}")

async def interactive_demo():
    """対話型デモ"""
    agent = PracticalMCPAgent()
    await agent.initialize()
    await agent.interactive_session()

def main():
    """メインメニュー"""
    print("\n" + "="*60)
    print("第10章 MCPエージェント デモプログラム")
    print("="*60)
    print("\n利用可能なデモ:")
    print("  1. 基本デモ（簡単な計算タスク）")
    print("  2. プランニングデモ（複雑なタスクの計画）")
    print("  3. エラーハンドリングデモ（エラー処理）")
    print("  4. 対話モード（インタラクティブ）")
    print("  0. 終了")
    
    while True:
        print("\n選択してください (0-4): ", end="")
        choice = input().strip()
        
        if choice == "0":
            print("終了します")
            break
        elif choice == "1":
            asyncio.run(basic_demo())
        elif choice == "2":
            asyncio.run(planning_demo())
        elif choice == "3":
            asyncio.run(error_handling_demo())
        elif choice == "4":
            asyncio.run(interactive_demo())
        else:
            print("無効な選択です")

if __name__ == "__main__":
    main()