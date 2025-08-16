"""
実際のMCPサーバーを使用するデモ
第3章、第6章、第7章、第8章のサーバーと連携
"""

import asyncio
import sys
from pathlib import Path

# 親ディレクトリをパスに追加
sys.path.append(str(Path(__file__).parent.parent))

from integrated_agent import MCPAgent

async def test_calculator():
    """第3章の電卓サーバーを使用"""
    print("\n" + "="*60)
    print("Test 1: Calculator Server (Chapter 3)")
    print("="*60)
    
    agent = MCPAgent(use_mock=False)
    
    task = """
    以下の計算を実行してください：
    1. 15 + 25 = ?
    2. 結果を2倍にする
    3. 最終結果から10を引く
    """
    
    result = await agent.execute(task)
    print(f"Result: {result['result']}")

async def test_database():
    """第6章のデータベースサーバーを使用"""
    print("\n" + "="*60)
    print("Test 2: Database Server (Chapter 6)")
    print("="*60)
    
    agent = MCPAgent(use_mock=False)
    
    task = """
    データベースで以下の操作を実行：
    1. usersテーブルがあるか確認
    2. もしなければ作成（id, name, email）
    3. サンプルユーザーを追加
    4. 全ユーザーを取得して表示
    """
    
    result = await agent.execute(task)
    print(f"Result: {result['result']}")

async def test_weather():
    """第7章の天気APIサーバーを使用"""
    print("\n" + "="*60)
    print("Test 3: Weather API Server (Chapter 7)")
    print("="*60)
    
    agent = MCPAgent(use_mock=False)
    
    task = """
    天気情報を取得：
    1. 東京の現在の天気
    2. 明日の予報
    3. 週間天気の概要
    """
    
    result = await agent.execute(task)
    print(f"Result: {result['result']}")

async def test_universal():
    """第8章の汎用ツールサーバーを使用"""
    print("\n" + "="*60)
    print("Test 4: Universal Tools Server (Chapter 8)")
    print("="*60)
    
    agent = MCPAgent(use_mock=False)
    
    task = """
    以下のタスクを実行：
    1. "Python MCP"について検索
    2. 検索結果の要約を作成
    3. 簡単なPythonコードを実行（1から5の合計）
    """
    
    result = await agent.execute(task)
    print(f"Result: {result['result']}")

async def integrated_task():
    """複数のサーバーを組み合わせたタスク"""
    print("\n" + "="*60)
    print("Integrated Task: Using Multiple Servers")
    print("="*60)
    
    agent = MCPAgent(use_mock=False)
    
    task = """
    統合タスクを実行：
    1. 今日の東京の気温を取得（weather）
    2. 気温を摂氏から華氏に変換（calculator）
    3. 結果をデータベースに保存（database）
    4. 保存したデータを確認
    """
    
    result = await agent.execute(task)
    print(f"Result: {result['result']}")

async def main():
    """メイン処理"""
    print("\n" + "="*80)
    print(" Real MCP Servers Demo")
    print(" Testing integration with Chapter 3, 6, 7, 8 servers")
    print("="*80)
    
    # 各サーバーが存在するか確認
    servers_ok = True
    required_servers = [
        ("calculator", "C:\\MCP_Learning\\chapter03\\calculator_server.py"),
        ("database", "C:\\MCP_Learning\\chapter06\\database_server.py"),
        ("weather", "C:\\MCP_Learning\\chapter07\\external_api_server.py"),
        ("universal", "C:\\MCP_Learning\\chapter08\\universal_tools_server.py")
    ]
    
    print("\nChecking required servers...")
    for name, path in required_servers:
        if Path(path).exists():
            print(f"[OK] {name}: {path}")
        else:
            print(f"[MISSING] {name}: {path}")
            servers_ok = False
    
    if not servers_ok:
        print("\n[ERROR] Some servers are missing. Please ensure all chapter servers are set up.")
        print("You can still run the demo with mock mode.")
        return
    
    print("\nSelect demo:")
    print("1. Calculator (Chapter 3)")
    print("2. Database (Chapter 6)")
    print("3. Weather API (Chapter 7)")
    print("4. Universal Tools (Chapter 8)")
    print("5. Integrated Task (All servers)")
    print("0. Exit")
    
    choice = input("\nEnter your choice: ").strip()
    
    try:
        if choice == "1":
            await test_calculator()
        elif choice == "2":
            await test_database()
        elif choice == "3":
            await test_weather()
        elif choice == "4":
            await test_universal()
        elif choice == "5":
            await integrated_task()
        elif choice == "0":
            print("Exiting...")
        else:
            print("Invalid choice")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        print("\nTip: Make sure:")
        print("1. Your API key is set in .env file")
        print("2. All required servers are installed")
        print("3. You ran 'uv sync' in the chapter10 directory")

if __name__ == "__main__":
    asyncio.run(main())