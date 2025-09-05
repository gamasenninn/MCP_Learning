#!/usr/bin/env python3
"""
Background Input Monitor
バックグラウンドでキー入力を監視してESC中断を検知

Windows/Unix両対応のキー監視機能
"""

import asyncio
import threading
import sys
import atexit
from typing import Optional, Callable

from interrupt_manager import get_interrupt_manager
from utils import Logger

# 端末復元のための保険
_terminal_backup = None

try:
    import msvcrt  # Windows用
    WINDOWS_AVAILABLE = True
except ImportError:
    WINDOWS_AVAILABLE = False

try:
    import select  # Unix用
    UNIX_AVAILABLE = True
except ImportError:
    UNIX_AVAILABLE = False


class BackgroundInputMonitor:
    """
    バックグラウンドでキー入力を監視するクラス
    
    ESCキーが押されたときに中断マネージャーに通知する
    """
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.logger = Logger(verbose=verbose)
        self.interrupt_manager = get_interrupt_manager(verbose=verbose)
        
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()  # 簡易ロック
        
        # プラットフォーム判定
        self.is_windows = sys.platform.startswith('win')
        self.can_monitor = WINDOWS_AVAILABLE or UNIX_AVAILABLE
        
        if not self.can_monitor:
            if verbose:
                self.logger.ulog("バックグラウンド入力監視は利用できません", "warning:monitor")
    
    def start_monitoring(self) -> bool:
        """
        バックグラウンド監視を開始
        
        Returns:
            True: 監視開始成功
            False: 監視開始失敗（非対応環境など）
        """
        if not self.can_monitor:
            return False
            
        # 非TTY環境では開始しない
        import sys
        if not sys.stdin.isatty():
            if self.verbose:
                self.logger.ulog("非TTY環境のため、バックグラウンド監視をスキップ", "info:monitor", always_print=True)
            return False
            
        with self._lock:  # ロック保護
            if self._monitoring:
                return True  # 既に監視中
                
            try:
                # 停止ログフラグをリセット
                self._stop_logged = False
                
                self._stop_event.clear()
                self._monitor_thread = threading.Thread(
                    target=self._monitor_loop, 
                    daemon=True,
                    name="ESC-Monitor"
                )
                self._monitor_thread.start()
                self._monitoring = True
                
                if self.verbose:
                    self.logger.ulog("バックグラウンドESC監視を開始", "info:monitor", always_print=True)
                
                return True
                
            except Exception as e:
                if self.verbose:
                    self.logger.ulog(f"バックグラウンド監視開始エラー: {e}", "error:monitor")
                return False
    
    def stop_monitoring(self):
        """バックグラウンド監視を停止"""
        with self._lock:  # ロック保護
            if not self._monitoring:
                if self.verbose:
                    self.logger.ulog("[DEBUG] stop_monitoring called but not monitoring", "debug:monitor", always_print=False)
                return
                
            self._stop_event.set()
            self._monitoring = False
            
            if self._monitor_thread and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=1.0)
            
            if self.verbose:
                # インスタンスレベルでログ制御（より確実）
                if not hasattr(self, '_stop_logged'):
                    self._stop_logged = False
                
                if not self._stop_logged:
                    self._stop_logged = True
                    self.logger.ulog("バックグラウンドESC監視を停止", "info:monitor", always_print=True)
    
    def _monitor_loop(self):
        """バックグラウンド監視のメインループ"""
        try:
            if self.is_windows and WINDOWS_AVAILABLE:
                self._windows_monitor_loop()
            elif UNIX_AVAILABLE:
                self._unix_monitor_loop()
        except Exception as e:
            if self.verbose:
                self.logger.ulog(f"監視ループエラー: {e}", "error:monitor")
    
    def _windows_monitor_loop(self):
        """Windows用の監視ループ"""
        while not self._stop_event.is_set():
            try:
                if msvcrt.kbhit():
                    key = msvcrt.getch()
                    if key == b'\x1b':  # ESCキー
                        self._handle_esc_key()
                
                # 短時間待機
                self._stop_event.wait(0.1)
                
            except Exception as e:
                if self.verbose:
                    self.logger.ulog(f"Windows監視エラー: {e}", "debug:monitor")
                break
    
    def _unix_monitor_loop(self):
        """Unix/Linux用の監視ループ"""
        import termios
        import tty
        
        # 元の端末設定を保存
        fd = sys.stdin.fileno()
        old_settings = None
        
        try:
            old_settings = termios.tcgetattr(fd)
            # 端末復元の保険
            global _terminal_backup
            if _terminal_backup is None:
                _terminal_backup = (fd, old_settings)
                atexit.register(lambda: termios.tcsetattr(fd, termios.TCSADRAIN, old_settings))
            tty.setraw(fd)
            
            while not self._stop_event.is_set():
                try:
                    # 入力待機（タイムアウト付き）
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        key = sys.stdin.read(1)
                        if ord(key) == 27:  # ESCキー
                            self._handle_esc_key()
                
                except Exception as e:
                    if self.verbose:
                        self.logger.ulog(f"Unix監視エラー: {e}", "debug:monitor")
                    break
                    
        finally:
            # 端末設定を復元
            if old_settings:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    
    def _handle_esc_key(self):
        """ESCキーが押されたときの処理"""
        try:
            import time
            now = time.monotonic()
            
            # ダブルESC判定（1.2秒以内）
            if hasattr(self, "_last_esc") and (now - self._last_esc) < 1.2:
                # ダブルESC: 実行中なら即確定
                status = self.interrupt_manager.get_status()
                if status['is_executing']:
                    self.interrupt_manager.request_interrupt()
                    self.interrupt_manager.confirm_interrupt()
                    if self.verbose:
                        self.logger.ulog("[DOUBLE-ESC] 中断確定", "warning:interrupt", always_print=True)
                return
            
            # 重複チェック（既に中断要求中の場合は無視）
            if self.interrupt_manager.is_interrupted():
                return  # 既に中断要求中
            
            # 中断要求を発行
            self.interrupt_manager.request_interrupt()
            self._last_esc = now
            
            if self.verbose:
                self.logger.ulog("[ESC] バックグラウンドESC検知 → 中断要求", "info:interrupt", always_print=True)
                
        except Exception as e:
            if self.verbose:
                self.logger.ulog(f"ESC処理エラー: {e}", "error:monitor")
    
    def is_monitoring(self) -> bool:
        """監視中かどうかを返す"""
        return self._monitoring


# グローバルモニターインスタンス
_global_monitor: Optional[BackgroundInputMonitor] = None
_stop_logged: bool = False  # 重複ログ防止フラグ


def get_background_monitor(verbose: bool = True) -> BackgroundInputMonitor:
    """
    グローバルバックグラウンドモニターのインスタンスを取得
    
    Args:
        verbose: 詳細ログ出力（初回作成時のみ適用）
        
    Returns:
        BackgroundInputMonitorのインスタンス
    """
    global _global_monitor
    
    if _global_monitor is None:
        _global_monitor = BackgroundInputMonitor(verbose=verbose)
    
    return _global_monitor


def start_background_monitoring(verbose: bool = True) -> bool:
    """
    バックグラウンドESC監視を開始
    
    Args:
        verbose: 詳細ログ出力
        
    Returns:
        True: 開始成功, False: 開始失敗
    """
    global _stop_logged
    _stop_logged = False  # 新しい監視開始時にフラグリセット
    monitor = get_background_monitor(verbose=verbose)
    return monitor.start_monitoring()


def stop_background_monitoring():
    """バックグラウンドESC監視を停止"""
    global _global_monitor
    if _global_monitor and _global_monitor.is_monitoring():
        monitor = get_background_monitor(verbose=True)
        monitor.stop_monitoring()