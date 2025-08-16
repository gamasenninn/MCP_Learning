# my_first_agent.py
"""
初めてのMCPエージェント
本番モードで動作するシンプルな例
"""

import asyncio
import sys
from pathlib import Path

# 親ディレクトリをパスに追加
sys.path.append(str(Path(__file__).parent.parent))

from integrated_agent import MCPAgent

async def main():
    print("="*60)
    print("My First MCP Agent")
    print("="*60)
    
    # APIキーの確認
    import os
    if not os.getenv("OPENAI_API_KEY"):
        print("\n[ERROR] APIキーが設定されていません")
        print("環境変数 OPENAI_API_KEY を設定してください")
        print("例: set OPENAI_API_KEY=sk-xxxxx")
        return
    
    print("\n初期化中...")
    
    # 本番モードでエージェント起動
    agent = MCPAgent(use_mock=False)
    
    # シンプルなタスク
    task = "1から10までの数字を足し算してください"
    print(f"\nタスク: {task}")
    print("\n実行中...")
    
    result = await agent.execute(task)
    
    # 結果の表示
    print("\n" + "="*60)
    if result['success']:
        print("[成功]")
        print(f"結果: {result['result']}")
        print(f"実行時間: {result['duration']:.2f}秒")
        print(f"実行ステップ数: {result['steps_executed']}")
    else:
        print("[失敗]")
        print(f"エラー: {result.get('error', '不明なエラー')}")
    
    print("="*60)

if __name__ == "__main__":
    # ログレベルを調整してクリーンな出力に
    import logging
    logging.getLogger("mcp_manager").setLevel(logging.WARNING)
    logging.getLogger("integrated_agent").setLevel(logging.WARNING)
    logging.getLogger("task_planner").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    asyncio.run(main())