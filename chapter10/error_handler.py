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
from typing import Dict, Any, Optional, Callable, List, Union
from dataclasses import asdict
from openai import AsyncOpenAI


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
    
    def __init__(self, config: Union[Dict, Any], llm: Optional[AsyncOpenAI] = None, verbose: bool = True):
        """
        Args:
            config: 設定辞書またはConfigオブジェクト
            llm: OpenAI LLMクライアント（パラメータ修正用）
            verbose: 詳細ログ出力
        """
        # Configオブジェクトの場合は辞書に変換
        if hasattr(config, '__dataclass_fields__'):  # dataclassの場合
            self.config = asdict(config)
        else:
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
                print("[修正] LLMが利用できないため自動修正をスキップ")
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
                model=self.config["llm"]["model"],
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
                        print(f"[修正成功] パラメータを自動修正: {result.get('params')}")
                    return result.get("params")
            
            if self.verbose:
                print(f"[修正失敗] LLM応答の解析に失敗: {response_text[:100]}...")
            
            return None
            
        except Exception as e:
            if self.verbose:
                print(f"[修正エラー] パラメータ修正に失敗: {e}")
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
        max_retries = self.config.get("execution", {}).get("max_retries", 3)
        original_params = params.copy()  # 元のパラメータを保持
        
        for attempt in range(max_retries + 1):
            try:
                result = await execute_func(tool, params)
                
                # デバッグ：error_handlerでの結果チェック
                if isinstance(result, str):
                    surrogate_count = sum(1 for char in result if 0xD800 <= ord(char) <= 0xDFFF)
                    if surrogate_count > 0:
                        print(f"[error_handler] Found {surrogate_count} surrogate characters in result")
                        for i, char in enumerate(result):
                            if 0xD800 <= ord(char) <= 0xDFFF:
                                print(f"[error_handler] First surrogate at position {i}: {repr(char)} (U+{ord(char):04X})")
                                break
                
                # 成功時のログ
                if attempt > 0:
                    self.error_stats["retry_success"] += 1
                    if self.verbose:
                        print(f"  [成功] {attempt}回目のリトライで成功しました")
                
                return result
                
            except Exception as e:
                self.error_stats["total_errors"] += 1
                # エラーメッセージからサロゲート文字を除去
                error_msg = safe_str(str(e))
                error_type = self.classify_error(error_msg)
                
                if self.verbose:
                    print(f"  [エラー分類] {error_type}: {error_msg}")
                
                # 最後の試行の場合は例外を投げる
                if attempt >= max_retries:
                    if self.verbose:
                        print(f"  [失敗] 最大リトライ回数({max_retries})に到達")
                    raise e
                
                # エラータイプに応じた処理
                if error_type == "PARAM_ERROR":
                    # パラメータエラーの場合、LLMで修正を試みる
                    if self.config.get("error_handling", {}).get("auto_correct_params", True):
                        if self.verbose:
                            print(f"  [分析] パラメータエラーを検出 - LLMで修正を試みます")
                        
                        if tools_info_func:
                            tools_info = tools_info_func()
                            corrected_params = await self.fix_params_with_llm(
                                tool, params, error_msg, tools_info
                            )
                            
                            if corrected_params and corrected_params != params:
                                params = corrected_params
                                if self.verbose:
                                    safe_params = safe_str(str(params))
                                    print(f"  [修正] パラメータを修正しました: {safe_params}")
                                # パラメータ修正後は残り試行回数を制限（無限ループ防止）
                                max_retries = min(max_retries, attempt + 2)
                            else:
                                if self.verbose:
                                    print(f"  [修正失敗] パラメータの自動修正に失敗")
                                # 修正できない場合は即座に失敗
                                raise e
                        else:
                            # ツール情報が取得できない場合は即座に失敗
                            if self.verbose:
                                print(f"  [修正失敗] ツール情報が取得できないため修正不可")
                            raise e
                    else:
                        # 自動修正が無効の場合は即座に失敗
                        raise e
                
                elif error_type == "TRANSIENT_ERROR":
                    # 一時的エラーの場合は通常のリトライ
                    if self.verbose:
                        print(f"  [リトライ] 一時的エラー - {attempt + 1}/{max_retries}")
                    retry_interval = self.config.get("error_handling", {}).get("retry_interval", 1.0)
                    await asyncio.sleep(retry_interval)
                
                else:
                    # 不明なエラーの場合は短時間リトライ
                    if self.verbose:
                        print(f"  [リトライ] 不明なエラー - {attempt + 1}/{max_retries}")
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
            print(f"[{level}] {context}: {str(error)}")
    
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
        current_user_query: str = None
    ) -> str:
        """LLM判断用プロンプトの生成"""
        # 結果を安全な文字列に変換
        result_str = safe_str(result)
        current_params_str = safe_str(current_params)
        original_params_str = safe_str(original_params)
        
        # ユーザークエリを決定
        if current_user_query is None:
            current_user_query = self.current_user_query or "（不明）"
        
        return f"""あなたはツール実行結果を判断するエキスパートです。以下の実行結果を分析してください。

## 現在実行中のタスク
タスク: {description or "タスクの説明なし"}

## 実行情報
- ツール名: {tool}
- 現在のパラメータ: {current_params_str}
- 元のパラメータ: {original_params_str}
- 試行回数: {attempt}/{max_retries + 1}
- ユーザーの要求: {current_user_query}

## 実行結果
{result_str}

## 判断基準
1. **成功判定**: 期待される結果が得られている
2. **失敗判定**: エラーメッセージ、構文エラー、実行エラーが含まれている
3. **リトライ判定**: パラメータを修正すれば成功する可能性がある

## **重要**: パラメータ修正時のルール
- **現在実行中のタスクの目的を必ず尊重してください**
- 修正は元のパラメータ（{original_params_str}）を基準に行ってください
- 他のタスクのパラメータに変更してはいけません
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
- セミコロン記法 → 複数行に分解"""
    
    def _get_llm_params(self, **kwargs) -> Dict:
        """モデルに応じたパラメータを生成"""
        model = self.config["llm"]["model"]
        params = {"model": model, **kwargs}
        
        if model.startswith("gpt-5"):
            # GPT-5系の設定
            params["max_completion_tokens"] = self.config["llm"].get("max_completion_tokens", 5000)
            params["reasoning_effort"] = self.config["llm"].get("reasoning_effort", "minimal")
            
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
            self.logger.debug(f"[LLM生レスポンス] {safe_str(raw_response)[:500]}")
            
            return json.loads(raw_response)
            
        except Exception as e:
            self.logger.error(f"[LLM判断エラー] {e}")
            # フォールバック: 成功として扱う
            return {
                "is_success": True,
                "needs_retry": False,
                "processed_result": "LLM判断に失敗しました。結果をそのまま表示します。",
                "summary": "LLM判断エラーによるフォールバック"
            }
    
    def log_judgment_result(self, judgment: Dict):
        """判断結果の詳細ログ出力"""
        self.logger.info(f"[LLM判断] 成功: {judgment.get('is_success')}, リトライ必要: {judgment.get('needs_retry')}")
        
        if judgment.get('needs_retry'):
            self.logger.info(f"[LLM理由] {judgment.get('error_reason', '不明')}")
            if judgment.get('corrected_params'):
                self.logger.info(f"[LLM修正案] {safe_str(judgment.get('corrected_params'))[:200]}")
        else:
            self.logger.info(f"[LLM判断理由] リトライ不要 - {judgment.get('summary', '詳細不明')}")
    
    async def judge_and_process_result(
        self, 
        tool: str, 
        current_params: Dict,
        original_params: Dict, 
        result: Any,
        attempt: int = 1,
        max_retries: int = 3,
        description: str = "",
        current_user_query: str = "（不明）"
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
        # プロンプト生成
        prompt = self.build_judgment_prompt(
            tool=tool,
            current_params=current_params,
            original_params=original_params,
            result=result,
            attempt=attempt,
            max_retries=max_retries,
            description=description,
            current_user_query=current_user_query
        )
        
        # LLM呼び出し
        judgment = await self.call_llm_for_judgment(prompt)
        
        # ログ出力
        self.log_judgment_result(judgment)
        
        return judgment
    
