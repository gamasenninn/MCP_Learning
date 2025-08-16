#!/usr/bin/env python3
"""
LLM統合MCPクライアント（完全版）
Step 1-3の成果を統合した実用的な対話型クライアント
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

# Step 1-3のクラスをインポート
from mcp_llm_step1 import ToolCollector
from mcp_llm_step2 import LLMIntegrationPrep

load_dotenv()

class CompleteLLMClient:
    """完全なLLM統合MCPクライアント"""
    
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
        
        # MCPクライアントを接続
        for server_name, server_info in self.collector.servers.items():
            try:
                client = Client(server_info["path"])
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
        
        # 結果を文字列に変換
        if hasattr(result, 'content'):
            if isinstance(result.content, list) and result.content:
                first = result.content[0]
                if hasattr(first, 'text'):
                    return first.text
        return str(result)
    
    async def _interpret_result(self, query: str, selection: Dict, result: Any) -> str:
        """ツール実行結果を自然言語で解釈"""
        interpretation_prompt = f"""
ユーザーの質問: {query}
実行したツール: {selection['server']}.{selection['tool']}
引数: {selection['arguments']}
結果: {result}

この結果を基に、ユーザーの質問に対して分かりやすく日本語で回答してください。
数値は適切にフォーマットし、技術的な詳細は必要最小限にしてください。
"""
        
        response = await self.llm.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "あなたは親切なアシスタントです。"},
                {"role": "user", "content": interpretation_prompt}
            ],
            temperature=0.7
        )
        
        answer = response.choices[0].message.content
        self.conversation_history.append({"role": "assistant", "content": answer})
        return answer
    
    async def _generate_conversation_response(self, query: str) -> str:
        """通常の会話応答を生成"""
        # 会話履歴を含めて応答
        messages = [
            {"role": "system", "content": "あなたは親切で知識豊富なアシスタントです。"}
        ]
        
        # 最近の会話履歴を追加（最大10件）
        recent_history = self.conversation_history[-10:] if len(self.conversation_history) > 10 else self.conversation_history
        messages.extend(recent_history)
        
        response = await self.llm.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7
        )
        
        answer = response.choices[0].message.content
        self.conversation_history.append({"role": "assistant", "content": answer})
        return answer
    
    async def interactive_session(self):
        """対話型セッション"""
        print("="*60)
        print("[LLM統合MCPクライアント] 対話モード")
        print("="*60)
        print("[ヒント]")
        print("  - 自然な日本語で質問してください")
        print("  - 'help'でヘルプ表示")
        print("  - 'tools'で利用可能なツール一覧")
        print("  - 'history'で会話履歴")
        print("  - 'exit'または'quit'で終了")
        print("-"*60 + "\n")
        
        while True:
            try:
                # プロンプト表示
                user_input = input("You> ").strip()
                
                # 特殊コマンド処理
                if user_input.lower() in ['exit', 'quit', '終了']:
                    print("\n[終了] セッションを終了します")
                    break
                elif user_input.lower() == 'help':
                    self._show_help()
                    continue
                elif user_input.lower() == 'tools':
                    self._show_available_tools()
                    continue
                elif user_input.lower() == 'history':
                    self._show_history()
                    continue
                elif not user_input:
                    continue
                
                # クエリを処理
                print("\n" + "="*40, flush=True)
                response = await self.process_query(user_input)
                print("-"*40)
                print(f"\nAssistant> {response}\n", flush=True)
                
            except KeyboardInterrupt:
                print("\n\n[中断] 中断されました")
                break
            except Exception as e:
                print(f"\n[エラー] {e}\n")
    
    def _show_help(self):
        """ヘルプを表示"""
        print("\n[ヘルプ]")
        print("  計算例: '100と250を足して'")
        print("  天気例: '東京の天気を教えて'")
        print("  DB例: 'ユーザー一覧を表示して'")
        print("  会話例: 'MCPについて教えて'")
        print()
    
    def _show_history(self):
        """会話履歴を表示"""
        print("\n[履歴] 会話履歴:")
        if not self.conversation_history:
            print("  （まだ会話がありません）")
        else:
            for i, msg in enumerate(self.conversation_history[-10:], 1):
                role = "You" if msg["role"] == "user" else "AI"
                content = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
                print(f"  {i}. {role}: {content}")
        print()
    
    def show_statistics(self):
        """統計情報を表示"""
        duration = datetime.now() - self.context["session_start"]
        print("\n[統計] セッション統計:")
        print(f"  - セッション時間: {duration}")
        print(f"  - ツール呼び出し: {self.context['tool_calls']}回")
        print(f"  - エラー: {self.context['errors']}回")
        print(f"  - 会話数: {len(self.conversation_history)}件")
    
    async def cleanup(self):
        """クリーンアップ処理"""
        for client in self.clients.values():
            try:
                await client.__aexit__(None, None, None)
            except:
                pass

async def main():
    """メイン処理"""
    # APIキーの確認
    if not os.getenv("OPENAI_API_KEY"):
        print("[エラー] 環境変数 OPENAI_API_KEY を設定してください")
        print("   例: export OPENAI_API_KEY='your-api-key'")
        return
    
    client = CompleteLLMClient()
    
    try:
        # 初期化
        await client.initialize()
        
        # 対話型セッション
        await client.interactive_session()
        
        # 統計表示
        client.show_statistics()
        
    finally:
        await client.cleanup()
        print("\n[終了] ご利用ありがとうございました！")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[終了] プログラムを終了します")
        sys.exit(0)