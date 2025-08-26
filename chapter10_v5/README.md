# MCP Agent - Interactive Dialogue Engine

Claude Code風の対話型MCPエージェント

## 概要

遅去バージョンの知見を活かし、Claude Codeのような対話的で視覚的に分かりやすいエージェントです。依存関係管理をLLMに任せることで、よりシンプルで理解しやすい実装を実現しました。

## 過去バージョンからの進化

### V3 → V4の主要な変更点

| 要素 | V3 | V4 |
|------|----|----|
| **実行方式** | 一括タスク分解・依存関係管理 | 対話的逐次実行 |
| **コード行数** | 約500行 | 約250行（50%削減） |
| **視覚表示** | 基本的なログ出力 | チェックボックス付きタスクリスト |
| **依存関係** | 複雑な`{task_X}`参照システム | LLMが前の結果を見て次を判断 |
| **エラー処理** | task_executor.pyで複雑な処理 | シンプルなリトライ機構 |

### 継承された要素（V3の良さをそのまま活用）

- ✅ **AGENT.md方式**: コード変更なしでカスタマイズ可能
- ✅ **会話文脈機能**: 「私の場所の天気は？」等に対応
- ✅ **NO_TOOL判定**: 日常会話での不要なツール呼び出し防止
- ✅ **connection_manager**: MCPサーバー接続管理

## ファイル構成

```
chapter10_v4/
├── mcp_agent.py           # メインエージェント（250行）
├── display_manager.py     # 視覚的表示管理（150行）
├── connection_manager.py  # MCP接続管理（V3から流用）
├── config.yaml           # 設定ファイル
├── AGENT.md              # カスタマイズ指示書（V3から流用）
└── README.md             # このファイル
```

## 特徴

### 1. Claude Code風の表示

```
[タスク一覧]
  [x] IPアドレス情報を取得 (0.8秒)
  [x] 位置から天気情報を取得 (1.2秒)
  [ ] 結果をまとめて表示

[ステップ 3/3] 結果をまとめて表示
  開始時刻: 14:35:22
  [完了] 結果をまとめて表示 (0.1秒)
```

### 2. 対話的逐次実行

V3の複雑な依存関係管理：
```python
# V3: 複雑だが高速
{
  "tasks": [
    {"id": "task_1", "tool": "add", "params": {"a": 100, "b": 200}},
    {"id": "task_2", "tool": "multiply", "params": {"a": "{task_1}", "b": 3}}
  ]
}
```

V4のシンプルな段階実行：
```python
# V4: シンプルで理解しやすい
step1 = await call_tool("add", {"a": 100, "b": 200})    # → 300
step2 = await call_tool("multiply", {"a": 300, "b": 3}) # → 900
```

### 3. 柔軟な設定管理

`config.yaml`で細かく動作をカスタマイズ：
```yaml
display:
  show_timing: true      # 実行時間表示
  show_thinking: false   # 思考過程表示
  
execution:
  max_retries: 3         # リトライ回数
  timeout_seconds: 30    # タイムアウト
```

## 使用方法

### 基本的な実行

```bash
# V4ディレクトリに移動
cd C:\MCP_Learning\chapter10_v4

# エージェント実行
uv run python mcp_agent.py
```

### 設定のカスタマイズ

1. **表示設定の変更**
   ```yaml
   # config.yaml
   display:
     show_thinking: true  # 思考過程を表示
   ```

2. **AGENT.mdでの動作カスタマイズ**
   ```markdown
   # AGENT.md
   ## このプロジェクト専用の規則
   - 金額は必ず日本円で表示
   - 天気情報には体感温度も含める
   ```

## V3との比較

### パフォーマンス

| 項目 | V3 | V4 |
|------|----|----|
| **実行速度** | 高速（並列実行） | やや低速（逐次実行） |
| **API呼び出し** | 少ない（一括計画） | やや多い（段階的実行） |
| **メモリ使用量** | 多い（複雑な依存管理） | 少ない（シンプル構造） |

### 開発効率

| 項目 | V3 | V4 |
|------|----|----|
| **コード理解** | 困難（依存関係が複雑） | 容易（直線的な流れ） |
| **デバッグ** | 困難（どこで問題？） | 容易（ステップごとに確認） |
| **機能拡張** | 困難（既存コードへの影響） | 容易（独立したステップ） |

## 実装のポイント

### 1. 段階的実行の仕組み

```python
async def _execute_interactive_dialogue(self, user_query: str) -> str:
    execution_context = []  # 実行履歴を蓄積
    
    while True:
        # LLMが次のアクションを決定
        action = await self._get_next_action(user_query, execution_context)
        
        if action["type"] == "COMPLETE":
            return action["response"]
        
        # 1ステップ実行
        result = await self._execute_step(action)
        execution_context.append(result)  # 履歴に追加
```

### 2. エラー処理のシンプル化

V3の複雑なエラー分析を削除し、シンプルなリトライに集約：
```python
async def _execute_tool_with_retry(self, tool: str, params: Dict):
    for attempt in range(max_retries + 1):
        try:
            return await self.connection_manager.call_tool(tool, params)
        except Exception as e:
            if attempt < max_retries:
                await asyncio.sleep(retry_interval)
            else:
                raise e
```

## トラブルシューティング

### よくある問題

1. **YAML設定エラー**
   ```
   [警告] 設定ファイル読み込みエラー
   ```
   → `config.yaml`の構文を確認

2. **AGENT.mdが見つからない**
   ```
   [情報] AGENT.mdが見つかりません
   ```
   → 正常です。基本能力のみで動作

3. **MCP接続エラー**
   ```
   [エラー] MCP server connection failed
   ```
   → V3と同じ解決方法を適用

## 今後の拡張予定

- [ ] 中断・再開機能
- [ ] 実行ログの外部保存
- [ ] プラグイン機構
- [ ] Web UI対応

## ライセンス

V3と同じライセンス

---

*V3とV4、それぞれに異なる魅力があります。高速実行が必要ならV3、理解しやすさと柔軟性を重視するならV4をお選びください。*