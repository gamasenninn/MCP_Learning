#!/usr/bin/env python3
"""
LLM統合MCPクライアント（完全版 V2 - mcpServers形式対応）
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
from fastmcp.client.transports import StdioTransport

# Step 1-3のV2クラスをインポート
from mcp_llm_step1_v2 import ToolCollectorV2
from mcp_llm_step2_v2 import LLMIntegrationPrepV2

load_dotenv()

class CompleteLLMClientV2:
    """完全なLLM統合MCPクライアント（mcpServers形式対応）"""
    
    def __init__(self):
        # Step 1-3のV2クラスを活用
        self.collector = ToolCollectorV2()
        self.prep = LLMIntegrationPrepV2()
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
        print("[起動] LLM統合MCPクライアント V2 を起動中...", flush=True)
        print("前編で作成したmcpServers形式の設定ファイルを使用します", flush=True)
        
        try:
            # Step 1: 全ツール情報の収集
            await self.collector.collect_all_tools()
            
            # 各サーバーへの永続接続を確立（StdioTransport使用）
            print("[接続] サーバーとの永続接続を確立中...", flush=True)
            for server_name, server_info in self.collector.servers.items():
                transport = StdioTransport(
                    command=server_info["command"],
                    args=server_info["args"]
                )
                client = Client(transport)
                await client.__aenter__()
                self.clients[server_name] = client
                print(f"[OK] {server_name} サーバーに接続しました")
            
            print(f"[完了] 初期化が完了しました（{len(self.clients)}個のサーバーに接続）\n")
            
        except Exception as e:
            print(f"[FATAL] 初期化に失敗: {e}")
            raise
    
    async def process_user_input(self, user_input: str) -> Optional[str]:
        """ユーザー入力を処理してツール実行"""
        try:
            # Step 2: LLMによるツール選択
            tools_desc = self.prep.prepare_tools_for_llm(self.collector.tools_schema)
            prompt = self.prep.create_tool_selection_prompt(user_input, tools_desc)
            
            # LLMに問い合わせ
            response = await self.llm.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "あなたは正確なJSON形式でツール選択を行うアシスタントです。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            
            # 応答を検証
            validation = self.prep.validate_llm_response(response.choices[0].message.content)
            
            if not validation["valid"]:
                print(f"[ERROR] LLM応答の検証に失敗: {validation['error']}")
                return f"申し訳ありません。要求を理解できませんでした: {validation['error']}"
            
            # ツール実行
            result = await self.execute_tool(
                validation["server_name"],
                validation["tool_name"], 
                validation["parameters"],
                validation["reasoning"]
            )
            
            if result is not None:
                self.context["tool_calls"] += 1
                # 会話履歴に追加
                self.conversation_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "user_input": user_input,
                    "selected_tool": f"{validation['server_name']}.{validation['tool_name']}",
                    "parameters": validation["parameters"],
                    "reasoning": validation["reasoning"],
                    "result": str(result)[:200]  # 結果は200文字まで
                })
                return str(result)
            else:
                self.context["errors"] += 1
                return "ツールの実行に失敗しました。"
                
        except Exception as e:
            self.context["errors"] += 1
            print(f"[ERROR] 処理中にエラー: {e}")
            return f"処理中にエラーが発生しました: {str(e)}"
    
    async def execute_tool(self, server_name: str, tool_name: str, parameters: Dict, reasoning: str) -> Any:
        """選択されたツールを実行"""
        if server_name not in self.clients:
            print(f"[ERROR] サーバー '{server_name}' に接続されていません")
            return None
        
        try:
            client = self.clients[server_name]
            print(f"[実行] {server_name}.{tool_name}")
            print(f"[理由] {reasoning}")
            print(f"[引数] {parameters}")
            
            result = await client.call_tool(tool_name, parameters)
            
            # 結果の抽出（複数の形式に対応）
            if hasattr(result, 'structured_content') and result.structured_content:
                extracted = result.structured_content.get('result', str(result))
            elif hasattr(result, 'content') and result.content:
                if isinstance(result.content, list) and result.content:
                    first_content = result.content[0]
                    extracted = first_content.text if hasattr(first_content, 'text') else str(first_content)
                else:
                    extracted = str(result.content)
            elif hasattr(result, 'data'):
                extracted = result.data
            else:
                extracted = str(result)
            
            print(f"[完了] 実行が完了しました\n")
            return extracted
            
        except Exception as e:
            print(f"[ERROR] ツール実行に失敗: {e}")
            return None
    
    def display_help(self):
        """ヘルプメッセージを表示"""
        print("\n" + "="*60)
        print("🤖 LLM統合MCPクライアント V2 - ヘルプ")
        print("="*60)
        print("このクライアントでは、自然言語でMCPツールを操作できます。")
        print("\n📝 使用例:")
        print("  • '10と20を足して'")
        print("  • '東京の天気を教えて'") 
        print("  • '円周率の3乗を計算して'")
        print("  • 'コードを実行: print(\"Hello World\")'")
        print("\n🔧 特殊コマンド:")
        print("  • help または ? - このヘルプを表示")
        print("  • status - セッション情報を表示")
        print("  • history - 実行履歴を表示")
        print("  • servers - 利用可能なサーバー一覧")
        print("  • quit または exit - プログラム終了")
        print("="*60)
    
    def display_status(self):
        """セッション情報を表示"""
        duration = datetime.now() - self.context["session_start"]
        print(f"\n📊 セッション情報:")
        print(f"  起動時間: {self.context['session_start'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  経過時間: {str(duration).split('.')[0]}")
        print(f"  接続サーバー数: {len(self.clients)}")
        print(f"  ツール実行回数: {self.context['tool_calls']}")
        print(f"  エラー回数: {self.context['errors']}")
    
    def display_history(self):
        """実行履歴を表示"""
        if not self.conversation_history:
            print("\n📋 実行履歴はありません")
            return
        
        print(f"\n📋 実行履歴（最新{min(len(self.conversation_history), 5)}件）:")
        for i, record in enumerate(self.conversation_history[-5:], 1):
            timestamp = datetime.fromisoformat(record["timestamp"]).strftime('%H:%M:%S')
            print(f"\n{i}. [{timestamp}] {record['user_input']}")
            print(f"   → {record['selected_tool']} {record['parameters']}")
            print(f"   → {record['result']}")
    
    def display_servers(self):
        """利用可能なサーバー一覧を表示"""
        print(f"\n🔧 利用可能なサーバー ({len(self.collector.servers)}個):")
        for name, info in self.collector.servers.items():
            status = "🟢 接続中" if name in self.clients else "🔴 未接続"
            tools_count = len(self.collector.tools_schema.get(name, []))
            print(f"  • {name} - {info['description']} ({info['chapter']}) {status}")
            print(f"    ツール数: {tools_count}個")
    
    async def run_interactive_session(self):
        """対話型セッションを実行"""
        print("\n🌟 LLM統合MCPクライアント V2 へようこそ！")
        print("自然言語でMCPツールを操作できます。")
        print("'help'でヘルプを表示、'quit'で終了します。\n")
        
        while True:
            try:
                user_input = input("💬 あなた: ").strip()
                
                if not user_input:
                    continue
                
                # 特殊コマンドの処理
                if user_input.lower() in ['quit', 'exit']:
                    print("\n👋 お疲れさまでした！")
                    break
                elif user_input.lower() in ['help', '?']:
                    self.display_help()
                    continue
                elif user_input.lower() == 'status':
                    self.display_status()
                    continue
                elif user_input.lower() == 'history':
                    self.display_history()
                    continue
                elif user_input.lower() == 'servers':
                    self.display_servers()
                    continue
                
                # ユーザー入力を処理
                print("🤔 考え中...", flush=True)
                result = await self.process_user_input(user_input)
                print(f"🤖 アシスタント: {result}\n")
                
            except KeyboardInterrupt:
                print("\n\n[STOP] Ctrl+Cが押されました。'quit'で正常終了してください。")
                continue
            except EOFError:
                print("\n👋 お疲れさまでした！")
                break
            except Exception as e:
                print(f"[ERROR] 予期しないエラー: {e}")
    
    async def cleanup(self):
        """リソースのクリーンアップ"""
        print("[終了] リソースをクリーンアップ中...", flush=True)
        for client in self.clients.values():
            try:
                await client.__aexit__(None, None, None)
            except:
                pass
        await self.collector.cleanup()
        print("[OK] クリーンアップ完了")

async def main():
    """メイン処理"""
    print("🚀 LLM統合MCPクライアント V2 (mcpServers形式対応)")
    print("前編と同じ設定ファイルを使用して、自然言語でMCPツールを操作")
    
    # 環境変数の確認
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY 環境変数が設定されていません")
        print("   .env ファイルに OPENAI_API_KEY=your_key_here を追加してください")
        return
    
    client = CompleteLLMClientV2()
    
    try:
        # 初期化
        await client.initialize()
        
        # 対話型セッション開始
        await client.run_interactive_session()
        
    except KeyboardInterrupt:
        print("\n[STOP] プログラムが中断されました")
    except Exception as e:
        print(f"[FATAL] 致命的エラー: {e}")
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())