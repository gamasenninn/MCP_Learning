#!/usr/bin/env python3
"""
適応型タスクプランナー
エラー情報を基にタスクを動的に再計画
"""

import asyncio
import json
import os
import sys
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from dotenv import load_dotenv

# Windows環境でのUnicode対応
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

# .envファイルから環境変数を読み込む
load_dotenv()

from openai import AsyncOpenAI
from universal_task_planner import UniversalTaskPlanner, UniversalTask

@dataclass
class FailureContext:
    """失敗コンテキスト"""
    failed_task: UniversalTask
    error_message: str
    attempt_count: int
    previous_approaches: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

class AdaptiveTaskPlanner(UniversalTaskPlanner):
    """エラーから学習して適応するタスクプランナー"""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        self.failure_history: List[FailureContext] = []
        self.adaptation_cache = {}
        self.learning_enabled = True
    
    async def replan_on_error(
        self,
        original_query: str,
        failed_tasks: List[UniversalTask],
        error_info: Dict[str, Any]
    ) -> List[UniversalTask]:
        """エラー情報を基にタスクを再計画"""
        
        print("\n[適応的再計画] エラーから学習してタスクを再計画中...")
        
        # 失敗コンテキストを作成
        failure_context = self._create_failure_context(failed_tasks, error_info)
        self.failure_history.append(failure_context)
        
        # 再計画プロンプトを構築
        replan_prompt = self._build_replan_prompt(
            original_query,
            failure_context,
            self.tools_info
        )
        
        try:
            # LLMに再計画を依頼
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "あなたはMCPタスクの再計画専門家です。失敗から学習し、より良いアプローチを提案してください。"},
                    {"role": "user", "content": replan_prompt}
                ],
                temperature=0.5,
                max_tokens=1500
            )
            
            # 新しいタスクを解析
            new_tasks = self._parse_tasks(response.choices[0].message.content)
            
            if new_tasks:
                print(f"  [成功] {len(new_tasks)}個の新しいタスクを生成")
                
                # 検証
                errors = self.validate_tasks(new_tasks)
                if errors:
                    print("  [警告] 検証エラー:")
                    for error in errors:
                        print(f"    - {error}")
                
                return new_tasks
            else:
                print("  [失敗] タスクの再計画に失敗")
                return []
                
        except Exception as e:
            print(f"  [エラー] 再計画中にエラー: {e}")
            return []
    
    def _create_failure_context(
        self,
        failed_tasks: List[UniversalTask],
        error_info: Dict[str, Any]
    ) -> FailureContext:
        """失敗コンテキストを作成"""
        
        # 最初に失敗したタスクを特定
        failed_task = None
        for task in failed_tasks:
            if task.error:
                failed_task = task
                break
        
        if not failed_task:
            failed_task = failed_tasks[-1] if failed_tasks else UniversalTask(
                id="unknown",
                name="不明なタスク",
                tool="unknown"
            )
        
        return FailureContext(
            failed_task=failed_task,
            error_message=error_info.get("error", "不明なエラー"),
            attempt_count=error_info.get("attempts", 1),
            previous_approaches=[task.tool for task in failed_tasks]
        )
    
    def _build_replan_prompt(
        self,
        original_query: str,
        failure_context: FailureContext,
        tools_info: Dict[str, Any]
    ) -> str:
        """再計画用のプロンプトを構築"""
        
        prompt_parts = [
            "以下の失敗したタスクを分析し、別のアプローチで再計画してください。",
            "",
            "## 元のリクエスト",
            original_query,
            "",
            "## 失敗したタスク",
            f"ツール: {failure_context.failed_task.tool}",
            f"パラメータ: {json.dumps(failure_context.failed_task.params, ensure_ascii=False)}",
            f"エラー: {failure_context.error_message}",
            "",
            "## 試行済みのアプローチ",
            ", ".join(failure_context.previous_approaches),
            "",
            "## 利用可能なツール",
            json.dumps(list(tools_info.keys()), ensure_ascii=False),
            "",
            "## 再計画の指針",
            "1. 同じエラーを避ける別のアプローチを考える",
            "2. より小さなステップに分解することを検討",
            "3. 代替ツールの使用を検討",
            "4. エラーの原因を回避するパラメータを使用",
            "",
            "## 出力形式",
            "タスクをJSON形式で出力してください：",
            "```json",
            "[",
            "  {",
            '    "id": "task_1",',
            '    "name": "タスクの説明",',
            '    "tool": "ツール名",',
            '    "params": {"param1": value1}',
            "  }",
            "]",
            "```"
        ]
        
        # ゼロ除算エラーの特別な処理
        if "zero" in failure_context.error_message.lower() or "ゼロ" in failure_context.error_message:
            prompt_parts.extend([
                "",
                "## 特別な注意",
                "ゼロ除算エラーが発生しています。除数が0にならないよう注意してください。"
            ])
        
        return "\n".join(prompt_parts)
    
    async def learn_from_success(
        self,
        query: str,
        successful_tasks: List[UniversalTask]
    ):
        """成功したタスクパターンを学習"""
        
        if not self.learning_enabled:
            return
        
        # 成功パターンをキャッシュ
        cache_key = self._get_query_signature(query)
        self.adaptation_cache[cache_key] = {
            "tasks": [task.to_dict() for task in successful_tasks],
            "timestamp": datetime.now().isoformat()
        }
        
        print(f"[学習] 成功パターンを記録: {len(successful_tasks)}個のタスク")
    
    def _get_query_signature(self, query: str) -> str:
        """クエリのシグネチャを生成"""
        # クエリの主要な要素を抽出してキーを作成
        import hashlib
        normalized = query.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()[:16]
    
    async def plan_with_adaptation(
        self,
        query: str,
        use_cache: bool = True
    ) -> List[UniversalTask]:
        """適応的な学習を使用してタスクを計画"""
        
        # キャッシュチェック
        if use_cache:
            cache_key = self._get_query_signature(query)
            if cache_key in self.adaptation_cache:
                cached = self.adaptation_cache[cache_key]
                print(f"[キャッシュ] 学習済みパターンを使用")
                
                # キャッシュからタスクを復元
                tasks = []
                for task_dict in cached["tasks"]:
                    task = UniversalTask(
                        id=task_dict["id"],
                        name=task_dict["name"],
                        tool=task_dict["tool"],
                        server=task_dict.get("server"),
                        params=task_dict.get("params", {}),
                        dependencies=task_dict.get("dependencies", [])
                    )
                    tasks.append(task)
                return tasks
        
        # 通常の計画を実行
        return await self.plan_task(query)
    
    def get_adaptation_report(self) -> str:
        """適応学習レポートを生成"""
        
        report_lines = [
            "適応型タスクプランナー学習レポート",
            "=" * 60
        ]
        
        # 学習統計
        report_lines.extend([
            "\n[学習統計]",
            f"  失敗履歴: {len(self.failure_history)}件",
            f"  成功パターン: {len(self.adaptation_cache)}件"
        ])
        
        # 最近の失敗
        if self.failure_history:
            report_lines.append("\n[最近の失敗と対処]")
            for context in self.failure_history[-3:]:
                report_lines.append(f"  - {context.failed_task.tool}: {context.error_message[:50]}")
        
        # 学習済みパターン
        if self.adaptation_cache:
            report_lines.append("\n[学習済みパターン]")
            for key in list(self.adaptation_cache.keys())[-5:]:
                cached = self.adaptation_cache[key]
                task_count = len(cached["tasks"])
                report_lines.append(f"  - パターン{key[:8]}: {task_count}個のタスク")
        
        return "\n".join(report_lines)


# テスト関数
async def test_adaptive_planner():
    """適応型タスクプランナーのテスト"""
    
    print("適応型タスクプランナーのテスト")
    print("=" * 60)
    
    # APIキーチェック
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("[警告] OPENAI_API_KEYが設定されていません")
        return
    
    planner = AdaptiveTaskPlanner(api_key=api_key)
    await planner.initialize()
    
    # テスト1: 通常のタスク計画
    print("\n[テスト1] 通常のタスク計画")
    print("-" * 40)
    
    query1 = "100と200を足して、その結果を2で割って"
    tasks1 = await planner.plan_with_adaptation(query1)
    
    print(f"生成されたタスク: {len(tasks1)}個")
    for task in tasks1:
        print(f"  - {task.name}: {task.tool}({task.params})")
    
    # テスト2: エラー後の再計画
    print("\n[テスト2] エラー後の再計画")
    print("-" * 40)
    
    # ゼロ除算エラーをシミュレート
    failed_task = UniversalTask(
        id="failed_1",
        name="ゼロで除算",
        tool="divide",
        server="calculator",
        params={"a": 100, "b": 0},
        error="division by zero"
    )
    
    error_info = {
        "error": "ゼロ除算エラー",
        "attempts": 2
    }
    
    new_tasks = await planner.replan_on_error(
        "100を0で割って",
        [failed_task],
        error_info
    )
    
    if new_tasks:
        print(f"再計画されたタスク: {len(new_tasks)}個")
        for task in new_tasks:
            print(f"  - {task.name}: {task.tool}({task.params})")
    
    # テスト3: 成功パターンの学習
    print("\n[テスト3] 成功パターンの学習")
    print("-" * 40)
    
    # 成功したタスクを学習
    successful_tasks = [
        UniversalTask(
            id="success_1",
            name="加算",
            tool="add",
            params={"a": 100, "b": 200}
        ),
        UniversalTask(
            id="success_2",
            name="除算",
            tool="divide",
            params={"a": "{task_1}", "b": 2}
        )
    ]
    
    await planner.learn_from_success(query1, successful_tasks)
    
    # 同じクエリでキャッシュを使用
    print("\n同じクエリを再実行（キャッシュ使用）:")
    tasks_cached = await planner.plan_with_adaptation(query1, use_cache=True)
    print(f"キャッシュから{len(tasks_cached)}個のタスクを取得")
    
    # 学習レポート
    print("\n" + "=" * 60)
    print(planner.get_adaptation_report())


if __name__ == "__main__":
    asyncio.run(test_adaptive_planner())