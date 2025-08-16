# my_first_agent.py
import asyncio
import sys
from pathlib import Path

# 親ディレクトリをパスに追加
sys.path.append(str(Path(__file__).parent.parent))

from integrated_agent import MCPAgent

async def main():
    # 本番モードでエージェント起動
    agent = MCPAgent(use_mock=False)
    
    # シンプルなタスク
    result = await agent.execute(
        "55と45を足して、その結果を表示してください"
    )
    
    print(f"結果: {result['result']}")

if __name__ == "__main__":
    asyncio.run(main())