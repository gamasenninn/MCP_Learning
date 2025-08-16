"""
実サーバーでの複雑なタスクテスト
"""

import asyncio
import sys
from pathlib import Path

# 親ディレクトリをパスに追加
sys.path.append(str(Path(__file__).parent))

from integrated_agent import MCPAgent

async def main():
    """複雑なタスクのテスト"""
    print("\n" + "="*60)
    print("Complex Task Test with Real Servers")
    print("="*60)
    
    # 実際のMCPサーバーを使用
    agent = MCPAgent(use_mock=False)
    
    # 複数ステップのタスク
    task = """
    以下の計算を順番に実行してください：
    1. 100と50を足す
    2. その結果から30を引く
    3. 最後に2倍にする
    """
    
    try:
        result = await agent.execute(task)
        print(f"\n[Result]")
        print(f"Success: {result['success']}")
        if result['success']:
            print(f"Answer: {result['result']}")
            print(f"Duration: {result['duration']:.2f} seconds")
            print(f"Steps executed: {result['steps_executed']}")
        else:
            print(f"Error: {result.get('error')}")
    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())