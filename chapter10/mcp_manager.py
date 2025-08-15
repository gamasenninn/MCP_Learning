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

logger = logging.getLogger(__name__)

@dataclass
class MCPServer:
    """MCPサーバー情報"""
    name: str
    command: str
    args: List[str]
    env: Optional[Dict[str, str]] = None
    working_dir: Optional[str] = None
    process: Optional[subprocess.Popen] = None
    tools: List[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "command": self.command,
            "args": self.args,
            "env": self.env,
            "working_dir": self.working_dir,
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
        config_path = Path.home() / ".config" / "mcp" / "servers.json"
        
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                for name, server_config in config.get("servers", {}).items():
                    self.servers[name] = MCPServer(
                        name=name,
                        command=server_config["command"],
                        args=server_config.get("args", []),
                        env=server_config.get("env"),
                        working_dir=server_config.get("working_dir")
                    )
                    
                logger.info(f"[CONFIG] Loaded {len(self.servers)} MCP servers")
            except Exception as e:
                logger.error(f"[ERROR] Failed to load config: {e}")
    
    async def connect_server(self, server_name: str) -> bool:
        """
        MCPサーバーに接続
        
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
            # サーバープロセスを起動
            logger.info(f"[CONNECT] Starting {server_name}...")
            
            # コマンドを構築
            cmd = [server.command] + server.args
            
            # プロセスを起動
            server.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=server.env,
                cwd=server.working_dir,
                text=True
            )
            
            # 初期化メッセージを送信
            await self._initialize_server(server)
            
            # ツール一覧を取得
            tools = await self._get_server_tools(server)
            server.tools = tools
            
            self.connected_servers[server_name] = server
            logger.info(f"[OK] Connected to {server_name} with {len(tools)} tools")
            
            return True
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to connect to {server_name}: {e}")
            return False
    
    async def _initialize_server(self, server: MCPServer):
        """サーバーを初期化"""
        # JSON-RPC初期化メッセージ
        init_message = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "0.1.0",
                "capabilities": {}
            },
            "id": 1
        }
        
        # メッセージを送信
        await self._send_message(server, init_message)
        
        # レスポンスを待つ
        response = await self._receive_message(server)
        
        if response and "result" in response:
            logger.info(f"[INIT] Server initialized: {server.name}")
        else:
            raise Exception(f"Failed to initialize server: {response}")
    
    async def _get_server_tools(self, server: MCPServer) -> List[Dict[str, Any]]:
        """サーバーのツール一覧を取得"""
        message = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 2
        }
        
        await self._send_message(server, message)
        response = await self._receive_message(server)
        
        if response and "result" in response:
            return response["result"].get("tools", [])
        return []
    
    async def _send_message(self, server: MCPServer, message: Dict[str, Any]):
        """サーバーにメッセージを送信"""
        if not server.process or not server.process.stdin:
            raise Exception(f"Server {server.name} is not connected")
        
        json_str = json.dumps(message)
        server.process.stdin.write(json_str + '\n')
        server.process.stdin.flush()
    
    async def _receive_message(self, server: MCPServer) -> Optional[Dict[str, Any]]:
        """サーバーからメッセージを受信"""
        if not server.process or not server.process.stdout:
            raise Exception(f"Server {server.name} is not connected")
        
        try:
            # タイムアウト付きで読み取り
            line = await asyncio.wait_for(
                asyncio.to_thread(server.process.stdout.readline),
                timeout=10.0
            )
            
            if line:
                return json.loads(line.strip())
        except asyncio.TimeoutError:
            logger.warning(f"[TIMEOUT] No response from {server.name}")
        except json.JSONDecodeError as e:
            logger.error(f"[ERROR] Invalid JSON from {server.name}: {e}")
        
        return None
    
    async def call_tool(self, tool_call: ToolCall) -> ToolResult:
        """
        ツールを実行
        
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
            # ツール実行メッセージ
            message = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": tool_call.tool,
                    "arguments": tool_call.params
                },
                "id": self._get_next_id()
            }
            
            await self._send_message(server, message)
            response = await self._receive_message(server)
            
            if response and "result" in response:
                return ToolResult(
                    success=True,
                    data=response["result"]
                )
            elif response and "error" in response:
                return ToolResult(
                    success=False,
                    data=None,
                    error=response["error"].get("message", "Unknown error")
                )
            else:
                return ToolResult(
                    success=False,
                    data=None,
                    error="No response from server"
                )
                
        except Exception as e:
            logger.error(f"[ERROR] Tool call failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                error=str(e)
            )
    
    def _get_next_id(self) -> int:
        """次のメッセージIDを取得"""
        if not hasattr(self, '_message_id'):
            self._message_id = 100
        self._message_id += 1
        return self._message_id
    
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
            if server.process:
                logger.info(f"[DISCONNECT] Disconnecting from {server_name}")
                server.process.terminate()
                await asyncio.sleep(0.5)
                if server.process.poll() is None:
                    server.process.kill()
        
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
                command="python",
                args=["calculator_server.py"],
                tools=[
                    {"name": "add", "description": "Add two numbers"},
                    {"name": "multiply", "description": "Multiply two numbers"}
                ]
            ),
            "database": MCPServer(
                name="database",
                command="python",
                args=["database_server.py"],
                tools=[
                    {"name": "query", "description": "Execute SQL query"},
                    {"name": "insert", "description": "Insert data"}
                ]
            ),
            "web_search": MCPServer(
                name="web_search",
                command="python",
                args=["web_search_server.py"],
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
            a = tool_call.params.get("a", 0)
            b = tool_call.params.get("b", 0)
            return ToolResult(success=True, data={"result": a + b})
        
        elif tool_call.tool == "query":
            return ToolResult(
                success=True,
                data={"rows": [{"id": 1, "name": "Sample"}]}
            )
        
        elif tool_call.tool == "search":
            query = tool_call.params.get("query", "")
            return ToolResult(
                success=True,
                data={"results": [f"Result for: {query}"]}
            )
        
        return ToolResult(
            success=False,
            data=None,
            error="Unknown tool"
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