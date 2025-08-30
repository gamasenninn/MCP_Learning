# MCP Agent テストスイート

## テスト構成

```
tests_new/
├── unit/          # モックを使用した単体テスト（高速）
├── integration/   # コンポーネント間の統合テスト
├── functional/    # 機能テスト（モックベース）
├── e2e/          # エンドツーエンド実環境テスト（要API KEY）
└── smoke/        # 最小限のリアル環境確認テスト
```

## テストの実行方法

### 1. モックテスト（通常の開発時）

```bash
# 全モックテスト実行
uv run python run_tests.py

# 高速単体テストのみ（0.04秒）
uv run python run_tests.py quick

# スモークテスト（最重要機能のみ）
uv run python run_tests.py smoke

# カバレッジ付き実行
uv run python run_tests.py --coverage
```

### 2. リアルテスト（実際のAPI使用）

#### 準備
```bash
# 1. 環境設定ファイルをコピー
cp .env.test.example .env.test

# 2. .env.testを編集してAPI KEYを設定
# OPENAI_API_KEY=sk-your-actual-key

# 3. 環境変数として設定（または.env.testから読み込み）
export OPENAI_API_KEY=sk-your-actual-key
```

#### 実行
```bash
# リアルテスト（高額テストはスキップ）
uv run python run_tests.py real

# E2Eテスト
uv run python run_tests.py e2e

# 高額テストも含めて実行（注意！）
export RUN_EXPENSIVE_TESTS=true
uv run python run_tests.py real
```

## テストマーカー

| マーカー | 説明 | 使用例 |
|---------|------|--------|
| `@pytest.mark.unit` | 単体テスト | 個別コンポーネントのテスト |
| `@pytest.mark.integration` | 統合テスト | コンポーネント間連携 |
| `@pytest.mark.functional` | 機能テスト | エンドツーエンド機能確認 |
| `@pytest.mark.real` | リアルテスト | 実際のAPI/サービス使用 |
| `@pytest.mark.requires_api` | API KEY必要 | OpenAI APIなど |
| `@pytest.mark.expensive` | 高額テスト | GPT-5/o1モデル使用 |
| `@pytest.mark.slow` | 遅いテスト | 実行時間が長い |
| `@pytest.mark.e2e` | E2Eテスト | 完全な実環境テスト |
| `@pytest.mark.smoke` | スモークテスト | 最小限の動作確認 |

## 個別テストの実行

```bash
# 特定のテストファイル
uv run python -m pytest tests_new/unit/test_state_manager.py -v --disable-warnings

# 特定のテスト関数
uv run python -m pytest tests_new/unit/test_state_manager.py::test_state_manager_initialization

# マーカーで絞り込み
uv run python -m pytest tests_new -m "unit and not slow" --disable-warnings
uv run python -m pytest tests_new -m gpt5 --disable-warnings
```

## CI/CD設定例

```yaml
# GitHub Actions例
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Run mock tests (PR)
        run: uv run python run_tests.py
        
      - name: Run E2E tests (Nightly)
        if: github.event_name == 'schedule'
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          RUN_EXPENSIVE_TESTS: false
        run: uv run python run_tests.py e2e
```

## トラブルシューティング

### API KEY関連
- `OPENAI_API_KEY`が`test_key`の場合、リアルテストはスキップされます
- 実際のAPI KEYは絶対にコミットしないでください

### 警告の抑制
- すべてのテスト実行で`--disable-warnings`が自動的に適用されます
- pytest.iniで`-W ignore::pytest.PytestUnknownMarkWarning`を設定済み

### コスト管理
- `MAX_API_CALLS`環境変数でAPI呼び出し回数を制限
- `SKIP_EXPENSIVE=true`（デフォルト）で高額テストをスキップ
- `COST_WARNING_THRESHOLD`で警告閾値を設定可能

## カバレッジ

現在のカバレッジ: 34% (2010行中1319行)

主要ファイル:
- state_manager.py: 43%
- task_manager.py: 28%
- mcp_agent.py: 24%
- gpt5_chat.py: 0% (新機能、テスト未実装)