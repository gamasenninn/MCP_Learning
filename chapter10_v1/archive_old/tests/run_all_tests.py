#!/usr/bin/env python3
"""
第10章 全テスト実行スクリプト
すべてのテストを順番に実行
"""

import asyncio
import os
import sys
import time

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

# 各テストモジュールをインポート
from test_planner import test_planner
from test_executor import test_executor
from test_integration import test_integration

async def run_all_tests():
    """全テストを実行"""
    print("=" * 70)
    print(" 第10章 MCPエージェント - 全テスト実行")
    print("=" * 70)
    
    # 全体の開始時間
    total_start = time.time()
    
    # 結果を格納
    results = []
    
    # 1. プランナーテスト
    print("\n" + "=" * 70)
    print(" [1/3] タスクプランナーテスト")
    print("=" * 70)
    try:
        passed, failed = await test_planner()
        results.append(("プランナー", passed, failed))
    except Exception as e:
        print(f"エラー: {e}")
        results.append(("プランナー", 0, -1))
    
    # 少し待機（サーバーの安定化のため）
    await asyncio.sleep(1)
    
    # 2. エグゼキューターテスト
    print("\n" + "=" * 70)
    print(" [2/3] タスク実行エンジンテスト")
    print("=" * 70)
    try:
        passed, failed = await test_executor()
        results.append(("エグゼキューター", passed, failed))
    except Exception as e:
        print(f"エラー: {e}")
        results.append(("エグゼキューター", 0, -1))
    
    # 少し待機
    await asyncio.sleep(1)
    
    # 3. 統合テスト
    print("\n" + "=" * 70)
    print(" [3/3] 統合テスト")
    print("=" * 70)
    try:
        passed, failed = await test_integration()
        results.append(("統合", passed, failed))
    except Exception as e:
        print(f"エラー: {e}")
        results.append(("統合", 0, -1))
    
    # 全体の実行時間
    total_time = time.time() - total_start
    
    # 最終サマリ
    print("\n" + "=" * 70)
    print(" 全テスト結果サマリ")
    print("=" * 70)
    
    total_passed = 0
    total_failed = 0
    
    for test_name, passed, failed in results:
        if failed == -1:
            print(f"  {test_name:20s}: エラー発生")
        else:
            print(f"  {test_name:20s}: 成功 {passed:3d}, 失敗 {failed:3d}")
            total_passed += passed
            total_failed += failed
    
    print("-" * 70)
    print(f"  {'合計':20s}: 成功 {total_passed:3d}, 失敗 {total_failed:3d}")
    
    # 成功率
    total_tests = total_passed + total_failed
    if total_tests > 0:
        success_rate = (total_passed / total_tests) * 100
        print(f"  {'成功率':20s}: {success_rate:.1f}%")
    
    print(f"  {'総実行時間':20s}: {total_time:.2f}秒")
    
    # 最終判定
    print("\n" + "=" * 70)
    if total_failed == 0:
        print(" [SUCCESS] すべてのテストが成功しました！")
    else:
        print(f" [WARNING] {total_failed}個のテストが失敗しました")
    print("=" * 70)

async def run_specific_test(test_type: str):
    """特定のテストのみ実行"""
    print(f"特定テスト実行: {test_type}")
    print("=" * 60)
    
    if test_type == "planner":
        await test_planner()
    elif test_type == "executor":
        await test_executor()
    elif test_type == "integration":
        await test_integration()
    else:
        print(f"不明なテストタイプ: {test_type}")
        print("使用可能: planner, executor, integration")

def print_usage():
    """使用方法を表示"""
    print("使用方法:")
    print("  python run_all_tests.py          # 全テスト実行")
    print("  python run_all_tests.py planner  # プランナーテストのみ")
    print("  python run_all_tests.py executor # エグゼキューターテストのみ")
    print("  python run_all_tests.py integration # 統合テストのみ")
    print("  python run_all_tests.py --help   # ヘルプ表示")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--help" or arg == "-h":
            print_usage()
        else:
            # 特定のテストを実行
            asyncio.run(run_specific_test(arg))
    else:
        # 全テストを実行
        asyncio.run(run_all_tests())