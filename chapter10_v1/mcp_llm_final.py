#!/usr/bin/env python3
"""
LLM統合MCPクライアント（完全版 V3 - 元のコード保持版）
Step 1-3の成果を統合した実用的な対話型クライアント

※接続部分のみ修正、その他は元のコードの動作を完全に保持
"""

import asyncio
import os
import sys

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dotenv import load_dotenv
from openai import AsyncOpenAI
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

# Step 1-3のクラスをインポート
from mcp_llm_step1 import ToolCollector
from mcp_llm_step2 import LLMIntegrationPrep

load_dotenv()

class CompleteLLMClient:
    """完全なLLM統合MCPクライアント（元のコード保持版）"""
    
    def __init__(self):
        # Step 1-3のクラスを活用
        self.collector = ToolCollector()
        self.prep = LLMIntegrationPrep()
        self.llm = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # クライアント管理
        self.clients = {}
        
        # 会話履歴とコンテキスト
        self.conversation_history = []
        self.context = {
            "session_start": datetime.now(),
            "tool_calls": 0,
            "errors": 0
        }
        
    async def initialize(self):
        """初期化処理"""
        print("[起動] LLM統合MCPクライアントを起動中...", flush=True)
        
        # Step 1: ツール情報を収集
        await self.collector.collect_all_tools()
        
        # MCPクライアントを接続（StdioTransport対応）
        for server_name, server_info in self.collector.servers.items():
            try:
                command = server_info["path"][0]
                args = server_info["path"][1:]
                transport = StdioTransport(command=command, args=args)
                client = Client(transport)
                await client.__aenter__()
                self.clients[server_name] = client
            except Exception as e:
                print(f"  [WARNING] {server_name}への接続失敗: {e}")
        
        print("[完了] 初期化完了\n", flush=True)
        self._show_available_tools()
    
    def _show_available_tools(self):
        """利用可能なツールを表示"""
        total_tools = sum(len(tools) for tools in self.collector.tools_schema.values())
        print(f"[ツール] 利用可能なツール: {total_tools}個")
        for server_name, tools in self.collector.tools_schema.items():
            print(f"  - {server_name}: {len(tools)}個のツール")
        print()
    
    async def _analyze_query(self, query: str) -> Dict:
        """クエリを分析し、ツール実行の必要性と対応を決定"""
        tools_desc = self.prep.prepare_tools_for_llm(self.collector.tools_schema)
        
        # 最近の会話履歴を取得（最大5件）
        recent_history = ""
        if self.conversation_history:
            recent_messages = self.conversation_history[-5:]
            history_lines = []
            for msg in recent_messages:
                role = "ユーザー" if msg["role"] == "user" else "アシスタント"
                history_lines.append(f"{role}: {msg['content']}")
            recent_history = "\n".join(history_lines)
        
        prompt = f"""
あなたは優秀なアシスタントです。ユーザーの質問を分析し、適切な対応を決定してください。

## これまでの会話
{recent_history if recent_history else "（新しい会話）"}

## 現在のユーザーの質問
{query}

## 利用可能なツール
{tools_desc}

## 判定基準
- 計算、データ取得、外部情報の参照、ツールの実行が必要 → needs_tool: true
- 一般的な知識、説明、会話、意見、アドバイスで答えられる → needs_tool: false
- 重要：これまでの会話の文脈を考慮して応答してください

## 応答形式
以下のJSON形式で必ず応答してください（JSONのみ、説明文は不要）：

needs_tool=trueの場合:
{{
  "needs_tool": true,
  "server": "サーバー名のみ（例: calculator）",
  "tool": "ツール名のみ（例: add）※サーバー名は含めない",
  "arguments": {{パラメータ}},
  "reasoning": "なぜこのツールを選んだか"
}}

needs_tool=falseの場合:
{{
  "needs_tool": false,
  "reasoning": "なぜツールが不要か",
  "response": "ユーザーへの直接回答"
}}

## 重要な注意
- ツール一覧は "サーバー名.ツール名" の形式で表示されていますが
- JSONでは server と tool を別々に指定してください
- 例: "calculator.add" → server: "calculator", tool: "add"
- 例: "weather.get_weather" → server: "weather", tool: "get_weather"
"""
        
        response = await self.llm.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that analyzes queries and determines appropriate actions. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        
        # デバッグ: LLMの生レスポンスを表示
        raw_response = response.choices[0].message.content
        print(f"  [LLM] 生レスポンス（最初の300文字）:", flush=True)
        print(f"  {raw_response[:300]}...", flush=True)
        
        try:
            return self.prep.validate_llm_response(raw_response)
        except Exception as e:
            print(f"  [ERROR] パースエラー: {e}")
            print(f"  [INFO] 完全なレスポンス:")
            print(raw_response)
            raise
    
    async def process_query(self, query: str) -> str:
        """ユーザーのクエリを処理"""
        try:
            # クエリを分析（会話履歴を参照しつつ）
            print("  [分析] クエリを分析中...", flush=True)
            decision = await self._analyze_query(query)
            
            # 分析後に会話履歴に追加
            self.conversation_history.append({"role": "user", "content": query})
            
            # 判断理由を表示
            if decision.get("reasoning"):
                print(f"  [判断] {decision['reasoning']}", flush=True)
            
            if decision.get("needs_tool", False):
                # ツール実行パス
                print(f"  [選択] ツール: {decision['server']}.{decision['tool']}", flush=True)
                print(f"     引数: {decision['arguments']}", flush=True)
                print(f"  [実行] 処理中...", flush=True)
                
                result = await self._execute_tool(
                    decision['server'],
                    decision['tool'],
                    decision['arguments']
                )
                print(f"  [完了] 実行完了", flush=True)
                
                # 結果を解釈
                print("  [解釈] 結果を解釈中...", flush=True)
                return await self._interpret_result(query, decision, result)
            else:
                # 直接応答パス
                print("  [応答] 直接応答モード", flush=True)
                response = decision.get("response", "申し訳ありません。回答を生成できませんでした。")
                self.conversation_history.append({"role": "assistant", "content": response})
                return response
                
        except Exception as e:
            self.context["errors"] += 1
            return f"申し訳ありません。エラーが発生しました: {str(e)}"
    
    async def _execute_tool(self, server: str, tool: str, arguments: Dict) -> Any:
        """MCPツールを実行"""
        if server not in self.clients:
            raise ValueError(f"サーバー '{server}' が見つかりません")
        
        self.context["tool_calls"] += 1
        client = self.clients[server]
        result = await client.call_tool(tool, arguments)
        
        # 結果を適切な形式で取得
        if hasattr(result, 'content'):
            if isinstance(result.content, list) and result.content:
                first = result.content[0]
                if hasattr(first, 'text'):
                    return first.text
        return str(result)
    
    async def _interpret_result(self, query: str, decision: Dict, result: Any) -> str:
        """ツール実行結果をユーザーに分かりやすく解釈"""
        interpretation_prompt = f"""
ユーザーの質問とツール実行結果をもとに、わかりやすい回答を作成してください。

ユーザーの質問: {query}
実行したツール: {decision['server']}.{decision['tool']}
ツールの実行結果: {result}

## 指示
1. ツールの実行結果をユーザーが理解しやすいように説明してください
2. 必要に応じて追加の解釈や説明を加えてください
3. エラーが発生した場合は、可能であればその理由を説明してください
4. 結果が期待と異なる場合は、その旨を伝えてください

## 回答形式
自然で親しみやすい日本語で回答してください（JSON形式は不要）。
"""
        
        response = await self.llm.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that interprets tool results for users in a clear and friendly manner."},
                {"role": "user", "content": interpretation_prompt}
            ],
            temperature=0.3
        )
        
        interpreted_response = response.choices[0].message.content
        self.conversation_history.append({"role": "assistant", "content": interpreted_response})
        
        return interpreted_response
    
    async def interactive_mode(self):
        """対話モードの実行"""
        print("\n" + "="*60)
        print("🤖 LLM統合MCPクライアント V3 - 対話モード")
        print("="*60)
        print("自然言語でMCPツールを操作できます。")
        print("使用例: '10と20を足して', '東京の天気を教えて'")
        print("特殊コマンド: help, status, history, quit")
        print("="*60 + "\n")
        
        while True:
            try:
                user_input = input("💬 あなた: ").strip()
                
                if not user_input:
                    continue
                
                # 特殊コマンドの処理
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("\n👋 お疲れさまでした！")
                    break
                elif user_input.lower() in ['help', '?']:
                    self._show_help()
                    continue
                elif user_input.lower() == 'status':
                    self._show_status()
                    continue
                elif user_input.lower() == 'history':
                    self._show_history()
                    continue
                elif user_input.lower() == 'tools':
                    self._show_available_tools()
                    continue
                
                # 通常のクエリ処理
                print("\n🔍 処理中...")
                response = await self.process_query(user_input)
                print(f"\n🤖 アシスタント: {response}\n")
                
            except KeyboardInterrupt:
                print("\n\n[STOP] ユーザーにより中断されました")
                break
            except Exception as e:
                print(f"\n[ERROR] エラーが発生しました: {e}\n")
    
    def _show_help(self):
        """ヘルプメッセージを表示"""
        print("\n" + "="*50)
        print("📖 ヘルプ")
        print("="*50)
        print("• 自然言語でMCPツールを操作できます")
        print("• 例: '100と250を足して', '東京の天気を教えて'")
        print("\n特殊コマンド:")
        print("  help - このヘルプを表示")
        print("  status - セッション情報を表示")
        print("  history - 会話履歴を表示")
        print("  tools - 利用可能なツールを表示")
        print("  quit - プログラムを終了")
        print("="*50 + "\n")
    
    def _show_status(self):
        """セッション情報を表示"""
        duration = datetime.now() - self.context["session_start"]
        print("\n" + "="*50)
        print("📊 セッション情報")
        print("="*50)
        print(f"起動時間: {self.context['session_start'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"経過時間: {str(duration).split('.')[0]}")
        print(f"接続サーバー数: {len(self.clients)}")
        print(f"ツール実行回数: {self.context['tool_calls']}")
        print(f"エラー回数: {self.context['errors']}")
        print("="*50 + "\n")
    
    def _show_history(self):
        """会話履歴を表示"""
        if not self.conversation_history:
            print("\n📋 会話履歴はありません\n")
            return
        
        print("\n" + "="*50)
        print(f"📋 会話履歴（最新{min(len(self.conversation_history), 10)}件）")
        print("="*50)
        
        for i, msg in enumerate(self.conversation_history[-10:], 1):
            role = "あなた" if msg["role"] == "user" else "アシスタント"
            content = msg["content"][:80] + ("..." if len(msg["content"]) > 80 else "")
            print(f"{i:2d}. {role}: {content}")
        
        print("="*50 + "\n")
    
    async def cleanup(self):
        """クリーンアップ"""
        for client in self.clients.values():
            try:
                await client.__aexit__(None, None, None)
            except:
                pass

async def main():
    """メイン処理"""
    # APIキーの確認
    if not os.getenv("OPENAI_API_KEY"):
        print("[ERROR] 環境変数 OPENAI_API_KEY を設定してください")
        print("例: set OPENAI_API_KEY=your_api_key_here")
        return
    
    client = CompleteLLMClient()
    
    try:
        # 初期化
        await client.initialize()
        
        # 対話モード開始
        await client.interactive_mode()
        
    except KeyboardInterrupt:
        print("\n[STOP] ユーザーにより中断されました")
    except Exception as e:
        print(f"[FATAL] 予期しないエラー: {e}")
    finally:
        await client.cleanup()
        print("[EXIT] プログラムを終了します")

if __name__ == "__main__":
    asyncio.run(main())
