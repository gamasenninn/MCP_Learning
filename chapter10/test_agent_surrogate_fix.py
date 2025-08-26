#!/usr/bin/env python3
"""
Test script to verify agent surrogate character fixes
MCPエージェントV4でサロゲート文字問題が解決されたかをテスト
"""

import asyncio
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_agent import MCPAgent

async def test_agent_with_surrogate():
    """エージェントでサロゲート文字を含む可能性があるリクエストをテスト"""
    
    print("=" * 60)
    print("MCP Agent - Surrogate Character Fix Test")
    print("=" * 60)
    
    # Create config file for test (complete version)
    config_content = """{
    "connection": {
        "config_file": "mcp_servers.json"
    },
    "llm": {
        "provider": "openai", 
        "model": "gpt-4o",
        "temperature": 0.1
    },
    "ui": {
        "mode": "simple",
        "show_thinking": true
    },
    "display": {
        "show_timing": true,
        "show_thinking": true
    },
    "agent": {
        "max_execution_steps": 10,
        "custom_instructions": null
    }
}"""
    
    config_path = "test_config.json"
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(config_content)
    
    # Initialize agent
    agent = MCPAgent(config_path)
    
    try:
        # Initialize connections
        await agent.initialize()
        print("\n[初期化完了] エージェントが起動しました")
        
        # Test 1: Simple sudoku request (similar to what user reported)
        print("\n" + "=" * 40)
        print("Test 1: 数独パズル生成と解答")
        print("=" * 40)
        
        user_query = "数独パズルを生成して、それを解いてください。結果を表示してください。"
        
        print(f"\nUser: {user_query}")
        print("\nAgent: 処理中...")
        
        response = await agent.process_request(user_query)
        
        print(f"\nAgent Response:")
        print("-" * 40)
        print(response)
        print("-" * 40)
        
        # Test 2: Simple code execution
        print("\n" + "=" * 40)  
        print("Test 2: シンプルなコード実行")
        print("=" * 40)
        
        user_query2 = "フィボナッチ数列の最初の10個を計算して表示してください。"
        
        print(f"\nUser: {user_query2}")
        print("\nAgent: 処理中...")
        
        response2 = await agent.process_request(user_query2)
        
        print(f"\nAgent Response:")
        print("-" * 40)
        print(response2)
        print("-" * 40)
        
        print("\n✓ すべてのテストが完了しました！")
        print("  サロゲート文字エラーが発生しなければ修正は成功です。")
        
    except Exception as e:
        print(f"\n✗ テスト中にエラーが発生: {e}")
        import traceback
        traceback.print_exc()
        
        # Check if it's a surrogate character error
        if "surrogates not allowed" in str(e):
            print("\n⚠️  サロゲート文字エラーが検出されました")
            print("   まだ修正が必要な箇所があります")
        
    finally:
        await agent.cleanup()
        print("\n[終了] エージェントを終了しました")


if __name__ == "__main__":
    asyncio.run(test_agent_with_surrogate())