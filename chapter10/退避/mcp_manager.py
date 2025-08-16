"""
MCPマネージャー
MCPサーバーとの通信を管理
"""

import json
import asyncio
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import subprocess
from pathlib import Path
from fastmcp import Client

logger = logging.getLogger(__name__)

@dataclass
class MCPServer:
    """MCPサーバー情報"""
    name: str
    path: str  # サーバーのPythonファイルパス
    client: Optional[Client] = None  # FastMCPクライアント
    tools: List[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "tools": self.tools or []
        }

@dataclass
class ToolCall:
    """ツール呼び出し"""
    server: str
    tool: str
    params: Dict[str, Any]
    
@dataclass
class ToolResult:
    """ツール実行結果"""
    success: bool
    data: Any
    error: Optional[str] = None

class MCPManager:
    """
    MCPサーバーの管理とツール実行
    """
    
    def __init__(self):
        self.servers: Dict[str, MCPServer] = {}
        self.connected_servers: Dict[str, MCPServer] = {}
        self._load_config()
        
    def _load_config(self):
        """設定ファイルからMCPサーバー情報を読み込み"""
        # まず、ローカルのmcp_servers.jsonを確認
        local_config_path = Path(__file__).parent / "mcp_servers.json"
        
        if local_config_path.exists():
            try:
                with open(local_config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                # servers配列を処理
                for server_info in config.get("servers", []):
                    name = server_info["name"]
                    path = server_info["path"]
                    
                    # MCPサーバー情報を保存
                    self.servers[name] = MCPServer(
                        name=name,
                        path=path
                    )
                    
                logger.info(f"[CONFIG] Loaded {len(self.servers)} MCP servers from local config")
            except Exception as e:
                logger.error(f"[ERROR] Failed to load local config: {e}")
        
        # 次に、ユーザーのホームディレクトリの設定を確認
        config_path = Path.home() / ".config" / "mcp" / "servers.json"
        
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                for name, server_config in config.get("servers", {}).items():
                    # ローカル設定にない場合のみ追加
                    if name not in self.servers:
                        # パスが指定されていない場合はスキップ
                        if "path" not in server_config:
                            continue
                        self.servers[name] = MCPServer(
                            name=name,
                            path=server_config["path"]
                        )
                    
                logger.info(f"[CONFIG] Total {len(self.servers)} MCP servers available")
            except Exception as e:
                logger.error(f"[ERROR] Failed to load user config: {e}")
    
    async def connect_server(self, server_name: str) -> bool:
        """
        MCPサーバーに接続（FastMCPクライアントを使用）
        
        Args:
            server_name: サーバー名
            
        Returns:
            接続成功かどうか
        """
        if server_name not in self.servers:
            logger.error(f"[ERROR] Unknown server: {server_name}")
            return False
            
        if server_name in self.connected_servers:
            logger.info(f"[INFO] Already connected to {server_name}")
            return True
        
        server = self.servers[server_name]
        
        try:
            logger.info(f"[CONNECT] Connecting to {server_name}...")
            
            # FastMCPクライアントを作成して接続
            client = Client(server.path)
            await client.__aenter__()
            server.client = client
            
            # 接続確認
            await client.ping()
            
            # ツール一覧を取得（list_toolsの戻り値は直接ツールのリスト）
            try:
                tools = await client.list_tools()
                server.tools = []
                for tool in tools:
                    tool_info = {
                        "name": tool.name,
                        "description": getattr(tool, 'description', '')
                    }
                    # パラメータ情報を追加
                    if hasattr(tool, 'inputSchema'):
                        tool_info["parameters"] = tool.inputSchema
                    server.tools.append(tool_info)
                    
                logger.info(f"[DEBUG] Found tools: {[tool.name for tool in tools]}")
            except Exception as e:
                logger.warning(f"[WARNING] Failed to get tools list: {e}")
                server.tools = []
            
            self.connected_servers[server_name] = server
            logger.info(f"[OK] Connected to {server_name} with {len(server.tools)} tools")
            
            return True
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to connect to {server_name}: {e}")
            return False
    
    
    async def call_tool(self, tool_call: ToolCall) -> ToolResult:
        """
        ツールを実行（FastMCPクライアントを使用）
        
        Args:
            tool_call: ツール呼び出し情報
            
        Returns:
            実行結果
        """
        logger.info(f"[TOOL] Calling {tool_call.server}.{tool_call.tool}")
        
        # サーバーに接続
        if tool_call.server not in self.connected_servers:
            connected = await self.connect_server(tool_call.server)
            if not connected:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Failed to connect to {tool_call.server}"
                )
        
        server = self.connected_servers[tool_call.server]
        
        try:
            # FastMCPクライアントでツールを実行
            result = await server.client.call_tool(tool_call.tool, tool_call.params)
            
            # 結果を文字列に変換
            result_str = None
            if hasattr(result, 'content'):
                if isinstance(result.content, list) and result.content:
                    first = result.content[0]
                    if hasattr(first, 'text'):
                        result_str = first.text
            
            if result_str is None:
                result_str = str(result)
                
            return ToolResult(
                success=True,
                data=result_str
            )
                
        except Exception as e:
            logger.error(f"[ERROR] Tool call failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=str(e)
            )
    
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        利用可能なツール一覧を取得
        
        Returns:
            ツール情報のリスト
        """
        tools = []
        for server_name, server in self.connected_servers.items():
            if server.tools:
                for tool in server.tools:
                    tool_info = tool.copy()
                    tool_info["server"] = server_name
                    tools.append(tool_info)
        return tools
    
    def find_tool(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        ツールを検索
        
        Args:
            tool_name: ツール名
            
        Returns:
            ツール情報（サーバー名を含む）
        """
        for server_name, server in self.connected_servers.items():
            if server.tools:
                for tool in server.tools:
                    if tool.get("name") == tool_name:
                        tool_info = tool.copy()
                        tool_info["server"] = server_name
                        return tool_info
        return None
    
    async def disconnect_all(self):
        """すべてのサーバーから切断"""
        for server_name, server in self.connected_servers.items():
            if server.client:
                logger.info(f"[DISCONNECT] Disconnecting from {server_name}")
                try:
                    await server.client.__aexit__(None, None, None)
                except Exception as e:
                    logger.error(f"[ERROR] Failed to disconnect from {server_name}: {e}")
        
        self.connected_servers.clear()
        logger.info("[OK] All servers disconnected")

# シミュレーション用のモックMCPマネージャー
class MockMCPManager(MCPManager):
    """テスト用のモックMCPマネージャー"""
    
    def __init__(self):
        super().__init__()
        self._setup_mock_servers()
    
    def _setup_mock_servers(self):
        """モックサーバーを設定"""
        self.servers = {
            "calculator": MCPServer(
                name="calculator",
                path="mock://calculator",
                tools=[
                    {"name": "add", "description": "Add two numbers"},
                    {"name": "multiply", "description": "Multiply two numbers"}
                ]
            ),
            "database": MCPServer(
                name="database",
                path="mock://database",
                tools=[
                    {"name": "query", "description": "Execute SQL query"},
                    {"name": "insert", "description": "Insert data"}
                ]
            ),
            "web_search": MCPServer(
                name="web_search",
                path="mock://web_search",
                tools=[
                    {"name": "search", "description": "Search the web"},
                    {"name": "fetch_page", "description": "Fetch web page content"}
                ]
            )
        }
    
    async def connect_server(self, server_name: str) -> bool:
        """モック接続"""
        if server_name in self.servers:
            self.connected_servers[server_name] = self.servers[server_name]
            logger.info(f"[MOCK] Connected to {server_name}")
            return True
        return False
    
    async def call_tool(self, tool_call: ToolCall) -> ToolResult:
        """モックツール実行"""
        logger.info(f"[MOCK] Calling {tool_call.server}.{tool_call.tool}")
        
        # シミュレートされた結果を返す
        if tool_call.tool == "add":
            # パラメータ名のバリエーションに対応
            a = tool_call.params.get("a") or tool_call.params.get("x") or tool_call.params.get("num1") or tool_call.params.get("number1", 0)
            b = tool_call.params.get("b") or tool_call.params.get("y") or tool_call.params.get("num2") or tool_call.params.get("number2", 0)
            
            # 数値に変換
            try:
                a = float(a) if a else 0
                b = float(b) if b else 0
                result = a + b
                return ToolResult(success=True, data=str(result))
            except:
                return ToolResult(success=True, data="30")  # デフォルト値
        
        elif tool_call.tool == "multiply":
            a = tool_call.params.get("a") or tool_call.params.get("x") or tool_call.params.get("num1") or tool_call.params.get("number1", 0)
            b = tool_call.params.get("b") or tool_call.params.get("y") or tool_call.params.get("num2") or tool_call.params.get("number2", 0)
            
            try:
                a = float(a) if a else 0
                b = float(b) if b else 0
                result = a * b
                return ToolResult(success=True, data=str(result))
            except:
                return ToolResult(success=True, data="90")  # デフォルト値
        
        elif tool_call.tool == "query":
            sql = tool_call.params.get("sql", "")
            return ToolResult(
                success=True,
                data=f"Query executed: {sql}\nReturned 5 rows"
            )
        
        elif tool_call.tool == "insert":
            return ToolResult(
                success=True,
                data="Data inserted successfully"
            )
        
        elif tool_call.tool == "search":
            query = tool_call.params.get("query", "")
            return ToolResult(
                success=True,
                data=f"Found 3 results for '{query}':\n1. Python Tutorial - Beginner Guide\n2. Advanced Python Techniques\n3. Python Best Practices"
            )
        
        elif tool_call.tool == "fetch_page":
            url = tool_call.params.get("url", "")
            return ToolResult(
                success=True,
                data=f"Page content from {url}: Lorem ipsum dolor sit amet..."
            )
        
        # sum関数（1からnまでの合計）
        elif tool_call.tool == "sum_range":
            n = tool_call.params.get("n", 10)
            result = sum(range(1, int(n) + 1))
            return ToolResult(success=True, data=str(result))
        
        # デフォルト応答
        return ToolResult(
            success=True,
            data=f"Mock result for {tool_call.tool}"
        )

# 使用例とテスト
async def test_mcp_manager():
    """MCPマネージャーのテスト"""
    
    # モックマネージャーを使用
    manager = MockMCPManager()
    
    # サーバーに接続
    print("\n" + "="*60)
    print("Connecting to MCP Servers")
    print("="*60)
    
    await manager.connect_server("calculator")
    await manager.connect_server("database")
    await manager.connect_server("web_search")
    
    # 利用可能なツールを表示
    tools = manager.get_available_tools()
    print(f"\nAvailable tools: {len(tools)}")
    for tool in tools:
        print(f"  - {tool.get('server')}.{tool.get('name')}: {tool.get('description')}")
    
    # ツールを実行
    print("\n" + "="*60)
    print("Executing Tools")
    print("="*60)
    
    # 計算ツール
    result = await manager.call_tool(ToolCall(
        server="calculator",
        tool="add",
        params={"a": 10, "b": 20}
    ))
    print(f"\nCalculator.add(10, 20) = {result.data}")
    
    # データベースツール
    result = await manager.call_tool(ToolCall(
        server="database",
        tool="query",
        params={"sql": "SELECT * FROM users"}
    ))
    print(f"\nDatabase.query result: {result.data}")
    
    # Web検索ツール
    result = await manager.call_tool(ToolCall(
        server="web_search",
        tool="search",
        params={"query": "MCP protocol"}
    ))
    print(f"\nWeb search result: {result.data}")
    
    # 切断
    await manager.disconnect_all()

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_mcp_manager())