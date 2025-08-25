#!/usr/bin/env python3
"""
エラー対応実行エンジン V2（依存注入修正版）
エラー発生時に自動的にリカバリーを試みる

V2の主要変更点：
- _resolve_dependenciesメソッドを追加
- execute_tasks_with_recoveryで依存関係を正しく解決
- タスク間の結果の引き渡しを修正
"""

import asyncio
import json
import os
import sys
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from dotenv import load_dotenv
import re

if TYPE_CHECKING:
    from universal_task_planner import UniversalTaskPlanner

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

# .envファイルから環境変数を読み込む
load_dotenv()

from mcp_connection_manager import MCPConnectionManager
from universal_task_planner import UniversalTask
from intelligent_error_handler import IntelligentErrorHandler

@dataclass
class ExecutionAttempt:
    """実行試行の記録"""
    attempt_number: int
    task: UniversalTask
    params_used: Dict[str, Any]
    result: Optional[Any] = None
    error: Optional[str] = None
    fix_applied: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.now)

class ErrorAwareExecutor:
    """エラー対応機能を持つタスク実行エンジン（V2版）"""
    
    def __init__(
        self,
        connection_manager: Optional[MCPConnectionManager] = None,
        task_planner: Optional["UniversalTaskPlanner"] = None,
        use_ai: bool = True,
        max_retries: int = 3,
        verbose: bool = True
    ):
        self.connection_manager = connection_manager or MCPConnectionManager()
        self.task_planner = task_planner
        self.use_ai = use_ai
        self.max_retries = max_retries
        self.verbose = verbose
        self.execution_history: List[ExecutionAttempt] = []
        
        # インテリジェントエラーハンドラーの初期化
        if use_ai:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self.error_handler = IntelligentErrorHandler(api_key=api_key, verbose=verbose)
            else:
                print("[警告] OpenAI APIキーが設定されていません。基本エラーハンドリングを使用します。")
                self.use_ai = False
                from error_handler import BasicErrorHandler
                self.error_handler = BasicErrorHandler(verbose=verbose)
        else:
            from error_handler import BasicErrorHandler
            self.error_handler = BasicErrorHandler(verbose=verbose)
    
    async def connect_all_servers(self):
        """接続マネージャーを初期化"""
        if not self.connection_manager._initialized:
            await self.connection_manager.initialize()
    
    def _resolve_dependencies(self, task: UniversalTask, completed_tasks: List[UniversalTask]):
        """タスクの依存関係を解決し、パラメータに実際の値を注入"""
        
        # パラメータ内の{task_N}プレースホルダーを実際の結果に置換
        for param_key, param_value in task.params.items():
            if isinstance(param_value, str) and "{task_" in param_value:
                # {task_1}, {task_2} などのプレースホルダーを探す
                placeholders = re.findall(r'\{task_(\d+)\}', param_value)
                
                for placeholder_num in placeholders:
                    # task_1, task_2 などの形式でタスクIDを構成
                    dep_task_id = f"task_{placeholder_num}"
                    placeholder_full = f"{{task_{placeholder_num}}}"
                    
                    # 依存タスクを完了済みタスクから探す
                    dep_task = None
                    for completed_task in completed_tasks:
                        if completed_task.id == dep_task_id and completed_task.result is not None:
                            dep_task = completed_task
                            break
                    
                    if dep_task and dep_task.result is not None:
                        # プレースホルダーを実際の値に置換
                        if param_value == placeholder_full:
                            # パラメータ全体がプレースホルダーの場合、結果をそのまま設定
                            task.params[param_key] = dep_task.result
                        else:
                            # プレースホルダーが文字列の一部の場合、文字列置換
                            task.params[param_key] = param_value.replace(placeholder_full, str(dep_task.result))
                        
                        if self.verbose:
                            print(f"  [依存解決] {param_key}: {placeholder_full} → {dep_task.result}")
    
    async def execute_task(self, task: UniversalTask) -> Any:
        """単一タスクを実行"""
        if self.verbose:
            print(f"\n[実行] {task.name}")
            print(f"  ツール: {task.tool} (サーバー: {task.server})")
            print(f"  パラメータ: {task.params}")
        
        try:
            result = await self.connection_manager.execute_tool(task.tool, task.params)
            
            # 結果を整形して数値として保存
            if hasattr(result, 'content'):
                if hasattr(result.content[0], 'text'):
                    task.result = float(result.content[0].text) if result.content[0].text.replace('.', '').replace('-', '').isdigit() else result.content[0].text
                else:
                    task.result = result
            elif hasattr(result, 'data'):
                task.result = result.data
            else:
                task.result = result
            
            if self.verbose:
                print(f"  結果: {task.result}")
            
            return task.result
            
        except Exception as e:
            task.error = str(e)
            if self.verbose:
                print(f"  エラー: {e}")
            raise
    
    async def cleanup(self):
        """接続をクリーンアップ"""
        await self.connection_manager.cleanup()
    
    async def execute_task_with_recovery(self, task: UniversalTask) -> Any:
        """エラーリカバリー機能付きでタスクを実行"""
        
        if self.verbose:
            print(f"\n[実行] {task.name} (リカバリー機能付き)")
        
        # 実行試行ループ
        for attempt in range(1, self.max_retries + 1):
            # 実行記録を作成
            execution_attempt = ExecutionAttempt(
                attempt_number=attempt,
                task=task,
                params_used=task.params.copy()
            )
            
            if attempt > 1 and self.verbose:
                print(f"\n[リトライ {attempt}/{self.max_retries}]")
            
            # リトライ前にエラーをクリア
            task.error = None
            
            try:
                # タスク実行
                result = await self.execute_task(task)
                
                # 成功した場合
                if task.error is None:
                    execution_attempt.result = result
                    self.execution_history.append(execution_attempt)
                    
                    # AIハンドラーに成功を学習させる
                    if self.use_ai and attempt > 1:
                        await self.error_handler.learn_from_success(
                            Exception("Previous error resolved"),
                            execution_attempt.fix_applied or {},
                            True
                        )
                    
                    # タスクプランナーに成功した実行を学習させる
                    if self.task_planner and hasattr(task, 'original_query'):
                        self.task_planner.learn_from_execution(
                            task.tool, 
                            task.original_query, 
                            task.params
                        )
                    
                    return result
                
                # エラーがある場合は例外として扱う
                raise Exception(task.error)
                
            except Exception as e:
                execution_attempt.error = str(e)
                self.execution_history.append(execution_attempt)
                
                if self.verbose:
                    print(f"  [エラー] {str(e)[:100]}")
                
                # 最後の試行の場合はエラー処理をスキップ
                if attempt >= self.max_retries:
                    if self.verbose:
                        print(f"  [失敗] 最大リトライ回数に到達")
                    task.error = f"最大リトライ後も失敗: {e}"
                    return None
                
                # エラー分析と修正案の取得
                if self.use_ai:
                    fix_result = await self._get_ai_fix(e, task)
                    if fix_result and fix_result.get("success"):
                        await self._apply_fix(task, fix_result)
                        execution_attempt.fix_applied = fix_result
                    else:
                        # AI修正が失敗した場合は基本的なリトライ
                        await asyncio.sleep(2 ** (attempt - 1))  # 指数バックオフ
                else:
                    # 基本的なエラーハンドリング
                    await self._basic_error_recovery(e, task, attempt)
        
        return None
    
    async def _get_ai_fix(self, error: Exception, task: UniversalTask) -> Optional[Dict[str, Any]]:
        """AIを使ってエラーの修正案を取得"""
        
        # タスクコンテキストを構築
        context = {
            "tool": task.tool,
            "params": task.params,
            "server": task.server,
            "available_tools": list(self.connection_manager.tools_map.keys())
        }
        
        # AI分析を実行
        fix_result = await self.error_handler.suggest_fix(error, context)
        
        return fix_result
    
    async def _apply_fix(self, task: UniversalTask, fix_result: Dict[str, Any]):
        """修正案をタスクに適用"""
        
        strategy = fix_result.get("strategy", {})
        action = strategy.get("action", "retry")
        
        if action == "modify_and_retry":
            # パラメータを修正
            modifications = strategy.get("modifications", {})
            if modifications:
                if self.verbose:
                    print(f"  [修正] パラメータを更新: {modifications}")
                task.params.update(modifications)
        
        elif action == "use_alternative":
            # 代替ツールを使用
            alternative = strategy.get("alternative")
            if alternative and alternative in self.connection_manager.tools_map:
                if self.verbose:
                    print(f"  [代替] ツールを変更: {task.tool} → {alternative}")
                task.tool = alternative
                task.server = self.connection_manager.tools_map[alternative]
                
                # パラメータのマッピングが必要な場合
                # 例: calculate_tax(amount, rate) → add(a, b) or multiply(a, b)
                if alternative in ["add", "subtract", "multiply", "divide", "power"]:
                    # 既存のパラメータから新しいパラメータへマッピング
                    old_params = task.params.copy()
                    task.params.clear()
                    
                    # 最初の2つのパラメータをa, bにマッピング
                    param_values = list(old_params.values())
                    if len(param_values) >= 1:
                        task.params["a"] = param_values[0]
                    if len(param_values) >= 2:
                        task.params["b"] = param_values[1]
                    
                    if self.verbose:
                        print(f"  [マッピング] パラメータを変換: {old_params} → {task.params}")
        
        elif action == "skip":
            # このタスクをスキップ
            if self.verbose:
                print(f"  [スキップ] このタスクをスキップします")
            task.error = "AIの判断によりスキップ"
    
    async def _basic_error_recovery(self, error: Exception, task: UniversalTask, attempt: int):
        """基本的なエラーリカバリー"""
        
        error_str = str(error).lower()
        
        # 接続エラーの場合
        if "connection" in error_str or "refused" in error_str:
            wait_time = 2 ** attempt
            if self.verbose:
                print(f"  [待機] 接続エラーのため{wait_time}秒待機")
            await asyncio.sleep(wait_time)
        
        # パラメータエラーの場合
        elif "parameter" in error_str or "invalid" in error_str or "validation" in error_str:
            if self.verbose:
                print(f"  [確認] パラメータを確認してください: {task.params}")
            # パラメータの型変換を試みる
            for key, value in task.params.items():
                if isinstance(value, str) and value.replace(".", "").replace("-", "").isdigit():
                    try:
                        task.params[key] = float(value)
                        if self.verbose:
                            print(f"  [修正] {key}を数値に変換: {value} → {task.params[key]}")
                    except:
                        pass
        
        # その他のエラー
        else:
            wait_time = 1
            if self.verbose:
                print(f"  [待機] {wait_time}秒待機後にリトライ")
            await asyncio.sleep(wait_time)
    
    async def execute_tasks_with_recovery(self, tasks: List[UniversalTask]) -> Dict[str, Any]:
        """タスクリストをリカバリー機能付きで実行（V2: 依存関係解決対応）"""
        
        if self.verbose:
            print(f"\n[タスク実行] {len(tasks)}個のタスクを実行（リカバリー機能付き・依存関係解決対応）")
            print("=" * 60)
        
        success_count = 0
        fail_count = 0
        recovered_count = 0
        completed_tasks = []  # 完了したタスクのリスト
        
        for i, task in enumerate(tasks, 1):
            if self.verbose:
                print(f"\n[{i}/{len(tasks)}] タスク: {task.name}")
            
            # **重要**: タスク実行前に依存関係を解決
            self._resolve_dependencies(task, completed_tasks)
            
            # 実行履歴の初期サイズ
            initial_history_size = len(self.execution_history)
            
            # リカバリー機能付きで実行
            result = await self.execute_task_with_recovery(task)
            
            # 完了したタスクリストに追加（成功・失敗問わず）
            completed_tasks.append(task)
            
            # リカバリーが発生したかチェック
            attempts_made = len(self.execution_history) - initial_history_size
            if attempts_made > 1 and task.error is None:
                recovered_count += 1
                if self.verbose:
                    print(f"  [回復] {attempts_made}回目の試行で成功")
            
            if task.error:
                fail_count += 1
            else:
                success_count += 1
        
        # 最終結果を取得
        final_result = None
        for task in reversed(tasks):
            if task.result is not None:
                final_result = task.result
                break
        
        # 実行統計
        stats = {
            "total": len(tasks),
            "success": success_count,
            "failed": fail_count,
            "recovered": recovered_count,
            "recovery_rate": (recovered_count / len(tasks) * 100) if len(tasks) > 0 else 0
        }
        
        if self.verbose:
            print("\n" + "=" * 60)
            print("実行統計:")
            print(f"  成功: {success_count}/{len(tasks)}")
            print(f"  失敗: {fail_count}/{len(tasks)}")
            print(f"  リカバリー: {recovered_count}件")
            print(f"  リカバリー率: {stats['recovery_rate']:.1f}%")
            print(f"  最終結果: {final_result}")
        
        return {
            "tasks": [task.to_dict() for task in tasks],
            "final_result": final_result,
            "success": fail_count == 0,
            "stats": stats,
            "execution_history": [
                {
                    "attempt": attempt.attempt_number,
                    "task": attempt.task.name,
                    "success": attempt.error is None,
                    "error": attempt.error,
                    "fix_applied": attempt.fix_applied
                }
                for attempt in self.execution_history[-10:]  # 最新10件
            ]
        }
    
    def get_execution_report(self) -> str:
        """実行レポートを生成"""
        
        report_lines = [
            "エラー対応実行レポート V2",
            "=" * 60
        ]
        
        # 実行統計
        total_attempts = len(self.execution_history)
        successful_attempts = sum(1 for a in self.execution_history if a.error is None)
        failed_attempts = total_attempts - successful_attempts
        
        report_lines.extend([
            "\n[実行統計]",
            f"  総実行回数: {total_attempts}",
            f"  成功: {successful_attempts}",
            f"  失敗: {failed_attempts}"
        ])
        
        # リカバリー統計
        recovery_attempts = [a for a in self.execution_history if a.attempt_number > 1 and a.error is None]
        if recovery_attempts:
            report_lines.extend([
                "\n[リカバリー統計]",
                f"  リカバリー成功: {len(recovery_attempts)}件",
                f"  平均試行回数: {sum(a.attempt_number for a in recovery_attempts) / len(recovery_attempts):.1f}"
            ])
        
        # AI修正統計
        if self.use_ai:
            ai_fixes = [a for a in self.execution_history if a.fix_applied]
            if ai_fixes:
                report_lines.extend([
                    "\n[AI支援統計]",
                    f"  AI修正適用: {len(ai_fixes)}件"
                ])
        
        # エラーハンドラーのレポート
        if hasattr(self.error_handler, 'get_report'):
            report_lines.extend([
                "\n" + self.error_handler.get_report()
            ])
        
        return "\n".join(report_lines)


# テスト関数
async def test_error_aware_executor_v2():
    """エラー対応実行エンジン V2のテスト"""
    
    print("エラー対応実行エンジン V2のテスト（依存関係解決）")
    print("=" * 60)
    
    from universal_task_planner import UniversalTaskPlanner
    
    # プランナーと実行エンジンの初期化
    planner = UniversalTaskPlanner()
    executor = ErrorAwareExecutor(use_ai=True, verbose=True)
    
    await planner.initialize()
    await executor.connect_all_servers()
    
    # テストケース: 依存関係のあるタスク
    print("\n[テスト] 依存関係解決テスト: 100+200-5*10")
    print("-" * 50)
    
    test_query = "100+200-5*10"
    tasks = await planner.plan_task(test_query)
    
    if tasks:
        print(f"\n分解されたタスク: {len(tasks)}個")
        for task in tasks:
            print(f"  [{task.id}] {task.name} - {task.tool}({task.params})")
        
        result = await executor.execute_tasks_with_recovery(tasks)
        print(f"\n最終結果: {result['final_result']} (期待値: 250)")
    else:
        print("タスクが分解されませんでした")
    
    # 実行レポート
    print("\n" + "=" * 60)
    print(executor.get_execution_report())
    
    # クリーンアップ
    await executor.cleanup()


if __name__ == "__main__":
    asyncio.run(test_error_aware_executor_v2())