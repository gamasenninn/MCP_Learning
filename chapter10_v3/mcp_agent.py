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
        self.executor = TaskExecutor(
            self.connection_manager, 
            verbose=verbose, 
            param_corrector=self._correct_parameters
        )
        
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

1. **ツール理解**: 各ツールの説明を読み、用途を理解して適切に選択
2. **依存関係解析**: 複数ステップが必要な場合、適切な順序を決定
3. **並列実行判断**: 独立したタスクは並列実行可能と判断
4. **エラー対応**: エラーメッセージから問題を特定し、修正方法を提案

## タスク分解ルール
- **最重要**: まず「ツールが必要かどうか」を判断する
- 利用可能なツールの説明をよく読む
- 1つのタスクは1つのツールを使用
- 前のタスクの結果が必要な場合は依存関係を設定
- 数式や複雑な計算は演算の優先順位を考慮
- パラメータには具体的な値を指定

## ツール不要の判定基準
以下の場合は **NO_TOOL** を選択してください：
- **挨拶**: 「こんにちは」「おはよう」「お疲れさま」等
- **自己紹介**: 「私の名前は〇〇です」「私は〇〇と申します」等
- **雑談**: 「今日はいい天気ですね」「お元気ですか」等
- **感想・意見**: 「それは面白いですね」「よくできました」等
- **単純な返答**: 「ありがとう」「わかりました」「そうですね」等
- **質問への応答**: 相手の質問に対する単純な答え

これらは人間らしい会話であり、外部ツールは不要です。

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

### ツール不要（日常会話）
```json
{
  "type": "NO_TOOL",
  "response": "適切な応答メッセージ",
  "reason": "挨拶/自己紹介/雑談等"
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

## プロジェクト固有の追加指示
{self.custom_instructions if self.custom_instructions else "なし"}

## 分析手順（必ず順序通りに実行）
**手順1**: まず以下を判定してください
- これは日常会話（挨拶・雑談・自己紹介等）ですか？
- YES → NO_TOOL を選択
- NO → 手順2へ

**手順2**: 作業が必要な場合のみ
1. 利用可能なツールの説明を読み、最適なツールを選択
2. ツールの説明に従って適切なパラメータを設定
3. 複雑なタスクは段階的に分解し、依存関係を明確にする
4. 数式がある場合は演算の優先順位（乗除算→加減算）を考慮
5. AGENT.mdの指示は追加のガイダンスとして活用

## ユーザーの要求
{user_query}

上記の手順に従って分析し、JSON形式で回答してください。
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
                    print(f"[計画] NO_TOOL選択 - 理由: {result.get('reason', '日常会話')}")
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
        LLMを使って全ての実行結果を統合的に解釈
        
        Args:
            original_query: 元のユーザー要求
            results: 全タスクの実行結果
            
        Returns:
            LLMが生成した自然な回答
        """
        # 全結果を収集（成功・失敗両方）
        all_results = []
        for r in results:
            result_info = {
                "task_id": r.task_id,
                "tool": r.tool,
                "params": r.params,
                "success": r.success
            }
            
            if r.success:
                # 成功時は結果データを抽出
                if hasattr(r.result, 'data'):
                    result_info["result"] = r.result.data
                elif hasattr(r.result, 'structured_content'):
                    result_info["result"] = r.result.structured_content
                else:
                    result_info["result"] = str(r.result)
            else:
                # 失敗時はエラー情報
                result_info["error"] = r.error
            
            all_results.append(result_info)
        
        # 依存関係の有無を判定
        has_dependencies = any(
            len(getattr(r, 'dependencies', [])) > 0 for r in results
        )
        
        # 結果をJSONシリアライズ可能にする
        serializable_results = self._safe_serialize(all_results)
        
        # LLMに解釈を依頼
        interpretation_prompt = f"""
あなたは実行結果を解釈して、ユーザーに分かりやすく回答するアシスタントです。

## ユーザーの元の質問
{original_query}

## 実行されたタスクと結果
{json.dumps(serializable_results, ensure_ascii=False, indent=2)}

## タスクの関係性
{"依存関係あり（最終結果が重要）" if has_dependencies else "独立した並列タスク（全結果が重要）"}

## プロジェクト固有の表示指示
{self.custom_instructions if self.custom_instructions else "特になし"}

## 回答のガイドライン
1. ユーザーの質問に直接答える
2. 依存関係がある場合は最終結果を中心に説明
3. 並列タスクの場合は全ての結果を含める
4. エラーがある場合は分かりやすく説明
5. 技術的な詳細は省いて自然な日本語で
6. 数値は適切にフォーマット（カンマ区切り、単位付きなど）

回答を生成してください：
"""
        
        try:
            response = await self.llm.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": interpretation_prompt}],
                temperature=0.3
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            # フォールバック：LLMが使えない場合
            successful_results = [r for r in results if r.success]
            if all(r.success for r in results):
                # 成功時は最後の結果を簡易表示
                if successful_results:
                    last_result = successful_results[-1].result
                    if hasattr(last_result, 'data'):
                        return f"実行完了: {str(last_result.data)[:200]}"
                return f"タスクが正常に完了しました。"
            else:
                failed = sum(1 for r in results if not r.success)
                return f"一部のタスクが失敗しました（{failed}/{len(results)}件失敗）"
    
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
    
    async def _correct_parameters(self, tool: str, params: Dict[str, Any], error: str) -> Optional[Dict[str, Any]]:
        """
        エラーに基づいてパラメータを修正
        
        Args:
            tool: エラーが発生したツール名
            params: 元のパラメータ
            error: エラーメッセージ
            
        Returns:
            修正されたパラメータ（修正できない場合はNone）
        """
        try:
            # AGENT.mdのエラー対処指示を含む修正プロンプト
            correction_prompt = f"""
エラーが発生したため、パラメータの修正が必要です。

## エラー情報
ツール: {tool}
現在のパラメータ: {json.dumps(params, ensure_ascii=False)}
エラーメッセージ: {error}

## プロジェクト固有のエラー対処指示
{self.custom_instructions if self.custom_instructions else "なし"}

## 一般的なエラー対処パターン
- 404エラー（Not Found）→ パラメータの値を確認
- 天気API: "New York,JP" → "New York,US"
- データベース: "no such column" → 正しいカラム名に修正
- 計算ツール: 文字列 → 数値に変更

## 指示
上記のエラーメッセージを分析し、パラメータを修正してください。
修正後のパラメータのみをJSON形式で返してください。
修正が不可能な場合は、元のパラメータをそのまま返してください。

例:
{{"location": "Tokyo,JP", "units": "metric"}}
"""
            
            response = await self.llm.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": correction_prompt}],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            corrected_params = json.loads(response.choices[0].message.content)
            
            # 元のパラメータと同じ場合は修正なし
            if corrected_params == params:
                return None
                
            if self.verbose:
                print(f"  [パラメータ修正] {params} → {corrected_params}")
                
            return corrected_params
            
        except Exception as e:
            if self.verbose:
                print(f"  [修正エラー] パラメータ修正に失敗: {e}")
            return None
    
    def _safe_serialize(self, obj) -> Any:
        """
        オブジェクトをJSONシリアライズ可能な形式に変換
        
        Args:
            obj: 変換するオブジェクト
            
        Returns:
            JSONシリアライズ可能なオブジェクト
        """
        if obj is None:
            return None
        elif isinstance(obj, (str, int, float, bool)):
            return obj
        elif isinstance(obj, (list, tuple)):
            return [self._safe_serialize(item) for item in obj]
        elif isinstance(obj, dict):
            return {key: self._safe_serialize(value) for key, value in obj.items()}
        elif hasattr(obj, '__dict__'):
            # オブジェクトの属性を辞書として取得
            return {
                key: self._safe_serialize(value) 
                for key, value in obj.__dict__.items()
                if not key.startswith('_')  # プライベート属性は除外
            }
        elif hasattr(obj, 'dict') and callable(getattr(obj, 'dict')):
            # Pydanticモデルなどのdict()メソッドを持つオブジェクト
            try:
                return self._safe_serialize(obj.dict())
            except:
                return str(obj)
        elif hasattr(obj, 'to_dict') and callable(getattr(obj, 'to_dict')):
            # to_dict()メソッドを持つオブジェクト
            try:
                return self._safe_serialize(obj.to_dict())
            except:
                return str(obj)
        else:
            # その他は文字列化
            return str(obj)
    
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