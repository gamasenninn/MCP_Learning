#!/usr/bin/env python3
"""
リトライ機能のテストスクリプト
エラー時のリトライ動作を検証
"""

import asyncio
from mcp_agent import MCPAgentV4

async def test_retry():
    """リトライ機能をテスト"""
    print("リトライ機能テスト開始")
    print("=" * 60)
    
    agent = MCPAgentV4()
    await agent.initialize()
    
    # テストケース: 存在しないツールを実行してリトライを確認
    test_cases = [
        # 1. 存在しないツール（リトライされるはず）
        ("fake_tool", {"param": "value"}),
        
        # 2. 正常なツール
        ("add", {"a": 100, "b": 200}),
        
        # 3. パラメータエラー（LLMが修正を試みるはず）
        ("add", {"x": 100, "y": 200}),  # 間違ったパラメータ名
    ]
    
    for i, (tool, params) in enumerate(test_cases, 1):
        print(f"\n[テスト{i}] ツール: {tool}, パラメータ: {params}")
        print("-" * 40)
        
        try:
            # 直接ツール実行メソッドを呼び出し
            result = await agent._execute_tool_with_retry(tool, params)
            print(f"[成功] 結果: {result}")
        except Exception as e:
            print(f"[失敗] エラー: {e}")
        
        # エラー統計を表示
        stats = agent.error_handler.get_error_statistics()
        print(f"[統計] エラー総数: {stats['total_errors']}, "
              f"自動修正: {stats['auto_fixed']}, "
              f"リトライ成功: {stats['retry_success']}")
    
    await agent.close()
    print("\n" + "=" * 60)
    print("リトライ機能テスト完了")

if __name__ == "__main__":
    asyncio.run(test_retry())