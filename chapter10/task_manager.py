#!/usr/bin/env python3
"""
シンプルなタスクマネージャー
タスクの登録、実行状態の管理、結果の追跡を行う
"""

import asyncio
import time
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json

class TaskStatus(Enum):
    """タスクの状態"""
    PENDING = "pending"      # 実行待ち
    RUNNING = "running"      # 実行中
    COMPLETED = "completed"  # 完了
    FAILED = "failed"        # 失敗
    SKIPPED = "skipped"      # スキップ

@dataclass
class Task:
    """タスク定義"""
    id: str
    name: str
    description: str
    function: Optional[Callable] = None
    args: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    dependencies: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "result": str(self.result) if self.result else None,
            "error": self.error,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "retry_count": self.retry_count,
            "execution_time": self.get_execution_time()
        }
    
    def get_execution_time(self) -> Optional[float]:
        """実行時間を取得（秒）"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

class SimpleTaskManager:
    """シンプルなタスクマネージャー"""
    
    def __init__(self, verbose: bool = True):
        self.tasks: Dict[str, Task] = {}
        self.task_queue: List[str] = []
        self.completed_tasks: List[str] = []
        self.failed_tasks: List[str] = []
        self.verbose = verbose
        self.execution_history: List[Dict[str, Any]] = []
        
    def add_task(self, task: Task) -> None:
        """タスクを追加"""
        self.tasks[task.id] = task
        self.task_queue.append(task.id)
        if self.verbose:
            print(f"[TASK] タスク追加: {task.name} (ID: {task.id})")
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """タスクを取得"""
        return self.tasks.get(task_id)
    
    def get_status_summary(self) -> Dict[str, int]:
        """ステータスサマリを取得"""
        summary = {status.value: 0 for status in TaskStatus}
        for task in self.tasks.values():
            summary[task.status.value] += 1
        return summary
    
    def can_execute(self, task: Task) -> bool:
        """タスクが実行可能かチェック"""
        # 依存タスクがすべて完了しているかチェック
        for dep_id in task.dependencies:
            dep_task = self.tasks.get(dep_id)
            if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                return False
        return True
    
    async def execute_task(self, task: Task) -> bool:
        """単一タスクを実行"""
        if not self.can_execute(task):
            task.status = TaskStatus.SKIPPED
            task.error = "依存タスクが未完了"
            if self.verbose:
                print(f"[SKIP] {task.name}: 依存タスクが未完了")
            return False
        
        task.status = TaskStatus.RUNNING
        task.start_time = datetime.now()
        
        if self.verbose:
            print(f"[実行] {task.name} を開始...")
        
        try:
            if task.function:
                # 非同期関数の場合
                if asyncio.iscoroutinefunction(task.function):
                    task.result = await task.function(**task.args)
                else:
                    # 同期関数を非同期で実行
                    loop = asyncio.get_event_loop()
                    # functools.partial を使って引数を固定
                    from functools import partial
                    func = partial(task.function, **task.args)
                    task.result = await loop.run_in_executor(None, func)
            else:
                # 関数が指定されていない場合はシミュレート
                await asyncio.sleep(0.5)  # 処理時間をシミュレート
                task.result = f"タスク {task.name} が完了しました"
            
            task.status = TaskStatus.COMPLETED
            task.end_time = datetime.now()
            self.completed_tasks.append(task.id)
            
            if self.verbose:
                exec_time = task.get_execution_time()
                print(f"[完了] {task.name} ({exec_time:.2f}秒)")
            
            return True
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.end_time = datetime.now()
            task.retry_count += 1
            
            if self.verbose:
                print(f"[エラー] {task.name}: {e}")
            
            # リトライ可能かチェック
            if task.retry_count < task.max_retries:
                if self.verbose:
                    print(f"[リトライ] {task.name} (試行 {task.retry_count}/{task.max_retries})")
                await asyncio.sleep(1 * task.retry_count)  # Exponential backoff
                return await self.execute_task(task)
            else:
                self.failed_tasks.append(task.id)
                return False
    
    async def execute_all(self, stop_on_error: bool = False) -> Dict[str, Any]:
        """すべてのタスクを実行"""
        start_time = time.time()
        
        if self.verbose:
            print(f"\n[開始] {len(self.task_queue)}個のタスクを実行")
            print("=" * 50)
        
        # タスクキューから順次実行
        while self.task_queue:
            task_id = self.task_queue.pop(0)
            task = self.tasks[task_id]
            
            success = await self.execute_task(task)
            
            # エラー時の処理
            if not success and stop_on_error:
                if self.verbose:
                    print(f"[中断] エラーにより実行を中断")
                break
            
            # 実行履歴に追加
            self.execution_history.append(task.to_dict())
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # 実行結果のサマリ
        result = {
            "total_tasks": len(self.tasks),
            "completed": len(self.completed_tasks),
            "failed": len(self.failed_tasks),
            "skipped": len([t for t in self.tasks.values() if t.status == TaskStatus.SKIPPED]),
            "execution_time": execution_time,
            "status_summary": self.get_status_summary(),
            "success_rate": len(self.completed_tasks) / len(self.tasks) * 100 if self.tasks else 0
        }
        
        if self.verbose:
            print("\n" + "=" * 50)
            print("[完了] 実行結果サマリ:")
            print(f"  - 総タスク数: {result['total_tasks']}")
            print(f"  - 完了: {result['completed']}")
            print(f"  - 失敗: {result['failed']}")
            print(f"  - スキップ: {result['skipped']}")
            print(f"  - 実行時間: {result['execution_time']:.2f}秒")
            print(f"  - 成功率: {result['success_rate']:.1f}%")
        
        return result
    
    def get_report(self) -> str:
        """実行レポートを生成"""
        report_lines = ["タスク実行レポート", "=" * 50]
        
        # ステータスサマリ
        summary = self.get_status_summary()
        report_lines.append("\n[ステータスサマリ]")
        for status, count in summary.items():
            report_lines.append(f"  {status}: {count}")
        
        # 各タスクの詳細
        report_lines.append("\n[タスク詳細]")
        for task in self.tasks.values():
            report_lines.append(f"\n  タスク: {task.name}")
            report_lines.append(f"    ID: {task.id}")
            report_lines.append(f"    状態: {task.status.value}")
            if task.get_execution_time():
                report_lines.append(f"    実行時間: {task.get_execution_time():.2f}秒")
            if task.error:
                report_lines.append(f"    エラー: {task.error}")
            if task.result:
                report_lines.append(f"    結果: {task.result}")
        
        return "\n".join(report_lines)
    
    def reset(self):
        """タスクマネージャーをリセット"""
        self.tasks.clear()
        self.task_queue.clear()
        self.completed_tasks.clear()
        self.failed_tasks.clear()
        self.execution_history.clear()
        if self.verbose:
            print("[リセット] タスクマネージャーをリセットしました")


# デモ用のサンプル関数
async def sample_async_task(name: str, delay: float = 1.0) -> str:
    """サンプル非同期タスク"""
    await asyncio.sleep(delay)
    return f"{name} completed after {delay}s"

def sample_sync_task(name: str, value: int = 0) -> int:
    """サンプル同期タスク"""
    time.sleep(0.5)
    return value * 2


# テスト実行
async def test_task_manager():
    """タスクマネージャーのテスト"""
    print("タスクマネージャーのテスト開始\n")
    
    manager = SimpleTaskManager(verbose=True)
    
    # タスクを追加
    task1 = Task(
        id="task1",
        name="データ取得",
        description="外部APIからデータを取得",
        function=sample_async_task,
        args={"name": "API Call", "delay": 1.0}
    )
    
    task2 = Task(
        id="task2",
        name="データ処理",
        description="取得したデータを処理",
        function=sample_sync_task,
        args={"name": "Processing", "value": 42},
        dependencies=["task1"]  # task1に依存
    )
    
    task3 = Task(
        id="task3",
        name="結果保存",
        description="処理結果を保存",
        function=sample_async_task,
        args={"name": "Save Results", "delay": 0.5},
        dependencies=["task2"]  # task2に依存
    )
    
    # エラーを発生させるタスク（テスト用）
    async def error_task():
        await asyncio.sleep(0.2)
        raise ValueError("テストエラー")
    
    task4 = Task(
        id="task4",
        name="エラータスク",
        description="エラーを発生させるテストタスク",
        function=error_task,
        max_retries=2  # 2回までリトライ
    )
    
    # タスクをマネージャーに追加
    manager.add_task(task1)
    manager.add_task(task2)
    manager.add_task(task3)
    manager.add_task(task4)
    
    # すべてのタスクを実行
    result = await manager.execute_all(stop_on_error=False)
    
    # レポートを表示
    print("\n" + manager.get_report())
    
    return result


if __name__ == "__main__":
    # テスト実行
    asyncio.run(test_task_manager())