# MCPエージェント指示書（データベース特化版）

このプロジェクトはECサイトのデータベース分析用です。

## 重要な原則

### セキュリティルール
- 顧客の個人情報（email, phone, address）は絶対に表示しない
- 価格は必ず日本円形式で表示（例：159,800円）
- データは必ず最新20件以下で制限

### データベース固有の設定

#### テーブル対応表
- **商品情報** → `products` テーブル
- **売上データ** → `sales` テーブル  
- **顧客データ** → `customers` テーブル（個人情報は除外）

#### 日付処理
- SQLiteの`strftime`関数を使用
- 今月: `strftime('%Y-%m', 'now')`
- 今年: `strftime('%Y', 'now')`

## 頻繁に使用するクエリパターン

### 売上分析系
```sql
-- 今月の売上合計
SELECT SUM(total_amount) FROM sales 
WHERE strftime('%Y-%m', sale_date) = strftime('%Y-%m', 'now')

-- 商品別売上トップ10  
SELECT p.name, SUM(s.total_amount) as total_sales
FROM sales s 
JOIN products p ON s.product_id = p.id 
GROUP BY p.id 
ORDER BY total_sales DESC 
LIMIT 10

-- 月次売上推移
SELECT strftime('%Y-%m', sale_date) as month, 
       SUM(total_amount) as monthly_sales
FROM sales 
GROUP BY month 
ORDER BY month
```

### 在庫管理系
```sql
-- 在庫少ない商品（5個以下）
SELECT name, stock, price FROM products 
WHERE stock <= 5 
ORDER BY stock

-- カテゴリ別商品数
SELECT category, COUNT(*) as product_count 
FROM products 
GROUP BY category
```

### 顧客分析系（個人情報除外）
```sql
-- 顧客タイプ別統計
SELECT customer_type, COUNT(*) as customer_count,
       AVG(total_purchases) as avg_purchases
FROM customers 
GROUP BY customer_type

-- 購入頻度の高い顧客（IDのみ）
SELECT id, total_purchases, customer_type
FROM customers 
WHERE total_purchases > 10 
ORDER BY total_purchases DESC
```

## 特別なルール

### エラー対処
- "no such column" エラー → 必ずスキーマ確認してから再実行
- JOINエラー → テーブル関係を確認してから再構築  
- 日付フォーマットエラー → strftime形式を確認

### データ表示形式
- 金額： カンマ区切り + 円表示（例：1,234,567円）
- 日付： YYYY-MM-DD形式
- 件数： 必ず件数を明記

### パフォーマンス考慮
- 大量データの場合は必ずLIMITを指定
- 複雑なクエリの場合はINDEXの存在を考慮
- JOINは必要最小限に

## 分析パターンの例

### 要求: 「売上分析レポート」
```
1. list_tables → テーブル確認
2. get_table_schema(sales) → 売上テーブル構造確認  
3. get_table_schema(products) → 商品テーブル構造確認
4. execute_safe_query → 月次売上推移
5. execute_safe_query → 商品別売上TOP10
6. execute_safe_query → カテゴリ別売上
```

### 要求: 「在庫状況チェック」
```
1. list_tables → テーブル確認
2. get_table_schema(products) → 商品テーブル構造確認
3. execute_safe_query → 在庫少ない商品リスト
4. execute_safe_query → カテゴリ別在庫数
```

---
*ECサイトデータベース分析に最適化された設定*