#!/usr/bin/env python3
"""
簡略化されたLLM統合MCPクライアント
MCPサーバーのスキーマを活用した自然言語インターフェース
"""

import asyncio
import json
import os
from typing import Dict, List, Any, Optional
from fastmcp import Client
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

class SimpleLLMClient:
    """LLM統合MCPクライアント（簡略版）"""
    
    def __init__(self, config_file: str = "mcp_servers.json"):
        self.servers = {}
        self.clients = {}
        self.tools_schema = {}
        self.load_config(config_file)
        self.llm = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def load_config(self, config_file: str):
        """設定ファイルを読み込む"""
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        for server_info in config.get("servers", []):
            self.servers[server_info["name"]] = server_info
    
    async def collect_all_tools(self):
        """全サーバーのツール情報を収集"""
        print("🔍 ツール情報を収集中...")
        
        for server_name, server_info in self.servers.items():
            if server_name not in self.clients:
                # サーバーに接続
                client = Client(server_info["path"])
                await client.__aenter__()
                await client.ping()
                self.clients[server_name] = client
            
            # ツール情報を取得
            tools = await self.clients[server_name].list_tools()
            self.tools_schema[server_name] = []
            
            for tool in tools:
                tool_info = {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.input_schema if hasattr(tool, 'input_schema') else {}
                }
                self.tools_schema[server_name].append(tool_info)
            
            print(f"  ✅ {server_name}: {len(tools)}個のツール")
    
    def prepare_tools_for_llm(self) -> str:
        """ツール情報をLLM用に整形"""
        tools_description = []
        
        for server_name, tools in self.tools_schema.items():
            for tool in tools:
                # パラメータの説明を生成
                params = tool.get('parameters', {})
                params_desc = ""
                if params and 'properties' in params:
                    param_list = []
                    for key, value in params['properties'].items():
                        param_type = value.get('type', 'any')
                        required = key in params.get('required', [])
                        req_mark = " (必須)" if required else ""
                        param_list.append(f"    - {key}: {param_type}{req_mark}")
                    if param_list:
                        params_desc = "\n  パラメータ:\n" + "\n".join(param_list)
                
                tool_desc = f"""
{server_name}.{tool['name']}:
  説明: {tool['description']}{params_desc}
"""
                tools_description.append(tool_desc)
        
        return "\n".join(tools_description)
    
    async def select_tool_with_llm(self, query: str) -> Optional[Dict]:
        """LLMを使ってツールと引数を選択"""
        tools_desc = self.prepare_tools_for_llm()
        
        prompt = f"""
ユーザーの要求: {query}

利用可能なツール:
{tools_desc}

最適なツールを選び、必要な引数を決定してください。

重要な注意事項：
- serverには「calculator」「database」「weather」「universal」のいずれかを入れてください
- toolにはツール名のみを入れてください（サーバー名は含めない）
- 例: server: "calculator", tool: "add" （calculator.addではない）

以下のJSON形式で応答してください：

{{
  "server": "サーバー名",
  "tool": "ツール名のみ",
  "arguments": {{引数のキーと値}},
  "reasoning": "なぜこのツールを選んだか"
}}

JSONのみを返してください。
"""
        
        try:
            response = await self.llm.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that selects appropriate tools. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            
            # JSON形式で返ってきた応答をパース
            content = response.choices[0].message.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            
            result = json.loads(content.strip())
            return result
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析エラー: {e}")
            return None
        except Exception as e:
            print(f"❌ エラー: {e}")
            return None
    
    async def execute_tool(self, server_name: str, tool_name: str, arguments: dict):
        """MCPツールを実行"""
        if server_name not in self.clients:
            print(f"❌ サーバー {server_name} が見つかりません")
            print(f"   利用可能なサーバー: {list(self.clients.keys())}")
            return None
        
        try:
            client = self.clients[server_name]
            print(f"   [デバッグ] call_tool({tool_name}, {arguments})")
            result = await client.call_tool(tool_name, arguments)
            
            # 結果を文字列に変換
            if hasattr(result, 'content'):
                if isinstance(result.content, list) and result.content:
                    first = result.content[0]
                    if hasattr(first, 'text'):
                        return first.text
            
            return str(result)
            
        except Exception as e:
            print(f"❌ ツール実行エラー: {e}")
            return None
    
    async def process_query(self, query: str):
        """ユーザーのクエリを処理"""
        print(f"\n👤 ユーザー: {query}")
        
        # ツール情報が未収集の場合は収集
        if not self.tools_schema:
            await self.collect_all_tools()
        
        # LLMにツール選択を依頼
        selection = await self.select_tool_with_llm(query)
        
        if not selection:
            print("🤖 アシスタント: 申し訳ありません。リクエストを理解できませんでした。")
            return
        
        # ツールを実行
        server = selection.get("server")
        tool = selection.get("tool")
        arguments = selection.get("arguments", {})
        reasoning = selection.get("reasoning", "")
        
        # LLMが誤った形式で返した場合の修正
        # ケース1: server.server.tool -> server, tool
        # ケース2: server_name.server.tool -> server, tool
        if tool and '.' in tool:
            parts = tool.split('.')
            # 最後の部分をツール名として使用
            tool = parts[-1]
            # server名も修正が必要な場合
            if '.' in server:
                server_parts = server.split('.')
                # calculator_server -> calculator のような修正
                for known_server in self.servers.keys():
                    if known_server in server_parts[-1] or known_server in server_parts[0]:
                        server = known_server
                        break
        
        # server名に余計な文字が含まれている場合の修正
        if server and server not in self.servers:
            # calculator_server -> calculator のような修正
            for known_server in self.servers.keys():
                if known_server in server or server in known_server:
                    server = known_server
                    break
        
        if reasoning:
            print(f"💭 判断: {reasoning}")
        
        print(f"🔧 実行: {server}.{tool} {arguments}")
        print(f"   [デバッグ] サーバー: {server}, ツール: {tool}")
        
        result = await self.execute_tool(server, tool, arguments)
        
        if result:
            # 結果をLLMに解釈させて回答
            interpretation_prompt = f"""
ユーザーの質問: {query}
実行したツール: {server}.{tool}
結果: {result}

この結果を基に、ユーザーの質問に分かりやすく日本語で回答してください。
数値は適切に丸めて、自然な表現を使ってください。
"""
            
            response = await self.llm.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that interprets tool results for users in Japanese."},
                    {"role": "user", "content": interpretation_prompt}
                ],
                temperature=0.7
            )
            
            print(f"🤖 アシスタント: {response.choices[0].message.content}")
        else:
            print("🤖 アシスタント: ツールの実行に失敗しました。")
    
    async def interactive_session(self):
        """対話型セッション"""
        print("\n" + "="*50)
        print("🤖 LLM統合MCPクライアント（簡略版）")
        print("="*50)
        print("自然言語で質問してください。'exit'で終了します。\n")
        
        # 初回のツール収集
        await self.collect_all_tools()
        
        while True:
            try:
                query = input("\n💬 > ")
                
                if query.lower() in ['exit', 'quit', '終了']:
                    print("👋 終了します")
                    break
                
                if not query.strip():
                    continue
                
                await self.process_query(query)
                
            except KeyboardInterrupt:
                print("\n👋 終了します")
                break
            except Exception as e:
                print(f"❌ エラー: {e}")
    
    async def cleanup(self):
        """クリーンアップ"""
        for client in self.clients.values():
            await client.__aexit__(None, None, None)

async def main():
    # APIキーの確認
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ 環境変数 OPENAI_API_KEY を設定してください")
        return
    
    client = SimpleLLMClient()
    
    try:
        await client.interactive_session()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())