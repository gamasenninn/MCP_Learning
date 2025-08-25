#!/usr/bin/env python3
"""
シンプルなタスクプランニング機能のテスト
統合前の基本機能を確認
"""

import asyncio
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

@dataclass
class SimpleTask:
    """シンプルなタスク定義"""
    id: str
    name: str
    tool: str
    params: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    result: Any = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "tool": self.tool,
            "params": self.params,
            "dependencies": self.dependencies,
            "result": str(self.result) if self.result else None,
            "error": self.error
        }

class SimpleTaskPlanner:
    """シンプルなタスクプランナー"""
    
    def __init__(self):
        self.llm = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
    async def plan_calculation(self, expression: str) -> List[SimpleTask]:
        """計算式をタスクに分解"""
        
        prompt = f"""
あなたは計算タスクを分解する専門家です。
以下の計算式を、基本的な計算ツールを使った実行可能なタスクに分解してください。

計算式: {expression}

利用可能なツール:
- add: 2つの数値を加算 (パラメータ: a, b)
- subtract: 2つの数値を減算 (パラメータ: a, b)
- multiply: 2つの数値を乗算 (パラメータ: a, b)
- divide: 2つの数値を除算 (パラメータ: a, b)

重要な注意:
1. 各タスクは2つの値だけを処理できます
2. 複数の演算がある場合は、優先順位に従って分解してください（乗除が先、加減が後）
3. 前のタスクの結果を使う場合は、パラメータに "{{task_X}}" と記述してください

例1: "10 + 20"
→ タスク1つ: add(a=10, b=20)

例2: "10 + 20 * 3"
→ タスク1: multiply(a=20, b=3) # 優先順位により先に実行
→ タスク2: add(a=10, b={{task_1}}) # task_1の結果を使用

出力形式（JSON）:
{{
  "tasks": [
    {{
      "id": "task_1",
      "name": "タスクの説明",
      "tool": "ツール名",
      "params": {{"a": 値またはタスク参照, "b": 値またはタスク参照}},
      "dependencies": []  # 依存するタスクIDのリスト
    }}
  ]
}}
"""
        
        try:
            response = await self.llm.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # SimpleTaskオブジェクトに変換
            tasks = []
            for task_data in result.get("tasks", []):
                task = SimpleTask(
                    id=task_data["id"],
                    name=task_data["name"],
                    tool=task_data["tool"],
                    params=task_data["params"],
                    dependencies=task_data.get("dependencies", [])
                )
                tasks.append(task)
            
            return tasks
            
        except Exception as e:
            print(f"タスク分解エラー: {e}")
            return []

class SimpleTaskExecutor:
    """シンプルなタスク実行エンジン"""
    
    def __init__(self):
        self.results = {}  # タスクIDと結果のマッピング
        
    async def execute_tasks(self, tasks: List[SimpleTask]) -> Dict[str, Any]:
        """タスクを実行（シミュレーション）"""
        
        for task in tasks:
            print(f"\n実行: {task.name}")
            print(f"  ツール: {task.tool}")
            print(f"  パラメータ: {task.params}")
            
            # パラメータの解決
            resolved_params = {}
            for key, value in task.params.items():
                if isinstance(value, str) and value.startswith("{task_"):
                    # タスク参照を解決
                    task_id = value.strip("{}") 
                    if task_id in self.results:
                        resolved_params[key] = self.results[task_id]
                        print(f"    {key} = {self.results[task_id]} (from {task_id})")
                    else:
                        task.error = f"依存タスク {task_id} が見つかりません"
                        print(f"  エラー: {task.error}")
                        continue
                else:
                    resolved_params[key] = value
            
            if task.error:
                continue
                
            # 計算実行（シミュレーション）
            try:
                if task.tool == "add":
                    result = resolved_params["a"] + resolved_params["b"]
                elif task.tool == "subtract":
                    result = resolved_params["a"] - resolved_params["b"]
                elif task.tool == "multiply":
                    result = resolved_params["a"] * resolved_params["b"]
                elif task.tool == "divide":
                    result = resolved_params["a"] / resolved_params["b"]
                else:
                    raise ValueError(f"不明なツール: {task.tool}")
                
                task.result = result
                self.results[task.id] = result
                print(f"  結果: {result}")
                
            except Exception as e:
                task.error = str(e)
                print(f"  エラー: {e}")
        
        return {
            "tasks": [task.to_dict() for task in tasks],
            "final_result": list(self.results.values())[-1] if self.results else None
        }

async def test_task_planning():
    """タスクプランニングのテスト"""
    print("タスクプランニング機能テスト")
    print("=" * 60)
    
    planner = SimpleTaskPlanner()
    executor = SimpleTaskExecutor()
    
    # テストケース
    test_cases = [
        "100 + 200",
        "100 + 200 + 300",
        "100 + 200 * 3",
        "100 + 200 + 4 * 50",
        "(100 + 200) / 2"
    ]
    
    for expression in test_cases:
        print(f"\n{'='*60}")
        print(f"計算式: {expression}")
        print("-" * 40)
        
        # タスクに分解
        tasks = await planner.plan_calculation(expression)
        
        if not tasks:
            print("タスク分解に失敗しました")
            continue
        
        print(f"\n分解されたタスク数: {len(tasks)}")
        for task in tasks:
            print(f"  - {task.id}: {task.name}")
            print(f"    ツール: {task.tool}, パラメータ: {task.params}")
            if task.dependencies:
                print(f"    依存: {task.dependencies}")
        
        # タスクを実行
        print("\n実行:")
        result = await executor.execute_tasks(tasks)
        
        print(f"\n最終結果: {result['final_result']}")
        
        # Pythonのevalで答え合わせ（安全な式のみ）
        try:
            correct_answer = eval(expression)
            print(f"正解: {correct_answer}")
            if result['final_result'] and abs(result['final_result'] - correct_answer) < 0.01:
                print("✓ 正解！")
            else:
                print("✗ 不正解")
        except:
            print("（答え合わせスキップ）")

async def test_manual_tasks():
    """手動で作成したタスクのテスト"""
    print("\n" + "=" * 60)
    print("手動タスクテスト: 100 + 200 + 4 * 50")
    print("-" * 40)
    
    # 手動でタスクを作成
    tasks = [
        SimpleTask(
            id="task_1",
            name="4 * 50を計算",
            tool="multiply",
            params={"a": 4, "b": 50},
            dependencies=[]
        ),
        SimpleTask(
            id="task_2",
            name="100 + 200を計算",
            tool="add",
            params={"a": 100, "b": 200},
            dependencies=[]
        ),
        SimpleTask(
            id="task_3",
            name="前の結果を加算",
            tool="add",
            params={"a": "{task_2}", "b": "{task_1}"},
            dependencies=["task_1", "task_2"]
        )
    ]
    
    executor = SimpleTaskExecutor()
    result = await executor.execute_tasks(tasks)
    
    print(f"\n最終結果: {result['final_result']}")
    print(f"正解: {100 + 200 + 4 * 50} = 500")

if __name__ == "__main__":
    asyncio.run(test_task_planning())
    asyncio.run(test_manual_tasks())