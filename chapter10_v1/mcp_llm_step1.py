"""
Step 1: ツール情報の収集と整理 (V3 - 元コード保持版)

元のコードの動作を完全に保持し、mcp_servers.json形式対応のみ実施
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, List, Any
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

class ToolCollector:
    """MCPサーバーのツール情報を収集するクラス（元のコード保持版）"""
    
    def __init__(self, config_file: str = "mcp_servers.json"):
        self.servers = {}
        self.clients = {}
        self.tools_schema = {}
        self.load_config(config_file)
    
    def load_config(self, config_file: str):
        """設定ファイルを読み込む（mcpServers形式対応）"""
        config_path = Path(config_file)
        if not config_path.exists():
            print(f"[WARNING] 設定ファイル {config_file} が見つかりません")
            # デフォルト設定を使用（元の形式を維持）
            self.servers = {
                "calculator": {
                    "name": "calculator",
                    "path": ["uv", "run", "--directory", r"C:\MCP_Learning\chapter03", "python", "calculator_server.py"]
                },
                "weather": {
                    "name": "weather", 
                    "path": ["uv", "run", "--directory", r"C:\MCP_Learning\chapter07", "python", "external_api_server.py"]
                }
            }
            return
            
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # mcpServers形式から従来のpath形式に変換
        if "mcpServers" in config:
            for server_name, server_config in config["mcpServers"].items():
                # commandとargsを結合してpathを作成
                path = [server_config["command"]] + server_config["args"]
                self.servers[server_name] = {
                    "name": server_name,
                    "path": path
                }
        else:
            # 従来形式（servers配列）のサポートも維持
            for server_info in config.get("servers", []):
                self.servers[server_info["name"]] = server_info
    
    async def collect_all_tools(self):
        """全サーバーのツール情報を収集"""
        print("[収集] ツール情報を収集中...", flush=True)
        
        for server_name, server_info in self.servers.items():
            try:
                # StdioTransportを使用してサーバーに接続
                command = server_info["path"][0]
                args = server_info["path"][1:]
                transport = StdioTransport(command=command, args=args)
                client = Client(transport)
                await client.__aenter__()
                await client.ping()
                self.clients[server_name] = client
                
                # ツール情報を取得
                tools = await client.list_tools()
                self.tools_schema[server_name] = []
                
                for tool in tools:
                    # tool.inputSchemaを使用（FastMCPの正しい属性名）
                    tool_info = {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": tool.inputSchema if hasattr(tool, 'inputSchema') else {}
                    }
                    self.tools_schema[server_name].append(tool_info)
                
                print(f"  [成功] {server_name}: {len(tools)}個のツールを発見", flush=True)
                
                # 接続を閉じる
                await client.__aexit__(None, None, None)
                
            except Exception as e:
                print(f"  [エラー] {server_name}: {e}", flush=True)
    
    def display_tools(self):
        """収集したツール情報を表示（Windowsエンコーディング対応）"""
        for server_name, tools in self.tools_schema.items():
            print(f"\n[{server_name}] サーバーのツール:")
            for tool in tools:
                try:
                    # エンコーディング問題を回避するため、安全な表示
                    tool_name = tool.get('name', 'unknown')
                    print(f"  - {tool_name}: [ツール説明は正常に読み込まれました]")
                    
                    # パラメータ情報も表示（簡略化）
                    params = tool.get('parameters', {})
                    if params and 'properties' in params:
                        param_count = len(params['properties'])
                        print(f"    パラメータ: {param_count}個")
                except Exception as e:
                    print(f"  - [表示エラー]: {e}")

async def main():
    """メイン処理"""
    collector = ToolCollector()
    
    # ツール情報を収集
    await collector.collect_all_tools()
    
    # 収集した情報を表示
    collector.display_tools()
    
    # 統計情報
    total_tools = sum(len(tools) for tools in collector.tools_schema.values())
    print(f"\n[統計]")
    print(f"  サーバー数: {len(collector.servers)}")
    print(f"  総ツール数: {total_tools}")

if __name__ == "__main__":
    asyncio.run(main())
