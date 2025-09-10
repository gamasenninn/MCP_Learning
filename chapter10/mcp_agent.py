#!/usr/bin/env python3
"""
MCP Agent - Interactive Dialogue Engine
Claude Code風の対話型エージェント

"""

import os
import json
import asyncio
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

from connection_manager import ConnectionManager
from display_manager import DisplayManager
from error_handler import ErrorHandler
from prompts import PromptTemplates
from config_manager import ConfigManager, Config
from utils import Logger, safe_str
from state_manager import StateManager, TaskState
from task_manager import TaskManager
from conversation_manager import ConversationManager
from task_executor import TaskExecutor
from clarification_handler import ClarificationHandler
from interrupt_manager import get_interrupt_manager
from background_input_monitor import get_background_monitor
from llm_interface import LLMInterface

# Rich UI support
try:
    from display_manager_rich import RichDisplayManager
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False



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
        self.config = ConfigManager.load(config_path)
        ConfigManager.validate_config(self.config)
        
        self._initialize_ui_and_logging()  # ログ設定を最初に初期化
        self._initialize_core_components()
        self._initialize_task_executor()  # 最後に初期化（他の全てが必要なため）
        
        # prompt_toolkit用
        self._prompt_session = None
        
        # バックグラウンドタスク管理
        self._background_tasks = set()
    
    def _initialize_core_components(self):
        """コアコンポーネント（外部サービス、設定、データ構造）の初期化"""
        # 外部サービス
        self.connection_manager = ConnectionManager()
        
        # LLMInterface統一インターフェースを初期化
        self.llm_interface = LLMInterface(self.config, self.logger)
        
        # ErrorHandlerにLLMInterfaceを渡す
        self.error_handler = ErrorHandler(
            config=self.config,
            llm_interface=self.llm_interface,
            verbose=self.config.development.verbose
        )
        
        self.state_manager = StateManager()
        self.task_manager = TaskManager(self.state_manager)
        # ConversationManagerにConfig型を直接渡す
        self.conversation_manager = ConversationManager(self.state_manager, self.config)
        
        # ClarificationHandlerを初期化
        self.clarification_handler = ClarificationHandler(
            state_manager=self.state_manager,
            task_manager=self.task_manager,
            conversation_manager=self.conversation_manager,
            llm_interface=self.llm_interface,
            logger=self.logger
        )
        
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
        
        # 中断管理
        self.interrupt_manager = get_interrupt_manager(
            verbose=self.verbose,
            non_interactive_default=self.config.interrupt_handling.non_interactive_default,
            timeout=self.config.interrupt_handling.timeout
        )
        
        # バックグラウンド入力監視
        self.background_monitor = get_background_monitor(verbose=self.verbose)
    
    def _initialize_ui_and_logging(self):
        """UI表示とログ設定の初期化"""
        # ログ設定を最初に初期化
        self.verbose = self.config.development.verbose
        log_level = self.config.development.log_level
        self.logger = Logger(verbose=self.verbose, log_level=log_level)
        
        # UI表示管理
        ui_mode = self.config.display.ui_mode
        
        if ui_mode == "rich" and RICH_AVAILABLE:
            self.display = RichDisplayManager(
                show_timing=self.config.display.show_timing,
                show_thinking=self.config.display.show_thinking
            )
            self.ui_mode = "rich"
        else:
            if ui_mode == "rich" and not RICH_AVAILABLE:
                self.logger.ulog("Rich UI requested but rich library not available. Using basic UI.", "warning:warning", always_print=True)
            self.display = DisplayManager(
                show_timing=self.config.display.show_timing,
                show_thinking=self.config.display.show_thinking
            )
            self.ui_mode = "basic"
        
        if self.verbose:
            self.display.show_banner()
            if self._is_rich_ui_enabled():
                self.logger.ulog("Rich UI mode enabled", "info")
            else:
                self.logger.ulog("Basic UI mode enabled", "info")
    
    def _initialize_task_executor(self):
        """TaskExecutorの初期化（全コンポーネント初期化後に実行）"""
        self.task_executor = TaskExecutor(
            task_manager=self.task_manager,
            connection_manager=self.connection_manager,
            state_manager=self.state_manager,
            display_manager=self.display,
            llm_interface=self.llm_interface,
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
    
    
    
    def _load_agent_md(self) -> str:
        """AGENT.mdを読み込み（V3から継承）"""
        agent_md_path = "AGENT.md"
        
        if os.path.exists(agent_md_path):
            try:
                with open(agent_md_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if hasattr(self, 'logger'):
                    self.logger.ulog(f"AGENT.mdを読み込みました ({len(content)}文字)", "info", show_level=True)
                elif self.config.development.verbose:
                    self.logger.ulog(f"AGENT.mdを読み込みました ({len(content)}文字)", "info:config")
                return content
            except Exception as e:
                self.logger.ulog(f"AGENT.md読み込みエラー: {e}", "warning:warning")
                return ""
        else:
            if self.config.development.verbose:
                self.logger.ulog("AGENT.mdが見つかりません（基本能力のみで動作）", "info:info")
            return ""
    
    async def initialize(self, session_id: Optional[str] = None):
        """エージェントの初期化"""
        if self.verbose:
            self.logger.ulog(f"\n{'カスタム指示あり' if self.custom_instructions else '基本能力のみ'}", "info:instruction")
            self.logger.ulog("=" * 60, "info")
        
        # MCP接続管理を初期化（V3から継承）
        await self.connection_manager.initialize()
        
        # セッション状態を初期化
        actual_session_id = await self.state_manager.initialize_session(session_id)
        
        if self.verbose:
            self.logger.ulog(actual_session_id, "info:session")
            
            # 復元されたタスクがある場合は通知
            if self.state_manager.has_pending_tasks():
                pending_count = len(self.state_manager.get_pending_tasks())
                self.logger.ulog(f"未完了タスクが{pending_count}個あります", "info:restore")
        
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
            self.logger.ulog(f"\n#{self.session_stats['total_requests']} {user_query}", "info:request")
            self.logger.ulog("-" * 60, "info")
        
        # 会話文脈を表示
        conversation_summary = self.conversation_manager.get_conversation_summary()
        if conversation_summary["total_messages"] > 0:
            context_count = min(conversation_summary["total_messages"], 
                              self.config.conversation.context_limit)
            self.display.show_context_info(context_count)
        
        try:
            # バックグラウンド監視を開始
            self.background_monitor.start_monitoring()
            
            # 対話的実行の開始
            response = await self._execute_interactive_dialogue(user_query)
            
            # 会話履歴に追加（V3から継承）
            # 実行結果については各実行メソッドで追加される
            self.conversation_manager.add_to_conversation("user", user_query)
            
            return response
            
        except Exception as e:
            error_msg = f"処理エラー: {str(e)}"
            if self.verbose:
                self.logger.ulog(error_msg, "error:error")
            return error_msg
        finally:
            # バックグラウンド監視を停止
            self.background_monitor.stop_monitoring()
    
    async def _execute_interactive_dialogue(self, user_query: str) -> str:
        """
        統合実行エンジン - 状態管理とCLARIFICATION対応
        
        新機能:
        - 状態の永続化
        - CLARIFICATIONタスクによるユーザー確認
        - タスクの中断・再開機能
        """
        # クエリコンテキストの準備
        await self._prepare_query_context(user_query)
        
        # 実行フローの制御
        return await self._handle_execution_flow(user_query)
    
    async def _prepare_query_context(self, user_query: str) -> None:
        """クエリコンテキストの準備"""
        # 現在のクエリを保存（LLM判断で使用）
        self.current_user_query = user_query
        
        # 状態に会話を記録（リファクタリング前と同じ動作）
        await self.state_manager.add_conversation_entry("user", user_query)
    
    async def _handle_execution_flow(self, user_query: str) -> str:
        """実行フローの制御"""
        # CLARIFICATION待ちタスクがある場合のみ継続処理
        if self.clarification_handler.has_pending_clarifications():
            return await self._handle_pending_tasks(user_query)
        
        # CLARIFICATIONでない通常タスクが残っている場合はクリア（新しいリクエストを優先）
        if self.state_manager.has_pending_tasks():
            pending_tasks = self.state_manager.get_pending_tasks()
            non_clarification_tasks = [t for t in pending_tasks if t.tool != "CLARIFICATION"]
            if non_clarification_tasks:
                # 古いタスクをクリア
                for task in non_clarification_tasks:
                    await self.state_manager.move_task_to_completed(task.task_id, {"skipped": True, "reason": "新しいリクエストのため自動スキップ"})
        
        self.display.show_analysis("リクエストを分析中...")
        
        # まず処理方式を判定（CLARIFICATION対応版）
        execution_result = await self._determine_execution_type(user_query)
        execution_type = execution_result.get("type", "SIMPLE")
        
        # 状態に実行タイプを記録
        await self.state_manager.set_user_query(user_query, execution_type)
        
        # 実行タイプ別のルーティング
        return await self._route_by_execution_type(execution_type, user_query, execution_result)
    
    async def _route_by_execution_type(self, execution_type: str, user_query: str, execution_result: Dict) -> str:
        """実行タイプ別ルーティング"""
        if execution_type == "NO_TOOL":
            response = execution_result.get("response", "了解しました。")
            await self.state_manager.add_conversation_entry("assistant", response)
            self.conversation_manager.add_to_conversation("assistant", response)
            return response
        elif execution_type == "CLARIFICATION":
            # ユーザーへの確認が必要（ClarificationHandlerに委譲）
            return await self.clarification_handler.handle_clarification_needed(user_query, execution_result)
        else:
            # SIMPLE/COMPLEX統合：全てのツール実行要求を統一メソッドで処理
            return await self._execute_with_tasklist(user_query)
    
    async def _determine_execution_type(self, user_query: str) -> Dict:
        """CLARIFICATION対応の実行方式判定"""
        recent_context = self.conversation_manager.get_recent_context(include_results=False)
        tools_info = self.connection_manager.format_tools_for_llm()
        
        return await self.llm_interface.determine_execution_type(user_query, recent_context, tools_info)
    
    async def _handle_pending_tasks(self, user_query: str) -> str:
        """未完了タスクがある場合の処理"""
        pending_tasks = self.state_manager.get_pending_tasks()
        
        # CLARIFICATIONタスクがある場合（ClarificationHandlerに委譲）
        if self.clarification_handler.has_pending_clarifications():
            # CLARIFICATION応答の処理
            result_query = await self.clarification_handler.process_clarification_response(user_query)
            
            # skipの場合はスマートクエリが返される、通常の場合は結合クエリが返される
            if user_query.lower() == 'skip':
                self.logger.ulog("\n質問をスキップしました。利用可能な情報で処理を続行します。", "info", always_print=True)
                
            # 状態をリセットして新しいクエリとして処理
            await self.state_manager.set_user_query(result_query, "TOOL")
            
            return await self._execute_with_tasklist(result_query)
        
        # 通常のタスクを継続実行
        return await self._continue_pending_tasks(user_query)
    
    async def _process_clarification_task(self, task: TaskState, user_query: str) -> str:
        """CLARIFICATIONタスクの処理"""
        if user_query.lower() == 'skip':
            # スキップ処理
            smart_query = await self.task_manager.handle_clarification_skip(
                task, self.conversation_manager, self.state_manager
            )
            self.logger.ulog("\n質問をスキップしました。会話履歴と文脈から最適な処理を実行します。", "info", always_print=True)
            return await self._execute_with_tasklist(smart_query)
        else:
            # 通常の応答処理
            combined_query = await self.task_manager.handle_clarification_response(
                task, user_query, self.state_manager
            )
            return await self._execute_with_tasklist(combined_query)
    
    async def _continue_pending_tasks(self, user_query: str) -> str:
        """保留中タスクの継続実行"""
        next_task = self.task_manager.get_next_executable_task()
        
        if not next_task:
            return "実行可能なタスクがありません。"
        
        # タスクを実行
        result = await self.task_executor.execute_task_sequence([next_task], user_query)
        return result
    
    
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
            return await self.clarification_handler.execute_clarification_task(clarification_task)
        
        # 通常のタスクリスト実行
        execution_context = await self.task_executor.execute_task_sequence(tasks, user_query)
        
        # すべてのタスクがスキップされた場合の処理
        if not execution_context:
            return "タスクがスキップされました。"
            
        return await self._interpret_planned_results(user_query, execution_context)
    
    
    async def _generate_task_list_with_retry(self, user_query: str) -> List[Dict]:
        """
        リトライ機能付き適応的タスクリスト生成
        
        Args:
            user_query: ユーザークエリ
            
        Returns:
            生成されたタスクリスト
        """
        retry_config = self.config.execution.retry_strategy
        max_retries = retry_config.max_retries
        use_progressive = retry_config.progressive_temperature
        initial_temp = retry_config.initial_temperature
        temp_increment = retry_config.temperature_increment
        
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # プログレッシブtemperature調整
                if use_progressive and attempt > 0:
                    temperature = min(initial_temp + (attempt * temp_increment), 0.9)
                else:
                    temperature = initial_temp
                
                # 統一タスクリスト生成を使用
                task_list = await self._generate_unified_task_list(user_query, temperature)
                
                if task_list:
                    
                    if attempt > 0:
                        self.logger.ulog(f"タスクリスト生成 - {attempt + 1}回目の試行で成功", "info:success", show_level=True)
                    
                    # タスク数制限（全体的な上限）
                    max_tasks = self.config.execution.max_tasks
                    if len(task_list) > max_tasks:
                        self.logger.ulog(f"タスク数制限: {len(task_list)} → {max_tasks}", "warning", show_level=True)
                        task_list = task_list[:max_tasks]
                    
                    return task_list
                else:
                    last_error = f"試行{attempt + 1}: 空のタスクリストが生成されました"
                    
            except json.JSONDecodeError as e:
                last_error = f"試行{attempt + 1}: JSON解析エラー - {str(e)}"
                self.logger.ulog(last_error, "info:retry")
            except Exception as e:
                last_error = f"試行{attempt + 1}: {str(e)}"
                self.logger.ulog(last_error, "info:retry")
                    
        # 全ての試行が失敗
        self.logger.ulog(f"タスクリスト生成 - {max_retries}回の試行全てが失敗", "error:failed", show_level=True)
        self.logger.ulog(f"最後のエラー: {last_error}", "error", show_level=True)
            
        return []
    
    
    async def _interpret_planned_results(self, user_query: str, results: List[Dict]) -> str:
        """計画実行の結果を解釈"""
        # 結果のシリアライズ
        serializable_results = self._serialize_execution_results(results)
        
        # LLMによる結果解釈
        final_response = await self._generate_interpretation_response(user_query, serializable_results)
        
        # 表示・保存処理
        self._handle_result_display_and_storage(final_response, serializable_results)
        
        # basicモードの場合、結果表示ヘッダーを追加
        if self.ui_mode == "basic":
            result_with_header = f"\n{'='*50}\n🔍 実行結果\n{'='*50}\n{final_response}"
            return result_with_header
        
        return final_response
    
    def _serialize_execution_results(self, results: List[Dict]) -> List[Dict]:
        """実行結果のシリアライズ処理"""
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
                max_length = self.config.result_display.max_result_length
                result_str = str(r["result"])
                
                if len(result_str) <= max_length:
                    result_data["result"] = result_str
                else:
                    # 長すぎる場合は省略情報を追加
                    result_data["result"] = result_str[:max_length]
                    if self.config.result_display.show_truncated_info:
                        result_data["result"] += f"\n[注記: 結果が長いため{max_length}文字で省略。実際の結果はより多くのデータを含む可能性があります]"
            else:
                result_data["error"] = r["error"]
            
            serializable_results.append(result_data)
        
        # デバッグ: LLMに渡されるデータを確認
        self.logger.ulog("Serializable results being sent to LLM:", "debug", show_level=True)
        for i, result in enumerate(serializable_results):
            result_preview = str(result.get("result", "N/A"))[:100] + "..." if len(str(result.get("result", "N/A"))) > 100 else str(result.get("result", "N/A"))
            self.logger.ulog(f"[{i+1}] Tool: {result['tool']}, Result: {result_preview}", "debug", show_level=True)
        
        return serializable_results
    
    async def _generate_interpretation_response(self, user_query: str, serializable_results: List[Dict]) -> str:
        """LLMによる結果解釈処理"""
        recent_context = self.conversation_manager.get_recent_context(include_results=False)
        
        return await self.llm_interface.interpret_results(
            user_query=user_query,
            results=serializable_results,
            context=recent_context,
            custom_instructions=self.custom_instructions
        )
    
    def _handle_result_display_and_storage(self, final_response: str, serializable_results: List[Dict]) -> None:
        """表示・保存処理"""
        # Rich UIの場合は美しく表示
        if self._has_rich_method('show_result_panel'):
            # JSONまたは長いテキストかどうか判定
            if len(final_response) > 100 or final_response.strip().startswith('{'):
                self.display.show_result_panel("実行結果", final_response, success=True)
            
        # 実行結果と共に履歴に保存
        self.conversation_manager.add_to_conversation("assistant", final_response, serializable_results)
        
        # 状態管理への追加は非同期なので、必要に応じて別途実行
        import asyncio
        task = asyncio.create_task(self.state_manager.add_conversation_entry("assistant", final_response))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
        # basicモードの場合はヘッダー付き表示で返す（呼び出し元で処理）
    
    async def pause_session(self):
        """セッションを一時停止（ESCキー対応）"""
        await self.state_manager.pause_all_tasks()
        self.logger.ulog("\n作業が保存されました。", "info:pause", always_print=True)
        self.logger.ulog("次回再開時に続きから実行できます。", "info", always_print=True)
        return self.state_manager.get_session_summary()
    
    async def resume_session(self) -> Dict[str, Any]:
        """セッション再開"""
        await self.state_manager.resume_paused_tasks()
        summary = self.state_manager.get_session_summary()
        
        if summary.get("has_work_to_resume", False):
            self.logger.ulog(f"\n{summary['pending_tasks']}個のタスクが待機中です", "info:resume", always_print=True)
            
            # 実行可能なタスクがある場合は継続実行を提案
            next_task = self.task_manager.get_next_executable_task()
            if next_task:
                self.logger.ulog(f"次のタスク: {next_task.description}", "info", always_print=True)
        else:
            self.logger.ulog("\n新しいタスクの準備完了", "info:resume", always_print=True)
        
        return summary
    
    
    
    
    async def _generate_unified_task_list(self, user_query: str, temperature: float = 0.3) -> List[Dict[str, Any]]:
        """統一タスクリスト生成（SIMPLE/COMPLEX統合版）"""
        recent_context = self.conversation_manager.get_recent_context(include_results=False)
        tools_info = self.connection_manager.format_tools_for_llm()
        
        return await self.llm_interface.generate_task_list(
            user_query=user_query,
            context=recent_context,
            tools_info=tools_info,
            custom_instructions=self.custom_instructions
        )
    
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
        
        # バックグラウンドタスクのクリーンアップ
        if hasattr(self, '_background_tasks') and self._background_tasks:
            try:
                for task in self._background_tasks:
                    task.cancel()
                await asyncio.gather(*self._background_tasks, return_exceptions=True)
            except Exception as e:
                self.logger.ulog(f"Error cleaning up background tasks: {e}", "error:cleanup")
        
        # バックグラウンド監視を確実に停止
        try:
            self.background_monitor.stop_monitoring()
        except Exception as e:
            self.logger.ulog(f"Error in cleanup: {e}", "error:cleanup")

