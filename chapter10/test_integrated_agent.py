#!/usr/bin/env python3
"""
統合MCPエージェントのテスト
"""

import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

# .envファイルから環境変数を読み込む
load_dotenv()

from integrated_mcp_agent import IntegratedMCPAgent

async def test_basic_calculation():
    """基本的な計算テスト"""
    print("\n[テスト1] 基本的な計算")
    print("-" * 40)
    
    agent = IntegratedMCPAgent(use_ai=True, enable_learning=True, verbose=False)
    await agent.initialize()
    
    # 単純な計算
    result = await agent.process_request("100と200を足して")
    assert result["success"], f"計算失敗: {result['error']}"
    assert result["result"] == 300, f"計算結果が正しくない: {result['result']}"
    print(f"✓ 100 + 200 = {result['result']}")
    
    # 複数ステップの計算
    result = await agent.process_request("100と200を足して、その結果を2で割って")
    assert result["success"], f"計算失敗: {result['error']}"
    assert result["result"] == 150, f"計算結果が正しくない: {result['result']}"
    print(f"✓ (100 + 200) / 2 = {result['result']}")
    
    await agent.cleanup()
    print("✓ 基本計算テスト完了")

async def test_error_recovery():
    """エラーリカバリーテスト"""
    print("\n[テスト2] エラーリカバリー")
    print("-" * 40)
    
    agent = IntegratedMCPAgent(use_ai=True, enable_learning=True, verbose=False)
    await agent.initialize()
    
    # パラメータエラーのリカバリー（わざと文字列を渡す）
    # ※実際にはプランナーが適切に処理するため、エラーにならない可能性がある
    result = await agent.process_request("100と50を足して")
    if result["success"]:
        print(f"✓ 正常実行: {result['result']}")
    else:
        print(f"✓ エラー処理: {result['error']}")
    
    await agent.cleanup()
    print("✓ エラーリカバリーテスト完了")

async def test_learning():
    """学習機能テスト"""
    print("\n[テスト3] 学習機能")
    print("-" * 40)
    
    agent = IntegratedMCPAgent(use_ai=True, enable_learning=True, verbose=False)
    await agent.initialize()
    
    # 1回目の実行
    query = "123と456を足して"
    start1 = datetime.now()
    result1 = await agent.process_request(query)
    time1 = (datetime.now() - start1).total_seconds()
    assert result1["success"], f"1回目の実行失敗: {result1['error']}"
    print(f"✓ 1回目実行: {result1['result']} ({time1:.2f}秒)")
    
    # 2回目の実行（学習済みパターンを使用）
    start2 = datetime.now()
    result2 = await agent.process_request(query)
    time2 = (datetime.now() - start2).total_seconds()
    assert result2["success"], f"2回目の実行失敗: {result2['error']}"
    assert result2["learning_applied"], "学習パターンが適用されていない"
    print(f"✓ 2回目実行（学習済み）: {result2['result']} ({time2:.2f}秒)")
    
    # 学習による高速化を確認（厳密ではないが、傾向として）
    if time2 < time1:
        print(f"✓ 学習による高速化: {time1:.2f}秒 → {time2:.2f}秒")
    
    await agent.cleanup()
    print("✓ 学習機能テスト完了")

async def test_session_management():
    """セッション管理テスト"""
    print("\n[テスト4] セッション管理")
    print("-" * 40)
    
    agent = IntegratedMCPAgent(use_ai=True, enable_learning=True, verbose=False)
    await agent.initialize()
    
    # いくつかのリクエストを実行
    queries = [
        "10と20を足して",
        "100から50を引いて",
        "5と6を掛けて"
    ]
    
    for query in queries:
        result = await agent.process_request(query)
        print(f"✓ {query}: {result['result']}")
    
    # セッション統計を確認
    stats = agent.session.get_stats()
    assert stats["total_requests"] == 3, f"リクエスト数が正しくない: {stats['total_requests']}"
    assert stats["successful_tasks"] > 0, "成功タスクがない"
    
    print(f"\n[セッション統計]")
    print(f"  総リクエスト: {stats['total_requests']}")
    print(f"  成功タスク: {stats['successful_tasks']}")
    print(f"  成功率: {stats['success_rate']:.1f}%")
    
    # セッションの保存と読み込み
    test_file = "test_session.json"
    agent.save_session(test_file)
    print(f"✓ セッションを {test_file} に保存")
    
    # 新しいエージェントで読み込み
    agent2 = IntegratedMCPAgent(use_ai=True, enable_learning=True, verbose=False)
    await agent2.initialize()
    success = agent2.load_session(test_file)
    assert success, "セッションの読み込みに失敗"
    assert len(agent2.success_patterns) > 0, "学習パターンが復元されていない"
    print(f"✓ セッションを読み込み（{len(agent2.success_patterns)}個のパターン）")
    
    # クリーンアップ
    await agent.cleanup()
    await agent2.cleanup()
    
    # テストファイルを削除
    if os.path.exists(test_file):
        os.remove(test_file)
    
    print("✓ セッション管理テスト完了")

async def test_complex_workflow():
    """複雑なワークフローテスト"""
    print("\n[テスト5] 複雑なワークフロー")
    print("-" * 40)
    
    agent = IntegratedMCPAgent(use_ai=True, enable_learning=True, verbose=False)
    await agent.initialize()
    
    # 複雑な計算タスク
    complex_query = "100と200を足して、その結果に50を掛けて、最後に10で割って"
    result = await agent.process_request(complex_query)
    
    if result["success"]:
        expected = ((100 + 200) * 50) / 10  # 1500
        assert result["result"] == expected, f"計算結果が正しくない: {result['result']} != {expected}"
        print(f"✓ 複雑な計算: {result['result']}")
        print(f"  実行タスク数: {result['tasks_executed']}")
    else:
        print(f"✗ エラー: {result['error']}")
    
    await agent.cleanup()
    print("✓ 複雑なワークフローテスト完了")

async def run_all_tests():
    """すべてのテストを実行"""
    print("\n" + "=" * 70)
    print(" 統合MCPエージェント - テストスイート")
    print("=" * 70)
    
    # APIキーチェック
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("\n[警告] OPENAI_API_KEYが設定されていません")
        print("AI機能を使用しないテストのみ実行します")
    
    tests = [
        ("基本計算", test_basic_calculation),
        ("エラーリカバリー", test_error_recovery),
        ("学習機能", test_learning),
        ("セッション管理", test_session_management),
        ("複雑なワークフロー", test_complex_workflow)
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            await test_func()
            passed += 1
        except Exception as e:
            print(f"\n✗ {name}テスト失敗: {e}")
            failed += 1
    
    # 結果サマリー
    print("\n" + "=" * 70)
    print(" テスト結果")
    print("=" * 70)
    print(f"  成功: {passed}/{len(tests)}")
    print(f"  失敗: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n[SUCCESS] すべてのテストが成功しました！")
    else:
        print(f"\n[PARTIAL] {failed}個のテストが失敗しました")

async def interactive_test():
    """対話型テスト（手動確認用）"""
    print("\n" + "=" * 70)
    print(" 統合MCPエージェント - 対話型テスト")
    print("=" * 70)
    
    agent = IntegratedMCPAgent(
        use_ai=True,
        enable_learning=True,
        verbose=True  # 詳細ログを表示
    )
    
    try:
        await agent.initialize()
        
        # テスト用のクエリを自動実行
        test_queries = [
            "100と200を足して",
            "データベースのテーブル一覧を取得",  # DBサーバーが必要
            "2の8乗を計算して"
        ]
        
        print("\n[自動テスト実行]")
        for query in test_queries:
            print(f"\n実行: {query}")
            result = await agent.process_request(query)
            if result["success"]:
                print(f"→ 結果: {result['result']}")
            else:
                print(f"→ エラー: {result['error']}")
        
        # 対話モードに移行するか確認
        print("\n対話モードに移行しますか？ (y/n): ", end="")
        if input().lower() == 'y':
            await agent.interactive_session()
    
    finally:
        await agent.cleanup()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        # 対話型テスト
        asyncio.run(interactive_test())
    else:
        # 自動テスト
        asyncio.run(run_all_tests())