"""
LLMベースのタスクプランナー
自然言語タスクを実行可能なステップに分解
"""

import json
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging
from llm_client import get_llm_client

logger = logging.getLogger(__name__)

@dataclass
class TaskStep:
    """タスクステップ"""
    id: str
    action: str
    description: str
    tool: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    dependencies: List[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "action": self.action,
            "description": self.description,
            "tool": self.tool,
            "params": self.params or {},
            "dependencies": self.dependencies or []
        }

@dataclass
class ExecutionPlan:
    """実行計画"""
    task_description: str
    steps: List[TaskStep]
    estimated_time: float
    required_tools: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task_description,
            "steps": [step.to_dict() for step in self.steps],
            "estimated_time_seconds": self.estimated_time,
            "required_tools": self.required_tools
        }

class LLMTaskPlanner:
    """
    LLMを使用してタスクを計画するプランナー
    """
    
    def __init__(self, llm_client=None):
        self.llm = llm_client or get_llm_client()
        
    async def create_plan(
        self, 
        task_description: str,
        available_tools: List[Dict[str, Any]] = None
    ) -> ExecutionPlan:
        """
        タスクの実行計画を作成
        
        Args:
            task_description: タスクの説明
            available_tools: 利用可能なツールのリスト
            
        Returns:
            実行計画
        """
        logger.info(f"[PLAN] Creating plan for: {task_description}")
        
        # プロンプトの構築
        prompt = self._build_planning_prompt(task_description, available_tools)
        
        # LLMに計画を生成させる
        response = await self.llm.complete(
            prompt,
            system=self._get_system_prompt(),
            temperature=0.3  # より決定的な出力のため低めに設定
        )
        
        # レスポンスをパース
        plan = self._parse_plan_response(response.content, task_description)
        
        logger.info(f"[OK] Plan created with {len(plan.steps)} steps")
        return plan
    
    def _get_system_prompt(self) -> str:
        """システムプロンプトを取得"""
        return """You are an expert task planner for an AI agent system.
Your role is to break down complex tasks into specific, executable steps.

Guidelines:
1. Each step should be atomic and clearly defined
2. Identify dependencies between steps
3. Select appropriate tools for each step
4. Estimate realistic execution times
5. Output valid JSON format

Output format:
{
    "steps": [
        {
            "id": "step_1",
            "action": "action_name",
            "description": "What this step does",
            "tool": "tool_name or null",
            "params": {"param1": "value1"},
            "dependencies": []
        }
    ],
    "estimated_time_seconds": 30,
    "required_tools": ["tool1", "tool2"]
}"""
    
    def _build_planning_prompt(
        self, 
        task: str, 
        tools: List[Dict[str, Any]] = None
    ) -> str:
        """プランニング用のプロンプトを構築"""
        
        prompt = f"Task to plan: {task}\n\n"
        
        if tools:
            prompt += "Available tools:\n"
            for tool in tools:
                prompt += f"- {tool['name']}: {tool.get('description', 'No description')}\n"
                if 'functions' in tool:
                    prompt += f"  Functions: {', '.join(tool['functions'])}\n"
            prompt += "\n"
        
        prompt += """Please create a detailed execution plan for this task.
Break it down into specific steps that can be executed by the available tools.
Consider dependencies between steps and estimate the total execution time.

Output the plan as valid JSON."""
        
        return prompt
    
    def _parse_plan_response(self, response: str, task: str) -> ExecutionPlan:
        """LLMのレスポンスをパースして実行計画を作成"""
        
        try:
            # JSONを抽出（マークダウンコードブロックに対応）
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 全体をJSONとして扱う
                json_str = response
            
            # JSONをパース
            data = json.loads(json_str)
            
            # ステップを作成
            steps = []
            for step_data in data.get("steps", []):
                step = TaskStep(
                    id=step_data.get("id", f"step_{len(steps) + 1}"),
                    action=step_data.get("action", "execute"),
                    description=step_data.get("description", ""),
                    tool=step_data.get("tool"),
                    params=step_data.get("params", {}),
                    dependencies=step_data.get("dependencies", [])
                )
                steps.append(step)
            
            # 実行計画を作成
            plan = ExecutionPlan(
                task_description=task,
                steps=steps,
                estimated_time=data.get("estimated_time_seconds", 30),
                required_tools=data.get("required_tools", [])
            )
            
            return plan
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"[WARN] Failed to parse JSON, using fallback: {e}")
            return self._create_fallback_plan(task)
    
    def _create_fallback_plan(self, task: str) -> ExecutionPlan:
        """パース失敗時のフォールバック計画"""
        
        logger.info("[FALLBACK] Creating simple fallback plan")
        
        # シンプルな3ステップ計画
        steps = [
            TaskStep(
                id="step_1",
                action="analyze",
                description="Analyze the task requirements",
                tool=None,
                params={},
                dependencies=[]
            ),
            TaskStep(
                id="step_2",
                action="execute",
                description="Execute the main task",
                tool=None,
                params={},
                dependencies=["step_1"]
            ),
            TaskStep(
                id="step_3",
                action="verify",
                description="Verify the results",
                tool=None,
                params={},
                dependencies=["step_2"]
            )
        ]
        
        return ExecutionPlan(
            task_description=task,
            steps=steps,
            estimated_time=60,
            required_tools=[]
        )
    
    async def refine_plan(
        self,
        plan: ExecutionPlan,
        feedback: str
    ) -> ExecutionPlan:
        """
        フィードバックに基づいて計画を改善
        
        Args:
            plan: 現在の計画
            feedback: 改善のためのフィードバック
            
        Returns:
            改善された計画
        """
        prompt = f"""Current plan:
{json.dumps(plan.to_dict(), indent=2)}

Feedback: {feedback}

Please refine the plan based on the feedback. 
Maintain the same JSON format but improve the steps, dependencies, or tool selections."""

        response = await self.llm.complete(
            prompt,
            system=self._get_system_prompt()
        )
        
        return self._parse_plan_response(response.content, plan.task_description)

# 使用例とテスト
async def test_planner():
    """タスクプランナーのテスト"""
    
    planner = LLMTaskPlanner()
    
    # 利用可能なツール
    available_tools = [
        {
            "name": "database",
            "description": "Database operations",
            "functions": ["query", "insert", "update", "delete"]
        },
        {
            "name": "calculator",
            "description": "Mathematical calculations",
            "functions": ["add", "subtract", "multiply", "divide", "statistics"]
        },
        {
            "name": "web_search",
            "description": "Web search and information retrieval",
            "functions": ["search", "fetch_page", "extract_content"]
        },
        {
            "name": "file_system",
            "description": "File system operations",
            "functions": ["read", "write", "list", "delete"]
        }
    ]
    
    # テストケース
    test_tasks = [
        "売上データを分析して月次レポートを作成",
        "競合3社の最新ニュースを調査して比較表を作成",
        "プロジェクトのソースコードを解析してドキュメントを生成"
    ]
    
    for task in test_tasks:
        print(f"\n{'='*60}")
        print(f"Task: {task}")
        print('='*60)
        
        # 計画を作成
        plan = await planner.create_plan(task, available_tools)
        
        # 結果を表示
        print(f"\nEstimated time: {plan.estimated_time} seconds")
        print(f"Required tools: {', '.join(plan.required_tools)}")
        print(f"\nSteps:")
        for step in plan.steps:
            deps = f" (depends on: {', '.join(step.dependencies)})" if step.dependencies else ""
            tool = f" [Tool: {step.tool}]" if step.tool else ""
            print(f"  {step.id}: {step.description}{tool}{deps}")
        
        # 計画の改善例
        if "レポート" in task:
            print("\n[Refining plan with feedback...]")
            refined = await planner.refine_plan(
                plan,
                "Add a step to visualize data with charts before creating the report"
            )
            print(f"Refined plan now has {len(refined.steps)} steps")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_planner())