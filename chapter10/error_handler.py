#!/usr/bin/env python3
"""
Error Handler for MCP Agent
エラー処理の一元管理司令塔

すべてのエラー処理をこのクラスで統一管理：
- エラー分類
- LLMによるパラメータ修正
- リトライ処理
- エラーログ出力
"""

import asyncio
import json
import re
import time
from typing import Dict, Any, Optional, Callable, List, Union
from openai import AsyncOpenAI

from config_manager import Config
from utils import safe_str, Logger


class ErrorHandler:
    """
    エラー処理司令塔クラス
    
    すべてのエラー処理を一元管理し、適切な対応を自動選択
    """
    
    # エラーパターン定義
    ERROR_PATTERNS = {
        'PARAM_ERROR': {
            'indicators': [
                '404', 'not found', 'invalid parameter', '400', 'bad request',
                'parameter', 'argument', 'invalid input', 'validation error',
                'no such column', 'no such table', 'syntax error'
            ],
            'stat_key': 'param_errors'
        },
        'TRANSIENT_ERROR': {
            'indicators': [
                'timeout', 'connection', '503', '500', '502', '504',
                'network', 'temporary', 'unavailable', 'retry'
            ],
            'stat_key': 'transient_errors'
        }
    }
    
    def __init__(self, config: Config, llm: Optional[AsyncOpenAI] = None, verbose: bool = True):
        """
        Args:
            config: 設定辞書またはConfigオブジェクト
            llm: OpenAI LLMクライアント（パラメータ修正用）
            verbose: 詳細ログ出力
        """
        self.config = config
        self.llm = llm
        self.verbose = verbose
        self.logger = Logger(verbose=verbose)
        self.current_user_query = ""
        
        # エラー統計
        self.error_stats = {
            "total_errors": 0,
            "param_errors": 0,
            "transient_errors": 0,
            "unknown_errors": 0,
            "auto_fixed": 0,
            "retry_success": 0
        }
        
        # 試行履歴（無限ループ防止用）
        self.attempt_history = []
    
    def classify_error(self, error_msg: str) -> str:
        """
        エラーメッセージを分類
        
        Args:
            error_msg: エラーメッセージ
            
        Returns:
            エラーの分類 (PARAM_ERROR, TRANSIENT_ERROR, UNKNOWN)
        """
        error_lower = error_msg.lower()
        
        # パターンマッチングによる分類
        for error_type, config in self.ERROR_PATTERNS.items():
            if any(indicator in error_lower for indicator in config['indicators']):
                self.error_stats[config['stat_key']] += 1
                return error_type
        
        # いずれにも該当しない場合
        self.error_stats["unknown_errors"] += 1
        return "UNKNOWN"
    
    async def fix_params_with_llm(
        self, 
        tool: str, 
        params: Dict, 
        error_msg: str, 
        tools_info: str
    ) -> Optional[Dict]:
        """
        LLMを使ってパラメータを修正
        
        Args:
            tool: ツール名
            params: 元のパラメータ
            error_msg: エラーメッセージ
            tools_info: 利用可能なツール情報
            
        Returns:
            修正されたパラメータ（修正できない場合はNone）
        """
        if not self.llm:
            if self.verbose:
                self.logger.ulog("LLMが利用できないため自動修正をスキップ", "info:correction")
            return None
        
        try:
            prompt = f"""ツール実行時にエラーが発生しました。パラメータを修正してください。

## エラー情報
ツール: {tool}
エラーメッセージ: {error_msg}
現在のパラメータ: {json.dumps(params, ensure_ascii=False)}

## 利用可能なツール定義
{tools_info}

## 修正指針
1. エラーメッセージを分析してパラメータの問題を特定
2. ツール定義を確認して正しいパラメータ形式を理解
3. 一般的な修正パターン：
   - 日本語パラメータ → 英語に変換（例：「北京」→「Beijing」）
   - テーブル・カラム名の修正
   - 型変換（文字列 ↔ 数値）
   - 必須パラメータの追加

## 出力形式
修正可能な場合：
```json
{{"修正成功": true, "params": {{修正されたパラメータ}}}}
```

修正不可能な場合：
```json
{{"修正成功": false, "理由": "修正できない理由"}}
```"""

            response = await self.llm.chat.completions.create(
                model=self.config.llm.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1  # 低温度で安定した修正
            )
            
            response_text = response.choices[0].message.content
            
            # JSONブロックを抽出
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
                if result.get("修正成功"):
                    self.error_stats["auto_fixed"] += 1
                    if self.verbose:
                        self.logger.ulog(f"パラメータを自動修正: {result.get('params')}", "info:correction")
                    return result.get("params")
            
            if self.verbose:
                self.logger.ulog(f"LLM応答の解析に失敗: {response_text[:100]}...", "error:correction")
            
            return None
            
        except Exception as e:
            if self.verbose:
                self.logger.ulog(f"パラメータ修正に失敗: {e}", "error:correction")
            return None
    
    async def execute_with_retry(
        self, 
        tool: str, 
        params: Dict, 
        execute_func: Callable,
        tools_info_func: Optional[Callable] = None
    ) -> Any:
        """
        リトライ機能付きでツール実行
        
        Args:
            tool: ツール名
            params: パラメータ
            execute_func: 実行関数
            tools_info_func: ツール情報取得関数（パラメータ修正用）
            
        Returns:
            実行結果
            
        Raises:
            Exception: 全てのリトライに失敗した場合
        """
        max_retries = self.config.execution.max_retries
        original_params = params.copy()  # 元のパラメータを保持
        
        for attempt in range(max_retries + 1):
            try:
                result = await execute_func(tool, params)
                
                # デバッグ：error_handlerでの結果チェック
                if isinstance(result, str):
                    surrogate_count = sum(1 for char in result if 0xD800 <= ord(char) <= 0xDFFF)
                    if surrogate_count > 0:
                        self.logger.ulog(f"Found {surrogate_count} surrogate characters in result", "info:correction")
                        for i, char in enumerate(result):
                            if 0xD800 <= ord(char) <= 0xDFFF:
                                self.logger.ulog(f"First surrogate at position {i}: {repr(char)} (U+{ord(char):04X})", "info:correction")
                                break
                
                # 成功時のログ
                if attempt > 0:
                    self.error_stats["retry_success"] += 1
                    if self.verbose:
                        self.logger.ulog(f"{attempt}回目のリトライで成功しました", "info:success")
                
                return result
                
            except Exception as e:
                self.error_stats["total_errors"] += 1
                # エラーメッセージからサロゲート文字を除去
                error_msg = safe_str(str(e))
                error_type = self.classify_error(error_msg)
                
                if self.verbose:
                    self.logger.ulog(f"{error_type}: {error_msg}", "info:classification")
                
                # 最後の試行の場合は例外を投げる
                if attempt >= max_retries:
                    if self.verbose:
                        self.logger.ulog(f"最大リトライ回数({max_retries})に到達", "error:failed")
                    raise e
                
                # エラータイプに応じた処理
                if error_type == "PARAM_ERROR":
                    # パラメータエラーの場合、LLMで修正を試みる
                    if self.config.error_handling.auto_correct_params:
                        self.logger.ulog("パラメータエラーを検出 - LLMで修正を試みます", "info:analysis", show_level=True)
                        
                        if tools_info_func:
                            tools_info = tools_info_func()
                            corrected_params = await self.fix_params_with_llm(
                                tool, params, error_msg, tools_info
                            )
                            
                            if corrected_params and corrected_params != params:
                                params = corrected_params
                                if self.verbose:
                                    safe_params = safe_str(str(params))
                                    self.logger.ulog(f"パラメータを修正しました: {safe_params}", "info:correction")
                                # パラメータ修正後は残り試行回数を制限（無限ループ防止）
                                max_retries = min(max_retries, attempt + 2)
                            else:
                                if self.verbose:
                                    self.logger.ulog("パラメータの自動修正に失敗", "error:correction")
                                # 修正できない場合は即座に失敗
                                raise e
                        else:
                            # ツール情報が取得できない場合は即座に失敗
                            if self.verbose:
                                self.logger.ulog("ツール情報が取得できないため修正不可", "error:correction")
                            raise e
                    else:
                        # 自動修正が無効の場合は即座に失敗
                        raise e
                
                elif error_type == "TRANSIENT_ERROR":
                    # 一時的エラーの場合は通常のリトライ
                    if self.verbose:
                        self.logger.ulog(f"一時的エラー - {attempt + 1}/{max_retries}", "info:retry")
                    retry_interval = self.config.error_handling.retry_interval
                    await asyncio.sleep(retry_interval)
                
                else:
                    # 不明なエラーの場合は短時間リトライ
                    if self.verbose:
                        self.logger.ulog(f"不明なエラー - {attempt + 1}/{max_retries}", "info:retry")
                    await asyncio.sleep(0.5)
    
    def log_error(self, context: str, error: Exception, level: str = "ERROR"):
        """
        エラーログを統一形式で出力
        
        Args:
            context: エラー発生コンテキスト
            error: 例外オブジェクト
            level: ログレベル
        """
        if self.verbose:
            self.logger.ulog(f"{context}: {str(error)}", f"{level}:error")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """エラー統計情報を取得"""
        total = self.error_stats["total_errors"]
        if total == 0:
            success_rate = 100.0
        else:
            success_rate = (self.error_stats["retry_success"] + self.error_stats["auto_fixed"]) / total * 100
        
        return {
            **self.error_stats,
            "success_rate": round(success_rate, 1)
        }
    
    def build_judgment_prompt(
        self, 
        tool: str, 
        current_params: Dict,
        original_params: Dict,
        result: Any,
        attempt: int,
        max_retries: int,
        description: str,
        current_user_query: str = None,
        execution_context: List[Dict] = None
    ) -> str:
        """LLM判断用プロンプトの生成"""
        # 結果を安全な文字列に変換
        result_str = safe_str(result)
        current_params_str = safe_str(current_params)
        original_params_str = safe_str(original_params)
        
        # ユーザークエリを決定
        if current_user_query is None:
            current_user_query = self.current_user_query or "（不明）"
        
        # 実行履歴の構築
        execution_history_str = ""
        if execution_context and len(execution_context) > 0:
            history_lines = []
            for i, ctx in enumerate(execution_context, 1):
                tool_name = ctx.get("tool", "不明")
                desc = ctx.get("description", "")
                result = ctx.get("result", "")
                # 結果を短縮（200文字以内）
                short_result = safe_str(result)[:200]
                if len(str(result)) > 200:
                    short_result += "..."
                history_lines.append(f"{i}. ツール: {tool_name} | 説明: {desc} | 結果: {short_result}")
            execution_history_str = "\n".join(history_lines)
        else:
            execution_history_str = "関連する実行履歴はありません"
        
        # 試行履歴の構築（無限ループ防止用）
        attempt_history_str = ""
        if self.attempt_history and len(self.attempt_history) > 0:
            attempt_lines = []
            for i, attempt_info in enumerate(self.attempt_history, 1):
                attempt_num = attempt_info.get("attempt", i)
                params = attempt_info.get("params", {})
                result = attempt_info.get("result", "")
                # パラメータと結果を短縮
                short_params = safe_str(params)[:150]
                short_result = safe_str(result)[:100]
                if len(str(params)) > 150:
                    short_params += "..."
                if len(str(result)) > 100:
                    short_result += "..."
                attempt_lines.append(f"試行{attempt_num}: パラメータ={short_params} → 結果={short_result}")
            attempt_history_str = "\n".join(attempt_lines)
        else:
            attempt_history_str = "過去の試行履歴はありません"
        
        return f"""あなたはツール実行結果を判断するエキスパートです。以下の実行結果を分析してください。

## 現在実行中のタスク
タスク: {description or "タスクの説明なし"}

## 実行情報
- ツール名: {tool}
- 現在のパラメータ: {current_params_str}
- 元のパラメータ: {original_params_str}
- 試行回数: {attempt}/{max_retries + 1}
- ユーザーの要求: {current_user_query}

## 関連する実行履歴
{execution_history_str}

## 過去の試行履歴（このタスクの）
{attempt_history_str}

## 実行結果
{result_str}

## 判断基準
1. **成功判定**: 
   - 有効なデータが含まれている（空でない結果）
   - エラーメッセージが含まれていない
   - 期待される形式の結果が得られている

2. **失敗判定**:
   - 結果が空文字列（""）、空配列（[]）、または"{{}}"
   - エラーメッセージ、構文エラー、実行エラーが含まれている
   - "no such column", "no such table"などのデータベースエラー
   - 予期しない空の応答や無効な形式

3. **リトライ判定**: パラメータを修正すれば成功する可能性がある
   - データベースクエリ: カラム名・テーブル名の修正（例: product_name → name）
   - API呼び出し: パラメータ形式の修正（例: 都市名に国コード追加）
   - コード実行: 構文エラーの修正

## **重要**: パラメータ修正時のルール
- **現在実行中のタスクの目的を必ず尊重してください**
- 修正は元のパラメータ（{original_params_str}）を基準に行ってください
- 他のタスクのパラメータに変更してはいけません
- **無限ループ防止**: 過去の試行履歴で既に試したパラメータは避けてください
- 同じエラーパターンが繰り返される場合は、根本的に異なるアプローチを提案してください
- 例：都市名に国コードを追加（例："Tokyo" → "Tokyo, JP"）

## 出力形式（JSON）
{{
    "is_success": boolean,
    "needs_retry": boolean,
    "error_reason": "エラーの理由（失敗時のみ）",
    "corrected_params": {{元のパラメータを基準とした修正案}},
    "processed_result": "ユーザー向けの整形済み結果",
    "summary": "実行結果の要約"
}}

## 修正例
- 構文エラー → コードを正しい構文に修正
- 都市名エラー → 国コード付きに修正
- 日本語パラメータ → 英語に変換
- セミコロン記法 → 複数行に分解
- データベースクエリの空の結果 → テーブル構造を確認してクエリを修正
- 存在しないカラム名 → 実際のカラム名に置換（例: product_name → name）

## データベースクエリのヒント（該当する場合のみ）
- 存在しないカラムエラーの場合、テーブル間の関係を確認
- 集計データが必要な場合、適切なJOINを検討

## 基本的なJOIN構文例
- 基本JOIN: `SELECT a.col, b.col FROM table1 a JOIN table2 b ON a.id = b.foreign_id`
- 集計JOIN: `SELECT a.name, SUM(b.amount) FROM table1 a JOIN table2 b ON a.id = b.foreign_id GROUP BY a.name`
- ソート: `ORDER BY SUM(b.amount) DESC`"""
    
    def _get_llm_params(self, **kwargs) -> Dict:
        """モデルに応じたパラメータを生成"""
        model = self.config.llm.model
        params = {"model": model, **kwargs}
        
        if model.startswith("gpt-5"):
            # GPT-5系の設定
            params["max_completion_tokens"] = self.config.llm.max_completion_tokens
            params["reasoning_effort"] = self.config.llm.reasoning_effort
            
            # GPT-5系はtemperature=1のみサポート
            if "temperature" in params:
                params["temperature"] = 1.0
        
        return params
    
    async def call_llm_for_judgment(self, prompt: str) -> Dict:
        """LLMに判断を依頼してJSON結果を返す"""
        try:
            params = self._get_llm_params(
                messages=[{"role": "system", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            response = await self.llm.chat.completions.create(**params)
            
            raw_response = response.choices[0].message.content
            self.logger.ulog(f"{safe_str(raw_response)[:500]}", "debug:llm_response", show_level=True)
            
            return json.loads(raw_response)
            
        except Exception as e:
            self.logger.ulog(f"{e}", "error:llm_error", show_level=True)
            # フォールバック: 成功として扱う
            return {
                "is_success": True,
                "needs_retry": False,
                "processed_result": "LLM判断に失敗しました。結果をそのまま表示します。",
                "summary": "LLM判断エラーによるフォールバック"
            }
    
    def log_judgment_result(self, judgment: Dict):
        """判断結果の詳細ログ出力"""
        self.logger.ulog(f"成功: {judgment.get('is_success')}, リトライ必要: {judgment.get('needs_retry')}", "info:llm_judgment", show_level=True)
        
        if judgment.get('needs_retry'):
            self.logger.ulog(f"{judgment.get('error_reason', '不明')}", "info:llm_reason", show_level=True)
            if judgment.get('corrected_params'):
                self.logger.ulog(f"{safe_str(judgment.get('corrected_params'))[:200]}", "info:llm_correction", show_level=True)
        else:
            self.logger.ulog(f"リトライ不要 - {judgment.get('summary', '詳細不明')}", "info:llm_judgment", show_level=True)
    
    async def judge_and_process_result(
        self, 
        tool: str, 
        current_params: Dict,
        original_params: Dict, 
        result: Any,
        attempt: int = 1,
        max_retries: int = 3,
        description: str = "",
        current_user_query: str = "（不明）",
        execution_context: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        LLMによるツール実行結果の判断と処理
        
        Args:
            tool: ツール名
            current_params: 現在実行したパラメータ
            original_params: 元のパラメータ（修正の基準）
            result: ツール実行結果
            attempt: 現在の試行回数
            max_retries: 最大リトライ回数
            description: 現在実行中のタスクの説明
            current_user_query: ユーザーの要求
            
        Returns:
            判断結果辞書
        """
        # 試行履歴に現在のパラメータを記録
        self.attempt_history.append({
            "attempt": attempt,
            "params": current_params.copy(),
            "result": safe_str(result),
            "timestamp": time.time()
        })
        
        # 最新3回分のみ保持（プロンプト肥大化を防ぐ）
        if len(self.attempt_history) > 3:
            self.attempt_history = self.attempt_history[-3:]
        
        # プロンプト生成
        prompt = self.build_judgment_prompt(
            tool=tool,
            current_params=current_params,
            original_params=original_params,
            result=result,
            attempt=attempt,
            max_retries=max_retries,
            description=description,
            current_user_query=current_user_query,
            execution_context=execution_context
        )
        
        # LLM呼び出し
        judgment = await self.call_llm_for_judgment(prompt)
        
        # ログ出力
        self.log_judgment_result(judgment)
        
        return judgment
    
