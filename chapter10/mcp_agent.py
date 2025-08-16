#!/usr/bin/env python3
"""
MCPエージェント（統合版）
タスクマネージャーとエラーハンドラーを統合した高度なMCPクライアント
"""

import asyncio
import os
import sys
import json
import shlex
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dotenv import load_dotenv

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

from openai import AsyncOpenAI
from fastmcp import Client

# タスクマネージャーとエラーハンドラーをインポート
from task_manager import SimpleTaskManager, Task, TaskStatus
from error_handler import BasicErrorHandler, ErrorSeverity

# 第9章のコンポーネントもインポート
from mcp_llm_step1 import ToolCollector
from mcp_llm_step2 import LLMIntegrationPrep

load_dotenv()

class MCPAgent:
    """統合MCPエージェント"""
    
    def __init__(self, verbose: bool = True):
        # 基本コンポーネント
        self.collector = ToolCollector()
        self.prep = LLMIntegrationPrep()
        self.llm = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # タスクマネージャーとエラーハンドラー
        self.task_manager = SimpleTaskManager(verbose=verbose)
        self.error_handler = BasicErrorHandler(verbose=verbose)
        
        # クライアント管理
        self.clients = {}
        self.verbose = verbose
        
        # 会話履歴とコンテキスト
        self.conversation_history = []
        self.context = {
            "session_start": datetime.now(),
            "tool_calls": 0,
            "errors": 0,
            "tasks_completed": 0
        }
    
    async def initialize(self):
        """初期化処理"""
        print("[起動] MCPエージェントを起動中...", flush=True)
        
        # タスクを作成
        init_tasks = []
        
        # ツール収集タスク
        task1 = Task(
            id="init_1",
            name="ツール情報収集",
            description="利用可能なMCPツールを収集",
            function=self.collector.collect_all_tools
        )
        init_tasks.append(task1)
        
        # サーバー接続タスク
        task2 = Task(
            id="init_2",
            name="MCPサーバー接続",
            description="MCPサーバーに接続",
            function=self._connect_servers,
            dependencies=["init_1"]
        )
        init_tasks.append(task2)
        
        # タスクマネージャーに追加
        for task in init_tasks:
            self.task_manager.add_task(task)
        
        # 初期化タスクを実行
        result = await self.task_manager.execute_all(stop_on_error=False)
        
        if result["completed"] == len(init_tasks):
            print("[完了] 初期化完了\n", flush=True)
            self._show_available_tools()
        else:
            print("[警告] 一部の初期化処理が失敗しました\n", flush=True)
    
    async def _connect_servers(self):
        """MCPサーバーに接続"""
        connected = 0
        for server_name, server_info in self.collector.servers.items():
            try:
                client = Client(server_info["path"])
                await client.__aenter__()
                self.clients[server_name] = client
                connected += 1
            except Exception as e:
                # エラーハンドラーで処理
                await self.error_handler.handle_error(
                    e,
                    task=f"サーバー接続: {server_name}",
                    operation="connect"
                )
        
        return f"{connected}/{len(self.collector.servers)}サーバーに接続"
    
    def _show_available_tools(self):
        """利用可能なツールを表示"""
        total_tools = sum(len(tools) for tools in self.collector.tools_schema.values())
        print(f"[ツール] 利用可能なツール: {total_tools}個")
        for server_name, tools in self.collector.tools_schema.items():
            print(f"  - {server_name}: {len(tools)}個のツール")
        print()
    
    async def process_query(self, query: str) -> str:
        """クエリを処理（タスク分解とエラーハンドリング付き）"""
        # 会話履歴に追加
        self.conversation_history.append({"role": "user", "content": query})
        
        # クエリを分析してタスクに分解
        tasks = await self._decompose_query_to_tasks(query)
        
        if not tasks:
            # タスク分解不要の単純なクエリ
            return await self._process_simple_query(query)
        
        # タスクマネージャーをリセット
        self.task_manager.reset()
        
        # タスクを追加
        for task in tasks:
            self.task_manager.add_task(task)
        
        # タスクを実行
        print(f"\n[タスク実行] {len(tasks)}個のタスクを実行します")
        result = await self.task_manager.execute_all(stop_on_error=False)
        
        # 結果を集約
        response = self._aggregate_task_results(result)
        
        # 会話履歴に追加
        self.conversation_history.append({"role": "assistant", "content": response})
        self.context["tasks_completed"] += result["completed"]
        
        return response
    
    async def _decompose_query_to_tasks(self, query: str) -> List[Task]:
        """クエリをタスクに分解"""
        tools_desc = self.prep.prepare_tools_for_llm(self.collector.tools_schema)
        
        prompt = f"""
あなたはタスクプランナーです。ユーザーのリクエストを分析し、実行可能なタスクに分解してください。

## ユーザーのリクエスト
{query}

## 利用可能なツール
{tools_desc}

## 重要な注意事項
- ツール名はサーバー名を含めず、ツール名のみを指定してください（例: "add" であり "calculator.add" ではない）
- パラメータ名は正確に指定してください：
  - add, subtract, multiply, divide: "a" と "b" を使用
  - power: "base" と "exponent" を使用
  - square_root: "n" を使用

## 指示
1. リクエストが複数の手順を必要とする場合、それぞれをタスクに分解してください
2. 各タスクには依存関係がある場合は明記してください
3. 単純なリクエストの場合は「SIMPLE」と回答してください

## 出力形式（JSON）
複雑なタスクの場合:
{{
  "tasks": [
    {{
      "id": "task_1",
      "name": "タスク名",
      "description": "タスクの説明",
      "tool": "使用するツール名（オプション）",
      "params": {{正確なパラメータ名と値}},
      "dependencies": []
    }}
  ]
}}

単純なタスクの場合:
{{
  "type": "SIMPLE"
}}
"""
        
        try:
            response = await self.llm.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            result = json.loads(response.choices[0].message.content)
            
            if result.get("type") == "SIMPLE":
                return []
            
            # タスクオブジェクトに変換
            tasks = []
            for task_data in result.get("tasks", []):
                task = Task(
                    id=task_data["id"],
                    name=task_data["name"],
                    description=task_data["description"],
                    function=self._create_task_function(task_data),
                    args=task_data.get("params", {}),
                    dependencies=task_data.get("dependencies", [])
                )
                tasks.append(task)
            
            return tasks
            
        except Exception as e:
            if self.verbose:
                print(f"[タスク分解] エラー: {e}")
            return []
    
    def _create_task_function(self, task_data: Dict) -> Optional[callable]:
        """タスクデータから実行関数を作成"""
        tool_name = task_data.get("tool")
        if not tool_name:
            return None
        
        # パラメータを取得
        params = task_data.get("params", {})
        
        async def execute_tool():
            # ツールを実行
            server_name = None
            for srv_name, tools in self.collector.tools_schema.items():
                if any(t["name"] == tool_name for t in tools):
                    server_name = srv_name
                    break
            
            if not server_name or server_name not in self.clients:
                raise ValueError(f"ツール {tool_name} が見つかりません")
            
            client = self.clients[server_name]
            # パラメータを正しく渡す
            result = await client.call_tool(tool_name, params)
            return result
        
        return execute_tool
    
    async def _process_simple_query(self, query: str) -> str:
        """単純なクエリを処理（第9章の実装を流用）"""
        analysis = await self._analyze_query(query)
        
        if analysis.get("requires_tool"):
            # ツール実行が必要
            try:
                tool_result = await self._execute_tool_with_error_handling(analysis)
                response = await self._generate_response(query, tool_result)
            except Exception as e:
                # エラーハンドリング
                error_result = await self.error_handler.handle_error(
                    e,
                    task="ツール実行",
                    operation=analysis.get("tool_name")
                )
                
                if error_result["success"]:
                    response = await self._generate_response(query, error_result["result"])
                else:
                    response = f"申し訳ございません。エラーが発生しました: {error_result['error']}"
        else:
            # 直接回答
            response = analysis.get("response", "お答えできません")
        
        return response
    
    async def _analyze_query(self, query: str) -> Dict:
        """クエリを分析（第9章の実装を流用）"""
        tools_desc = self.prep.prepare_tools_for_llm(self.collector.tools_schema)
        
        recent_history = ""
        if self.conversation_history:
            recent_messages = self.conversation_history[-5:]
            history_lines = []
            for msg in recent_messages:
                role = "ユーザー" if msg["role"] == "user" else "アシスタント"
                history_lines.append(f"{role}: {msg['content']}")
            recent_history = "\n".join(history_lines)
        
        prompt = f"""
あなたは優秀なアシスタントです。ユーザーの質問を分析し、適切な対応を決定してください。

## これまでの会話
{recent_history if recent_history else "（新しい会話）"}

## 現在のユーザーの質問
{query}

## 利用可能なツール
{tools_desc}

## 重要な注意事項
- ツール名はサーバー名を含めず、ツール名のみを指定してください
- 例: "calculator.add" ではなく "add" と指定
- パラメータ名は正確に指定してください（例: addツールは "a" と "b"）

## 回答形式（JSON）
{{
  "requires_tool": true/false,
  "tool_name": "ツール名のみ（サーバー名は含めない）",
  "tool_params": {{パラメータ}},
  "response": "直接回答（ツール不要の場合）"
}}
"""
        
        response = await self.llm.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        return json.loads(response.choices[0].message.content)
    
    async def _execute_tool_with_error_handling(self, analysis: Dict) -> Any:
        """エラーハンドリング付きでツールを実行"""
        tool_name = analysis["tool_name"]
        tool_params = analysis.get("tool_params", {})
        
        # サーバーとクライアントを特定
        server_name = None
        for srv_name, tools in self.collector.tools_schema.items():
            if any(t["name"] == tool_name for t in tools):
                server_name = srv_name
                break
        
        if not server_name:
            raise ValueError(f"ツール {tool_name} が見つかりません")
        
        if server_name not in self.clients:
            # サーバー未接続の場合は接続を試行
            server_info = self.collector.servers[server_name]
            
            async def connect_and_execute():
                client = Client(server_info["path"])
                await client.__aenter__()
                self.clients[server_name] = client
                result = await client.call_tool(tool_name, tool_params)
                return result
            
            # エラーハンドリング付きで実行
            error_result = await self.error_handler.handle_error(
                ConnectionError(f"サーバー {server_name} に未接続"),
                task=f"ツール実行: {tool_name}",
                retry_func=connect_and_execute
            )
            
            if error_result["success"]:
                return error_result["result"]
            else:
                raise Exception(error_result["error"])
        
        # ツール実行
        client = self.clients[server_name]
        result = await client.call_tool(tool_name, tool_params)
        self.context["tool_calls"] += 1
        
        return result
    
    async def _generate_response(self, query: str, tool_result: Any) -> str:
        """ツール結果を基に応答を生成"""
        prompt = f"""
ユーザーの質問: {query}

ツールの実行結果:
{json.dumps(tool_result, ensure_ascii=False, indent=2) if isinstance(tool_result, (dict, list)) else str(tool_result)}

この結果を基に、ユーザーの質問に対して自然で分かりやすい日本語で回答してください。
"""
        
        response = await self.llm.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": prompt}],
            temperature=0.7
        )
        
        return response.choices[0].message.content
    
    def _aggregate_task_results(self, execution_result: Dict) -> str:
        """タスク実行結果を集約"""
        lines = []
        
        lines.append(f"タスク実行が完了しました。")
        lines.append(f"- 実行タスク数: {execution_result['total_tasks']}")
        lines.append(f"- 成功: {execution_result['completed']}")
        
        if execution_result['failed'] > 0:
            lines.append(f"- 失敗: {execution_result['failed']}")
        
        if execution_result['skipped'] > 0:
            lines.append(f"- スキップ: {execution_result['skipped']}")
        
        lines.append(f"- 実行時間: {execution_result['execution_time']:.2f}秒")
        
        # 各タスクの結果
        if self.task_manager.tasks:
            lines.append("\n実行結果:")
            for task in self.task_manager.tasks.values():
                if task.status == TaskStatus.COMPLETED:
                    lines.append(f"[OK] {task.name}: {task.result}")
                elif task.status == TaskStatus.FAILED:
                    lines.append(f"[FAIL] {task.name}: {task.error}")
                elif task.status == TaskStatus.SKIPPED:
                    lines.append(f"[SKIP] {task.name}: 依存タスクの失敗")
        
        return "\n".join(lines)
    
    async def run_interactive(self):
        """対話型セッション"""
        await self.initialize()
        
        print("MCPエージェント対話モード")
        print("コマンド: exit, quit, stats, report, reset")
        print("-" * 50)
        
        while True:
            try:
                user_input = input("\nあなた> ").strip()
                
                if not user_input:
                    continue
                
                # コマンド処理
                if user_input.lower() in ["exit", "quit", "bye"]:
                    print("セッションを終了します。")
                    break
                
                elif user_input.lower() == "stats":
                    # 統計情報表示
                    print("\n[統計情報]")
                    print(f"セッション開始: {self.context['session_start']}")
                    print(f"ツール呼び出し: {self.context['tool_calls']}回")
                    print(f"エラー発生: {self.error_handler.error_stats['total']}回")
                    print(f"タスク完了: {self.context['tasks_completed']}個")
                    
                    # エラー統計
                    error_stats = self.error_handler.get_statistics()
                    if error_stats['total'] > 0:
                        print(f"エラー解決率: {error_stats['resolution_rate']:.1f}%")
                    continue
                
                elif user_input.lower() == "report":
                    # レポート表示
                    print("\n" + "=" * 50)
                    print(self.task_manager.get_report())
                    print("\n" + "=" * 50)
                    print(self.error_handler.get_report())
                    continue
                
                elif user_input.lower() == "reset":
                    # リセット
                    self.task_manager.reset()
                    self.conversation_history.clear()
                    print("タスクマネージャーと会話履歴をリセットしました。")
                    continue
                
                # 通常のクエリ処理
                print("\nエージェント> ", end="", flush=True)
                response = await self.process_query(user_input)
                print(response)
                
            except KeyboardInterrupt:
                print("\n\n中断されました。")
                break
            
            except Exception as e:
                print(f"\nエラー: {e}")
                self.context["errors"] += 1
        
        # クリーンアップ
        await self.cleanup()
    
    async def cleanup(self):
        """クリーンアップ処理"""
        print("\nクリーンアップ中...")
        
        # 最終統計
        print("\n[セッション統計]")
        session_time = (datetime.now() - self.context["session_start"]).total_seconds()
        print(f"セッション時間: {session_time:.1f}秒")
        print(f"総ツール呼び出し: {self.context['tool_calls']}回")
        print(f"総タスク完了: {self.context['tasks_completed']}個")
        print(f"総エラー: {self.error_handler.error_stats['total']}回")
        
        # MCPクライアントを閉じる
        for client in self.clients.values():
            try:
                await client.__aexit__(None, None, None)
            except:
                pass
        
        print("終了しました。")


# デモ実行
async def demo_agent():
    """エージェントのデモ"""
    print("MCPエージェントデモ\n")
    
    agent = MCPAgent(verbose=True)
    await agent.initialize()
    
    # テストクエリ
    test_queries = [
        "電卓ツールで 123 + 456 を計算してください",
        "今日の天気を教えて",
        "データベースから商品一覧を取得して分析してください"
    ]
    
    for query in test_queries:
        print(f"\n[クエリ] {query}")
        response = await agent.process_query(query)
        print(f"[応答] {response}\n")
        print("-" * 50)
    
    # 統計表示
    print("\n[最終統計]")
    print(f"ツール呼び出し: {agent.context['tool_calls']}回")
    print(f"タスク完了: {agent.context['tasks_completed']}個")
    
    # クリーンアップ
    await agent.cleanup()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        # デモモード
        asyncio.run(demo_agent())
    else:
        # 対話モード
        agent = MCPAgent(verbose=True)
        asyncio.run(agent.run_interactive())