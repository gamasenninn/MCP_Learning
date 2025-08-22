# MCP Agent V3 - AGENT.md方式

革新的なAGENT.md方式による第3世代MCPエージェント

## 特徴

- 🎯 **AGENT.mdによるカスタマイズ**: カレントディレクトリのAGENT.mdで動作をカスタマイズ
- 🧠 **階層的指示システム**: 基本能力 + プロジェクト固有指示の組み合わせ  
- 🔧 **シンプルなアーキテクチャ**: 従来の2000行→450行に簡素化
- 🚀 **高速起動**: 複雑な学習機能を削除し高速化

## クイックスタート

```bash
# ディレクトリに移動
cd C:\MCP_Learning\chapter10_v3

# エージェント起動
uv run python mcp_agent.py
```

## AGENT.mdのカスタマイズ

カレントディレクトリに`AGENT.md`を作成することで、エージェントの動作をカスタマイズできます。

### 基本的な例
```markdown
# MCPエージェント指示書

## このプロジェクトのルール
- 「売上」→ salesテーブルを使用
- 「商品」→ productsテーブルを使用
- データは必ず10件以下で表示

## よく使うクエリ
- 今月売上: SELECT SUM(total_amount) FROM sales WHERE strftime('%Y-%m', sale_date) = strftime('%Y-%m', 'now')
```

### 高度な例
```markdown  
# プロジェクトA - ECサイト分析用

## 重要な原則
- 個人情報は絶対に表示しない
- 金額は必ず日本円形式で表示
- エラー時は詳細なログを出力

## カスタム判断ルール
- 「分析」「レポート」→ 必ず複数テーブルを結合
- 「一覧」→ 最大20件まで表示
- 「集計」→ GROUP BYを使用

## よくある要求パターン
「売上トップ10」
→ list_tables → get_table_schema(sales) → get_table_schema(products) → execute_safe_query(SELECT p.name, SUM(s.total_amount) FROM sales s JOIN products p ON s.product_id = p.id GROUP BY p.id ORDER BY SUM(s.total_amount) DESC LIMIT 10)
```

## アーキテクチャ

```
mcp_agent.py          # メインエージェント (200行)
├── connection_manager.py  # MCP接続管理 (150行) 
├── task_executor.py      # タスク実行 (100行)
└── AGENT.md             # 指示書 (ユーザー編集)
```

## 対話例

```
Agent> 商品データを一覧表示

[リクエスト #1] 商品データを一覧表示
------------------------------------------------------------
[計画] 3個のタスクを生成

[タスク実行] 3個のタスクを実行
==================================================

[1/3] タスク: list_tables
  [成功] 実行時間: 0.05秒

[2/3] タスク: get_table_schema  
  パラメータ: {'table_name': 'products'}
  [成功] 実行時間: 0.03秒

[3/3] タスク: execute_safe_query
  パラメータ: {'sql': 'SELECT * FROM products LIMIT 10'}
  [成功] 実行時間: 0.02秒

==================================================
実行統計:
  成功: 3/3
  失敗: 0/3
  リトライ: 0件

実行結果（10件）:
id | name                    | price  | stock | category        
------------------------------------------------------------
1  | iPhone 15 Pro          | 159800 | 15    | スマートフォン        
2  | MacBook Air M3         | 134800 | 8     | ノートPC        
3  | iPad Pro 12.9          | 128800 | 12    | タブレット
...
```

## 従来版との比較

| 項目 | V2（従来版） | V3（AGENT.md版） |
|-----|-------------|-----------------|
| コード行数 | 2000行 | 450行 |
| ファイル数 | 7個 | 3個 |
| 設定方法 | コード修正 | AGENT.md編集 |
| 学習機能 | 自動学習 | ユーザー指示 |
| 起動時間 | 遅い | 高速 |
| カスタマイズ | 困難 | 簡単 |

## サンプルAGENT.mdファイル

### examples/AGENT_database.md
データベース操作に特化した設定例

### examples/AGENT_minimal.md  
最小構成の設定例

## 開発者向け情報

### 拡張方法
新しいMCPサーバーを追加する場合：
1. `mcp_servers.json`にサーバー設定を追加
2. `AGENT.md`に使用方法を記述
3. コード変更は不要

### デバッグ
```python
agent = MCPAgent(verbose=True)  # 詳細ログ有効
```

---

AGENT.md方式により、コードを触らずにエージェントの動作を完全にカスタマイズできる革新的なアーキテクチャを実現しました。