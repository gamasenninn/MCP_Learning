#!/usr/bin/env python3
"""
FastMCPを使った対話型マルチサーバークライアント
複数のサーバーを統合管理
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Optional
from fastmcp import Client
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt

console = Console()

def extract_text(result):
    """結果からテキストを抽出"""
    sc = getattr(result, "structured_content", None)
    if isinstance(sc, dict) and "result" in sc:
        return str(sc["result"])
    content = getattr(result, "content", None)
    if isinstance(content, list) and content:
        first = content[0]
        txt = getattr(first, "text", None)
        if isinstance(txt, str):
            return txt
    data = getattr(result, "data", None)
    if data is not None:
        return str(data)
    return str(result)

class MultiServerClient:
    """複数のMCPサーバーを管理するクライアント"""
    
    def __init__(self, config_file: str = "mcp_servers.json"):
        self.servers = {}
        self.clients = {}
        self.config_file = config_file
        self.history = []
        self.load_config()
    
    def load_config(self):
        """設定ファイルを読み込む"""
        config_path = Path(self.config_file)
        if not config_path.exists():
            console.print(f"[red]設定ファイルが見つかりません: {self.config_file}[/red]")
            return
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        for server_info in config.get("servers", []):
            self.servers[server_info["name"]] = server_info
    
    async def connect_server(self, name: str):
        """サーバーに接続"""
        if name not in self.servers:
            console.print(f"[red]サーバー '{name}' が見つかりません[/red]")
            return False
        
        if name in self.clients:
            console.print(f"[yellow]既に接続済み: {name}[/yellow]")
            return True
        
        server_info = self.servers[name]
        console.print(f"[cyan]🔌 {name} に接続中... ({server_info['chapter']})[/cyan]")
        
        try:
            # FastMCPクライアントを作成
            client = Client(server_info["path"])
            await client.__aenter__()
            await client.ping()
            
            self.clients[name] = client
            
            # ツール一覧を取得
            tools = await client.list_tools()
            console.print(f"[green]✅ {name} に接続しました（{len(tools)}個のツール）[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]❌ 接続エラー: {e}[/red]")
            return False
    
    async def disconnect_server(self, name: str):
        """サーバーから切断"""
        if name in self.clients:
            await self.clients[name].__aexit__(None, None, None)
            del self.clients[name]
            console.print(f"[yellow]👋 {name} から切断しました[/yellow]")
    
    async def call_tool(self, server_name: str, tool_name: str, arguments: dict):
        """ツールを呼び出す"""
        if server_name not in self.clients:
            # 自動接続
            if not await self.connect_server(server_name):
                return None
        
        client = self.clients[server_name]
        console.print(f"[dim]🚀 {server_name}.{tool_name} を実行中...[/dim]")
        
        try:
            result = await client.call_tool(tool_name, arguments)
            result_text = extract_text(result)
            
            # 履歴に追加
            self.history.append({
                "server": server_name,
                "tool": tool_name,
                "arguments": arguments,
                "result": result_text
            })
            
            return result_text
        except Exception as e:
            console.print(f"[red]エラー: {e}[/red]")
            return None
    
    def show_status(self):
        """接続状態を表示"""
        table = Table(title="MCPサーバー接続状態")
        table.add_column("サーバー", style="cyan")
        table.add_column("状態", style="green")
        table.add_column("説明")
        table.add_column("作成章")
        
        for name, info in self.servers.items():
            status = "🟢 接続中" if name in self.clients else "⭕ 未接続"
            table.add_row(name, status, info["description"], info["chapter"])
        
        console.print(table)
    
    async def show_tools(self, server_name: str):
        """ツール一覧を表示"""
        if server_name not in self.clients:
            console.print(f"[yellow]{server_name} は未接続です[/yellow]")
            return
        
        # 非同期でツール一覧を取得
        client = self.clients[server_name]
        tools = await client.list_tools()
        
        table = Table(title=f"{server_name} のツール")
        table.add_column("ツール名", style="cyan")
        table.add_column("説明")
        
        for tool in tools:
            table.add_row(tool.name, tool.description or "")
        
        console.print(table)
    
    def show_history(self, limit: int = 10):
        """実行履歴を表示"""
        if not self.history:
            console.print("[dim]実行履歴はありません[/dim]")
            return
        
        console.print(f"\n[bold]直近の実行履歴（最新{limit}件）:[/bold]")
        
        for i, entry in enumerate(self.history[-limit:], 1):
            console.print(f"\n[cyan]{i}. {entry['server']}.{entry['tool']}[/cyan]")
            console.print(f"   引数: {entry['arguments']}")
            result = entry['result']
            if result and len(str(result)) > 100:
                result = str(result)[:100] + "..."
            console.print(f"   結果: {result}")
    
    async def demo_workflow(self):
        """デモ: 複数サーバーの連携"""
        console.print(Panel(
            "[bold]デモ: 複数サーバーの連携[/bold]\n\n"
            "複数のツールを組み合わせて実用的なタスクを実行します",
            title="🎯 統合デモ",
            border_style="green"
        ))
        
        try:
            # 1. 基本的な計算
            console.print("\n[cyan]1. 基本的な計算を実行[/cyan]")
            result1 = await self.call_tool("calculator", "multiply", {"a": 15, "b": 8})
            console.print(f"   15 × 8 = {result1}")
            
            result2 = await self.call_tool("calculator", "power", {"a": 2, "b": 10})
            console.print(f"   2の10乗 = {result2}")
            
            # 2. 簡単なPythonコードを実行
            console.print("\n[cyan]2. Pythonで簡単な処理を実行[/cyan]")
            simple_code = """
for i in range(1, 6):
    print(f"Count: {i}")
print("Done!")
"""
            python_result = await self.call_tool("universal", "execute_python", {"code": simple_code})
            console.print(f"   実行結果:\n   {python_result}")
            
            # 3. 東京の現在の天気を確認
            console.print("\n[cyan]3. 東京の現在の天気を確認[/cyan]")
            weather_result = await self.call_tool("weather", "get_weather", {"city": "Tokyo"})
            # 結果を整形して表示
            weather_text = extract_text(weather_result)
            if weather_text:
                console.print(f"   天気情報: {weather_text[:200]}")
            
            console.print("\n[green]✨ デモ完了！3つのサーバーを連携できました[/green]")
            console.print("[dim]計算→コード実行→情報取得という実用的なワークフローを実行しました[/dim]")
            
        except Exception as e:
            console.print(f"[red]デモ中にエラーが発生しました: {e}[/red]")
    
    async def interactive_session(self):
        """対話型セッション"""
        console.print(Panel(
            "[bold]FastMCP対話型クライアント[/bold]\n\n"
            "コマンド:\n"
            "  connect <server>  - サーバーに接続\n"
            "  call <server>.<tool> <args...> - ツールを呼び出す\n"
            "  status - 接続状態を表示\n"
            "  tools <server> - ツール一覧を表示\n"
            "  history - 実行履歴を表示\n"
            "  demo - 統合デモを実行\n"
            "  exit - 終了",
            title="🎮 Interactive MCP Client",
            border_style="blue"
        ))
        
        while True:
            try:
                command = Prompt.ask("\n[bold cyan]mcp>[/bold cyan]")
                
                if not command.strip():
                    continue
                
                parts = command.split()
                cmd = parts[0].lower()
                
                if cmd == "exit":
                    break
                
                elif cmd == "connect" and len(parts) > 1:
                    await self.connect_server(parts[1])
                
                elif cmd == "call" and len(parts) >= 2:
                    # call server.tool arg1=value1 arg2=value2
                    target = parts[1]
                    if "." not in target:
                        console.print("[red]形式: call <server>.<tool> [args...][/red]")
                        continue
                    
                    server_name, tool_name = target.split(".", 1)
                    
                    # 引数をパース
                    arguments = {}
                    for arg in parts[2:]:
                        if "=" in arg:
                            key, value = arg.split("=", 1)
                            # 数値に変換を試みる
                            try:
                                value = float(value)
                                if value.is_integer():
                                    value = int(value)
                            except ValueError:
                                pass
                            arguments[key] = value
                    
                    result = await self.call_tool(server_name, tool_name, arguments)
                    if result:
                        console.print(f"[green]結果: {result}[/green]")
                
                elif cmd == "status":
                    self.show_status()
                
                elif cmd == "tools" and len(parts) > 1:
                    await self.show_tools(parts[1])
                
                elif cmd == "history":
                    self.show_history()
                
                elif cmd == "demo":
                    await self.demo_workflow()
                
                else:
                    console.print(f"[yellow]不明なコマンド: {cmd}[/yellow]")
                
            except KeyboardInterrupt:
                console.print("\n[yellow]終了するには 'exit' と入力してください[/yellow]")
            except Exception as e:
                console.print(f"[red]エラー: {e}[/red]")
    
    async def cleanup(self):
        """すべてのサーバーから切断"""
        for name in list(self.clients.keys()):
            await self.disconnect_server(name)

async def main():
    client = MultiServerClient()
    
    try:
        await client.interactive_session()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())