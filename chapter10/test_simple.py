"""
最もシンプルなテスト - モックモードで基本動作を確認
"""

import asyncio
from integrated_agent import MCPAgent

async def main():
    print("\n" + "="*60)
    print("シンプルテスト - 10 + 20 を計算して3倍")
    print("="*60)
    
    # モックモードで実行（APIキー不要）
    agent = MCPAgent(use_mock=True)
    
    # タスクを実行
    result = await agent.execute("10と20を足して、その結果を3倍にしてください")
    
    # 結果を表示
    print(f"\n【結果】")
    print(f"成功: {result['success']}")
    print(f"実行時間: {result['duration']:.2f}秒")
    print(f"実行ステップ数: {result['steps_executed']}")
    print(f"\n回答:")
    print(result['result'])
    
    # 期待される答え: (10 + 20) × 3 = 90

if __name__ == "__main__":
    asyncio.run(main())