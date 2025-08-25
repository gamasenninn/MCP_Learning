#!/usr/bin/env python3
"""
実践的なMCPエージェント - 第9章ベース版
第9章のmcp_llm_final.pyの実績あるコードを基盤として拡張
"""

import asyncio
import json
import os
import sys
from typing import Dict, List, Any, Optional, Callable
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
    IMMEDIATE = "immediate"
    EXPONENTIAL_BACKOFF = "exponential"
    ALTERNATIVE = "alternative"

@dataclass
class RetryConfig:
    """リトライ設定"""
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0

# ========================
# 第9章のToolCollectorクラス（実績あり）
# ========================

class ToolCollector:
    """MCPツール情報を収集するクラス"""
    
    def __init__(self):
        self.servers = {}
        self.tools_schema = {}
        self.clients = {}
    
    async def collect_all_tools(self):
        """すべてのMCPサーバーからツール情報を収集"""
        # 設定ファイルを読み込み
        config_path = os.path.join(os.path.dirname(__file__), "mcp_servers.json")
        
        if not os.path.exists(config_path):
            print("[WARNING] mcp_servers.jsonが見つかりません")
            return
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # serversキーから配列を取得
        if "servers" in config:
            servers_list = config["servers"]
            for server_info in servers_list:
                server_name = server_info.get("name")
                server_path = server_info.get("path")
                if server_name and server_path:
                    self.servers[server_name] = {"path": server_path}
        
        print(f"[INFO] {len(self.servers)}個のMCPサーバーを検出", flush=True)
        
        # 各サーバーに接続してツール情報を取得（第9章と同じロジック）
        for server_name, server_info in self.servers.items():
            try:
                # サーバーに接続
                client = Client(server_info["path"])
                await client.__aenter__()
                await client.ping()
                self.clients[server_name] = client
                
                # ツール情報を取得
                tools = await client.list_tools()
                self.tools_schema[server_name] = []
                
                for tool in tools:
                    tool_info = {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": tool.inputSchema if hasattr(tool, 'inputSchema') else {}
                    }
                    self.tools_schema[server_name].append(tool_info)
                
                print(f"  [OK] {server_name}: {len(tools)}個のツールを発見", flush=True)
                
            except Exception as e:
                print(f"  [WARNING] {server_name}: 接続失敗 - {e}", flush=True)

# ========================
# 第9章のLLMIntegrationPrepクラス
# ========================

class LLMIntegrationPrep:
    """LLM統合のための準備クラス"""
    
    def prepare_tools_for_llm(self, tools_schema: Dict) -> str:
        """ツール情報をLLM用に整形"""
        formatted = []
        for server_name, tools in tools_schema.items():
            for tool in tools:
                formatted.append(
                    f"- {server_name}.{tool['name']}: {tool.get('description', 'No description')}"
                )
        return "\n".join(formatted) if formatted else "利用可能なツールがありません"
    
    def validate_llm_response(self, response: str) -> Dict:
        """LLMレスポンスを検証"""
        try:
            # JSON部分を抽出
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                response = response[start:end]
            
            return json.loads(response)
        except json.JSONDecodeError:
            return {"needs_tool": False, "response": response}

# ========================
# 第9章のCompleteLLMClient（ベース）
# ========================

class CompleteLLMClient:
    """完全なLLM統合MCPクライアント（第9章版）"""
    
    def __init__(self):
        self.collector = ToolCollector()
        self.prep = LLMIntegrationPrep()
        self.llm = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # クライアント管理（collectorのclientsを使用）
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
        print("[起動] エージェントを起動中...", flush=True)
        
        # ツール情報を収集（第9章と同じ）
        await self.collector.collect_all_tools()
        
        # clientsを引き継ぐ
        self.clients = self.collector.clients
        
        print("[完了] 初期化完了\n", flush=True)
        self._show_available_tools()
    
    def _show_available_tools(self):
        """利用可能なツールを表示"""
        total_tools = sum(len(tools) for tools in self.collector.tools_schema.values())
        print(f"[ツール] 利用可能なツール: {total_tools}個")
        for server_name, tools in self.collector.tools_schema.items():
            print(f"  - {server_name}: {len(tools)}個のツール")
        print()
    
    async def _execute_tool(self, server: str, tool: str, arguments: Dict) -> Any:
        """MCPツールを実行（第9章と同じロジック）"""
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
    
    async def cleanup(self):
        """クリーンアップ処理"""
        for client in self.clients.values():
            try:
                await client.__aexit__(None, None, None)
            except:
                pass

# ========================
# タスクプランニング機能（新規追加）
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
        tools_description = self.prep.prepare_tools_for_llm(self.collector.tools_schema)
        
        planning_prompt = f"""
あなたは優秀なタスクプランナーです。
以下のリクエストを実行可能なステップに分解してください。

## ユーザーリクエスト
{user_request}

## 利用可能なツール
{tools_description}

## 計画作成のルール
1. 各ステップは単一の明確なアクションであること
2. 依存関係を明示すること
3. 利用可能なツールのみを使用すること
4. 重要: server と tool は別々のフィールドです
   - 正しい例: "server": "calculator", "tool": "add"
   - 間違い例: "server": "calculator", "tool": "calculator.add"

## 応答形式
以下のJSON形式で応答してください：
{{
    "plan": [
        {{
            "step_number": 1,
            "description": "ステップの説明",
            "action": "tool_call",
            "parameters": {{
                "server": "サーバー名",
                "tool": "ツール名",
                "arguments": {{}}
            }},
            "depends_on": []
        }}
    ],
    "reasoning": "なぜこの計画にしたか"
}}
"""
        
        try:
            response = await self.llm.chat.completions.create(
                model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": "You are a task planning assistant."},
                    {"role": "user", "content": planning_prompt}
                ],
                temperature=0
            )
            
            plan_data = self.prep.validate_llm_response(response.choices[0].message.content)
            
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
                    description=user_request,
                    action="tool_call",
                    parameters={}
                )
            ]
        
        return self.current_plan
    
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
            server = step.parameters.get("server")
            tool = step.parameters.get("tool")
            args = step.parameters.get("arguments", {})
            
            # ツール名の修正（calculator.addのような形式の場合）
            if "." in str(tool):
                # server.toolという形式になっている場合、分割する
                parts = tool.split(".")
                if len(parts) == 2 and parts[0] == server:
                    # 重複を削除（calculator.calculator.add -> calculator.add）
                    tool = parts[1]
                    print(f"    [修正] ツール名を修正: {server}.{parts[0]}.{parts[1]} -> {server}.{tool}")
            
            print(f"    実行: {server}.{tool}({args})")
            
            return await self._execute_tool(server, tool, args)
        else:
            # その他のアクション
            return {"result": "completed"}

# ========================
# エラーハンドリング機能（新規追加）
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
        self.error_handlers["ToolError"] = self._handle_tool_error
    
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
    
    async def _handle_tool_error(self, step: TaskStep, error: Exception) -> bool:
        """ツールエラーを処理"""
        print(f"    [対処] ツールエラー: {error}")
        
        # ツール名を分析して修正を試みる
        if step.action == "tool_call":
            tool = step.parameters.get("tool", "")
            server = step.parameters.get("server", "")
            
            # ツール名に重複がないか確認
            if "." in tool:
                parts = tool.split(".")
                # server.tool形式の場合、最後の部分だけを使う
                step.parameters["tool"] = parts[-1]
                print(f"    [修正] ツール名を簡略化: {tool} -> {parts[-1]}")
                return True
            
            # 利用可能なツールを確認
            if server in self.collector.tools_schema:
                available_tools = [t["name"] for t in self.collector.tools_schema[server]]
                print(f"    [情報] {server}の利用可能なツール: {available_tools}")
                
                # 類似のツール名を探す
                for available_tool in available_tools:
                    if available_tool.lower() in tool.lower() or tool.lower() in available_tool.lower():
                        step.parameters["tool"] = available_tool
                        print(f"    [修正] ツール名を修正: {tool} -> {available_tool}")
                        return True
        
        return False

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
        
        # 成功したステップの結果を含める
        if completed > 0:
            results = []
            for step in plan:
                if step.status == "completed" and step.result:
                    results.append(str(step.result)[:100])  # 最初の100文字
            if results:
                message += f"\n結果: {', '.join(results[:3])}"
        
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
            
            # 簡単な計算タスク
            if "calculator" in agent.collector.tools_schema:
                result = await agent.execute(
                    "100と200を足してください",
                    auto_approve=True
                )
            else:
                result = await agent.execute(
                    "テストタスクを実行してください",
                    auto_approve=True
                )
            
            print(f"\n最終結果: {result}")
        elif mode == "test":
            # テストモード
            print("[テストモード]")
            print("利用可能なサーバー:")
            for server_name in agent.collector.tools_schema.keys():
                print(f"  - {server_name}")
            
            # 最初のサーバーでテスト
            if agent.collector.tools_schema:
                first_server = list(agent.collector.tools_schema.keys())[0]
                first_tool = agent.collector.tools_schema[first_server][0]["name"]
                
                print(f"\nテスト: {first_server}.{first_tool}")
                result = await agent.execute(
                    f"{first_server}の{first_tool}ツールをテストしてください",
                    auto_approve=True
                )
                print(f"結果: {result}")
        else:
            print(f"Unknown mode: {mode}")
            print("Usage: python practical_mcp_agent_v9_based.py [interactive|demo|test]")
    finally:
        # 必ずクリーンアップ
        await agent.cleanup()

if __name__ == "__main__":
    # 実行
    asyncio.run(main())