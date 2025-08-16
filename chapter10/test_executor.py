#!/usr/bin/env python3
"""
タスク実行エンジンの単体テスト
実行結果が正しいかを確認
"""

import asyncio
import os
import sys

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

from my_test_cases import EXECUTOR_TESTS
from universal_task_planner import UniversalTaskPlanner
from universal_task_executor import UniversalTaskExecutor

async def test_executor():
    """エグゼキューターのテスト実行"""
    print("タスク実行エンジン単体テスト")
    print("=" * 60)
    
    # プランナーとエグゼキューターの初期化
    planner = UniversalTaskPlanner()
    executor = UniversalTaskExecutor()
    
    print("\n[初期化中...]")
    await planner.initialize()
    await executor.connect_all_servers()
    
    # テスト結果の統計
    total = len(EXECUTOR_TESTS)
    passed = 0
    failed = 0
    skipped = 0
    
    print(f"\n{total}個のテストを実行")
    print("-" * 60)
    
    for test_case in EXECUTOR_TESTS:
        # テストケースの解析
        if len(test_case) == 3:
            query, description, expected = test_case
        else:
            query, description = test_case[:2]
            expected = None
        
        print(f"\n[{description}]")
        print(f"  クエリ: {query}")
        
        try:
            # タスク分解
            tasks = await planner.plan_task(query)
            
            if not tasks:
                print("  → タスクなし（スキップ）")
                skipped += 1
                continue
            
            print(f"  → {len(tasks)}個のタスクを実行")
            
            # タスク実行
            result = await executor.execute_tasks(tasks)
            
            if result["success"]:
                actual = result["final_result"]
                
                # 結果の表示（長い場合は省略）
                if isinstance(actual, str) and len(str(actual)) > 50:
                    print(f"  結果: {str(actual)[:50]}...")
                else:
                    print(f"  結果: {actual}")
                
                # 期待値チェック
                if expected is not None:
                    # 数値の場合は近似値でチェック
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
                            print(f"  [NG] 期待{expected}、実際{actual}")
                            failed += 1
                else:
                    print(f"  [INFO] 期待値なし（結果表示のみ）")
                    passed += 1
            else:
                print(f"  [FAIL] 実行失敗")
                # エラー詳細を表示
                for task_data in result["tasks"]:
                    if task_data.get("error"):
                        print(f"    - {task_data['name']}: {task_data['error']}")
                failed += 1
                
        except Exception as e:
            print(f"  [ERROR] 実行エラー: {e}")
            failed += 1
        
        finally:
            # 結果をクリア（次のテストに影響しないように）
            executor.results.clear()
    
    # 結果サマリ
    print("\n" + "=" * 60)
    print("テスト結果サマリ")
    print("-" * 60)
    print(f"  総テスト数: {total}")
    print(f"  成功: {passed}")
    print(f"  失敗: {failed}")
    print(f"  スキップ: {skipped}")
    print(f"  成功率: {passed/total*100:.1f}%")
    
    # クリーンアップ
    await executor.cleanup()
    
    return passed, failed

async def test_executor_single(query: str):
    """単一クエリの詳細テスト（デバッグ用）"""
    print("エグゼキューター詳細テスト")
    print("=" * 60)
    
    planner = UniversalTaskPlanner()
    executor = UniversalTaskExecutor()
    
    await planner.initialize()
    await executor.connect_all_servers()
    
    print(f"\nテストクエリ: {query}")
    print("-" * 40)
    
    # タスク分解
    tasks = await planner.plan_task(query)
    print(f"\nタスク数: {len(tasks)}")
    
    for task in tasks:
        print(f"  [{task.id}] {task.tool}({task.params})")
    
    # 実行
    print("\n実行詳細:")
    result = await executor.execute_tasks(tasks)
    
    print(f"\n実行結果:")
    print(f"  成功: {result['success']}")
    print(f"  最終結果: {result['final_result']}")
    print(f"  統計: {result['stats']}")
    
    # 各タスクの結果
    print(f"\n各タスクの詳細:")
    for task_data in result["tasks"]:
        print(f"  [{task_data['id']}] {task_data['name']}")
        print(f"    結果: {task_data.get('result', 'なし')}")
        if task_data.get('error'):
            print(f"    エラー: {task_data['error']}")
    
    await executor.cleanup()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # 特定のクエリをテスト
        query = " ".join(sys.argv[1:])
        asyncio.run(test_executor_single(query))
    else:
        # 通常のテスト実行
        asyncio.run(test_executor())