#!/usr/bin/env python3
"""
ハノイの塔のパラメータフィルタリング修正のテスト
"""

import asyncio
import json
from task_manager import TaskManager
from state_manager import StateManager, TaskState
from typing import Dict, List, Any

async def test_description_filtering():
    """descriptionパラメータのフィルタリングをテスト"""
    
    # StateManagerのモック
    state_manager = StateManager(session_dir=".test_session")
    
    # TaskManagerのインスタンス
    task_manager = TaskManager(state_manager)
    
    # LLMが誤ってdescriptionをparamsに含めた場合のテストケース
    problematic_task_list = [
        {
            "tool": "execute_python",
            "params": {
                "code": "def hanoi(n, source, target, auxiliary):\n    if n == 1:\n        print(f'Move disk 1 from {source} to {target}')\n        return\n    hanoi(n - 1, source, auxiliary, target)\n    print(f'Move disk {n} from {source} to {target}')\n    hanoi(n - 1, auxiliary, target, source)\n\nhanoi(3, 'A', 'C', 'B')",
                "description": "ハノイの塔を解くPythonコードを実行する"  # これが問題
            },
            "description": "execute_pythonを実行"
        }
    ]
    
    # 正しいタスクリスト（比較用）
    correct_task_list = [
        {
            "tool": "execute_python",
            "params": {
                "code": "print('Hello, World!')"
            },
            "description": "Hello Worldを出力"
        }
    ]
    
    print("テスト1: 問題のあるタスクリスト（descriptionがparamsに含まれる）")
    tasks = await task_manager.create_tasks_from_list(
        problematic_task_list, 
        "ハノイの塔を解くPythonコードを書いて実行してください"
    )
    
    for task in tasks:
        print(f"  Tool: {task.tool}")
        print(f"  Params: {json.dumps(task.params, ensure_ascii=False, indent=2)}")
        print(f"  Description: {task.description}")
        
        # 検証: paramsにdescriptionが含まれていないことを確認
        assert 'description' not in task.params, "ERROR: 'description'がparamsに残っています！"
        print("  ✓ paramsから'description'が正しく削除されました")
        print()
    
    print("\nテスト2: 正しいタスクリスト（descriptionがタスクレベルのみ）")
    tasks2 = await task_manager.create_tasks_from_list(
        correct_task_list,
        "Hello Worldを出力してください"
    )
    
    for task in tasks2:
        print(f"  Tool: {task.tool}")
        print(f"  Params: {json.dumps(task.params, ensure_ascii=False, indent=2)}")
        print(f"  Description: {task.description}")
        
        # 検証: paramsが正しく処理されていることを確認
        assert 'code' in task.params, "ERROR: 'code'パラメータが見つかりません！"
        assert 'description' not in task.params, "ERROR: 不要な'description'がparamsに含まれています！"
        print("  ✓ paramsが正しく処理されました")
        print()
    
    print("すべてのテストが成功しました！")
    
    # クリーンアップ
    import shutil
    import os
    if os.path.exists(".test_session"):
        shutil.rmtree(".test_session")

if __name__ == "__main__":
    asyncio.run(test_description_filtering())