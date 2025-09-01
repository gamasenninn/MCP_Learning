# MCP Agent ツール実行フロー - デバッグ用詳細ガイド

このドキュメントは、MCP Agentでのツール実行の完全なフローを詳細に記録し、デバッグの土台として使用するためのものです。

## 📍 エントリーポイント
```
ユーザー入力例: "売上が高い順に商品を表示して"
```

## 1️⃣ リクエスト受信 (`mcp_agent.py`)

### `MCPAgent.process_request(user_query: str)`
- **役割**: ユーザーリクエストの最初の受付窓口
- **処理内容**:
  - セッション統計の更新: `session_stats["total_requests"] += 1`
  - 会話履歴の確認: `conversation_manager.get_conversation_summary()`
  - コンテキスト情報の表示
- **次のステップ**: `_execute_interactive_dialogue(user_query)`

## 2️⃣ 対話的実行開始 (`mcp_agent.py`)

### `MCPAgent._execute_interactive_dialogue(user_query: str)`
- **役割**: 統合実行エンジンのエントリーポイント
- **処理内容**:
  1. **クエリコンテキスト準備** (`_prepare_query_context`)
     - `self.current_user_query = user_query` (ErrorHandlerで後で使用)
     - `state_manager.add_conversation_entry("user", user_query)`
  2. **実行フロー制御** (`_handle_execution_flow`)

## 3️⃣ 実行フロー制御 (`mcp_agent.py`)

### `MCPAgent._handle_execution_flow(user_query: str)`
- **役割**: 実行パスの決定とルーティング
- **処理フロー**:
  1. **未完了タスクの確認**: `state_manager.has_pending_tasks()`
  2. **実行タイプの判定** (`_determine_execution_type`)
     - 会話コンテキスト取得: `conversation_manager.get_recent_context()`
     - ツール情報収集: `connection_manager.format_tools_for_llm()`
     - LLMでタイプ判定: `NO_TOOL` / `CLARIFICATION` / `TOOL`
  3. **状態への記録**: `state_manager.set_user_query(user_query, execution_type)`
  4. **実行タイプ別ルーティング** (`_route_by_execution_type`)

### 実行タイプの判定結果
- **NO_TOOL**: 通常の会話応答
- **CLARIFICATION**: ユーザーへの確認が必要
- **TOOL**: ツール実行が必要（今回のケース）

## 4️⃣ タスクリスト生成と実行準備 (`mcp_agent.py`)

### `MCPAgent._execute_with_tasklist(user_query: str)`
- **役割**: タスクリストの生成とタスク実行の開始
- **処理フロー**:
  1. **タスクリスト生成** (`_generate_task_list_with_retry`)
     - LLMによるタスク分解
     - リトライ機能付き（最大3回）
  2. **TaskStateオブジェクト作成**: `task_manager.create_tasks_from_list`
  3. **状態管理への登録**: 各タスクを`state_manager.add_pending_task(task)`
  4. **CLARIFICATION処理**: 確認タスクがある場合の優先処理
  5. **タスク実行開始**: `task_executor.execute_task_sequence(tasks, user_query)`

### 生成されるタスクリスト例
```python
[
    {"tool": "list_tables", "params": {}, "description": "データベース内のテーブル一覧確認"},
    {"tool": "get_table_schema", "params": {"table_name": "sales"}, "description": "売上テーブル構造確認"},
    {"tool": "execute_safe_query", "params": {"sql": "SELECT * FROM products ORDER BY sales DESC"}, "description": "売上順に商品表示"}
]
```

## 5️⃣ タスクシーケンス実行 (`task_executor.py`)

### `TaskExecutor.execute_task_sequence(tasks, user_query)`
- **役割**: タスクリストの順次実行とコンテキスト管理
- **重要な初期化**:
  - `self.current_user_query = user_query` (ErrorHandlerに伝達用)
  - `execution_context = []` (実行履歴の蓄積)
- **各タスクの処理**:
  1. **ステップ表示**: `display.show_step_start(i+1, total, description)`
  2. **パラメータ解決**: `resolve_parameters_with_llm(task, execution_context)`
  3. **ツール呼び出し表示**: `display.show_tool_call(tool, params)`
  4. **リトライ付き実行**: `execute_tool_with_retry`
  5. **結果の状態更新**: `state_manager.move_task_to_completed`
  6. **実行コンテキスト更新**: `execution_context.append(...)`

### パラメータ解決プロセス
- **入力**: 現在のタスクと過去の実行履歴
- **処理**: LLMが過去の結果を参照してパラメータを動的決定
- **出力**: 解決されたパラメータ辞書

## 6️⃣ リトライ付きツール実行（核心部分）(`task_executor.py`)

### `TaskExecutor.execute_tool_with_retry(tool, params, description)`
- **役割**: エラー処理とリトライを含む実際のツール実行
- **新機能**: 実行コンテキストの取得と活用

#### 📈 実行コンテキスト取得（今回の改善点）
```python
# StateManagerから過去の実行結果を取得
completed_tasks = self.state_manager.get_completed_tasks()
execution_context = []
for task in completed_tasks[-5:]:  # 最新5件
    execution_context.append({
        "tool": task.tool,
        "description": task.description,
        "result": task.result
    })
```

#### 🔄 リトライループ処理
```python
for attempt in range(max_retries + 1):  # デフォルト3回
    # 1. ツール実行
    try:
        raw_result = await connection_manager.call_tool(tool, current_params)
        is_exception = False
    except Exception as e:
        raw_result = f"ツールエラー: {e}"
        is_exception = True
    
    # 2. LLM判断（必ず実行）
    if self.error_handler and self.llm:
        judgment = await self.error_handler.judge_and_process_result(
            tool=tool,
            current_params=current_params,
            original_params=original_params,
            result=raw_result,
            execution_context=execution_context  # 🆕 新機能
        )
        
        # 3. 判断に基づく次の行動
        if judgment.get("needs_retry") and attempt < max_retries:
            # パラメータを修正してリトライ
            current_params = judgment.get("corrected_params", current_params)
        else:
            # 終了（成功または最大試行回数到達）
            return judgment.get("processed_result")
```

## 7️⃣ エラーハンドリングとLLM判断 (`error_handler.py`)

### `ErrorHandler.judge_and_process_result(...)`
- **役割**: 実行結果の成功/失敗判定とパラメータ修正
- **新機能**: 実行履歴を考慮した判断

#### プロンプト生成 (`build_judgment_prompt`)
```
あなたはツール実行結果を判断するエキスパートです。以下の実行結果を分析してください。

## 現在実行中のタスク
タスク: {description}

## 実行情報
- ツール名: {tool}
- 現在のパラメータ: {current_params}
- 元のパラメータ: {original_params}
- 試行回数: {attempt}/{max_retries + 1}
- ユーザーの要求: {current_user_query}

## 関連する実行履歴 🆕
1. ツール: list_tables | 説明: データベース内のテーブル一覧確認 | 結果: テーブル一覧...
2. ツール: get_table_schema | 説明: 売上テーブル構造確認 | 結果: salesテーブル構造...

## 実行結果
{result}

## 判断基準
1. 成功判定: 有効なデータが含まれている（空でない結果）
2. 失敗判定: 結果が空文字列（""）、エラーメッセージが含まれている
3. リトライ判定: パラメータを修正すれば成功する可能性がある

## 基本的なJOIN構文例
- 基本JOIN: `SELECT a.col, b.col FROM table1 a JOIN table2 b ON a.id = b.foreign_id`
- 集計JOIN: `SELECT a.name, SUM(b.amount) FROM table1 a JOIN table2 b ON a.id = b.foreign_id GROUP BY a.name`
```

#### LLM応答例
```json
{
    "is_success": false,
    "needs_retry": true,
    "error_reason": "salesカラムが存在しません",
    "corrected_params": {
        "sql": "SELECT p.name, SUM(s.total_amount) FROM products p JOIN sales s ON p.id = s.product_id GROUP BY p.name ORDER BY SUM(s.total_amount) DESC"
    },
    "processed_result": "修正されたクエリで再実行します",
    "summary": "JOINクエリに修正しました"
}
```

## 8️⃣ ツール呼び出し (`connection_manager.py`)

### `ConnectionManager.call_tool(tool_name, arguments)`
- **役割**: 実際のMCPサーバーとの通信
- **処理内容**:
  - ツール存在確認
  - MCPクライアントでのツール実行
  - 結果の取得と返却
- **エラー処理**: サーバー通信エラー、ツール実行エラーの補足

## 9️⃣ 状態管理 (`state_manager.py`)

### 主要メソッド
- **`add_pending_task(task)`**: 実行待ちタスクの追加
- **`move_task_to_completed(task_id, result, error)`**: タスク完了の記録
- **`get_completed_tasks()`**: 完了済みタスクの取得（実行コンテキストで使用）

### セッション永続化
- **セッションファイル**: `.mcp_agent/session.json`
- **タスク状態**: pending_tasks, completed_tasks
- **会話履歴**: conversation_context

## 🔟 結果解釈と応答生成 (`mcp_agent.py`)

### `MCPAgent._interpret_planned_results(user_query, execution_context)`
- **役割**: 全タスクの実行結果を統合してユーザー向け応答を生成
- **処理内容**:
  - 実行結果の収集
  - LLMによる結果解釈
  - ユーザーフレンドリーな応答の生成
- **会話履歴への追加**: `conversation_manager.add_to_conversation`

## 🔴 エラーパスとデバッグポイント

### A. 正常リトライパス
1. **エラー検出**: `connection_manager.call_tool` でエラー発生
2. **LLM判断**: `error_handler.judge_and_process_result` で分析
3. **パラメータ修正**: `corrected_params` でリトライ
4. **再実行**: 修正されたパラメータで再度実行

### B. 最大リトライ超過パス
1. **判断**: `needs_retry=True` だが `attempt >= max_retries`
2. **終了**: エラーメッセージを生成して終了
3. **状態更新**: `state_manager.move_task_to_completed(error=...)`

### C. 成功パス
1. **判断**: `is_success=True` または `needs_retry=False`
2. **結果返却**: `processed_result` を返す
3. **状態更新**: `state_manager.move_task_to_completed(result=...)`

## 🛠️ デバッグ時の確認ポイント

### 1. 実行開始時
- **確認項目**: `execute_tool_with_retry` 開始ログ
- **ログ形式**: `[DEBUG] execute_tool_with_retry が呼び出されました: tool={tool}`

### 2. 実行コンテキスト取得
- **確認項目**: 過去の実行結果が正しく取得されているか
- **デバッグ出力**: `[DEBUG] 実行コンテキスト取得エラー: {error}`

### 3. LLM判断
- **確認項目**: LLMの生レスポンス
- **ログ形式**: `[LLM生レスポンス] {response}`
- **判断結果**: `[LLM判断] 成功: {is_success}, リトライ必要: {needs_retry}`

### 4. ツール実行
- **確認項目**: 実際のツール呼び出し結果
- **エラー例**: "no such column", "no such table"

### 5. パラメータ修正
- **確認項目**: 修正されたパラメータ
- **ログ形式**: `[LLM修正案] {corrected_params}`

## 📊 今回の改善点サマリー

### 🆕 実行コンテキスト共有システム
- **TaskExecutor**: 過去5件の完了タスクを取得
- **ErrorHandler**: 実行履歴を含むプロンプト生成
- **効果**: スキーマ情報、API認証情報、ディレクトリ構造等を参照可能

### 🔄 完全LLM信頼設計の復活
- **変更前**: 例外発生時のみLLM判断
- **変更後**: 全ての実行結果でLLM判断
- **効果**: 空の結果や微妙な失敗ケースも検出可能

### 🎯 汎用的なエラー処理
- **設計方針**: SQL固有ではなく汎用的な実装
- **適用範囲**: データベース、API、ファイル操作等すべて
- **拡張性**: 新しいツールタイプにも対応可能

このフローを参考に、問題が発生している箇所を特定し、適切なデバッグを行ってください。