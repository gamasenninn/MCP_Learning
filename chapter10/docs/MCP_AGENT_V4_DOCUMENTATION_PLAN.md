# MCP Agent V4 技術ガイド作成プラン

## 作成日時
2025-01-24

## 対象ファイル
- **ソースコード**: `mcp_agent.py` (948行)
- **ドキュメント**: `MCP_AGENT_V4_TECHNICAL_GUIDE.md`
- **保存場所**: `C:\MCP_Learning\chapter10_v5\`

## ドキュメント構成詳細

### 1. 概要とアーキテクチャ（約500行）

#### 1.1 MCP Agent V4の位置づけ
- Claude Code風の対話型エージェント
- Model Context Protocol (MCP)を活用した外部ツール統合
- 自然言語による指示を実行可能なタスクに変換
- Windows環境でのUnicode問題完全対応

#### 1.2 V3からV4への進化点
- **V3**: 一括実行型（全タスクを一度に計画・実行）
- **V4**: 対話的逐次実行（結果を見ながら次のステップを決定）
- **新機能**: チェックボックスUI、プログレス表示、リアルタイム更新
- **最適化**: サロゲート文字処理の効率化

#### 1.3 システムアーキテクチャ図
```
User Input
    ↓
MCPAgentV4 (Orchestrator)
    ├── ConnectionManager → MCP Servers
    ├── DisplayManager → UI (Basic/Rich)
    ├── ErrorHandler → リトライ・修正
    └── LLM Client → OpenAI API
    ↓
Response Output
```

#### 1.4 主要な設計思想
- **責任分離**: 各コンポーネントが明確な役割を持つ
- **防御in深度**: 複数レイヤーでのエラー処理
- **ユーザー体験**: 進行状況の可視化とリアルタイムフィードバック

### 2. 主要コンポーネント詳細（約800行）

#### 2.1 MCPAgentV4クラス（948行の中核）
- **役割**: 全体のオーケストレーター
- **主要属性**:
  - `config`: YAML設定管理
  - `connection_manager`: MCP接続管理
  - `display`: UI表示制御
  - `error_handler`: エラー処理統制
  - `llm`: OpenAI APIクライアント
  - `conversation_history`: 会話履歴管理
  - `execution_context`: 実行コンテキスト

- **主要メソッド**:
  - `process_request()`: メインエントリポイント
  - `_execute_interactive_dialogue()`: 実行タイプ振り分け
  - `_execute_with_tasklist()`: タスクリスト実行エンジン
  - `_execute_planned_task()`: 個別タスク実行
  - `_resolve_placeholders()`: プレースホルダー解決

#### 2.2 ConnectionManager（346行）
- **役割**: MCPサーバーとの接続管理・通信制御
- **主要機能**:
  - `initialize()`: 全サーバーへの接続確立
  - `call_tool()`: ツール実行（サロゲート文字対策込み）
  - `get_available_tools()`: 利用可能ツール一覧取得
  - `format_tools_for_llm()`: LLM用ツール情報フォーマット

- **技術的特徴**:
  - mcpServers形式の設定対応
  - FastMCP Clientを使用したStdio通信
  - CallToolResult処理でのサロゲート文字クリーンアップ
  - Windows環境対応（UTF-8エンコーディング）

#### 2.3 DisplayManager（基本版: 200行）
- **役割**: ユーザーへの視覚的フィードバック
- **主要機能**:
  - `show_checklist()`: タスクリスト表示
  - `update_checklist()`: 進捗更新
  - `show_tool_call()`: ツール実行表示
  - `show_step_complete()`: ステップ完了表示

- **表示要素**:
  - チェックボックス（`[ ]` / `[x]`）
  - 実行時間表示
  - プログレスインジケーター
  - ステータスメッセージ

#### 2.4 RichDisplayManager（拡張版: 400行）
- **役割**: リッチUIによる高度な表示機能
- **追加機能**:
  - ライブ更新（Live Updates）
  - シンタックスハイライト
  - プログレスバー
  - テーブル表示

- **Rich Library活用**:
  - `Live`: リアルタイム画面更新
  - `Syntax`: コードシンタックスハイライト
  - `Progress`: 視覚的進捗バー
  - `Panel`: 情報パネル表示

#### 2.5 ErrorHandler（323行）
- **役割**: エラー処理の統括管理
- **主要機能**:
  - `classify_error()`: エラー分類（PARAM_ERROR/TRANSIENT_ERROR/UNKNOWN）
  - `fix_params_with_llm()`: LLMによるパラメータ自動修正
  - `execute_with_retry()`: リトライ付き実行

- **統計管理**:
  - 総エラー数
  - パラメータエラー数
  - 一時的エラー数
  - 自動修正成功数
  - リトライ成功数

#### 2.6 PromptTemplates（250行）
- **役割**: プロンプト管理の一元化
- **主要プロンプト**:
  - 実行タイプ判定プロンプト
  - タスクリスト生成プロンプト
  - ツール選択プロンプト
  - パラメータ決定プロンプト

- **設計原則**:
  - 動的値の注入機能
  - 保守性の向上
  - プロンプトの再利用可能性

### 3. 実行フローの詳細（約600行）

#### 3.1 実行タイプ判定フロー
```
1. ユーザーリクエスト受付
    ↓
2. 会話コンテキスト取得（直近3件）
    ↓
3. LLMによる実行タイプ判定:
   - NO_TOOL: ツール不要（挨拶・雑談等）
   - SIMPLE: 1-2ステップの単純なタスク
   - COMPLEX: 3ステップ以上の複雑なタスク
    ↓
4. 対応する実行メソッドへ振り分け
```

#### 3.2 タスクリスト実行フロー
```
1. タスクリスト生成（LLM）
    ↓
2. チェックリスト表示
    ↓
3. 各タスクを順次実行:
   a. プレースホルダー解決
   b. ツール・パラメータ選択
   c. ツール実行
   d. 結果の記録・表示
   e. UIの更新
    ↓
4. 最終結果の統合・応答生成
```

#### 3.3 プレースホルダー解決メカニズム
- `{前の結果}`: 直前のタスク実行結果
- `{タスク1の結果}`: 特定タスクの結果参照
- `{ユーザー入力}`: 元のユーザーリクエスト
- 動的な値の注入による柔軟な実行制御

#### 3.4 ループ検出と依存関係解決
- 無限ループの検出機能
- 依存関係の自動解決
- 実行順序の最適化

### 4. 設定とカスタマイズ（約300行）

#### 4.1 config.yaml構造
```yaml
llm:
  provider: "openai"
  model: "gpt-4o-mini"
  temperature: 0.3

display:
  ui_mode: "rich"  # "basic" or "rich"
  show_timing: true
  show_thinking: false
  rich_options:
    enable_live_updates: true
    syntax_highlighting: true

execution:
  max_retries: 3
  timeout: 30
  max_tasks: 10

conversation:
  context_limit: 5
  max_history: 50

error_handling:
  auto_correct_params: true
  retry_interval: 1.0
  max_fix_attempts: 2

development:
  verbose: false
  debug_mode: false
```

#### 4.2 AGENT.mdによるカスタマイズ
- カスタム指示の追加方法
- 専門知識の注入
- 振る舞いの調整
- 実例とベストプラクティス

#### 4.3 環境変数による制御
- `SURROGATE_POLICY`: サロゲート文字処理方針
- `OPENAI_API_KEY`: OpenAI API認証
- デバッグフラグ各種

### 5. サロゲート文字対策（約200行）

#### 5.1 Windows環境での問題
- Unicode サロゲート文字（U+D800-U+DFFF）
- Windows cp932エンコーディングとの衝突
- subprocess実行時の文字化け

#### 5.2 解決策の実装
- `clean_surrogate_chars()`: サロゲート文字除去
- `safe_str()`: 安全な文字列変換
- `safe_repr()`: 安全なrepr変換

#### 5.3 処理の最適化
- universal_tools_serverでの根本処理
- 重複処理の削除
- パフォーマンス向上

### 6. 統計とモニタリング（約150行）

#### 6.1 セッション統計
- 総リクエスト数
- 成功したタスク数
- 失敗したタスク数
- 平均実行時間

#### 6.2 エラー統計
- エラー分類別カウント
- 自動修正成功率
- リトライ成功率
- エラーパターン分析

#### 6.3 パフォーマンス計測
- 実行時間計測
- ツール呼び出し頻度
- LLM API利用統計

### 7. 実装例とコードサンプル（約400行）

#### 7.1 基本的な使用例
- 簡単な計算タスク
- データベース操作
- ファイル操作

#### 7.2 カスタムエージェント作成
- 専門分野向けエージェント
- AGENT.mdの活用例
- 設定のカスタマイズ

#### 7.3 エラー処理のカスタマイズ
- カスタムエラーハンドラー
- 特定ドメイン向けリトライ戦略

### 8. トラブルシューティング（約200行）

#### 8.1 よくあるエラーと対処法
- MCP接続エラー
- OpenAI API関連エラー
- サロゲート文字エラー
- タイムアウトエラー

#### 8.2 デバッグ方法
- ログ出力の活用
- verbose モードの使用
- ステップバイステップ実行

#### 8.3 パフォーマンス最適化
- タスク分割の最適化
- プロンプトの効率化
- メモリ使用量の管理

## 実装方針

### ドキュメントの特徴
- **総計**: 約3,200行の包括的技術ドキュメント
- **コード例**: 実際のmcp_agent.pyコードと対応した具体例
- **図表**: アーキテクチャ図、フローチャート、状態遷移図
- **実践的**: 実際の使用シナリオに基づく説明
- **段階的**: 初心者から上級者まで理解できる構成

### 品質基準
- **正確性**: 実際のコードと完全に対応
- **完全性**: 全機能をカバー
- **可読性**: 明確な構造と説明
- **実用性**: すぐに活用できる内容

### 更新・保守
- バージョン管理による変更履歴
- 定期的な内容見直し
- ユーザーフィードバックの反映

---

**作成予定日**: 2025-01-24  
**対象バージョン**: MCP Agent V4  
**ファイル名**: `MCP_AGENT_V4_TECHNICAL_GUIDE.md`