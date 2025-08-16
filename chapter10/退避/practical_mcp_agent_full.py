#!/usr/bin/env python3
"""
実践的なMCPエージェント - 完全版（実際のMCPサーバー接続対応）
第9章のLLM統合クライアントをエージェントに進化させた最終形
"""

import asyncio
import json
import os
import sys
import time
import subprocess
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from dotenv import load_dotenv
from openai import AsyncOpenAI
from fastmcp import Client

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

load_dotenv()

# ========================
# データクラス定義
# ========================

@dataclass
class TaskStep:
    """タスクの1ステップを表現"""
    step_number: int
    description: str
    action: str  # "tool_call", "analysis", "decision"
    parameters: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[int] = field(default_factory=list)
    status: str = "pending"  # pending, in_progress, completed, failed
    result: Any = None
    error: Optional[str] = None

class RetryStrategy(Enum):
    """リトライ戦略"""
    IMMEDIATE = "immediate"  # すぐにリトライ
    EXPONENTIAL_BACKOFF = "exponential"  # 指数バックオフ
    ALTERNATIVE = "alternative"  # 代替方法を試す

@dataclass
class RetryConfig:
    """リトライ設定"""
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0

# ========================
# ツール収集クラス
# ========================

class ToolCollector:
    """MCPツール情報を収集するクラス"""
    
    def __init__(self):
        self.servers = {}
        self.tools_schema = {}
        self.connection_status = {}
        self.claude_config_path = self._find_claude_config()
    
    def _find_claude_config(self) -> str:
        """Claude Desktop設定ファイルを探す"""
        possible_paths = [
            os.path.expanduser("~/AppData/Roaming/Claude/claude_desktop_config.json"),
            os.path.expanduser("~/.config/claude/claude_desktop_config.json"),
            os.path.expanduser("~/Library/Application Support/Claude/claude_desktop_config.json")
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # ローカル設定ファイルを使用
        local_config = os.path.join(os.path.dirname(__file__), "mcp_servers.json")
        if os.path.exists(local_config):
            return local_config
            
        return None
    
    async def collect_all_tools(self):
        """すべてのMCPサーバーからツール情報を収集"""
        if not self.claude_config_path:
            print("[WARNING] MCP設定ファイルが見つかりません")
            return
        
        try:
            with open(self.claude_config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            # 設定ファイルの形式を判定
            if "mcpServers" in config:
                # Claude Desktop形式
                mcp_servers = config["mcpServers"]
                for server_name, server_info in mcp_servers.items():
                    self.servers[server_name] = server_info
                    self.tools_schema[server_name] = []
                    self.connection_status[server_name] = "disconnected"
            elif "servers" in config:
                # カスタム形式（配列）
                for server_info in config["servers"]:
                    server_name = server_info.get("name")
                    if server_name:
                        # パスからuvコマンドを構築
                        server_path = server_info.get("path", "")
                        server_dir = os.path.dirname(server_path)
                        server_file = os.path.basename(server_path)
                        
                        self.servers[server_name] = {
                            "command": "uv",
                            "args": [
                                "--directory",
                                server_dir,
                                "run",
                                "python",
                                server_file
                            ]
                        }
                        self.tools_schema[server_name] = []
                        self.connection_status[server_name] = "disconnected"
            else:
                # 直接のサーバー定義（オブジェクト形式）
                for server_name, server_info in config.items():
                    if isinstance(server_info, dict):
                        self.servers[server_name] = server_info
                        self.tools_schema[server_name] = []
                        self.connection_status[server_name] = "disconnected"
                
        except Exception as e:
            print(f"[ERROR] 設定ファイルの読み込みエラー: {e}")
            return
        
        print(f"[INFO] {len(self.servers)}個のMCPサーバーを検出")
        
        # 各サーバーに接続してツール情報を取得
        for server_name in self.servers:
            try:
                # サーバープロセスを起動してツール情報を取得
                tools = await self._get_server_tools(server_name)
                if tools:
                    self.tools_schema[server_name] = tools
                    self.connection_status[server_name] = "connected"
                    print(f"  [OK] {server_name}: {len(tools)}個のツール")
            except Exception as e:
                print(f"  [ERROR] {server_name}: 接続失敗 - {e}")
    
    async def _get_server_tools(self, server_name: str) -> List[Dict]:
        """サーバーからツール情報を取得（簡略版）"""
        # ここでは実際の接続はせず、デモ用のツール情報を返す
        # 実際の接続は_connect_to_serversで行う
        
        # サーバーごとのデモツール
        demo_tools = {
            "calculator": [
                {"name": "add", "description": "2つの数を足す"},
                {"name": "subtract", "description": "2つの数を引く"},
                {"name": "multiply", "description": "2つの数を掛ける"},
                {"name": "divide", "description": "2つの数を割る"}
            ],
            "database": [
                {"name": "query", "description": "SQLクエリを実行"},
                {"name": "insert", "description": "データを挿入"}
            ],
            "filesystem": [
                {"name": "read_file", "description": "ファイルを読む"},
                {"name": "write_file", "description": "ファイルに書く"}
            ],
            "external_api": [
                {"name": "get_weather", "description": "天気情報を取得"}
            ]
        }
        
        return demo_tools.get(server_name, [])

# ========================
# LLM統合準備クラス
# ========================

class LLMIntegrationPrep:
    """LLM統合のための準備クラス"""
    
    def prepare_tools_for_llm(self, tools_schema: Dict) -> str:
        """ツール情報をLLM用に整形"""
        formatted = []
        for server_name, tools in tools_schema.items():
            for tool in tools:
                formatted.append(
                    f"- {server_name}.{tool.get('name', 'unknown')}: "
                    f"{tool.get('description', 'No description')}"
                )
        return "\n".join(formatted) if formatted else "利用可能なツールがありません"
    
    def validate_llm_response(self, response: str) -> Dict:
        """LLMレスポンスを検証"""
        try:
            # JSONをパース
            data = json.loads(response)
            return data
        except json.JSONDecodeError:
            # JSON以外のレスポンスの場合
            return {
                "needs_tool": False,
                "response": response
            }

# ========================
# 基本LLMクライアント
# ========================

class CompleteLLMClient:
    """完全なLLM統合MCPクライアント"""
    
    def __init__(self):
        self.collector = ToolCollector()
        self.prep = LLMIntegrationPrep()
        self.llm = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # クライアント管理
        self.clients = {}
        self.server_processes = {}
        
        # 会話履歴とコンテキスト
        self.conversation_history = []
        self.context = {
            "session_start": datetime.now(),
            "tool_calls": 0,
            "errors": 0
        }
    
    async def initialize(self):
        """初期化処理"""
        print("[起動] エージェントを起動中...", flush=True)
        
        # ツール情報を収集
        await self.collector.collect_all_tools()
        
        # MCPサーバーに接続
        await self._connect_to_servers()
        
        print("[完了] 初期化完了\n", flush=True)
        self._show_available_tools()
    
    async def _connect_to_servers(self):
        """MCPサーバーに接続（簡略版）"""
        for server_name, server_info in self.collector.servers.items():
            if self.collector.connection_status[server_name] == "disconnected":
                try:
                    # サーバー情報から実行可能なコマンドを作成
                    cmd = server_info.get("command")
                    args = server_info.get("args", [])
                    
                    if cmd and args:
                        # FastMCPで接続を試みる
                        # スタンドアロンモードで起動
                        server_cmd = [cmd] + args
                        
                        # Clientを作成（stdio transport）
                        client = Client(server_name, server_cmd)
                        
                        # 接続を試みる
                        await client.__aenter__()
                        self.clients[server_name] = client
                        
                        # ツール一覧を取得
                        tools = await client.list_tools()
                        
                        if tools:
                            self.collector.tools_schema[server_name] = tools
                            self.collector.connection_status[server_name] = "connected"
                            print(f"  [CONNECT] {server_name}: 接続成功 ({len(tools)}個のツール)")
                        else:
                            # ツールが取得できない場合はデモツールを使用
                            demo_tools = await self._get_server_tools(server_name)
                            self.collector.tools_schema[server_name] = demo_tools
                            print(f"  [DEMO] {server_name}: デモモード ({len(demo_tools)}個のツール)")
                    
                except Exception as e:
                    # エラー時はデモツールを使用
                    print(f"  [WARNING] {server_name}: 実接続失敗、デモモードを使用 - {e}")
                    demo_tools = await self._get_server_tools(server_name)
                    if demo_tools:
                        self.collector.tools_schema[server_name] = demo_tools
                        self.collector.connection_status[server_name] = "demo"
    
    async def _start_server_process(self, server_name: str, server_info: Dict) -> subprocess.Popen:
        """サーバープロセスを起動"""
        try:
            cmd = server_info.get("command")
            args = server_info.get("args", [])
            
            if cmd:
                # コマンドラインを構築
                full_cmd = [cmd] + args
                
                # プロセスを起動
                process = subprocess.Popen(
                    full_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # 少し待機してサーバーが起動するのを待つ
                await asyncio.sleep(2)
                
                return process
        except Exception as e:
            print(f"    [ERROR] サーバー起動失敗: {e}")
            
        return None
    
    def _show_available_tools(self):
        """利用可能なツールを表示"""
        total_tools = sum(len(tools) for tools in self.collector.tools_schema.values())
        print(f"[ツール] 利用可能なツール: {total_tools}個")
        for server_name, tools in self.collector.tools_schema.items():
            if tools:
                print(f"  - {server_name}: {len(tools)}個のツール")
                for tool in tools[:3]:  # 最初の3個だけ表示
                    print(f"    • {tool.get('name', 'unknown')}")
                if len(tools) > 3:
                    print(f"    ... 他{len(tools)-3}個")
        print()
    
    async def _execute_tool(self, server: str, tool: str, arguments: Dict) -> Any:
        """MCPツールを実行"""
        self.context["tool_calls"] += 1
        
        # 実際のMCPクライアントを使用
        if server in self.clients:
            client = self.clients[server]
            try:
                result = await client.call_tool(tool, arguments)
                
                # 結果を文字列に変換
                if hasattr(result, 'content'):
                    if isinstance(result.content, list) and result.content:
                        first = result.content[0]
                        if hasattr(first, 'text'):
                            return first.text
                return str(result)
                
            except Exception as e:
                print(f"    [ERROR] ツール実行エラー: {e}")
                raise
        else:
            # サーバーが接続されていない場合
            print(f"    [WARNING] サーバー '{server}' は接続されていません")
            
            # サーバーへの接続を試みる
            if server in self.collector.servers:
                print(f"    [INFO] {server}への接続を試みます...")
                await self._connect_single_server(server)
                
                # 再度実行を試みる
                if server in self.clients:
                    return await self._execute_tool(server, tool, arguments)
            
            raise ValueError(f"サーバー '{server}' が利用できません")
    
    async def _connect_single_server(self, server_name: str):
        """単一のサーバーに接続"""
        if server_name not in self.collector.servers:
            return
            
        server_info = self.collector.servers[server_name]
        
        try:
            # サーバープロセスを起動
            process = await self._start_server_process(server_name, server_info)
            if process:
                self.server_processes[server_name] = process
            
            # クライアントを作成
            client = Client(server_name)
            await client.__aenter__()
            self.clients[server_name] = client
            
            # ツール情報を取得
            tools = await client.list_tools()
            self.collector.tools_schema[server_name] = tools
            self.collector.connection_status[server_name] = "connected"
            
            print(f"    [OK] 接続成功: {len(tools)}個のツール")
            
        except Exception as e:
            print(f"    [ERROR] 接続失敗: {e}")
    
    async def cleanup(self):
        """クリーンアップ処理"""
        # クライアントを閉じる
        for client in self.clients.values():
            try:
                await client.__aexit__(None, None, None)
            except:
                pass
        
        # サーバープロセスを終了
        for process in self.server_processes.values():
            try:
                process.terminate()
                process.wait(timeout=5)
            except:
                pass

# ========================
# タスクプランニング機能
# ========================

class TaskPlanningAgent(CompleteLLMClient):
    """タスクプランニング機能を追加したエージェント"""
    
    def __init__(self):
        super().__init__()
        self.current_plan: List[TaskStep] = []
        self.execution_history: List[Dict] = []
    
    async def create_plan(self, user_request: str) -> List[TaskStep]:
        """ユーザーリクエストから実行計画を生成"""
        
        # 利用可能なツール情報を取得
        tools_description = self._format_available_tools()
        
        planning_prompt = f"""
あなたは優秀なタスクプランナーです。
以下のリクエストを実行可能なステップに分解してください。

## ユーザーリクエスト
{user_request}

## 利用可能なツール
{tools_description}

## 計画作成のルール
1. 各ステップは単一の明確なアクションであること
2. 依存関係を明示すること（前のステップの結果が必要な場合）
3. 利用可能なツールのみを使用すること
4. ツール名は正確に記載すること

## 応答形式
以下のJSON形式で応答してください：
{{
    "plan": [
        {{
            "step_number": 1,
            "description": "ステップの説明",
            "action": "tool_call",
            "parameters": {{
                "server": "サーバー名（例: calculator）",
                "tool": "ツール名（例: add）",
                "arguments": {{具体的な引数}}
            }},
            "depends_on": []
        }}
    ],
    "reasoning": "なぜこの計画にしたか"
}}

重要: serverとtoolは別々に指定してください。
例: calculator.add → server: "calculator", tool: "add"
"""
        
        try:
            # LLMに計画を作成させる
            response = await self.llm.chat.completions.create(
                model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": "You are a task planning assistant. Always respond with valid JSON."},
                    {"role": "user", "content": planning_prompt}
                ],
                temperature=0
            )
            
            # レスポンスをパース
            response_text = response.choices[0].message.content
            
            # JSONブロックを抽出（```json ... ```の形式に対応）
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                response_text = response_text[start:end]
            
            plan_data = json.loads(response_text)
            
            # TaskStepオブジェクトに変換
            self.current_plan = [
                TaskStep(**step_data) for step_data in plan_data["plan"]
            ]
            
            print(f"[計画] {len(self.current_plan)}ステップの計画を作成")
            
        except Exception as e:
            print(f"[WARNING] 計画作成エラー: {e}")
            # エラー時は単純な計画を作成
            self.current_plan = [
                TaskStep(
                    step_number=1,
                    description=f"{user_request}を実行",
                    action="analysis",
                    parameters={}
                )
            ]
        
        return self.current_plan
    
    def _format_available_tools(self) -> str:
        """利用可能なツールを整形"""
        lines = []
        for server_name, tools in self.collector.tools_schema.items():
            if tools:
                for tool in tools:
                    tool_name = tool.get('name', 'unknown')
                    tool_desc = tool.get('description', 'No description')
                    lines.append(f"- {server_name}.{tool_name}: {tool_desc}")
        
        if not lines:
            lines.append("- 現在利用可能なツールがありません")
            
        return "\n".join(lines)

# ========================
# エラーハンドリング機能
# ========================

class ErrorHandlingAgent(TaskPlanningAgent):
    """エラーハンドリング機能を追加したエージェント"""
    
    def __init__(self):
        super().__init__()
        self.retry_config = RetryConfig()
        self.error_handlers: Dict[str, Callable] = {}
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """デフォルトのエラーハンドラーを登録"""
        self.error_handlers["FileNotFoundError"] = self._handle_file_not_found
        self.error_handlers["ConnectionError"] = self._handle_connection_error
        self.error_handlers["ValueError"] = self._handle_value_error
    
    async def execute_with_retry(
        self, 
        func: Callable, 
        step: TaskStep,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    ) -> Any:
        """リトライ機能付きで関数を実行"""
        
        last_error = None
        delay = self.retry_config.initial_delay
        
        for attempt in range(self.retry_config.max_attempts):
            try:
                print(f"    [試行 {attempt + 1}/{self.retry_config.max_attempts}]", end=" ")
                result = await func()
                print("[成功]")
                return result
                
            except Exception as e:
                last_error = e
                error_type = type(e).__name__
                
                print(f"[失敗: {error_type}]")
                
                # エラー固有のハンドラーを実行
                if error_type in self.error_handlers:
                    handled = await self.error_handlers[error_type](step, e)
                    if handled:
                        continue
                
                # リトライ戦略を適用
                if attempt < self.retry_config.max_attempts - 1:
                    if strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
                        print(f"    [待機] {delay:.1f}秒後にリトライします...")
                        await asyncio.sleep(delay)
                        delay = min(
                            delay * self.retry_config.exponential_base,
                            self.retry_config.max_delay
                        )
                    elif strategy == RetryStrategy.ALTERNATIVE:
                        # 代替方法を生成
                        alternative = await self._generate_alternative(step, e)
                        if alternative:
                            step.parameters = alternative
                            print(f"    [代替案] 別の方法を試します")
        
        # すべての試行が失敗
        raise Exception(f"すべてのリトライが失敗しました: {last_error}")
    
    async def _handle_file_not_found(self, step: TaskStep, error: Exception) -> bool:
        """ファイルが見つからないエラーを処理"""
        print("    [対処] ファイルが見つかりません")
        return False
    
    async def _handle_connection_error(self, step: TaskStep, error: Exception) -> bool:
        """接続エラーを処理"""
        print("    [対処] 接続エラーが発生しました")
        print("    [待機] 5秒後に再接続します...")
        await asyncio.sleep(5)
        return True
    
    async def _handle_value_error(self, step: TaskStep, error: Exception) -> bool:
        """値エラーを処理"""
        print(f"    [対処] 値エラー: {error}")
        return False
    
    async def _generate_alternative(self, step: TaskStep, error: Exception) -> Optional[Dict]:
        """代替案を生成"""
        return None

# ========================
# 統合エージェント（最終形）
# ========================

class PracticalMCPAgent(ErrorHandlingAgent):
    """実践的なMCPエージェント - すべての機能を統合"""
    
    def __init__(self):
        super().__init__()
        self.session_memory = {
            "variables": {},
            "completed_tasks": [],
            "errors": []
        }
    
    async def execute(self, user_request: str, auto_approve: bool = False) -> Dict:
        """ユーザーリクエストを完全に実行"""
        
        print(f"\n{'='*60}")
        print(f"[タスク] {user_request}")
        print(f"{'='*60}\n")
        
        # Step 1: 計画を作成
        print("[フェーズ1] タスク分析と計画作成")
        plan = await self.create_plan(user_request)
        
        # 計画を表示
        self._show_plan(plan)
        
        # Step 2: ユーザー確認（必要な場合）
        if not auto_approve:
            print("\nこの計画を実行しますか？ (y/n): ", end="")
            user_input = input().strip().lower()
            if user_input != 'y':
                return {"status": "cancelled", "message": "ユーザーによりキャンセルされました"}
        
        # Step 3: 計画を実行（エラーハンドリング付き）
        print("\n[フェーズ2] タスク実行")
        
        completed_steps = 0
        failed_steps = 0
        
        for step in plan:
            print(f"\n[ステップ {step.step_number}] {step.description}")
            
            # 依存関係をチェック
            if not self._check_dependencies(step, plan):
                print("  [スキップ] 依存関係が未解決")
                continue
            
            try:
                # リトライ機能付きで実行
                result = await self.execute_with_retry(
                    lambda: self._execute_step(step),
                    step,
                    RetryStrategy.EXPONENTIAL_BACKOFF
                )
                
                step.status = "completed"
                step.result = result
                completed_steps += 1
                
                # 結果をメモリに保存
                self.session_memory["variables"][f"step_{step.step_number}"] = result
                
            except Exception as e:
                step.status = "failed"
                step.error = str(e)
                failed_steps += 1
                
                self.session_memory["errors"].append({
                    "step": step.step_number,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
                
                # クリティカルなステップの場合は中断
                if self._is_critical_step(step):
                    print(f"  [中断] クリティカルなエラーのため実行を中断")
                    break
        
        # Step 4: 結果をまとめる
        return self._summarize_execution(plan, completed_steps, failed_steps)
    
    def _check_dependencies(self, step: TaskStep, plan: List[TaskStep]) -> bool:
        """依存関係をチェック"""
        for dep_num in step.depends_on:
            dep_step = next((s for s in plan if s.step_number == dep_num), None)
            if not dep_step or dep_step.status != "completed":
                return False
        return True
    
    async def _execute_step(self, step: TaskStep) -> Any:
        """単一ステップを実行"""
        if step.action == "tool_call":
            # MCPツールを呼び出し
            server = step.parameters.get("server")
            tool = step.parameters.get("tool")
            args = step.parameters.get("arguments", {})
            
            print(f"    実行: {server}.{tool}({args})")
            
            return await self._execute_tool(server, tool, args)
        else:
            # その他のアクション（分析など）
            await asyncio.sleep(0.3)
            return {"result": "analysis completed"}
    
    def _show_plan(self, plan: List[TaskStep]):
        """計画を表示"""
        print("\n[実行計画]")
        print("-"*40)
        for step in plan:
            status_mark = {
                "pending": "[ ]",
                "completed": "[OK]",
                "failed": "[FAIL]"
            }.get(step.status, "[ ]")
            
            print(f"{status_mark} Step {step.step_number}: {step.description}")
            if step.depends_on:
                print(f"     └─ 依存: Step {step.depends_on}")
    
    def _is_critical_step(self, step: TaskStep) -> bool:
        """クリティカルなステップかどうか判定"""
        critical_tools = ["delete", "drop", "truncate", "remove"]
        if step.action == "tool_call":
            tool_name = step.parameters.get("tool", "").lower()
            return any(critical in tool_name for critical in critical_tools)
        return False
    
    def _summarize_execution(self, plan: List[TaskStep], completed: int, failed: int) -> Dict:
        """実行結果をまとめる"""
        total = len(plan)
        
        if failed == 0:
            status = "success"
            message = "すべてのステップが正常に完了しました。"
        elif completed > 0:
            status = "partial"
            message = f"{completed}個のステップが完了、{failed}個が失敗しました。"
        else:
            status = "failed"
            message = "タスクの実行に失敗しました。"
        
        # 結果を詳しく生成
        if completed > 0 and plan:
            # 完了したステップの結果を集約
            results = []
            for step in plan:
                if step.status == "completed" and step.result:
                    results.append(f"Step {step.step_number}: {step.result}")
            
            if results:
                message += "\n結果: " + ", ".join(results[:3])  # 最初の3個まで表示
        
        # 完了タスクを記録
        self.session_memory["completed_tasks"].append({
            "timestamp": datetime.now().isoformat(),
            "steps": total,
            "completed": completed,
            "failed": failed
        })
        
        return {
            "status": status,
            "total_steps": total,
            "completed_steps": completed,
            "failed_steps": failed,
            "result": message
        }
    
    async def interactive_session(self):
        """対話型セッション"""
        print("\n" + "="*60)
        print("MCPエージェント - 対話モード")
        print("="*60)
        print("コマンド:")
        print("  - 自然言語でタスクを入力")
        print("  - 'status' でセッション状態を表示")
        print("  - 'tools' で利用可能なツールを表示")
        print("  - 'exit' で終了")
        print("-"*60 + "\n")
        
        try:
            while True:
                try:
                    user_input = input("\nあなた> ").strip()
                    
                    if user_input.lower() == 'exit':
                        print("終了します")
                        break
                    elif user_input.lower() == 'status':
                        self._show_session_status()
                        continue
                    elif user_input.lower() == 'tools':
                        self._show_available_tools()
                        continue
                    elif not user_input:
                        continue
                    
                    # タスクを実行
                    result = await self.execute(user_input)
                    
                    # 結果を表示
                    print(f"\n[完了] ステータス: {result['status']}")
                    print(f"結果: {result['result']}")
                    
                except KeyboardInterrupt:
                    print("\n\n中断されました")
                    break
                except Exception as e:
                    print(f"\nエラー: {e}")
        finally:
            # クリーンアップ
            await self.cleanup()
    
    def _show_session_status(self):
        """セッション状態を表示"""
        print("\n[セッション状態]")
        print(f"完了タスク: {len(self.session_memory['completed_tasks'])}")
        print(f"保存変数: {len(self.session_memory['variables'])}")
        print(f"エラー数: {len(self.session_memory['errors'])}")

# ========================
# メイン実行
# ========================

async def main():
    """メイン実行関数"""
    import sys
    
    # コマンドライン引数をチェック
    if len(sys.argv) > 1:
        mode = sys.argv[1]
    else:
        mode = "interactive"
    
    # エージェントを初期化
    agent = PracticalMCPAgent()
    
    try:
        await agent.initialize()
        
        if mode == "interactive":
            # 対話モード
            await agent.interactive_session()
        elif mode == "demo":
            # デモ実行
            print("[デモモード]")
            result = await agent.execute(
                "100と200を足してください",
                auto_approve=True
            )
            print(f"\n最終結果: {result}")
        elif mode == "test":
            # テスト実行
            print("[テストモード]")
            
            # calculatorサーバーが利用可能か確認
            if "calculator" in agent.collector.tools_schema:
                result = await agent.execute(
                    "55と45を足してください",
                    auto_approve=True
                )
                print(f"\nテスト結果: {result}")
            else:
                print("calculatorサーバーが利用できません")
                print("利用可能なサーバー:", list(agent.collector.tools_schema.keys()))
        else:
            print(f"Unknown mode: {mode}")
            print("Usage: python practical_mcp_agent_full.py [interactive|demo|test]")
    finally:
        # 必ずクリーンアップ
        await agent.cleanup()

if __name__ == "__main__":
    # 実行
    asyncio.run(main())