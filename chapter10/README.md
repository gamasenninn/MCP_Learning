# MCP Agent

Claude Code風の対話型AIエージェント - MCPサーバー統合とマルチモデル対応

## 🚀 特徴

- 🤖 **マルチモデル対応**: GPT-4o-mini、GPT-5シリーズ（mini/nano/5）完全サポート
- 🔧 **MCPサーバー統合**: 5つのサーバー（計算機、データベース、天気、ユニバーサルツール、ファイルシステム）
- 💾 **セッション管理**: .mcp_agent/フォルダでの状態永続化、作業の中断・再開機能
- 🎯 **CLARIFICATION機能**: 不明な情報（年齢、商品名等）を対話的に確認
- ⚡ **インテリジェントなパラメータ解決**: 「前の計算結果」等を自動的に実際の値に変換
- 🎨 **UI切り替え**: Rich（美しいUI）とBasic（シンプル）モードの選択可能

## 📦 必要環境

- Python 3.8以上
- uv（推奨）またはpip
- OpenAI APIキー

## 🔧 セットアップ

### 1. 依存関係のインストール

```bash
# uvを使用（推奨）
uv add openai pyyaml rich

# または pip
pip install openai pyyaml rich
```

### 2. 環境変数の設定

`.env`ファイルを作成してOpenAI APIキーを設定：

```bash
# .env
OPENAI_API_KEY=your-api-key-here
```

### 3. 設定ファイルの確認

`config.yaml`でエージェントの動作を設定：

```yaml
# 基本設定
display:
  ui_mode: "basic"  # または "rich"

llm:
  model: "gpt-4o-mini"  # または "gpt-5-mini", "gpt-5-nano", "gpt-5"
  reasoning_effort: "minimal"  # GPT-5用: minimal/low/medium/high
```

## 💻 使用方法

### 基本起動

```bash
# 新しいセッションで開始
uv run python mcp_agent.py

# または通常のpython
python mcp_agent.py
```

### 使用例

```
Agent> 私の年齢に5をかけて200を引いて

### 確認が必要です
あなたの年齢はいくつですか？
> 回答をお待ちしています。

Agent> 65

[タスク一覧]
  [ ] 年齢65に5を掛ける
  [ ] 掛け算の結果から200を引く

[ステップ 1/2] 年齢65に5を掛ける
  -> multiply を実行中...
  [完了] 325

[ステップ 2/2] 掛け算の結果から200を引く
  -> subtract を実行中...
  [完了] 125

### 実行結果
計算が完了しました：
- 65 × 5 = 325
- 325 - 200 = 125

最終結果: **125**
```

## ⚙️ 設定

### config.yaml 主要設定項目

```yaml
# 表示設定
display:
  ui_mode: "basic"        # "basic" または "rich"
  show_timing: true       # 実行時間表示
  show_thinking: true     # 思考過程表示

# LLM設定
llm:
  model: "gpt-4o-mini"           # 使用モデル
  temperature: 0.2               # 創造性パラメータ
  
  # GPT-5専用設定
  reasoning_effort: "minimal"    # 推論レベル
  max_completion_tokens: 5000    # 最大トークン数

# 実行設定
execution:
  max_retries: 3                 # 最大リトライ回数
  timeout_seconds: 30            # タイムアウト時間
  max_tasks: 10                  # タスク最大数

# 会話設定
conversation:
  context_limit: 10              # 参照する会話件数
  max_history: 50                # 履歴保持件数
```

### GPT-5特有の設定

GPT-5シリーズを使用する場合：

```yaml
llm:
  model: "gpt-5-mini"  # または "gpt-5-nano", "gpt-5"
  reasoning_effort: "minimal"  # 高速応答用
  # reasoning_effort: "high"   # 複雑な問題用
```

## 📁 ファイル構成

```
chapter10/
├── mcp_agent.py              # メインエージェント
├── state_manager.py          # セッション状態管理
├── task_manager.py           # タスク管理・CLARIFICATION
├── connection_manager.py     # MCP接続管理
├── display_manager.py        # UI表示管理
├── display_manager_rich.py   # Rich UI実装
├── error_handler.py          # エラー処理
├── prompts.py                # プロンプトテンプレート
├── utils.py                  # ユーティリティ
├── config.yaml               # 設定ファイル
├── mcp_servers.json          # MCPサーバー設定
├── AGENT.md                  # エージェント指示書
├── gpt5_chat.py             # GPT-5対話プログラム
├── .mcp_agent/              # セッション状態フォルダ
│   ├── session.json         # 現在のセッション
│   ├── conversation.txt     # 会話ログ
│   └── history/             # 過去のセッション
└── tests/                   # テストファイル
```

## 🔗 対応MCPサーバー

1. **calculator** - 基本的な計算機能（加減乗除、べき乗等）
2. **database** - SQLiteデータベース操作
3. **weather** - 天気情報の取得
4. **universal** - ユニバーサルツール（Python実行等）
5. **filesystem** - ファイル・ディレクトリ操作

## 🎯 CLARIFICATION機能

不明な情報を自動検出し、ユーザーに確認：

- 「私の年齢」「当社の売上」等の曖昧な表現
- 具体的な値が必要なパラメータ
- データベースのテーブル名やカラム名

## 💡 セッション管理

### 自動保存
- 全ての会話と実行結果を`.mcp_agent/`フォルダに保存
- セッション中断時も状態を保持

### 状態ファイル
```
.mcp_agent/
├── session.json         # 現在のセッション状態
├── conversation.txt     # 会話履歴（人間可読）
└── history/            # 過去のセッション
```

## 🐛 トラブルシューティング

### よくある問題

#### 1. エンコーディングエラー
```bash
# Windows環境での文字化け
export PYTHONIOENCODING=utf-8
```

#### 2. セッション復元失敗
```bash
# 破損したセッションファイルの削除
rm -rf .mcp_agent/session.json
```

#### 3. パラメータ解決が動作しない
- verboseモードで詳細ログを確認：
```yaml
development:
  verbose: true
```

#### 4. GPT-5で応答が空白
- `max_completion_tokens`を1000以上に設定
- `reasoning_effort: "minimal"`で高速モード使用

### デバッグ情報の有効化

```yaml
development:
  verbose: true              # 詳細ログ表示
  show_api_calls: true       # API呼び出し表示
```

## 🚀 開発・テスト

### テスト実行（pytest）

```bash
# テスト用依存関係のインストール
uv add --dev pytest pytest-asyncio pytest-cov

# 全テスト実行
python run_tests.py

# カテゴリ別実行
python run_tests.py --type unit          # 単体テスト
python run_tests.py --type integration   # 統合テスト
python run_tests.py --type functional    # 機能テスト

# 高速実行（リファクタリング後のチェック）
python run_tests.py quick

# カバレッジ付き実行
python run_tests.py --coverage

# 並列実行（高速化）
python run_tests.py --parallel 4
```

### テスト構成

```
tests/
├── unit/                     # 単体テスト - 高速実行
│   ├── test_state_manager.py
│   ├── test_task_manager.py
│   └── test_utils.py
├── integration/              # 統合テスト - コンポーネント間
│   ├── test_gpt5_support.py
│   ├── test_parameter_resolution.py
│   └── test_clarification.py
├── functional/               # 機能テスト - エンドツーエンド
│   ├── test_calculation_tasks.py
│   └── test_database_operations.py
└── conftest.py              # 共通設定・フィクスチャ
```

## 📄 ライセンス

このプロジェクトはオープンソースです。

---

**MCP Agent** - あなたの作業を確実に完了まで導く対話型AIエージェント