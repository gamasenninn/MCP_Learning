# MCP Agent V6

Claude Code風の対話型MCPエージェント - 状態管理とユーザー確認機能を搭載

## 🆕 V6 新機能

### 状態の永続化
- **.mcp_agent/フォルダ**: セッション状態をテキストファイルで管理
- **会話履歴の永続化**: すべての会話が保存・復元可能
- **タスク状態管理**: 実行待ち・完了タスクの状態追跡

### ユーザー確認機能（CLARIFICATION）
- **不明な情報の検出**: 「私の年齢」「当社の売上」等を自動検出
- **対話的な確認**: ユーザーに具体的な質問を投げかけ
- **タスク継続**: 回答を受けて処理を継続

### タスク中断・再開
- **ESCキー対応**: 作業中断時に状態を自動保存
- **セッション復元**: 再起動時に前回の続きから実行
- **タスク依存関係**: 前のタスク結果を利用した処理

### 計算タスクの改善
- **適切な分割**: 複雑な計算を段階的に処理
- **パラメータ解決**: 動的な値の置換と推論
- **エラー処理**: 失敗時の自動リトライ機能

## 📁 ファイル構成

```
chapter10_v6/
├── mcp_agent.py          # メインエージェント（V6対応）
├── state_manager.py     # 🆕 状態管理システム
├── task_manager.py      # 🆕 タスク管理＆CLARIFICATION
├── prompts.py           # プロンプトテンプレート（V6対応）
├── AGENT.md            # エージェント指示書（V6更新）
├── connection_manager.py # MCP接続管理
├── display_manager.py   # UI表示管理
├── error_handler.py     # エラー処理
├── utils.py            # ユーティリティ
├── config.yaml         # 設定ファイル
├── tests/              # テストファイル
│   ├── test_state_manager.py
│   ├── test_task_manager.py
│   └── test_v6_integration.py
└── docs/               # ドキュメント
```

## 🔧 セットアップ

### 1. 依存関係のインストール

```bash
# uvを使用（推奨）
uv add openai pyyaml rich

# または pip
pip install openai pyyaml rich
```

### 2. 設定ファイルの準備

```bash
# config.sample.yaml を config.yaml にコピー
cp config.sample.yaml config.yaml

# OpenAI API キーを設定
# config.yaml の api_key: "your-api-key-here" を編集
```

### 3. エージェントの起動

```bash
# 基本起動
uv run python mcp_agent.py

# 特定のセッションで再開
python mcp_agent.py --session session_20241201_143022
```

## 🚀 使用例

### 基本的な使い方

```
Agent> こんにちは
こんにちは！何かお手伝いできることはありますか？

Agent> 私の年齢に10を足して計算して
### 確認が必要です

年齢を教えてください。

**背景情報:**
要求: 私の年齢に10を足して計算して
パラメータで「私の年齢」が指定されていますが、具体的な値がわかりません。

**例:**
- 例: 25歳
- 例: 30歳です
- 例: 私の年齢は28歳

> 回答をお待ちしています。ESCキーで作業を中断することもできます。

Agent> 25歳です
タスクが完了しました: 年齢に10を加算して計算
結果: 35
```

### セッション管理

```python
# セッション状態の確認
agent.get_session_status()

# セッション一時停止
await agent.pause_session()

# セッション再開
await agent.resume_session()

# セッションクリア
await agent.clear_session()
```

## 📊 状態ファイル構造

V6では `.mcp_agent/` フォルダに以下のファイルが生成されます：

```
.mcp_agent/
├── session.json         # セッション情報
├── conversation.txt     # 会話ログ（人間可読）
├── tasks/
│   ├── pending.json     # 実行待ちタスク
│   ├── completed.json   # 完了タスク
│   └── current.txt      # 現在の状況（人間可読）
└── history/            # 過去のセッション
    ├── session_20241201_143022.json
    └── session_20241201_143022_conversation.txt
```

## 🧪 テスト

V6の新機能をテストできます：

```bash
# 状態管理のテスト
uv run python tests/test_state_manager.py

# タスク管理のテスト  
uv run python tests/test_task_manager.py

# 統合テスト
uv run python tests/test_v6_integration.py

# 全テスト実行
uv run python tests/test_import_check.py
```

## 🔄 マイグレーション

### V5からV6への移行

V6では新しい状態管理システムが導入されています。既存のV5環境から移行する場合：

1. **設定ファイル**: `config.yaml` はそのまま使用可能
2. **AGENT.md**: V6対応版に更新（CLARIFICATIONパターンを追加）
3. **状態ファイル**: 新規作成（`.mcp_agent/` フォルダ）

## ⚙️ V6設定項目

`config.yaml` でV6特有の設定を調整できます：

```yaml
# V6状態管理設定
state_management:
  state_dir: ".mcp_agent"
  auto_save_interval: 30  # 秒
  max_conversation_history: 50
  session_timeout: 3600   # 秒

# CLARIFICATION設定  
clarification:
  enable_clarification: true
  auto_detect_patterns: true
  max_clarification_attempts: 3

# タスク実行設定
task_execution:
  enable_task_persistence: true
  auto_resume_on_startup: true
  max_pending_tasks: 20
```

## 🆚 バージョン比較

| 機能 | V5 | V6 |
|------|----|----|
| 基本実行 | ✅ | ✅ |
| タスク分解 | ✅ | ✅ |
| 会話履歴 | メモリのみ | 永続化 |
| 状態管理 | なし | ✅ |
| ユーザー確認 | なし | ✅ |
| タスク中断・再開 | なし | ✅ |
| 計算分割 | 基本的 | 高度 |

## 🐛 トラブルシューティング

### よくある問題

1. **状態ファイルの権限エラー**
   ```bash
   # .mcp_agent フォルダの権限を確認
   ls -la .mcp_agent/
   chmod -R 755 .mcp_agent/
   ```

2. **セッション復元失敗**
   ```bash
   # 破損したセッションファイルの削除
   rm -rf .mcp_agent/session.json
   ```

3. **CLARIFICATION が動作しない**
   - `config.yaml` の `enable_clarification: true` を確認
   - AGENT.md のパターンが正しいか確認

### ログとデバッグ

```yaml
# config.yaml でデバッグ情報を有効化
development:
  verbose: true
  show_api_calls: true
  debug_state_management: true
```

## 🤝 貢献

V6の改善にご協力ください：

1. **Issue報告**: バグや改善提案をお寄せください
2. **テストケース**: 新しいテストシナリオの作成
3. **ドキュメント**: 使用例や設定例の追加

## 📄 ライセンス

このプロジェクトはオープンソースです。詳細は LICENSE ファイルをご覧ください。

---

**MCP Agent V6** - あなたの作業を中断されることなく、確実に完了まで導きます。