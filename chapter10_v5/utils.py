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
    if sys.platform == "win32":
        os.environ["PYTHONIOENCODING"] = "utf-8"
        
        # Windows環境でのUTF-8エンコーディング問題対策
        # 標準出力をUTF-8でerrors='replace'に設定（絵文字エラー防止）
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except AttributeError:
            # Python 3.7未満の場合のフォールバック
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer,
                encoding='utf-8',
                errors='replace'
            )
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer,
                encoding='utf-8', 
                errors='replace'
            )


class Logger:
    """統一されたログ出力クラス"""
    
    def __init__(self, verbose: bool = True):
        """
        Args:
            verbose: ログ出力を有効にするかどうか
        """
        self.verbose = verbose
    
    def debug(self, message: str):
        """デバッグメッセージ"""
        if self.verbose:
            print(f"[DEBUG] {message}")
    
    def info(self, message: str):
        """情報メッセージ"""
        if self.verbose:
            print(f"[INFO] {message}")
    
    def warning(self, message: str):
        """警告メッセージ"""
        if self.verbose:
            print(f"[WARNING] {message}")
    
    def error(self, message: str):
        """エラーメッセージ"""
        if self.verbose:
            print(f"[ERROR] {message}")
    
    def analysis(self, message: str):
        """分析メッセージ"""
        if self.verbose:
            print(f"[分析] {message}")
    
    def execution(self, message: str):
        """実行メッセージ"""
        if self.verbose:
            print(f"[実行] {message}")
    
    def success(self, message: str):
        """成功メッセージ"""
        if self.verbose:
            print(f"[成功] {message}")
    
    def config_info(self, message: str):
        """設定メッセージ"""
        if self.verbose:
            print(f"[設定] {message}")