#!/usr/bin/env python3
"""
Simple Task Executor for MCP Agent V3
タスクの実行とリトライ機能（シンプル版）

V3での特徴：
- 複雑なエラー分析は削除
- 基本的な実行とリトライに特化
- AGENT.mdの指示に従う
"""

import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Task:
    """実行するタスクの情報"""
    id: str
    tool: str
    params: Dict[str, Any]
    dependencies: List[str] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


@dataclass 
class TaskResult:
    """タスクの実行結果"""
    task_id: str
    tool: str
    params: Dict[str, Any]
    success: bool
    result: Any = None
    error: str = None
    execution_time: float = 0.0
    retry_count: int = 0


class TaskExecutor:
    """
    シンプルなタスク実行器（V3版）
    
    複雑なエラー分析や学習機能を削除し、
    基本的な実行とリトライに専念
    """
    
    def __init__(self, connection_manager, verbose: bool = True, param_corrector=None):
        """
        Args:
            connection_manager: ConnectionManagerのインスタンス
            verbose: 詳細ログ出力
            param_corrector: パラメータ修正を行うコールバック関数
        """
        self.connection_manager = connection_manager
        self.verbose = verbose
        self.execution_history: List[TaskResult] = []
        self.param_corrector = param_corrector
    
    async def execute_single(self, task: Task, max_retry: int = 3) -> TaskResult:
        """
        単一タスクを実行（リトライ付き）
        
        Args:
            task: 実行するタスク
            max_retry: 最大リトライ回数
        
        Returns:
            TaskResult: 実行結果
        """
        start_time = asyncio.get_event_loop().time()
        retry_count = 0
        last_error = None
        
        if self.verbose:
            print(f"\n[実行] {task.tool}")
            print(f"  パラメータ: {task.params}")
        
        # リトライループ
        for attempt in range(max_retry + 1):
            try:
                # ツール実行
                result = await self.connection_manager.call_tool(
                    task.tool, 
                    task.params
                )
                
                # 成功
                execution_time = asyncio.get_event_loop().time() - start_time
                task_result = TaskResult(
                    task_id=task.id,
                    tool=task.tool,
                    params=task.params,
                    success=True,
                    result=result,
                    execution_time=execution_time,
                    retry_count=retry_count
                )
                
                if self.verbose:
                    if retry_count > 0:
                        print(f"  [成功] リトライ {retry_count}回目で成功")
                    else:
                        print(f"  [成功] 実行時間: {execution_time:.2f}秒")
                
                self.execution_history.append(task_result)
                return task_result
                
            except Exception as e:
                last_error = str(e)
                retry_count = attempt
                
                # エラーの種類を判別
                error_type = self._classify_error(str(e))
                
                if self.verbose:
                    if attempt < max_retry:
                        print(f"  [リトライ {attempt + 1}/{max_retry}] エラー: {last_error}")
                    else:
                        print(f"  [失敗] 最大リトライ回数に到達: {last_error}")
                
                # パラメータエラーの場合、修正を試みる
                if error_type == "PARAM_ERROR" and self.param_corrector and attempt < max_retry:
                    if self.verbose:
                        print(f"  [分析] パラメータエラーの可能性 - 修正を試行")
                    
                    try:
                        corrected_params = await self.param_corrector(
                            task.tool, 
                            task.params, 
                            str(e)
                        )
                        
                        if corrected_params and corrected_params != task.params:
                            if self.verbose:
                                print(f"  [修正] パラメータを修正: {corrected_params}")
                            task.params = corrected_params
                            # 修正後、残りの試行を1回に制限（無限ループ防止）
                            max_retry = min(max_retry, attempt + 2)
                        else:
                            if self.verbose:
                                print(f"  [修正] パラメータ修正に失敗")
                    except Exception as correction_error:
                        if self.verbose:
                            print(f"  [修正エラー] {correction_error}")
                
                # 最後の試行でなければ少し待つ
                if attempt < max_retry:
                    if error_type == "TRANSIENT_ERROR":
                        await asyncio.sleep(0.5)  # 一時的エラーは短時間待機
                    else:
                        await asyncio.sleep(0.1)  # その他は短時間待機
        
        # 失敗
        execution_time = asyncio.get_event_loop().time() - start_time
        task_result = TaskResult(
            task_id=task.id,
            tool=task.tool,
            params=task.params,
            success=False,
            error=last_error,
            execution_time=execution_time,
            retry_count=retry_count
        )
        
        self.execution_history.append(task_result)
        return task_result
    
    async def execute_batch(self, tasks: List[Task], max_retry: int = 3) -> List[TaskResult]:
        """
        複数タスクを依存関係を考慮して実行
        
        Args:
            tasks: 実行するタスクのリスト
            max_retry: 各タスクの最大リトライ回数
        
        Returns:
            List[TaskResult]: 各タスクの実行結果
        """
        if not tasks:
            return []
        
        if self.verbose:
            print(f"\n[タスク実行] {len(tasks)}個のタスクを実行")
            print("=" * 50)
        
        results: List[TaskResult] = []
        executed_tasks: Dict[str, TaskResult] = {}
        remaining_tasks = tasks.copy()
        
        # 依存関係を解決しながら実行
        while remaining_tasks:
            executed_in_round = []
            
            # 実行可能なタスクを探す
            for task in remaining_tasks:
                can_execute = True
                
                # 依存関係をチェック
                for dep_id in task.dependencies:
                    if dep_id not in executed_tasks:
                        can_execute = False
                        break
                    # 依存タスクが失敗していた場合
                    elif not executed_tasks[dep_id].success:
                        can_execute = False
                        break
                
                if can_execute:
                    # 依存タスクの結果をパラメータに注入
                    resolved_params = self._resolve_task_references(
                        task.params, 
                        executed_tasks
                    )
                    resolved_task = Task(
                        id=task.id,
                        tool=task.tool,
                        params=resolved_params,
                        dependencies=task.dependencies
                    )
                    
                    # タスク実行
                    if self.verbose:
                        print(f"[{len(results) + 1}/{len(tasks)}] タスク: {task.tool}")
                    
                    result = await self.execute_single(resolved_task, max_retry)
                    results.append(result)
                    executed_tasks[task.id] = result
                    executed_in_round.append(task)
            
            # 実行したタスクを残りから削除
            for task in executed_in_round:
                remaining_tasks.remove(task)
            
            # 実行可能なタスクがない場合（循環依存など）
            if not executed_in_round and remaining_tasks:
                if self.verbose:
                    print("[エラー] 依存関係を解決できないタスクが残っています")
                for task in remaining_tasks:
                    error_result = TaskResult(
                        task_id=task.id,
                        tool=task.tool,
                        params=task.params,
                        success=False,
                        error="依存関係を解決できません",
                        execution_time=0.0
                    )
                    results.append(error_result)
                break
        
        # 統計表示
        if self.verbose:
            self._print_execution_stats(results)
        
        return results
    
    def _resolve_task_references(self, params: Dict[str, Any], executed_tasks: Dict[str, TaskResult]) -> Dict[str, Any]:
        """
        パラメータ内のタスク参照（{task_X}）を実際の値に置換
        
        Args:
            params: 元のパラメータ
            executed_tasks: 実行済みタスクの結果
        
        Returns:
            解決されたパラメータ
        """
        resolved = {}
        
        for key, value in params.items():
            if isinstance(value, str) and value.startswith("{task_"):
                # タスク参照の解決
                task_ref = value[1:-1]  # {task_X} -> task_X
                if task_ref in executed_tasks:
                    task_result = executed_tasks[task_ref]
                    if task_result.success:
                        # CallToolResultから実際の値を抽出
                        resolved[key] = self._extract_actual_value(task_result.result)
                    else:
                        resolved[key] = None
                else:
                    resolved[key] = value  # 解決できない場合はそのまま
            else:
                resolved[key] = value
        
        return resolved
    
    def _extract_actual_value(self, result) -> Any:
        """
        CallToolResultから実際の値を抽出
        
        Args:
            result: ツールの実行結果（CallToolResult等）
            
        Returns:
            実際の値
        """
        # CallToolResultオブジェクトの場合
        if hasattr(result, 'data') and result.data is not None:
            # FastMCP形式: dataフィールドに実際の値
            return result.data
        elif hasattr(result, 'structured_content') and result.structured_content:
            # 構造化コンテンツから値を取得
            content = result.structured_content
            if isinstance(content, dict):
                # 'result' キーがあればそれを使用
                if 'result' in content:
                    return content['result']
                # 'results' キーがあれば（データベース結果等）
                elif 'results' in content:
                    return content
                # その他のキーがある場合は最初の値
                elif content:
                    return list(content.values())[0]
            return content
        elif hasattr(result, 'content') and result.content:
            # コンテンツから値を抽出
            content = result.content
            if isinstance(content, list) and len(content) > 0:
                first_content = content[0]
                if hasattr(first_content, 'text'):
                    text = first_content.text
                    # 数値への変換を試みる
                    try:
                        # 整数
                        if text.isdigit() or (text.startswith('-') and text[1:].isdigit()):
                            return int(text)
                        # 浮動小数点数
                        return float(text)
                    except:
                        return text
                return first_content
            return content
        else:
            # プリミティブ値やその他の場合
            return result
    
    def _classify_error(self, error_msg: str) -> str:
        """
        エラーメッセージを分類
        
        Args:
            error_msg: エラーメッセージ
            
        Returns:
            エラーの分類 (PARAM_ERROR, TRANSIENT_ERROR, UNKNOWN)
        """
        error_lower = error_msg.lower()
        
        # パラメータエラー（修正が必要）
        param_error_indicators = [
            '404', 'not found', 'invalid parameter', '400', 'bad request',
            'parameter', 'argument', 'invalid input', 'validation error',
            'no such column', 'no such table', 'syntax error'
        ]
        
        if any(indicator in error_lower for indicator in param_error_indicators):
            return "PARAM_ERROR"
        
        # 一時的エラー（リトライで解決可能）
        transient_error_indicators = [
            'timeout', 'connection', '503', '500', '502', '504',
            'network', 'temporary', 'unavailable', 'retry'
        ]
        
        if any(indicator in error_lower for indicator in transient_error_indicators):
            return "TRANSIENT_ERROR"
        
        return "UNKNOWN"
    
    def _print_execution_stats(self, results: List[TaskResult]):
        """実行統計を表示"""
        success_count = sum(1 for r in results if r.success)
        failure_count = len(results) - success_count
        total_retry_count = sum(r.retry_count for r in results)
        
        print("\n" + "=" * 50)
        print("実行統計:")
        print(f"  成功: {success_count}/{len(results)}")
        print(f"  失敗: {failure_count}/{len(results)}")
        print(f"  リトライ: {total_retry_count}件")
        
        # 最終結果（最後に成功したタスクの結果）
        last_success = None
        for result in reversed(results):
            if result.success:
                last_success = result.result
                break
        
        if last_success:
            print(f"  最終結果: {str(last_success)[:200]}{'...' if len(str(last_success)) > 200 else ''}")
    
    def get_execution_history(self, limit: int = 10) -> List[TaskResult]:
        """実行履歴を取得"""
        return self.execution_history[-limit:]
    
    def clear_history(self):
        """実行履歴をクリア"""
        self.execution_history.clear()