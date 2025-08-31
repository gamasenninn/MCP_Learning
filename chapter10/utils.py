#!/usr/bin/env python3
"""
Utility functions for MCP Agent
共通ユーティリティ関数
"""

import sys
import os
import io
from typing import Any


def safe_str(obj: Any, use_repr: bool = False) -> str:
    """
    オブジェクトをサロゲート文字を除去して文字列化（最適化版）
    
    Args:
        obj: 文字列に変換するオブジェクト
        use_repr: Trueならrepr()、Falseならstr()を使用
        
    Returns:
        サロゲート文字が除去された文字列
    """
    text = repr(obj) if use_repr else str(obj)
    if not isinstance(text, str):
        return text
    
    # Windows環境でのcp932エンコーディング処理（高速化）
    if sys.platform == "win32":
        try:
            # エンコード/デコードによる一括変換
            return text.encode('cp932', errors='replace').decode('cp932')
        except Exception:
            # フォールバック: 従来の文字ごと処理
            pass
    
    # サロゲート文字のみ除去（非Windows環境またはcp932処理失敗時）
    return ''.join(
        char if not (0xD800 <= ord(char) <= 0xDFFF) else '?'
        for char in text
    )


def setup_windows_encoding():
    """Windows環境でのUnicode対応設定"""
    if sys.platform != "win32":
        return
    
    os.environ["PYTHONIOENCODING"] = "utf-8"
    
    # 標準出力/エラー出力の再設定を共通化
    for stream_name in ['stdout', 'stderr']:
        stream = getattr(sys, stream_name)
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except AttributeError:
            # Python 3.7未満のフォールバック
            wrapper = io.TextIOWrapper(
                stream.buffer,
                encoding='utf-8',
                errors='replace'
            )
            setattr(sys, stream_name, wrapper)


class Logger:
    """統一されたログ出力クラス"""
    
    LEVELS = {
        'debug': 'DEBUG',
        'info': 'INFO',
        'warning': 'WARNING',
        'error': 'ERROR'
    }
    
    # ログレベルの優先度
    LEVEL_PRIORITY = {
        'DEBUG': 10,
        'INFO': 20,
        'WARNING': 30,
        'ERROR': 40
    }
    
    def __init__(self, verbose: bool = True, log_level: str = "INFO"):
        """
        Args:
            verbose: ログ出力を有効にするかどうか
            log_level: 出力する最小ログレベル (DEBUG/INFO/WARNING/ERROR)
        """
        self.verbose = verbose
        self.log_level = log_level.upper()
        self.min_priority = self.LEVEL_PRIORITY.get(self.log_level, 20)
    
    def log(self, level: str, message: str):
        """統一ログ出力メソッド"""
        if self.verbose:
            level_name = self.LEVELS.get(level, level.upper())
            print(f"[{level_name}] {message}")
    
    def debug(self, message: str):
        """デバッグメッセージ"""
        self.log('debug', message)
    
    def info(self, message: str):
        """情報メッセージ"""
        self.log('info', message)
    
    def warning(self, message: str):
        """警告メッセージ"""
        self.log('warning', message)
    
    def error(self, message: str):
        """エラーメッセージ"""
        self.log('error', message)
    
    def should_log(self, level: str) -> bool:
        """指定レベルのログを出力すべきか判定"""
        level = level.upper()
        priority = self.LEVEL_PRIORITY.get(level, 20)
        return priority >= self.min_priority
    
    def ulog(self, message: str, level: str = "info", always_print: bool = False) -> None:
        """
        統一ログ出力メソッド (unified log)
        
        Args:
            message: ログメッセージ
            level: ログレベル（形式: "loglevel" または "loglevel:prefix"）
                   例: "info", "error", "info:session", "warning:interrupt"
            always_print: Trueの場合、verbose設定に関わらず表示
        """
        # ログレベルとプレフィックスの分離
        parts = level.split(':', 1)
        log_level = parts[0]
        prefix_key = parts[1] if len(parts) > 1 else None
        
        # ログレベル判定（always_printの場合は無視）
        if not self.should_log(log_level) and not always_print:
            return
            
        # コンソール出力
        if self.verbose or always_print:
            if prefix_key:
                prefixes = {
                    "session": "[セッション]",
                    "request": "[リクエスト]", 
                    "restore": "[復元]",
                    "pause": "[セッション一時停止]",
                    "resume": "[セッション再開]",
                    "clear": "[セッションクリア]",
                    "esc": "[ESC]",
                    "interrupt": "[中断]",
                    "warning": "[警告]",
                    "error": "[エラー]",
                    "info": "[情報]",
                    "retry": "[リトライ]",
                    "config": "[設定]",
                    "instruction": "[指示書]",
                }
                prefix = prefixes.get(prefix_key, f"[{prefix_key.upper()}]")
                print(f"{prefix} {message}")
            else:
                print(message)
    
