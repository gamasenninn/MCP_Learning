#!/usr/bin/env python3
"""
Interrupt Manager for ESC-based task interruption
ESCキーによるタスク中断機能の管理

機能:
- ESCキーの中断シグナル管理
- 中断状態の追跡と制御
- 中断ポイントでの適切な処理
"""

import asyncio
import threading
import time
from typing import Optional, Callable
from enum import Enum

from utils import Logger


class InterruptState(Enum):
    """中断状態の列挙"""
    NONE = "none"               # 中断なし
    REQUESTED = "requested"     # 中断要求あり
    CONFIRMED = "confirmed"     # 中断確定
    IGNORED = "ignored"         # 中断無視（継続実行）


class InterruptManager:
    """
    ESCキーによる中断機能を管理するクラス
    
    主な責任:
    - 中断フラグの管理
    - 中断状態の追跡
    - 中断時のユーザー選択肢の提示
    """
    
    def __init__(self, verbose: bool = True, non_interactive_default: str = "abort"):
        """
        Args:
            verbose: 詳細ログ出力
            non_interactive_default: 非対話環境でのデフォルト選択 ("abort", "continue", "skip")
        """
        self.verbose = verbose
        self.logger = Logger(verbose=verbose)
        self.non_interactive_default = non_interactive_default
        
        # 中断状態管理
        self._interrupt_state = InterruptState.NONE
        self._interrupt_timestamp = 0.0
        self._lock = threading.Lock()
        
        # 実行状態の追跡
        self._is_executing = False
        self._current_task = None
        self._task_start_time = 0.0
        
        # コールバック
        self._on_interrupt_callback: Optional[Callable] = None
        
        # 中断タイムアウト設定（秒）
        self.interrupt_timeout = 10.0
    
    def set_interrupt_callback(self, callback: Callable) -> None:
        """
        中断時のコールバック関数を設定
        
        Args:
            callback: 中断時に呼び出される関数
        """
        self._on_interrupt_callback = callback
    
    def request_interrupt(self) -> None:
        """
        中断要求を発行（ESCキー押下時に呼び出される）
        """
        with self._lock:
            # 新しい中断要求は常に受け付ける（前の状態をリセット）
            if self._interrupt_state in [InterruptState.NONE, InterruptState.IGNORED]:
                self._interrupt_state = InterruptState.REQUESTED
                self._interrupt_timestamp = time.monotonic()
                
                if self.verbose:
                    if self._is_executing and self._current_task:
                        self.logger.ulog(f"\n[INTERRUPT] 中断要求: {self._current_task}", "warning:interrupt", always_print=True)
                    else:
                        self.logger.ulog("\n[INTERRUPT] 中断要求を受け付けました", "info:interrupt", always_print=True)
                
                # コールバック実行
                if self._on_interrupt_callback:
                    try:
                        self._on_interrupt_callback()
                    except Exception as e:
                        self.logger.ulog(f"中断コールバックエラー: {e}", "error:callback")
            elif self._interrupt_state == InterruptState.REQUESTED:
                # 既に要求中の場合はタイムスタンプのみ更新（連打防止にもなる）
                self._interrupt_timestamp = time.monotonic()
    
    def check_interrupt(self) -> bool:
        """
        中断チェック（実行ポイントで呼び出す）
        
        Returns:
            True: 中断が要求されている
            False: 継続実行
        """
        with self._lock:
            if self._interrupt_state == InterruptState.REQUESTED:
                # タイムアウトチェック
                if time.monotonic() - self._interrupt_timestamp > self.interrupt_timeout:
                    self.logger.ulog("\n[TIMEOUT] 中断要求がタイムアウトしました", "warning:timeout", always_print=True)
                    self._interrupt_state = InterruptState.NONE
                    return False
                
                return True
            
            return False
    
    def confirm_interrupt(self) -> None:
        """中断を確定する"""
        with self._lock:
            if self._interrupt_state == InterruptState.REQUESTED:
                self._interrupt_state = InterruptState.CONFIRMED
                if self.verbose:
                    self.logger.ulog("[CONFIRMED] 中断が確定されました", "info:interrupt", always_print=True)
    
    def ignore_interrupt(self) -> None:
        """中断を無視して継続する"""
        with self._lock:
            if self._interrupt_state in [InterruptState.REQUESTED, InterruptState.CONFIRMED]:
                self._interrupt_state = InterruptState.IGNORED
                if self.verbose:
                    self.logger.ulog("[CONTINUE] 中断を無視して継続します", "info:continue", always_print=True)
    
    def reset_interrupt(self) -> None:
        """中断状態をリセット"""
        with self._lock:
            self._interrupt_state = InterruptState.NONE
            self._interrupt_timestamp = 0.0
    
    def start_execution(self, task_description: str = "タスク") -> None:
        """
        タスク実行開始を記録
        
        Args:
            task_description: 実行中のタスクの説明
        """
        with self._lock:
            self._is_executing = True
            self._current_task = task_description
            self._task_start_time = time.monotonic()
    
    def end_execution(self) -> None:
        """タスク実行終了を記録"""
        with self._lock:
            self._is_executing = False
            self._current_task = None
            self._task_start_time = 0.0
    
    def get_status(self) -> dict:
        """
        現在の中断管理状態を取得
        
        Returns:
            状態情報の辞書
        """
        with self._lock:
            return {
                "interrupt_state": self._interrupt_state.value,
                "is_executing": self._is_executing,
                "current_task": self._current_task,
                "has_interrupt_pending": self._interrupt_state == InterruptState.REQUESTED,
                "execution_duration": time.monotonic() - self._task_start_time if self._is_executing and self._task_start_time > 0 else 0.0
            }
    
    async def handle_interrupt_choice(self) -> str:
        """
        中断時の選択肢を提示してユーザーの選択を取得
        
        Returns:
            ユーザーの選択 ('continue', 'skip', 'abort')
        """
        if not self.check_interrupt():
            return 'continue'
        
        try:
            # 選択肢を表示
            self.logger.ulog("\n" + "="*50, "info", always_print=True)
            self.logger.ulog("[INTERRUPT] タスクが中断されました", "warning:interrupt", always_print=True)
            self.logger.ulog("", "info", always_print=True)
            self.logger.ulog("選択肢:", "info", always_print=True)
            self.logger.ulog("  1. 継続 (c/continue) - このタスクを続行", "info", always_print=True)
            self.logger.ulog("  2. スキップ (s/skip) - このタスクをスキップして次へ", "info", always_print=True)
            self.logger.ulog("  3. 中止 (a/abort) - 全体を中止", "info", always_print=True)
            self.logger.ulog("", "info", always_print=True)
            
            # ユーザー入力を待機（同期的に）
            try:
                # パイプ入力の場合はデフォルト選択を使用
                import sys
                if not sys.stdin.isatty():
                    self.logger.ulog(f"非対話環境のため {self.non_interactive_default} を選択します", "warning", always_print=True)
                    
                    if self.non_interactive_default == 'abort':
                        self.confirm_interrupt()
                        return 'abort'
                    elif self.non_interactive_default == 'skip':
                        self.confirm_interrupt()
                        return 'skip'
                    else:  # continue
                        self.ignore_interrupt()
                        return 'continue'
                
                # 非同期入力のためのタイムアウト付き入力
                choice = await self._async_input_with_timeout("選択してください [c/s/a]: ", timeout=30.0)
                
                if choice in ['c', 'continue', '継続']:
                    self.ignore_interrupt()
                    return 'continue'
                elif choice in ['s', 'skip', 'スキップ']:
                    self.confirm_interrupt()
                    return 'skip'
                elif choice in ['a', 'abort', '中止']:
                    self.confirm_interrupt()
                    return 'abort'
                else:
                    self.logger.ulog("無効な選択です。タスクをスキップします。", "warning", always_print=True)
                    self.confirm_interrupt()
                    return 'skip'
                    
            except (EOFError, KeyboardInterrupt):
                self.logger.ulog("入力が中断されました。中止します。", "warning", always_print=True)
                self.confirm_interrupt()
                return 'abort'
                
        finally:
            self.logger.ulog("="*50, "info", always_print=True)
    
    async def _async_input_with_timeout(self, prompt: str, timeout: float = 30.0) -> str:
        """
        タイムアウト付きの非同期入力
        """
        import asyncio
        import sys
        
        def sync_input():
            return input(prompt).strip().lower()
        
        try:
            # 非同期で入力を待機（タイムアウト付き）
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, sync_input),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            self.logger.ulog(f"\n[TIMEOUT] 入力タイムアウト({timeout}秒)。中止します。", "warning", always_print=True)
            return 'abort'
        except Exception as e:
            self.logger.ulog(f"\n[ERROR] 入力エラー: {e}。中止します。", "error", always_print=True)
            return 'abort'
    
    def is_interrupted(self) -> bool:
        """
        中断されているかどうかを判定
        
        Returns:
            True: 中断状態（要求中または確定済み）
            False: 継続状態（なし、無視、またはリセット済み）
        """
        with self._lock:
            return self._interrupt_state in [InterruptState.REQUESTED, InterruptState.CONFIRMED]
    
    def should_abort(self) -> bool:
        """
        中止すべきかどうかを判定
        
        Returns:
            True: 中止すべき
            False: 継続または他の処理
        """
        with self._lock:
            return self._interrupt_state == InterruptState.CONFIRMED


# グローバル中断マネージャー（シングルトン）
_global_interrupt_manager: Optional[InterruptManager] = None


def get_interrupt_manager(verbose: bool = True, non_interactive_default: str = None, timeout: float = None) -> InterruptManager:
    """
    グローバル中断マネージャーのインスタンスを取得
    
    Args:
        verbose: 詳細ログ出力（初回作成時のみ適用）
        non_interactive_default: 非対話環境でのデフォルト選択（渡されない場合は設定から読み込み）
        timeout: 中断タイムアウト時間（渡されない場合は設定から読み込み）
        
    Returns:
        InterruptManagerのインスタンス
    """
    global _global_interrupt_manager
    
    if _global_interrupt_manager is None:
        # パラメータで渡されない場合は設定ファイルから読み込み
        if non_interactive_default is None or timeout is None:
            try:
                from config_manager import ConfigManager
                import os
                config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
                if os.path.exists(config_path):
                    config = ConfigManager.load(config_path)
                    if non_interactive_default is None:
                        non_interactive_default = config.interrupt_handling.non_interactive_default
                    if timeout is None:
                        timeout = config.interrupt_handling.timeout
                else:
                    if non_interactive_default is None:
                        non_interactive_default = "abort"
                    if timeout is None:
                        timeout = 10.0
            except Exception:
                if non_interactive_default is None:
                    non_interactive_default = "abort"
                if timeout is None:
                    timeout = 10.0
            
        _global_interrupt_manager = InterruptManager(
            verbose=verbose, 
            non_interactive_default=non_interactive_default
        )
        _global_interrupt_manager.interrupt_timeout = timeout
    
    return _global_interrupt_manager


def request_interrupt():
    """グローバル中断マネージャーに中断要求を発行"""
    manager = get_interrupt_manager()
    manager.request_interrupt()