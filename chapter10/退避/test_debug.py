"""
デバッグ用テスト - 詳細な情報を表示
"""

import asyncio
import logging
from integrated_agent import MCPAgent
from mcp_manager import MockMCPManager, ToolCall

# ログレベルをDEBUGに設定（詳細情報を表示）
logging.basicConfig(
    level=logging.INFO,  # DEBUGは詳しすぎるのでINFOに
    format='%(message)s'  # シンプルな形式
)

async def test_mock_tools():
    """モックツールの動作を直接確認"""
    print("\n" + "="*60)
    print("モックツールの直接テスト")
    print("="*60)
    
    manager = MockMCPManager()
    
    # 加算テスト
    print("\n1. 加算: 10 + 20")
    result = await manager.call_tool(ToolCall(
        server="calculator",
        tool="add",
        params={"a": 10, "b": 20}
    ))
    print(f"   結果: {result.data}")
    print(f"   成功: {result.success}")
    
    # 乗算テスト
    print("\n2. 乗算: 30 × 3")
    result = await manager.call_tool(ToolCall(
        server="calculator",
        tool="multiply",
        params={"a": 30, "b": 3}
    ))
    print(f"   結果: {result.data}")
    print(f"   成功: {result.success}")

async def test_agent_with_details():
    """エージェントの詳細な動作確認"""
    print("\n" + "="*60)
    print("エージェントの詳細テスト")
    print("="*60)
    
    agent = MCPAgent(use_mock=True)
    
    # シンプルなタスク
    print("\n実行するタスク: 「15 + 25 を計算」")
    result = await agent.execute("15 + 25 を計算")
    
    print(f"\n【実行結果】")
    print(f"成功: {result['success']}")
    print(f"結果: {result['result'][:200]}...")  # 最初の200文字
    
    # より複雑なタスク
    print("\n" + "="*60)
    print("複雑なタスク: 「(100 ÷ 5) × 3」")
    result = await agent.execute("100を5で割って、その結果を3倍にして")
    
    print(f"\n【実行結果】")
    print(f"成功: {result['success']}")
    print(f"結果: {result['result'][:200]}...")

async def main():
    # モックツールを直接テスト
    await test_mock_tools()
    
    # エージェント経由でテスト
    await test_agent_with_details()
    
    print("\n" + "="*60)
    print("テスト完了！")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())