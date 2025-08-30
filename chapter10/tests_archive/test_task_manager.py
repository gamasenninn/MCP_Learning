#!/usr/bin/env python3
"""
Test Task Manager functionality
V6のタスク管理とCLARIFICATION機能のテスト
"""

import asyncio
import sys
import os
import tempfile

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state_manager import StateManager, TaskState
from task_manager import TaskManager, ClarificationRequest


async def test_task_manager():
    """タスク管理システムのテスト"""
    print("=" * 50)
    print("Task Manager Test - V6")
    print("=" * 50)
    
    # 一時ディレクトリでテスト
    with tempfile.TemporaryDirectory() as temp_dir:
        test_state_dir = os.path.join(temp_dir, ".mcp_agent_test")
        
        print(f"\n[1] TaskManager初期化...")
        sm = StateManager(test_state_dir)
        tm = TaskManager(sm)
        
        # セッション初期化
        await sm.initialize_session()
        print("✓ 初期化完了")
        
        # 通常のタスク作成テスト
        print(f"\n[2] 通常タスク作成テスト...")
        normal_task_list = [
            {
                "tool": "get_weather",
                "params": {"city": "Tokyo"},
                "description": "東京の天気を取得"
            },
            {
                "tool": "get_weather", 
                "params": {"city": "{{previous_result}}"},
                "description": "前の結果の都市の天気を取得"
            }
        ]
        
        tasks = await tm.create_tasks_from_list(normal_task_list, "東京の天気を取得して")
        print(f"✓ 通常タスク生成: {len(tasks)}件")
        
        for task in tasks:
            print(f"  - {task.task_id}: {task.description}")
            if task.tool == "CLARIFICATION":
                print(f"    [CLARIFICATION] {task.params.get('question', '不明')}")
        
        # CLARIFICATION が必要なタスクテスト
        print(f"\n[3] CLARIFICATIONタスクテスト...")
        clarification_task_list = [
            {
                "tool": "execute_python",
                "params": {"code": "age = 私の年齢\nresult = age + 10\nprint(result)"},
                "description": "私の年齢に10を足して計算"
            }
        ]
        
        clarification_tasks = await tm.create_tasks_from_list(
            clarification_task_list, 
            "私の年齢に10を足して"
        )
        
        print(f"✓ CLARIFICATIONタスク生成: {len(clarification_tasks)}件")
        
        clarification_found = False
        for task in clarification_tasks:
            print(f"  - {task.task_id}: {task.description}")
            if task.tool == "CLARIFICATION":
                clarification_found = True
                print(f"    [質問] {task.params.get('question', '不明')}")
                print(f"    [文脈] {task.params.get('context', '不明')}")
        
        if clarification_found:
            print("✓ CLARIFICATION検出成功")
        else:
            print("✗ CLARIFICATION検出失敗")
        
        # CLARIFICATIONタスク実行テスト
        print(f"\n[4] CLARIFICATIONタスク実行テスト...")
        clarification_task = None
        for task in clarification_tasks:
            if task.tool == "CLARIFICATION":
                clarification_task = task
                break
        
        if clarification_task:
            # タスクを状態管理に追加
            await sm.add_pending_task(clarification_task)
            
            # CLARIFICATION実行
            question_message = await tm.execute_clarification_task(clarification_task)
            print("✓ CLARIFICATION実行結果:")
            print(question_message[:200] + "..." if len(question_message) > 200 else question_message)
            
            # ユーザー回答のシミュレーション
            user_response = "25"
            await sm.move_task_to_completed(clarification_task.task_id, {"user_response": user_response})
            
            # 回答処理
            resolved = await tm.resolve_clarification(clarification_task.task_id, user_response)
            print(f"✓ 回答処理結果: {resolved}")
        
        # 依存関係解決テスト
        print(f"\n[5] 依存関係解決テスト...")
        
        # 完了済みタスクをシミュレーション
        completed_task = TaskState(
            task_id="completed_001",
            tool="get_ip_info",
            params={},
            description="IP情報取得",
            status="completed",
            result={"city": "Tokyo", "country": "Japan"}
        )
        
        await sm.add_pending_task(completed_task)
        await sm.move_task_to_completed(completed_task.task_id, completed_task.result)
        
        # 依存関係のあるタスク
        dependent_task = TaskState(
            task_id="dependent_001",
            tool="get_weather",
            params={"city": "DEPENDENCY:取得した都市名"},
            description="取得した都市の天気",
            status="pending"
        )
        
        completed_tasks = sm.get_completed_tasks()
        resolved_task = await tm.resolve_task_dependencies(dependent_task, completed_tasks)
        
        print(f"✓ 依存関係解決前: {dependent_task.params}")
        print(f"✓ 依存関係解決後: {resolved_task.params}")
        
        # タスク要約テスト
        print(f"\n[6] タスク要約テスト...")
        summary = tm.get_task_summary()
        print("✓ タスク要約:")
        for key, value in summary.items():
            print(f"  {key}: {value}")
        
        # 実行可能タスク取得テスト
        print(f"\n[7] 実行可能タスク取得テスト...")
        next_task = tm.get_next_executable_task()
        if next_task:
            print(f"✓ 次の実行可能タスク: {next_task.description}")
        else:
            print("✓ 実行可能タスクなし")
        
        # CLARIFICATIONチェックテスト
        has_clarification = tm.has_clarification_tasks()
        print(f"✓ CLARIFICATION有無: {has_clarification}")
        
        print("\n" + "=" * 50)
        print("Task Manager Test 完了！")
        print("=" * 50)


if __name__ == "__main__":
    asyncio.run(test_task_manager())