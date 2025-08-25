#!/usr/bin/env python3
"""
MCPエージェントの簡単なテスト
タスクマネージャーとエラーハンドラーの統合動作を確認
"""

import asyncio
import sys
import os

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

from mcp_agent import MCPAgent

async def test_basic_agent():
    """基本的なエージェント機能のテスト"""
    print("=" * 60)
    print("MCPエージェント基本テスト")
    print("=" * 60)
    
    agent = MCPAgent(verbose=True)
    
    # 初期化
    print("\n[1] エージェントの初期化")
    await agent.initialize()
    
    # 簡単なクエリのテスト
    print("\n[2] 簡単なクエリのテスト")
    test_queries = [
        "こんにちは",
        "今何ができますか？",
        "利用可能なツールを教えて"
    ]
    
    for query in test_queries:
        print(f"\nユーザー: {query}")
        response = await agent.process_query(query)
        print(f"エージェント: {response[:200]}...")  # 最初の200文字だけ表示
    
    # 統計表示
    print("\n[3] セッション統計")
    print(f"- ツール呼び出し: {agent.context['tool_calls']}回")
    print(f"- タスク完了: {agent.context['tasks_completed']}個")
    print(f"- エラー発生: {agent.error_handler.error_stats['total']}回")
    
    # クリーンアップ
    await agent.cleanup()
    
    print("\n基本テスト完了")
    return True

async def test_task_decomposition():
    """タスク分解機能のテスト"""
    print("\n" + "=" * 60)
    print("タスク分解機能のテスト")
    print("=" * 60)
    
    agent = MCPAgent(verbose=True)
    await agent.initialize()
    
    # 複雑なクエリ
    complex_query = "データを取得して、処理して、結果を保存してください"
    
    print(f"\n複雑なクエリ: {complex_query}")
    response = await agent.process_query(complex_query)
    print(f"結果: {response}")
    
    # タスクマネージャーのレポート
    print("\n" + agent.task_manager.get_report())
    
    await agent.cleanup()
    print("\nタスク分解テスト完了")
    return True

async def test_error_handling():
    """エラーハンドリングのテスト"""
    print("\n" + "=" * 60)
    print("エラーハンドリング機能のテスト")
    print("=" * 60)
    
    agent = MCPAgent(verbose=True)
    await agent.initialize()
    
    # エラーを発生させそうなクエリ
    error_queries = [
        "存在しないツールを実行して",
        "接続できないサーバーにアクセスして"
    ]
    
    for query in error_queries:
        print(f"\nエラーテスト: {query}")
        try:
            response = await agent.process_query(query)
            print(f"結果: {response}")
        except Exception as e:
            print(f"エラー: {e}")
    
    # エラーハンドラーのレポート
    print("\n" + agent.error_handler.get_report())
    
    await agent.cleanup()
    print("\nエラーハンドリングテスト完了")
    return True

async def main():
    """メインテスト実行"""
    print("MCPエージェント統合テスト開始\n")
    
    tests = [
        ("基本機能", test_basic_agent),
        ("タスク分解", test_task_decomposition),
        ("エラーハンドリング", test_error_handling)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            print(f"\n実行中: {test_name}")
            success = await test_func()
            results.append((test_name, "成功" if success else "失敗"))
        except Exception as e:
            print(f"テスト失敗: {e}")
            results.append((test_name, f"エラー: {e}"))
    
    # 結果サマリ
    print("\n" + "=" * 60)
    print("テスト結果サマリ")
    print("=" * 60)
    for test_name, result in results:
        print(f"- {test_name}: {result}")
    
    print("\nすべてのテストが完了しました")

if __name__ == "__main__":
    # テスト実行
    asyncio.run(main())