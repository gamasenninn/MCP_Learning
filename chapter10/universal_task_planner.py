#!/usr/bin/env python3
"""
汎用タスクプランナー
任意のMCPツールを使用してタスクを分解・計画
"""

import asyncio
import json
import os
import sys
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

# 第9章のコンポーネントをインポート
# MCPConnectionManagerを使用
from mcp_connection_manager import MCPConnectionManager

load_dotenv()

@dataclass
class UniversalTask:
    """汎用タスク定義"""
    id: str
    name: str
    tool: str
    server: Optional[str] = None  # ツールが属するサーバー
    params: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    result: Any = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "tool": self.tool,
            "server": self.server,
            "params": self.params,
            "dependencies": self.dependencies,
            "result": str(self.result) if self.result else None,
            "error": self.error
        }

class UniversalTaskPlanner:
    """汎用タスクプランナー"""
    
    def __init__(self, connection_manager: Optional[MCPConnectionManager] = None):
        """
        Args:
            connection_manager: MCP接続マネージャー（提供されない場合は新規作成）
        """
        self.connection_manager = connection_manager or MCPConnectionManager()
        self.llm = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.tools_info = {}
        
    async def initialize(self):
        """接続マネージャーを初期化してツール情報を取得"""
        # 接続マネージャーが初期化されていなければ初期化
        if not self.connection_manager._initialized:
            await self.connection_manager.initialize()
        
        # 接続マネージャーからツール情報を取得
        self.tools_info = self.connection_manager.tools_info
    
    async def plan_task(self, query: str) -> List[UniversalTask]:
        """クエリをタスクに分解"""
        
        # ツールのパラメータ情報を詳細に記述
        tools_detail = []
        for tool_name, tool_info in self.tools_info.items():
            schema = tool_info["schema"]
            params = schema.get("inputSchema", {}).get("properties", {})
            param_desc = []
            for param_name, param_info in params.items():
                param_type = param_info.get("type", "any")
                param_desc.append(f"{param_name}: {param_type}")
            
            tools_detail.append(
                f"- {tool_name}: {schema.get('description', 'No description')}\n"
                f"  パラメータ: {', '.join(param_desc) if param_desc else 'なし'}"
            )
        
        tools_detail_str = "\n".join(tools_detail)
        
        prompt = f"""
あなたはタスクプランナーです。ユーザーのリクエストを分析し、利用可能なツールを使って実行可能なタスクに分解してください。

## ユーザーのリクエスト
{query}

## 利用可能なツール
{tools_detail_str}

## タスク分解のルール
1. まず、ツールを使う必要があるか判断してください
2. 挨拶、感謝、褒め言葉などはツール不要です
3. ツールが必要な場合のみ、タスクに分解してください
4. 各タスクは1つのツールを使用します
5. 複数のステップが必要な場合は、順序と依存関係を明確にしてください
6. 前のタスクの結果を使う場合は、パラメータに "{{task_X}}" と記述してください
7. **重要**: パラメータは必ず具体的な値を入れてください。空の辞書 {{}} は使用しないでください

## 例
- "100 + 200を計算" → add ツールで params: {{"a": 100, "b": 200}}
- "2の8乗" → power ツールで params: {{"a": 2, "b": 8}}  （aのb乗）
- "結果を2倍" → multiply ツールで params: {{"a": "{{task_1}}", "b": 2}}
- "100から25を引く" → subtract ツールで params: {{"a": 100, "b": 25}}
- "100を4で割る" → divide ツールで params: {{"a": 100, "b": 4}}
- "商品の一覧を表示" → execute_safe_query ツールで params: {{"sql": "SELECT * FROM products"}}
- "テーブル構造を確認" → list_tables ツールで params: {{}}
- "商品テーブルのスキーマ" → get_table_schema ツールで params: {{"table_name": "products"}}
- "在庫が10以下の商品" → execute_safe_query ツールで params: {{"sql": "SELECT * FROM products WHERE stock <= 10"}}
- "売上データを表示" → execute_safe_query ツールで params: {{"sql": "SELECT * FROM sales"}}

## 出力形式（JSON）

複雑なタスクの場合:
{{
  "tasks": [
    {{
      "id": "task_1",
      "name": "タスクの説明",
      "tool": "使用するツール名",
      "params": {{
        "パラメータ名": 値または"{{task_X}}"
      }},
      "dependencies": ["依存するタスクID"]
    }}
  ]
}}

単純なタスクの場合（タスク分解不要）:
{{
  "type": "SIMPLE",
  "tool": "使用するツール名",
  "params": {{}}
}}

ツールが不要な場合（挨拶、感謝、雑談など）:
{{
  "type": "NO_TOOL",
  "response": "適切な応答メッセージ"
}}

## 判断基準
- 計算、データ取得、ファイル操作など → ツール必要
- テーブル構造の確認 → list_tables または get_table_schema
- 実際のデータ取得・検索・集計 → execute_safe_query
- 挨拶、感謝、褒め言葉、質問への簡単な回答 → ツール不要（NO_TOOL）
"""
        
        try:
            response = await self.llm.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.2
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # 単純なタスクの場合
            if result.get("type") == "SIMPLE":
                task = UniversalTask(
                    id="task_1",
                    name="Simple task",
                    tool=result.get("tool", ""),
                    params=result.get("params", {})
                )
                # サーバー情報を追加
                if task.tool in self.tools_info:
                    task.server = self.tools_info[task.tool]["server"]
                return [task]
            
            # ツール不要の場合
            if result.get("type") == "NO_TOOL":
                return []
            
            # 複雑なタスクの場合
            tasks = []
            for task_data in result.get("tasks", []):
                task = UniversalTask(
                    id=task_data["id"],
                    name=task_data["name"],
                    tool=task_data["tool"],
                    params=task_data.get("params", {}),
                    dependencies=task_data.get("dependencies", [])
                )
                
                # サーバー情報を追加
                if task.tool in self.tools_info:
                    task.server = self.tools_info[task.tool]["server"]
                
                tasks.append(task)
            
            return tasks
            
        except Exception as e:
            print(f"タスク分解エラー: {e}")
            return []
    
    def validate_tasks(self, tasks: List[UniversalTask]) -> List[str]:
        """タスクの妥当性をチェック"""
        errors = []
        
        for task in tasks:
            # ツールの存在チェック
            if task.tool not in self.tools_info:
                errors.append(f"タスク {task.id}: 不明なツール '{task.tool}'")
                continue
            
            # パラメータの検証
            tool_schema = self.tools_info[task.tool]["schema"]
            required_params = tool_schema.get("inputSchema", {}).get("required", [])
            
            for param in required_params:
                if param not in task.params:
                    # タスク参照でない場合はエラー
                    if not any(f"{{task_" in str(v) for v in task.params.values()):
                        errors.append(f"タスク {task.id}: 必須パラメータ '{param}' が不足")
            
            # 依存関係の検証
            for dep_id in task.dependencies:
                if not any(t.id == dep_id for t in tasks):
                    errors.append(f"タスク {task.id}: 依存タスク '{dep_id}' が存在しない")
        
        return errors

async def test_planner():
    """プランナーのテスト"""
    print("汎用タスクプランナーテスト")
    print("=" * 60)
    
    planner = UniversalTaskPlanner()
    await planner.initialize()
    
    # テストケース
    test_queries = [
        "100と200を足して",
        "データベースから全ての商品を取得して",
        "東京の天気を教えて",
        "100 + 200を計算して、その結果を2倍にして",
        "商品データを取得して、価格の合計を計算して"
    ]
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"クエリ: {query}")
        print("-" * 40)
        
        # タスクに分解
        tasks = await planner.plan_task(query)
        
        if not tasks:
            print("タスク分解不要またはツール不要")
            continue
        
        print(f"\n分解されたタスク: {len(tasks)}個")
        for task in tasks:
            print(f"\n  [{task.id}] {task.name}")
            print(f"    ツール: {task.tool}")
            print(f"    サーバー: {task.server}")
            print(f"    パラメータ: {task.params}")
            if task.dependencies:
                print(f"    依存: {task.dependencies}")
        
        # 妥当性チェック
        errors = planner.validate_tasks(tasks)
        if errors:
            print("\n検証エラー:")
            for error in errors:
                print(f"  - {error}")
        else:
            print("\n検証: OK")

if __name__ == "__main__":
    asyncio.run(test_planner())