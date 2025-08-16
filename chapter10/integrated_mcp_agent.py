#!/usr/bin/env python3
"""
統合MCPエージェント
すべてのコンポーネントを統合した高度なCLIエージェント
"""

import asyncio
import json
import os
import sys
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

# .envファイルから環境変数を読み込む
load_dotenv()

# コンポーネントのインポート
from universal_task_planner import UniversalTaskPlanner, UniversalTask
from adaptive_task_planner import AdaptiveTaskPlanner
from intelligent_error_handler import IntelligentErrorHandler
from error_aware_executor import ErrorAwareExecutor

@dataclass
class SessionState:
    """セッション状態"""
    start_time: datetime = field(default_factory=datetime.now)
    total_requests: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    recovered_tasks: int = 0
    learning_entries: int = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """統計情報を取得"""
        duration = (datetime.now() - self.start_time).total_seconds()
        return {
            "duration_seconds": duration,
            "total_requests": self.total_requests,
            "successful_tasks": self.successful_tasks,
            "failed_tasks": self.failed_tasks,
            "recovered_tasks": self.recovered_tasks,
            "success_rate": (self.successful_tasks / max(1, self.successful_tasks + self.failed_tasks)) * 100,
            "learning_entries": self.learning_entries
        }

class IntegratedMCPAgent:
    """統合MCPエージェント - すべての機能を結集"""
    
    def __init__(
        self,
        config_file: str = "mcp_servers.json",
        use_ai: bool = True,
        max_retries: int = 3,
        enable_learning: bool = True,
        verbose: bool = True
    ):
        """
        Args:
            config_file: MCPサーバー設定ファイル
            use_ai: AI支援エラーハンドリングを使用
            max_retries: 最大リトライ回数
            enable_learning: 学習機能を有効化
            verbose: 詳細ログ出力
        """
        self.config_file = config_file
        self.use_ai = use_ai
        self.enable_learning = enable_learning
        self.verbose = verbose
        
        # コンポーネントの初期化
        self.planner = UniversalTaskPlanner(config_file)
        self.adaptive_planner = AdaptiveTaskPlanner() if use_ai else None
        self.executor = ErrorAwareExecutor(
            config_file=config_file,
            use_ai=use_ai,
            max_retries=max_retries,
            verbose=verbose
        )
        
        # セッション管理
        self.session = SessionState()
        self.command_history: List[str] = []
        self.execution_results: List[Dict[str, Any]] = []
        
        # 学習キャッシュ
        self.success_patterns: Dict[str, List[UniversalTask]] = {}
        
        # 会話コンテキスト管理
        self.conversation_memory = {
            "user_name": None,           # ユーザーの名前
            "agent_name": None,          # エージェントの名前
            "recent_results": [],        # 最近の計算結果や実行結果
            "context": [],               # 会話の文脈（最新10件）
            "important_facts": {},       # 重要な事実（名前、場所など）
            "current_location": None     # 現在の場所
        }
        self.max_context_length = 10    # 保持する会話履歴の最大数
        
    async def initialize(self):
        """エージェントの初期化"""
        if self.verbose:
            print("\n" + "=" * 70)
            print(" 統合MCPエージェント - 初期化")
            print("=" * 70)
        
        # プランナーの初期化
        await self.planner.initialize()
        
        # 適応型プランナーの初期化
        if self.adaptive_planner:
            await self.adaptive_planner.initialize()
        
        # エグゼキューターの初期化（サーバー接続）
        await self.executor.connect_all_servers()
        
        if self.verbose:
            print(f"\n[初期化完了]")
            print(f"  利用可能ツール: {len(self.planner.tools_info)}個")
            print(f"  AI支援: {'有効' if self.use_ai else '無効'}")
            print(f"  学習機能: {'有効' if self.enable_learning else '無効'}")
    
    async def process_request(
        self,
        query: str,
        auto_retry: bool = True,
        interpret_result: bool = True
    ) -> Dict[str, Any]:
        """
        ユーザーリクエストを処理
        
        Args:
            query: 自然言語のリクエスト
            auto_retry: 失敗時の自動リトライ
            interpret_result: 結果の解釈を行うか
            
        Returns:
            実行結果の辞書
        """
        self.session.total_requests += 1
        self.command_history.append(query)
        
        # 会話コンテキストを更新
        self._update_conversation_context(query)
        
        # 重要な情報を抽出（名前の設定など）
        await self._extract_important_info(query)
        
        if self.verbose:
            print(f"\n{'='*70}")
            print(f"[リクエスト #{self.session.total_requests}] {query}")
            print("-" * 70)
        
        start_time = datetime.now()
        result = {
            "query": query,
            "timestamp": start_time.isoformat(),
            "success": False,
            "result": None,
            "error": None,
            "tasks_executed": 0,
            "recovery_attempted": False,
            "learning_applied": False
        }
        
        try:
            # Step 1: 学習済みパターンをチェック
            if self.enable_learning and query in self.success_patterns:
                if self.verbose:
                    print("[学習] 成功パターンを発見、キャッシュから実行")
                tasks = self.success_patterns[query]
                result["learning_applied"] = True
            else:
                # Step 2: タスク分解
                if self.verbose:
                    print("[分析] タスクを分解中...")
                
                # 適応型プランナーがあれば優先使用
                if self.adaptive_planner and self.enable_learning:
                    tasks = await self.adaptive_planner.plan_with_adaptation(query)
                else:
                    tasks = await self.planner.plan_task(query)
                
                if not tasks:
                    # ツール不要の応答を処理
                    if self.use_ai:
                        # AIで適切な応答を生成
                        no_tool_response = await self._generate_no_tool_response(query)
                        result["result"] = no_tool_response
                    else:
                        result["result"] = "タスク分解不要またはツール不要です"
                    result["success"] = True
                    
                    if self.verbose:
                        print(f"\n[応答] {result['result']}")
                    
                    self.execution_results.append(result)
                    return result
                
                if self.verbose:
                    print(f"  → {len(tasks)}個のタスクに分解")
                    for task in tasks:
                        print(f"     - {task.id}: {task.tool}")
            
            # Step 3: タスク実行（エラーリカバリー付き）
            if self.verbose:
                print("\n[実行] タスクを実行中...")
            
            execution_result = await self.executor.execute_tasks_with_recovery(tasks)
            result["tasks_executed"] = len(tasks)
            
            # Step 4: 実行結果の処理
            if execution_result["success"]:
                result["success"] = True
                result["result"] = execution_result["final_result"]
                
                # 成功パターンを学習
                if self.enable_learning and not result["learning_applied"]:
                    self.success_patterns[query] = tasks
                    self.session.learning_entries += 1
                    if self.adaptive_planner:
                        await self.adaptive_planner.learn_from_success(query, tasks)
                
                self.session.successful_tasks += execution_result["stats"]["success"]
                
                # Step 4.5: 結果をLLMで解釈（オプション）
                if interpret_result and self.use_ai:
                    interpretation = await self._interpret_result(query, execution_result, tasks)
                    result["interpretation"] = interpretation
                    if self.verbose:
                        print(f"\n[結果の解釈]")
                        print("-" * 40)
                        print(interpretation)
                else:
                    if self.verbose:
                        print(f"\n[成功] 結果: {result['result']}")
            
            else:
                # Step 5: 失敗時の処理
                failed_count = execution_result["stats"]["failed"]
                self.session.failed_tasks += failed_count
                
                if auto_retry and self.adaptive_planner:
                    # 再計画を試みる
                    if self.verbose:
                        print("\n[再計画] 失敗したタスクの再計画中...")
                    
                    result["recovery_attempted"] = True
                    
                    # 失敗したタスクを特定
                    failed_tasks = [t for t in tasks if t.error]
                    error_info = {
                        "error": failed_tasks[0].error if failed_tasks else "不明なエラー",
                        "attempts": 1
                    }
                    
                    # 再計画
                    new_tasks = await self.adaptive_planner.replan_on_error(
                        query, failed_tasks, error_info
                    )
                    
                    if new_tasks:
                        # 再実行
                        retry_result = await self.executor.execute_tasks_with_recovery(new_tasks)
                        
                        if retry_result["success"]:
                            result["success"] = True
                            result["result"] = retry_result["final_result"]
                            self.session.recovered_tasks += 1
                            
                            if self.verbose:
                                print(f"[回復成功] 結果: {result['result']}")
                        else:
                            result["error"] = "再計画後も失敗しました"
                    else:
                        result["error"] = "再計画の生成に失敗しました"
                else:
                    result["error"] = f"{failed_count}個のタスクが失敗しました"
                    
                if not result["success"] and self.verbose:
                    print(f"\n[失敗] {result['error']}")
            
            # リカバリー統計
            if execution_result["stats"].get("recovered", 0) > 0:
                self.session.recovered_tasks += execution_result["stats"]["recovered"]
            
            # 結果を記憶に追加
            if result["success"] and result.get("result"):
                self._update_memory_with_result(query, result["result"])
            
        except Exception as e:
            result["error"] = str(e)
            if self.verbose:
                print(f"\n[エラー] {e}")
        
        # 実行時間を記録
        result["execution_time"] = (datetime.now() - start_time).total_seconds()
        
        # 結果を履歴に追加
        self.execution_results.append(result)
        
        return result
    
    async def interactive_session(self):
        """対話型セッション"""
        print("\n" + "=" * 70)
        print(" 統合MCPエージェント - 対話モード")
        print("=" * 70)
        print("\nコマンド:")
        print("  - 自然言語でタスクを入力")
        print("  - 'status' : セッション状態を表示")
        print("  - 'history': 実行履歴を表示")
        print("  - 'learn'  : 学習状況を表示")
        print("  - 'clear'  : 画面をクリア")
        print("  - 'help'   : ヘルプを表示")
        print("  - 'exit'   : 終了")
        print("-" * 70)
        
        while True:
            try:
                # プロンプト表示
                user_input = input(f"\nAgent[{self.session.total_requests + 1}]> ").strip()
                
                if not user_input:
                    continue
                
                # 特殊コマンドの処理
                command_lower = user_input.lower()
                
                if command_lower == 'exit':
                    print("\nエージェントを終了します...")
                    break
                    
                elif command_lower == 'status':
                    self._show_status()
                    continue
                    
                elif command_lower == 'history':
                    self._show_history()
                    continue
                    
                elif command_lower == 'learn':
                    self._show_learning()
                    continue
                    
                elif command_lower == 'clear':
                    os.system('cls' if os.name == 'nt' else 'clear')
                    continue
                    
                elif command_lower == 'help':
                    self._show_help()
                    continue
                
                # 通常のリクエスト処理
                result = await self.process_request(user_input)
                
                # 結果の簡潔な表示
                if not self.verbose:
                    if result["success"]:
                        print(f"✓ 結果: {result['result']}")
                    else:
                        print(f"✗ エラー: {result['error']}")
                
            except KeyboardInterrupt:
                print("\n\n中断されました")
                break
            except Exception as e:
                print(f"\nセッションエラー: {e}")
    
    def _show_status(self):
        """セッション状態を表示"""
        stats = self.session.get_stats()
        
        print("\n[セッション状態]")
        print("-" * 40)
        print(f"  実行時間: {stats['duration_seconds']:.1f}秒")
        print(f"  総リクエスト: {stats['total_requests']}")
        print(f"  成功タスク: {stats['successful_tasks']}")
        print(f"  失敗タスク: {stats['failed_tasks']}")
        print(f"  リカバリー: {stats['recovered_tasks']}")
        print(f"  成功率: {stats['success_rate']:.1f}%")
        print(f"  学習エントリー: {stats['learning_entries']}")
    
    def _show_history(self):
        """実行履歴を表示"""
        print("\n[実行履歴]")
        print("-" * 40)
        
        if not self.execution_results:
            print("  まだ実行履歴がありません")
            return
        
        # 最新10件を表示
        for i, result in enumerate(self.execution_results[-10:], 1):
            status = "✓" if result["success"] else "✗"
            time_str = datetime.fromisoformat(result["timestamp"]).strftime("%H:%M:%S")
            query = result["query"][:50] + "..." if len(result["query"]) > 50 else result["query"]
            
            print(f"  {i}. [{time_str}] {status} {query}")
            if result.get("learning_applied"):
                print(f"     (学習済みパターン使用)")
            if result.get("recovery_attempted"):
                print(f"     (リカバリー実行)")
    
    def _show_learning(self):
        """学習状況を表示"""
        print("\n[学習状況]")
        print("-" * 40)
        
        if not self.success_patterns:
            print("  学習済みパターンはありません")
            return
        
        print(f"  学習済みパターン: {len(self.success_patterns)}個")
        
        for query, tasks in list(self.success_patterns.items())[:5]:
            query_short = query[:40] + "..." if len(query) > 40 else query
            print(f"  - {query_short}")
            print(f"    → {len(tasks)}個のタスク")
    
    def _show_help(self):
        """ヘルプを表示"""
        print("\n[ヘルプ]")
        print("-" * 40)
        print("使用例:")
        print("  - '100と200を足して'")
        print("  - '売上データを分析してレポート作成'")
        print("  - 'データベースから商品情報を取得'")
        print("\n特殊コマンド:")
        print("  - status : 現在のセッション統計")
        print("  - history: 過去の実行履歴")
        print("  - learn  : 学習済みパターン")
        print("  - help   : このヘルプ")
        print("  - exit   : 終了")
    
    def _update_conversation_context(self, query: str):
        """会話コンテキストを更新"""
        # 会話履歴に追加
        self.conversation_memory["context"].append({
            "timestamp": datetime.now().isoformat(),
            "speaker": "user",
            "message": query
        })
        
        # 最大長を超えたら古いものを削除
        if len(self.conversation_memory["context"]) > self.max_context_length:
            self.conversation_memory["context"] = self.conversation_memory["context"][-self.max_context_length:]
    
    async def _extract_important_info(self, query: str):
        """重要な情報を抽出して記憶"""
        import re
        query_lower = query.lower()
        
        # 名前の設定を検出
        if "君の名前は" in query or "あなたの名前は" in query or "お前の名前は" in query:
            # 名前を抽出（より柔軟なパターン）
            name_match = re.search(r'(?:君の名前は|あなたの名前は|お前の名前は)(\S+?)(?:だ|です|よ|$)', query)
            if name_match:
                self.conversation_memory["agent_name"] = name_match.group(1)
                self.conversation_memory["important_facts"]["agent_name"] = name_match.group(1)
                if self.verbose:
                    print(f"[記憶] エージェント名を設定: {self.conversation_memory['agent_name']}")
        
        # 場所の言及を検出
        if "場所" in query or "ここ" in query:
            if "天気" in query:
                # 現在地を推測（実際にはIPアドレスなどから取得すべき）
                self.conversation_memory["current_location"] = "現在地"
        
        # ユーザー名の言及を検出
        if "私の名前は" in query or "俺の名前は" in query or "僕の名前は" in query:
            # より柔軟なパターンマッチング
            name_match = re.search(r'(?:私の名前は|俺の名前は|僕の名前は)(\S+?)(?:だ|です|よ|$)', query)
            if name_match:
                self.conversation_memory["user_name"] = name_match.group(1)
                self.conversation_memory["important_facts"]["user_name"] = name_match.group(1)
                if self.verbose:
                    print(f"[記憶] ユーザー名を設定: {self.conversation_memory['user_name']}")
    
    def _update_memory_with_result(self, query: str, result: Any):
        """実行結果を記憶に追加"""
        # 最近の結果に追加
        self.conversation_memory["recent_results"].append({
            "query": query,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
        
        # 最大10件まで保持
        if len(self.conversation_memory["recent_results"]) > 10:
            self.conversation_memory["recent_results"] = self.conversation_memory["recent_results"][-10:]
        
        # 会話コンテキストに結果を追加
        self.conversation_memory["context"].append({
            "timestamp": datetime.now().isoformat(),
            "speaker": "agent",
            "message": str(result)
        })
    
    async def _generate_no_tool_response(self, query: str) -> str:
        """
        ツール不要な質問に対する応答を生成
        """
        from openai import AsyncOpenAI
        
        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # 会話コンテキストを整形
        context_str = ""
        if self.conversation_memory["context"]:
            recent_context = self.conversation_memory["context"][-5:]  # 最近5件
            for entry in recent_context:
                speaker = "ユーザー" if entry["speaker"] == "user" else "エージェント"
                context_str += f"{speaker}: {entry['message']}\n"
        
        # 重要な情報を整形
        memory_info = ""
        if self.conversation_memory["agent_name"]:
            memory_info += f"- あなたの名前は「{self.conversation_memory['agent_name']}」です\n"
        if self.conversation_memory["user_name"]:
            memory_info += f"- ユーザーの名前は「{self.conversation_memory['user_name']}」です\n"
        if self.conversation_memory["recent_results"]:
            last_result = self.conversation_memory["recent_results"][-1]
            memory_info += f"- 直前の計算結果: {last_result['result']}\n"
        
        prompt = f"""
あなたは親切なアシスタントです。ユーザーからの挨拶、感謝、褒め言葉、簡単な質問に対して、
自然で適切な日本語で応答してください。

## 会話の文脈
{context_str if context_str else "（新しい会話）"}

## 記憶している情報
{memory_info if memory_info else "（まだ記憶はありません）"}

## ユーザーの発言
{query}

## 注意事項
- 自然で親しみやすい応答を心がけてください
- 会話の文脈を考慮して応答してください
- 名前を設定された場合は、その名前で自己紹介してください
- 「君の名前を言ってみて」と聞かれたら、設定された名前を答えてください
- 前の計算結果や会話内容を参照することができます
- 絵文字は使用しないでください
- 簡潔に応答してください（1-2文程度）

応答:"""
        
        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a friendly assistant that responds naturally in Japanese."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=200
            )
            
            return response.choices[0].message.content.strip()
        except:
            # フォールバック応答
            if "ありがと" in query:
                return "どういたしまして。お役に立てて嬉しいです。"
            elif "すごい" in query or "素晴らしい" in query:
                return "ありがとうございます。お褒めの言葉をいただき光栄です。"
            elif "こんにち" in query:
                return "こんにちは！何かお手伝いできることはありますか？"
            else:
                return "承知しました。"
    
    async def _interpret_result(
        self, 
        original_query: str, 
        execution_result: Dict[str, Any],
        tasks: List[UniversalTask]
    ) -> str:
        """
        実行結果をLLMで解釈して、人間にわかりやすく説明
        """
        from openai import AsyncOpenAI
        
        # OpenAIクライアント
        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # 実行されたタスクの詳細
        task_details = []
        for task_data in execution_result.get("tasks", []):
            if task_data.get("result") is not None:
                task_details.append(f"- {task_data['name']}: {task_data['result']}")
        
        # 最終結果の整形
        final_result = execution_result.get("final_result")
        if isinstance(final_result, dict):
            result_str = json.dumps(final_result, ensure_ascii=False, indent=2)
        else:
            result_str = str(final_result)
        
        # 解釈用プロンプト
        interpretation_prompt = f"""
あなたは親切なアシスタントです。ユーザーの質問に対する実行結果を、わかりやすく自然な日本語で説明してください。

## ユーザーの質問
{original_query}

## 実行されたタスク
{chr(10).join(task_details) if task_details else "詳細なし"}

## 最終結果
{result_str}

## 指示
1. 結果を自然な日本語で説明してください
2. 数値計算の場合は、計算過程も含めて説明してください
3. 天気情報の場合は、見やすく整形してください
4. データベースやファイルの結果は、要約して説明してください
5. 技術的な詳細は省き、ユーザーが理解しやすい形にしてください
6. 絵文字は使わないでください

回答:"""
        
        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that explains technical results in simple Japanese."},
                    {"role": "user", "content": interpretation_prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            return f"結果: {final_result}"
    
    async def cleanup(self):
        """クリーンアップ"""
        if self.verbose:
            print("\n[クリーンアップ] リソースを解放中...")
        
        # エグゼキューターのクリーンアップ
        await self.executor.cleanup()
        
        # 最終統計を表示
        if self.verbose:
            self._show_status()
            
            # エラーハンドラーのレポート
            if hasattr(self.executor, 'error_handler') and hasattr(self.executor.error_handler, 'get_learning_report'):
                print("\n" + self.executor.error_handler.get_learning_report())
            
            # 適応型プランナーのレポート
            if self.adaptive_planner and hasattr(self.adaptive_planner, 'get_adaptation_report'):
                print("\n" + self.adaptive_planner.get_adaptation_report())
    
    def save_session(self, filename: str = "agent_session.json"):
        """セッションを保存"""
        session_data = {
            "timestamp": datetime.now().isoformat(),
            "stats": self.session.get_stats(),
            "command_history": self.command_history,
            "success_patterns": {
                query: [task.to_dict() for task in tasks]
                for query, tasks in self.success_patterns.items()
            },
            "execution_results": self.execution_results[-100:],  # 最新100件
            "conversation_memory": self.conversation_memory  # 会話記憶を追加
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)
        
        if self.verbose:
            print(f"[保存] セッションを {filename} に保存しました")
    
    def load_session(self, filename: str = "agent_session.json"):
        """セッションを読み込み"""
        if not Path(filename).exists():
            if self.verbose:
                print(f"[警告] {filename} が見つかりません")
            return False
        
        with open(filename, 'r', encoding='utf-8') as f:
            session_data = json.load(f)
        
        # 学習パターンを復元
        for query, tasks_data in session_data.get("success_patterns", {}).items():
            tasks = []
            for task_data in tasks_data:
                task = UniversalTask(
                    id=task_data["id"],
                    name=task_data["name"],
                    tool=task_data["tool"],
                    server=task_data.get("server"),
                    params=task_data.get("params", {}),
                    dependencies=task_data.get("dependencies", [])
                )
                tasks.append(task)
            self.success_patterns[query] = tasks
        
        # 会話記憶を復元
        if "conversation_memory" in session_data:
            self.conversation_memory = session_data["conversation_memory"]
            if self.verbose:
                memory_info = []
                if self.conversation_memory.get("user_name"):
                    memory_info.append(f"ユーザー名: {self.conversation_memory['user_name']}")
                if self.conversation_memory.get("agent_name"):
                    memory_info.append(f"エージェント名: {self.conversation_memory['agent_name']}")
                if self.conversation_memory.get("recent_results"):
                    memory_info.append(f"記憶済み結果: {len(self.conversation_memory['recent_results'])}件")
                
                if memory_info:
                    print(f"[記憶復元] {', '.join(memory_info)}")
        
        # 統計を更新
        self.session.learning_entries = len(self.success_patterns)
        
        if self.verbose:
            print(f"[読込] {len(self.success_patterns)}個の学習パターンを復元しました")
        
        return True


async def main():
    """メイン関数"""
    print("統合MCPエージェントを起動中...")
    
    # エージェントの作成
    agent = IntegratedMCPAgent(
        use_ai=True,
        enable_learning=True,
        verbose=True
    )
    
    try:
        # 初期化
        await agent.initialize()
        
        # 既存セッションの読み込み（あれば）
        agent.load_session()
        
        # 対話型セッション開始
        await agent.interactive_session()
        
    finally:
        # セッションの保存
        agent.save_session()
        
        # クリーンアップ
        await agent.cleanup()
        
        print("\nエージェントを終了しました")


if __name__ == "__main__":
    asyncio.run(main())