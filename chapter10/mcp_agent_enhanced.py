#!/usr/bin/env python3
"""
MCPエージェント（拡張版）
数式評価ツールを含む改良版
"""

import asyncio
import os
import sys

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

from mcp_agent import MCPAgent
from mcp_llm_step1 import ToolCollector

class EnhancedMCPAgent(MCPAgent):
    """拡張版MCPエージェント"""
    
    def __init__(self, verbose: bool = True):
        # 拡張版の設定ファイルを使用
        super().__init__(verbose)
        self.collector = ToolCollector(config_file="mcp_servers_enhanced.json")

async def run_enhanced_agent():
    """拡張版エージェントの実行"""
    print("=" * 60)
    print("第10章 MCPエージェント（拡張版）")
    print("数式評価ツール搭載")
    print("=" * 60)
    print()
    print("機能:")
    print("- 複雑な数式の一括評価")
    print("- 計算過程の表示")
    print("- タスクマネージャーとエラーハンドリング")
    print()
    print("コマンド:")
    print("- 'stats': セッション統計を表示")
    print("- 'report': 詳細レポートを表示")
    print("- 'reset': タスクと会話履歴をリセット")
    print("- 'exit/quit': 終了")
    print()
    
    agent = EnhancedMCPAgent(verbose=True)
    
    try:
        await agent.run_interactive()
    except KeyboardInterrupt:
        print("\n\n中断されました。")
        await agent.cleanup()
    except Exception as e:
        print(f"\nエラーが発生しました: {e}")
        await agent.cleanup()

if __name__ == "__main__":
    asyncio.run(run_enhanced_agent())