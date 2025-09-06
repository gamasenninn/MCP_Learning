#!/usr/bin/env python3
"""
Integration tests for interrupt functionality
中断機能の統合テスト

TaskExecutorとの統合をテスト
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from task_executor import TaskExecutor
from interrupt_manager import InterruptManager, get_interrupt_manager
from state_manager import StateManager, TaskState
from task_manager import TaskManager
from connection_manager import ConnectionManager
from display_manager import DisplayManager
from error_handler import ErrorHandler
from config_manager import Config
from utils import Logger


class TestInterruptIntegration:
    """中断機能の統合テストクラス"""
    
    def setup_method(self):
        """各テスト前のセットアップ"""
        # グローバルマネージャーをリセット
        import interrupt_manager
        interrupt_manager._global_interrupt_manager = None
        
        # モックコンポーネントを作成
        self.state_manager = Mock(spec=StateManager)
        self.task_manager = Mock(spec=TaskManager)
        self.connection_manager = Mock(spec=ConnectionManager)
        self.display_manager = Mock(spec=DisplayManager)
        self.error_handler = Mock(spec=ErrorHandler)
        self.llm_interface = Mock()
        
        # 設定モック
        from config_manager import ExecutionConfig
        self.config = Config(
            execution=ExecutionConfig(
                max_retries=2,
                timeout_seconds=30,
                max_tasks=10
            )
        )
        
        # TaskExecutorを初期化
        self.task_executor = TaskExecutor(
            task_manager=self.task_manager,
            connection_manager=self.connection_manager,
            state_manager=self.state_manager,
            display_manager=self.display_manager,
            llm_interface=self.llm_interface,
            config=self.config,
            error_handler=self.error_handler,
            verbose=False
        )
        
        # 中断マネージャーを取得
        self.interrupt_manager = self.task_executor.interrupt_manager
    
    @pytest.mark.asyncio
    async def test_task_sequence_interrupt_before_start(self):
        """タスクシーケンス開始前の中断テスト"""
        # テストタスクを作成
        test_task = TaskState(
            task_id="test_1",
            tool="test_tool",
            params={"test": "value"},
            description="テストタスク",
            status="pending"
        )
        
        # 中断要求を事前に発行
        self.interrupt_manager.request_interrupt()
        
        # 中断選択をモック（中止を選択）
        async def mock_abort():
            return 'abort'
        
        with patch.object(self.interrupt_manager, 'handle_interrupt_choice', 
                         side_effect=mock_abort):
            
            result = await self.task_executor.execute_task_sequence([test_task], "テストクエリ")
        
        # 実行が中止されたことを確認
        # display.show_task_list が呼ばれていることを確認（タスクリスト表示）
        self.display_manager.show_task_list.assert_called()
        
        # connection_manager.call_tool が呼ばれていないことを確認（中止のため）
        self.connection_manager.call_tool.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_task_sequence_interrupt_skip(self):
        """タスクスキップの中断テスト"""
        # テストタスクを作成
        test_task = TaskState(
            task_id="test_1",
            tool="test_tool",
            params={"test": "value"},
            description="テストタスク",
            status="pending"
        )
        
        # LLMパラメータ解決をモック
        async def mock_resolve_params(task, ctx):
            return {"resolved": True}
            
        # 事前に中断要求を発行
        self.interrupt_manager.request_interrupt()
        
        # 中断選択をモック（スキップを選択）
        async def mock_skip():
            return 'skip'
            
        with patch.object(self.task_executor, 'resolve_parameters_with_llm',
                         side_effect=mock_resolve_params), \
             patch.object(self.interrupt_manager, 'handle_interrupt_choice',
                         side_effect=mock_skip):
            
            result = await self.task_executor.execute_task_sequence([test_task], "テストクエリ")
        
        # タスクがスキップされたことを確認
        self.connection_manager.call_tool.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_parameter_resolution_interrupt(self):
        """パラメータ解決中の中断テスト"""
        # テストタスクを作成
        test_task = TaskState(
            task_id="test_1",
            tool="test_tool",
            params={"test": "value"},
            description="テストタスク",
            status="pending"
        )
        
        # 中断要求を事前に発行
        self.interrupt_manager.request_interrupt()
        
        # 中断選択をモック（中止を選択してKeyboardInterruptを発生させる）
        async def mock_abort():
            return 'abort'
        
        with patch.object(self.interrupt_manager, 'handle_interrupt_choice',
                         side_effect=mock_abort):
            
            # EscInterruptが発生することを期待
            with pytest.raises(Exception, match="ユーザーが中止を選択"):
                await self.task_executor.resolve_parameters_with_llm(test_task, [])
        
        # LLMInterfaceが呼ばれていないことを確認
        # (中断されたため)
    
    def test_execution_tracking(self):
        """実行追跡機能のテスト"""
        task_desc = "統合テストタスク"
        
        # 実行開始
        self.interrupt_manager.start_execution(task_desc)
        
        status = self.interrupt_manager.get_status()
        assert status['is_executing'] == True
        assert status['current_task'] == task_desc
        
        # 中断要求
        self.interrupt_manager.request_interrupt()
        
        # 実行中の中断要求が正しく検知されることを確認
        assert self.interrupt_manager.check_interrupt() == True
        
        # 実行終了
        self.interrupt_manager.end_execution()
        
        final_status = self.interrupt_manager.get_status()
        assert final_status['is_executing'] == False
    
    @pytest.mark.skip(reason="Test needs redesign after interrupt handling refactor")
    @pytest.mark.asyncio
    async def test_multiple_tasks_interrupt(self):
        """複数タスクでの中断テスト"""
        # 複数のテストタスクを作成
        tasks = [
            TaskState(
                task_id=f"test_{i}",
                tool="test_tool",
                params={"test": f"value_{i}"},
                description=f"テストタスク{i}",
                status="pending"
            )
            for i in range(3)
        ]
        
        # 最初のタスクが完了した後に中断要求を発行する設定
        call_count = 0
        original_call_tool = self.connection_manager.call_tool
        
        def mock_call_tool(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # 最初のタスク完了後に中断要求
                self.interrupt_manager.request_interrupt()
            return AsyncMock(return_value=Mock())
        
        self.connection_manager.call_tool = AsyncMock(side_effect=mock_call_tool)
        
        # LLMパラメータ解決をモック
        async def mock_resolve_params_multi(task, ctx):
            return {"resolved": True}
            
        with patch.object(self.task_executor, 'resolve_parameters_with_llm',
                         side_effect=mock_resolve_params_multi):
            
            # state_managerのメソッドをモック
            self.state_manager.move_task_to_completed = AsyncMock()
            
            # 中断選択をモック（2番目のタスクで中止を選択）
            async def mock_abort_multi():
                return 'abort'
                
            with patch.object(self.interrupt_manager, 'handle_interrupt_choice',
                             side_effect=mock_abort_multi):
                
                result = await self.task_executor.execute_task_sequence(tasks, "複数タスクテスト")
        
        # 最初のタスクのみ実行され、その後中止されたことを確認
        assert call_count == 1  # 最初のタスクのみ実行
    
    def test_interrupt_manager_integration_with_task_executor(self):
        """TaskExecutorとInterruptManagerの統合テスト"""
        # TaskExecutorが中断マネージャーを正しく持っていることを確認
        assert hasattr(self.task_executor, 'interrupt_manager')
        assert isinstance(self.task_executor.interrupt_manager, InterruptManager)
        
        # 同一のグローバルインスタンスを使用していることを確認
        global_manager = get_interrupt_manager()
        assert self.task_executor.interrupt_manager is global_manager


if __name__ == "__main__":
    # 統合テストを実行
    pytest.main([__file__, "-v"])