#!/usr/bin/env python3
"""
Simplified MCP Connection Manager for V3 Agent
MCPサーバーへの接続とツール情報管理（簡素版）

V3での変更点：
- 学習機能を削除
- ツール情報の詳細収集を簡素化
- 純粋な接続管理に特化
"""

import asyncio
import json
import os
import sys
from typing import Dict, List, Any, Optional
from pathlib import Path
from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from utils import setup_windows_encoding

# Windows環境設定
setup_windows_encoding()

load_dotenv()

class ConnectionManager:
    """
    MCPサーバーへの接続を管理するシンプルなマネージャー（V3版）
    
    学習機能や複雑な情報収集を削除し、純粋な接続管理に特化
    """
    
    def __init__(self, config_file: str = "mcp_servers.json", verbose: bool = True):
        """
        Args:
            config_file: MCPサーバー設定ファイルのパス
            verbose: 詳細ログ出力
        """
        self.config_file = config_file
        self.verbose = verbose
        
        # 接続管理用のデータ構造
        self.servers: Dict[str, Dict] = {}      # サーバー設定情報
        self.clients: Dict[str, Client] = {}    # 接続済みクライアント
        self.tools_info: Dict[str, Dict] = {}   # ツール名 -> {server, schema}
        
        self._initialized = False
        self._load_config()
    
    def _load_config(self):
        """設定ファイルを読み込み（mcpServers形式対応）"""
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"設定ファイルが見つかりません: {self.config_file}")
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # mcpServers形式から変換
        if "mcpServers" in config:
            for server_name, server_config in config["mcpServers"].items():
                path = [server_config["command"]] + server_config["args"]
                self.servers[server_name] = {
                    "name": server_name,
                    "path": path
                }
        else:
            # 従来形式のサポート
            for server_info in config.get("servers", []):
                self.servers[server_info["name"]] = server_info
    
    async def initialize(self):
        """全サーバーに接続してツール情報を収集"""
        if self._initialized:
            if self.verbose:
                print("[接続管理] 既に初期化済みです")
            return
        
        if self.verbose:
            print("=" * 50)
            print(" MCP Connection Manager V3")
            print("=" * 50)
            print(f"[設定] {len(self.servers)}個のサーバーを検出")
        
        # 各サーバーに接続
        await self._connect_all_servers()
        
        # ツール情報を収集
        await self._collect_tools_info()
        
        self._initialized = True
        
        if self.verbose:
            print(f"\n[初期化完了]")
            print(f"  接続サーバー: {len(self.clients)}個")
            print(f"  利用可能ツール: {len(self.tools_info)}個")
            print("=" * 50)
    
    async def _connect_all_servers(self):
        """全サーバーに接続"""
        if self.verbose:
            print("\n[接続] MCPサーバーに接続中...")
        
        for server_name, server_info in self.servers.items():
            try:
                if self.verbose:
                    print(f"  {server_name}に接続中...", end="")
                
                # StdioTransportを使用してクライアントを作成
                command = server_info["path"][0]
                args = server_info["path"][1:]
                transport = StdioTransport(command=command, args=args)
                client = Client(transport)
                await client.__aenter__()
                self.clients[server_name] = client
                
                if self.verbose:
                    print(" OK")
                    
            except Exception as e:
                if self.verbose:
                    print(f" 失敗: {e}")
                continue
    
    async def _collect_tools_info(self):
        """接続済みサーバーからツール情報を収集（簡素版）"""
        if self.verbose:
            print("\n[収集] ツール情報を収集中...")
        
        for server_name, client in self.clients.items():
            try:
                # ツールリストを取得
                tools = await client.list_tools()
                tool_count = 0
                
                for tool in tools:
                    tool_name = tool.name
                    
                    # ツール情報を保存（必要最小限）
                    self.tools_info[tool_name] = {
                        "server": server_name,
                        "schema": tool.inputSchema if hasattr(tool, 'inputSchema') else {},
                        "description": tool.description if hasattr(tool, 'description') else ""
                    }
                    tool_count += 1
                
                if self.verbose:
                    print(f"  [{server_name}] {tool_count}個のツールを発見")
                    
            except Exception as e:
                if self.verbose:
                    print(f"  [{server_name}] ツール情報取得失敗: {e}")
                continue
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        指定されたツールを実行
        
        Args:
            tool_name: 実行するツール名
            arguments: ツールに渡す引数
        
        Returns:
            ツールの実行結果
        """
        if tool_name not in self.tools_info:
            raise ValueError(f"未知のツール: {tool_name}")
        
        server_name = self.tools_info[tool_name]["server"]
        
        if server_name not in self.clients:
            raise ValueError(f"サーバー '{server_name}' に接続されていません")
        
        client = self.clients[server_name]
        
        try:
            # ツール実行
            result = await client.call_tool(tool_name, arguments)
            
            # FastMCP CallToolResult オブジェクトの内容をサロゲート文字クリーンアップ
            if hasattr(result, 'content') and hasattr(result.content, '__iter__'):
                for content_item in result.content:
                    if hasattr(content_item, 'text') and isinstance(content_item.text, str):
                        # サロゲート文字をクリーンアップ
                        surrogate_count = sum(1 for char in content_item.text if 0xD800 <= ord(char) <= 0xDFFF)
                        if surrogate_count > 0:
                            clean_text = ''.join(
                                char if not (0xD800 <= ord(char) <= 0xDFFF) else '?'
                                for char in content_item.text
                            )
                            content_item.text = clean_text
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            # エラーメッセージも同様に処理（絵文字のみ置換）
            if sys.platform == "win32":
                try:
                    error_msg.encode('cp932')
                except UnicodeEncodeError:
                    # エンコードできない文字のみ置換
                    safe_msg = []
                    for char in error_msg:
                        try:
                            char.encode('cp932')
                            safe_msg.append(char)
                        except UnicodeEncodeError:
                            safe_msg.append('?')
                    error_msg = ''.join(safe_msg)
            raise RuntimeError(f"ツール実行エラー ({tool_name}): {error_msg}")
    
    def get_available_tools(self) -> List[str]:
        """利用可能なツール一覧を取得"""
        return list(self.tools_info.keys())
    
    def get_tool_info(self, tool_name: str) -> Optional[Dict]:
        """指定されたツールの情報を取得"""
        return self.tools_info.get(tool_name)
    
    def get_tools_by_server(self, server_name: str) -> List[str]:
        """指定されたサーバーのツール一覧を取得"""
        return [tool_name for tool_name, info in self.tools_info.items() 
                if info["server"] == server_name]
    
    def format_tools_for_llm(self) -> str:
        """LLM用にツール情報をフォーマット"""
        formatted = []
        
        for tool_name, info in self.tools_info.items():
            server = info["server"]
            description = info["description"]
            
            # パラメータ情報を簡潔に記述
            schema = info.get("schema", {})
            properties = schema.get("properties", {})
            required = schema.get("required", [])
            
            params_info = []
            for param_name, param_info in properties.items():
                param_type = param_info.get("type", "any")
                is_required = param_name in required
                req_text = "必須" if is_required else "オプション"
                param_desc = param_info.get("description", "")
                params_info.append(f"  - {param_name} ({param_type}, {req_text}): {param_desc}")
            
            params_text = "\n".join(params_info) if params_info else "  パラメータなし"
            
            formatted.append(f"""
{tool_name} (サーバー: {server}):
  説明: {description}
  パラメータ:
{params_text}
""".strip())
        
        return "\n\n".join(formatted)
    
    async def close(self):
        """全ての接続を閉じる"""
        for server_name, client in self.clients.items():
            try:
                await client.__aexit__(None, None, None)
            except Exception as e:
                if self.verbose:
                    print(f"[警告] {server_name}の切断エラー: {e}")
        
        self.clients.clear()
        self._initialized = False