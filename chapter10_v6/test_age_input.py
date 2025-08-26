#!/usr/bin/env python3
"""
年齢計算テストスクリプト
CLARIFICATIONタスクに年齢を応答してテストする
"""

import asyncio
from mcp_agent import MCPAgent

async def test_age_calculation():
    """年齢計算のテストを実行"""
    
    # エージェント初期化（設定ファイルパスを渡す）
    agent = MCPAgent('config.yaml')
    await agent.initialize()
    
    print("=== 年齢計算テスト開始 ===")
    
    # 1. 最初のリクエスト
    print("\n1. 年齢計算をリクエスト")
    result1 = await agent.process_request("calculate my age times 2 minus 100")
    print(f"結果: {result1}")
    
    # 2. 年齢を応答
    print("\n2. 年齢を応答 (65歳)")
    result2 = await agent.process_request("65")
    print(f"結果: {result2}")
    
    # 完了メッセージ
    print("\n=== テスト完了 ===")
    
    # クリーンアップ
    await agent.cleanup()

if __name__ == "__main__":
    asyncio.run(test_age_calculation())