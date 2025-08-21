"""
Step 1: ツール情報の収集と整理 (V2 - mcpServers形式対応)

前編で作成したmcp_servers.json（mcpServers形式）に対応
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, List, Any
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

class ToolCollectorV2:
    """MCPサーバーのツール情報を収集するクラス（mcpServers形式対応）"""
    
    def __init__(self, config_file: str = "mcp_servers.json"):
        self.servers = {}
        self.clients = {}
        self.tools_schema = {}
        self.load_config(config_file)
    
    def load_config(self, config_file: str):
        """mcpServers形式の設定ファイルを読み込む"""
        config_path = Path(config_file)
        if not config_path.exists():
            print(f"[WARNING] 設定ファイル {config_file} が見つかりません")
            # デフォルト設定（mcpServers形式）
            self.servers = {
                "calculator": {
                    "name": "calculator",
                    "command": "uv",
                    "args": ["--directory", r"C:\MCP_Learning\chapter03", "run", "python", "calculator_server.py"],
                    "description": "基本的な計算機能",
                    "chapter": "第3章"
                },
                "weather": {
                    "name": "weather", 
                    "command": "uv",
                    "args": ["--directory", r"C:\MCP_Learning\chapter07", "run", "python", "external_api_server.py"],
                    "description": "天気情報の取得",
                    "chapter": "第7章"
                }
            }
            return
            
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # mcpServers形式の設定を読み込み
        for server_name, server_config in config.get("mcpServers", {}).items():
            self.servers[server_name] = {
                "name": server_name,
                "command": server_config["command"],
                "args": server_config["args"],
                "description": server_config.get("meta", {}).get("description", ""),
                "chapter": server_config.get("meta", {}).get("chapter", "")
            }
    
    async def collect_all_tools(self):
        """全サーバーのツール情報を収集"""
        print("[収集] ツール情報を収集中...", flush=True)
        
        for server_name, server_info in self.servers.items():
            try:
                # StdioTransportでサーバーに接続
                transport = StdioTransport(
                    command=server_info["command"],
                    args=server_info["args"]
                )
                client = Client(transport)
                await client.__aenter__()
                await client.ping()
                self.clients[server_name] = client
                
                # ツール情報を取得
                tools = await client.list_tools()
                self.tools_schema[server_name] = []
                
                for tool in tools:
                    # tool.inputSchemaを使用（FastMCPの正しい属性名）
                    schema_info = {
                        "name": tool.name,
                        "description": tool.description,
                        "server": server_name,
                        "parameters": {}
                    }
                    
                    # inputSchemaからパラメータ情報を抽出
                    if hasattr(tool, 'inputSchema') and tool.inputSchema:
                        schema = tool.inputSchema
                        if isinstance(schema, dict) and "properties" in schema:
                            for param_name, param_info in schema["properties"].items():
                                schema_info["parameters"][param_name] = {
                                    "type": param_info.get("type", "string"),
                                    "description": param_info.get("description", "")
                                }
                    
                    self.tools_schema[server_name].append(schema_info)
                
                print(f"[OK] {server_name}: {len(tools)}個のツールを収集")
                
            except Exception as e:
                print(f"[ERROR] {server_name} の接続に失敗: {e}")
                self.tools_schema[server_name] = []
    
    def display_collected_info(self):
        """収集した情報を表示"""
        print("\n" + "="*50)
        print("📋 収集されたツール情報")
        print("="*50)
        
        total_tools = 0
        for server_name, tools in self.tools_schema.items():
            if tools:
                print(f"\n🔧 {server_name} サーバー ({self.servers[server_name]['description']})")
                print(f"   章: {self.servers[server_name]['chapter']}")
                for tool in tools:
                    print(f"   - {tool['name']}: {tool['description']}")
                    if tool['parameters']:
                        for param, info in tool['parameters'].items():
                            print(f"     └ {param} ({info['type']}): {info['description']}")
                total_tools += len(tools)
        
        print(f"\n📊 サマリー:")
        print(f"  - サーバー数: {len(self.servers)}")
        print(f"  - 総ツール数: {total_tools}")
    
    async def cleanup(self):
        """クリーンアップ"""
        for client in self.clients.values():
            try:
                await client.__aexit__(None, None, None)
            except:
                pass

async def main():
    """メイン処理"""
    print("🚀 MCP ツール情報収集システム (V2 - mcpServers形式対応)")
    print("前編で作成した設定ファイルを使用します\n")
    
    collector = ToolCollectorV2()
    
    try:
        await collector.collect_all_tools()
        collector.display_collected_info()
        
    except KeyboardInterrupt:
        print("\n[STOP] ユーザーにより中断されました")
    except Exception as e:
        print(f"[FATAL] 予期しないエラー: {e}")
    finally:
        await collector.cleanup()
        print("\n[EXIT] プログラムを終了します")

if __name__ == "__main__":
    asyncio.run(main())