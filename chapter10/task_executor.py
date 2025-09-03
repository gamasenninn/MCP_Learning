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

import json
import re
import time
from typing import Dict, List, Any, Optional, Union
from openai import AsyncOpenAI

from state_manager import TaskState, StateManager
from task_manager import TaskManager
from connection_manager import ConnectionManager
from display_manager import DisplayManager
from error_handler import ErrorHandler
from config_manager import Config
from utils import safe_str, Logger


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
                 llm: AsyncOpenAI,
                 config: Config,
                 error_handler: ErrorHandler = None,
                 verbose: bool = True):
        """
        Args:
            task_manager: タスク管理クラス
            connection_manager: MCP接続管理クラス
            state_manager: 状態管理クラス
            display_manager: 表示管理クラス
            llm: OpenAI LLMクライアント
            config: 設定辞書
            error_handler: エラー処理クラス（オプション）
            verbose: 詳細ログ出力
        """
        self.task_manager = task_manager
        self.connection_manager = connection_manager
        self.state_manager = state_manager
        self.display = display_manager
        self.llm = llm
        self.config = config
        self.error_handler = error_handler
        self.verbose = verbose
        self.logger = Logger(verbose=verbose)
    
    async def execute_task_sequence(self, tasks: List[TaskState], user_query: str) -> str:
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
        
        for i, task in enumerate(executable_tasks):
            # ステップ開始の表示
            self.display.show_step_start(i+1, len(executable_tasks), task.description)
            
            # LLMベースでパラメータを解決
            resolved_params = await self.resolve_parameters_with_llm(task, execution_context)
            
            # ツール呼び出し情報を表示
            self.display.show_tool_call(task.tool, resolved_params)
            
            # タスク実行（リトライ機能付き）
            start_time = time.time()
            
            # ErrorHandlerに現在のクエリを伝達
            if self.error_handler:
                self.error_handler.current_user_query = user_query
            
            result = await self.execute_tool_with_retry(
                tool=task.tool,
                params=resolved_params,
                description=task.description
            )
            duration = time.time() - start_time
            
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
        
        # 完了状況の表示
        if completed:
            print(f"\n[完了] {len(completed)}個のタスクが正常完了")
        if failed:
            print(f"[失敗] {len(failed)}個のタスクでエラーが発生")
        
        return execution_context
    
    async def execute_single_task(self, task: TaskState) -> str:
        """
        単一タスクを実行
        
        Args:
            task: 実行するタスク
            
        Returns:
            実行結果メッセージ
        """
        try:
            # 依存関係を解決
            completed_tasks = self.state_manager.get_completed_tasks()
            resolved_task = await self.task_manager.resolve_task_dependencies(task, completed_tasks)
            
            # タスクを実行
            result = await self.connection_manager.call_tool(resolved_task.tool, resolved_task.params)
            
            # 結果を安全な形式に変換
            safe_result = safe_str(result)
            
            # 結果を状態に保存
            await self.state_manager.move_task_to_completed(task.task_id, safe_result)
            
            return f"タスクが完了しました: {task.description}\n結果: {safe_result}"
            
        except Exception as e:
            await self.state_manager.move_task_to_completed(task.task_id, error=str(e))
            return f"タスク実行エラー: {task.description}\nエラー: {str(e)}"
    
    async def resolve_parameters_with_llm(self, task: TaskState, execution_context: List[Dict]) -> Dict:
        """
        LLMを使用してタスクパラメータを解決
        
        Args:
            task: パラメータを解決するタスク
            execution_context: これまでの実行文脈
            
        Returns:
            解決されたパラメータ辞書
        """
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
            params_llm = self._get_llm_params(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            response = await self.llm.chat.completions.create(**params_llm)
            
            response_text = response.choices[0].message.content
            
            # JSONブロックを抽出
            json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                try:
                    json_text = json_match.group(1).strip()
                    result = json.loads(json_text)
                    resolved_params = result.get("resolved_params", params)
                    reasoning = result.get("reasoning", "")
                    
                    if self.verbose:
                        print(f"[パラメータ解決] {reasoning}")
                    
                    return resolved_params
                except json.JSONDecodeError:
                    pass
            else:
                # ```json```ブロックがない場合
                try:
                    result = json.loads(response_text.strip())
                    resolved_params = result.get("resolved_params", params)
                    reasoning = result.get("reasoning", "")
                    
                    if self.verbose:
                        print(f"[パラメータ解決] {reasoning}")
                    
                    return resolved_params
                except json.JSONDecodeError:
                    pass
            
            if self.verbose:
                print(f"[パラメータ解決失敗] JSON解析エラー: {response_text[:100]}...")
            return params
            
        except Exception as e:
            if self.verbose:
                print(f"[パラメータ解決エラー] {e}")
            return params
    
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
        if self.verbose:
            self.logger.debug(f"execute_tool_with_retry が呼び出されました: tool={tool}")
        
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
                if self.verbose:
                    self.logger.debug(f"実行コンテキスト取得エラー: {e}")
        
        max_retries = self.config.execution.max_retries
        original_params = params.copy()
        current_params = params.copy()
        current_user_query = getattr(self, 'current_user_query', '')
        
        for attempt in range(max_retries + 1):
            # 1. ツール実行（例外をキャッチして結果として扱う）
            try:
                raw_result = await self.connection_manager.call_tool(tool, current_params)
                is_exception = False
                if self.verbose:
                    self.logger.debug(f"ツール実行成功 attempt={attempt + 1}")
            except Exception as e:
                raw_result = f"ツールエラー: {e}"
                is_exception = True
                error_msg = safe_str(str(e))
                if self.verbose:
                    print(f"  [エラー] {error_msg}")
            
            # 2. LLM判断を常に実行（ErrorHandlerが利用可能な場合）
            if self.error_handler and self.llm:
                try:
                    if self.verbose:
                        self.logger.info(f"  [分析] LLM判断を開始...")
                    
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
                        self.logger.info(f"  [LLM判断] リトライ必要: {judgment.get('error_reason', 'LLM判断によるリトライ')}")
                        
                        corrected_params = judgment.get("corrected_params", current_params)
                        if corrected_params != current_params:
                            self.logger.info(f"  [修正] パラメータを修正: {safe_str(corrected_params)}")
                            current_params = corrected_params
                        
                        continue
                    else:
                        # 成功またはリトライ不要と判断
                        if self.verbose:
                            self.logger.info(f"  [LLM判断] 処理完了")
                        if attempt > 0 and not is_exception:
                            self.logger.info(f"  [成功] {attempt}回目のリトライで成功しました")
                        return judgment.get("processed_result", raw_result)
                        
                except Exception as llm_error:
                    if self.verbose:
                        self.logger.error(f"  [LLM判断エラー] {safe_str(str(llm_error))}")
                    # LLM判断でエラーの場合は結果をそのまま返すか例外処理
                    if not is_exception:
                        return raw_result
            else:
                # ErrorHandlerがない場合の処理
                if not is_exception:
                    # 成功時のログ
                    if attempt > 0 and self.verbose:
                        print(f"  [成功] {attempt}回目のリトライで成功しました")
                    return raw_result
            
            # ErrorHandlerなしで例外が発生した場合の従来のリトライ処理
            if is_exception:
                if attempt >= max_retries:
                    if self.verbose:
                        print(f"  [失敗] 最大リトライ回数({max_retries})に到達")
                    raise Exception(raw_result)
                
                if self.verbose:
                    print(f"  [リトライ] {attempt + 1}/{max_retries}")
                
                continue
        
        # ここには到達しないはずだが、念のため
        return None
    
    def _get_llm_params(self, **kwargs) -> Dict:
        """
        モデルに応じたパラメータを生成
        
        Args:
            **kwargs: LLMパラメータ
            
        Returns:
            調整済みパラメータ辞書
        """
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