# MCP Agent - LLM統合型エージェント

## 概要

本プロジェクトは、LLM（大規模言語モデル）とMCP（Model Context Protocol）を統合した実践的なAIエージェントです。自然言語でタスクを指示すると、自動的に計画を立て、適切なツールを選択し、エラーにも対応しながらタスクを完遂します。

## 特徴

- **マルチLLMサポート**: OpenAI (GPT-4/GPT-3.5)、Anthropic (Claude)、Google (Gemini) に対応
- **インテリジェントタスクプランニング**: LLMがタスクを理解し、実行可能なステップに分解
- **スマートエラーハンドリング**: エラーを分析し、リトライ、スキップ、フォールバックを自動判断
- **MCPツール統合**: 様々なMCPサーバーのツールをシームレスに活用
- **コスト最適化**: キャッシング機能でAPI呼び出しを削減

## セットアップ

### 1. 依存パッケージのインストール

```bash
cd C:\MCP_Learning\chapter10
uv init
uv sync
```

または通常のpipを使用：

```bash
pip install -r requirements.txt
```

### 2. 環境設定

`.env.example`を`.env`にコピーして設定：

```bash
cp .env.example .env
```

`.env`ファイルを編集：

```env
# LLMプロバイダー（openai, anthropic, google から選択）
LLM_PROVIDER=openai

# APIキー（使用するプロバイダーのものを設定）
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxx
# ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx
# GOOGLE_API_KEY=AIzaxxxxxxxxxxxxx

# モデル設定
LLM_MODEL=gpt-4o-mini

# コスト管理
MAX_TOKENS_PER_REQUEST=1000
ENABLE_CACHE=true
CACHE_TTL_SECONDS=3600
```

### 3. APIキーの取得

使用するLLMプロバイダーのAPIキーを取得：

- **OpenAI**: https://platform.openai.com/api-keys
- **Anthropic**: https://console.anthropic.com/
- **Google**: https://makersuite.google.com/app/apikey

## クイックスタート

### シンプルなデモ

```bash
uv run python examples/simple_demo.py
```

### インタラクティブモード

```bash
uv run python examples/data_analysis_demo.py
# 「4」を選択してインタラクティブモードへ
```

### Pythonコードから使用

```python
import asyncio
from integrated_agent import MCPAgent

async def main():
    # エージェントを初期化
    agent = MCPAgent(use_mock=True)  # テスト用モックモード
    
    # タスクを実行
    result = await agent.execute(
        "競合3社の最新ニュースを調査して比較表を作成"
    )
    
    if result['success']:
        print(f"結果: {result['result']}")
    else:
        print(f"エラー: {result['error']}")

asyncio.run(main())
```

## アーキテクチャ

```
MCPAgent
├── LLMClient (llm_client.py)
│   ├── OpenAIClient
│   ├── AnthropicClient
│   └── GoogleClient
├── TaskPlanner (task_planner.py)
│   └── タスクを実行可能なステップに分解
├── ErrorHandler (error_handler.py)
│   └── エラーを分析して対処法を決定
└── MCPManager (mcp_manager.py)
    └── MCPサーバーとの通信管理
```

## ファイル構成

```
chapter10/
├── .env                    # 環境設定（要作成）
├── .env.example           # 環境設定テンプレート
├── pyproject.toml         # プロジェクト設定
├── README.md              # このファイル
├── llm_client.py          # LLMクライアント実装
├── task_planner.py        # タスクプランナー
├── error_handler.py       # エラーハンドラー
├── mcp_manager.py         # MCPマネージャー
├── integrated_agent.py    # 統合エージェント
└── examples/              # 使用例
    ├── simple_demo.py     # シンプルなデモ
    └── data_analysis_demo.py  # 高度なデモ
```

## 使用例

### 1. 計算タスク

```python
result = await agent.execute(
    "15と25を足して、その結果を2倍にして"
)
```

### 2. データ分析

```python
result = await agent.execute("""
    売上データを分析：
    1. Q4の売上を集計
    2. 前年同期比を計算
    3. トップ5商品を特定
    4. レポート作成
""")
```

### 3. Web調査

```python
result = await agent.execute(
    "AI業界の最新トレンドを調査してまとめて"
)
```

## カスタマイズ

### 新しいMCPサーバーの追加

`~/.config/mcp/servers.json`に設定を追加：

```json
{
  "servers": {
    "my_server": {
      "command": "python",
      "args": ["path/to/my_server.py"]
    }
  }
}
```

### エラーハンドリングのカスタマイズ

```python
from error_handler import LLMErrorHandler, ErrorResolution

class CustomErrorHandler(LLMErrorHandler):
    def _create_default_resolution(self, context):
        # カスタムエラー処理ロジック
        return ErrorResolution(
            strategy="retry",
            description="Custom retry logic",
            max_retries=5
        )
```

## トラブルシューティング

### LLM APIエラー

```
Error: OpenAI API error: Invalid API key
```
→ `.env`ファイルのAPIキーを確認

### MCPサーバー接続エラー

```
Error: Failed to connect to calculator
```
→ MCPサーバーが正しく設定されているか確認

### メモリ不足

キャッシュを無効化：
```env
ENABLE_CACHE=false
```

## パフォーマンス最適化

1. **キャッシング**: 同じプロンプトの結果を再利用
2. **モデル選択**: 軽量モデル（gpt-3.5-turbo等）を使用
3. **トークン制限**: MAX_TOKENS_PER_REQUESTを調整

## セキュリティ

- APIキーは必ず`.env`ファイルで管理
- `.env`ファイルは`.gitignore`に追加
- 本番環境では環境変数を使用

## ライセンス

MIT License

## サポート

質問や問題がある場合は、Issueを作成してください。