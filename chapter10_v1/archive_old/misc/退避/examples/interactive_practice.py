#!/usr/bin/env python3
"""
インタラクティブ練習モード
原稿の例題を実際に試せます
"""

import asyncio
import sys
from pathlib import Path

# 親ディレクトリをパスに追加
sys.path.append(str(Path(__file__).parent.parent))

from integrated_agent import MCPAgent
import os

async def main():
    """メイン処理"""
    
    print("\n" + "="*80)
    print(" MCPエージェント - インタラクティブ練習モード")
    print("="*80)
    
    # APIキーの確認
    if not os.getenv("OPENAI_API_KEY"):
        print("\n[INFO] APIキーが設定されていません。モックモードで実行します。")
        print("本番モードで実行するには：")
        print("  set OPENAI_API_KEY=sk-xxxxx")
        agent = MCPAgent(use_mock=True)
    else:
        print("\n[INFO] 本番モードで実行（実際のAIが応答します）")
        agent = MCPAgent(use_mock=False)
    
    print("\n試してみる質問例：")
    print("  - 「50と75を足してください」")
    print("  - 「100から25を引いて、その結果を2倍にしてください」")
    print("  - 「現在のタスク一覧を表示して」")
    print("  - 「簡単な自己紹介文を作って」")
    print("\n終了するには 'quit' または 'exit' と入力してください")
    print("="*80)
    
    while True:
        print("\n質問を入力してください")
        print("> ", end="")
        
        try:
            task = input().strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n終了します...")
            break
        
        if task.lower() in ['quit', 'exit', 'q', '終了']:
            print("\nありがとうございました！")
            break
        
        if not task:
            continue
        
        print("\n処理中...")
        
        try:
            result = await agent.execute(task)
            
            if result['success']:
                print("\n" + "="*60)
                print("[成功]")
                print("-"*60)
                # 結果を整形して表示
                result_text = result['result']
                # 長すぎる場合は切り詰める（1500文字まで表示）
                if len(result_text) > 1500:
                    result_text = result_text[:1500] + "\n\n[...結果が長いため省略されました...]"
                print(result_text)
                print("-"*60)
                print(f"実行時間: {result['duration']:.2f}秒")
                print(f"実行ステップ数: {result['steps_executed']}")
                print("="*60)
            else:
                print("\n[エラー]")
                print(f"申し訳ありません。エラーが発生しました: {result.get('error', '不明なエラー')}")
                
        except Exception as e:
            print(f"\n[システムエラー] {e}")
            print("もう一度お試しください。")
    
    print("\n練習セッション終了")
    print("="*80)

if __name__ == "__main__":
    # ログレベルを調整してクリーンな出力に
    import logging
    logging.getLogger("mcp_manager").setLevel(logging.CRITICAL)  # エラーログを抑制
    logging.getLogger("integrated_agent").setLevel(logging.WARNING)
    logging.getLogger("task_planner").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("llm_client").setLevel(logging.WARNING)
    logging.getLogger("error_handler").setLevel(logging.WARNING)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n中断されました。")
        sys.exit(0)