"""
実際のMCPサーバーとの接続テスト（自動実行版）
"""

import asyncio
import sys
from pathlib import Path

# 親ディレクトリをパスに追加
sys.path.append(str(Path(__file__).parent))

from integrated_agent import MCPAgent

async def test_with_real_calculator():
    """第3章の電卓サーバーを使用（実際のサーバー）"""
    print("\n" + "="*60)
    print("Test: Real Calculator Server")
    print("="*60)
    
    # 実際のMCPサーバーを使用
    agent = MCPAgent(use_mock=False)
    
    task = """
    以下の計算を実行してください：
    1. 15 + 25を計算
    2. その結果を2倍にする
    """
    
    try:
        result = await agent.execute(task)
        print(f"Success: {result['success']}")
        if result['success']:
            print(f"Result: {result['result']}")
        else:
            print(f"Error: {result.get('error')}")
    except Exception as e:
        print(f"Exception: {e}")
        print("\nNote: 実際のMCPサーバーへの接続にはサーバーが起動している必要があります")

async def test_with_mock():
    """モックモードでのテスト"""
    print("\n" + "="*60)
    print("Test: Mock Mode")
    print("="*60)
    
    agent = MCPAgent(use_mock=True)
    
    task = "10 + 20を計算して、結果を3倍にしてください"
    
    result = await agent.execute(task)
    print(f"Success: {result['success']}")
    print(f"Result: {result['result']}")
    print(f"Duration: {result['duration']:.2f} seconds")

async def main():
    """メイン処理"""
    print("\nMCP Agent Test - Mock vs Real Servers")
    print("="*80)
    
    # まずモックモードでテスト
    await test_with_mock()
    
    # 次に実際のサーバーでテスト（エラーが出ても続行）
    await test_with_real_calculator()
    
    print("\n" + "="*80)
    print("Test completed!")
    print("\nConclusion:")
    print("- モックモード: すぐに使える、テストに最適")
    print("- 実サーバーモード: より高度な機能、サーバー起動が必要")

if __name__ == "__main__":
    asyncio.run(main())