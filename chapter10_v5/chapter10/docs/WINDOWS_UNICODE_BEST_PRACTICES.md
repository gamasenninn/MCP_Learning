# Windows環境でのUnicode・MCP開発 ベストプラクティス

## 概要

Windows環境でMCP（Model Context Protocol）アプリケーションを開発する際のUnicode処理、特にサロゲート文字問題への対策をまとめたベストプラクティスガイド。

## 基本原則

### 1. 防御in深度（Defense in Depth）
```python
# 入口・処理・出口の3層でサロゲート文字を処理
def process_with_surrogate_protection(data):
    # 入口: データ受信時の無害化
    clean_input = scrub_surrogates(data)
    
    # 処理: 安全な環境での実行
    result = subprocess.run(..., errors='replace')
    
    # 出口: 出力時の最終無害化
    clean_output = scrub_surrogates(result.stdout)
    return clean_output
```

### 2. 統一ポリシーの適用
```python
# 全体で一貫したサロゲート処理ポリシー
SURROGATE_POLICY = os.environ.get("SURROGATE_POLICY", "replace")

def scrub_surrogates(text: str, mode: str = None) -> str:
    mode = mode or SURROGATE_POLICY
    # 統一された処理ロジック
```

### 3. 環境変数による制御
```bash
# Windows環境でのPython実行前に設定
set PYTHONIOENCODING=utf-8:replace
set PYTHONLEGACYWINDOWSFSENCODING=0
set PYTHONUTF8=1
set SURROGATE_POLICY=replace
```

## 具体的な実装パターン

### 1. サロゲート文字検出・処理関数

```python
import unicodedata
import os
from typing import Literal

def scrub_surrogates(
    s: str, 
    mode: Literal["replace", "ignore", "escape"] = "replace"
) -> str:
    """
    Unicode サロゲート文字（U+D800-U+DFFF）を安全に処理
    
    Args:
        s: 処理対象の文字列
        mode: 処理モード
            - "replace": ?に置換（推奨）
            - "ignore": 削除
            - "escape": \\uDCXX形式にエスケープ
    
    Returns:
        処理済み文字列
    """
    if not isinstance(s, str):
        s = str(s)
    
    # Unicode正規化（推奨）
    try:
        s = unicodedata.normalize("NFC", s)
    except Exception:
        pass
    
    result = []
    for char in s:
        code_point = ord(char)
        if 0xD800 <= code_point <= 0xDFFF:  # サロゲート範囲
            if mode == "ignore":
                continue
            elif mode == "escape":
                result.append(f"\\u{code_point:04X}")
            else:  # "replace"
                result.append("?")
        else:
            result.append(char)
    
    return "".join(result)

def detect_surrogates(text: str) -> dict:
    """
    文字列内のサロゲート文字を検出・分析
    
    Returns:
        検出情報の辞書
    """
    surrogates = []
    for i, char in enumerate(text):
        code_point = ord(char)
        if 0xD800 <= code_point <= 0xDFFF:
            surrogates.append({
                "position": i,
                "character": char,
                "code_point": f"U+{code_point:04X}",
                "type": "high" if 0xD800 <= code_point <= 0xDBFF else "low"
            })
    
    return {
        "count": len(surrogates),
        "surrogates": surrogates,
        "has_surrogates": len(surrogates) > 0
    }
```

### 2. subprocess実行時の安全な設定

```python
import subprocess
import sys
import os

def safe_subprocess_run(code: str, **kwargs):
    """
    Windows環境でサロゲート文字に対応したsubprocess実行
    """
    # 環境変数の準備
    env = os.environ.copy()
    env.update({
        'PYTHONIOENCODING': 'utf-8:replace',
        'PYTHONLEGACYWINDOWSFSENCODING': '0',
        'PYTHONUTF8': '1',
        'LC_ALL': 'C.UTF-8',
        'LANG': 'en_US.UTF-8'
    })
    
    # コードの事前処理
    clean_code = scrub_surrogates(code)
    
    # 安全なsubprocess実行
    result = subprocess.run(
        [sys.executable, "-c", "import sys; exec(sys.stdin.read())"],
        input=clean_code,
        text=True,
        capture_output=True,
        encoding='utf-8',
        errors='replace',  # 重要：replace mode
        env=env,
        **kwargs
    )
    
    # 出力の後処理
    clean_stdout = scrub_surrogates(result.stdout)
    clean_stderr = scrub_surrogates(result.stderr)
    
    return result._replace(stdout=clean_stdout, stderr=clean_stderr)
```

### 3. MCP サーバーでの実装パターン

```python
from fastmcp import FastMCP
from fastmcp.client.client import CallToolResult

def process_mcp_result(result) -> str:
    """
    MCP CallToolResult オブジェクトのサロゲート文字処理
    """
    if isinstance(result, CallToolResult):
        if hasattr(result, 'content') and result.content:
            for content_item in result.content:
                if hasattr(content_item, 'text') and content_item.text:
                    content_item.text = scrub_surrogates(content_item.text)
        
        if hasattr(result, 'data') and result.data:
            result.data = scrub_surrogates(result.data)
    
    return result

# FastMCP ツール実装例
mcp = FastMCP("Safe Unicode Server")

@mcp.tool()
def execute_safe_python(code: str) -> str:
    """サロゲート文字対応のPython実行"""
    try:
        # 入口での処理
        clean_code = scrub_surrogates(code)
        
        # 実行
        result = safe_subprocess_run(clean_code)
        
        # 出口での処理
        if result.returncode == 0:
            return f"成功:\n{result.stdout}" if result.stdout else "成功:\n(出力なし)"
        else:
            return f"エラー:\n{result.stderr}"
    
    except Exception as e:
        # エラーメッセージも処理
        error_msg = scrub_surrogates(str(e))
        return f"実行エラー: {error_msg}"
```

### 4. 設定ファイルでの管理

```yaml
# config.yaml
unicode_handling:
  surrogate_policy: "replace"  # replace, ignore, escape
  encoding: "utf-8"
  normalization: "NFC"
  
subprocess:
  timeout: 5
  encoding: "utf-8"
  errors: "replace"
  
environment:
  PYTHONIOENCODING: "utf-8:replace"
  PYTHONUTF8: "1"
  PYTHONLEGACYWINDOWSFSENCODING: "0"
```

```python
# 設定読み込み例
import yaml

class UnicodeConfig:
    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
    
    @property
    def surrogate_policy(self) -> str:
        return self.config.get("unicode_handling", {}).get("surrogate_policy", "replace")
    
    def get_env_vars(self) -> dict:
        return self.config.get("environment", {})
```

## トラブルシューティング

### よくある問題と対処法

#### 1. `UnicodeEncodeError: surrogates not allowed`
```python
# 対処法：errors='replace'を使用
result = subprocess.run(..., errors='replace')

# または事前にサロゲート文字を除去
clean_input = scrub_surrogates(input_text)
```

#### 2. 日本語文字の文字化け
```python
# Windows環境変数の確認・設定
os.environ['PYTHONIOENCODING'] = 'utf-8:replace'
os.environ['PYTHONUTF8'] = '1'

# より適切なエンコーディング処理
def safe_decode(data: bytes) -> str:
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        return data.decode('utf-8', errors='replace')
```

#### 3. FastMCP での文字化け
```python
# CallToolResult オブジェクトの処理
def clean_tool_result(result):
    if hasattr(result, 'content'):
        for item in result.content:
            if hasattr(item, 'text'):
                item.text = scrub_surrogates(item.text)
```

### デバッグ支援機能

```python
def debug_unicode_issues(text: str, context: str = ""):
    """
    Unicode問題のデバッグ支援
    """
    print(f"=== Unicode Debug: {context} ===")
    print(f"Length: {len(text)}")
    print(f"Type: {type(text)}")
    
    # サロゲート文字の検出
    detection = detect_surrogates(text)
    print(f"Surrogates: {detection['count']}")
    
    if detection['has_surrogates']:
        print("Surrogate details:")
        for s in detection['surrogates']:
            print(f"  Pos {s['position']}: {s['code_point']} ({s['type']})")
    
    # エンコーディングテスト
    encodings = ['utf-8', 'cp932', 'shift_jis']
    for enc in encodings:
        try:
            text.encode(enc)
            print(f"✓ {enc}: OK")
        except UnicodeEncodeError as e:
            print(f"✗ {enc}: {e}")
    
    print("=" * 40)
```

## テスト戦略

### 1. 包括的テストケース

```python
import pytest

class TestUnicodeHandling:
    test_cases = [
        # (description, input, expected_safe)
        ("ASCII only", "Hello World", True),
        ("日本語", "こんにちは", True),
        ("混在", "Hello こんにちは", True),
        ("絵文字", "🎌🗾", True),
        ("サロゲート文字", "test\udc86test", False),
        ("空文字", "", True),
        ("長文", "あ" * 1000, True),
    ]
    
    @pytest.mark.parametrize("desc,text,expected_safe", test_cases)
    def test_surrogate_detection(self, desc, text, expected_safe):
        detection = detect_surrogates(text)
        assert not detection['has_surrogates'] == expected_safe, f"Failed: {desc}"
    
    @pytest.mark.parametrize("desc,text,expected_safe", test_cases)
    def test_surrogate_scrubbing(self, desc, text, expected_safe):
        cleaned = scrub_surrogates(text)
        detection = detect_surrogates(cleaned)
        assert not detection['has_surrogates'], f"Scrubbing failed: {desc}"
```

### 2. 統合テスト

```python
def test_end_to_end_japanese():
    """日本語コードの端末間実行テスト"""
    japanese_code = '''
print("ハノイの塔を開始します")
for i in range(3):
    print(f"ステップ {i+1}")
print("完了しました")
'''
    
    # 実行
    result = safe_subprocess_run(japanese_code)
    
    # 検証
    assert result.returncode == 0, "実行が失敗しました"
    assert "を開始" in result.stdout or "?" in result.stdout, "出力が期待と異なります"
    
    # サロゲート文字がないことを確認
    detection = detect_surrogates(result.stdout)
    assert not detection['has_surrogates'], "出力にサロゲート文字が含まれています"
```

## パフォーマンス最適化

### 1. 効率的なサロゲート検出

```python
def fast_has_surrogates(text: str) -> bool:
    """
    高速なサロゲート文字存在チェック
    """
    return any(0xD800 <= ord(c) <= 0xDFFF for c in text)

def batch_scrub_surrogates(texts: list[str]) -> list[str]:
    """
    バッチ処理版サロゲート文字クリーンアップ
    """
    return [scrub_surrogates(text) for text in texts if fast_has_surrogates(text)]
```

### 2. キャッシュ機能

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def cached_scrub_surrogates(text: str) -> str:
    """
    キャッシュ機能付きサロゲート処理
    """
    return scrub_surrogates(text)
```

## まとめ

### 重要なポイント

1. **防御in深度**: 複数の層でサロゲート文字を処理
2. **統一ポリシー**: 一貫した処理方針の適用
3. **環境変数制御**: Windows特有の設定が重要
4. **包括的テスト**: 多様なケースでの動作確認
5. **デバッグ機能**: 問題発生時の迅速な特定

### チェックリスト

- [ ] `scrub_surrogates()` 関数の実装
- [ ] subprocess実行時の `errors='replace'` 設定
- [ ] Windows環境変数の適切な設定
- [ ] MCP結果オブジェクトの処理
- [ ] 包括的テストケースの作成
- [ ] デバッグ機能の組み込み

---

**最終更新**: 2025-01-24  
**対象環境**: Windows 11, Python 3.12+, FastMCP 2.11+  
**ライセンス**: MIT License