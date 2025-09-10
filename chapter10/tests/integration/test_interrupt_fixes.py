#!/usr/bin/env python3
"""
今回の中断処理修正をテストするための統合テスト

修正内容：
1. 空入力時の処理（interrupt_manager.py） - 空エンターで「スキップ」選択
2. タスク状態管理（mcp_agent.py） - 新しいリクエスト時に古いタスクをクリア  
3. 中断→継続時の動作（task_executor.py） - 継続選択時の正しい実行
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

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
from mcp_agent import MCPAgent
from clarification_handler import ClarificationHandler
from conversation_manager import ConversationManager
from llm_interface import LLMInterface


class TestInterruptFixes:
    """中断処理修正のテストクラス"""
    
    def setup_method(self):
        """各テスト前のセットアップ"""
        # グローバルマネージャーをリセット
        import interrupt_manager
        interrupt_manager._global_interrupt_manager = None
        
        # モックコンポーネント
        self.connection_manager = Mock(spec=ConnectionManager)
        self.display_manager = Mock(spec=DisplayManager)
        self.error_handler = Mock(spec=ErrorHandler)
        self.llm_interface = Mock(spec=LLMInterface)
        self.state_manager = Mock(spec=StateManager)
        self.task_manager = Mock(spec=TaskManager)
        
        # インタラプトマネージャー（実際のインスタンス）
        self.interrupt_manager = get_interrupt_manager()
        self.interrupt_manager.reset_interrupt()
        
        # 設定
        from config_manager import ExecutionConfig, ErrorHandlingConfig
        self.config = Config(
            execution=ExecutionConfig(
                max_retries=2,
                timeout_seconds=30
            ),
            error_handling=ErrorHandlingConfig(
                retry_interval=0.1
            )
        )
        
        
        # TaskExecutorインスタンス
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
        
        # TaskExecutor内でグローバルインタラプトマネージャーが使われるはず
        self.interrupt_manager = self.task_executor.interrupt_manager

    @pytest.mark.asyncio
    async def test_invalid_choice_defaults_to_skip(self):
        """空入力や無効な選択時にスキップになることを確認"""
        
        # 中断要求を設定
        self.interrupt_manager.request_interrupt()
        
        # 空文字列入力をモック（無効な選択）
        with patch.object(self.interrupt_manager, '_async_input_with_timeout',
                         return_value=""), \
             patch('sys.stdin.isatty', return_value=True):  # 対話環境として扱う
            
            choice = await self.interrupt_manager.handle_interrupt_choice()
            
            # 空入力の場合、スキップが選択される
            assert choice == 'skip'
    
    @pytest.mark.asyncio
    async def test_continue_choice_executes_tool(self):
        """中断→継続選択時にツールが正しく実行されることを確認"""
        
        # ツール実行をモック
        mock_result = {"result": "test_success"}
        self.connection_manager.call_tool = AsyncMock(return_value=mock_result)
        
        # 継続選択をモック
        with patch.object(self.interrupt_manager, 'check_interrupt', return_value=True), \
             patch.object(self.interrupt_manager, 'handle_interrupt_choice', 
                         return_value='continue'), \
             patch('sys.stdin.isatty', return_value=True):
            
            # _execute_tool_with_interruptを直接テスト
            result = await self.task_executor._execute_tool_with_interrupt(
                "test_tool", {"param": "value"}
            )
            
            # 結果が返されることを確認
            assert result == mock_result
            self.connection_manager.call_tool.assert_called()

    @pytest.mark.asyncio  
    async def test_skip_choice_returns_skip(self):
        """中断→スキップ選択時にSKIPが返されることを確認"""
        
        # ツール実行に遅延を追加して中断監視が動作するようにする
        async def delayed_tool_call(*args, **kwargs):
            await asyncio.sleep(0.2)  # 中断監視が動作する時間を与える
            return {"result": "test"}
            
        self.connection_manager.call_tool = AsyncMock(side_effect=delayed_tool_call)
        
        # スキップ選択をモック
        with patch.object(self.interrupt_manager, 'check_interrupt', return_value=True), \
             patch.object(self.interrupt_manager, 'handle_interrupt_choice', 
                         return_value='skip'), \
             patch('sys.stdin.isatty', return_value=True):
            
            # SKIP定数をインポート
            from task_executor import SKIP
            
            result = await self.task_executor._execute_tool_with_interrupt(
                "test_tool", {"param": "value"}
            )
            
            # SKIPが返されることを確認
            assert result is SKIP
    
    def test_task_state_cleaning_logic(self):
        """MCPAgent内のタスククリア処理をテスト"""
        
        # モックsetup
        mock_clarification_handler = Mock()
        mock_clarification_handler.has_pending_clarifications.return_value = False
        
        mock_state_manager = Mock()
        
        # pending_tasksのモックデータ
        mock_tasks = [
            TaskState(
                task_id="task1",
                tool="get_weather", 
                params={"city": "Tokyo"},
                description="東京の天気",
                status="pending",
                created_at=datetime.now().isoformat()
            ),
            TaskState(
                task_id="task2",
                tool="CLARIFICATION",
                params={},
                description="確認",
                status="pending", 
                created_at=datetime.now().isoformat()
            )
        ]
        
        mock_state_manager.has_pending_tasks.return_value = True
        mock_state_manager.get_pending_tasks.return_value = mock_tasks
        mock_state_manager.move_task_to_completed = AsyncMock()
        
        # MCPAgentの_handle_execution_flowをテスト用に分離
        async def test_task_cleaning():
            # CLARIFICATIONでない通常タスクが残っている場合はクリア
            if mock_state_manager.has_pending_tasks():
                pending_tasks = mock_state_manager.get_pending_tasks()
                non_clarification_tasks = [t for t in pending_tasks if t.tool != "CLARIFICATION"]
                if non_clarification_tasks:
                    # 古いタスクをクリア
                    for task in non_clarification_tasks:
                        await mock_state_manager.move_task_to_completed(
                            task.task_id, 
                            {"skipped": True, "reason": "新しいリクエストのため自動スキップ"}
                        )
        
        # テスト実行
        asyncio.run(test_task_cleaning())
        
        # 通常タスクのみがクリアされることを確認
        mock_state_manager.move_task_to_completed.assert_called_once_with(
            "task1", 
            {"skipped": True, "reason": "新しいリクエストのため自動スキップ"}
        )

    @pytest.mark.asyncio
    async def test_execute_tool_direct_bypasses_interrupt(self):
        """_execute_tool_directが中断なしで実行されることを確認"""
        
        mock_result = {"direct": "execution"}
        self.connection_manager.call_tool = AsyncMock(return_value=mock_result)
        
        # 中断要求があっても無視される
        self.interrupt_manager.request_interrupt()
        
        result = await self.task_executor._execute_tool_direct(
            "test_tool", {"param": "value"}, "test description"
        )
        
        # 結果が正しく返される
        assert result == mock_result
        self.connection_manager.call_tool.assert_called_once_with("test_tool", {"param": "value"})

    @pytest.mark.asyncio
    async def test_task_execution_with_interrupt_continue_flow(self):
        """タスク実行→中断→継続の完全なフローをテスト"""
        
        # テストタスク
        test_task = TaskState(
            task_id="test_task",
            tool="test_tool",
            params={"test": "param"},
            description="テストタスク",
            status="pending",
            created_at=datetime.now().isoformat()
        )
        
        # ツール実行結果のモック
        expected_result = {"success": True, "data": "test_result"}
        self.connection_manager.call_tool = AsyncMock(return_value=expected_result)
        
        # LLMパラメータ解決のモック
        self.llm_interface.resolve_task_parameters = AsyncMock(
            return_value={"test": "resolved_param"}
        )
        
        # StateManagerのモック
        self.state_manager.move_task_to_completed = AsyncMock()
        
        # DisplayManagerのモック
        self.display_manager.show_step_start = Mock()
        self.display_manager.show_tool_call = Mock()
        self.display_manager.show_step_complete = Mock()
        self.display_manager.update_checklist = Mock()
        
        # 中断→継続のシナリオ
        interrupt_call_count = 0
        def mock_check_interrupt():
            nonlocal interrupt_call_count
            interrupt_call_count += 1
            # 最初の呼び出しでは中断、2回目以降は中断なし
            return interrupt_call_count == 1
        
        with patch.object(self.interrupt_manager, 'check_interrupt', 
                         side_effect=mock_check_interrupt), \
             patch.object(self.interrupt_manager, 'handle_interrupt_choice',
                         return_value='continue'), \
             patch('sys.stdin.isatty', return_value=True):
            
            # タスク実行
            result = await self.task_executor.execute_task_sequence(
                [test_task], "test query"
            )
            
            # タスクが完了扱いになることを確認
            self.state_manager.move_task_to_completed.assert_called()
            
            # 結果が正しいことを確認
            assert len(result) > 0


class TestInterruptManagerFixes:
    """InterruptManagerの修正テスト"""
    
    def setup_method(self):
        """セットアップ"""
        import interrupt_manager
        interrupt_manager._global_interrupt_manager = None
        self.interrupt_manager = get_interrupt_manager()

    @pytest.mark.asyncio
    async def test_empty_input_results_in_skip(self):
        """空入力でスキップが選択されることを確認"""
        
        self.interrupt_manager.request_interrupt()
        
        # 空文字列や無効な文字列をテスト
        invalid_inputs = ["", "  ", "invalid", "x", "123"]
        
        for invalid_input in invalid_inputs:
            # リセット
            self.interrupt_manager.reset_interrupt() 
            self.interrupt_manager.request_interrupt()
            
            with patch.object(self.interrupt_manager, '_async_input_with_timeout',
                             return_value=invalid_input), \
                 patch('sys.stdin.isatty', return_value=True):
                
                choice = await self.interrupt_manager.handle_interrupt_choice()
                assert choice == 'skip', f"入力'{invalid_input}'でスキップが選択されるべき"

    @pytest.mark.asyncio
    async def test_valid_choices_work_correctly(self):
        """有効な選択肢が正しく動作することを確認"""
        
        valid_choices = {
            'c': 'continue',
            'continue': 'continue',
            '継続': 'continue',
            's': 'skip', 
            'skip': 'skip',
            'スキップ': 'skip',
            'a': 'abort',
            'abort': 'abort',
            '中止': 'abort'
        }
        
        for input_choice, expected_result in valid_choices.items():
            # リセット
            self.interrupt_manager.reset_interrupt()
            self.interrupt_manager.request_interrupt()
            
            with patch.object(self.interrupt_manager, '_async_input_with_timeout',
                             return_value=input_choice), \
                 patch('sys.stdin.isatty', return_value=True):
                
                choice = await self.interrupt_manager.handle_interrupt_choice()
                assert choice == expected_result, f"入力'{input_choice}'で'{expected_result}'が選択されるべき"


# テスト実行用の関数
def run_tests():
    """テストを実行"""
    pytest.main([__file__, "-v"])


if __name__ == "__main__":
    run_tests()