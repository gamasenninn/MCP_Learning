#!/usr/bin/env python3
"""
MCPConnectionManager - MCP接続管理層
全てのMCPサーバーへの接続とツール情報を一元管理
"""

import asyncio
import json
import os
import sys
from typing import Dict, List, Any, Optional
from pathlib import Path
from dotenv import load_dotenv

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

load_dotenv()

# MCPクライアントをインポート
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir / "chapter09"))

try:
    from mcp_client_minimal import Client
except ImportError:
    # フォールバック: 同じディレクトリから試す
    try:
        from mcp_client import Client
    except ImportError:
        # 最終フォールバック
        from mcp_llm_step1 import Client

class MCPConnectionManager:
    """
    MCPサーバーへの接続を一元管理するマネージャー
    
    このクラスが全てのサーバー接続とツール情報を管理することで、
    上位層は接続の詳細を意識せずに済む
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
        self.tools_map: Dict[str, str] = {}     # ツール名 -> サーバー名
        self.tools_by_server: Dict[str, List] = {}  # サーバー名 -> ツールリスト
        
        self._initialized = False
        self._load_config()
    
    def _load_config(self):
        """設定ファイルを読み込み"""
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"設定ファイルが見つかりません: {self.config_file}")
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # サーバー情報を整理
        for server_info in config.get("servers", []):
            self.servers[server_info["name"]] = server_info
    
    async def initialize(self):
        """
        全サーバーに接続してツール情報を収集
        
        この処理は一度だけ実行され、以降は_initializedフラグで制御
        """
        if self._initialized:
            if self.verbose:
                print("[接続管理] 既に初期化済みです")
            return
        
        if self.verbose:
            print("\n" + "=" * 70)
            print(" MCP接続管理層 - 初期化")
            print("=" * 70)
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
            print("=" * 70)
    
    async def _connect_all_servers(self):
        """全サーバーに接続"""
        if self.verbose:
            print("\n[接続] MCPサーバーに接続中...")
        
        for server_name, server_info in self.servers.items():
            try:
                if self.verbose:
                    print(f"  {server_name}に接続中...", end="")
                
                # クライアントを作成して接続
                client = Client(server_info["path"])
                await client.__aenter__()
                self.clients[server_name] = client
                
                if self.verbose:
                    print(" OK")
                    
            except Exception as e:
                if self.verbose:
                    print(f" 失敗: {e}")
                # 接続失敗しても続行（一部のサーバーが利用不可でも動作）
                continue
    
    async def _collect_tools_info(self):
        """接続済みサーバーからツール情報を収集"""
        if self.verbose:
            print("\n[収集] ツール情報を収集中...")
        
        for server_name, client in self.clients.items():
            try:
                # ツールリストを取得
                tools = await client.list_tools()
                tool_count = 0
                server_tools = []
                
                for tool in tools:
                    tool_name = tool.name
                    
                    # ツール情報を保存
                    self.tools_info[tool_name] = {
                        "server": server_name,
                        "schema": {
                            "name": tool_name,
                            "description": tool.description or "",
                            "inputSchema": tool.inputSchema if hasattr(tool, 'inputSchema') else {}
                        }
                    }
                    
                    # マッピングを保存
                    self.tools_map[tool_name] = server_name
                    server_tools.append(tool_name)
                    tool_count += 1
                
                self.tools_by_server[server_name] = server_tools
                
                if self.verbose:
                    print(f"  [{server_name}] {tool_count}個のツールを発見")
                    
            except Exception as e:
                if self.verbose:
                    print(f"  [{server_name}] ツール取得エラー: {e}")
                continue
    
    async def execute_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """
        ツールを実行
        
        Args:
            tool_name: 実行するツール名
            params: ツールのパラメータ
            
        Returns:
            実行結果
            
        Raises:
            ValueError: ツールが見つからない場合
            Exception: 実行エラー
        """
        if tool_name not in self.tools_map:
            raise ValueError(f"ツール '{tool_name}' が見つかりません")
        
        server_name = self.tools_map[tool_name]
        
        if server_name not in self.clients:
            raise Exception(f"サーバー '{server_name}' に接続されていません")
        
        client = self.clients[server_name]
        
        try:
            result = await client.call_tool(tool_name, params)
            return result
        except Exception as e:
            raise Exception(f"ツール実行エラー: {e}")
    
    def get_tool_info(self, tool_name: str) -> Optional[Dict]:
        """
        ツールの詳細情報を取得
        
        Args:
            tool_name: ツール名
            
        Returns:
            ツール情報の辞書、見つからない場合はNone
        """
        return self.tools_info.get(tool_name)
    
    def get_server_tools(self, server_name: str) -> List[str]:
        """
        特定サーバーのツールリストを取得
        
        Args:
            server_name: サーバー名
            
        Returns:
            ツール名のリスト
        """
        return self.tools_by_server.get(server_name, [])
    
    def get_all_tools_schema(self) -> Dict[str, List[Dict]]:
        """
        全サーバーのツールスキーマを取得（後方互換性のため）
        
        Returns:
            {server_name: [tool_schemas]} の辞書
        """
        result = {}
        for server_name in self.servers.keys():
            result[server_name] = []
            for tool_name in self.tools_by_server.get(server_name, []):
                if tool_name in self.tools_info:
                    result[server_name].append(self.tools_info[tool_name]["schema"])
        return result
    
    async def cleanup(self):
        """全接続をクリーンアップ"""
        if self.verbose:
            print("\n[クリーンアップ] 接続を閉じています...")
        
        for server_name, client in self.clients.items():
            try:
                await client.__aexit__(None, None, None)
                if self.verbose:
                    print(f"  {server_name}: 切断")
            except Exception as e:
                if self.verbose:
                    print(f"  {server_name}: クリーンアップエラー: {e}")
        
        self.clients.clear()
        self._initialized = False
    
    def __str__(self) -> str:
        """接続状態の文字列表現"""
        return (
            f"MCPConnectionManager("
            f"servers={len(self.servers)}, "
            f"connected={len(self.clients)}, "
            f"tools={len(self.tools_info)})"
        )
    
    def __repr__(self) -> str:
        return self.__str__()


# テスト関数
async def test_connection_manager():
    """MCPConnectionManagerのテスト"""
    
    print("MCPConnectionManagerのテスト")
    print("=" * 60)
    
    # マネージャーの作成と初期化
    manager = MCPConnectionManager(verbose=True)
    await manager.initialize()
    
    # 接続状態の確認
    print(f"\n{manager}")
    
    # ツール情報の表示
    print("\n[利用可能なツール]")
    for tool_name, info in list(manager.tools_info.items())[:5]:  # 最初の5個
        print(f"  - {tool_name} (サーバー: {info['server']})")
        print(f"    {info['schema'].get('description', 'No description')[:50]}...")
    
    # ツール実行のテスト
    if "add" in manager.tools_map:
        print("\n[ツール実行テスト]")
        result = await manager.execute_tool("add", {"a": 100, "b": 200})
        print(f"  add(100, 200) = {result}")
    
    # クリーンアップ
    await manager.cleanup()
    
    print("\n" + "=" * 60)
    print("テスト完了")


if __name__ == "__main__":
    asyncio.run(test_connection_manager())