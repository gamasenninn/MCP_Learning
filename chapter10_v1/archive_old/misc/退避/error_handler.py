"""
エラーハンドラー
LLMを使用してエラーを分析し、適切な対処法を決定
"""

import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from llm_client import get_llm_client
import traceback

logger = logging.getLogger(__name__)

class ErrorSeverity(Enum):
    """エラーの重要度"""
    LOW = "low"        # 無視可能
    MEDIUM = "medium"  # リトライ推奨
    HIGH = "high"      # 即時対応必要
    CRITICAL = "critical"  # システム停止レベル

@dataclass
class ErrorContext:
    """エラーコンテキスト"""
    error: Exception
    task: str
    step: Optional[str] = None
    tool: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    traceback: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.traceback is None and self.error:
            self.traceback = traceback.format_exc()

@dataclass
class ErrorResolution:
    """エラー解決策"""
    strategy: str  # retry, skip, fallback, abort
    description: str
    severity: ErrorSeverity
    retry_params: Optional[Dict[str, Any]] = None
    fallback_action: Optional[str] = None
    max_retries: int = 3
    
class LLMErrorHandler:
    """
    LLMを使用したインテリジェントエラーハンドラー
    """
    
    def __init__(self, llm_client=None):
        self.llm = llm_client or get_llm_client()
        self.error_history: List[ErrorContext] = []
        self.resolution_cache: Dict[str, ErrorResolution] = {}
        
    async def handle_error(self, context: ErrorContext) -> ErrorResolution:
        """
        エラーを分析して解決策を提案
        
        Args:
            context: エラーコンテキスト
            
        Returns:
            エラー解決策
        """
        logger.error(f"[ERROR] Handling: {type(context.error).__name__}: {str(context.error)}")
        
        # エラー履歴に追加
        self.error_history.append(context)
        
        # キャッシュチェック
        cache_key = self._get_cache_key(context)
        if cache_key in self.resolution_cache:
            logger.info("[CACHE] Using cached error resolution")
            return self.resolution_cache[cache_key]
        
        # LLMで分析
        resolution = await self._analyze_with_llm(context)
        
        # キャッシュに保存
        self.resolution_cache[cache_key] = resolution
        
        logger.info(f"[RESOLUTION] Strategy: {resolution.strategy}, Severity: {resolution.severity.value}")
        return resolution
    
    def _get_cache_key(self, context: ErrorContext) -> str:
        """エラーのキャッシュキーを生成"""
        error_type = type(context.error).__name__
        error_msg = str(context.error)[:100]  # 最初の100文字
        return f"{error_type}:{error_msg}:{context.tool}"
    
    async def _analyze_with_llm(self, context: ErrorContext) -> ErrorResolution:
        """LLMを使用してエラーを分析"""
        
        prompt = self._build_error_prompt(context)
        
        response = await self.llm.complete(
            prompt,
            system=self._get_system_prompt(),
            temperature=0.3
        )
        
        return self._parse_resolution(response.content, context)
    
    def _get_system_prompt(self) -> str:
        """システムプロンプト"""
        return """You are an expert error handler for an AI agent system.
Analyze errors and provide appropriate resolution strategies.

Guidelines:
1. Determine error severity (low, medium, high, critical)
2. Choose strategy: retry (with modifications), skip, fallback, or abort
3. For retry: suggest parameter adjustments
4. For fallback: suggest alternative actions
5. Consider error patterns and history

Output format:
{
    "severity": "low|medium|high|critical",
    "strategy": "retry|skip|fallback|abort",
    "description": "Clear explanation of the resolution",
    "retry_params": {"adjusted parameters if retry"},
    "fallback_action": "alternative action if fallback",
    "max_retries": 3
}"""
    
    def _build_error_prompt(self, context: ErrorContext) -> str:
        """エラー分析用プロンプトを構築"""
        
        # 最近のエラーパターンを取得
        recent_errors = self._get_recent_error_patterns()
        
        prompt = f"""Error Analysis Request:

Error Type: {type(context.error).__name__}
Error Message: {str(context.error)}
Task: {context.task}
Step: {context.step or 'Unknown'}
Tool: {context.tool or 'None'}
Parameters: {json.dumps(context.params or {}, indent=2)}

Traceback (last 5 lines):
{self._get_traceback_summary(context.traceback)}

Recent Error Patterns:
{recent_errors}

Please analyze this error and provide a resolution strategy.
Consider if this is a transient issue that can be retried, or if we need an alternative approach."""
        
        return prompt
    
    def _get_traceback_summary(self, tb: str, lines: int = 5) -> str:
        """トレースバックの要約を取得"""
        if not tb:
            return "No traceback available"
        
        tb_lines = tb.strip().split('\n')
        return '\n'.join(tb_lines[-lines:])
    
    def _get_recent_error_patterns(self, limit: int = 3) -> str:
        """最近のエラーパターンを取得"""
        if not self.error_history:
            return "No recent errors"
        
        patterns = []
        for err in self.error_history[-limit:]:
            patterns.append(f"- {type(err.error).__name__}: {str(err.error)[:50]}...")
        
        return '\n'.join(patterns)
    
    def _parse_resolution(self, response: str, context: ErrorContext) -> ErrorResolution:
        """LLMレスポンスをパース"""
        
        try:
            # JSONを抽出
            import re
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = response
            
            data = json.loads(json_str)
            
            return ErrorResolution(
                strategy=data.get("strategy", "retry"),
                description=data.get("description", "Retry with default parameters"),
                severity=ErrorSeverity(data.get("severity", "medium")),
                retry_params=data.get("retry_params"),
                fallback_action=data.get("fallback_action"),
                max_retries=data.get("max_retries", 3)
            )
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"[WARN] Failed to parse resolution: {e}")
            return self._create_default_resolution(context)
    
    def _create_default_resolution(self, context: ErrorContext) -> ErrorResolution:
        """デフォルトの解決策を作成"""
        
        error_type = type(context.error).__name__
        
        # エラータイプ別のデフォルト戦略
        if "Timeout" in error_type:
            return ErrorResolution(
                strategy="retry",
                description="Retry with increased timeout",
                severity=ErrorSeverity.MEDIUM,
                retry_params={"timeout": 60},
                max_retries=2
            )
        elif "Connection" in error_type or "Network" in error_type:
            return ErrorResolution(
                strategy="retry",
                description="Retry after network delay",
                severity=ErrorSeverity.MEDIUM,
                retry_params={"delay": 5},
                max_retries=3
            )
        elif "Permission" in error_type or "Access" in error_type:
            return ErrorResolution(
                strategy="abort",
                description="Permission denied, cannot proceed",
                severity=ErrorSeverity.HIGH
            )
        else:
            return ErrorResolution(
                strategy="retry",
                description="Generic retry strategy",
                severity=ErrorSeverity.MEDIUM,
                max_retries=2
            )
    
    async def learn_from_outcome(
        self,
        context: ErrorContext,
        resolution: ErrorResolution,
        success: bool
    ):
        """
        エラー解決の結果から学習
        
        Args:
            context: エラーコンテキスト
            resolution: 実行した解決策
            success: 成功したかどうか
        """
        if success:
            logger.info(f"[LEARN] Successful resolution: {resolution.strategy}")
            # 成功した解決策の重みを増やす（将来の実装用）
        else:
            logger.info(f"[LEARN] Failed resolution: {resolution.strategy}")
            # 失敗した解決策をキャッシュから削除
            cache_key = self._get_cache_key(context)
            if cache_key in self.resolution_cache:
                del self.resolution_cache[cache_key]

# エラーリトライデコレーター
def with_retry(max_retries: int = 3, delay: float = 1.0):
    """
    リトライ機能付きデコレーター
    
    Args:
        max_retries: 最大リトライ回数
        delay: リトライ間隔（秒）
    """
    import asyncio
    from functools import wraps
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        logger.warning(f"[RETRY] Attempt {attempt + 1} failed: {e}")
                        await asyncio.sleep(delay * (attempt + 1))
                    else:
                        logger.error(f"[FAIL] All {max_retries} attempts failed")
            raise last_error
        return wrapper
    return decorator

# 使用例とテスト
async def test_error_handler():
    """エラーハンドラーのテスト"""
    
    handler = LLMErrorHandler()
    
    # テストケース1: タイムアウトエラー
    print("\n" + "="*60)
    print("Test Case 1: Timeout Error")
    print("="*60)
    
    timeout_context = ErrorContext(
        error=TimeoutError("Request timed out after 30 seconds"),
        task="Fetch data from API",
        step="api_call",
        tool="web_api",
        params={"url": "https://api.example.com/data", "timeout": 30}
    )
    
    resolution = await handler.handle_error(timeout_context)
    print(f"Strategy: {resolution.strategy}")
    print(f"Description: {resolution.description}")
    print(f"Severity: {resolution.severity.value}")
    if resolution.retry_params:
        print(f"Retry params: {resolution.retry_params}")
    
    # テストケース2: 権限エラー
    print("\n" + "="*60)
    print("Test Case 2: Permission Error")
    print("="*60)
    
    permission_context = ErrorContext(
        error=PermissionError("Access denied to /secure/data"),
        task="Read secure file",
        step="file_read",
        tool="file_system",
        params={"path": "/secure/data"}
    )
    
    resolution = await handler.handle_error(permission_context)
    print(f"Strategy: {resolution.strategy}")
    print(f"Description: {resolution.description}")
    print(f"Severity: {resolution.severity.value}")
    
    # テストケース3: 一般的なエラー
    print("\n" + "="*60)
    print("Test Case 3: Generic Error")
    print("="*60)
    
    generic_context = ErrorContext(
        error=ValueError("Invalid JSON format"),
        task="Parse API response",
        step="json_parse",
        tool="data_processor",
        params={"data": "{invalid json}"}
    )
    
    resolution = await handler.handle_error(generic_context)
    print(f"Strategy: {resolution.strategy}")
    print(f"Description: {resolution.description}")
    
    # 学習のテスト
    await handler.learn_from_outcome(timeout_context, resolution, True)
    
    # リトライデコレーターのテスト
    @with_retry(max_retries=3, delay=0.5)
    async def flaky_function():
        import random
        if random.random() < 0.7:
            raise ConnectionError("Random connection error")
        return "Success!"
    
    print("\n" + "="*60)
    print("Test Case 4: Retry Decorator")
    print("="*60)
    
    try:
        result = await flaky_function()
        print(f"Result: {result}")
    except Exception as e:
        print(f"Failed after retries: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_error_handler())