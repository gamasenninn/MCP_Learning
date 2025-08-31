#!/usr/bin/env python3
"""
MCP Agent - Interactive Dialogue Engine
Claude Code風の対話型エージェント

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
from state_manager import StateManager, TaskState
from task_manager import TaskManager
from conversation_manager import ConversationManager
from task_executor import TaskExecutor

# Rich UI support
try:
    from display_manager_rich import RichDisplayManager
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# prompt_toolkit support
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.key_binding import KeyBindings
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    PROMPT_TOOLKIT_AVAILABLE = False


class MCPAgent:
    """
    Claude Code風の対話型MCPエージェント   
   
    現在の主要機能:
    - 対話的逐次実行
    - ステップバイステップの可視化
    - 依存関係の自動解決
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        """初期化（メイン処理）"""
        self.config = self._load_config(config_path)
        
        self._initialize_core_components()
        self._initialize_ui_and_logging()
        self._initialize_task_executor()  # 最後に初期化（他の全てが必要なため）
        
        # prompt_toolkit用
        self._prompt_session = None
    
    def _initialize_core_components(self):
        """コアコンポーネント（外部サービス、設定、データ構造）の初期化"""
        # 外部サービス
        self.llm = AsyncOpenAI()
        self.connection_manager = ConnectionManager()
        
        self.error_handler = ErrorHandler(
            config=self.config,
            llm=self.llm,
            verbose=self.config.get("development", {}).get("verbose", True)
        )
        
        self.state_manager = StateManager()
        self.task_manager = TaskManager(self.state_manager, self.llm)
        self.conversation_manager = ConversationManager(self.state_manager, self.config)
        
        # データ構造
        self.session_stats = {
            "start_time": datetime.now(),
            "total_requests": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "total_api_calls": 0
        }
        
        # カスタム設定
        self.custom_instructions = self._load_agent_md()
    
    def _initialize_ui_and_logging(self):
        """UI表示とログ設定の初期化"""
        # UI表示管理
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
        
        # ログ設定とバナー表示
        self.verbose = self.config.get("development", {}).get("verbose", True)
        self.logger = Logger(verbose=self.verbose)
        
        if self.verbose:
            self.display.show_banner()
            if self._is_rich_ui_enabled():
                self.logger.info("Rich UI mode enabled")
            else:
                self.logger.info("Basic UI mode enabled")
    
    def _initialize_task_executor(self):
        """TaskExecutorの初期化（全コンポーネント初期化後に実行）"""
        self.task_executor = TaskExecutor(
            task_manager=self.task_manager,
            connection_manager=self.connection_manager,
            state_manager=self.state_manager,
            display_manager=self.display,
            llm=self.llm,
            config=self.config,
            error_handler=self.error_handler,
            verbose=self.verbose
        )
    
    def _is_rich_ui_enabled(self) -> bool:
        """Rich UIが有効かどうかを判定"""
        return self.ui_mode == "rich"
    
    def _has_rich_method(self, method_name: str) -> bool:
        """Rich UIの特定メソッドが利用可能か判定"""
        return self._is_rich_ui_enabled() and hasattr(self.display, method_name)
    
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
                    self.logger.info(f"AGENT.mdを読み込みました ({len(content)}文字)")
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
    
    async def initialize(self, session_id: Optional[str] = None):
        """エージェントの初期化"""
        if self.verbose:
            print(f"\n[指示書] {'カスタム指示あり' if self.custom_instructions else '基本能力のみ'}")
            print("=" * 60)
        
        # MCP接続管理を初期化（V3から継承）
        await self.connection_manager.initialize()
        
        # セッション状態を初期化
        actual_session_id = await self.state_manager.initialize_session(session_id)
        
        if self.verbose:
            print(f"[セッション] {actual_session_id}")
            
            # 復元されたタスクがある場合は通知
            if self.state_manager.has_pending_tasks():
                pending_count = len(self.state_manager.get_pending_tasks())
                print(f"[復元] 未完了タスクが{pending_count}個あります")
        
        return actual_session_id
    
    async def process_request(self, user_query: str) -> str:
        """
        ユーザーリクエストを対話的に処理（核心機能）
        
        特徴:
        - 一度に全タスクを分解せず、ステップごとに対話
        - 前の結果を見てから次の行動を決定
        - 実行過程を視覚的に表示
        """
        self.session_stats["total_requests"] += 1
        
        if self.verbose:
            print(f"\n[リクエスト #{self.session_stats['total_requests']}] {user_query}")
            print("-" * 60)
        
        # 会話文脈を表示
        conversation_summary = self.conversation_manager.get_conversation_summary()
        if conversation_summary["total_messages"] > 0:
            context_count = min(conversation_summary["total_messages"], 
                              self.config["conversation"]["context_limit"])
            self.display.show_context_info(context_count)
        
        try:
            # 対話的実行の開始
            response = await self._execute_interactive_dialogue(user_query)
            
            # 会話履歴に追加（V3から継承）
            # 実行結果については各実行メソッドで追加される
            self.conversation_manager.add_to_conversation("user", user_query)
            
            return response
            
        except Exception as e:
            error_msg = f"処理エラー: {str(e)}"
            if self.verbose:
                print(f"[エラー] {error_msg}")
            return error_msg
    
    async def _execute_interactive_dialogue(self, user_query: str) -> str:
        """
統合実行エンジン - 状態管理とCLARIFICATION対応
        
        新機能:
        - 状態の永続化
        - CLARIFICATIONタスクによるユーザー確認
        - タスクの中断・再開機能
        """
        # 現在のクエリを保存（LLM判断で使用）
        self.current_user_query = user_query
        
        # 状態に会話を記録
        await self.state_manager.add_conversation_entry("user", user_query)
        
        # 未完了のタスクがある場合の処理
        if self.state_manager.has_pending_tasks():
            return await self._handle_pending_tasks(user_query)
        
        self.display.show_analysis("リクエストを分析中...")
        
        # まず処理方式を判定（CLARIFICATION対応版）
        execution_result = await self._determine_execution_type(user_query)
        execution_type = execution_result.get("type", "SIMPLE")
        
        # 状態に実行タイプを記録
        await self.state_manager.set_user_query(user_query, execution_type)
        
        if execution_type == "NO_TOOL":
            response = execution_result.get("response", "了解しました。")
            await self.state_manager.add_conversation_entry("assistant", response)
            self.conversation_manager.add_to_conversation("assistant", response)
            return response
        elif execution_type == "CLARIFICATION":
            # ユーザーへの確認が必要
            return await self._handle_clarification_needed(user_query, execution_result)
        else:
            # SIMPLE/COMPLEX統合：全てのツール実行要求を統一メソッドで処理
            return await self._execute_with_tasklist(user_query)
    
    async def _determine_execution_type(self, user_query: str) -> Dict:
        """CLARIFICATION対応の実行方式判定"""
        recent_context = self.conversation_manager.get_recent_context(include_results=False)
        
        # 利用可能なツール情報を取得
        tools_info = self.connection_manager.format_tools_for_llm()
        
        # プロンプトテンプレートから取得
        prompt = PromptTemplates.get_execution_type_determination_prompt(
            recent_context=recent_context,
            user_query=user_query,
            tools_info=tools_info
        )

        try:
            params = self._get_llm_params(
                messages=[{"role": "system", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            response = await self.llm.chat.completions.create(**params)
            
            content = safe_str(response.choices[0].message.content)
            result = json.loads(content)
            
            # CLARIFICATION も含む
            # SIMPLE/COMPLEX統合のため、NO_TOOL, CLARIFICATION以外は全てTOOLに統一
            if result.get('type') in ['SIMPLE', 'COMPLEX']:
                result['type'] = 'TOOL'
            
            
            self.logger.info(f"判定: {result.get('type', 'UNKNOWN')} - {result.get('reason', '')}")
            
            return result
            
        except Exception as e:
            print(f"[エラー] 実行方式判定失敗: {e}")
            return {"type": "TOOL", "reason": "判定エラーによりデフォルト選択"}
    
    async def _handle_pending_tasks(self, user_query: str) -> str:
        """未完了タスクがある場合の処理"""
        pending_tasks = self.state_manager.get_pending_tasks()
        
        # CLARIFICATIONタスクの処理
        if self.task_manager.has_clarification_tasks():
            clarification_task = self.task_manager.find_pending_clarification_task(pending_tasks)
            
            if clarification_task:
                return await self._process_clarification_task(clarification_task, user_query)
        
        # 通常のタスクを継続実行
        return await self._continue_pending_tasks(user_query)
    
    async def _process_clarification_task(self, task: TaskState, user_query: str) -> str:
        """CLARIFICATIONタスクの処理"""
        if user_query.lower() == 'skip':
            # スキップ処理
            smart_query = await self.task_manager.handle_clarification_skip(
                task, self.conversation_manager, self.state_manager
            )
            print("\n質問をスキップしました。会話履歴と文脈から最適な処理を実行します。")
            return await self._execute_with_tasklist(smart_query)
        else:
            # 通常の応答処理
            combined_query = await self.task_manager.handle_clarification_response(
                task, user_query, self.state_manager
            )
            return await self._execute_with_tasklist(combined_query)
    
    async def _handle_clarification_needed(self, user_query: str, execution_result: Dict) -> str:
        """CLARIFICATION必要時の処理"""
        clarification_info = execution_result.get('clarification', {})
        
        # CLARIFICATIONタスクを生成
        clarification_task = TaskState(
            task_id=f"clarification_{int(time.time())}",
            tool="CLARIFICATION",
            params={
                "question": clarification_info.get('question', '詳細情報をお教えください'),
                "context": f"要求: {user_query}",
                "user_query": user_query
            },
            description="ユーザーに確認",
            status="pending"
        )
        
        await self.state_manager.add_pending_task(clarification_task)
        
        # CLARIFICATIONタスクを実行
        question_message = await self.task_manager.execute_clarification_task(clarification_task)
        await self.state_manager.add_conversation_entry("assistant", question_message)
        return question_message
    
    async def _handle_clarification_task(self, task: TaskState) -> str:
        """CLARIFICATIONタスクの処理"""
        return await self.task_manager.execute_clarification_task(task)
    
    async def _continue_pending_tasks(self, user_query: str) -> str:
        """保留中タスクの継続実行"""
        next_task = self.task_manager.get_next_executable_task()
        
        if not next_task:
            return "実行可能なタスクがありません。"
        
        # タスクを実行
        return await self.task_executor.execute_single_task(next_task)
    
    
    async def _execute_with_tasklist(self, user_query: str) -> str:
        """タスクリスト実行メソッド - 状態管理対応"""
        
        # リトライ機能付きタスク生成
        task_list_spec = await self._generate_task_list_with_retry(user_query)
        
        if not task_list_spec:
            error_msg = (f"申し訳ありません。{user_query}の処理方法を決定できませんでした。\n"
                       f"別の表現で再度お試しください。")
            return error_msg
        
        # TaskStateオブジェクトを生成（CLARIFICATION処理を含む）
        tasks = await self.task_manager.create_tasks_from_list(task_list_spec, user_query)
        
        # タスクを状態管理に追加
        for task in tasks:
            await self.state_manager.add_pending_task(task)
        
        # CLARIFICATIONタスクが生成された場合は優先処理
        clarification_task = next((task for task in tasks if task.tool == "CLARIFICATION"), None)
        if clarification_task:
            return await self._handle_clarification_task(clarification_task)
        
        # 通常のタスクリスト実行
        execution_context = await self.task_executor.execute_task_sequence(tasks, user_query)
        return await self._interpret_planned_results(user_query, execution_context)
    
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
        else:
            # GPT-4系は既存設定を維持（max_tokensは指定しない）
            pass
        
        return params
    
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
                
                # シンプルなタスクリスト生成を使用
                task_list = await self._generate_simple_task_list(user_query, temperature)
                
                if task_list:
                    
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
                    
        # 全ての試行が失敗
        self.logger.error(f"[失敗] タスクリスト生成 - {max_retries}回の試行全てが失敗")
        self.logger.error(f"最後のエラー: {last_error}")
            
        return []
    
    
    async def _interpret_planned_results(self, user_query: str, results: List[Dict]) -> str:
        """計画実行の結果を解釈"""
        # 現在のリクエストのみに焦点を当て、前のタスク結果の混入を防ぐ
        recent_context = self.conversation_manager.get_recent_context(include_results=False)
        
        # 結果をシリアライズ
        serializable_results = []
        for r in results:
            result_data = {
                "step": r.get("step", r.get("task_description", "タスク")),
                "tool": r.get("tool", r.get("task_tool", "不明")),
                "success": r["success"],
                "description": r.get("description", r.get("task_description", "実行完了"))
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
            self.logger.debug("Serializable results being sent to LLM:")
            for i, result in enumerate(serializable_results):
                result_preview = str(result.get("result", "N/A"))[:100] + "..." if len(str(result.get("result", "N/A"))) > 100 else str(result.get("result", "N/A"))
                self.logger.debug(f"  [{i+1}] Tool: {result['tool']}, Result: {result_preview}")
        
        # プロンプトテンプレートから取得
        prompt = PromptTemplates.get_result_interpretation_prompt(
            recent_context=recent_context,
            user_query=user_query,
            serializable_results=json.dumps(serializable_results, ensure_ascii=False, indent=2),
            custom_instructions=self.custom_instructions
        )

        try:
            params = self._get_llm_params(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            response = await self.llm.chat.completions.create(**params)
            
            # 最終応答を取得
            final_response = response.choices[0].message.content
            
            # Rich UIの場合は美しく表示
            if self._has_rich_method('show_result_panel'):
                # JSONまたは長いテキストかどうか判定
                if len(final_response) > 100 or final_response.strip().startswith('{'):
                    self.display.show_result_panel("実行結果", final_response, success=True)
                
            # 実行結果と共に履歴に保存
            self.conversation_manager.add_to_conversation("assistant", final_response, serializable_results)
            await self.state_manager.add_conversation_entry("assistant", final_response)
            
            # basicモードの場合、結果表示ヘッダーを追加
            if self.ui_mode == "basic":
                result_with_header = f"\n{'='*50}\n🔍 実行結果\n{'='*50}\n{final_response}"
                return result_with_header
            
            return final_response
            
        except Exception as e:
            # フォールバック
            successful_results = [r for r in results if r["success"]]
            if successful_results:
                return f"実行完了しました。{len(successful_results)}個のタスクが成功しました。"
            else:
                return f"申し訳ありませんが、処理中にエラーが発生しました。"
    
    async def pause_session(self):
        """セッションを一時停止（ESCキー対応）"""
        await self.state_manager.pause_all_tasks()
        print("\n[セッション一時停止] 作業が保存されました。")
        print("次回再開時に続きから実行できます。")
        return self.state_manager.get_session_summary()
    
    async def resume_session(self) -> Dict[str, Any]:
        """セッション再開"""
        await self.state_manager.resume_paused_tasks()
        summary = self.state_manager.get_session_summary()
        
        if summary.get("has_work_to_resume", False):
            print(f"\n[セッション再開] {summary['pending_tasks']}個のタスクが待機中です")
            
            # 実行可能なタスクがある場合は継続実行を提案
            next_task = self.task_manager.get_next_executable_task()
            if next_task:
                print(f"次のタスク: {next_task.description}")
        else:
            print("\n[セッション再開] 新しいタスクの準備完了")
        
        return summary
    
    async def clear_session(self):
        """現在のセッションをクリア"""
        await self.state_manager.clear_current_session()
        print("\n[セッションクリア] 新しいセッションで開始します")
    
    def get_session_status(self) -> Dict[str, Any]:
        """現在のセッション状態を取得"""
        session_summary = self.state_manager.get_session_summary()
        task_summary = self.task_manager.get_task_summary()
        
        return {
            "session": session_summary,
            "tasks": task_summary,
            "can_resume": session_summary.get("has_work_to_resume", False),
            "ui_mode": self.ui_mode,
            "verbose": self.verbose
        }
    
    async def _generate_simple_task_list(self, user_query: str, temperature: float = 0.3) -> List[Dict[str, Any]]:
        """シンプルなタスクリスト生成"""
        try:
            recent_context = self.conversation_manager.get_recent_context(include_results=False)
            tools_info = self.connection_manager.format_tools_for_llm()
            
            # シンプルなプロンプトを使用
            prompt = PromptTemplates.get_simple_task_list_prompt(
                recent_context=recent_context,
                user_query=user_query,
                tools_info=tools_info
            )
            
            params = self._get_llm_params(
                messages=[{"role": "system", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=temperature
            )
            response = await self.llm.chat.completions.create(**params)
            
            content = safe_str(response.choices[0].message.content)
            result = json.loads(content)
            
            tasks = result.get("tasks", [])
            
            return tasks
            
        except Exception as e:
            self.logger.error(f"タスクリスト生成失敗: {e}")
            # フォールバック処理は削除 - エラー時は空リストを返す
            return []
    
    async def close(self):
        """リソースの解放"""
        # セッションをアーカイブ
        if self.state_manager and self.state_manager.current_session:
            try:
                await asyncio.wait_for(
                    self.state_manager.archive_session(),
                    timeout=2.0
                )
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
                
        # 接続のクリーンアップ
        if self.connection_manager:
            try:
                await asyncio.wait_for(
                    self.connection_manager.close(),
                    timeout=3.0
                )
            except (asyncio.TimeoutError, asyncio.CancelledError):
                # タイムアウトやキャンセルは静かに処理
                pass

def create_prompt_session(agent):
    """ESCでスキップ/キャンセル機能付きプロンプトセッション作成"""
    if not PROMPT_TOOLKIT_AVAILABLE:
        return None
    
    try:
        bindings = KeyBindings()
        
        @bindings.add('escape')  # ESC単発のみ
        async def handle_esc(event):
            # CLARIFICATION状態かチェック
            if agent.state_manager.has_pending_tasks():
                pending_tasks = agent.state_manager.get_pending_tasks()
                clarification_tasks = [t for t in pending_tasks if t.tool == "CLARIFICATION"]
                
                if clarification_tasks:
                    print("\n⏭ 確認をスキップします...")
                    event.app.exit(result='skip')
                    return
            
            # 通常時は入力をキャンセル
            print("\n[ESC] 入力をキャンセルしました")
            event.app.exit(result='')
        
        return PromptSession(key_bindings=bindings)
    
    except Exception:
        # Windows環境やCI環境でのコンソールエラーを無視
        return None

async def main():
    """メイン実行関数"""
    print("MCP Agent を起動しています...")
    agent = MCPAgent()
    await agent.initialize()
    
    try:
        # 初期化完了後のウェルカムメッセージ
        agent.display.show_welcome(
            servers=len(agent.connection_manager.clients),
            tools=len(agent.connection_manager.tools_info),
            ui_mode=agent.ui_mode
        )
        print("終了するには 'quit' または 'exit' を入力してください。")
        
        # プロンプトセッション初期化
        agent._prompt_session = create_prompt_session(agent)
        if agent._prompt_session:
            print("ESCキー: 確認スキップ/入力キャンセル")
        
        print("-" * 60)
        
        while True:
            try:
                if agent._prompt_session:
                    # prompt_toolkit使用
                    user_input = await agent._prompt_session.prompt_async("Agent> ")
                elif agent._has_rich_method('input_prompt'):
                    user_input = agent.display.input_prompt("Agent").strip()
                else:
                    user_input = input("\nAgent> ").strip()
            except (EOFError, KeyboardInterrupt):
                # Ctrl+Cでも一時停止を実行
                if hasattr(agent, 'pause_session'):
                    print("\n作業を保存中...")
                    await agent.pause_session()
                break
            
            if user_input.lower() in ['quit', 'exit', '終了']:
                break
            
            if not user_input:
                continue
            
            # リクエスト処理
            response = await agent.process_request(user_input)
            
            # Rich UIの場合はMarkdown整形表示
            if agent._has_rich_method('show_markdown_result'):
                agent.display.show_markdown_result(response)
            else:
                print(f"\n{response}")
    
    except KeyboardInterrupt:
        print("\n\n[中断] Ctrl+Cが押されました。")
    finally:
        try:
            await agent.close()
        except (asyncio.CancelledError, Exception):
            # クリーンアップエラーは無視
            pass
        print("\nMCP Agent を終了しました。")

if __name__ == "__main__":
    asyncio.run(main())