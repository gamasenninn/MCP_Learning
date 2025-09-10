#!/usr/bin/env python3
"""
Task Executor for MCP Agent
タスク実行のオーケストレーションを担当

主な責任:
- タスクシーケンスの実行
- 単一タスクの実行
- パラメータの解決（LLMベース）
- ツール実行とリトライ処理
"""

import asyncio
import json
import re
import time
from typing import Dict, List, Any, Optional, Union

from state_manager import TaskState, StateManager
from task_manager import TaskManager
from connection_manager import ConnectionManager
from display_manager import DisplayManager
from error_handler import ErrorHandler
from config_manager import Config
from utils import safe_str, Logger
from interrupt_manager import get_interrupt_manager
from llm_interface import LLMInterface

# カスタム例外
class EscInterrupt(Exception):
    """ESCキーによる中断を示すカスタム例外"""
    pass


# スキップ判定用のセンチネル
SKIP = object()


class TaskExecutor:
    """
    タスク実行のオーケストレーションクラス
    
    TaskManagerが管理するタスクを実際に実行し、
    ConnectionManagerを通じてツールを呼び出す
    """
    
    def __init__(self, 
                 task_manager: TaskManager,
                 connection_manager: ConnectionManager,
                 state_manager: StateManager,
                 display_manager: DisplayManager,
                 llm_interface: LLMInterface,
                 config: Config,
                 error_handler: ErrorHandler = None,
                 verbose: bool = True):
        """
        Args:
            task_manager: タスク管理クラス
            connection_manager: MCP接続管理クラス
            state_manager: 状態管理クラス
            display_manager: 表示管理クラス
            llm_interface: LLM統一インターフェース
            config: 設定辞書
            error_handler: エラー処理クラス（オプション）
            verbose: 詳細ログ出力
        """
        self.task_manager = task_manager
        self.connection_manager = connection_manager
        self.state_manager = state_manager
        self.display = display_manager
        self.llm_interface = llm_interface
        self.config = config
        self.error_handler = error_handler
        self.verbose = verbose
        self.logger = Logger(verbose=verbose)
        
        # 中断管理
        self.interrupt_manager = get_interrupt_manager(verbose=verbose)
        
        # アクティブタスク管理
        self.active_tasks = set()
    
    async def execute_task_sequence(self, tasks: List[TaskState], user_query: str) -> List[Dict]:
        # 実行停止フラグ
        self._stop_execution = False
        """
        タスクシーケンスを順次実行
        
        Args:
            tasks: 実行するタスクリスト
            user_query: 元のユーザークエリ（文脈用）
            
        Returns:
            実行結果サマリー
        """
        # CLARIFICATIONタスクを除外
        task_list_for_display = [
            {
                "tool": task.tool,
                "description": task.description,
                "params": task.params
            }
            for task in tasks if task.tool != "CLARIFICATION"
        ]
        
        if task_list_for_display:
            # タスク一覧の表示
            tasks_for_display = [{"description": t['description']} for t in task_list_for_display]
            self.display.show_task_list(tasks_for_display)
        
        # 実行結果を追跡
        completed = []
        failed = []
        execution_context = []
        
        # タスクを順次実行
        executable_tasks = [t for t in tasks if t.tool != "CLARIFICATION"]
        
        # 現在のユーザークエリを保存
        self.current_user_query = user_query
        
        # 新しいタスクシーケンス開始時に中断状態をリセット
        # 既存の中断状態を確認してから適切に処理
        await self.handle_interruption()
        
        for i, task in enumerate(executable_tasks):
            # 中断チェックポイント1: タスク開始前
            interrupt_status = self.interrupt_manager.get_status()
            self.logger.ulog(f"[STATUS] タスク{i+1}開始前: 中断状態={interrupt_status['interrupt_state']}", "debug:interrupt")  # デバッグ用
            
            if self.interrupt_manager.check_interrupt():
                self.logger.ulog("[CHECK] タスク開始前に中断検知", "info:interrupt", always_print=True)
                choice = await self.interrupt_manager.handle_interrupt_choice()
                if choice == 'abort':
                    self.logger.ulog("[ABORT] タスクシーケンスを中止しました", "warning:abort", always_print=True)
                    break
                elif choice == 'skip':
                    self.logger.ulog(f"[SKIP] タスクをスキップ: {task.description}", "info:skip", always_print=True)
                    await self.state_manager.move_task_to_completed(task.task_id, {"skipped": True})
                    continue
                # choice == 'continue' の場合は継続
            else:
                self.logger.ulog(f"[DEBUG] 中断チェック結果: 継続実行", "debug:interrupt")
            
            # タスク実行開始を記録
            self.interrupt_manager.start_execution(task.description)
            
            try:
                # ステップ開始の表示
                self.display.show_step_start(i+1, len(executable_tasks), task.description)
                
                # LLMベースでパラメータを解決
                resolved_params = await self.resolve_parameters_with_llm(task, execution_context)
                
                # スキップされた場合の処理
                if resolved_params is SKIP:
                    self.logger.ulog(f"[SKIP] パラメータ解決段階でスキップ: {task.description}", "info:skip", always_print=True)
                    continue  # 次のタスクへ
                
                # ツール呼び出し情報を表示
                self.display.show_tool_call(task.tool, resolved_params)
                
                # タスク実行（リトライ機能付き）
                start_time = time.monotonic()
                
                # ErrorHandlerに現在のクエリを伝達
                if self.error_handler:
                    self.error_handler.current_user_query = user_query
                
                result = await self.execute_tool_with_retry(
                    tool=task.tool,
                    params=resolved_params,
                    description=task.description
                )
                duration = time.monotonic() - start_time
                
                # スキップされた場合の処理
                if result is SKIP:
                    self.logger.ulog(f"[SKIP] タスクがスキップされました: {task.description}", "info:skip", always_print=True)
                    continue  # 次のタスクへ
                
                # 結果を安全な形式に変換
                safe_result = safe_str(result)
                
                # 成功時の処理
                await self.state_manager.move_task_to_completed(task.task_id, safe_result)
                completed.append(i)
                
                # ステップ完了の表示（実行時間付き）
                self.display.show_step_complete(task.description, duration, success=True)
                
                # チェックリストの更新表示
                tasks_with_duration = [
                    {"description": t.description, "duration": duration if j in completed else None}
                    for j, t in enumerate(executable_tasks)
                ]
                self.display.update_checklist(tasks_with_duration, current=-1, completed=completed, failed=failed)
                
                execution_context.append({
                    "success": True,
                    "result": safe_result,
                    "duration": duration,
                    "task_description": task.description,
                    "tool": task.tool
                })
                
            finally:
                # 必ずend_execution()を呼ぶ
                self.interrupt_manager.end_execution()
        
        # 完了状況の表示
        if completed:
            self.logger.ulog(f"\n{len(completed)}個のタスクが正常完了", "info:completed")
        if failed:
            self.logger.ulog(f"{len(failed)}個のタスクでエラーが発生", "error:failed")
        
        # すべてスキップされた場合
        # 実行コンテキストを返す（結果解釈は呼び出し元で処理）
        return execution_context
    
    async def resolve_parameters_with_llm(self, task: TaskState, execution_context: List[Dict]) -> Dict:
        """
        LLMを使用してタスクパラメータを解決
        
        Args:
            task: パラメータを解決するタスク
            execution_context: これまでの実行文脈
            
        Returns:
            解決されたパラメータ辞書
        """
        # 中断チェック（パラメータ解決前）
        if self.interrupt_manager.should_abort():
            raise EscInterrupt("ユーザーが中止を確定")
        if self.interrupt_manager.check_interrupt():
            # 要求中の場合は選択肢を提示
            choice = await self.interrupt_manager.handle_interrupt_choice()
            if choice == 'abort':
                raise EscInterrupt("ユーザーが中止を選択")
            elif choice == 'skip':
                return SKIP
            # continue の場合は処理を続行
        
        tool = task.tool
        params = task.params
        description = task.description
        
        # 実行文脈から結果情報を抽出
        context_info = []
        if execution_context:
            for i, ctx in enumerate(execution_context):
                if ctx.get("success"):
                    result_str = str(ctx.get("result", ""))
                    task_desc = ctx.get("task_description", "不明なタスク")
                    context_info.append(f"タスク{i+1}: {task_desc} → 結果: {result_str}")
        
        context_str = "\n".join(context_info) if context_info else "前の実行結果はありません"
        
        prompt = f"""次のタスクを実行するためのパラメータを、実行履歴から適切に決定してください。

## 実行するタスク
- ツール: {tool}
- 説明: {description}
- 元のパラメータ: {json.dumps(params, ensure_ascii=False)}

## これまでの実行履歴
{context_str}

## 指示
前の実行結果を参考にして、このタスクに最適なパラメータを決定してください。
前のタスクの数値結果を使う場合は、その数値を直接パラメータに設定してください。

## 出力形式（JSON）
```json
{{
  "resolved_params": {{実際のパラメータ値}},
  "reasoning": "パラメータを決定した理由"
}}
```"""

        try:
            # LLM呼び出し前の中断チェック
            if self.interrupt_manager.check_interrupt():
                self.logger.ulog("[CHECK] パラメータ解決前に中断検知", "info:interrupt", always_print=True)
                return params
            
            # LLMInterfaceを使用してパラメータを解決
            tools_info = self.connection_manager.format_tools_for_llm()
            user_query = f"タスク: {description}"
            
            task_dict = {
                'tool': tool,
                'params': params,
                'description': description
            }
            
            return await self.llm_interface.resolve_task_parameters(
                task_dict=task_dict,
                context=execution_context or [],
                tools_info=tools_info,
                user_query=user_query
            )
            
        except Exception as e:
            self.logger.ulog(f"{e}", "error:param", show_level=True)
            return params
    
    async def _execute_tool_direct(self, tool: str, params: Dict, description: str = "") -> Any:
        """中断なしでツールを直接実行"""
        return await self.connection_manager.call_tool(tool, params)
    
    async def _execute_tool_with_interrupt(self, tool: str, params: Dict):
        """
        中断可能なツール実行ラッパー
        定期的に中断をチェックしながらツールを実行する
        """
        # メインのツール実行タスク
        tool_task = asyncio.create_task(self.connection_manager.call_tool(tool, params))
        self.active_tasks.add(tool_task)
        tool_task.add_done_callback(self.active_tasks.discard)
        
        # 中断監視タスク
        async def interrupt_monitor():
            while not tool_task.done():
                await asyncio.sleep(0.1)  # 0.1秒ごとに中断チェック
                if self.interrupt_manager.check_interrupt():
                    self.logger.ulog("[CHECK] ツール実行中に中断検知", "info:interrupt", always_print=True)
                    choice = await self.interrupt_manager.handle_interrupt_choice()
                    if choice in ('abort', 'skip'):
                        tool_task.cancel()
                        return choice      # ← raise せず戻り値で通知
                    # continue選択時は監視を続行（returnせずループ継続）
                    continue

        monitor_task = asyncio.create_task(interrupt_monitor())
        self.active_tasks.add(monitor_task)
        monitor_task.add_done_callback(self.active_tasks.discard)

        try:
            result = await tool_task
            monitor_task.cancel()
            return result
        except asyncio.CancelledError:
            # 監視側の決定を受け取る
            try:
                choice = await asyncio.wait_for(monitor_task, timeout=0.05)
            except Exception:
                choice = 'abort'
            if choice == 'skip':
                return SKIP
            elif choice == 'continue':
                # 継続の場合はツールを再実行
                return await self._execute_tool_direct(tool, params, description)
            raise Exception("ユーザーによる中断")
        except Exception:
            monitor_task.cancel()
            raise
    
    async def execute_tool_with_retry(self, tool: str, params: Dict, description: str = "") -> Any:
        """
        リトライ機能付きでツールを実行（LLM判断機能統合版）
        
        Args:
            tool: ツール名
            params: 実行パラメータ
            description: タスクの説明
            
        Returns:
            実行結果
        """
        self.logger.ulog(f"execute_tool_with_retry が呼び出されました: tool={tool}", "debug", show_level=True)
        
        # ErrorHandlerの試行履歴をリセット（新しいタスク開始時）
        if self.error_handler:
            self.error_handler.attempt_history = []
        
        # 実行コンテキストを取得（過去の実行結果）
        execution_context = []
        if self.state_manager:
            try:
                completed_tasks = self.state_manager.get_completed_tasks()
                # 最新の5個のタスク結果を取得（汎用的）
                for task in completed_tasks[-5:]:
                    if task.result:  # 結果がある場合のみ
                        execution_context.append({
                            "tool": task.tool,
                            "description": task.description,
                            "result": task.result
                        })
            except Exception as e:
                self.logger.ulog(f"実行コンテキスト取得エラー: {e}", "debug", show_level=True)
        
        max_retries = self.config.execution.max_retries
        original_params = params.copy()
        current_params = params.copy()
        current_user_query = getattr(self, 'current_user_query', '')
        
        for attempt in range(max_retries + 1):
            # デコレータで中断チェックは処理されるため、個別のチェックは削除
            
            # 1. ツール実行（例外をキャッチして結果として扱う）
            try:
                # ツール実行を中断可能にするためのラッパー（中断チェックはこの内部で実行）
                raw_result = await self._execute_tool_with_interrupt(tool, current_params)
                
                # SKIPが返された場合は即座に終了
                if raw_result is SKIP:
                    return SKIP
                
                is_exception = False
                self.logger.ulog(f"ツール実行成功 attempt={attempt + 1}", "debug", show_level=True)
            except Exception as e:
                raw_result = f"ツールエラー: {e}"
                is_exception = True
                error_msg = safe_str(str(e))
                self.logger.ulog(f"{error_msg}", "error:error", show_level=True)
            
            # 2. LLM判断を常に実行（ErrorHandlerが利用可能な場合）
            if self.error_handler and self.llm_interface:
                try:
                    self.logger.ulog("LLM判断を開始...", "info:analysis", show_level=True)
                    
                    # すべての結果をLLMに判断させる（元の設計思想）
                    judgment = await self.error_handler.judge_and_process_result(
                        tool=tool,
                        current_params=current_params,
                        original_params=original_params,
                        result=raw_result,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        description=description,
                        current_user_query=current_user_query,
                        execution_context=execution_context
                    )
                    
                    # 3. LLMの判断に基づいて行動
                    if judgment.get("needs_retry", False) and attempt < max_retries:
                        self.logger.ulog(f"リトライ必要: {judgment.get('error_reason', 'LLM判断によるリトライ')}", "info:llm_judgment", show_level=True)
                        
                        corrected_params = judgment.get("corrected_params", current_params)
                        if corrected_params != current_params:
                            self.logger.ulog(f"パラメータを修正: {safe_str(corrected_params)}", "info:correction", show_level=True)
                            current_params = corrected_params
                        
                        continue
                    else:
                        # 成功またはリトライ不要と判断
                        self.logger.ulog("処理完了", "info:llm_judgment", show_level=True)
                        if attempt > 0 and not is_exception:
                            self.logger.ulog(f"{attempt}回目のリトライで成功しました", "info:success", show_level=True)
                        return judgment.get("processed_result", raw_result)
                        
                except Exception as llm_error:
                    self.logger.ulog(f"{safe_str(str(llm_error))}", "error:llm_error", show_level=True)
                    # LLM判断でエラーの場合は結果をそのまま返すか例外処理
                    if not is_exception:
                        return raw_result
            else:
                # ErrorHandlerがない場合の処理
                if not is_exception:
                    # 成功時のログ
                    if attempt > 0:
                        self.logger.ulog(f"{attempt}回目のリトライで成功しました", "info:success", show_level=True)
                    return raw_result
            
            # ErrorHandlerなしで例外が発生した場合の従来のリトライ処理
            if is_exception:
                if attempt >= max_retries:
                    self.logger.ulog(f"最大リトライ回数({max_retries})に到達", "info:failed", show_level=True)
                    raise Exception(raw_result)
                
                self.logger.ulog(f"{attempt + 1}/{max_retries}", "info:retry", show_level=True)
                
                continue
        
        # ここには到達しないはずだが、念のため
        return None
    
    async def cleanup(self):
        """全アクティブタスクのキャンセル"""
        if self.active_tasks:
            for task in self.active_tasks:
                task.cancel()
            await asyncio.gather(*self.active_tasks, return_exceptions=True)
    
    async def handle_interruption(self):
        """中断処理の改善"""
        # 既存の中断処理ロジックを元の動作に合わせて修正
        # 元のコードでは、タスクシーケンス開始前にresetしていたが、
        # 適切な中断チェックのみを行う
        pass
    
