#!/usr/bin/env python3
"""
MCPエージェントのデバッグバージョン
ツール呼び出しの詳細を表示
"""

import asyncio
import sys
import os
import json
from typing import Dict, Any

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

from mcp_agent import MCPAgent

class DebugMCPAgent(MCPAgent):
    """デバッグ機能付きMCPエージェント"""
    
    async def _analyze_query(self, query: str) -> Dict:
        """クエリを分析（デバッグ情報付き）"""
        result = await super()._analyze_query(query)
        
        print("\n[DEBUG] LLM分析結果:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        return result
    
    async def _execute_tool_with_error_handling(self, analysis: Dict) -> Any:
        """ツール実行（デバッグ情報付き）"""
        tool_name = analysis["tool_name"]
        tool_params = analysis.get("tool_params", {})
        
        print(f"\n[DEBUG] ツール実行:")
        print(f"  ツール名: {tool_name}")
        print(f"  パラメータ: {tool_params}")
        
        # 利用可能なツールを確認
        for server_name, tools in self.collector.tools_schema.items():
            for tool in tools:
                if tool["name"] == tool_name:
                    print(f"  サーバー: {server_name}")
                    print(f"  ツール定義:")
                    print(f"    パラメータ: {tool.get('inputSchema', {}).get('properties', {})}")
                    break
        
        try:
            result = await super()._execute_tool_with_error_handling(analysis)
            print(f"  結果: {result}")
            return result
        except Exception as e:
            print(f"  エラー: {e}")
            raise

async def debug_calculation():
    """計算機能のデバッグ"""
    print("MCPエージェント デバッグモード")
    print("=" * 60)
    
    agent = DebugMCPAgent(verbose=False)
    await agent.initialize()
    
    # 簡単な計算をテスト
    query = "100と200を足してください"
    print(f"\nクエリ: {query}")
    
    response = await agent.process_query(query)
    print(f"\n最終応答: {response}")
    
    await agent.cleanup()

if __name__ == "__main__":
    asyncio.run(debug_calculation())