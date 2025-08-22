# MCPエージェント指示書

この指示書は、MCPエージェントがタスクを分解し実行する際のガイドラインです。

## 基本原則

### 1. データベース操作のルール
- **3ステップ実行**: データベース関連の要求は必ず以下の順序で実行
  1. `list_tables` - テーブル一覧の確認
  2. `get_table_schema` - 対象テーブルのスキーマ確認
  3. `execute_safe_query` - 実際のクエリ実行

### 2. ユーザー意図の解釈
- **「一覧」「表示」「見る」「取得」** → 実際のデータ取得が必要
- **「構造」「スキーマ」「テーブル情報」** → メタ情報の確認のみ
- **「テーブル一覧」** → list_tablesのみ実行

### 3. エラー対処の指針
- **"no such column" エラー** → get_table_schemaでカラム名を確認してから再実行
- **"no such table" エラー** → list_tablesでテーブル名を確認
- **接続エラー** → 最大3回リトライ

## よく使うパターン

### データベース関連
```
「商品データを一覧表示」
→ list_tables → get_table_schema(products) → execute_safe_query(SELECT * FROM products LIMIT 10)

「売上合計を計算」  
→ list_tables → get_table_schema(sales) → execute_safe_query(SELECT SUM(total_amount) FROM sales)

「月次売上レポート」
→ list_tables → get_table_schema(sales) → execute_safe_query(SELECT strftime('%Y-%m', sale_date) as month, SUM(total_amount) FROM sales GROUP BY month)
```

### 計算関連
```
「100と200を足して」
→ add(a=100, b=200)

「フィボナッチ数列10個」
→ generate_sequence(type="fibonacci", count=10)
```

## プロジェクト固有の設定

### テーブル対応
- **商品関連** → `products`テーブル
- **売上関連** → `sales`テーブル  
- **顧客関連** → `customers`テーブル

### よく使うクエリ
- **全商品一覧**: `SELECT * FROM products`
- **在庫少ない商品**: `SELECT * FROM products WHERE stock < 5`
- **今月の売上**: `SELECT SUM(total_amount) FROM sales WHERE strftime('%Y-%m', sale_date) = strftime('%Y-%m', 'now')`

## 重要な注意事項

1. **データ表示時の制限**: 大量データの場合は必ず`LIMIT`句を使用（推奨: 10〜20件）
2. **日付形式**: SQLiteでは`strftime`関数を使用
3. **エラー時の対応**: エラーメッセージを分析し、適切な前処理を実行
4. **並列実行**: 依存関係のないタスクは並列実行可能

## カスタマイズの例

この指示書は各プロジェクトでカスタマイズ可能です：

```markdown
## このプロジェクト専用の規則
- データは常に日本円形式で表示
- 売上データは税込み価格で計算  
- 顧客情報は個人情報を除外して表示
```

---
*このファイルを編集することで、エージェントの動作をカスタマイズできます*