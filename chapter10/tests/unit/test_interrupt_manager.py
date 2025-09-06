#!/usr/bin/env python3
"""
Unit tests for InterruptManager
InterruptManagerクラスの単体テスト
"""

import pytest
import time
import asyncio
from unittest.mock import Mock, patch

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from interrupt_manager import InterruptManager, InterruptState, get_interrupt_manager, request_interrupt


class TestInterruptManager:
    """InterruptManagerのテストクラス"""
    
    def setup_method(self):
        """各テスト前のセットアップ"""
        # グローバルマネージャーをリセット
        import interrupt_manager
        interrupt_manager._global_interrupt_manager = None
        
        self.manager = InterruptManager(verbose=False, non_interactive_default="continue")
    
    def test_initial_state(self):
        """初期状態のテスト"""
        status = self.manager.get_status()
        
        assert status['interrupt_state'] == InterruptState.NONE.value
        assert status['is_executing'] == False
        assert status['current_task'] is None
        assert status['has_interrupt_pending'] == False
        assert status['execution_duration'] == 0.0
    
    def test_request_interrupt(self):
        """中断要求のテスト"""
        # 中断要求
        self.manager.request_interrupt()
        
        status = self.manager.get_status()
        assert status['interrupt_state'] == InterruptState.REQUESTED.value
        assert status['has_interrupt_pending'] == True
        assert self.manager.check_interrupt() == True
    
    def test_confirm_interrupt(self):
        """中断確定のテスト"""
        # 中断要求 → 確定
        self.manager.request_interrupt()
        self.manager.confirm_interrupt()
        
        status = self.manager.get_status()
        assert status['interrupt_state'] == InterruptState.CONFIRMED.value
        assert self.manager.should_abort() == True
    
    def test_ignore_interrupt(self):
        """中断無視のテスト"""
        # 中断要求 → 無視
        self.manager.request_interrupt()
        self.manager.ignore_interrupt()
        
        status = self.manager.get_status()
        assert status['interrupt_state'] == InterruptState.IGNORED.value
        assert self.manager.check_interrupt() == False
    
    def test_reset_interrupt(self):
        """中断リセットのテスト"""
        # 中断要求 → リセット
        self.manager.request_interrupt()
        self.manager.reset_interrupt()
        
        status = self.manager.get_status()
        assert status['interrupt_state'] == InterruptState.NONE.value
        assert status['has_interrupt_pending'] == False
    
    def test_execution_tracking(self):
        """実行追跡のテスト"""
        task_desc = "テストタスク"
        
        # 実行開始
        self.manager.start_execution(task_desc)
        
        # わずかな待機（実行時間を確保）- より長い時間で確実性向上
        time.sleep(0.05)
        
        status = self.manager.get_status()
        assert status['is_executing'] == True
        assert status['current_task'] == task_desc
        assert status['execution_duration'] > 0
        
        # 少し待つ
        time.sleep(0.1)
        
        # 実行時間が増加していることを確認
        new_status = self.manager.get_status()
        assert new_status['execution_duration'] > status['execution_duration']
        
        # 実行終了
        self.manager.end_execution()
        
        final_status = self.manager.get_status()
        assert final_status['is_executing'] == False
        assert final_status['current_task'] is None
        assert final_status['execution_duration'] == 0.0
    
    def test_interrupt_timeout(self):
        """中断タイムアウトのテスト"""
        # タイムアウトを短く設定
        self.manager.interrupt_timeout = 0.1
        
        # 中断要求
        self.manager.request_interrupt()
        assert self.manager.check_interrupt() == True
        
        # タイムアウト待機
        time.sleep(0.15)
        
        # タイムアウト後はfalseが返される
        assert self.manager.check_interrupt() == False
        
        # 状態もリセットされている
        status = self.manager.get_status()
        assert status['interrupt_state'] == InterruptState.NONE.value
    
    def test_callback_functionality(self):
        """コールバック機能のテスト"""
        callback_called = False
        
        def test_callback():
            nonlocal callback_called
            callback_called = True
        
        # コールバック設定
        self.manager.set_interrupt_callback(test_callback)
        
        # 中断要求
        self.manager.request_interrupt()
        
        # コールバックが呼ばれたことを確認
        assert callback_called == True
    
    def test_is_interrupted_method(self):
        """is_interruptedメソッドのテスト"""
        assert self.manager.is_interrupted() == False
        
        # 要求状態
        self.manager.request_interrupt()
        assert self.manager.is_interrupted() == True
        
        # 確定状態
        self.manager.confirm_interrupt()
        assert self.manager.is_interrupted() == True
        
        # 無視状態
        self.manager.ignore_interrupt()
        assert self.manager.is_interrupted() == False
        
        # リセット状態
        self.manager.reset_interrupt()
        assert self.manager.is_interrupted() == False
    
    @pytest.mark.asyncio
    async def test_handle_interrupt_choice_continue(self):
        """中断選択処理のテスト（継続）"""
        self.manager.request_interrupt()
        
        # 対話モードをシミュレートして入力をモック
        with patch('sys.stdin.isatty', return_value=True), \
             patch('builtins.input', return_value='c'):
            choice = await self.manager.handle_interrupt_choice()
            
        assert choice == 'continue'
        assert self.manager.get_status()['interrupt_state'] == InterruptState.IGNORED.value
    
    @pytest.mark.asyncio
    async def test_handle_interrupt_choice_skip(self):
        """中断選択処理のテスト（スキップ）"""
        self.manager.request_interrupt()
        
        # 対話モードをシミュレートして入力をモック
        with patch('sys.stdin.isatty', return_value=True), \
             patch('builtins.input', return_value='s'):
            choice = await self.manager.handle_interrupt_choice()
            
        assert choice == 'skip'
        assert self.manager.get_status()['interrupt_state'] == InterruptState.CONFIRMED.value
    
    @pytest.mark.asyncio
    async def test_handle_interrupt_choice_abort(self):
        """中断選択処理のテスト（中止）"""
        self.manager.request_interrupt()
        
        # 対話モードをシミュレートして入力をモック
        with patch('sys.stdin.isatty', return_value=True), \
             patch('builtins.input', return_value='a'):
            choice = await self.manager.handle_interrupt_choice()
            
        assert choice == 'abort'
        assert self.manager.get_status()['interrupt_state'] == InterruptState.CONFIRMED.value


class TestGlobalInterruptManager:
    """グローバル中断マネージャーのテストクラス"""
    
    def setup_method(self):
        """各テスト前のセットアップ"""
        # グローバルマネージャーをリセット
        import interrupt_manager
        interrupt_manager._global_interrupt_manager = None
    
    def test_singleton_behavior(self):
        """シングルトン動作のテスト"""
        manager1 = get_interrupt_manager()
        manager2 = get_interrupt_manager()
        
        # 同じインスタンスが返される
        assert manager1 is manager2
    
    def test_global_request_interrupt(self):
        """グローバル中断要求のテスト"""
        manager = get_interrupt_manager()
        
        # グローバル関数で中断要求
        request_interrupt()
        
        # マネージャーの状態が変わっていることを確認
        assert manager.check_interrupt() == True


if __name__ == "__main__":
    # 単体でテストを実行
    pytest.main([__file__, "-v"])