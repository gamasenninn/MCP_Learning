"""
Step 3: 統合テスト (V3 - 元のコード保持版)
Step 1とStep 2を組み合わせた動作確認

※接続部分のみ修正、その他は元のコードと同じ
"""
import asyncio
import os
from typing import List, Dict, Any
from dotenv import load_dotenv
from openai import AsyncOpenAI
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

# Step 1とStep 2のV3クラスをインポート
from mcp_llm_step1_v3 import ToolCollector
from mcp_llm_step2_v3 import LLMIntegrationPrep

load_dotenv()

class IntegrationTester:
    """統合テストクラス"""
    
    def __init__(self):
        self.collector = ToolCollector()
        self.prep = LLMIntegrationPrep()
        self.llm = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.clients = {}
        
    async def setup(self):
        """テスト環境のセットアップ"""
        print("[セットアップ] 統合テストのセットアップ中...")
        
        # Step 1: ツール情報の収集
        await self.collector.collect_all_tools()
        
        # MCPクライアントの接続を維持（StdioTransport対応）
        for server_name, server_info in self.collector.servers.items():
            command = server_info["path"][0]
            args = server_info["path"][1:]
            transport = StdioTransport(command=command, args=args)
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
    
    async def execute_tool(self, server: str, tool: str, arguments: Dict) -> Any:
        """MCPツールの実行"""
        if server not in self.clients:
            raise ValueError(f"サーバー '{server}' が見つかりません")
        
        client = self.clients[server]
        result = await client.call_tool(tool, arguments)
        
        # 結果を文字列に変換
        if hasattr(result, 'content'):
            if isinstance(result.content, list) and result.content:
                first = result.content[0]
                if hasattr(first, 'text'):
                    return first.text
        return str(result)
    
    async def run_test_case(self, test_name: str, query: str):
        """個別のテストケースを実行"""
        print(f"[テスト] {test_name}")
        print(f"   クエリ: {query}")
        
        try:
            # LLMでツール選択
            selection = await self.test_llm_tool_selection(query)
            print(f"   選択: {selection['server']}.{selection['tool']}")
            print(f"   引数: {selection['arguments']}")
            print(f"   理由: {selection.get('reasoning', 'なし')}")
            
            # ツール実行
            result = await self.execute_tool(
                selection['server'],
                selection['tool'],
                selection['arguments']
            )
            print(f"   結果: {result}")
            print(f"   [OK] テスト成功\n")
            
            return {"status": "success", "result": result}
            
        except Exception as e:
            print(f"   [ERROR] {e}\n")
            return {"status": "error", "error": str(e)}
    
    async def cleanup(self):
        """クリーンアップ"""
        for client in self.clients.values():
            await client.__aexit__(None, None, None)

async def main():
    """統合テストのメイン処理"""
    # APIキーの確認
    if not os.getenv("OPENAI_API_KEY"):
        print("[ERROR] 環境変数 OPENAI_API_KEY を設定してください")
        return
    
    tester = IntegrationTester()
    
    try:
        # セットアップ
        await tester.setup()
        
        # テストケースの定義
        test_cases = [
            ("基本的な計算", "100と250を足して"),
            ("複雑な計算", "2の10乗を計算して"),
            ("天気情報", "東京の天気を教えて"),
            ("データベース検索", "ユーザー一覧を表示して"),
            ("エラーケース", "これは処理できないリクエスト")
        ]
        
        # バッチテストの実行
        print("="*50)
        print("🧪 統合テスト開始")
        print("="*50 + "\n")
        
        results = []
        for test_name, query in test_cases:
            result = await tester.run_test_case(test_name, query)
            results.append({
                "test": test_name,
                "query": query,
                **result
            })
        
        # テスト結果のサマリー
        print("="*50)
        print("[サマリー] テスト結果")
        print("="*50)
        
        success_count = sum(1 for r in results if r["status"] == "success")
        total_count = len(results)
        
        print(f"成功: {success_count}/{total_count}")
        print(f"失敗: {total_count - success_count}/{total_count}")
        
        if success_count == total_count:
            print("\n🎉 すべてのテストが成功しました！")
        
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    asyncio.run(main())