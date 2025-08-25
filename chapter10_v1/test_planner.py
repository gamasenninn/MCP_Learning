#!/usr/bin/env python3
"""
タスクプランナーの単体テスト
タスク分解が正しく行われるかを確認
"""

import asyncio
import os
import sys

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

from my_test_cases import PLANNER_TESTS
from universal_task_planner import UniversalTaskPlanner

async def test_planner():
    """プランナーのテスト実行"""
    print("タスクプランナー単体テスト")
    print("=" * 60)
    
    # プランナーの初期化
    planner = UniversalTaskPlanner()
    print("\n[初期化中...]")
    await planner.initialize()
    print(f"  {len(planner.tools_info)}個のツールを利用可能")
    
    # テスト結果の統計
    total = len(PLANNER_TESTS)
    passed = 0
    failed = 0
    
    print(f"\n{total}個のテストを実行")
    print("-" * 60)
    
    for test_case in PLANNER_TESTS:
        # テストケースの解析
        if len(test_case) == 3:
            query, description, expected_tasks = test_case
        else:
            query, description = test_case[:2]
            expected_tasks = None
        
        print(f"\n[{description}]")
        print(f"  クエリ: {query}")
        
        try:
            # タスク分解を実行
            tasks = await planner.plan_task(query)
            
            if not tasks:
                print("  → タスク分解不要（単純なクエリ）")
            else:
                print(f"  → {len(tasks)}個のタスクに分解")
                
                # 各タスクの詳細を表示
                for i, task in enumerate(tasks, 1):
                    print(f"    [{task.id}] {task.tool}")
                    if task.params:
                        # パラメータを簡潔に表示
                        params_str = str(task.params)
                        if len(params_str) > 50:
                            params_str = params_str[:50] + "..."
                        print(f"        パラメータ: {params_str}")
                    if task.dependencies:
                        print(f"        依存: {task.dependencies}")
            
            # 期待タスク数のチェック
            if expected_tasks is not None:
                actual_tasks = len(tasks)
                if actual_tasks == expected_tasks:
                    print(f"  [OK] 期待通り{expected_tasks}個のタスク")
                    passed += 1
                else:
                    print(f"  [NG] 期待{expected_tasks}個、実際{actual_tasks}個")
                    failed += 1
            else:
                # 期待値なしの場合は成功扱い
                print(f"  [INFO] タスク数の検証なし")
                passed += 1
                
        except Exception as e:
            print(f"  [ERROR] タスク分解エラー: {e}")
            failed += 1
    
    # 結果サマリ
    print("\n" + "=" * 60)
    print("テスト結果サマリ")
    print("-" * 60)
    print(f"  総テスト数: {total}")
    print(f"  成功: {passed}")
    print(f"  失敗: {failed}")
    print(f"  成功率: {passed/total*100:.1f}%")
    
    return passed, failed

async def test_planner_verbose():
    """詳細モードでのテスト（デバッグ用）"""
    print("タスクプランナー詳細テスト")
    print("=" * 60)
    
    planner = UniversalTaskPlanner()
    await planner.initialize()
    
    # 1つのテストケースを詳細に確認
    query = "100と200を足して、その結果を2で割って"
    print(f"\nテストクエリ: {query}")
    print("-" * 40)
    
    tasks = await planner.plan_task(query)
    
    print(f"\n生成されたタスク: {len(tasks)}個")
    for task in tasks:
        print(f"\n[タスク {task.id}]")
        print(f"  名前: {task.name}")
        print(f"  ツール: {task.tool}")
        print(f"  サーバー: {task.server}")
        print(f"  パラメータ: {task.params}")
        print(f"  依存関係: {task.dependencies}")
    
    # 検証
    errors = planner.validate_tasks(tasks)
    if errors:
        print("\n検証エラー:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("\n検証: すべてOK")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--verbose":
        # 詳細モード
        asyncio.run(test_planner_verbose())
    else:
        # 通常モード
        asyncio.run(test_planner())