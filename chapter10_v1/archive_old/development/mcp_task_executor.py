#!/usr/bin/env python3
"""
MCPツールと連携するタスク実行エンジン
シンプルな実装で確実に動作させる
"""

import asyncio
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import os
import sys

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

from fastmcp import Client
from simple_task_planner import SimpleTask, SimpleTaskPlanner

class MCPTaskExecutor:
    """MCPツールを実行するエンジン"""
    
    def __init__(self):
        self.clients = {}
        self.results = {}
        self.tools_map = {}  # ツール名とサーバーのマッピング
        
    async def connect_calculator(self):
        """計算サーバーに接続"""
        try:
            server_path = "C:\\MCP_Learning\\chapter03\\calculator_server.py"
            client = Client(server_path)
            await client.__aenter__()
            self.clients["calculator"] = client
            
            # ツールを確認
            tools = await client.list_tools()
            for tool in tools:
                self.tools_map[tool.name] = "calculator"
                print(f"  ツール登録: {tool.name} -> calculator")
            
            print(f"計算サーバーに接続: {len(tools)}個のツール")
            return True
            
        except Exception as e:
            print(f"接続エラー: {e}")
            return False
    
    async def execute_task(self, task: SimpleTask) -> Any:
        """単一タスクを実行"""
        print(f"\n実行: {task.name}")
        print(f"  ツール: {task.tool}")
        
        # パラメータの解決
        resolved_params = {}
        for key, value in task.params.items():
            if isinstance(value, str) and value.startswith("{task_"):
                # タスク参照を解決
                task_id = value.strip("{}")
                if task_id in self.results:
                    resolved_params[key] = self.results[task_id]
                    print(f"  {key} = {self.results[task_id]} (from {task_id})")
                else:
                    error = f"依存タスク {task_id} が見つかりません"
                    print(f"  エラー: {error}")
                    task.error = error
                    return None
            else:
                resolved_params[key] = value
        
        print(f"  実行パラメータ: {resolved_params}")
        
        # ツールを実行
        if task.tool not in self.tools_map:
            error = f"ツール {task.tool} が見つかりません"
            print(f"  エラー: {error}")
            task.error = error
            return None
        
        server_name = self.tools_map[task.tool]
        client = self.clients.get(server_name)
        
        if not client:
            error = f"サーバー {server_name} に接続されていません"
            print(f"  エラー: {error}")
            task.error = error
            return None
        
        try:
            # MCPツールを呼び出し
            result = await client.call_tool(task.tool, resolved_params)
            
            # 結果を取得
            if hasattr(result, 'data'):
                actual_result = result.data
            elif hasattr(result, 'content'):
                actual_result = float(result.content[0].text)
            else:
                actual_result = result
            
            task.result = actual_result
            self.results[task.id] = actual_result
            print(f"  結果: {actual_result}")
            
            return actual_result
            
        except Exception as e:
            error = f"実行エラー: {e}"
            print(f"  {error}")
            task.error = error
            return None
    
    async def execute_tasks(self, tasks: List[SimpleTask]) -> Dict[str, Any]:
        """タスクリストを実行"""
        
        for task in tasks:
            await self.execute_task(task)
        
        # 最終結果を取得
        final_result = None
        for task in reversed(tasks):
            if task.result is not None:
                final_result = task.result
                break
        
        return {
            "tasks": [task.to_dict() for task in tasks],
            "final_result": final_result,
            "success": all(task.error is None for task in tasks)
        }
    
    async def cleanup(self):
        """クリーンアップ"""
        for client in self.clients.values():
            try:
                await client.__aexit__(None, None, None)
            except:
                pass

async def test_mcp_executor():
    """MCPタスク実行エンジンのテスト"""
    print("MCPタスク実行エンジンテスト")
    print("=" * 60)
    
    planner = SimpleTaskPlanner()
    executor = MCPTaskExecutor()
    
    # サーバーに接続
    print("\n[接続]")
    connected = await executor.connect_calculator()
    if not connected:
        print("サーバー接続に失敗しました")
        return
    
    # テストケース
    test_cases = [
        "100 + 200",
        "1000 - 250",
        "42 * 7",
        "100 / 4",
        "100 + 200 * 3",
        "100 + 200 + 4 * 50"
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
        
        print(f"\n分解されたタスク: {len(tasks)}個")
        for task in tasks:
            print(f"  {task.id}: {task.tool}({task.params})")
        
        # タスクを実行
        print("\n[実行]")
        result = await executor.execute_tasks(tasks)
        
        if result["success"]:
            print(f"\n[OK] 成功: {result['final_result']}")
        else:
            print(f"\n[FAIL] 失敗")
            for task_data in result["tasks"]:
                if task_data["error"]:
                    print(f"  - {task_data['name']}: {task_data['error']}")
        
        # 答え合わせ
        try:
            correct = eval(expression)
            if result["final_result"] and abs(result["final_result"] - correct) < 0.01:
                print(f"正解！ ({correct})")
            else:
                print(f"不正解 (正解: {correct})")
        except:
            pass
        
        # リセット
        executor.results.clear()
    
    # クリーンアップ
    await executor.cleanup()
    print("\n完了")

async def test_manual_execution():
    """手動タスクの実行テスト"""
    print("\n" + "=" * 60)
    print("手動タスク実行テスト: (100 + 200) * 2")
    print("-" * 40)
    
    executor = MCPTaskExecutor()
    
    # サーバーに接続
    await executor.connect_calculator()
    
    # 手動でタスクを作成
    tasks = [
        SimpleTask(
            id="task_1",
            name="100 + 200",
            tool="add",
            params={"a": 100, "b": 200}
        ),
        SimpleTask(
            id="task_2",
            name="結果を2倍",
            tool="multiply",
            params={"a": "{task_1}", "b": 2}
        )
    ]
    
    # 実行
    result = await executor.execute_tasks(tasks)
    
    print(f"\n最終結果: {result['final_result']}")
    print(f"正解: {(100 + 200) * 2} = 600")
    
    await executor.cleanup()

if __name__ == "__main__":
    asyncio.run(test_mcp_executor())
    asyncio.run(test_manual_execution())