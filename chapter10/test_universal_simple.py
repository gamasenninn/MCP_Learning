#!/usr/bin/env python3
"""
汎用タスクシステムの簡単なテスト
計算機能のみでテスト
"""

import asyncio
import os
import sys

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

from universal_task_planner import UniversalTaskPlanner
from universal_task_executor import UniversalTaskExecutor

async def test_calculation_only():
    """計算機能のみでテスト"""
    print("汎用タスクシステムテスト（計算のみ）")
    print("=" * 60)
    
    # プランナーとエグゼキューターを作成
    planner = UniversalTaskPlanner()
    executor = UniversalTaskExecutor()
    
    # 初期化（計算サーバーのみ）
    print("\n[初期化]")
    await planner.initialize()
    
    # 計算サーバーのみ接続
    print("\n[接続] 計算サーバーのみ接続")
    try:
        from fastmcp import Client
        server_path = "C:\\MCP_Learning\\chapter03\\calculator_server.py"
        client = Client(server_path)
        await client.__aenter__()
        executor.clients["calculator"] = client
        
        # ツールマップを作成
        tools = await client.list_tools()
        for tool in tools:
            executor.tools_map[tool.name] = "calculator"
        
        print(f"  計算サーバー接続: {len(tools)}個のツール")
    except Exception as e:
        print(f"  接続エラー: {e}")
        return
    
    # テストケース
    test_cases = [
        "100 + 200を計算して",
        "1000から250を引いて",
        "100と200を足して、その結果を2で割って",
        "2の8乗を計算して",
        "100 + 200 + 300を計算して"
    ]
    
    for query in test_cases:
        print(f"\n{'='*60}")
        print(f"クエリ: {query}")
        print("-" * 40)
        
        # タスクに分解
        tasks = await planner.plan_task(query)
        
        if not tasks:
            print("タスク分解不要")
            continue
        
        print(f"\nタスク数: {len(tasks)}")
        for task in tasks:
            print(f"  [{task.id}] {task.tool}({task.params})")
            if task.dependencies:
                print(f"    依存: {task.dependencies}")
        
        # タスクを実行
        print("\n実行:")
        result = await executor.execute_tasks(tasks)
        
        if result["success"]:
            print(f"\n[成功] 結果: {result['final_result']}")
        else:
            print(f"\n[失敗]")
            for task_data in result["tasks"]:
                if task_data["error"]:
                    print(f"  - {task_data['name']}: {task_data['error']}")
        
        # リセット
        executor.results.clear()
    
    # クリーンアップ
    print("\n[クリーンアップ]")
    try:
        await executor.clients["calculator"].__aexit__(None, None, None)
        print("  計算サーバー切断")
    except:
        pass
    
    print("\nテスト完了")

if __name__ == "__main__":
    asyncio.run(test_calculation_only())