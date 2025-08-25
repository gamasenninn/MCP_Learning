#!/usr/bin/env python3
"""
基本的なエラーハンドラー
エラーの分類、リトライ戦略、フォールバック処理を実装
"""

import asyncio
import time
import traceback
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import re

class ErrorSeverity(Enum):
    """エラーの重要度"""
    LOW = "low"          # 無視可能（警告レベル）
    MEDIUM = "medium"    # リトライ推奨
    HIGH = "high"        # 即時対応必要
    CRITICAL = "critical" # システム停止レベル

class ErrorCategory(Enum):
    """エラーのカテゴリ"""
    CONNECTION = "connection"    # 接続エラー
    TIMEOUT = "timeout"          # タイムアウト
    VALIDATION = "validation"    # 検証エラー
    PERMISSION = "permission"    # 権限エラー
    NOT_FOUND = "not_found"      # リソース不在
    RATE_LIMIT = "rate_limit"    # レート制限
    SYNTAX = "syntax"            # 構文エラー
    RUNTIME = "runtime"          # 実行時エラー
    UNKNOWN = "unknown"          # 不明なエラー

@dataclass
class ErrorContext:
    """エラーコンテキスト"""
    error: Exception
    task: str
    operation: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    traceback_str: Optional[str] = None
    
    def __post_init__(self):
        if self.traceback_str is None and self.error:
            self.traceback_str = traceback.format_exc()

@dataclass
class ErrorResolution:
    """エラー解決策"""
    strategy: str  # retry, skip, fallback, abort
    description: str
    severity: ErrorSeverity
    category: ErrorCategory
    retry_params: Optional[Dict[str, Any]] = None
    fallback_action: Optional[Callable] = None
    max_retries: int = 3
    retry_delay: float = 1.0
    exponential_backoff: bool = True

class BasicErrorHandler:
    """基本的なエラーハンドラー"""
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.error_history: List[ErrorContext] = []
        self.error_patterns = self._init_error_patterns()
        self.resolution_cache: Dict[str, ErrorResolution] = {}
        self.error_stats = {
            "total": 0,
            "resolved": 0,
            "retried": 0,
            "skipped": 0,
            "aborted": 0
        }
    
    def _init_error_patterns(self) -> Dict[str, Dict[str, Any]]:
        """エラーパターンを初期化"""
        return {
            # 接続エラー
            r"connection|refused|unreachable|offline": {
                "category": ErrorCategory.CONNECTION,
                "severity": ErrorSeverity.MEDIUM,
                "strategy": "retry",
                "max_retries": 5,
                "retry_delay": 2.0
            },
            # タイムアウトエラー
            r"timeout|timed out|deadline exceeded": {
                "category": ErrorCategory.TIMEOUT,
                "severity": ErrorSeverity.MEDIUM,
                "strategy": "retry",
                "max_retries": 3,
                "retry_delay": 1.0
            },
            # 権限エラー
            r"permission|denied|unauthorized|forbidden": {
                "category": ErrorCategory.PERMISSION,
                "severity": ErrorSeverity.HIGH,
                "strategy": "abort",
                "max_retries": 0
            },
            # リソース不在
            r"not found|404|missing|does not exist": {
                "category": ErrorCategory.NOT_FOUND,
                "severity": ErrorSeverity.MEDIUM,
                "strategy": "skip",
                "max_retries": 1
            },
            # レート制限
            r"rate limit|too many requests|429": {
                "category": ErrorCategory.RATE_LIMIT,
                "severity": ErrorSeverity.LOW,
                "strategy": "retry",
                "max_retries": 5,
                "retry_delay": 5.0,
                "exponential_backoff": True
            },
            # 構文エラー
            r"syntax|parse|invalid format|malformed": {
                "category": ErrorCategory.SYNTAX,
                "severity": ErrorSeverity.HIGH,
                "strategy": "abort",
                "max_retries": 0
            }
        }
    
    def classify_error(self, error: Exception) -> ErrorCategory:
        """エラーを分類"""
        error_str = str(error).lower()
        
        # パターンマッチングでカテゴリを判定
        for pattern, config in self.error_patterns.items():
            if re.search(pattern, error_str):
                return config["category"]
        
        return ErrorCategory.UNKNOWN
    
    def get_severity(self, error: Exception) -> ErrorSeverity:
        """エラーの重要度を判定"""
        error_str = str(error).lower()
        
        # パターンマッチングで重要度を判定
        for pattern, config in self.error_patterns.items():
            if re.search(pattern, error_str):
                return config["severity"]
        
        # デフォルトはMEDIUM
        return ErrorSeverity.MEDIUM
    
    def analyze_error(self, context: ErrorContext) -> ErrorResolution:
        """エラーを分析して解決策を提案"""
        error_str = str(context.error).lower()
        
        # キャッシュチェック
        cache_key = f"{type(context.error).__name__}:{error_str[:100]}"
        if cache_key in self.resolution_cache:
            if self.verbose:
                print(f"[CACHE] 既知のエラーパターンを検出")
            return self.resolution_cache[cache_key]
        
        # パターンマッチングで解決策を決定
        for pattern, config in self.error_patterns.items():
            if re.search(pattern, error_str):
                resolution = ErrorResolution(
                    strategy=config["strategy"],
                    description=f"{config['category'].value}エラーを検出",
                    severity=config["severity"],
                    category=config["category"],
                    max_retries=config.get("max_retries", 3),
                    retry_delay=config.get("retry_delay", 1.0),
                    exponential_backoff=config.get("exponential_backoff", True),
                    retry_params={"error_type": config["category"].value}
                )
                
                # キャッシュに保存
                self.resolution_cache[cache_key] = resolution
                
                if self.verbose:
                    print(f"[分析] {resolution.category.value}エラー (重要度: {resolution.severity.value})")
                    print(f"  戦略: {resolution.strategy}")
                
                return resolution
        
        # デフォルトの解決策
        return ErrorResolution(
            strategy="retry",
            description="不明なエラー - デフォルトリトライ",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.UNKNOWN,
            max_retries=2,
            retry_delay=1.0
        )
    
    async def handle_error(
        self,
        error: Exception,
        task: str,
        operation: Optional[str] = None,
        retry_func: Optional[Callable] = None,
        fallback_func: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """エラーを処理"""
        self.error_stats["total"] += 1
        
        # エラーコンテキストを作成
        context = ErrorContext(
            error=error,
            task=task,
            operation=operation
        )
        self.error_history.append(context)
        
        if self.verbose:
            print(f"\n[エラー処理] {type(error).__name__}: {str(error)[:100]}")
        
        # エラーを分析
        resolution = self.analyze_error(context)
        
        # 戦略に応じた処理
        result = {
            "success": False,
            "strategy": resolution.strategy,
            "error": str(error),
            "category": resolution.category.value,
            "severity": resolution.severity.value
        }
        
        if resolution.strategy == "retry" and retry_func:
            result = await self._handle_retry(
                retry_func, resolution, context
            )
            
        elif resolution.strategy == "fallback" and fallback_func:
            result = await self._handle_fallback(
                fallback_func, resolution, context
            )
            
        elif resolution.strategy == "skip":
            self.error_stats["skipped"] += 1
            if self.verbose:
                print(f"[スキップ] このエラーをスキップします")
            result["success"] = False
            result["action"] = "skipped"
            
        elif resolution.strategy == "abort":
            self.error_stats["aborted"] += 1
            if self.verbose:
                print(f"[中断] 致命的エラーのため処理を中断")
            result["success"] = False
            result["action"] = "aborted"
        
        return result
    
    async def _handle_retry(
        self,
        retry_func: Callable,
        resolution: ErrorResolution,
        context: ErrorContext
    ) -> Dict[str, Any]:
        """リトライ処理"""
        self.error_stats["retried"] += 1
        
        for attempt in range(1, resolution.max_retries + 1):
            if self.verbose:
                print(f"[リトライ] 試行 {attempt}/{resolution.max_retries}")
            
            # バックオフ待機
            if attempt > 1:
                delay = resolution.retry_delay
                if resolution.exponential_backoff:
                    delay = resolution.retry_delay * (2 ** (attempt - 1))
                
                if self.verbose:
                    print(f"  待機中... ({delay:.1f}秒)")
                await asyncio.sleep(delay)
            
            try:
                # リトライ実行
                result = await retry_func()
                
                self.error_stats["resolved"] += 1
                if self.verbose:
                    print(f"[成功] リトライ {attempt}回目で成功")
                
                return {
                    "success": True,
                    "strategy": "retry",
                    "attempts": attempt,
                    "result": result
                }
                
            except Exception as e:
                if self.verbose:
                    print(f"  失敗: {str(e)[:100]}")
                
                if attempt == resolution.max_retries:
                    if self.verbose:
                        print(f"[失敗] 最大リトライ回数に到達")
                    return {
                        "success": False,
                        "strategy": "retry",
                        "attempts": attempt,
                        "error": str(e)
                    }
    
    async def _handle_fallback(
        self,
        fallback_func: Callable,
        resolution: ErrorResolution,
        context: ErrorContext
    ) -> Dict[str, Any]:
        """フォールバック処理"""
        if self.verbose:
            print(f"[フォールバック] 代替処理を実行")
        
        try:
            result = await fallback_func()
            self.error_stats["resolved"] += 1
            
            return {
                "success": True,
                "strategy": "fallback",
                "result": result
            }
            
        except Exception as e:
            if self.verbose:
                print(f"[失敗] フォールバックも失敗: {e}")
            
            return {
                "success": False,
                "strategy": "fallback",
                "error": str(e)
            }
    
    def get_statistics(self) -> Dict[str, Any]:
        """エラー統計を取得"""
        stats = self.error_stats.copy()
        
        # エラーカテゴリ別の集計
        category_counts = {}
        severity_counts = {}
        
        for context in self.error_history:
            category = self.classify_error(context.error)
            severity = self.get_severity(context.error)
            
            category_counts[category.value] = category_counts.get(category.value, 0) + 1
            severity_counts[severity.value] = severity_counts.get(severity.value, 0) + 1
        
        stats["by_category"] = category_counts
        stats["by_severity"] = severity_counts
        stats["resolution_rate"] = (
            (stats["resolved"] / stats["total"] * 100) if stats["total"] > 0 else 0
        )
        
        return stats
    
    def get_report(self) -> str:
        """エラーレポートを生成"""
        stats = self.get_statistics()
        
        report_lines = ["エラー処理レポート", "=" * 50]
        
        # 基本統計
        report_lines.append("\n[基本統計]")
        report_lines.append(f"  総エラー数: {stats['total']}")
        report_lines.append(f"  解決済み: {stats['resolved']}")
        report_lines.append(f"  リトライ: {stats['retried']}")
        report_lines.append(f"  スキップ: {stats['skipped']}")
        report_lines.append(f"  中断: {stats['aborted']}")
        report_lines.append(f"  解決率: {stats['resolution_rate']:.1f}%")
        
        # カテゴリ別
        if stats["by_category"]:
            report_lines.append("\n[カテゴリ別]")
            for category, count in stats["by_category"].items():
                report_lines.append(f"  {category}: {count}")
        
        # 重要度別
        if stats["by_severity"]:
            report_lines.append("\n[重要度別]")
            for severity, count in stats["by_severity"].items():
                report_lines.append(f"  {severity}: {count}")
        
        # 最近のエラー
        if self.error_history:
            report_lines.append("\n[最近のエラー]")
            for context in self.error_history[-5:]:
                report_lines.append(f"  - {context.task}: {str(context.error)[:50]}")
        
        return "\n".join(report_lines)


# テスト用の関数
async def test_error_handler():
    """エラーハンドラーのテスト"""
    print("エラーハンドラーのテスト開始\n")
    
    handler = BasicErrorHandler(verbose=True)
    
    # テスト1: 接続エラー
    print("=" * 50)
    print("テスト1: 接続エラー")
    
    async def connection_task():
        raise ConnectionError("Server connection refused")
    
    retry_count = 0
    async def retry_connection():
        nonlocal retry_count
        retry_count += 1
        if retry_count < 3:
            raise ConnectionError("Still refusing connection")
        return "Connection successful!"
    
    result = await handler.handle_error(
        ConnectionError("Server connection refused"),
        task="データベース接続",
        operation="connect",
        retry_func=retry_connection
    )
    print(f"結果: {result}\n")
    
    # テスト2: タイムアウトエラー
    print("=" * 50)
    print("テスト2: タイムアウトエラー")
    
    result = await handler.handle_error(
        TimeoutError("Request timed out after 30s"),
        task="API呼び出し",
        operation="fetch_data"
    )
    print(f"結果: {result}\n")
    
    # テスト3: 権限エラー
    print("=" * 50)
    print("テスト3: 権限エラー")
    
    result = await handler.handle_error(
        PermissionError("Access denied to resource"),
        task="ファイル読み込み",
        operation="read_file"
    )
    print(f"結果: {result}\n")
    
    # テスト4: レート制限エラー
    print("=" * 50)
    print("テスト4: レート制限エラー")
    
    async def rate_limited_task():
        await asyncio.sleep(0.1)
        return "API call successful"
    
    result = await handler.handle_error(
        Exception("429 Too many requests"),
        task="API大量呼び出し",
        retry_func=rate_limited_task
    )
    print(f"結果: {result}\n")
    
    # レポート表示
    print("=" * 50)
    print(handler.get_report())
    
    return handler.get_statistics()


if __name__ == "__main__":
    asyncio.run(test_error_handler())