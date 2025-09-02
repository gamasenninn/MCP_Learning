# minimal_agent.py - たった20行で動く！本章で作る実際のエージェント
import asyncio
from mcp_agent import MCPAgent  # 本章で実際に作成するクラス

async def main():
    
    # 本章で作成する実際のエージェント（簡単設定）
    agent = MCPAgent(config_path="minimal_config.yaml")
    await agent.initialize()
    
    print("終了するには 'quit' と入力してください。")
    
    while True:
        user_input = input("あなた: ")
        if user_input.lower() in ['quit', '終了', 'exit']:
            break
            
        # ✨ 魔法の1行 - すべてはここで起きる
        response = await agent.process_request(user_input)
        print(f"エージェント: {response}")
        print()

if __name__ == "__main__":
    asyncio.run(main())