# MCPエージェント指示書

この指示書は、MCPエージェントがタスクを分解し実行する際のガイドラインです。

## 基本原則

### 1. データベース操作のルール
- **3ステップ実行**: データベース関連の要求は必ず以下の順序で実行
  1. `list_tables` - テーブル一覧の確認
  2. `get_table_schema` - 対象テーブルのスキーマ確認
  3. `execute_safe_query` - 実際のクエリ実行

### 2. ファイル操作のルール
- **ファイル読み込み**: `read_file`ツールを使用してテキストファイルの内容を取得
- **ファイル書き込み**: `write_file`ツールを使用してファイルに内容を保存
- **ディレクトリ一覧**: `list_directory`ツールを使用してフォルダの中身を確認

### 3. ユーザー意図の解釈
- **「一覧」「表示」「見る」「取得」** → 実際のデータ取得が必要
- **「構造」「スキーマ」「テーブル情報」** → メタ情報の確認のみ
- **「テーブル一覧」** → list_tablesのみ実行
- **「ファイルを読む」「.txtの内容」「ファイルを開く」** → read_fileツール使用
- **「ファイルに書く」「保存する」「書き込む」** → write_fileツール使用
- **「フォルダの中身」「ディレクトリ一覧」「ファイル一覧」** → list_directoryツール使用

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
数式を含む要求の場合：
- 演算の優先順位を守る（乗除算を先に、加減算を後に）
- 複雑な式は段階的に分解

例：
- 「100+200」の場合：単純な加算
- 「100+200+400*3」の場合：
  1. 400*3を先に計算（乗算優先）
  2. 100+200を計算
  3. 最後に両者を加算
- 「フィボナッチ数列10個」→ 数列生成ツールを使用

### ファイル操作関連
```
「fibonacci_sequence.txtを読んで」
→ filesystem: read_file(path="fibonacci_sequence.txt")

「README.mdの内容を表示」
→ filesystem: read_file(path="README.md")

「現在のディレクトリの内容を見る」
→ filesystem: list_directory(path=".")

「sample.txtに内容を書き込む」
→ filesystem: write_file(path="sample.txt", content="内容")

「numbered_list.mdファイルの中身」
→ filesystem: read_file(path="numbered_list.md")
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

### 複数の情報取得
並列で取得可能な情報（天気、データベースなど）：
- 全ての結果を含めて回答
- 比較や対比が必要な場合は明示的に説明

## エラー対処パターン

### 天気API（get_weather）
- **404エラー（Not Found）**: 都市名が存在しない
  - `"New York"` → `"New York,US"`
  - `"東京"` → `"Tokyo,JP"`
  - `"大阪"` → `"Osaka,JP"`

### データベースエラー
- **"no such column" エラー**: カラム名が間違っている
  - 必ず`get_table_schema`でカラム名を確認してから修正
- **"no such table" エラー**: テーブル名が間違っている
  - `list_tables`でテーブル名を確認
- **SQLシンタックスエラー**: クエリの文法エラー
  - 日付は`strftime`関数を使用
  - 文字列は単一引用符で囲む

### 計算ツールエラー
- **型エラー**: 文字列が渡されている
  - `"100"` → `100`（数値に変換）
- **パラメータ不足**: 必要なパラメータが不足
  - `add`には`a`と`b`が必須

### ネットワークエラー
- **タイムアウト**: 一時的な接続問題
  - 自動的にリトライされる（修正不要）
- **500/503エラー**: サーバー側の問題
  - 自動的にリトライされる（修正不要）

### ファイルシステムエラー
- **"File not found"エラー**: ファイルが存在しない
  - `list_directory`で存在確認してからread_file
- **"Permission denied"エラー**: アクセス権限なし
  - 別のパスを試すか、ユーザーに確認
- **パスエラー**: 相対パス/絶対パスの問題
  - 相対パス: `"./file.txt"` または `"file.txt"`
  - 絶対パス: `"C:\\MCP_Learning\\chapter10\\file.txt"`

## 重要な注意事項

1. **データ表示時の制限**: 大量データの場合は必ず`LIMIT`句を使用（推奨: 10〜20件）
2. **日付形式**: SQLiteでは`strftime`関数を使用
3. **エラー時の対応**: エラーメッセージを分析し、適切な前処理を実行
4. **並列実行**: 依存関係のないタスクは並列実行可能
5. **パラメータエラー**: 404/400系エラーは自動的にパラメータ修正を試行

## ツール不要のケース（重要）

以下は**日常会話**であり、ツールの使用は不要です：

### 挨拶・コミュニケーション
- 「こんにちは」「おはよう」「お疲れさま」
- 「私の名前はガーコです」「よろしくお願いします」
- 「今日はいい天気ですね」「お元気ですか」

### 感想・応答
- 「ありがとう」「よくできました」「素晴らしい」
- 「わかりました」「そうですね」「なるほど」

これらの場合は、親しみやすい挨拶や会話で応答してください。
データベースやツールを呼び出す必要はありません。

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