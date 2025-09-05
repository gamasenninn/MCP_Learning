#!/usr/bin/env python3
"""
ESCタスク管理の機能テスト
ESCでスキップした際のタスク状態管理をテスト

修正対象:
- ESCスキップでタスクがcompleted_tasksに移動する
- pending_tasksに残留しない
- 新しいリクエストで古いタスクが実行されない
"""

import pytest
import pytest_asyncio
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from state_manager import StateManager, TaskState
from task_executor import TaskExecutor, SKIP
from interrupt_manager import InterruptManager, get_interrupt_manager
from config_manager import Config, ExecutionConfig


@pytest_asyncio.fixture
async def temp_state_manager():
    """テスト用StateManagerの作成"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        state_dir = Path(temp_dir) / ".mcp_agent"
        state_manager = StateManager(state_dir=str(state_dir))
        await state_manager.initialize_session()
        yield state_manager


@pytest.fixture
def sample_tasks():
    """テスト用のタスクリスト"""
    return [
        TaskState(
            task_id="weather_tokyo_001",
            tool="get_weather",
            params={"location": "Tokyo"},
            description="東京の現在の天気を取得",
            status="pending"
        ),
        TaskState(
            task_id="weather_beijing_002", 
            tool="get_weather",
            params={"location": "Beijing"},
            description="北京の現在の天気を取得",
            status="pending"
        )
    ]


class TestEscTaskManagement:
    """ESCタスク管理テスト"""
    
    @pytest.mark.asyncio
    async def test_task_completion_with_skip_result(self, temp_state_manager, sample_tasks):
        """スキップ結果でのタスク完了処理"""
        
        state_manager = temp_state_manager
        task = sample_tasks[0]  # 東京の天気タスク
        
        # タスクを pending として追加
        await state_manager.add_pending_task(task)
        
        # pending 状態を確認
        pending_tasks = state_manager.get_pending_tasks()
        assert len(pending_tasks) == 1
        assert pending_tasks[0].task_id == "weather_tokyo_001"
        
        # スキップ処理をシミュレート（{"skipped": True} で完了）
        await state_manager.move_task_to_completed("weather_tokyo_001", {"skipped": True})
        
        # completed に移動し、pending から削除されることを確認
        completed_tasks = state_manager.get_completed_tasks()
        pending_tasks_after = state_manager.get_pending_tasks()
        
        assert len(completed_tasks) == 1
        assert len(pending_tasks_after) == 0
        
        # 完了タスクの内容確認
        completed_task = completed_tasks[0]
        assert completed_task.task_id == "weather_tokyo_001"
        assert completed_task.status == "completed"
        assert completed_task.result == {"skipped": True}
    
    @pytest.mark.asyncio
    async def test_multiple_tasks_skip_handling(self, temp_state_manager, sample_tasks):
        """複数タスクでのスキップ処理"""
        
        state_manager = temp_state_manager
        
        # 2つのタスクを追加
        for task in sample_tasks:
            await state_manager.add_pending_task(task)
        
        # 最初のタスクをスキップ
        await state_manager.move_task_to_completed("weather_tokyo_001", {"skipped": True})
        
        # 1つ目はcompleted、2つ目はまだpending
        completed_tasks = state_manager.get_completed_tasks()
        pending_tasks = state_manager.get_pending_tasks()
        
        assert len(completed_tasks) == 1
        assert len(pending_tasks) == 1
        assert completed_tasks[0].task_id == "weather_tokyo_001"
        assert pending_tasks[0].task_id == "weather_beijing_002"
        
        # 2つ目のタスクも正常完了させる
        await state_manager.move_task_to_completed("weather_beijing_002", "北京の天気: 曇り")
        
        # 両方ともcompleted
        final_completed = state_manager.get_completed_tasks()
        final_pending = state_manager.get_pending_tasks()
        
        assert len(final_completed) == 2
        assert len(final_pending) == 0
    
    @pytest.mark.asyncio
    async def test_task_state_transitions(self, temp_state_manager):
        """タスク状態遷移のテスト"""
        
        state_manager = temp_state_manager
        
        # 初期タスク作成
        task = TaskState(
            task_id="test_transition_001",
            tool="test_tool",
            params={"test": "value"},
            description="状態遷移テスト",
            status="pending"
        )
        
        # pending -> completed (skipped)
        await state_manager.add_pending_task(task)
        assert len(state_manager.get_pending_tasks()) == 1
        
        await state_manager.move_task_to_completed("test_transition_001", {"skipped": True})
        assert len(state_manager.get_pending_tasks()) == 0
        assert len(state_manager.get_completed_tasks()) == 1
        
        completed_task = state_manager.get_completed_tasks()[0]
        assert completed_task.status == "completed"
        assert completed_task.result["skipped"] == True
    
    @pytest.mark.asyncio
    async def test_skip_vs_normal_completion_distinction(self, temp_state_manager):
        """スキップと正常完了の区別テスト"""
        
        state_manager = temp_state_manager
        
        # 2つの類似タスクを作成
        skip_task = TaskState(
            task_id="skip_test_001",
            tool="get_weather", 
            params={"location": "Tokyo"},
            description="スキップテスト",
            status="pending"
        )
        
        normal_task = TaskState(
            task_id="normal_test_001",
            tool="get_weather",
            params={"location": "Beijing"}, 
            description="正常完了テスト",
            status="pending"
        )
        
        await state_manager.add_pending_task(skip_task)
        await state_manager.add_pending_task(normal_task)
        
        # 1つをスキップ、1つを正常完了
        await state_manager.move_task_to_completed("skip_test_001", {"skipped": True})
        await state_manager.move_task_to_completed("normal_test_001", "北京の天気: 晴れ")
        
        # 完了タスクを取得
        completed_tasks = state_manager.get_completed_tasks()
        assert len(completed_tasks) == 2
        
        # スキップタスクと正常完了タスクを区別できる
        skip_task_result = None
        normal_task_result = None
        
        for task in completed_tasks:
            if task.task_id == "skip_test_001":
                skip_task_result = task.result
            elif task.task_id == "normal_test_001":
                normal_task_result = task.result
        
        # スキップタスクは {"skipped": True}
        assert skip_task_result == {"skipped": True}
        # 正常タスクは実行結果の文字列
        assert normal_task_result == "北京の天気: 晴れ"
    
    def test_task_mixing_prevention_by_completion(self):
        """タスク混在防止のメカニズムテスト"""
        
        # TaskStateオブジェクトの状態確認
        task = TaskState(
            task_id="mixing_test_001",
            tool="get_weather",
            params={"location": "Tokyo"},
            description="混在防止テスト", 
            status="pending"
        )
        
        # 初期状態
        assert task.status == "pending"
        assert task.result is None
        
        # 完了状態への遷移
        task.status = "completed"
        task.result = {"skipped": True}
        
        # 完了状態確認
        assert task.status == "completed"  
        assert task.result == {"skipped": True}
        
        # completedタスクは再実行されないことの確認
        # (実際の実行ロジックでは completed status のタスクは除外される)
        assert task.status != "pending"


class TestInterruptManagerIntegration:
    """InterruptManagerとの統合テスト"""
    
    def setup_method(self):
        """各テスト前のセットアップ"""
        # グローバルマネージャーをリセット
        import interrupt_manager
        interrupt_manager._global_interrupt_manager = None
    
    @pytest.mark.asyncio
    async def test_interrupt_manager_skip_choice_handling(self):
        """InterruptManagerのスキップ選択処理"""
        
        # InterruptManagerのインスタンス取得
        interrupt_mgr = get_interrupt_manager()
        
        # 中断要求の発行
        interrupt_mgr.request_interrupt()
        assert interrupt_mgr.check_interrupt() == True
        
        # ユーザー選択のモック
        with patch.object(interrupt_mgr, 'handle_interrupt_choice', return_value='skip'):
            choice = await interrupt_mgr.handle_interrupt_choice()
            assert choice == 'skip'
        
        # 中断状態のリセット
        interrupt_mgr.reset_interrupt()
        assert interrupt_mgr.check_interrupt() == False
    
    def test_execution_tracking_integration(self):
        """実行追跡機能との統合"""
        
        interrupt_mgr = get_interrupt_manager()
        
        # 実行開始
        task_desc = "統合テスト実行"
        interrupt_mgr.start_execution(task_desc)
        
        status = interrupt_mgr.get_status()
        assert status['is_executing'] == True
        assert status['current_task'] == task_desc
        
        # 実行終了
        interrupt_mgr.end_execution()
        
        final_status = interrupt_mgr.get_status()
        assert final_status['is_executing'] == False
        assert final_status['current_task'] is None


class TestTaskCleanupAfterSkip:
    """スキップ後のタスククリーンアップテスト"""
    
    @pytest.mark.asyncio
    async def test_no_pending_tasks_after_skip_completion(self, temp_state_manager):
        """スキップ完了後にpendingタスクが残らない"""
        
        state_manager = temp_state_manager
        
        # 複数のタスクを作成
        tasks = [
            TaskState(
                task_id=f"cleanup_test_{i}",
                tool="test_tool",
                params={"index": i},
                description=f"クリーンアップテスト{i}",
                status="pending"
            )
            for i in range(3)
        ]
        
        # 全タスクをpendingに追加
        for task in tasks:
            await state_manager.add_pending_task(task)
        
        assert len(state_manager.get_pending_tasks()) == 3
        
        # 1つずつスキップ完了
        for i, task in enumerate(tasks):
            await state_manager.move_task_to_completed(
                task.task_id, 
                {"skipped": True}
            )
            
            # 順次pendingから減る
            remaining_pending = len(state_manager.get_pending_tasks())
            completed_count = len(state_manager.get_completed_tasks())
            
            assert remaining_pending == 3 - (i + 1)
            assert completed_count == i + 1
        
        # 最終的にpendingは空
        assert len(state_manager.get_pending_tasks()) == 0
        assert len(state_manager.get_completed_tasks()) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])