#!/usr/bin/env python3
"""
プランナーとエグゼキューターの統合テスト
エンドツーエンドの動作確認
"""

import asyncio
import os
import sys
import time

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

from my_test_cases import INTEGRATION_TESTS
from universal_task_planner import UniversalTaskPlanner
from universal_task_executor import UniversalTaskExecutor

async def test_integration():
    """統合テストの実行"""
    print("統合テスト（エンドツーエンド）")
    print("=" * 60)
    
    # プランナーとエグゼキューターの初期化
    planner = UniversalTaskPlanner()
    executor = UniversalTaskExecutor()
    
    print("\n[初期化中...]")
    start_time = time.time()
    await planner.initialize()
    await executor.connect_all_servers()
    init_time = time.time() - start_time
    print(f"  初期化完了 ({init_time:.2f}秒)")
    
    # テスト結果の統計
    total = len(INTEGRATION_TESTS)
    passed = 0
    failed = 0
    
    # 実行時間の記録
    execution_times = []
    
    print(f"\n{total}個のテストを実行")
    print("-" * 60)
    
    for test_case in INTEGRATION_TESTS:
        # テストケースの解析
        if len(test_case) == 3:
            query, description, expected = test_case
        elif len(test_case) == 2:
            query, description = test_case
            expected = None
        else:
            query = test_case if isinstance(test_case, str) else test_case[0]
            description = "テスト"
            expected = None
        
        print(f"\n[{description}]")
        print(f"  クエリ: {query}")
        
        try:
            # 実行時間を計測
            start_time = time.time()
            
            # タスク分解
            tasks = await planner.plan_task(query)
            
            if not tasks:
                print("  → タスクなし")
                passed += 1
                continue
            
            # タスク実行
            result = await executor.execute_tasks(tasks)
            
            # 実行時間を記録
            exec_time = time.time() - start_time
            execution_times.append(exec_time)
            
            if result["success"]:
                actual = result["final_result"]
                
                # 結果の表示
                if isinstance(actual, str) and len(str(actual)) > 100:
                    print(f"  結果: {str(actual)[:100]}...")
                else:
                    print(f"  結果: {actual}")
                
                print(f"  実行時間: {exec_time:.2f}秒")
                print(f"  タスク数: {result['stats']['total']}")
                
                # 期待値チェック
                if expected is not None:
                    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
                        if abs(actual - expected) < 0.01:
                            print(f"  [OK] 期待値と一致")
                            passed += 1
                        else:
                            print(f"  [NG] 期待{expected}、実際{actual}")
                            failed += 1
                    else:
                        if actual == expected:
                            print(f"  [OK] 期待値と一致")
                            passed += 1
                        else:
                            print(f"  [NG] 期待値と異なる")
                            failed += 1
                else:
                    print(f"  [OK] 実行成功")
                    passed += 1
            else:
                print(f"  [FAIL] 実行失敗")
                failed += 1
                
        except Exception as e:
            print(f"  [ERROR] エラー: {str(e)[:100]}")
            failed += 1
        
        finally:
            # 結果をクリア
            executor.results.clear()
    
    # パフォーマンス統計
    if execution_times:
        avg_time = sum(execution_times) / len(execution_times)
        max_time = max(execution_times)
        min_time = min(execution_times)
    else:
        avg_time = max_time = min_time = 0
    
    # 結果サマリ
    print("\n" + "=" * 60)
    print("テスト結果サマリ")
    print("-" * 60)
    print(f"  総テスト数: {total}")
    print(f"  成功: {passed}")
    print(f"  失敗: {failed}")
    print(f"  成功率: {passed/total*100:.1f}%")
    
    print("\nパフォーマンス")
    print("-" * 60)
    print(f"  平均実行時間: {avg_time:.2f}秒")
    print(f"  最大実行時間: {max_time:.2f}秒")
    print(f"  最小実行時間: {min_time:.2f}秒")
    
    # クリーンアップ
    await executor.cleanup()
    
    return passed, failed

async def test_integration_quick():
    """クイックテスト（最小限のテストのみ）"""
    print("クイック統合テスト")
    print("=" * 60)
    
    planner = UniversalTaskPlanner()
    executor = UniversalTaskExecutor()
    
    await planner.initialize()
    await executor.connect_all_servers()
    
    # 簡単なテストを1つだけ実行
    query = "100 + 200を計算して"
    print(f"\nテスト: {query}")
    
    tasks = await planner.plan_task(query)
    result = await executor.execute_tasks(tasks)
    
    if result["success"]:
        print(f"結果: {result['final_result']}")
        if result['final_result'] == 300:
            print("[OK] テスト成功")
        else:
            print("[NG] 期待値と異なる")
    else:
        print("[FAIL] 実行失敗")
    
    await executor.cleanup()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        # クイックテスト
        asyncio.run(test_integration_quick())
    else:
        # 通常の統合テスト
        asyncio.run(test_integration())