# Changelog

All notable changes to MCP Agent will be documented in this file.

## [6.0.0] - 2024-12-01

### 🆕 Added

#### 状態管理システム
- **StateManager クラス**: セッション状態の永続化
- **.mcp_agent/ フォルダ**: 状態ファイルの集約管理
- **会話履歴の永続化**: conversation.txt での履歴保存
- **セッション復元機能**: 中断した作業の継続実行
- **タスク状態追跡**: pending/completed タスクの管理

#### ユーザー確認機能（CLARIFICATION）
- **TaskManager クラス**: タスク管理とCLARIFICATION処理
- **不明情報の自動検出**: 「私の年齢」「当社の売上」等のパターン
- **対話的確認機能**: ユーザーへの具体的質問生成
- **回答受付処理**: ユーザー回答に基づくタスク継続
- **V6版実行方式判定**: CLARIFICATION を含む4段階判定

#### タスク中断・再開機能
- **pause_session()**: セッション一時停止
- **resume_session()**: セッション再開  
- **clear_session()**: セッションクリア
- **get_session_status()**: 現在状態の取得
- **ESCキー対応**: 作業保存と継続機能

#### 計算処理の改善
- **段階的タスク分割**: 複雑計算の適切な分解
- **パラメータ依存関係**: 前タスク結果の動的利用
- **CLARIFICATION統合**: 不明値の確認後計算実行

### 🔧 Enhanced

#### プロンプトシステム
- **PromptTemplates V6版**: CLARIFICATION判定基準を追加
- **get_execution_type_determination_prompt_v6()**: V6専用プロンプト
- **判定精度向上**: 4段階判定（NO_TOOL/CLARIFICATION/SIMPLE/COMPLEX）

#### エージェント機能
- **MCPAgent V6統合**: 新しい状態管理との統合
- **_execute_interactive_dialogue V6版**: CLARIFICATION対応実行
- **セッション管理メソッド**: 包括的な状態操作API
- **会話コンテキスト V6版**: StateManager からの履歴取得

#### エラー処理
- **状態管理エラー**: ファイルI/O エラーの適切な処理
- **CLARIFICATION タイムアウト**: 長時間応答なしの対応
- **セッション復元エラー**: 破損ファイルの自動復旧

### 📝 Updated

#### ドキュメント
- **AGENT.md V6版**: 新機能の説明と使用例
- **README.md**: V6機能の包括的説明
- **設定ガイド**: 状態管理とCLARIFICATION設定

#### 設定システム
- **config.yaml**: V6用設定項目の追加
- **状態管理設定**: state_dir, auto_save_interval等
- **CLARIFICATION設定**: enable_clarification, max_attempts等

### 🧪 Testing

#### 新テストスイート  
- **test_state_manager.py**: 状態管理機能の包括テスト
- **test_task_manager.py**: タスク管理とCLARIFICATIONテスト
- **test_v6_integration.py**: V6統合機能の実地テスト
- **モックシステム**: LLMクライアントのテストモック

#### テストカバレッジ
- 状態の永続化と復元
- CLARIFICATIONフローの完全テスト
- タスク依存関係の解決
- セッション管理のライフサイクル

### 📁 Files Added

```
chapter10_v6/
├── state_manager.py      # 状態管理システム
├── task_manager.py       # タスク・CLARIFICATION管理
├── tests/
│   ├── test_state_manager.py
│   ├── test_task_manager.py
│   └── test_v6_integration.py
├── README.md            # V6対応版
└── CHANGELOG.md         # このファイル
```

### 📁 Files Modified

```
├── mcp_agent.py         # V6機能統合
├── prompts.py          # V6プロンプト追加
├── AGENT.md            # V6機能説明追加
└── config.yaml         # V6設定項目追加
```

### 🔄 Migration Guide

#### V5 → V6 移行手順

1. **ファイルコピー**
   ```bash
   cp -r chapter10/* chapter10_v6/
   ```

2. **新ファイルの確認**
   - `state_manager.py` - 状態管理
   - `task_manager.py` - タスク管理

3. **設定更新**
   ```yaml
   # config.yaml に追加
   state_management:
     state_dir: ".mcp_agent"
   clarification:
     enable_clarification: true
   ```

4. **テスト実行**
   ```bash
   uv run python tests/test_v6_integration.py
   ```

#### 互換性

- ✅ **設定ファイル**: config.yaml はそのまま使用可能
- ✅ **MCP接続**: 既存のMCPサーバーとの互換性維持  
- ✅ **基本機能**: V5の全機能を継承
- ⚠️ **状態管理**: 新規作成（V5からのマイグレーションなし）

### 🚨 Breaking Changes

#### API変更
- `initialize()` → `initialize(session_id=None)`: セッションID対応
- `_get_recent_context()`: StateManager からの取得に変更
- `_execute_interactive_dialogue()`: V6版に全面刷新

#### 動作変更
- **会話履歴**: メモリではなくファイルベース
- **タスク管理**: 永続化による状態保持
- **実行フロー**: CLARIFICATION ステップの追加

### 📊 Performance Improvements

- **メモリ使用量**: 会話履歴のファイル化により削減
- **起動時間**: セッション復元の最適化
- **応答時間**: CLARIFICATION パターン検出の高速化

### 🔒 Security

- **ファイル権限**: 状態ファイルの適切な権限設定
- **データ暗号化**: 機密情報の保護機能追加検討
- **セッションタイムアウト**: 長期間放置セッションの自動クリア

---

## [5.0.0] - Previous Version

### Features
- 基本的なMCPエージェント機能
- タスクリスト生成と実行
- Rich UI サポート
- エラーハンドリング
- 会話履歴管理（メモリベース）

### Architecture
- MCPAgent クラス
- ConnectionManager
- DisplayManager  
- ErrorHandler
- PromptTemplates

---

**Legend:**
- 🆕 Added: 新機能
- 🔧 Enhanced: 機能強化  
- 📝 Updated: ドキュメント更新
- 🧪 Testing: テスト追加
- 🔄 Migration: 移行情報
- 🚨 Breaking: 破壊的変更
- 📊 Performance: パフォーマンス改善
- 🔒 Security: セキュリティ