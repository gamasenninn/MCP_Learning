#!/usr/bin/env python3
"""
MCPエージェント実行スクリプト
第10章で作成した統合MCPエージェントを起動する
"""

import asyncio
import sys
import os

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

from mcp_agent import MCPAgent

def print_banner():
    """バナーを表示"""
    print("=" * 60)
    print("第10章 MCPエージェント")
    print("タスクマネージャーとエラーハンドリング機能搭載")
    print("=" * 60)
    print()
    print("機能:")
    print("- 複雑なタスクの自動分解と実行")
    print("- エラーの自動検出とリトライ")
    print("- 実行状況のリアルタイム表示")
    print("- 統計情報とレポート機能")
    print()
    print("コマンド:")
    print("- 'stats': セッション統計を表示")
    print("- 'report': 詳細レポートを表示")
    print("- 'reset': タスクと会話履歴をリセット")
    print("- 'exit/quit': 終了")
    print()

async def main():
    """メイン実行"""
    print_banner()
    
    # エージェントを作成
    agent = MCPAgent(verbose=True)
    
    try:
        # 対話モードで実行
        await agent.run_interactive()
    except KeyboardInterrupt:
        print("\n\n中断されました。")
        await agent.cleanup()
    except Exception as e:
        print(f"\nエラーが発生しました: {e}")
        await agent.cleanup()

if __name__ == "__main__":
    asyncio.run(main())