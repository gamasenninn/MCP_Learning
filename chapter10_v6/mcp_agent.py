#!/usr/bin/env python3
"""
MCP Agent - Interactive Dialogue Engine
Claude Code風の対話型エージェント

主な特徴：
- 対話的逐次実行（依存関係の自動解決）
- チェックボックス付きタスク表示
- リアルタイムプログレス
- 過去バージョンの知見を活かした設計
"""

import os
import json
import asyncio
import time
import yaml
from typing import Dict, List, Any, Optional
from datetime import datetime
from openai import AsyncOpenAI

from connection_manager import ConnectionManager
from display_manager import DisplayManager
from error_handler import ErrorHandler
from prompts import PromptTemplates
from utils import Logger, safe_str
from state_manager import StateManager, TaskState
from task_manager import TaskManager

# Rich UI support
try:
    from display_manager_rich import RichDisplayManager
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False




class MCPAgent:
    """
    Claude Code風の対話型MCPエージェント
    
    過去バージョンから引き継いだ要素:
    - AGENT.mdによるカスタマイズ
    - 会話文脈の活用
    - NO_TOOL判定
    
    現在の主要機能:
    - 対話的逐次実行
    - ステップバイステップの可視化
    - 依存関係の自動解決
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        """初期化"""
        self.config = self._load_config(config_path)
        
        # UI モードに基づいて適切なDisplayManagerを選択
        ui_mode = self.config.get("display", {}).get("ui_mode", "basic")
        
        if ui_mode == "rich" and RICH_AVAILABLE:
            self.display = RichDisplayManager(
                show_timing=self.config["display"]["show_timing"],
                show_thinking=self.config["display"]["show_thinking"]
            )
            self.ui_mode = "rich"
        else:
            if ui_mode == "rich" and not RICH_AVAILABLE:
                print("[WARNING] Rich UI requested but rich library not available. Using basic UI.")
            self.display = DisplayManager(
                show_timing=self.config["display"]["show_timing"],
                show_thinking=self.config["display"]["show_thinking"]
            )
            self.ui_mode = "basic"
        
        # LLMクライアント
        self.llm = AsyncOpenAI()
        
        # MCP接続管理（V3から流用）
        self.connection_manager = ConnectionManager()
        
        # エラー処理司令塔（V4新機能）
        self.error_handler = ErrorHandler(
            config=self.config,
            llm=self.llm,
            verbose=self.config.get("development", {}).get("verbose", True)
        )
        
        # 状態管理システム（V6新機能）
        self.state_manager = StateManager()
        self.task_manager = TaskManager(self.state_manager, self.llm)
        
        # 会話履歴（V3から継承）
        self.conversation_history: List[Dict] = []
        
        # セッション統計
        self.session_stats = {
            "start_time": datetime.now(),
            "total_requests": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "total_api_calls": 0
        }
        
        # 実行メトリクス（新機能）
        self.execution_metrics = {
            "task_generation_success": 0,
            "task_generation_failures": 0,
            "task_generation_retry_success": 0,
            "task_generation_total_failures": 0,
            "json_parse_errors": 0,
            "timeout_count": 0,
            "fallback_usage": 0,
            "average_task_count": 0.0,
            "total_task_lists": 0
        }
        
        # AGENT.md読み込み（V3から継承）
        self.custom_instructions = self._load_agent_md()
        
        # Loggerを初期化
        self.verbose = self.config.get("development", {}).get("verbose", True)
        self.logger = Logger(verbose=self.verbose)
        
        if self.verbose:
            self.display.show_banner()
            if self.ui_mode == "rich":
                self.logger.info("Rich UI mode enabled")
            else:
                self.logger.info("Basic UI mode enabled")
    
    def _load_config(self, config_path: str) -> Dict:
        """設定ファイルを読み込み（必須）"""
        if not os.path.exists(config_path):
            raise FileNotFoundError(
                f"設定ファイル '{config_path}' が見つかりません。\n"
                f"'config.sample.yaml' を '{config_path}' にコピーしてください。"
            )
        
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    
    def _load_agent_md(self) -> str:
        """AGENT.mdを読み込み（V3から継承）"""
        agent_md_path = "AGENT.md"
        
        if os.path.exists(agent_md_path):
            try:
                with open(agent_md_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if hasattr(self, 'logger'):
                    self.logger.config_info(f"AGENT.mdを読み込みました ({len(content)}文字)")
                elif self.config.get("development", {}).get("verbose", False):
                    print(f"[設定] AGENT.mdを読み込みました ({len(content)}文字)")
                return content
            except Exception as e:
                print(f"[警告] AGENT.md読み込みエラー: {e}")
                return ""
        else:
            if self.config.get("development", {}).get("verbose", False):
                print("[情報] AGENT.mdが見つかりません（基本能力のみで動作）")
            return ""
    
    async def initialize(self, session_id: Optional[str] = None):
        """エージェントの初期化"""
        if self.verbose:
            print(f"\n[指示書] {'カスタム指示あり' if self.custom_instructions else '基本能力のみ'}")
            print("=" * 60)
        
        # MCP接続管理を初期化（V3から継承）
        await self.connection_manager.initialize()
        
        # セッション状態を初期化（V6新機能）
        actual_session_id = await self.state_manager.initialize_session(session_id)
        
        if self.verbose:
            print(f"[セッション] {actual_session_id}")
            
            # 復元されたタスクがある場合は通知
            if self.state_manager.has_pending_tasks():
                pending_count = len(self.state_manager.get_pending_tasks())
                print(f"[復元] 未完了タスクが{pending_count}個あります")
        
        return actual_session_id
    
    async def process_request(self, user_query: str) -> str:
        """
        ユーザーリクエストを対話的に処理（核心機能）
        
        特徴:
        - 一度に全タスクを分解せず、ステップごとに対話
        - 前の結果を見てから次の行動を決定
        - 実行過程を視覚的に表示
        """
        self.session_stats["total_requests"] += 1
        
        if self.verbose:
            print(f"\n[リクエスト #{self.session_stats['total_requests']}] {user_query}")
            print("-" * 60)
        
        # 会話文脈を表示
        context_count = min(len(self.conversation_history), 
                          self.config["conversation"]["context_limit"])
        if context_count > 0:
            self.display.show_context_info(context_count)
        
        try:
            # 対話的実行の開始
            response = await self._execute_interactive_dialogue(user_query)
            
            # 会話履歴に追加（V3から継承）
            # 実行結果については各実行メソッドで追加される
            self._add_to_history("user", user_query)
            
            return response
            
        except Exception as e:
            error_msg = f"処理エラー: {str(e)}"
            if self.verbose:
                print(f"[エラー] {error_msg}")
            return error_msg
    
    async def _execute_interactive_dialogue(self, user_query: str) -> str:
        """
        V6統合実行エンジン - 状態管理とCLARIFICATION対応
        
        新機能:
        - 状態の永続化
        - CLARIFICATIONタスクによるユーザー確認
        - タスクの中断・再開機能
        """
        # 現在のクエリを保存（LLM判断で使用）
        self.current_user_query = user_query
        
        # 状態に会話を記録
        await self.state_manager.add_conversation_entry("user", user_query)
        
        # 未完了のタスクがある場合の処理
        if self.state_manager.has_pending_tasks():
            return await self._handle_pending_tasks(user_query)
        
        self.display.show_analysis("リクエストを分析中...")
        
        # まず処理方式を判定（CLARIFICATION対応版）
        execution_result = await self._determine_execution_type_v6(user_query)
        execution_type = execution_result.get("type", "SIMPLE")
        
        # 状態に実行タイプを記録
        await self.state_manager.set_user_query(user_query, execution_type)
        
        if execution_type == "NO_TOOL":
            response = execution_result.get("response", "了解しました。")
            await self.state_manager.add_conversation_entry("assistant", response)
            self._add_to_history("assistant", response)
            return response
        elif execution_type == "CLARIFICATION":
            # ユーザーへの確認が必要
            return await self._handle_clarification_needed(user_query, execution_result)
        else:
            # SIMPLE/COMPLEX統合：全てのツール実行要求を統一メソッドで処理
            return await self._execute_with_tasklist_v6(user_query)
    
    async def _determine_execution_type_v6(self, user_query: str) -> Dict:
        """V6版: CLARIFICATION対応の実行方式判定"""
        recent_context = self._get_recent_context()
        
        # 利用可能なツール情報を取得
        tools_info = self.connection_manager.format_tools_for_llm()
        
        # プロンプトテンプレートから取得（V6対応版）
        prompt = PromptTemplates.get_execution_type_determination_prompt_v6(
            recent_context=recent_context,
            user_query=user_query,
            tools_info=tools_info
        )

        try:
            response = await self.llm.chat.completions.create(
                model=self.config["llm"]["model"],
                messages=[{"role": "system", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            content = safe_str(response.choices[0].message.content)
            result = json.loads(content)
            
            # V6版では CLARIFICATION も含む
            # SIMPLE/COMPLEX統合のため、NO_TOOL, CLARIFICATION以外は全てTOOLに統一
            if result.get('type') in ['SIMPLE', 'COMPLEX']:
                result['type'] = 'TOOL'
            
            
            self.logger.info(f"判定: {result.get('type', 'UNKNOWN')} - {result.get('reason', '')}")
            
            return result
            
        except Exception as e:
            print(f"[エラー] 実行方式判定失敗: {e}")
            return {"type": "TOOL", "reason": "判定エラーによりデフォルト選択"}
    
    async def _handle_pending_tasks(self, user_query: str) -> str:
        """未完了タスクがある場合の処理"""
        pending_tasks = self.state_manager.get_pending_tasks()
        
        # CLARIFICATIONタスクがある場合
        if self.task_manager.has_clarification_tasks():
            for task in pending_tasks:
                if task.tool == "CLARIFICATION" and task.status == "pending":
                    # CLARIFICATIONタスクを完了としてマーク
                    await self.state_manager.move_task_to_completed(task.task_id, {"user_response": user_query})
                    
                    # 元のクエリとユーザー応答を組み合わせて新しいクエリを作成
                    original_query = task.params.get("user_query", "")
                    question = task.params.get("question", "")
                    
                    # より明確な形式でLLMが理解しやすく構成
                    combined_query = f"{original_query}。{user_query}。"
                    
                    # 状態をリセットして新しいクエリとして処理
                    await self.state_manager.set_user_query(combined_query, "TOOL")
                    
                    # LLMに新しいタスクリストを生成させる
                    return await self._execute_with_tasklist_v6(combined_query)
        
        # 通常のタスクを継続実行
        return await self._continue_pending_tasks(user_query)
    
    async def _handle_clarification_needed(self, user_query: str, execution_result: Dict) -> str:
        """CLARIFICATION必要時の処理"""
        clarification_info = execution_result.get('clarification', {})
        
        # CLARIFICATIONタスクを生成
        clarification_task = TaskState(
            task_id=f"clarification_{int(time.time())}",
            tool="CLARIFICATION",
            params={
                "question": clarification_info.get('question', '詳細情報をお教えください'),
                "context": f"要求: {user_query}",
                "user_query": user_query
            },
            description="ユーザーに確認",
            status="pending"
        )
        
        await self.state_manager.add_pending_task(clarification_task)
        
        # CLARIFICATIONタスクを実行
        return await self.task_manager.execute_clarification_task(clarification_task)
    
    async def _handle_clarification_task(self, task: TaskState) -> str:
        """CLARIFICATIONタスクの処理"""
        return await self.task_manager.execute_clarification_task(task)
    
    async def _continue_pending_tasks(self, user_query: str) -> str:
        """保留中タスクの継続実行"""
        next_task = self.task_manager.get_next_executable_task()
        
        if not next_task:
            return "実行可能なタスクがありません。"
        
        # タスクを実行
        return await self._execute_single_task_v6(next_task)
    
    async def _execute_single_task_v6(self, task: TaskState) -> str:
        """単一タスクのV6実行"""
        try:
            # 依存関係を解決
            completed_tasks = self.state_manager.get_completed_tasks()
            resolved_task = await self.task_manager.resolve_task_dependencies(task, completed_tasks)
            
            # タスクを実行
            result = await self.connection_manager.call_tool(resolved_task.tool, resolved_task.params)
            
            # 結果を安全な形式に変換
            safe_result = safe_str(result)
            
            # 結果を状態に保存
            await self.state_manager.move_task_to_completed(task.task_id, safe_result)
            
            return f"タスクが完了しました: {task.description}\n結果: {safe_result}"
            
        except Exception as e:
            await self.state_manager.move_task_to_completed(task.task_id, error=str(e))
            return f"タスク実行エラー: {task.description}\nエラー: {str(e)}"
    
    async def _execute_with_tasklist_v6(self, user_query: str) -> str:
        """V6版タスクリスト実行メソッド - 状態管理対応"""
        
        # V6用のシンプルなタスク生成
        task_list_spec = await self._generate_simple_task_list_v6(user_query)
        
        if not task_list_spec:
            error_msg = (f"申し訳ありません。{user_query}の処理方法を決定できませんでした。\n"
                       f"別の表現で再度お試しください。")
            return error_msg
        
        # TaskStateオブジェクトを生成（CLARIFICATION処理を含む）
        tasks = await self.task_manager.create_tasks_from_list(task_list_spec, user_query)
        
        # タスクを状態管理に追加
        for task in tasks:
            await self.state_manager.add_pending_task(task)
        
        # CLARIFICATIONタスクが生成された場合は優先処理
        if self.task_manager.has_clarification_tasks():
            clarification_task = None
            for task in tasks:
                if task.tool == "CLARIFICATION":
                    clarification_task = task
                    break
            
            if clarification_task:
                return await self._handle_clarification_task(clarification_task)
        
        # 通常のタスクリスト実行
        return await self._execute_task_sequence_v6(tasks, user_query)
    
    async def _execute_task_sequence_v6(self, tasks: List[TaskState], user_query: str) -> str:
        """V6版タスク順次実行"""
        
        # チェックリストを表示（既存の表示ロジックを使用）
        task_list_for_display = [
            {
                "tool": task.tool,
                "description": task.description,
                "params": task.params
            }
            for task in tasks if task.tool != "CLARIFICATION"
        ]
        
        if task_list_for_display:
            # V6用のシンプル表示
            print("\n[タスク一覧]")
            for i, task in enumerate(task_list_for_display):
                print(f"  [ ] {task['description']}")
        
        # 実行結果を追跡
        completed = []
        failed = []
        execution_context = []
        
        # タスクを順次実行
        executable_tasks = [t for t in tasks if t.tool != "CLARIFICATION"]
        
        for i, task in enumerate(executable_tasks):
            # V6用のシンプル進行状況表示
            print(f"\n[実行中] {task.description}...")
            
            # LLMベースでパラメータを解決
            resolved_params = await self._generate_params_with_llm_v6(task, execution_context)
            
            # タスク実行（リトライ機能付き）
            start_time = time.time()
            result = await self._execute_tool_with_retry(
                tool=task.tool,
                params=resolved_params,
                description=task.description
            )
            duration = time.time() - start_time
            
            # 結果を安全な形式に変換
            safe_result = safe_str(result)
            
            # 成功時の処理
            await self.state_manager.move_task_to_completed(task.task_id, safe_result)
            completed.append(i)
            print(f"[完了] {task.description}")
            
            execution_context.append({
                "success": True,
                "result": safe_result,
                "duration": duration,
                "task_description": task.description
            })
        
        # V6用の最終状況表示
        if completed:
            print(f"\n[完了] {len(completed)}個のタスクが正常完了")
        if failed:
            print(f"[失敗] {len(failed)}個のタスクでエラーが発生")
        
        # 結果をLLMで解釈
        return await self._interpret_planned_results(user_query, execution_context)
    
    def _format_context_for_llm(self, execution_context: List[Dict]) -> str:
        """実行コンテキストをLLM用に整形"""
        if not execution_context:
            return "（まだ実行結果なし）"
        
        formatted_context = []
        for i, ctx in enumerate(execution_context, 1):
            tool = ctx.get("tool", "不明")
            result = safe_str(ctx.get("result", ""))[:200]  # 最初の200文字
            description = ctx.get("description", f"{tool}を実行")
            
            formatted_context.append(f"ステップ{i}: {description}")
            formatted_context.append(f"  ツール: {tool}")
            formatted_context.append(f"  結果: {result}")
            if len(safe_str(ctx.get("result", ""))) > 200:
                formatted_context.append("  （結果が長いため省略...）")
        
        return "\n".join(formatted_context)
    
    async def _generate_params_with_llm_v6(self, task: TaskState, execution_context: List[Dict]) -> Dict:
        """V6用: LLMが実行文脈を理解して直接パラメータを生成"""
        tool = task.tool
        params = task.params
        description = task.description
        
        # 実行文脈から結果情報を抽出
        context_info = []
        if execution_context:
            for i, ctx in enumerate(execution_context):
                if ctx.get("success"):
                    result_str = str(ctx.get("result", ""))
                    task_desc = ctx.get("task_description", "不明なタスク")
                    context_info.append(f"タスク{i+1}: {task_desc} → 結果: {result_str}")
        
        context_str = "\n".join(context_info) if context_info else "前の実行結果はありません"
        
        prompt = f"""次のタスクを実行するためのパラメータを、実行履歴から適切に決定してください。

## 実行するタスク
- ツール: {tool}
- 説明: {description}
- 元のパラメータ: {json.dumps(params, ensure_ascii=False)}

## これまでの実行履歴
{context_str}

## 指示
前の実行結果を参考にして、このタスクに最適なパラメータを決定してください。
前のタスクの数値結果を使う場合は、その数値を直接パラメータに設定してください。

## 出力形式（JSON）
```json
{{
  "resolved_params": {{実際のパラメータ値}},
  "reasoning": "パラメータを決定した理由"
}}
```"""

        try:
            response = await self.llm.chat.completions.create(
                model=self.config["llm"]["model"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            response_text = response.choices[0].message.content
            
            # JSONブロックを抽出
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
                resolved_params = result.get("resolved_params", params)
                reasoning = result.get("reasoning", "")
                
                if self.verbose:
                    print(f"[V6パラメータ解決] {reasoning}")
                
                return resolved_params
            
            if self.verbose:
                print(f"[V6パラメータ解決失敗] JSON解析エラー: {response_text[:100]}...")
            return params
            
        except Exception as e:
            if self.verbose:
                print(f"[V6パラメータ解決エラー] {e}")
            return params
    
    def _build_judgment_prompt(
        self, 
        tool: str, 
        current_params: Dict,
        original_params: Dict,
        result: Any,
        attempt: int,
        max_retries: int,
        description: str
    ) -> str:
        """LLM判断用プロンプトの生成"""
        # 結果を安全な文字列に変換
        result_str = safe_str(result)
        current_params_str = safe_str(current_params)
        original_params_str = safe_str(original_params)
        
        # 現在の会話文脈を取得
        current_query = getattr(self, 'current_user_query', '（不明）')
        
        return f"""あなたはツール実行結果を判断するエキスパートです。以下の実行結果を分析してください。

## 現在実行中のタスク
タスク: {description or "タスクの説明なし"}

## 実行情報
- ツール名: {tool}
- 現在のパラメータ: {current_params_str}
- 元のパラメータ: {original_params_str}
- 試行回数: {attempt}/{max_retries + 1}
- ユーザーの要求: {current_query}

## 実行結果
{result_str}

## 判断基準
1. **成功判定**: 期待される結果が得られている
2. **失敗判定**: エラーメッセージ、構文エラー、実行エラーが含まれている
3. **リトライ判定**: パラメータを修正すれば成功する可能性がある

## **重要**: パラメータ修正時のルール
- **現在実行中のタスクの目的を必ず尊重してください**
- 修正は元のパラメータ（{original_params_str}）を基準に行ってください
- 他のタスクのパラメータに変更してはいけません
- 例：都市名に国コードを追加（例："Tokyo" → "Tokyo, JP"）

## 出力形式（JSON）
{{
    "is_success": boolean,
    "needs_retry": boolean,
    "error_reason": "エラーの理由（失敗時のみ）",
    "corrected_params": {{元のパラメータを基準とした修正案}},
    "processed_result": "ユーザー向けの整形済み結果",
    "summary": "実行結果の要約"
}}

## 修正例
- 構文エラー → コードを正しい構文に修正
- 都市名エラー → 国コード付きに修正
- 日本語パラメータ → 英語に変換
- セミコロン記法 → 複数行に分解"""
    
    async def _call_llm_for_judgment(self, prompt: str) -> Dict:
        """LLMに判断を依頼してJSON結果を返す"""
        try:
            response = await self.llm.chat.completions.create(
                model=self.config["llm"]["model"],
                messages=[{"role": "system", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            raw_response = response.choices[0].message.content
            self.logger.debug(f"[LLM生レスポンス] {safe_str(raw_response)[:500]}")
            
            return json.loads(raw_response)
            
        except Exception as e:
            self.logger.error(f"[LLM判断エラー] {e}")
            # フォールバック: 成功として扱う
            return {
                "is_success": True,
                "needs_retry": False,
                "processed_result": "LLM判断に失敗しました。結果をそのまま表示します。",
                "summary": "LLM判断エラーによるフォールバック"
            }
    
    def _log_judgment_result(self, judgment: Dict):
        """判断結果の詳細ログ出力"""
        self.logger.info(f"[LLM判断] 成功: {judgment.get('is_success')}, リトライ必要: {judgment.get('needs_retry')}")
        
        if judgment.get('needs_retry'):
            self.logger.info(f"[LLM理由] {judgment.get('error_reason', '不明')}")
            if judgment.get('corrected_params'):
                self.logger.info(f"[LLM修正案] {safe_str(judgment.get('corrected_params'))[:200]}")
        else:
            self.logger.info(f"[LLM判断理由] リトライ不要 - {judgment.get('summary', '詳細不明')}")
    
    async def _generate_adaptive_task_list(self, user_query: str, temperature: float = 0.1) -> List[Dict]:
        """
        クエリの複雑さに応じて適応的にタスクリストを生成
        
        Args:
            user_query: ユーザークエリ
            temperature: LLMの温度パラメータ
            
        Returns:
            生成されたタスクリスト
        """
        recent_context = self._get_conversation_context_only()
        tools_info = self.connection_manager.format_tools_for_llm()
        
        # カスタム指示の有無で複雑さを判定
        custom_instructions = self.custom_instructions if self.custom_instructions.strip() else None
        
        # プロンプトテンプレートから取得
        prompt = PromptTemplates.get_adaptive_task_list_prompt(
            recent_context=recent_context,
            user_query=user_query,
            tools_info=tools_info,
            custom_instructions=custom_instructions
        )

        try:
            self.session_stats["total_api_calls"] += 1
            
            response = await self.llm.chat.completions.create(
                model=self.config["llm"]["model"],
                messages=[{"role": "system", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=temperature
            )
            
            content = safe_str(response.choices[0].message.content)
            result = json.loads(content)
            tasks = result.get("tasks", [])
            
            # タスク数に応じてログ出力
            task_type_label = "詳細" if custom_instructions else "シンプル"
            self.logger.info(f"{task_type_label}タスク: {len(tasks)}個のタスクを生成")
            for i, task in enumerate(tasks, 1):
                self.logger.debug(f"  [{i}] Tool: {task.get('tool')}, Params: {safe_str(task.get('params', {}))[:100]}...")
                self.logger.debug(f"      Description: {task.get('description', 'N/A')}")
            
            # シンプルな場合は最大3タスクに制限
            if not custom_instructions and len(tasks) > 3:
                self.logger.info(f"タスク数制限: {len(tasks)} → 3（シンプルモード）")
                tasks = tasks[:3]
            
            return tasks
            
        except Exception as e:
            print(f"[エラー] 適応的タスクリスト生成失敗: {e}")
            return []
    
    async def _generate_task_list_with_retry(self, user_query: str) -> List[Dict]:
        """
        リトライ機能付き適応的タスクリスト生成
        
        Args:
            user_query: ユーザークエリ
            
        Returns:
            生成されたタスクリスト
        """
        retry_config = self.config.get("execution", {}).get("retry_strategy", {})
        max_retries = retry_config.get("max_retries", 3)
        use_progressive = retry_config.get("progressive_temperature", True)
        initial_temp = retry_config.get("initial_temperature", 0.1)
        temp_increment = retry_config.get("temperature_increment", 0.2)
        
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # プログレッシブtemperature調整
                if use_progressive and attempt > 0:
                    temperature = min(initial_temp + (attempt * temp_increment), 0.9)
                else:
                    temperature = initial_temp
                
                # 統一された適応的タスクリスト生成を使用
                task_list = await self._generate_adaptive_task_list(user_query, temperature)
                
                if task_list:
                    # 成功時はメトリクスを更新
                    if hasattr(self, 'execution_metrics'):
                        self.execution_metrics['task_generation_success'] += 1
                        if attempt > 0:
                            self.execution_metrics['task_generation_retry_success'] += 1
                    
                    if attempt > 0:
                        self.logger.info(f"[成功] タスクリスト生成 - {attempt + 1}回目の試行で成功")
                    
                    # タスク数制限（全体的な上限）
                    max_tasks = self.config.get("execution", {}).get("max_tasks", 10)
                    if len(task_list) > max_tasks:
                        self.logger.warning(f"タスク数制限: {len(task_list)} → {max_tasks}")
                        task_list = task_list[:max_tasks]
                    
                    return task_list
                else:
                    last_error = f"試行{attempt + 1}: 空のタスクリストが生成されました"
                    
            except json.JSONDecodeError as e:
                last_error = f"試行{attempt + 1}: JSON解析エラー - {str(e)}"
                self.logger.info(f"[リトライ] {last_error}")
            except Exception as e:
                last_error = f"試行{attempt + 1}: {str(e)}"
                self.logger.info(f"[リトライ] {last_error}")
            
            # メトリクス更新
            if hasattr(self, 'execution_metrics'):
                self.execution_metrics['task_generation_failures'] += 1
        
        # 全ての試行が失敗
        self.logger.error(f"[失敗] タスクリスト生成 - {max_retries}回の試行全てが失敗")
        self.logger.error(f"最後のエラー: {last_error}")
        
        if hasattr(self, 'execution_metrics'):
            self.execution_metrics['task_generation_total_failures'] += 1
            
        return []

    
    
    async def _execute_tool_with_retry(self, tool: str, params: Dict, description: str = "") -> Any:
        """
        LLMベースの賢いツール実行・判断システム
        
        Args:
            tool: ツール名
            params: 実行パラメータ
            description: タスクの説明（LLM判断時のコンテキスト）
        """
        self.logger.info(f"[DEBUG] _execute_tool_with_retry が呼び出されました: tool={tool}")
        max_retries = 3
        
        # 元のパラメータを保持（破壊的変更を避ける）
        original_params = params.copy()
        current_params = params.copy()
        
        for attempt in range(max_retries + 1):
            # 1. ツール実行（例外もキャッチして結果として扱う）
            try:
                raw_result = await self.connection_manager.call_tool(tool, current_params)
                self.logger.info(f"[DEBUG] ツール実行成功 attempt={attempt + 1}, result_type={type(raw_result)}")
            except Exception as e:
                # 例外も「結果」として扱い、LLM判断に回す
                raw_result = f"ツールエラー: {e}"
                self.logger.info(f"[DEBUG] ツール実行でエラー発生 attempt={attempt + 1}, error={type(e).__name__}")
            
            # 2. LLMに結果を判断させる（成功・失敗問わず）
            try:
                self.logger.info(f"[DEBUG] LLM判断を開始...")
                judgment = await self._judge_and_process_result(
                    tool=tool,
                    current_params=current_params,
                    original_params=original_params,
                    result=raw_result,
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    description=description
                )
                self.logger.info(f"[DEBUG] LLM判断完了")
                
            except Exception as e:
                self.logger.error(f"[DEBUG] LLM判断でエラー発生: {type(e).__name__}: {e}")
                # LLM判断でエラーの場合は、結果をそのまま返す
                return raw_result
            
            # 3. LLMの判断に基づいて行動
            if judgment.get("needs_retry", False) and attempt < max_retries:
                self.logger.info(f"[リトライ] {attempt + 1}/{max_retries}: {judgment.get('error_reason', 'LLM判断によるリトライ')}")
                
                # 修正されたパラメータで再実行（元のparamsは保持）
                corrected_params = judgment.get("corrected_params", current_params)
                if corrected_params != current_params:
                    self.logger.info(f"[修正] パラメータを修正: {safe_str(corrected_params)}")
                    current_params = corrected_params
                
                continue
            
            # 成功または最大リトライ回数到達
            return judgment.get("processed_result", raw_result)
        
        # 最大リトライ回数に到達
        return judgment.get("processed_result", "最大リトライ回数に到達しました。")
    
    async def _judge_and_process_result(
        self, 
        tool: str, 
        current_params: Dict,
        original_params: Dict, 
        result: Any,
        attempt: int = 1,
        max_retries: int = 3,
        description: str = ""
    ) -> Dict[str, Any]:
        """
        LLMによるツール実行結果の判断と処理（リファクタリング版）
        
        Args:
            tool: ツール名
            current_params: 現在実行したパラメータ
            original_params: 元のパラメータ（修正の基準）
            result: ツール実行結果
            attempt: 現在の試行回数
            max_retries: 最大リトライ回数
            description: 現在実行中のタスクの説明
            
        Returns:
            判断結果辞書
        """
        # プロンプト生成
        prompt = self._build_judgment_prompt(
            tool=tool,
            current_params=current_params,
            original_params=original_params,
            result=result,
            attempt=attempt,
            max_retries=max_retries,
            description=description
        )
        
        # LLM呼び出し
        judgment = await self._call_llm_for_judgment(prompt)
        
        # ログ出力
        self._log_judgment_result(judgment)
        
        return judgment
    
    
    async def _interpret_planned_results(self, user_query: str, results: List[Dict]) -> str:
        """計画実行の結果を解釈"""
        # 現在のリクエストのみに焦点を当て、前のタスク結果の混入を防ぐ
        recent_context = self._get_conversation_context_only()
        
        # 結果をシリアライズ（V6対応）
        serializable_results = []
        for r in results:
            result_data = {
                "step": r.get("step", r.get("task_description", "タスク")),
                "tool": r.get("tool", "不明"),
                "success": r["success"],
                "description": r.get("description", r.get("task_description", "実行完了"))
            }
            
            if r["success"]:
                # 成功時は結果を含める
                max_length = self.config.get("result_display", {}).get("max_result_length", 1000)
                result_str = str(r["result"])
                
                if len(result_str) <= max_length:
                    result_data["result"] = result_str
                else:
                    # 長すぎる場合は省略情報を追加
                    result_data["result"] = result_str[:max_length]
                    if self.config.get("result_display", {}).get("show_truncated_info", True):
                        result_data["result"] += f"\n[注記: 結果が長いため{max_length}文字で省略。実際の結果はより多くのデータを含む可能性があります]"
            else:
                result_data["error"] = r["error"]
            
            serializable_results.append(result_data)
        
        # デバッグ: LLMに渡されるデータを確認
        if self.verbose:
            self.logger.debug("Serializable results being sent to LLM:")
            for i, result in enumerate(serializable_results):
                result_preview = str(result.get("result", "N/A"))[:100] + "..." if len(str(result.get("result", "N/A"))) > 100 else str(result.get("result", "N/A"))
                self.logger.debug(f"  [{i+1}] Tool: {result['tool']}, Result: {result_preview}")
        
        # プロンプトテンプレートから取得
        prompt = PromptTemplates.get_result_interpretation_prompt(
            recent_context=recent_context,
            user_query=user_query,
            serializable_results=json.dumps(serializable_results, ensure_ascii=False, indent=2),
            custom_instructions=self.custom_instructions
        )

        try:
            response = await self.llm.chat.completions.create(
                model=self.config["llm"]["model"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            # 最終応答を取得
            final_response = response.choices[0].message.content
            
            # Rich UIの場合は美しく表示
            if self.ui_mode == "rich" and hasattr(self.display, 'show_result_panel'):
                # JSONまたは長いテキストかどうか判定
                if len(final_response) > 100 or final_response.strip().startswith('{'):
                    self.display.show_result_panel("実行結果", final_response, success=True)
                
            # 実行結果と共に履歴に保存
            self._add_to_history("assistant", final_response, serializable_results)
            
            return final_response
            
        except Exception as e:
            # フォールバック
            successful_results = [r for r in results if r["success"]]
            if successful_results:
                return f"実行完了しました。{len(successful_results)}個のタスクが成功しました。"
            else:
                return f"申し訳ありませんが、処理中にエラーが発生しました。"
    
    def _get_recent_context(self, max_items: int = None) -> str:
        """最近の会話文脈を取得（V6版: 状態管理から）"""
        if max_items is None:
            max_items = self.config["conversation"]["context_limit"]
        
        # 状態管理から会話履歴を取得
        conversation_context = self.state_manager.get_conversation_context(max_items)
        
        if not conversation_context:
            return ""
        
        lines = []
        for entry in conversation_context:
            role = "User" if entry['role'] == "user" else "Assistant"
            # 長いメッセージは省略
            msg = entry['content'][:150] + "..." if len(entry['content']) > 150 else entry['content']
            timestamp = entry.get('timestamp', '')
            if timestamp:
                time_str = timestamp.split('T')[1][:5] if 'T' in timestamp else timestamp
                lines.append(f"[{time_str}] {role}: {msg}")
            else:
                lines.append(f"{role}: {msg}")
        
        return "\n".join(lines)
    
    def _get_conversation_context_only(self, max_items: int = 3) -> str:
        """
        会話文脈のみを取得（実行結果を除外）
        結果解釈時に前のタスク結果の混入を防ぐ
        """
        # V6では状態管理から会話履歴を取得
        conversation_context = self.state_manager.get_conversation_context(max_items)
        
        if not conversation_context:
            return ""
        
        lines = []
        for entry in conversation_context:
            role = "User" if entry['role'] == "user" else "Assistant"
            # 長いメッセージは省略
            msg = entry['content'][:150] + "..." if len(entry['content']) > 150 else entry['content']
            lines.append(f"{role}: {msg}")
            # 実行結果は含めない（混入を防ぐため）
        
        return "\n".join(lines)
    
    def _summarize_results(self, results: List[Dict]) -> str:
        """実行結果を要約して表示"""
        summary_parts = []
        for r in results:
            tool = r.get('tool', 'Unknown')
            success = r.get('success', False)
            
            if success and r.get('result'):
                result_str = str(r['result'])
                # 結果が長い場合は短縮
                if len(result_str) > 100:
                    result_str = result_str[:97] + "..."
                summary_parts.append(f"{tool}: {result_str}")
            else:
                summary_parts.append(f"{tool}: {'成功' if success else '失敗'}")
        
        return " | ".join(summary_parts[:3])  # 最大3つの結果を表示
    
    def _add_to_history(self, role: str, message: str, execution_results: List[Dict] = None):
        """会話履歴に追加（実行結果も含む）"""
        history_item = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "message": message
        }
        
        # 実行結果があれば追加
        if execution_results:
            history_item["execution_results"] = execution_results
        
        self.conversation_history.append(history_item)
        
        # 履歴の長さ制限
        max_history = self.config["conversation"]["max_history"]
        if len(self.conversation_history) > max_history:
            self.conversation_history = self.conversation_history[-max_history:]
    
    def _show_execution_metrics(self):
        """実行メトリクスを表示"""
        if not self.config.get("development", {}).get("show_statistics", True):
            return
            
        print("\n" + "=" * 50)
        print("📊 実行メトリクス")
        print("=" * 50)
        
        # タスクリスト生成統計
        total_attempts = (self.execution_metrics["task_generation_success"] + 
                         self.execution_metrics["task_generation_total_failures"])
        if total_attempts > 0:
            success_rate = (self.execution_metrics["task_generation_success"] / total_attempts) * 100
            print(f"タスクリスト生成成功率: {success_rate:.1f}% ({self.execution_metrics['task_generation_success']}/{total_attempts})")
        
        if self.execution_metrics["task_generation_retry_success"] > 0:
            print(f"リトライ成功: {self.execution_metrics['task_generation_retry_success']}回")
        
        if self.execution_metrics["json_parse_errors"] > 0:
            print(f"JSON解析エラー: {self.execution_metrics['json_parse_errors']}回")
            
        if self.execution_metrics["timeout_count"] > 0:
            print(f"タイムアウト発生: {self.execution_metrics['timeout_count']}回")
            
        if self.execution_metrics["fallback_usage"] > 0:
            print(f"フォールバック使用: {self.execution_metrics['fallback_usage']}回")
        
        if self.execution_metrics["total_task_lists"] > 0:
            avg_tasks = self.execution_metrics["average_task_count"] / self.execution_metrics["total_task_lists"]
            print(f"平均タスク数: {avg_tasks:.1f}個")
        
        print("=" * 50)
    
    def _show_session_statistics(self):
        """セッション統計を表示"""
        total_time = (datetime.now() - self.session_stats["start_time"]).total_seconds()
        
        self.display.show_result_summary(
            total_tasks=self.session_stats["successful_tasks"] + self.session_stats["failed_tasks"],
            successful=self.session_stats["successful_tasks"],
            failed=self.session_stats["failed_tasks"],
            total_duration=total_time
        )
        
        if self.config["development"]["show_api_calls"]:
            print(f"API呼び出し回数: {self.session_stats['total_api_calls']}")
    
    async def pause_session(self):
        """セッションを一時停止（ESCキー対応）"""
        await self.state_manager.pause_all_tasks()
        print("\n[セッション一時停止] 作業が保存されました。")
        print("次回再開時に続きから実行できます。")
        return self.state_manager.get_session_summary()
    
    async def resume_session(self) -> Dict[str, Any]:
        """セッション再開"""
        await self.state_manager.resume_paused_tasks()
        summary = self.state_manager.get_session_summary()
        
        if summary.get("has_work_to_resume", False):
            print(f"\n[セッション再開] {summary['pending_tasks']}個のタスクが待機中です")
            
            # 実行可能なタスクがある場合は継続実行を提案
            next_task = self.task_manager.get_next_executable_task()
            if next_task:
                print(f"次のタスク: {next_task.description}")
        else:
            print("\n[セッション再開] 新しいタスクの準備完了")
        
        return summary
    
    async def clear_session(self):
        """現在のセッションをクリア"""
        await self.state_manager.clear_current_session()
        print("\n[セッションクリア] 新しいセッションで開始します")
    
    def get_session_status(self) -> Dict[str, Any]:
        """現在のセッション状態を取得"""
        session_summary = self.state_manager.get_session_summary()
        task_summary = self.task_manager.get_task_summary()
        
        return {
            "session": session_summary,
            "tasks": task_summary,
            "can_resume": session_summary.get("has_work_to_resume", False),
            "ui_mode": self.ui_mode,
            "verbose": self.verbose
        }
    
    async def handle_user_response_to_clarification(self, response: str) -> str:
        """
        ユーザーのCLARIFICATION回答を処理
        注意: このメソッドは非推奨です。_handle_pending_tasksを使用してください。
        """
        # 新しい処理フローにリダイレクト
        return await self._handle_pending_tasks(response)
    
    async def _generate_simple_task_list_v6(self, user_query: str) -> List[Dict[str, Any]]:
        """V6用のシンプルなタスクリスト生成"""
        try:
            recent_context = self._get_recent_context()
            tools_info = self.connection_manager.format_tools_for_llm()
            
            # シンプルなプロンプトを使用
            prompt = PromptTemplates.get_simple_task_list_prompt(
                recent_context=recent_context,
                user_query=user_query,
                tools_info=tools_info
            )
            
            response = await self.llm.chat.completions.create(
                model=self.config["llm"]["model"],
                messages=[{"role": "system", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            content = safe_str(response.choices[0].message.content)
            result = json.loads(content)
            
            return result.get("tasks", [])
            
        except Exception as e:
            self.logger.error(f"タスクリスト生成失敗: {e}")
            # フォールバック処理は削除 - エラー時は空リストを返す
            return []
    
    async def close(self):
        """リソースの解放"""
        # セッションをアーカイブ
        if self.state_manager.current_session:
            await self.state_manager.archive_session()
        
        # 終了時にメトリクス表示
        self._show_execution_metrics()
        await self.connection_manager.close()


async def main():
    """メイン実行関数"""
    agent = MCPAgent()
    await agent.initialize()
    
    try:
        print("\nMCP Agent が準備完了しました！")
        print("終了するには 'quit' または 'exit' を入力してください。")
        print("-" * 60)
        
        while True:
            try:
                if hasattr(agent.display, 'input_prompt') and agent.ui_mode == "rich":
                    user_input = agent.display.input_prompt("Agent").strip()
                else:
                    user_input = input("\nAgent> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            
            if user_input.lower() in ['quit', 'exit', '終了']:
                break
            
            if not user_input:
                continue
            
            # リクエスト処理
            response = await agent.process_request(user_input)
            
            # Rich UIの場合はMarkdown整形表示
            if agent.ui_mode == "rich" and hasattr(agent.display, 'show_markdown_result'):
                agent.display.show_markdown_result(response)
            else:
                print(f"\n{response}")
    
    except KeyboardInterrupt:
        print("\n\n[中断] Ctrl+Cが押されました。")
    finally:
        await agent.close()
        print("\nMCP Agent を終了しました。")


if __name__ == "__main__":
    asyncio.run(main())