# MCP Agent

**Claude Code風の対話型AIエージェント** - ESC中断制御・REPLコマンド・包括的テストスイート完備

## 🌟 **新機能**

### ⚡ **ESC中断制御システム**
- **ESCキー**でタスクを即座に中断・スキップ・継続選択
- **リアルタイム制御**: 実行中のタスクを任意のタイミングで制御
- **状態管理**: スキップされたタスクは適切にクリーンアップ、混在を防止

### 🔧 **高機能REPLコマンドシステム**
```bash
/help          # 利用可能コマンド一覧
/status        # 現在の状態表示  
/tools         # MCPツール一覧
/tasks         # 実行中・完了タスク表示
/history [n]   # 会話履歴表示
/clear         # セッションクリア
/config [key]  # 設定表示・変更
/verbose       # 詳細モード切り替え
/ui [mode]     # UIモード切り替え
/save [name]   # セッション保存
/load [name]   # セッション復元
```

### 🏗️ **完全リファクタリングされたアーキテクチャ**
- **StateManager**: セッション・会話履歴の統合管理
- **ConversationManager**: 会話文脈の特化処理
- **TaskExecutor**: タスク実行とESC中断制御
- **InterruptManager**: グローバル中断制御システム
- **CommandManager**: REPLコマンドの高度な処理
- **ErrorHandler**: 包括的なエラー処理と回復

### 🧪 **包括的テストスイート（172テスト）**
- **機能テスト**: CLARIFICATION永続化、ESCタスク管理
- **統合テスト**: セッション状態フロー、パラメータ解決
- **単体テスト**: 全コンポーネントの詳細検証

## 🚀 **主要特徴**

### 🤖 **マルチモデル対応**
- **GPT-4o-mini**: 高速・汎用処理に最適化
- **GPT-5シリーズ**: (mini/nano/5) 高度推論・創造的タスク対応
- **理由付きモード**: `reasoning_effort`で推論深度制御

### 🔧 **MCPサーバー統合**
```bash
テストで使用する5つの専門サーバー:
├── calculator    # 数値計算（加減乗除、べき乗、関数）
├── database      # SQLite操作（CRUD、集計、分析）
├── weather       # リアルタイム気象情報
├── universal     # Python実行・ファイル処理
└── filesystem    # ディレクトリ・ファイル操作
```

### 💾 **高度セッション管理**
- **永続化**: `.mcp_agent/`での完全状態保存
- **会話履歴**: 人間可読形式 + JSON構造化データ
- **セッション復元**: 中断時点からの完全再開
- **履歴アーカイブ**: 過去セッションの体系的保存

### 🎯 **インテリジェントCLARIFICATION**
- **自動検出**: 「私の年齢」「当社の売上」等の曖昧表現
- **対話確認**: 不明パラメータの段階的確認
- **履歴記録**: 確認内容の永続保存と後続参照
- **スキップ機能**: ESCでスキップ → 自動推定値使用

### ⚡ **リアルタイム制御**
```bash
実行中にESCキー押下:
┌─────────────────────────────┐
│ [中断] タスクが中断されました    │
│                             │
│ 選択:                        │
│   1. 継続 (c/continue)      │
│   2. スキップ (s/skip)      │  
│   3. 中止 (a/abort)         │
└─────────────────────────────┘
```

## 📦 **セットアップ**

### 1. **依存関係インストール**
```bash
# uvを使用（推奨）
uv sync

# または個別インストール
uv add openai pyyaml rich prompt-toolkit
```

### 2. **環境変数設定**
```bash
# .env ファイル作成
echo "OPENAI_API_KEY=your-api-key-here" > .env
```

### 3. **エージェント起動**
```bash
# 基本起動
uv run python mcp_agent_repl.py

```

## 💻 **使用方法**

### **基本的な対話**
```bash
Agent> 私の年齢に5をかけて200を引いて

### 確認が必要です
あなたの年齢は何歳ですか？
> 65

[実行中] 65 × 5 = 325
[実行中] 325 - 200 = 125
         
### 実行結果
最終結果: **125**

Agent> 私の年齢は？
あなたの年齢は65歳です。（会話履歴から自動取得）
```

### **REPLコマンド例**
```bash
Agent> /status
=== MCP Agent Status ===
セッション: session_20250105_1435
モデル: gpt-4o-mini
実行中タスク: なし
完了タスク: 3件

Agent> /config verbose true
設定を更新しました: verbose = true

Agent> /history 5
=== 最近の会話履歴 (5件) ===
[USER] 私の年齢に5をかけて200を引いて
[ASSISTANT] あなたの年齢は何歳ですか？
[USER] 65
[ASSISTANT] 最終結果: 125
```

### **ESC中断制御**
```bash
Agent> 複雑な計算を実行して
[実行中] 複雑な処理を計算中...
         ↓ ESCキー押下
[中断] 処理を中断しました

選択: [c]継続 [s]スキップ [a]中止
> s

[スキップ] タスクをスキップしました
次の処理を代替手段で実行します...
```

## ⚙️ **設定 (config.yaml)**

### **設定例**
```yaml
# 表示設定
display:
  ui_mode: "rich"              # "basic" / "rich"
  show_timing: true            # 実行時間表示
  show_thinking: false         # 思考過程表示

# LLM設定  
llm:
  model: "gpt-4o-mini"         # "gpt-5-mini", "gpt-5-nano", "gpt-5"
  temperature: 0.2             # 創造性 (0.0-1.0)
  max_completion_tokens: 1000  # 最大トークン
  reasoning_effort: "minimal"  # GPT-5用: minimal/low/medium/high

# 実行設定
execution:
  max_retries: 3               # リトライ回数
  timeout_seconds: 30          # タイムアウト
  max_tasks: 10                # 同時タスク数

# 会話設定
conversation:
  context_limit: 10            # 参照履歴数
  max_history: 50              # 保存履歴数

# 中断処理設定
interrupt_handling:
  non_interactive_default: "abort"  # 非対話時の選択
  timeout: 30.0                     # 選択タイムアウト

# 開発設定
development:
  verbose: false               # 詳細ログ
  log_level: "info"           # debug/info/warning/error
```

## 🏗️ **アーキテクチャ構成**

### **コア・コンポーネント**
```
chapter10/
├── mcp_agent_repl.py         # REPLメインエントリー
├── mcp_agent.py             # コアエージェント
├── state_manager.py         # 統合状態管理
├── conversation_manager.py  # 会話文脈処理
├── task_executor.py         # タスク実行・ESC制御
├── task_manager.py          # タスク管理・CLARIFICATION
├── interrupt_manager.py     # グローバル中断制御
├── connection_manager.py    # MCP接続管理
├── config_manager.py        # 設定管理
├── error_handler.py         # エラー処理・回復
└── display_manager.py       # 表示制御
```

### **REPL・コマンド系**
```
├── repl_command_handlers.py # コマンド実装
├── repl_commands.py         # コマンド定義
├── display_manager_rich.py # Rich UI実装
└── background_monitor.py   # バックグラウンド監視
```

### **設定・データ**
```
├── config.yaml             # メイン設定
├── mcp_servers.json        # MCPサーバー定義
├── AGENT.md               # エージェント指示書
└── .mcp_agent/           # セッションデータ
    ├── session.json      # 現在状態
    ├── conversation.txt  # 会話ログ
    └── history/         # 過去セッション
```

## 🧪 **テストシステム**

### **テスト実行**
```bash
# 全テスト実行（推奨）
uv run python run_tests.py

# カテゴリ別実行
uv run python run_tests.py --type unit          # 単体テスト（高速）
uv run python run_tests.py --type integration   # 統合テスト
uv run python run_tests.py --type functional    # 機能テスト
uv run python run_tests.py --type e2e          # エンドツーエンド

# 高速実行（変更検証）
uv run python run_tests.py quick

# 並列実行（要 pytest-xdist: uv add pytest-xdist）
uv run python run_tests.py --parallel 4

# カバレッジ付き
uv run python run_tests.py --coverage
```

### **テストカバレッジ**
```
tests/
├── unit/ (32テスト)          # StateManager, TaskManager等
├── integration/ (28テスト)   # コンポーネント間連携  
├── functional/ (89テスト)    # CLARIFICATION, ESC制御等
├── e2e/ (4テスト)           # 完全ワークフロー
└── smoke/ (4テスト)         # 基本動作確認

総計: 172テスト (成功率: 100%)
```

### **重要テスト項目**
- ✅ **CLARIFICATION永続化**: 会話履歴の確実な記録・参照
- ✅ **ESCタスク管理**: 中断後の状態管理・混在防止  
- ✅ **セッション状態フロー**: 複数リクエスト間での状態継続
- ✅ **パラメータ解決**: 「前の結果」等の動的解決
- ✅ **エラー回復**: 各種エラー状況での適切な回復処理

## 🎯 **高度な使用例**

### **1. データ分析ワークフロー**
```bash
Agent> データベースのsalesテーブルから月別売上を分析して

[実行] テーブル構造を分析...
[実行] 月別集計クエリを生成...
[実行] グラフデータを出力...

### 分析結果
- 最高売上月: 12月 (¥15,200,000)
- 平均月売上: ¥11,800,000  
- 成長率: +12.3% (前年同期比)
```

### **2. 複合計算タスク**
```bash
Agent> フィボナッチ数列の10番目を計算してから、その値で複利計算（年率5%、10年）

[実行] フィボナッチ(10) = 55
[確認] 複利計算の詳細設定をお聞かせください
> 元本55、年率5%、10年間、年複利で

[実行] 複利計算: 55 × (1.05)^10 = ¥89.66
```


## 🔧 **トラブルシューティング**

### **よくある問題と解決法**

#### **1. セッション復元エラー**
```bash
# 破損セッション削除
rm .mcp_agent/session.json

```

#### **2. ESC中断が効かない**
```bash
# 対話的環境確認
python -c "import sys; print(sys.stdin.isatty())"

# 中断設定確認
Agent> /config interrupt_handling
```

#### **3. テスト失敗**
```bash
# 単体テストのみ実行
uv run python run_tests.py --type unit

# 詳細エラー表示
uv run python run_tests.py --verbose
```

#### **4. MCPサーバー接続エラー**
```bash
# サーバー状態確認  
Agent> /tools

# 設定ファイル確認
cat mcp_servers.json
```

### **デバッグ設定**
```yaml
development:
  verbose: true              # 全詳細ログ
  log_level: "debug"        # 最大詳細レベル
```

## 📈 **パフォーマンス最適化**

### **高速実行モード**
```yaml
# 高速設定
llm:
  model: "gpt-4o-mini"        # 最速モデル
  reasoning_effort: "minimal"  # 最小推論
  max_completion_tokens: 500   # トークン削減

execution:
  timeout_seconds: 15         # 短縮タイムアウト
```

### **テスト高速化**
```bash
# 並列実行（4プロセス、要 pytest-xdist: uv add pytest-xdist）
uv run python run_tests.py --parallel 4

# 単体テストのみ（数秒で完了）
uv run python run_tests.py --type unit
```

## 🔗 **MCPサーバー詳細**

### **Calculator Server**
- 基本演算: `+`, `-`, `*`, `/`, `**`
- 関数: `sqrt`, `abs`, `round`, `floor`, `ceil`
- 定数: `pi`, `e`

### **Database Server**  
- CRUD操作: `SELECT`, `INSERT`, `UPDATE`, `DELETE`
- 集計: `GROUP BY`, `ORDER BY`, `JOIN`
- スキーマ分析: テーブル構造自動認識

### **Weather Server**
- 現在天気: 任意地域の現在の気象状況
- 予報: 週間天気予報
- 詳細情報: 気温・湿度・風速・気圧

### **Universal Server**
- Python実行: 動的コード実行・データ処理
- ファイル処理: CSV・JSON・テキストファイル
- データ変換: フォーマット変換・データクリーニング

### **Filesystem Server**
- ディレクトリ操作: 作成・削除・一覧
- ファイル操作: 読み書き・コピー・移動
- パス解決: 相対・絶対パス変換

## 🌟 **今後の展開**

### **開発予定機能**
- [ ] **マルチモーダル対応**: 画像・音声入力処理
- [ ] **分散処理**: 複数エージェント協調動作
- [ ] **プラグインシステム**: カスタムMCPサーバー簡単追加
- [ ] **GUIフロントエンド**: Web・デスクトップアプリ

### **拡張性**
現在のアーキテクチャは高度に模様化されており、新機能の追加が容易です：

```python
# 新しいコマンド追加例
@register_command("analyze", ["ana"], "データ分析実行")  
async def analyze_command(self, args: str) -> str:
    return await self.agent.process_request(f"データを分析: {args}")
```

## 📄 **ライセンス・貢献**

このプロジェクトはオープンソースです。改善提案やバグレポートを歓迎します。

### **貢献方法**
1. 問題をIssueで報告
2. 機能改善をPull Requestで提案  
3. テストケースの追加・改善
4. ドキュメントの充実

---

**MCP Agent (第4フェーズ)** - リアルタイム制御・REPLコマンド・包括的テスト完備の次世代対話型AIエージェント

*Built with ❤️ and Claude Code*