#!/usr/bin/env python3
"""
MCP Agent V4 - Interactive Dialogue Engine
Claude Code風の対話型エージェント

V4の特徴：
- 対話的逐次実行（依存関係の自動解決）
- チェックボックス付きタスク表示
- リアルタイムプログレス
- V3の知見を活かした設計
"""

import os
import json
import asyncio
import time
import yaml
from typing import Dict, List, Any, Optional
from datetime import datetime
from openai import AsyncOpenAI

from connection_manager import ConnectionManager
from display_manager import DisplayManager
from error_handler import ErrorHandler
from prompts import PromptTemplates
from utils import Logger, safe_str

# Rich UI support
try:
    from display_manager_rich import RichDisplayManager
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False




class MCPAgentV4:
    """
    Claude Code風の対話型MCPエージェント
    
    V3から引き継いだ要素:
    - AGENT.mdによるカスタマイズ
    - 会話文脈の活用
    - NO_TOOL判定
    
    V4の新機能:
    - 対話的逐次実行
    - ステップバイステップの可視化
    - 依存関係の自動解決
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        """初期化"""
        self.config = self._load_config(config_path)
        
        # UI モードに基づいて適切なDisplayManagerを選択
        ui_mode = self.config.get("display", {}).get("ui_mode", "basic")
        
        if ui_mode == "rich" and RICH_AVAILABLE:
            self.display = RichDisplayManager(
                show_timing=self.config["display"]["show_timing"],
                show_thinking=self.config["display"]["show_thinking"]
            )
            self.ui_mode = "rich"
        else:
            if ui_mode == "rich" and not RICH_AVAILABLE:
                print("[WARNING] Rich UI requested but rich library not available. Using basic UI.")
            self.display = DisplayManager(
                show_timing=self.config["display"]["show_timing"],
                show_thinking=self.config["display"]["show_thinking"]
            )
            self.ui_mode = "basic"
        
        # LLMクライアント
        self.llm = AsyncOpenAI()
        
        # MCP接続管理（V3から流用）
        self.connection_manager = ConnectionManager()
        
        # エラー処理司令塔（V4新機能）
        self.error_handler = ErrorHandler(
            config=self.config,
            llm=self.llm,
            verbose=self.config.get("development", {}).get("verbose", True)
        )
        
        # 会話履歴（V3から継承）
        self.conversation_history: List[Dict] = []
        
        # セッション統計
        self.session_stats = {
            "start_time": datetime.now(),
            "total_requests": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "total_api_calls": 0
        }
        
        # 実行メトリクス（新機能）
        self.execution_metrics = {
            "task_generation_success": 0,
            "task_generation_failures": 0,
            "task_generation_retry_success": 0,
            "task_generation_total_failures": 0,
            "json_parse_errors": 0,
            "timeout_count": 0,
            "fallback_usage": 0,
            "average_task_count": 0.0,
            "total_task_lists": 0
        }
        
        # AGENT.md読み込み（V3から継承）
        self.custom_instructions = self._load_agent_md()
        
        # Loggerを初期化
        self.verbose = self.config.get("development", {}).get("verbose", True)
        self.logger = Logger(verbose=self.verbose)
        
        if self.verbose:
            self.display.show_banner()
            if self.ui_mode == "rich":
                self.logger.info("Rich UI mode enabled")
            else:
                self.logger.info("Basic UI mode enabled")
    
    def _load_config(self, config_path: str) -> Dict:
        """設定ファイルを読み込み（必須）"""
        if not os.path.exists(config_path):
            raise FileNotFoundError(
                f"設定ファイル '{config_path}' が見つかりません。\n"
                f"'config.sample.yaml' を '{config_path}' にコピーしてください。"
            )
        
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    
    def _load_agent_md(self) -> str:
        """AGENT.mdを読み込み（V3から継承）"""
        agent_md_path = "AGENT.md"
        
        if os.path.exists(agent_md_path):
            try:
                with open(agent_md_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if hasattr(self, 'logger'):
                    self.logger.config_info(f"AGENT.mdを読み込みました ({len(content)}文字)")
                elif self.config.get("development", {}).get("verbose", False):
                    print(f"[設定] AGENT.mdを読み込みました ({len(content)}文字)")
                return content
            except Exception as e:
                print(f"[警告] AGENT.md読み込みエラー: {e}")
                return ""
        else:
            if self.config.get("development", {}).get("verbose", False):
                print("[情報] AGENT.mdが見つかりません（基本能力のみで動作）")
            return ""
    
    async def initialize(self):
        """エージェントの初期化"""
        if self.verbose:
            print(f"\n[指示書] {'カスタム指示あり' if self.custom_instructions else '基本能力のみ'}")
            print("=" * 60)
        
        # MCP接続管理を初期化（V3から継承）
        await self.connection_manager.initialize()
    
    async def process_request(self, user_query: str) -> str:
        """
        ユーザーリクエストを対話的に処理（V4の核心機能）
        
        V3との違い:
        - 一度に全タスクを分解せず、ステップごとに対話
        - 前の結果を見てから次の行動を決定
        - 実行過程を視覚的に表示
        """
        self.session_stats["total_requests"] += 1
        
        if self.verbose:
            print(f"\n[リクエスト #{self.session_stats['total_requests']}] {user_query}")
            print("-" * 60)
        
        # 会話文脈を表示
        context_count = min(len(self.conversation_history), 
                          self.config["conversation"]["context_limit"])
        if context_count > 0:
            self.display.show_context_info(context_count)
        
        try:
            # 対話的実行の開始
            response = await self._execute_interactive_dialogue(user_query)
            
            # 会話履歴に追加（V3から継承）
            # 実行結果については各実行メソッドで追加される
            self._add_to_history("user", user_query)
            
            return response
            
        except Exception as e:
            error_msg = f"処理エラー: {str(e)}"
            if self.verbose:
                print(f"[エラー] {error_msg}")
            return error_msg
    
    async def _execute_interactive_dialogue(self, user_query: str) -> str:
        """
        改良版実行エンジン（V4.1）
        
        複雑なタスクはタスクリスト方式、シンプルなタスクは従来方式
        """
        # 現在のクエリを保存（LLM判断で使用）
        self.current_user_query = user_query
        self.display.show_analysis("リクエストを分析中...")
        
        # まず処理方式を判定
        execution_result = await self._determine_execution_type(user_query)
        execution_type = execution_result.get("type", "SIMPLE")
        
        if execution_type == "NO_TOOL":
            response = execution_result.get("response", "了解しました。")
            self._add_to_history("assistant", response)
            return response
        else:
            # SIMPLE/COMPLEX統合：全てのツール実行要求を統一メソッドで処理
            return await self._execute_with_tasklist(user_query)
    
    async def _determine_execution_type(self, user_query: str) -> Dict:
        """ユーザーの要求がNO_TOOLかツール実行かを判定（SIMPLE/COMPLEX統合後）"""
        recent_context = self._get_recent_context()
        
        # プロンプトテンプレートから取得
        prompt = PromptTemplates.get_execution_type_determination_prompt(
            recent_context=recent_context,
            user_query=user_query
        )

        try:
            response = await self.llm.chat.completions.create(
                model=self.config["llm"]["model"],
                messages=[{"role": "system", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            content = safe_str(response.choices[0].message.content)
            result = json.loads(content)
            
            # SIMPLE/COMPLEX統合のため、NO_TOOL以外は全てTOOLに統一
            if result.get('type') in ['SIMPLE', 'COMPLEX']:
                result['type'] = 'TOOL'
            
            self.logger.info(f"判定: {result.get('type', 'UNKNOWN')} - {result.get('reason', '')}")
            
            return result
            
        except Exception as e:
            print(f"[エラー] 実行方式判定失敗: {e}")
            return {"type": "TOOL", "reason": "判定エラーによりデフォルト選択"}
    
    async def _execute_with_tasklist(self, user_query: str) -> str:
        """統一されたタスクリスト実行メソッド（SIMPLE/COMPLEX統合版）"""
        
        # リトライ機能付きタスクリスト生成（統一メソッド使用）
        task_list = await self._generate_task_list_with_retry(user_query)
        
        if not task_list:
            # タスクリスト生成に失敗した場合のエラーメッセージ
            error_msg = (f"申し訳ありません。{user_query}の処理方法を決定できませんでした。\n"
                       f"別の表現で再度お試しください。")
            return error_msg
        
        # メトリクス更新
        self.execution_metrics["total_task_lists"] += 1
        self.execution_metrics["average_task_count"] += len(task_list)
        
        # チェックリストを表示
        if self.ui_mode == "rich" and self.config.get("display", {}).get("rich_options", {}).get("enable_live_updates", True):
            self.display.show_checklist(task_list)
        else:
            self.display.show_checklist(task_list)
        
        # 実行結果を追跡
        completed = []
        failed = []
        execution_context = []
        
        # タスクを順次実行
        for i, task in enumerate(task_list):
            # 進行状況更新（Rich UIの場合はライブ更新）
            if self.ui_mode == "rich" and hasattr(self.display, 'update_checklist_live'):
                self.display.update_checklist_live(task_list, current=i, completed=completed, failed=failed)
            else:
                self.display.update_checklist(task_list, current=i, completed=completed, failed=failed)
            
            try:
                # タスク実行（これまでの実行コンテキストを渡す）
                result = await self._execute_planned_task(task, i+1, len(task_list), execution_context.copy())
                
                if result["success"]:
                    completed.append(i)
                    task["duration"] = result["duration"]
                else:
                    failed.append(i)
                
                execution_context.append(result)
                
            except Exception as e:
                failed.append(i)
                print(f"[エラー] タスク{i+1}実行失敗: {e}")
        
        # 最終状況表示
        if self.ui_mode == "rich" and hasattr(self.display, 'update_checklist_live'):
            self.display.update_checklist_live(task_list, current=-1, completed=completed, failed=failed)
        else:
            self.display.update_checklist(task_list, current=-1, completed=completed, failed=failed)
        
        # 結果をLLMで解釈
        return await self._interpret_planned_results(user_query, execution_context)
    
    def _resolve_placeholders(self, params: Dict, execution_context: List[Dict]) -> Dict:
        """
        パラメータ内のプレースホルダーを実際の値に置換
        
        サポートされるプレースホルダー:
        - {{previous_result}} - 直前のタスク結果
        - {{task_N.field}} - N番目のタスクの特定フィールド
        - 文字列パターンマッチング（例：「取得した都市名」→ 実際の都市名）
        """
        if not execution_context:
            return params
        
        import re
        import json
        
        def replace_value(value):
            if not isinstance(value, str):
                return value
                
            # {{previous_result}} パターン
            if value == "{{previous_result}}" and execution_context:
                last_result = execution_context[-1].get("result", "")
                return str(last_result)
            
            # {{task_N.field}} パターン
            task_pattern = r'\{\{task_(\d+)\.(\w+)\}\}'
            matches = re.findall(task_pattern, value)
            for task_num, field in matches:
                task_index = int(task_num) - 1
                if 0 <= task_index < len(execution_context):
                    task_result = execution_context[task_index].get("result", {})
                    if isinstance(task_result, dict) and field in task_result:
                        placeholder = f"{{{{task_{task_num}.{field}}}}}"
                        value = value.replace(placeholder, str(task_result[field]))
            
            # 文字列パターンマッチング（IP地理情報 → 天気用）
            if value in ["取得した都市名", "取得した都市", "都市名"]:
                # 最新の結果から都市情報を探す
                for result_data in reversed(execution_context):
                    result = result_data.get("result", {})
                    if isinstance(result, dict):
                        # IPアドレス情報から都市を取得
                        if "city" in result:
                            return result["city"]
                        elif "市" in str(result) or "区" in str(result):
                            # 日本の市区情報を検索
                            city_match = re.search(r'([^、]+[市区])', str(result))
                            if city_match:
                                return city_match.group(1)
            
            return value
        
        # パラメータの各値を再帰的に処理
        def process_params(obj):
            if isinstance(obj, dict):
                return {k: process_params(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [process_params(item) for item in obj]
            else:
                return replace_value(obj)
        
        return process_params(params)
    
    async def _generate_adaptive_task_list(self, user_query: str, temperature: float = 0.1) -> List[Dict]:
        """
        クエリの複雑さに応じて適応的にタスクリストを生成
        
        Args:
            user_query: ユーザークエリ
            temperature: LLMの温度パラメータ
            
        Returns:
            生成されたタスクリスト
        """
        recent_context = self._get_conversation_context_only()
        tools_info = self.connection_manager.format_tools_for_llm()
        
        # カスタム指示の有無で複雑さを判定
        custom_instructions = self.custom_instructions if self.custom_instructions.strip() else None
        
        # プロンプトテンプレートから取得
        prompt = PromptTemplates.get_adaptive_task_list_prompt(
            recent_context=recent_context,
            user_query=user_query,
            tools_info=tools_info,
            custom_instructions=custom_instructions
        )

        try:
            self.session_stats["total_api_calls"] += 1
            
            response = await self.llm.chat.completions.create(
                model=self.config["llm"]["model"],
                messages=[{"role": "system", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=temperature
            )
            
            content = safe_str(response.choices[0].message.content)
            result = json.loads(content)
            tasks = result.get("tasks", [])
            
            # タスク数に応じてログ出力
            task_type_label = "詳細" if custom_instructions else "シンプル"
            self.logger.info(f"{task_type_label}タスク: {len(tasks)}個のタスクを生成")
            for i, task in enumerate(tasks, 1):
                self.logger.debug(f"  [{i}] Tool: {task.get('tool')}, Params: {safe_str(task.get('params', {}))[:100]}...")
                self.logger.debug(f"      Description: {task.get('description', 'N/A')}")
            
            # シンプルな場合は最大3タスクに制限
            if not custom_instructions and len(tasks) > 3:
                self.logger.info(f"タスク数制限: {len(tasks)} → 3（シンプルモード）")
                tasks = tasks[:3]
            
            return tasks
            
        except Exception as e:
            print(f"[エラー] 適応的タスクリスト生成失敗: {e}")
            return []
    
    async def _generate_task_list_with_retry(self, user_query: str) -> List[Dict]:
        """
        リトライ機能付き適応的タスクリスト生成
        
        Args:
            user_query: ユーザークエリ
            
        Returns:
            生成されたタスクリスト
        """
        retry_config = self.config.get("execution", {}).get("retry_strategy", {})
        max_retries = retry_config.get("max_retries", 3)
        use_progressive = retry_config.get("progressive_temperature", True)
        initial_temp = retry_config.get("initial_temperature", 0.1)
        temp_increment = retry_config.get("temperature_increment", 0.2)
        
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # プログレッシブtemperature調整
                if use_progressive and attempt > 0:
                    temperature = min(initial_temp + (attempt * temp_increment), 0.9)
                else:
                    temperature = initial_temp
                
                # 統一された適応的タスクリスト生成を使用
                task_list = await self._generate_adaptive_task_list(user_query, temperature)
                
                if task_list:
                    # 成功時はメトリクスを更新
                    if hasattr(self, 'execution_metrics'):
                        self.execution_metrics['task_generation_success'] += 1
                        if attempt > 0:
                            self.execution_metrics['task_generation_retry_success'] += 1
                    
                    if attempt > 0:
                        self.logger.info(f"[成功] タスクリスト生成 - {attempt + 1}回目の試行で成功")
                    
                    # タスク数制限（全体的な上限）
                    max_tasks = self.config.get("execution", {}).get("max_tasks", 10)
                    if len(task_list) > max_tasks:
                        self.logger.warning(f"タスク数制限: {len(task_list)} → {max_tasks}")
                        task_list = task_list[:max_tasks]
                    
                    return task_list
                else:
                    last_error = f"試行{attempt + 1}: 空のタスクリストが生成されました"
                    
            except json.JSONDecodeError as e:
                last_error = f"試行{attempt + 1}: JSON解析エラー - {str(e)}"
                self.logger.info(f"[リトライ] {last_error}")
            except Exception as e:
                last_error = f"試行{attempt + 1}: {str(e)}"
                self.logger.info(f"[リトライ] {last_error}")
            
            # メトリクス更新
            if hasattr(self, 'execution_metrics'):
                self.execution_metrics['task_generation_failures'] += 1
        
        # 全ての試行が失敗
        self.logger.error(f"[失敗] タスクリスト生成 - {max_retries}回の試行全てが失敗")
        self.logger.error(f"最後のエラー: {last_error}")
        
        if hasattr(self, 'execution_metrics'):
            self.execution_metrics['task_generation_total_failures'] += 1
            
        return []

    
    
    async def _execute_tool_with_retry(self, tool: str, params: Dict, description: str = "") -> Any:
        """
        LLMベースの賢いツール実行・判断システム
        
        Args:
            tool: ツール名
            params: 実行パラメータ
            description: タスクの説明（LLM判断時のコンテキスト）
        """
        self.logger.info(f"[DEBUG] _execute_tool_with_retry が呼び出されました: tool={tool}")
        max_retries = 3
        
        # 元のパラメータを保持（破壊的変更を避ける）
        original_params = params.copy()
        current_params = params.copy()
        
        for attempt in range(max_retries + 1):
            # 1. ツール実行（例外もキャッチして結果として扱う）
            try:
                raw_result = await self.connection_manager.call_tool(tool, current_params)
                self.logger.info(f"[DEBUG] ツール実行成功 attempt={attempt + 1}, result_type={type(raw_result)}")
            except Exception as e:
                # 例外も「結果」として扱い、LLM判断に回す
                raw_result = f"ツールエラー: {e}"
                self.logger.info(f"[DEBUG] ツール実行でエラー発生 attempt={attempt + 1}, error={type(e).__name__}")
            
            # 2. LLMに結果を判断させる（成功・失敗問わず）
            try:
                self.logger.info(f"[DEBUG] LLM判断を開始...")
                judgment = await self._judge_and_process_result(
                    tool=tool,
                    current_params=current_params,
                    original_params=original_params,
                    result=raw_result,
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    description=description
                )
                self.logger.info(f"[DEBUG] LLM判断完了")
                
            except Exception as e:
                self.logger.error(f"[DEBUG] LLM判断でエラー発生: {type(e).__name__}: {e}")
                # LLM判断でエラーの場合は、結果をそのまま返す
                return raw_result
            
            # 3. LLMの判断に基づいて行動
            if judgment.get("needs_retry", False) and attempt < max_retries:
                self.logger.info(f"[リトライ] {attempt + 1}/{max_retries}: {judgment.get('error_reason', 'LLM判断によるリトライ')}")
                
                # 修正されたパラメータで再実行（元のparamsは保持）
                corrected_params = judgment.get("corrected_params", current_params)
                if corrected_params != current_params:
                    self.logger.info(f"[修正] パラメータを修正: {safe_str(corrected_params)}")
                    current_params = corrected_params
                
                continue
            
            # 成功または最大リトライ回数到達
            return judgment.get("processed_result", raw_result)
        
        # 最大リトライ回数に到達
        return judgment.get("processed_result", "最大リトライ回数に到達しました。")
    
    async def _judge_and_process_result(
        self, 
        tool: str, 
        current_params: Dict,
        original_params: Dict, 
        result: Any,
        attempt: int = 1,
        max_retries: int = 3,
        description: str = ""
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
            
        Returns:
            判断結果辞書
        """
        # 結果を安全な文字列に変換
        result_str = safe_str(result)
        current_params_str = safe_str(current_params)
        original_params_str = safe_str(original_params)
        
        # 現在の会話文脈を取得
        current_query = getattr(self, 'current_user_query', '（不明）')
        
        prompt = f"""あなたはツール実行結果を判断するエキスパートです。以下の実行結果を分析してください。

## 現在実行中のタスク
タスク: {description or "タスクの説明なし"}

## 実行情報
- ツール名: {tool}
- 現在のパラメータ: {current_params_str}
- 元のパラメータ: {original_params_str}
- 試行回数: {attempt}/{max_retries + 1}
- ユーザーの要求: {current_query}

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
- 例：「Beijing」の天気取得なら → 「Beijing, CN」等に修正
- 例：「Tokyo」の天気取得なら → 「Tokyo, JP」等に修正

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
- 都市名エラー → 国コード付きに修正（例：Beijing → Beijing, CN）
- 日本語パラメータ → 英語に変換
- セミコロン記法 → 複数行に分解"""

        try:
            response = await self.llm.chat.completions.create(
                model=self.config["llm"]["model"],
                messages=[{"role": "system", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            raw_response = response.choices[0].message.content
            self.logger.debug(f"[LLM生レスポンス] {safe_str(raw_response)[:500]}")
            
            judgment = json.loads(raw_response)
            
            # デバッグログ（詳細版）
            self.logger.info(f"[LLM判断] 成功: {judgment.get('is_success')}, リトライ必要: {judgment.get('needs_retry')}")
            if judgment.get('needs_retry'):
                self.logger.info(f"[LLM理由] {judgment.get('error_reason', '不明')}")
                if judgment.get('corrected_params'):
                    self.logger.info(f"[LLM修正案] {safe_str(judgment.get('corrected_params'))[:200]}")
            else:
                self.logger.info(f"[LLM判断理由] リトライ不要 - {judgment.get('summary', '詳細不明')}")
            
            return judgment
            
        except Exception as e:
            self.logger.error(f"[LLM判断エラー] {e}")
            # フォールバック: 結果をそのまま返す
            return {
                "is_success": True,
                "needs_retry": False,
                "processed_result": result_str,
                "summary": "LLM判断に失敗しました。結果をそのまま表示します。"
            }
    
    
    async def _execute_planned_task(self, task: Dict, step_num: int, total: int, execution_context: List[Dict] = None) -> Dict:
        """計画されたタスクを実行"""
        tool = task.get("tool", "")
        params = task.get("params", {})
        description = task.get("description", f"{tool}を実行")
        
        # プレースホルダー置換処理
        if execution_context:
            params = self._resolve_placeholders(params, execution_context)
        
        # ステップ開始の表示
        self.display.show_step_start(step_num, "?", description)
        
        # デバッグ: ツール実行直前のパラメータを確認
        if self.verbose and tool == "execute_python":
            print(f"[DEBUG] About to execute {tool} with full params:")
            for k, v in params.items():
                print(f"  {k}: {safe_str(v, use_repr=True)}")
        
        self.display.show_tool_call(tool, params)
        
        start_time = time.time()
        
        try:
            # ツール実行
            result = await self._execute_tool_with_retry(tool, params, description)
            duration = time.time() - start_time
            
            # デバッグ: 実行結果を確認
            if self.verbose:
                safe_result = safe_str(result)
                result_preview = safe_result[:200] + "..." if len(safe_result) > 200 else safe_result
                print(f"[DEBUG] Tool: {tool}, Result: {result_preview}")
            
            self.display.show_step_complete(description, duration, success=True)
            
            self.session_stats["successful_tasks"] += 1
            
            return {
                "step": step_num,
                "tool": tool,
                "params": params,
                "result": result,
                "success": True,
                "duration": duration,
                "description": description
            }
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            
            self.session_stats["failed_tasks"] += 1
            
            return {
                "step": step_num,
                "tool": tool,
                "params": params,
                "error": error_msg,
                "success": False,
                "duration": duration,
                "description": description
            }
    
    async def _interpret_planned_results(self, user_query: str, results: List[Dict]) -> str:
        """計画実行の結果を解釈"""
        # 現在のリクエストのみに焦点を当て、前のタスク結果の混入を防ぐ
        recent_context = self._get_conversation_context_only()
        
        # 結果をシリアライズ
        serializable_results = []
        for r in results:
            result_data = {
                "step": r["step"],
                "tool": r["tool"],
                "success": r["success"],
                "description": r["description"]
            }
            
            if r["success"]:
                # 成功時は結果を含める
                max_length = self.config.get("result_display", {}).get("max_result_length", 1000)
                result_str = str(r["result"])
                
                if len(result_str) <= max_length:
                    result_data["result"] = result_str
                else:
                    # 長すぎる場合は省略情報を追加
                    result_data["result"] = result_str[:max_length]
                    if self.config.get("result_display", {}).get("show_truncated_info", True):
                        result_data["result"] += f"\n[注記: 結果が長いため{max_length}文字で省略。実際の結果はより多くのデータを含む可能性があります]"
            else:
                result_data["error"] = r["error"]
            
            serializable_results.append(result_data)
        
        # デバッグ: LLMに渡されるデータを確認
        if self.verbose:
            print(f"[DEBUG] Serializable results being sent to LLM:")
            for i, result in enumerate(serializable_results):
                result_preview = str(result.get("result", "N/A"))[:100] + "..." if len(str(result.get("result", "N/A"))) > 100 else str(result.get("result", "N/A"))
                print(f"  [{i+1}] Tool: {result['tool']}, Result: {result_preview}")
        
        # プロンプトテンプレートから取得
        prompt = PromptTemplates.get_result_interpretation_prompt(
            recent_context=recent_context,
            user_query=user_query,
            serializable_results=json.dumps(serializable_results, ensure_ascii=False, indent=2),
            custom_instructions=self.custom_instructions
        )

        try:
            response = await self.llm.chat.completions.create(
                model=self.config["llm"]["model"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            # 最終応答を取得
            final_response = response.choices[0].message.content
            
            # Rich UIの場合は美しく表示
            if self.ui_mode == "rich" and hasattr(self.display, 'show_result_panel'):
                # JSONまたは長いテキストかどうか判定
                if len(final_response) > 100 or final_response.strip().startswith('{'):
                    self.display.show_result_panel("実行結果", final_response, success=True)
                
            # 実行結果と共に履歴に保存
            self._add_to_history("assistant", final_response, serializable_results)
            
            return final_response
            
        except Exception as e:
            # フォールバック
            successful_results = [r for r in results if r["success"]]
            if successful_results:
                return f"実行完了しました。{len(successful_results)}個のタスクが成功しました。"
            else:
                return f"申し訳ありませんが、処理中にエラーが発生しました。"
    
    def _get_recent_context(self, max_items: int = None) -> str:
        """最近の会話文脈を取得（実行結果も含む）"""
        if max_items is None:
            max_items = self.config["conversation"]["context_limit"]
        
        if not self.conversation_history:
            return ""
        
        recent = self.conversation_history[-max_items:]
        lines = []
        for h in recent:
            role = "User" if h['role'] == "user" else "Assistant"
            # 長いメッセージは省略
            msg = h['message'][:150] + "..." if len(h['message']) > 150 else h['message']
            lines.append(f"{role}: {msg}")
            
            # 実行結果があれば追加
            if h.get('execution_results'):
                lines.append(f"実行結果データ: {self._summarize_results(h['execution_results'])}")
        
        return "\n".join(lines)
    
    def _get_conversation_context_only(self, max_items: int = 3) -> str:
        """
        会話文脈のみを取得（実行結果を除外）
        結果解釈時に前のタスク結果の混入を防ぐ
        """
        if not self.conversation_history:
            return ""
        
        recent = self.conversation_history[-max_items:]
        lines = []
        for h in recent:
            role = "User" if h['role'] == "user" else "Assistant"
            # 長いメッセージは省略
            msg = h['message'][:150] + "..." if len(h['message']) > 150 else h['message']
            lines.append(f"{role}: {msg}")
            # 実行結果は含めない（混入を防ぐため）
        
        return "\n".join(lines)
    
    def _summarize_results(self, results: List[Dict]) -> str:
        """実行結果を要約して表示"""
        summary_parts = []
        for r in results:
            tool = r.get('tool', 'Unknown')
            success = r.get('success', False)
            
            if success and r.get('result'):
                result_str = str(r['result'])
                # 結果が長い場合は短縮
                if len(result_str) > 100:
                    result_str = result_str[:97] + "..."
                summary_parts.append(f"{tool}: {result_str}")
            else:
                summary_parts.append(f"{tool}: {'成功' if success else '失敗'}")
        
        return " | ".join(summary_parts[:3])  # 最大3つの結果を表示
    
    def _add_to_history(self, role: str, message: str, execution_results: List[Dict] = None):
        """会話履歴に追加（実行結果も含む）"""
        history_item = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "message": message
        }
        
        # 実行結果があれば追加
        if execution_results:
            history_item["execution_results"] = execution_results
        
        self.conversation_history.append(history_item)
        
        # 履歴の長さ制限
        max_history = self.config["conversation"]["max_history"]
        if len(self.conversation_history) > max_history:
            self.conversation_history = self.conversation_history[-max_history:]
    
    def _show_execution_metrics(self):
        """実行メトリクスを表示"""
        if not self.config.get("development", {}).get("show_statistics", True):
            return
            
        print("\n" + "=" * 50)
        print("📊 実行メトリクス")
        print("=" * 50)
        
        # タスクリスト生成統計
        total_attempts = (self.execution_metrics["task_generation_success"] + 
                         self.execution_metrics["task_generation_total_failures"])
        if total_attempts > 0:
            success_rate = (self.execution_metrics["task_generation_success"] / total_attempts) * 100
            print(f"タスクリスト生成成功率: {success_rate:.1f}% ({self.execution_metrics['task_generation_success']}/{total_attempts})")
        
        if self.execution_metrics["task_generation_retry_success"] > 0:
            print(f"リトライ成功: {self.execution_metrics['task_generation_retry_success']}回")
        
        if self.execution_metrics["json_parse_errors"] > 0:
            print(f"JSON解析エラー: {self.execution_metrics['json_parse_errors']}回")
            
        if self.execution_metrics["timeout_count"] > 0:
            print(f"タイムアウト発生: {self.execution_metrics['timeout_count']}回")
            
        if self.execution_metrics["fallback_usage"] > 0:
            print(f"フォールバック使用: {self.execution_metrics['fallback_usage']}回")
        
        if self.execution_metrics["total_task_lists"] > 0:
            avg_tasks = self.execution_metrics["average_task_count"] / self.execution_metrics["total_task_lists"]
            print(f"平均タスク数: {avg_tasks:.1f}個")
        
        print("=" * 50)
    
    def _show_session_statistics(self):
        """セッション統計を表示"""
        total_time = (datetime.now() - self.session_stats["start_time"]).total_seconds()
        
        self.display.show_result_summary(
            total_tasks=self.session_stats["successful_tasks"] + self.session_stats["failed_tasks"],
            successful=self.session_stats["successful_tasks"],
            failed=self.session_stats["failed_tasks"],
            total_duration=total_time
        )
        
        if self.config["development"]["show_api_calls"]:
            print(f"API呼び出し回数: {self.session_stats['total_api_calls']}")
    
    async def close(self):
        """リソースの解放"""
        # 終了時にメトリクス表示
        self._show_execution_metrics()
        await self.connection_manager.close()


async def main():
    """メイン実行関数"""
    agent = MCPAgentV4()
    await agent.initialize()
    
    try:
        print("\nMCP Agent V4 が準備完了しました！")
        print("終了するには 'quit' または 'exit' を入力してください。")
        print("-" * 60)
        
        while True:
            try:
                if hasattr(agent.display, 'input_prompt') and agent.ui_mode == "rich":
                    user_input = agent.display.input_prompt("Agent").strip()
                else:
                    user_input = input("\nAgent> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            
            if user_input.lower() in ['quit', 'exit', '終了']:
                break
            
            if not user_input:
                continue
            
            # リクエスト処理
            response = await agent.process_request(user_input)
            
            # Rich UIの場合はMarkdown整形表示
            if agent.ui_mode == "rich" and hasattr(agent.display, 'show_markdown_result'):
                agent.display.show_markdown_result(response)
            else:
                print(f"\n{response}")
    
    except KeyboardInterrupt:
        print("\n\n[中断] Ctrl+Cが押されました。")
    finally:
        await agent.close()
        print("\nMCP Agent V4 を終了しました。")


if __name__ == "__main__":
    asyncio.run(main())