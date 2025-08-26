#!/usr/bin/env python3
"""
Test State Manager functionality
V6の状態管理システムのテスト
"""

import asyncio
import sys
import os
import tempfile
import shutil
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state_manager import StateManager, TaskState, SessionState


async def test_state_manager():
    """状態管理システムのテスト"""
    print("=" * 50)
    print("State Manager Test - V6")
    print("=" * 50)
    
    # 一時ディレクトリでテスト
    with tempfile.TemporaryDirectory() as temp_dir:
        test_state_dir = os.path.join(temp_dir, ".mcp_agent_test")
        
        print(f"\n[1] StateManager初期化テスト...")
        sm = StateManager(test_state_dir)
        
        # セッション初期化
        session_id = await sm.initialize_session()
        print(f"✓ セッション作成: {session_id}")
        
        # 会話エントリ追加
        print(f"\n[2] 会話履歴テスト...")
        await sm.add_conversation_entry("user", "こんにちは")
        await sm.add_conversation_entry("assistant", "こんにちは！お手伝いできることはありますか？")
        print("✓ 会話エントリ追加完了")
        
        # 会話履歴取得
        context = sm.get_conversation_context(2)
        print(f"✓ 会話履歴取得: {len(context)}件")
        for entry in context:
            print(f"  - [{entry['role']}] {entry['content'][:30]}...")
        
        # タスク管理テスト
        print(f"\n[3] タスク管理テスト...")
        
        # タスク追加
        task1 = TaskState(
            task_id="test_001",
            tool="get_weather",
            params={"city": "Tokyo"},
            description="東京の天気を取得",
            status="pending"
        )
        
        task2 = TaskState(
            task_id="test_002", 
            tool="CLARIFICATION",
            params={"question": "年齢を教えてください"},
            description="ユーザーに年齢確認",
            status="pending"
        )
        
        await sm.add_pending_task(task1)
        await sm.add_pending_task(task2)
        print("✓ タスク追加完了")
        
        # タスク取得
        pending = sm.get_pending_tasks()
        print(f"✓ 実行待ちタスク: {len(pending)}件")
        for task in pending:
            print(f"  - {task.task_id}: {task.description}")
        
        # タスク完了
        await sm.move_task_to_completed("test_001", {"temperature": "22°C", "condition": "sunny"})
        print("✓ タスク完了処理")
        
        # 状態確認
        print(f"\n[4] 状態確認テスト...")
        completed = sm.get_completed_tasks()
        pending_after = sm.get_pending_tasks()
        
        print(f"✓ 完了タスク: {len(completed)}件")
        print(f"✓ 残り実行待ち: {len(pending_after)}件")
        
        # セッション要約
        summary = sm.get_session_summary()
        print(f"\n[5] セッション要約:")
        for key, value in summary.items():
            print(f"  {key}: {value}")
        
        # 一時停止・再開テスト
        print(f"\n[6] 一時停止・再開テスト...")
        await sm.pause_all_tasks()
        print("✓ タスク一時停止")
        
        await sm.resume_paused_tasks()
        print("✓ タスク再開")
        
        # ファイル存在確認
        print(f"\n[7] ファイル生成確認...")
        state_dir = sm.state_dir
        
        files_to_check = [
            state_dir / "session.json",
            state_dir / "conversation.txt", 
            state_dir / "tasks" / "pending.json",
            state_dir / "tasks" / "completed.json",
            state_dir / "tasks" / "current.txt"
        ]
        
        for file_path in files_to_check:
            if file_path.exists():
                print(f"✓ {file_path.name} 生成済み")
            else:
                print(f"✗ {file_path.name} 未生成")
        
        # セッション復元テスト
        print(f"\n[8] セッション復元テスト...")
        sm2 = StateManager(test_state_dir)
        restored_session_id = await sm2.initialize_session(session_id)
        print(f"✓ セッション復元: {restored_session_id}")
        
        # 復元後の状態確認
        restored_context = sm2.get_conversation_context()
        restored_pending = sm2.get_pending_tasks()
        restored_completed = sm2.get_completed_tasks()
        
        print(f"✓ 復元後 - 会話: {len(restored_context)}件")
        print(f"✓ 復元後 - 実行待ち: {len(restored_pending)}件")
        print(f"✓ 復元後 - 完了: {len(restored_completed)}件")
        
        print("\n" + "=" * 50)
        print("State Manager Test 完了！")
        print("=" * 50)


if __name__ == "__main__":
    asyncio.run(test_state_manager())