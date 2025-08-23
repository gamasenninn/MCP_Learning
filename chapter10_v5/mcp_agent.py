#!/usr/bin/env python3
"""
MCP Agent V4 - Interactive Dialogue Engine
Claude Code風の対話型エージェント

V4の特徴：
- 対話的逐次実行（依存関係の自動解決）
- チェックボックス付きタスク表示
- リアルタイムプログレス
- V3の知見を活かした設計
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

# Rich UI support
try:
    from display_manager_rich import RichDisplayManager
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class MCPAgentV4:
    """
    Claude Code風の対話型MCPエージェント
    
    V3から引き継いだ要素:
    - AGENT.mdによるカスタマイズ
    - 会話文脈の活用
    - NO_TOOL判定
    
    V4の新機能:
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
        
        
        # AGENT.md読み込み（V3から継承）
        self.custom_instructions = self._load_agent_md()
        
        if self.config["development"]["verbose"]:
            self.display.show_banner()
            if self.ui_mode == "rich":
                print(f"[INFO] Rich UI mode enabled")
            else:
                print(f"[INFO] Basic UI mode enabled")
    
    def _load_config(self, config_path: str) -> Dict:
        """設定ファイルを読み込み"""
        if not os.path.exists(config_path):
            # デフォルト設定
            return {
                "display": {"show_timing": True, "show_thinking": False},
                "execution": {"max_retries": 3, "timeout_seconds": 30},
                "llm": {"model": "gpt-4o-mini", "temperature": 0.2},
                "conversation": {"context_limit": 3},
                "development": {"verbose": True}
            }
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"[警告] 設定ファイル読み込みエラー: {e}")
            return {}
    
    def _load_agent_md(self) -> str:
        """AGENT.mdを読み込み（V3から継承）"""
        agent_md_path = "AGENT.md"
        
        if os.path.exists(agent_md_path):
            try:
                with open(agent_md_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if self.config.get("development", {}).get("verbose", False):
                    print(f"[設定] AGENT.mdを読み込みました ({len(content)}文字)")
                return content
            except Exception as e:
                print(f"[警告] AGENT.md読み込みエラー: {e}")
                return ""
        else:
            if self.config.get("development", {}).get("verbose", False):
                print("[情報] AGENT.mdが見つかりません（基本能力のみで動作）")
            return ""
    
    async def initialize(self):
        """エージェントの初期化"""
        if self.config["development"]["verbose"]:
            print(f"\n[指示書] {'カスタム指示あり' if self.custom_instructions else '基本能力のみ'}")
            print("=" * 60)
        
        # MCP接続管理を初期化（V3から継承）
        await self.connection_manager.initialize()
    
    async def process_request(self, user_query: str) -> str:
        """
        ユーザーリクエストを対話的に処理（V4の核心機能）
        
        V3との違い:
        - 一度に全タスクを分解せず、ステップごとに対話
        - 前の結果を見てから次の行動を決定
        - 実行過程を視覚的に表示
        """
        self.session_stats["total_requests"] += 1
        
        if self.config["development"]["verbose"]:
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
            if self.config["development"]["verbose"]:
                print(f"[エラー] {error_msg}")
            return error_msg
    
    async def _execute_interactive_dialogue(self, user_query: str) -> str:
        """
        改良版実行エンジン（V4.1）
        
        複雑なタスクはタスクリスト方式、シンプルなタスクは従来方式
        """
        self.display.show_analysis("リクエストを分析中...")
        
        # まず処理方式を判定
        execution_result = await self._determine_execution_type(user_query)
        execution_type = execution_result.get("type", "SIMPLE")
        
        if execution_type == "NO_TOOL":
            response = execution_result.get("response", "了解しました。")
            self._add_to_history("assistant", response)
            return response
        elif execution_type == "SIMPLE":
            # 従来の対話型実行（1-2ステップの単純なタスク）
            return await self._execute_simple_dialogue(user_query)
        elif execution_type == "COMPLEX":
            # タスクリスト方式（複雑な多段階タスク）
            return await self._execute_planned_dialogue(user_query)
        else:
            return "処理方法を決定できませんでした。"
    
    async def _determine_execution_type(self, user_query: str) -> Dict:
        """実行方式を判定"""
        recent_context = self._get_recent_context()
        
        prompt = f"""ユーザーの要求を分析し、適切な実行方式を判定してください。

## 最近の会話
{recent_context if recent_context else "（新規会話）"}

## ユーザーの要求
{user_query}

## 判定基準
- **NO_TOOL**: 日常会話（挨拶・雑談・自己紹介・感想・お礼等のみ）
- **SIMPLE**: 1-2ステップの単純なタスク（計算、単一API呼び出し等）
- **COMPLEX**: データベース操作、多段階処理等

## 重要な注意
- 「天気」「温度」「気象」等は外部APIが必要なのでNO_TOOLではありません！

## 出力形式
NO_TOOLの場合：
```json
{{"type": "NO_TOOL", "response": "**Markdown形式**で適切な応答メッセージ", "reason": "判定理由"}}
```

その他の場合：
```json
{{"type": "SIMPLE|COMPLEX", "reason": "判定理由"}}
```"""

        try:
            response = await self.llm.chat.completions.create(
                model=self.config["llm"]["model"],
                messages=[{"role": "system", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            result = json.loads(response.choices[0].message.content)
            if self.config["development"]["verbose"]:
                print(f"[判定] {result.get('type', 'UNKNOWN')} - {result.get('reason', '')}")
            
            return result
            
        except Exception as e:
            print(f"[エラー] 実行方式判定失敗: {e}")
            return {"type": "SIMPLE", "reason": "判定エラーによりデフォルト選択"}
    
    async def _execute_with_tasklist(self, user_query: str, task_type: str = "SIMPLE") -> str:
        """統一されたタスクリスト実行メソッド（重複コード統合版）"""
        
        # タスクタイプに応じたタスクリスト生成
        if task_type == "SIMPLE":
            task_list = await self._generate_simple_task_list(user_query)
            if not task_list:
                # タスクリスト生成に失敗した場合は従来方式にフォールバック
                return await self._execute_fallback_dialogue(user_query)
        elif task_type == "COMPLEX":
            task_list = await self._generate_task_list(user_query)
            if not task_list:
                return "タスクリストの生成に失敗しました。"
        else:
            return f"不明なタスクタイプ: {task_type}"
        
        # チェックリストを表示
        if self.ui_mode == "rich" and self.config.get("display", {}).get("rich_options", {}).get("enable_live_updates", True):
            self.display.show_checklist(task_list)
        else:
            self.display.show_checklist(task_list)
        
        # 実行結果を追跡
        completed = []
        failed = []
        execution_context = []
        
        # タスクを順次実行
        for i, task in enumerate(task_list):
            # 進行状況更新（Rich UIの場合はライブ更新）
            if self.ui_mode == "rich" and hasattr(self.display, 'update_checklist_live'):
                self.display.update_checklist_live(task_list, current=i, completed=completed, failed=failed)
            else:
                self.display.update_checklist(task_list, current=i, completed=completed, failed=failed)
            
            try:
                # タスク実行
                result = await self._execute_planned_task(task, i+1, len(task_list))
                
                if result["success"]:
                    completed.append(i)
                    task["duration"] = result["duration"]
                else:
                    failed.append(i)
                
                execution_context.append(result)
                
            except Exception as e:
                failed.append(i)
                print(f"[エラー] タスク{i+1}実行失敗: {e}")
        
        # 最終状況表示
        if self.ui_mode == "rich" and hasattr(self.display, 'update_checklist_live'):
            self.display.update_checklist_live(task_list, current=-1, completed=completed, failed=failed)
        else:
            self.display.update_checklist(task_list, current=-1, completed=completed, failed=failed)
        
        # 結果をLLMで解釈
        return await self._interpret_planned_results(user_query, execution_context)

    async def _execute_simple_dialogue(self, user_query: str) -> str:
        """単純なタスクの実行（統一メソッド使用版）"""
        return await self._execute_with_tasklist(user_query, "SIMPLE")
    
    async def _generate_simple_task_list(self, user_query: str) -> List[Dict]:
        """シンプルなタスク用のタスクリスト生成"""
        recent_context = self._get_recent_context()
        tools_info = self.connection_manager.format_tools_for_llm()
        
        prompt = f"""ユーザーの単純な要求に対して、最小限のタスクリストを生成してください。

## 最近の会話
{recent_context if recent_context else "（新規会話）"}

## ユーザーの要求
{user_query}

## 利用可能なツール
{tools_info}

## 指針
- 1-3個の必要最小限のタスクで構成
- 計算の場合は演算順序を考慮
- 天気等の単一API呼び出しは1つのタスクで完結

## 出力形式
```json
{{"tasks": [
  {{"tool": "ツール名", "params": {{"param": "値"}}, "description": "何をするかの説明"}},
  ...
]}}
```"""

        try:
            response = await self.llm.chat.completions.create(
                model=self.config["llm"]["model"],
                messages=[{"role": "system", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            result = json.loads(response.choices[0].message.content)
            tasks = result.get("tasks", [])
            
            # 最大3タスクに制限
            if len(tasks) > 3:
                tasks = tasks[:3]
            
            return tasks
            
        except Exception as e:
            print(f"[エラー] シンプルタスクリスト生成失敗: {e}")
            return []
    
    async def _execute_fallback_dialogue(self, user_query: str) -> str:
        """フォールバック用の従来型対話実行"""
        execution_context = []
        step_count = 0
        max_steps = 5
        
        while step_count < max_steps:
            step_count += 1
            
            if self._detect_loop(execution_context):
                return "同じ処理が繰り返されています。処理を中断します。"
            
            action = await self._get_next_action(user_query, execution_context, step_count)
            
            if action.get("type") == "COMPLETE":
                return action.get("response", "処理を完了しました。")
            elif action.get("type") == "EXECUTE":
                step_result = await self._execute_step(action, step_count)
                execution_context.append(step_result)
            else:
                return "処理中にエラーが発生しました。"
        
        return "最大ステップ数に到達しました。処理を完了します。"
    
    
    async def _execute_planned_dialogue(self, user_query: str) -> str:
        """タスクリスト方式の実行（統一メソッド使用版）"""
        return await self._execute_with_tasklist(user_query, "COMPLEX")
    
    def _detect_loop(self, context: List[Dict], threshold: int = 3) -> bool:
        """無限ループ検出"""
        if len(context) < threshold:
            return False
        
        # 最後のN個が同じツールか確認
        last_tools = [c.get('tool', '') for c in context[-threshold:]]
        return len(set(last_tools)) == 1 and last_tools[0] != ''
    
    async def _get_next_action(self, user_query: str, context: List[Dict], 
                              step: int) -> Dict:
        """
        次のアクションを決定（LLMと対話）
        
        V3のタスク分解を段階的に実行する版
        """
        # 会話履歴を取得（V3から継承）
        recent_context = self._get_recent_context()
        
        # 利用可能なツール情報
        tools_info = self.connection_manager.format_tools_for_llm()
        
        # 実行コンテキストを整理
        context_summary = self._format_execution_context(context)
        
        prompt = f"""あなたは知的な対話型アシスタントです。ユーザーの要求を段階的に処理します。

## 最近の会話
{recent_context if recent_context else "（新規会話）"}

## ユーザーの要求
{user_query}

## これまでの実行状況
{context_summary if context_summary else "（まだ何も実行していません）"}

## 利用可能なツール
{tools_info}

## カスタム指示
{self.custom_instructions if self.custom_instructions else "なし"}

## 判定指針
**最優先**: これは日常会話（挨拶・雑談・自己紹介等）ですか？
- YES → NO_TOOL を選択

**ツール実行が必要な場合**:
1. これまでの実行結果を踏まえて、次に必要な1つのアクションを決定
2. 全て完了している場合は COMPLETE を選択
3. 1ステップずつ実行（Claude Code風）

## 出力形式
### 日常会話の場合
```json
{{"type": "NO_TOOL", "response": "**Markdown形式**で適切な応答"}}
```

### ツール実行の場合
```json
{{"type": "EXECUTE", "tool": "ツール名", "params": {{"param": "値"}}, "description": "何をするかの説明"}}
```

### 完了の場合  
```json
{{"type": "COMPLETE", "response": "**Markdown形式**で最終的な回答"}}
```

現在のステップ: {step}"""
        
        try:
            self.session_stats["total_api_calls"] += 1
            
            response = await self.llm.chat.completions.create(
                model=self.config["llm"]["model"],
                messages=[{"role": "system", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=self.config["llm"]["temperature"]
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            print(f"[エラー] アクション決定失敗: {e}")
            return {"type": "COMPLETE", "response": f"処理エラー: {str(e)}"}
    
    async def _execute_step(self, action: Dict, step_num: int) -> Dict:
        """
        1つのステップを実行
        """
        tool = action.get("tool", "")
        params = action.get("params", {})
        description = action.get("description", f"{tool}を実行")
        
        # ステップ開始の表示
        self.display.show_step_start(step_num, "?", description)
        self.display.show_tool_call(tool, params)
        
        start_time = time.time()
        
        try:
            # ツール実行（リトライ付き）
            result = await self._execute_tool_with_retry(tool, params)
            duration = time.time() - start_time
            
            self.display.show_step_complete(description, duration, success=True)
            self.session_stats["successful_tasks"] += 1
            
            return {
                "step": step_num,
                "tool": tool,
                "params": params,
                "result": result,
                "success": True,
                "duration": duration,
                "description": description
            }
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            
            self.display.show_step_complete(f"{description} - {error_msg}", 
                                          duration, success=False)
            self.session_stats["failed_tasks"] += 1
            
            return {
                "step": step_num,
                "tool": tool,
                "params": params,
                "error": error_msg,
                "success": False,
                "duration": duration,
                "description": description
            }
    
    async def _execute_tool_with_retry(self, tool: str, params: Dict) -> Any:
        """
        ツールをリトライ付きで実行（ErrorHandler統一版）
        """
        async def execute_func(tool_name: str, tool_params: Dict) -> Any:
            return await self.connection_manager.call_tool(tool_name, tool_params)
        
        def get_tools_info() -> str:
            return self.connection_manager.format_tools_for_llm()
        
        return await self.error_handler.execute_with_retry(
            tool=tool,
            params=params,
            execute_func=execute_func,
            tools_info_func=get_tools_info
        )
    
    
    
    def _format_execution_context(self, context: List[Dict]) -> str:
        """実行コンテキストを文字列にフォーマット"""
        if not context:
            return ""
        
        lines = []
        for i, ctx in enumerate(context, 1):
            status = "成功" if ctx["success"] else "失敗"
            lines.append(f"ステップ{i}: {ctx['description']} ({status})")
            
            if ctx["success"]:
                # 結果を簡潔に表示
                result_str = str(ctx["result"])[:100]
                if len(result_str) == 100:
                    result_str += "..."
                lines.append(f"  結果: {result_str}")
            else:
                lines.append(f"  エラー: {ctx['error']}")
        
        return "\n".join(lines)
    
    async def _generate_task_list(self, user_query: str) -> List[Dict]:
        """タスクリストを事前生成"""
        recent_context = self._get_recent_context()
        tools_info = self.connection_manager.format_tools_for_llm()
        
        prompt = f"""ユーザーの要求を分析し、実行に必要なタスクリストを生成してください。

## 最近の会話
{recent_context if recent_context else "（新規会話）"}

## ユーザーの要求
{user_query}

## 利用可能なツール
{tools_info}

## カスタム指示
{self.custom_instructions if self.custom_instructions else "なし"}

## データベース操作の必須ルール（重要）
データベース関連の要求は必ず以下の3ステップ：
1. list_tables - テーブル一覧確認
2. get_table_schema - 対象テーブルのスキーマ確認  
3. execute_safe_query - 実際のクエリ実行

## データベース表示ルール
- 「一覧」「全件」「すべて」→ LIMIT 20（適度な件数）
- 「少し」「いくつか」→ LIMIT 5
- 「全部」「制限なし」→ LIMIT 50（最大）
- 「1つ」「最高」「最安」→ LIMIT 1

例：「商品データ一覧を表示して」
→ [
  {{"tool": "list_tables", "description": "テーブル一覧を確認"}},
  {{"tool": "get_table_schema", "params": {{"table_name": "products"}}, "description": "商品テーブルのスキーマを確認"}},
  {{"tool": "execute_safe_query", "params": {{"query": "SELECT * FROM products LIMIT 20"}}, "description": "商品データを20件表示"}}
]

## 出力形式
```json
{{"tasks": [
  {{"tool": "ツール名", "params": {{"param": "値"}}, "description": "何をするかの説明"}},
  ...
]}}
```

必要最小限のタスクで構成し、効率的な実行計画を作成してください。"""

        try:
            self.session_stats["total_api_calls"] += 1
            
            response = await self.llm.chat.completions.create(
                model=self.config["llm"]["model"],
                messages=[{"role": "system", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            result = json.loads(response.choices[0].message.content)
            tasks = result.get("tasks", [])
            
            if self.config["development"]["verbose"]:
                print(f"[計画] {len(tasks)}個のタスクを生成")
            
            return tasks
            
        except Exception as e:
            print(f"[エラー] タスクリスト生成失敗: {e}")
            return []
    
    async def _execute_planned_task(self, task: Dict, step_num: int, total: int) -> Dict:
        """計画されたタスクを実行"""
        tool = task.get("tool", "")
        params = task.get("params", {})
        description = task.get("description", f"{tool}を実行")
        
        start_time = time.time()
        
        try:
            # ツール実行
            result = await self._execute_tool_with_retry(tool, params)
            duration = time.time() - start_time
            
            self.session_stats["successful_tasks"] += 1
            
            return {
                "step": step_num,
                "tool": tool,
                "params": params,
                "result": result,
                "success": True,
                "duration": duration,
                "description": description
            }
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            
            self.session_stats["failed_tasks"] += 1
            
            return {
                "step": step_num,
                "tool": tool,
                "params": params,
                "error": error_msg,
                "success": False,
                "duration": duration,
                "description": description
            }
    
    async def _interpret_planned_results(self, user_query: str, results: List[Dict]) -> str:
        """計画実行の結果を解釈"""
        recent_context = self._get_recent_context()
        
        # 結果をシリアライズ
        serializable_results = []
        for r in results:
            result_data = {
                "step": r["step"],
                "tool": r["tool"],
                "success": r["success"],
                "description": r["description"]
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
        
        prompt = f"""実行結果を解釈して、ユーザーに分かりやすく回答してください。

## 会話の文脈
{recent_context if recent_context else "（新規会話）"}

## ユーザーの元の質問
{user_query}

## 実行されたタスクと結果
{json.dumps(serializable_results, ensure_ascii=False, indent=2)}

## カスタム指示
{self.custom_instructions if self.custom_instructions else "特になし"}

ユーザーの質問に直接答え、成功したタスクの結果を統合して自然な回答を生成してください。
失敗したタスクがある場合は、その影響を考慮した回答にしてください。

## 出力形式
回答は**Markdown形式**で整理して出力してください：
- 見出しは `### タイトル`
- 重要な情報は `**太字**`
- リストは `-` または `1.` 
- コードや値は `code`
- 実行結果は `> 結果`
- 長い結果は適切に改行・整理

例：
### 実行結果
計算が完了しました：
- **100 + 200** = `300`
- 実行時間: `0.5秒`

> すべての計算が正常に完了しました。"""

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
        """最近の会話文脈を取得（実行結果も含む）"""
        if max_items is None:
            max_items = self.config["conversation"]["context_limit"]
        
        if not self.conversation_history:
            return ""
        
        recent = self.conversation_history[-max_items:]
        lines = []
        for h in recent:
            role = "User" if h['role'] == "user" else "Assistant"
            # 長いメッセージは省略
            msg = h['message'][:150] + "..." if len(h['message']) > 150 else h['message']
            lines.append(f"{role}: {msg}")
            
            # 実行結果があれば追加
            if h.get('execution_results'):
                lines.append(f"実行結果データ: {self._summarize_results(h['execution_results'])}")
        
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
    
    async def close(self):
        """リソースの解放"""
        await self.connection_manager.close()


async def main():
    """メイン実行関数"""
    agent = MCPAgentV4()
    await agent.initialize()
    
    try:
        print("\nMCP Agent V4 が準備完了しました！")
        print("終了するには 'quit' または 'exit' を入力してください。")
        print("-" * 60)
        
        while True:
            if hasattr(agent.display, 'input_prompt') and agent.ui_mode == "rich":
                user_input = agent.display.input_prompt("Agent").strip()
            else:
                user_input = input("\nAgent> ").strip()
            
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
        print("\nMCP Agent V4 を終了しました。")


if __name__ == "__main__":
    asyncio.run(main())