# 統合MCPエージェント 使用ガイド

## 最新機能

### 1. 結果の自動解釈
エージェントが実行結果をLLMで解釈し、人間にわかりやすく説明する機能

### 2. 会話記憶機能 [NEW]
エージェントが会話の文脈を記憶し、前の会話を参照して応答する機能

## 実行方法

### 1. 対話モード（デフォルト）
```cmd
uv run python run_integrated_agent.py
```

### 2. クイックデモ
```cmd
uv run python run_integrated_agent.py --demo
```

### 3. バッチ実行
```cmd
# コマンドラインから
uv run python run_integrated_agent.py --batch "100と200を足して" "2の8乗を計算"

# ファイルから
uv run python run_integrated_agent.py --file sample_tasks.txt
```

### 4. 結果解釈のオン/オフ
```cmd
# 解釈機能を無効化（高速化したい場合）
uv run python run_integrated_agent.py --no-interpret

# AI機能全体を無効化（OpenAI APIキーがない場合）
uv run python run_integrated_agent.py --no-ai
```

## 結果解釈の例

### 計算タスク
**入力**: "100と200を足して、その結果を2で割って"

**解釈された結果**:
```
計算を実行しました。
まず100と200を足して300になり、
その300を2で割った結果、150になりました。
```

### 天気情報
**入力**: "東京とニューヨークの天気を教えて"

**解釈された結果**:
```
東京とニューヨークの現在の天気情報です：

【東京】
- 気温: 31.5℃（体感温度: 38.2℃）
- 天候: 曇りがち
- 湿度: 68%
- 風速: 8.2 m/s

【ニューヨーク】
- 気温: 25.3℃（体感温度: 26.1℃）
- 天候: 晴れ
- 湿度: 45%
- 風速: 3.5 m/s

東京は蒸し暑く、ニューヨークは過ごしやすい天気です。
```

## セッション管理

### セッションの保存と復元
```cmd
# セッションを指定して起動
uv run python run_integrated_agent.py --session my_work.json

# 終了時に自動保存され、次回起動時に学習内容が復元されます
```

### 対話モードのコマンド
- `status` - セッション統計を表示
- `history` - 実行履歴を表示
- `learn` - 学習済みパターンを表示
- `help` - ヘルプを表示
- `exit` - 終了

## テスト

### 自動テスト
```cmd
uv run python test_integrated_agent.py
```

### 対話型テスト
```cmd
uv run python test_integrated_agent.py --interactive
```

## 会話記憶機能

### 記憶される情報
- **ユーザー名**: 「私の名前は○○です」と伝えると記憶
- **エージェント名**: 「君の名前は○○です」と設定すると記憶
- **計算結果**: 実行した計算や処理の結果を最新10件まで記憶
- **会話履歴**: 最近の会話10件を文脈として保持
- **重要な事実**: 名前、場所などの重要情報を永続的に記憶

### 使用例

```
ユーザー: 君の名前はガーコです
エージェント: [記憶] エージェント名を設定: ガーコ

ユーザー: 100と200を足して
エージェント: 計算結果は300です

ユーザー: さっきの計算結果は何だった？
エージェント: 前の計算結果は300でした

ユーザー: 君の名前を言ってみて
エージェント: 私の名前はガーコです
```

### セッション間での記憶の永続化

記憶はセッションファイルに保存され、次回起動時に自動的に復元されます：

```cmd
# 初回実行（記憶を設定）
uv run python integrated_mcp_agent.py
> 君の名前はアシスタントです
> 私の名前は太郎です
> exit

# 2回目の実行（記憶が復元される）
uv run python integrated_mcp_agent.py
> 君の名前は何？
アシスタント: 私の名前はアシスタントです

> 私の名前を覚えてる？
アシスタント: はい、太郎さんですね
```

### 記憶機能のテスト

```cmd
# 記憶機能の包括的テスト
uv run python test_memory_features.py
```

## トラブルシューティング

### エラー: "OPENAI_API_KEYが設定されていません"
`.env`ファイルにAPIキーを設定してください：
```
OPENAI_API_KEY=your_api_key_here
```

### エラー: "サーバーに接続できません"
MCPサーバーが起動していることを確認してください：
```cmd
# 別のターミナルで
cd C:\MCP_Learning\chapter03
uv run python calculator_server.py
```

## カスタマイズ

### 新しいMCPサーバーの追加

`mcp_servers.json`を編集：
```json
{
  "servers": [
    {
      "name": "calculator",
      "path": "C:\\MCP_Learning\\chapter03\\calculator_server.py",
      "chapter": "chapter03"
    },
    {
      "name": "your_server",
      "path": "C:\\path\\to\\your_server.py",
      "chapter": "custom"
    }
  ]
}
```

エージェントは自動的に新しいサーバーを認識します。