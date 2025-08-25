"""
実サーバーとの接続テスト（実サーバーのみ）
"""

import asyncio
import sys
from pathlib import Path

# 親ディレクトリをパスに追加
sys.path.append(str(Path(__file__).parent))

from integrated_agent import MCPAgent

async def main():
    """実サーバーでのテスト"""
    print("\n" + "="*60)
    print("Real Server Connection Test")
    print("="*60)
    
    # 実際のMCPサーバーを使用
    agent = MCPAgent(use_mock=False)
    
    # シンプルなタスク
    task = "25 + 35を計算してください"
    
    try:
        result = await agent.execute(task)
        print(f"\n[Result]")
        print(f"Success: {result['success']}")
        if result['success']:
            print(f"Answer: {result['result']}")
            print(f"Duration: {result['duration']:.2f} seconds")
            print(f"Steps: {result['steps_executed']}")
        else:
            print(f"Error: {result.get('error')}")
    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())