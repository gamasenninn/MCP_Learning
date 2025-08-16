#!/usr/bin/env python3
"""
実践的なMCPエージェント - 完全版
第9章のLLM統合クライアントをエージェントに進化させた最終形
"""

import asyncio
import json
import os
import sys
import time
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
# 基本クライアント（第9章から）
# ========================

class ToolCollector:
    """MCPツール情報を収集するクラス"""
    
    def __init__(self):
        self.servers = {}
        self.tools_schema = {}
        self.connection_status = {}
    
    async def collect_all_tools(self):
        """すべてのMCPサーバーからツール情報を収集"""
        # 設定ファイルからサーバー情報を読み込み
        config_path = os.path.join(os.path.dirname(__file__), "mcp_servers.json")
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                mcp_config = json.load(f)
                
            for server_name, server_info in mcp_config.items():
                self.servers[server_name] = server_info
                self.tools_schema[server_name] = []
                self.connection_status[server_name] = "disconnected"
        
        print(f"[INFO] {len(self.servers)}個のMCPサーバーを検出")

class CompleteLLMClient:
    """LLM統合MCPクライアント（第9章の成果物）"""
    
    def __init__(self):
        self.collector = ToolCollector()
        self.llm = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.clients = {}
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
        
        # MCPクライアントを接続（利用可能なもののみ）
        for server_name, server_info in self.collector.servers.items():
            try:
                # 実際の接続処理（簡略化）
                print(f"  {server_name}: 接続をスキップ（デモモード）")
                self.collector.tools_schema[server_name] = [
                    {"name": "sample_tool", "description": "Sample tool for demo"}
                ]
            except Exception as e:
                print(f"  [WARNING] {server_name}への接続失敗: {e}")
        
        print("[完了] 初期化完了\n", flush=True)
        self._show_available_tools()
    
    def _show_available_tools(self):
        """利用可能なツールを表示"""
        total_tools = sum(len(tools) for tools in self.collector.tools_schema.values())
        print(f"[ツール] 利用可能なツール: {total_tools}個")
        for server_name, tools in self.collector.tools_schema.items():
            if tools:
                print(f"  - {server_name}: {len(tools)}個のツール")
        print()
    
    async def _execute_tool(self, server: str, tool: str, arguments: Dict) -> Any:
        """MCPツールを実行（デモ用の簡略実装）"""
        self.context["tool_calls"] += 1
        
        # デモ用の仮実装
        print(f"    実行: {server}.{tool}({arguments})")
        await asyncio.sleep(0.5)  # 実行をシミュレート
        
        # 仮の結果を返す
        if tool == "add":
            return {"result": arguments.get("a", 0) + arguments.get("b", 0)}
        elif tool == "read":
            return {"content": "ファイル内容（デモ）"}
        else:
            return {"result": "success"}

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
3. エラーが起きやすそうなステップを識別すること

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
            # LLMに計画を作成させる
            response = await self.llm.chat.completions.create(
                model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": "You are a task planning assistant."},
                    {"role": "user", "content": planning_prompt}
                ],
                temperature=0
            )
            
            # レスポンスをパース
            plan_data = json.loads(response.choices[0].message.content)
            
            # TaskStepオブジェクトに変換
            self.current_plan = [
                TaskStep(**step_data) for step_data in plan_data["plan"]
            ]
            
            print(f"[計画] {len(self.current_plan)}ステップの計画を作成")
            
        except Exception as e:
            print(f"[WARNING] 計画作成に失敗、デフォルト計画を使用: {e}")
            # デモ用のデフォルト計画
            self.current_plan = [
                TaskStep(
                    step_number=1,
                    description="タスクを実行",
                    action="tool_call",
                    parameters={"server": "demo", "tool": "execute", "arguments": {}}
                )
            ]
        
        return self.current_plan
    
    def _format_available_tools(self) -> str:
        """利用可能なツールを整形"""
        lines = []
        for server_name, tools in self.collector.tools_schema.items():
            for tool in tools:
                lines.append(
                    f"- {server_name}.{tool['name']}: "
                    f"{tool.get('description', 'No description')}"
                )
        return "\n".join(lines) if lines else "- demo.execute: デモ用ツール"
    
    async def execute_plan(self, plan: List[TaskStep]) -> Dict[str, Any]:
        """計画を実行"""
        results = {
            "success": True,
            "completed_steps": 0,
            "total_steps": len(plan),
            "outputs": []
        }
        
        print("\n[実行開始] タスクプランを実行します")
        print(f"総ステップ数: {len(plan)}\n")
        
        for step in plan:
            # 依存関係をチェック
            if not self._check_dependencies(step, plan):
                print(f"[スキップ] ステップ{step.step_number}: 依存関係が未解決")
                continue
            
            print(f"[ステップ {step.step_number}/{len(plan)}] {step.description}")
            step.status = "in_progress"
            
            try:
                # ステップを実行
                result = await self._execute_step(step)
                
                step.status = "completed"
                step.result = result
                results["completed_steps"] += 1
                results["outputs"].append(result)
                
                print(f"  [OK] 完了")
                
            except Exception as e:
                step.status = "failed"
                step.error = str(e)
                print(f"  [ERROR] 失敗: {e}")
                results["success"] = False
                break
        
        return results
    
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
            return await self._execute_tool(
                step.parameters.get("server", "demo"),
                step.parameters.get("tool", "execute"),
                step.parameters.get("arguments", {})
            )
        else:
            # その他のアクション
            await asyncio.sleep(0.3)
            return {"result": "success"}

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
        
        # 代替ファイルを探す
        if "file" in step.parameters.get("arguments", {}):
            original_file = step.parameters["arguments"]["file"]
            alternatives = [
                original_file.replace(".csv", "_backup.csv"),
                original_file.replace(".csv", "_latest.csv"),
                f"sample_{original_file}"
            ]
            
            for alt_file in alternatives:
                print(f"    [確認] {alt_file}を探しています...", end=" ")
                # 実際のファイル存在チェック（デモでは常にFalse）
                if os.path.exists(alt_file):
                    print("[見つかりました]")
                    step.parameters["arguments"]["file"] = alt_file
                    return True
                print("[なし]")
        
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
        """LLMを使って代替案を生成"""
        
        alternative_prompt = f"""
以下のステップでエラーが発生しました。代替案を提案してください。

ステップ: {step.description}
元のパラメータ: {json.dumps(step.parameters, ensure_ascii=False)}
エラー: {str(error)}

代替案をJSON形式で提案してください。
"""
        
        try:
            response = await self.llm.chat.completions.create(
                model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": "You are an error recovery assistant."},
                    {"role": "user", "content": alternative_prompt}
                ],
                temperature=0.3
            )
            
            return json.loads(response.choices[0].message.content)
        except:
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
        print("  - 'history' で履歴を表示")
        print("  - 'clear' でメモリをクリア")
        print("  - 'exit' で終了")
        print("-"*60 + "\n")
        
        while True:
            try:
                user_input = input("\nあなた> ").strip()
                
                if user_input.lower() == 'exit':
                    print("終了します")
                    break
                elif user_input.lower() == 'status':
                    self._show_session_status()
                    continue
                elif user_input.lower() == 'history':
                    self._show_history()
                    continue
                elif user_input.lower() == 'clear':
                    self._clear_memory()
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
    
    def _show_session_status(self):
        """セッション状態を表示"""
        print("\n[セッション状態]")
        print(f"完了タスク: {len(self.session_memory['completed_tasks'])}")
        print(f"保存変数: {len(self.session_memory['variables'])}")
        print(f"エラー数: {len(self.session_memory['errors'])}")
        
        if self.session_memory['completed_tasks']:
            last_task = self.session_memory['completed_tasks'][-1]
            print(f"\n最後のタスク:")
            print(f"  時刻: {last_task['timestamp']}")
            print(f"  完了: {last_task['completed']}/{last_task['steps']}")
    
    def _show_history(self):
        """履歴を表示"""
        print("\n[実行履歴]")
        if not self.session_memory['completed_tasks']:
            print("履歴がありません")
            return
        
        for i, task in enumerate(self.session_memory['completed_tasks'][-5:], 1):
            print(f"{i}. {task['timestamp']}")
            print(f"   完了: {task['completed']}/{task['steps']} ステップ")
    
    def _clear_memory(self):
        """メモリをクリア"""
        self.session_memory = {
            "variables": {},
            "completed_tasks": [],
            "errors": []
        }
        print("メモリをクリアしました")

# ========================
# カスタムエージェントの例
# ========================

class DataAnalysisAgent(PracticalMCPAgent):
    """データ分析に特化したエージェント"""
    
    def __init__(self):
        super().__init__()
        self.analysis_templates = {
            "sales": "売上データの分析と可視化",
            "customer": "顧客データのセグメンテーション",
            "inventory": "在庫最適化分析"
        }
    
    async def analyze(self, data_type: str, **options):
        """定型的な分析を実行"""
        template = self.analysis_templates.get(data_type)
        if not template:
            raise ValueError(f"Unknown data type: {data_type}")
        
        # オプションを文字列化
        options_str = ", ".join(f"{k}={v}" for k, v in options.items())
        task = f"{template}を実行"
        if options_str:
            task += f"。条件: {options_str}"
        
        return await self.execute(task, auto_approve=True)

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
    await agent.initialize()
    
    if mode == "interactive":
        # 対話モード
        await agent.interactive_session()
    elif mode == "demo":
        # デモ実行
        print("[デモモード]")
        result = await agent.execute(
            "100と200を足して、その結果を2倍にしてください",
            auto_approve=True
        )
        print(f"\n最終結果: {result}")
    elif mode == "analysis":
        # データ分析エージェントのデモ
        analyst = DataAnalysisAgent()
        await analyst.initialize()
        result = await analyst.analyze(
            "sales",
            period="2024Q1",
            metrics=["revenue", "growth"]
        )
        print(f"\n分析結果: {result}")
    else:
        print(f"Unknown mode: {mode}")
        print("Usage: python practical_mcp_agent.py [interactive|demo|analysis]")

if __name__ == "__main__":
    # 実行
    asyncio.run(main())