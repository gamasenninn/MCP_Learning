"""
シンプルなMCPエージェントのデモ
基本的な使い方を示す例
"""

import asyncio
import os
import sys
from pathlib import Path

# 親ディレクトリをパスに追加
sys.path.append(str(Path(__file__).parent.parent))

from integrated_agent import MCPAgent

async def main():
    """メイン処理"""
    
    print("[MCP Agent Simple Demo]")
    print("="*60)
    
    # エージェントを初期化（モックモード）
    print("\n1. Initializing agent...")
    agent = MCPAgent(use_mock=True)
    print("[OK] Agent initialized in mock mode")
    
    # シンプルなタスクを実行
    print("\n2. Executing simple calculation task...")
    task1 = "Calculate 10 + 20, then multiply by 3"
    result = await agent.execute(task1)
    
    if result['success']:
        print(f"[SUCCESS] Result: {result['result']}")
    else:
        print(f"[FAILED] Error: {result.get('error')}")
    
    print(f"Duration: {result['duration']:.2f} seconds")
    
    # 複数ステップのタスク
    print("\n3. Executing multi-step task...")
    task2 = "Search for Python tutorials, select the top 3 results, and create a summary"
    result = await agent.execute(task2)
    
    if result['success']:
        print(f"[SUCCESS] Completed {result['steps_executed']} steps")
        print(f"Summary: {result['result'][:200]}...")  # 最初の200文字
    else:
        print(f"[FAILED] Error: {result.get('error')}")
    
    # エラー処理のデモ
    print("\n4. Testing error handling...")
    task3 = "Access restricted database and retrieve sensitive data"
    result = await agent.execute(task3)
    
    if not result['success']:
        print(f"[EXPECTED ERROR] {result.get('error')}")
        print("Error handling worked correctly!")
    
    print("\n" + "="*60)
    print("Demo completed!")

if __name__ == "__main__":
    asyncio.run(main())