"""
統合MCPエージェント
LLM、タスクプランナー、エラーハンドラー、MCPマネージャーを統合
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from llm_client import get_llm_client, BaseLLMClient
from task_planner import LLMTaskPlanner, ExecutionPlan, TaskStep
from error_handler import LLMErrorHandler, ErrorContext, ErrorResolution
from mcp_manager import MCPManager, MockMCPManager, ToolCall, ToolResult

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    """タスクステータス"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class TaskExecution:
    """タスク実行情報"""
    task: str
    plan: ExecutionPlan
    status: TaskStatus
    results: List[Any]
    errors: List[ErrorContext]
    start_time: datetime
    end_time: Optional[datetime] = None
    
    def duration_seconds(self) -> float:
        """実行時間を秒で返す"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

class MCPAgent:
    """
    統合MCPエージェント
    LLMを使用してタスクを理解し、MCPツールを活用して実行
    """
    
    def __init__(
        self,
        llm_client: Optional[BaseLLMClient] = None,
        use_mock: bool = False
    ):
        """
        初期化
        
        Args:
            llm_client: LLMクライアント（省略時は環境変数から設定）
            use_mock: モックMCPマネージャーを使用するか
        """
        self.llm = llm_client or get_llm_client()
        self.planner = LLMTaskPlanner(self.llm)
        self.error_handler = LLMErrorHandler(self.llm)
        self.mcp_manager = MockMCPManager() if use_mock else MCPManager()
        self.execution_history: List[TaskExecution] = []
        
    async def execute(
        self,
        task_description: str,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        タスクを実行
        
        Args:
            task_description: 実行するタスクの説明
            max_retries: 最大リトライ回数
            
        Returns:
            実行結果
        """
        logger.info(f"[AGENT] Starting task: {task_description}")
        
        # 実行情報を初期化
        execution = TaskExecution(
            task=task_description,
            plan=None,
            status=TaskStatus.RUNNING,
            results=[],
            errors=[],
            start_time=datetime.now()
        )
        
        try:
            # 利用可能なツールを取得
            available_tools = await self._get_available_tools()
            logger.info(f"[TOOLS] Available tools: {len(available_tools)}")
            
            # タスクプランを作成
            plan = await self.planner.create_plan(task_description, available_tools)
            execution.plan = plan
            
            logger.info(f"[PLAN] Created plan with {len(plan.steps)} steps")
            logger.info(f"[PLAN] Estimated time: {plan.estimated_time} seconds")
            
            # 各ステップを実行
            for step in plan.steps:
                result = await self._execute_step(step, execution, max_retries)
                execution.results.append(result)
                
                # エラーで中断すべきか判断
                if result.get("status") == "failed" and result.get("abort", False):
                    logger.error(f"[ABORT] Critical error in step {step.id}")
                    break
            
            # 結果をまとめる
            final_result = await self._summarize_results(execution)
            
            execution.status = TaskStatus.COMPLETED
            execution.end_time = datetime.now()
            
            logger.info(f"[OK] Task completed in {execution.duration_seconds():.2f} seconds")
            
            return {
                "success": True,
                "task": task_description,
                "result": final_result,
                "duration": execution.duration_seconds(),
                "steps_executed": len(execution.results)
            }
            
        except Exception as e:
            logger.error(f"[ERROR] Task failed: {e}")
            execution.status = TaskStatus.FAILED
            execution.end_time = datetime.now()
            
            return {
                "success": False,
                "task": task_description,
                "error": str(e),
                "duration": execution.duration_seconds(),
                "steps_executed": len(execution.results)
            }
        
        finally:
            self.execution_history.append(execution)
    
    async def _get_available_tools(self) -> List[Dict[str, Any]]:
        """利用可能なツールを取得"""
        # 既知のサーバーに接続を試みる
        for server_name in self.mcp_manager.servers.keys():
            await self.mcp_manager.connect_server(server_name)
        
        return self.mcp_manager.get_available_tools()
    
    def _resolve_step_references(
        self,
        params: Dict[str, Any],
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """パラメータ内のステップ参照を実際の値に解決"""
        resolved = {}
        
        for key, value in params.items():
            if isinstance(value, str) and value.startswith("step_") and value.endswith("_result"):
                # ステップIDを抽出 (例: "step_1_result" -> "step_1")
                step_id = value.replace("_result", "")
                
                # 該当するステップの結果を検索
                for result in results:
                    if result.get("step") == step_id and result.get("status") == "completed":
                        # 結果のデータを数値に変換して使用
                        try:
                            resolved[key] = float(result.get("data", 0))
                        except (ValueError, TypeError):
                            resolved[key] = result.get("data", 0)
                        break
                else:
                    # ステップが見つからない場合はデフォルト値
                    resolved[key] = 0
            else:
                resolved[key] = value
        
        return resolved
    
    async def _execute_step(
        self,
        step: TaskStep,
        execution: TaskExecution,
        max_retries: int
    ) -> Dict[str, Any]:
        """
        単一ステップを実行
        
        Args:
            step: 実行するステップ
            execution: 実行情報
            max_retries: 最大リトライ回数
            
        Returns:
            ステップ実行結果
        """
        logger.info(f"[STEP] Executing: {step.id} - {step.description}")
        
        # 依存関係をチェック
        if not self._check_dependencies(step, execution):
            logger.warning(f"[SKIP] Dependencies not met for {step.id}")
            return {
                "step": step.id,
                "status": "skipped",
                "reason": "Dependencies not met"
            }
        
        # ツールが必要な場合
        if step.tool:
            return await self._execute_tool_step(step, execution, max_retries)
        else:
            # LLMで直接実行
            return await self._execute_llm_step(step, execution)
    
    async def _execute_tool_step(
        self,
        step: TaskStep,
        execution: TaskExecution,
        max_retries: int
    ) -> Dict[str, Any]:
        """ツールを使用するステップを実行"""
        
        retry_count = 0
        last_error = None
        
        while retry_count <= max_retries:
            try:
                # ツールを検索
                tool_info = self.mcp_manager.find_tool(step.tool)
                if not tool_info:
                    # サーバーを探して接続を試みる
                    for server_name in self.mcp_manager.servers.keys():
                        await self.mcp_manager.connect_server(server_name)
                        tool_info = self.mcp_manager.find_tool(step.tool)
                        if tool_info:
                            break
                
                if not tool_info:
                    raise ValueError(f"Tool not found: {step.tool}")
                
                # パラメータ内のステップ参照を解決
                resolved_params = self._resolve_step_references(
                    step.params or {},
                    execution.results
                )
                
                # ツールを実行
                tool_call = ToolCall(
                    server=tool_info["server"],
                    tool=step.tool,
                    params=resolved_params
                )
                
                result = await self.mcp_manager.call_tool(tool_call)
                
                if result.success:
                    logger.info(f"[OK] Tool {step.tool} executed successfully")
                    return {
                        "step": step.id,
                        "status": "completed",
                        "data": result.data
                    }
                else:
                    raise Exception(result.error or "Tool execution failed")
                    
            except Exception as e:
                last_error = e
                logger.error(f"[ERROR] Step {step.id} failed: {e}")
                
                # エラーコンテキストを作成
                error_context = ErrorContext(
                    error=e,
                    task=execution.task,
                    step=step.id,
                    tool=step.tool,
                    params=step.params
                )
                execution.errors.append(error_context)
                
                # エラーハンドラーで解決策を取得
                resolution = await self.error_handler.handle_error(error_context)
                
                if resolution.strategy == "retry" and retry_count < max_retries:
                    retry_count += 1
                    logger.info(f"[RETRY] Attempt {retry_count} for step {step.id}")
                    
                    # リトライパラメータを適用
                    if resolution.retry_params:
                        step.params.update(resolution.retry_params)
                    
                    await asyncio.sleep(min(retry_count * 2, 10))  # 指数バックオフ
                    
                elif resolution.strategy == "skip":
                    logger.warning(f"[SKIP] Skipping step {step.id}")
                    return {
                        "step": step.id,
                        "status": "skipped",
                        "reason": str(last_error)
                    }
                    
                elif resolution.strategy == "fallback" and resolution.fallback_action:
                    logger.info(f"[FALLBACK] Using fallback for {step.id}")
                    # フォールバックアクションを実行
                    return await self._execute_fallback(step, resolution.fallback_action)
                    
                else:  # abort
                    logger.error(f"[ABORT] Cannot recover from error in {step.id}")
                    return {
                        "step": step.id,
                        "status": "failed",
                        "error": str(last_error),
                        "abort": True
                    }
        
        # リトライ回数を超えた
        return {
            "step": step.id,
            "status": "failed",
            "error": f"Max retries exceeded: {last_error}"
        }
    
    async def _execute_llm_step(
        self,
        step: TaskStep,
        execution: TaskExecution
    ) -> Dict[str, Any]:
        """LLMで直接実行するステップ"""
        
        try:
            prompt = f"""Execute the following step:
Step: {step.description}
Action: {step.action}
Parameters: {step.params}

Previous results:
{self._get_previous_results(execution, limit=3)}

Please perform this step and provide the result."""

            response = await self.llm.complete(prompt)
            
            return {
                "step": step.id,
                "status": "completed",
                "data": response.content
            }
            
        except Exception as e:
            logger.error(f"[ERROR] LLM step failed: {e}")
            return {
                "step": step.id,
                "status": "failed",
                "error": str(e)
            }
    
    async def _execute_fallback(
        self,
        step: TaskStep,
        fallback_action: str
    ) -> Dict[str, Any]:
        """フォールバックアクションを実行"""
        
        prompt = f"""Fallback action required:
Original step: {step.description}
Fallback: {fallback_action}

Please execute the fallback action and provide the result."""

        try:
            response = await self.llm.complete(prompt)
            return {
                "step": step.id,
                "status": "completed",
                "data": response.content,
                "fallback": True
            }
        except Exception as e:
            return {
                "step": step.id,
                "status": "failed",
                "error": f"Fallback failed: {e}"
            }
    
    def _check_dependencies(
        self,
        step: TaskStep,
        execution: TaskExecution
    ) -> bool:
        """依存関係をチェック"""
        if not step.dependencies:
            return True
        
        completed_steps = {
            r["step"] for r in execution.results
            if r.get("status") == "completed"
        }
        
        return all(dep in completed_steps for dep in step.dependencies)
    
    def _get_previous_results(
        self,
        execution: TaskExecution,
        limit: int = 3
    ) -> str:
        """前のステップの結果を取得"""
        if not execution.results:
            return "No previous results"
        
        recent = execution.results[-limit:]
        summary = []
        for result in recent:
            step_id = result.get("step", "unknown")
            status = result.get("status", "unknown")
            data = str(result.get("data", ""))[:100]
            summary.append(f"- {step_id}: {status} - {data}")
        
        return "\n".join(summary)
    
    async def _summarize_results(
        self,
        execution: TaskExecution
    ) -> str:
        """実行結果をまとめる"""
        
        # 成功したステップの結果を集める
        successful_results = [
            r for r in execution.results
            if r.get("status") == "completed"
        ]
        
        if not successful_results:
            return "No successful steps completed"
        
        # LLMで要約
        prompt = f"""Summarize the task execution results:

Task: {execution.task}

Results from {len(successful_results)} successful steps:
{self._format_results_for_summary(successful_results)}

Please provide a concise summary of what was accomplished."""

        try:
            response = await self.llm.complete(prompt)
            return response.content
        except Exception as e:
            logger.error(f"[ERROR] Failed to summarize: {e}")
            return f"Completed {len(successful_results)} steps successfully"
    
    def _format_results_for_summary(
        self,
        results: List[Dict[str, Any]]
    ) -> str:
        """要約用に結果をフォーマット"""
        formatted = []
        for r in results[:10]:  # 最大10件
            step = r.get("step", "unknown")
            data = str(r.get("data", ""))[:200]
            formatted.append(f"- {step}: {data}")
        return "\n".join(formatted)

# 使用例とテスト
async def test_agent():
    """エージェントのテスト"""
    
    # モックモードでエージェントを作成
    agent = MCPAgent(use_mock=True)
    
    # テストケース
    test_tasks = [
        "Calculate the sum of 15 and 25, then multiply the result by 2",
        "Search for information about MCP protocol and create a summary",
        "Query the database for user statistics and analyze the trends"
    ]
    
    for task in test_tasks:
        print("\n" + "="*80)
        print(f"Task: {task}")
        print("="*80)
        
        result = await agent.execute(task)
        
        print(f"\nSuccess: {result['success']}")
        if result['success']:
            print(f"Result: {result['result']}")
        else:
            print(f"Error: {result.get('error')}")
        print(f"Duration: {result['duration']:.2f} seconds")
        print(f"Steps executed: {result['steps_executed']}")

async def demo_real_agent():
    """実際のMCPサーバーを使用するデモ"""
    
    print("\n" + "="*80)
    print("Real MCP Agent Demo")
    print("="*80)
    
    # 実際のMCPマネージャーを使用
    agent = MCPAgent(use_mock=False)
    
    # 実際のタスク
    task = "データベースから売上データを取得して、月次レポートを作成してください"
    
    print(f"\nExecuting: {task}")
    result = await agent.execute(task)
    
    if result['success']:
        print(f"\n[SUCCESS] Task completed")
        print(f"Result: {result['result']}")
    else:
        print(f"\n[FAILED] Task failed")
        print(f"Error: {result.get('error')}")

if __name__ == "__main__":
    import asyncio
    
    # テストを実行
    asyncio.run(test_agent())
    
    # 実際のエージェントのデモ（MCPサーバーが設定されている場合）
    # asyncio.run(demo_real_agent())