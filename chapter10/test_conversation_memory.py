#!/usr/bin/env python3
"""会話記憶のテスト"""

import asyncio
import sys
sys.path.append('C:\\MCP_Learning\\chapter10')

async def test_conversation_memory():
    from mcp_agent import MCPAgent
    
    print("=== 会話記憶テスト ===")
    agent = MCPAgent()
    
    # セッション開始（自動で開始される）
    
    # 1. 名前を伝える
    print("\n[TEST] ユーザー: 俺の名前はサトシだ")
    response = await agent.process_request("俺の名前はサトシだ")
    print(f"[RESPONSE] {response}")
    
    # 2. 名前を尋ねる
    print("\n[TEST] ユーザー: 俺の名前は？")
    response = await agent.process_request("俺の名前は？")
    print(f"[RESPONSE] {response}")
    
    # 3. 年齢を伝える
    print("\n[TEST] ユーザー: 私の年齢は65歳です")
    response = await agent.process_request("私の年齢は65歳です")
    print(f"[RESPONSE] {response}")
    
    # 4. 年齢を使った計算
    print("\n[TEST] ユーザー: 私の年齢に10を足して")
    response = await agent.process_request("私の年齢に10を足して")
    print(f"[RESPONSE] {response}")
    
    await agent.cleanup()
    print("\n=== テスト完了 ===")

if __name__ == "__main__":
    asyncio.run(test_conversation_memory())