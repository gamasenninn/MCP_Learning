#!/usr/bin/env python3
"""
汎用タスク実行エンジン
複数のMCPサーバーと連携してタスクを実行
"""

import asyncio
import json
import os
import sys
from typing import Dict, List, Any, Optional
from pathlib import Path

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

from fastmcp import Client
from universal_task_planner import UniversalTask, UniversalTaskPlanner

class UniversalTaskExecutor:
    """汎用タスク実行エンジン"""
    
    def __init__(self, config_file: str = "mcp_servers.json"):
        self.config_file = config_file
        self.servers = {}
        self.clients = {}
        self.results = {}
        self.tools_map = {}
        self._load_config()
    
    def _load_config(self):
        """設定ファイルを読み込み"""
        config_path = Path(self.config_file)
        if not config_path.exists():
            print(f"[警告] 設定ファイル {self.config_file} が見つかりません")
            return
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        for server_info in config.get("servers", []):
            self.servers[server_info["name"]] = server_info
    
    async def connect_all_servers(self):
        """全サーバーに接続"""
        print("[接続] MCPサーバーに接続中...")
        
        for server_name, server_info in self.servers.items():
            try:
                print(f"  {server_name}に接続中...", end="")
                client = Client(server_info["path"])
                await client.__aenter__()
                self.clients[server_name] = client
                
                # ツールを確認
                tools = await client.list_tools()
                for tool in tools:
                    self.tools_map[tool.name] = server_name
                
                print(f" OK ({len(tools)}個のツール)")
                
            except Exception as e:
                print(f" 失敗: {e}")
        
        print(f"  合計: {len(self.tools_map)}個のツールが利用可能")
    
    async def execute_task(self, task: UniversalTask) -> Any:
        """単一タスクを実行"""
        print(f"\n[実行] {task.name}")
        print(f"  ツール: {task.tool} (サーバー: {task.server})")
        
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
        
        print(f"  パラメータ: {resolved_params}")
        
        # サーバーの特定
        server_name = task.server or self.tools_map.get(task.tool)
        if not server_name:
            error = f"ツール {task.tool} のサーバーが見つかりません"
            print(f"  エラー: {error}")
            task.error = error
            return None
        
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
                # コンテンツから結果を抽出
                content = result.content
                if isinstance(content, list) and len(content) > 0:
                    text = content[0].text
                    # 数値に変換可能か試す
                    try:
                        actual_result = float(text)
                    except:
                        actual_result = text
                else:
                    actual_result = str(content)
            else:
                actual_result = result
            
            task.result = actual_result
            self.results[task.id] = actual_result
            
            # 結果の表示（長い場合は省略）
            if isinstance(actual_result, str) and len(actual_result) > 100:
                print(f"  結果: {actual_result[:100]}...")
            else:
                print(f"  結果: {actual_result}")
            
            return actual_result
            
        except Exception as e:
            error = f"実行エラー: {e}"
            print(f"  {error}")
            task.error = error
            return None
    
    async def execute_tasks(self, tasks: List[UniversalTask]) -> Dict[str, Any]:
        """タスクリストを実行"""
        
        success_count = 0
        fail_count = 0
        
        for task in tasks:
            result = await self.execute_task(task)
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
        
        return {
            "tasks": [task.to_dict() for task in tasks],
            "final_result": final_result,
            "success": fail_count == 0,
            "stats": {
                "total": len(tasks),
                "success": success_count,
                "failed": fail_count
            }
        }
    
    async def cleanup(self):
        """クリーンアップ"""
        print("\n[クリーンアップ] 接続を閉じています...")
        for server_name, client in self.clients.items():
            try:
                await client.__aexit__(None, None, None)
                print(f"  {server_name}: 切断")
            except:
                pass

async def test_universal_executor():
    """汎用タスク実行エンジンのテスト"""
    print("汎用タスク実行エンジンテスト")
    print("=" * 60)
    
    planner = UniversalTaskPlanner()
    executor = UniversalTaskExecutor()
    
    # 初期化
    await planner.initialize()
    await executor.connect_all_servers()
    
    # テストケース
    test_cases = [
        # 計算タスク
        ("100 + 200を計算して", "計算"),
        
        # 複数ステップの計算
        ("100と200を足して、その結果を3で割って", "複数ステップ計算"),
        
        # データベースタスク（実際のDBがない場合はエラーになる）
        # ("データベースのテーブル一覧を取得", "DB操作"),
        
        # 天気タスク（APIキーが必要）
        # ("東京の天気を教えて", "天気情報"),
        
        # 複合タスク
        ("2の8乗を計算して", "べき乗計算"),
    ]
    
    for query, task_type in test_cases:
        print(f"\n{'='*60}")
        print(f"テスト: {task_type}")
        print(f"クエリ: {query}")
        print("-" * 40)
        
        # タスクに分解
        tasks = await planner.plan_task(query)
        
        if not tasks:
            print("タスク分解不要またはツール不要")
            continue
        
        print(f"\n分解されたタスク: {len(tasks)}個")
        for task in tasks:
            print(f"  {task.id}: {task.tool}({task.params})")
        
        # タスクを実行
        result = await executor.execute_tasks(tasks)
        
        print(f"\n[結果]")
        if result["success"]:
            print(f"  成功: {result['final_result']}")
        else:
            print(f"  失敗")
            for task_data in result["tasks"]:
                if task_data["error"]:
                    print(f"    - {task_data['name']}: {task_data['error']}")
        
        print(f"  統計: {result['stats']}")
        
        # リセット
        executor.results.clear()
    
    # クリーンアップ
    await executor.cleanup()
    print("\n完了")

async def demo_complex_task():
    """複雑なタスクのデモ"""
    print("\n" + "=" * 60)
    print("複雑なタスクのデモ")
    print("-" * 40)
    
    planner = UniversalTaskPlanner()
    executor = UniversalTaskExecutor()
    
    await planner.initialize()
    await executor.connect_all_servers()
    
    # 複雑な計算タスク
    query = "100と200を足して、その結果に50を掛けて、最後に10で割って"
    print(f"クエリ: {query}")
    
    tasks = await planner.plan_task(query)
    
    if tasks:
        print(f"\nタスク数: {len(tasks)}")
        result = await executor.execute_tasks(tasks)
        print(f"\n最終結果: {result['final_result']}")
        
        # 答え合わせ
        correct = ((100 + 200) * 50) / 10
        print(f"正解: {correct}")
    
    await executor.cleanup()

if __name__ == "__main__":
    asyncio.run(test_universal_executor())
    asyncio.run(demo_complex_task())