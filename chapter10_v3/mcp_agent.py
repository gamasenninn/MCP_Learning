#!/usr/bin/env python3
"""
MCP Agent V3 - AGENT.md方式による革新的MCPエージェント

V3の特徴:
- AGENT.mdによるカスタマイズ可能な指示システム
- 階層的プロンプト（基本能力 + カスタム指示）
- シンプルで保守しやすいアーキテクチャ
- 学習機能の代わりにユーザー主導の指示書方式
"""

import asyncio
import json
import os
import sys
from typing import Dict, List, Any, Optional
from datetime import datetime
from openai import AsyncOpenAI

from connection_manager import ConnectionManager
from task_executor import TaskExecutor, Task


class MCPAgent:
    """
    AGENT.md方式による革新的MCPエージェント（V3）
    
    カレントディレクトリのAGENT.mdから指示を読み込み、
    基本的な推論能力と組み合わせてタスクを実行
    """
    
    def __init__(self, verbose: bool = True):
        """
        Args:
            verbose: 詳細ログ出力
        """
        self.verbose = verbose
        self.base_instructions = self._load_base_instructions()
        self.custom_instructions = self._load_agent_md()
        
        # コンポーネント初期化
        self.connection_manager = ConnectionManager(verbose=verbose)
        self.executor = TaskExecutor(self.connection_manager, verbose=verbose)
        
        # LLMクライアント
        self.llm = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # セッション管理
        self.conversation_history: List[Dict] = []
        self.session_stats = {
            "start_time": datetime.now(),
            "total_requests": 0,
            "successful_tasks": 0,
            "failed_tasks": 0
        }
    
    def _load_base_instructions(self) -> str:
        """基本的な推論能力の指示を定義"""
        return """
## 基本能力
あなたは知的なタスクプランナーです。以下の能力を持っています：

1. **ツール理解**: 各ツールの説明から最適な使用方法を推論できます
2. **依存関係解析**: 複数ステップが必要な場合、適切な順序を決定できます  
3. **エラー対応**: エラーメッセージから問題を特定し、修正方法を提案できます
4. **パラメータ推論**: ユーザーの要求から適切なパラメータ値を決定できます

## タスク分解ルール
- 1つのタスクは1つのツールを使用
- 前のタスクの結果が必要な場合は依存関係を設定
- パラメータには具体的な値を指定（空の辞書は禁止）
- 複雑な要求は段階的に分解

## 出力形式
### 複雑なタスク（複数ツール必要）
```json
{
  "tasks": [
    {
      "id": "task_1",
      "tool": "ツール名",
      "params": {"param1": "値1"},
      "dependencies": []
    },
    {
      "id": "task_2", 
      "tool": "ツール名",
      "params": {"param1": "{task_1}"},
      "dependencies": ["task_1"]
    }
  ]
}
```

### シンプルなタスク（単一ツール）
```json
{
  "type": "SIMPLE",
  "tool": "ツール名",
  "params": {"param1": "値1"}
}
```

### ツール不要（挨拶・質問）
```json
{
  "type": "NO_TOOL",
  "response": "適切な応答メッセージ"
}
```
"""
    
    def _load_agent_md(self) -> str:
        """カレントディレクトリのAGENT.mdを読み込み"""
        agent_md_path = "AGENT.md"
        
        if os.path.exists(agent_md_path):
            try:
                with open(agent_md_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if self.verbose:
                    print(f"[設定] AGENT.mdを読み込みました ({len(content)}文字)")
                return content
            except Exception as e:
                if self.verbose:
                    print(f"[警告] AGENT.md読み込みエラー: {e}")
                return ""
        else:
            if self.verbose:
                print("[情報] AGENT.mdが見つかりません（基本能力のみで動作）")
            return ""
    
    async def initialize(self):
        """エージェントの初期化（MCP接続など）"""
        if self.verbose:
            print("=" * 60)
            print(" MCP Agent V3 - AGENT.md方式")
            print("=" * 60)
        
        # MCP接続管理を初期化
        await self.connection_manager.initialize()
        
        if self.verbose:
            print(f"\n[指示書] {'カスタム指示あり' if self.custom_instructions else '基本能力のみ'}")
            print("=" * 60)
    
    async def process_request(self, user_query: str) -> str:
        """
        ユーザーのリクエストを処理
        
        Args:
            user_query: ユーザーからの要求
            
        Returns:
            処理結果のメッセージ
        """
        self.session_stats["total_requests"] += 1
        
        if self.verbose:
            print(f"\n[リクエスト #{self.session_stats['total_requests']}] {user_query}")
            print("-" * 60)
        
        try:
            # 1. タスク分解
            plan_result = await self._plan_tasks(user_query)
            
            # 2. ツール不要の場合
            if plan_result.get("type") == "NO_TOOL":
                return plan_result.get("response", "了解しました。")
            
            # 3. タスク実行
            tasks = self._extract_tasks(plan_result)
            if not tasks:
                return "実行可能なタスクが見つかりませんでした。"
            
            if self.verbose:
                print(f"[分析] {len(tasks)}個のタスクに分解")
            
            # 4. 実行
            results = await self.executor.execute_batch(tasks)
            
            # 5. 統計更新
            for result in results:
                if result.success:
                    self.session_stats["successful_tasks"] += 1
                else:
                    self.session_stats["failed_tasks"] += 1
            
            # 6. 結果の解釈
            response = await self._interpret_results(user_query, results)
            
            # 7. 会話履歴に追加
            self._add_to_history("user", user_query)
            self._add_to_history("assistant", response)
            
            return response
            
        except Exception as e:
            error_msg = f"処理エラー: {str(e)}"
            if self.verbose:
                print(f"[エラー] {error_msg}")
            return error_msg
    
    async def _plan_tasks(self, user_query: str) -> Dict:
        """
        ユーザーの要求をタスクに分解
        
        AGENT.mdの指示と基本能力を組み合わせてLLMに問い合わせ
        """
        # 利用可能なツール情報を取得
        tools_info = self.connection_manager.format_tools_for_llm()
        
        # 階層的プロンプトの構築
        prompt = f"""{self.base_instructions}

## 利用可能なツール
{tools_info}

## プロジェクト固有の指示（最優先）
{self.custom_instructions if self.custom_instructions else "なし"}

## 重要な判断基準
- プロジェクト固有の指示があれば、それに従って判断
- なければ、基本能力とツール説明から最適な方法を推論
- データベース操作の場合、段階的アプローチを検討

## ユーザーの要求
{user_query}

上記を踏まえて、適切にタスクを分解してください。JSON形式で回答してください。
"""
        
        try:
            response = await self.llm.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.2
            )
            
            result = json.loads(response.choices[0].message.content)
            
            if self.verbose:
                task_count = len(result.get("tasks", []))
                if result.get("type") == "SIMPLE":
                    task_count = 1
                elif result.get("type") == "NO_TOOL":
                    task_count = 0
                print(f"[計画] {task_count}個のタスクを生成")
            
            return result
            
        except Exception as e:
            if self.verbose:
                print(f"[エラー] タスク分解失敗: {e}")
            return {"type": "NO_TOOL", "response": f"タスク分解エラー: {str(e)}"}
    
    def _extract_tasks(self, plan_result: Dict) -> List[Task]:
        """プランからTaskオブジェクトのリストを生成"""
        tasks = []
        
        if plan_result.get("type") == "SIMPLE":
            # シンプルなタスク
            task = Task(
                id="task_1",
                tool=plan_result.get("tool", ""),
                params=plan_result.get("params", {})
            )
            tasks.append(task)
        elif "tasks" in plan_result:
            # 複雑なタスク
            for task_data in plan_result["tasks"]:
                task = Task(
                    id=task_data.get("id", ""),
                    tool=task_data.get("tool", ""),
                    params=task_data.get("params", {}),
                    dependencies=task_data.get("dependencies", [])
                )
                tasks.append(task)
        
        return tasks
    
    async def _interpret_results(self, original_query: str, results: List) -> str:
        """
        実行結果をユーザーに分かりやすく解釈
        
        Args:
            original_query: 元のユーザー要求
            results: 実行結果のリスト
            
        Returns:
            解釈されたメッセージ
        """
        # 成功した結果を取得
        successful_results = [r for r in results if r.success]
        failed_results = [r for r in results if not r.success]
        
        if not successful_results and not failed_results:
            return "実行するタスクがありませんでした。"
        
        if not successful_results:
            # 全て失敗
            error_messages = [r.error for r in failed_results if r.error]
            return f"実行に失敗しました。エラー: {', '.join(error_messages[:2])}"
        
        # 最後の成功結果を基本とする
        last_result = successful_results[-1].result
        
        # シンプルな結果表示
        if isinstance(last_result, (dict, list)):
            if isinstance(last_result, dict) and "results" in last_result:
                # データベースクエリの結果
                data = last_result["results"]
                if data:
                    row_count = len(data)
                    if row_count <= 10:
                        # 少量データは全表示
                        formatted_data = self._format_table_data(data)
                        return f"実行結果（{row_count}件）:\n{formatted_data}"
                    else:
                        # 大量データは概要のみ
                        sample_data = self._format_table_data(data[:5])
                        return f"実行結果（{row_count}件、最初の5件を表示）:\n{sample_data}\n\n... 他 {row_count - 5}件"
                else:
                    return "クエリは正常に実行されましたが、結果は空でした。"
            else:
                # その他の辞書・リスト
                return f"実行結果: {str(last_result)[:500]}{'...' if len(str(last_result)) > 500 else ''}"
        else:
            # プリミティブ値
            return f"実行結果: {last_result}"
    
    def _format_table_data(self, data: List[Dict]) -> str:
        """テーブル形式のデータを見やすくフォーマット"""
        if not data:
            return "データなし"
        
        # カラム名を取得
        columns = list(data[0].keys())
        
        # 各カラムの幅を計算
        widths = {}
        for col in columns:
            widths[col] = max(
                len(str(col)),
                max(len(str(row.get(col, ""))) for row in data)
            )
            # 最大幅制限
            widths[col] = min(widths[col], 20)
        
        # ヘッダー作成
        header = " | ".join(col.ljust(widths[col]) for col in columns)
        separator = "-" * len(header)
        
        # データ行作成
        rows = []
        for row in data:
            row_str = " | ".join(
                str(row.get(col, "")).ljust(widths[col])[:widths[col]]
                for col in columns
            )
            rows.append(row_str)
        
        return f"{header}\n{separator}\n" + "\n".join(rows)
    
    def _add_to_history(self, role: str, message: str):
        """会話履歴に追加"""
        self.conversation_history.append({
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "message": message
        })
        
        # 履歴の長さ制限（最新50件）
        if len(self.conversation_history) > 50:
            self.conversation_history = self.conversation_history[-50:]
    
    def get_session_stats(self) -> Dict:
        """セッション統計を取得"""
        current_time = datetime.now()
        duration = current_time - self.session_stats["start_time"]
        
        return {
            **self.session_stats,
            "session_duration": str(duration),
            "success_rate": (
                self.session_stats["successful_tasks"] / 
                max(1, self.session_stats["successful_tasks"] + self.session_stats["failed_tasks"])
            ) * 100
        }
    
    async def close(self):
        """リソースの解放"""
        await self.connection_manager.close()


async def main():
    """対話型エージェントのメイン関数"""
    agent = MCPAgent(verbose=True)
    
    try:
        # 初期化
        await agent.initialize()
        
        print("\n" + "=" * 60)
        print(" MCP Agent V3 - 対話開始")
        print("=" * 60)
        print("使用方法:")
        print("  - 自然言語でリクエストを入力")
        print("  - 'stats' : セッション統計表示")
        print("  - 'exit' : 終了")
        print("=" * 60)
        
        # 対話ループ
        while True:
            try:
                user_input = input("\nAgent> ").strip()
                
                if user_input.lower() in ['exit', 'quit', '終了']:
                    print("エージェントを終了します...")
                    break
                elif user_input.lower() == 'stats':
                    stats = agent.get_session_stats()
                    print(f"\n[セッション統計]")
                    print(f"  稼働時間: {stats['session_duration']}")
                    print(f"  総リクエスト: {stats['total_requests']}")
                    print(f"  成功タスク: {stats['successful_tasks']}")
                    print(f"  失敗タスク: {stats['failed_tasks']}")
                    print(f"  成功率: {stats['success_rate']:.1f}%")
                    continue
                
                if not user_input:
                    continue
                
                # リクエスト処理
                response = await agent.process_request(user_input)
                print(f"\n{response}")
                
            except KeyboardInterrupt:
                print("\n\nエージェントを終了します...")
                break
            except Exception as e:
                print(f"エラー: {e}")
    
    finally:
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())