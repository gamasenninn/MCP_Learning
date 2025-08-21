"""
Step 3: 統合テスト (V2 - mcpServers形式対応)
Step 1とStep 2を組み合わせた動作確認
"""
import asyncio
import os
from typing import List, Dict, Any
from dotenv import load_dotenv
from openai import AsyncOpenAI
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

# Step 1とStep 2のV2クラスをインポート
from mcp_llm_step1_v2 import ToolCollectorV2
from mcp_llm_step2_v2 import LLMIntegrationPrepV2

load_dotenv()

class IntegrationTesterV2:
    """統合テストクラス（mcpServers形式対応）"""
    
    def __init__(self):
        self.collector = ToolCollectorV2()
        self.prep = LLMIntegrationPrepV2()
        self.llm = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.clients = {}
        
    async def setup(self):
        """テスト環境のセットアップ"""
        print("[セットアップ] 統合テストのセットアップ中...")
        
        # Step 1: ツール情報の収集
        await self.collector.collect_all_tools()
        
        # MCPクライアントの接続を維持（StdioTransport使用）
        for server_name, server_info in self.collector.servers.items():
            transport = StdioTransport(
                command=server_info["command"],
                args=server_info["args"]
            )
            client = Client(transport)
            await client.__aenter__()
            self.clients[server_name] = client
        
        print("[OK] セットアップ完了\n")
    
    async def test_llm_tool_selection(self, query: str) -> Dict:
        """LLMによるツール選択のテスト"""
        # Step 2: スキーマ整形とプロンプト生成
        tools_desc = self.prep.prepare_tools_for_llm(self.collector.tools_schema)
        prompt = self.prep.create_tool_selection_prompt(query, tools_desc)
        
        # LLMに問い合わせ
        response = await self.llm.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        
        # 応答を検証
        return self.prep.validate_llm_response(response.choices[0].message.content)
    
    async def execute_selected_tool(self, validation_result: Dict) -> Any:
        """選択されたツールを実行"""
        if not validation_result["valid"]:
            print(f"[ERROR] 無効な応答: {validation_result['error']}")
            return None
        
        server_name = validation_result["server_name"]
        tool_name = validation_result["tool_name"]
        parameters = validation_result["parameters"]
        
        if server_name not in self.clients:
            print(f"[ERROR] サーバー '{server_name}' に接続されていません")
            return None
        
        try:
            client = self.clients[server_name]
            print(f"[実行] {server_name}.{tool_name} を実行中...")
            print(f"[パラメータ] {parameters}")
            
            result = await client.call_tool(tool_name, parameters)
            
            # 結果の抽出
            if hasattr(result, 'structured_content') and result.structured_content:
                return result.structured_content.get('result', str(result))
            elif hasattr(result, 'content') and result.content:
                if isinstance(result.content, list) and result.content:
                    return result.content[0].text if hasattr(result.content[0], 'text') else str(result)
            elif hasattr(result, 'data'):
                return result.data
            else:
                return str(result)
                
        except Exception as e:
            print(f"[ERROR] ツール実行に失敗: {e}")
            return None
    
    async def run_integration_test(self, test_queries: List[str]):
        """統合テストの実行"""
        print("🧪 統合テスト開始")
        print("="*50)
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n🔍 テスト {i}: '{query}'")
            print("-" * 30)
            
            try:
                # Step 1: LLMによるツール選択
                validation = await self.test_llm_tool_selection(query)
                
                if validation["valid"]:
                    print(f"[OK] ツール選択: {validation['server_name']}.{validation['tool_name']}")
                    print(f"[理由] {validation['reasoning']}")
                    
                    # Step 2: 選択されたツールの実行
                    result = await self.execute_selected_tool(validation)
                    
                    if result is not None:
                        print(f"[結果] {result}")
                    else:
                        print("[FAIL] ツール実行に失敗")
                else:
                    print(f"[FAIL] ツール選択に失敗: {validation['error']}")
                    
            except Exception as e:
                print(f"[ERROR] テスト実行中にエラー: {e}")
            
            print()
    
    async def cleanup(self):
        """リソースのクリーンアップ"""
        print("[クリーンアップ] 接続を終了中...")
        for client in self.clients.values():
            try:
                await client.__aexit__(None, None, None)
            except:
                pass
        await self.collector.cleanup()
        print("[OK] クリーンアップ完了")

async def main():
    """メイン処理"""
    print("🚀 MCP + LLM 統合テストシステム (V2 - mcpServers形式対応)")
    print("前編で作成した設定ファイルを使用します")
    
    # OpenAI APIキーの確認
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY 環境変数が設定されていません")
        print("   .env ファイルに OPENAI_API_KEY=your_key_here を追加してください")
        return
    
    tester = IntegrationTesterV2()
    
    # テスト用のクエリ
    test_queries = [
        "10と20を足して",
        "東京の天気を教えて",
        "円周率の2乗を計算して",
        "大阪の気温を知りたい"
    ]
    
    try:
        # セットアップ
        await tester.setup()
        
        # 統合テストの実行
        await tester.run_integration_test(test_queries)
        
    except KeyboardInterrupt:
        print("\n[STOP] ユーザーにより中断されました")
    except Exception as e:
        print(f"[FATAL] 予期しないエラー: {e}")
    finally:
        await tester.cleanup()
        print("\n[EXIT] プログラムを終了します")

if __name__ == "__main__":
    asyncio.run(main())