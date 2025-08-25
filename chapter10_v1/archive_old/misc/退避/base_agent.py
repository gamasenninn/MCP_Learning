"""
MCPベースエージェント
拡張可能な基本エージェント機能を提供
"""

import asyncio
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Task:
    """タスクを表現するデータクラス"""
    id: str
    description: str
    steps: List[str]
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime = None
    completed_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

class MCPAgent:
    """
    MCPベースの拡張可能エージェント
    """
    
    def __init__(self, name: str = "MCPAgent"):
        self.name = name
        self.mcp_servers = {}
        self.task_history = []
        self.current_task = None
        
        # コンポーネントの初期化は後で行う
        self.task_planner = None
        self.error_handler = None
        self.mcp_manager = None
        
        logger.info(f"[START] {self.name} initialized")
    
    def add_mcp_server(self, name: str, config: Dict[str, Any]):
        """
        MCPサーバーを動的に追加
        
        Args:
            name: サーバー名
            config: サーバー設定
        """
        try:
            self.mcp_servers[name] = config
            logger.info(f"[OK] Added MCP server: {name}")
            return True
        except Exception as e:
            logger.error(f"[ERROR] Failed to add server {name}: {e}")
            return False
    
    async def execute_task(self, task_description: str) -> Dict[str, Any]:
        """
        タスクを実行
        
        Args:
            task_description: 自然言語でのタスク記述
            
        Returns:
            実行結果
        """
        # タスクの作成
        task = Task(
            id=f"task_{len(self.task_history) + 1}",
            description=task_description,
            steps=[]
        )
        
        self.current_task = task
        self.task_history.append(task)
        
        logger.info(f"[START] Task: {task_description}")
        
        try:
            # ステップ1: タスクを計画
            task.steps = await self._plan_task(task_description)
            task.status = "running"
            
            # ステップ2: 各ステップを実行
            results = []
            for i, step in enumerate(task.steps, 1):
                logger.info(f"[EXEC] Step {i}/{len(task.steps)}: {step}")
                result = await self._execute_step(step)
                results.append(result)
            
            # ステップ3: 結果をまとめる
            task.status = "completed"
            task.completed_at = datetime.now()
            task.result = {
                "steps": task.steps,
                "results": results,
                "duration": (task.completed_at - task.created_at).total_seconds()
            }
            
            logger.info(f"[OK] Task completed in {task.result['duration']:.2f}s")
            return task.result
            
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            logger.error(f"[ERROR] Task failed: {e}")
            
            # エラーハンドリング（後で実装）
            return {
                "error": str(e),
                "task_id": task.id
            }
    
    async def _plan_task(self, description: str) -> List[str]:
        """
        タスクを実行可能なステップに分解
        （この段階ではシンプルな実装）
        """
        # TODO: LLMを使った高度なプランニング
        # 現時点では固定的なルールベース
        
        steps = []
        
        # キーワードベースの簡単なプランニング
        if "データ" in description and "分析" in description:
            steps = [
                "データソースに接続",
                "データを取得",
                "データを分析",
                "結果を整形",
                "レポートを生成"
            ]
        elif "ファイル" in description:
            steps = [
                "ファイルパスを確認",
                "ファイルを読み込み",
                "処理を実行",
                "結果を保存"
            ]
        else:
            # デフォルト
            steps = [
                "タスクを解析",
                "必要なツールを特定",
                "処理を実行",
                "結果を返す"
            ]
        
        return steps
    
    async def _execute_step(self, step: str) -> Dict[str, Any]:
        """
        個別のステップを実行
        （この段階ではモック実装）
        """
        # TODO: 実際のMCPサーバー呼び出し
        await asyncio.sleep(0.5)  # 処理のシミュレーション
        
        return {
            "step": step,
            "status": "completed",
            "timestamp": datetime.now().isoformat()
        }
    
    def get_status(self) -> Dict[str, Any]:
        """
        エージェントの現在の状態を取得
        """
        return {
            "name": self.name,
            "mcp_servers": list(self.mcp_servers.keys()),
            "current_task": self.current_task.description if self.current_task else None,
            "task_history_count": len(self.task_history),
            "status": "ready"
        }

# 使用例
async def main():
    # エージェントの作成
    agent = MCPAgent("MyFirstAgent")
    
    # MCPサーバーの追加
    agent.add_mcp_server("calculator", {"type": "calculator"})
    agent.add_mcp_server("database", {"type": "sqlite", "path": "data.db"})
    
    # タスクの実行
    result = await agent.execute_task("売上データを分析してレポートを作成")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # ステータス確認
    status = agent.get_status()
    print(f"\nAgent Status: {json.dumps(status, indent=2)}")

if __name__ == "__main__":
    asyncio.run(main())