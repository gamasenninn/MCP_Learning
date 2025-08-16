# my_first_agent_mock.py
"""
初めてのMCPエージェント（モックモード版）
APIキーなしで動作確認できます
"""

import asyncio
import sys
from pathlib import Path

# 親ディレクトリをパスに追加
sys.path.append(str(Path(__file__).parent.parent))

from integrated_agent import MCPAgent

async def main():
    print("="*60)
    print("My First MCP Agent (Mock Mode)")
    print("="*60)
    
    print("\n[INFO] モックモードで実行（APIキー不要）")
    
    # モックモードでエージェント起動
    agent = MCPAgent(use_mock=True)
    
    # いくつかのタスクを試す
    tasks = [
        "1から10までの数字を足し算してください",
        "25と35を掛け算して、その結果を2で割ってください",
        "100から50を引いて、その結果を3倍にしてください"
    ]
    
    for i, task in enumerate(tasks, 1):
        print(f"\n--- タスク {i} ---")
        print(f"内容: {task}")
        print("実行中...")
        
        result = await agent.execute(task)
        
        if result['success']:
            print(f"[成功] 実行時間: {result['duration']:.2f}秒")
            # 結果の最初の100文字を表示
            result_text = result['result'][:100]
            if len(result['result']) > 100:
                result_text += "..."
            print(f"結果: {result_text}")
        else:
            print(f"[失敗] {result.get('error', '不明なエラー')}")
    
    print("\n" + "="*60)
    print("デモ完了！")
    print("\n本番モードで実行するには：")
    print("1. APIキーを設定: set OPENAI_API_KEY=sk-xxxxx")
    print("2. my_first_agent.py を実行")

if __name__ == "__main__":
    # ログレベルを調整
    import logging
    logging.getLogger("mcp_manager").setLevel(logging.WARNING)
    logging.getLogger("integrated_agent").setLevel(logging.WARNING)
    logging.getLogger("task_planner").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("llm_client").setLevel(logging.WARNING)
    logging.getLogger("error_handler").setLevel(logging.WARNING)
    
    asyncio.run(main())