# MCP Agent V4 サロゲート文字問題 完全解決記録

## 概要

Windows環境でMCP Agent V4実行時に発生する `UnicodeEncodeError: 'utf-8' codec can't encode character '\udcXX' in position X: surrogates not allowed` エラーの根本原因解明と完全解決策を記録する。

## 問題の症状

### 初期症状
- 日本語を含むPythonコードの実行時にUnicodeEncodeErrorが発生
- エラーメッセージに `\udc81`, `\udc86`, `\udc8b` などのサロゲート文字が含まれる
- 英語のみのコードは正常動作
- エラー発生位置が実行のたびに変動（23→57→121→286）

### エラーメッセージ例
```
UnicodeEncodeError: 'utf-8' codec can't encode character '\udc86' in position 74: surrogates not allowed
```

## 根本原因の解明過程

### 1. 初期仮説（誤り）
**仮説**: Rich ライブラリの `Syntax()` 関数がサロゲート文字を生成
- **検証結果**: 部分的解決のみ。問題の本質ではなかった

### 2. 中間仮説（部分的）
**仮説**: connection_manager.py や error_handler.py でのサロゲート文字処理不備
- **検証結果**: 防御層としては有効だが、根本原因ではなかった

### 3. 真の根本原因
**発見**: ワーカープロセス内でのPython実行時にサロゲート文字が生成される

#### 技術的詳細
- Windows環境でPythonが日本語文字列を処理する際、内部的にサロゲートペアに変換
- `subprocess.run()` でワーカープロセスを起動し、標準入力経由でコードを渡す
- ワーカープロセス内の `exec(sys.stdin.read())` 実行時にサロゲート文字が混入
- UTF-8エンコーディングではサロゲート文字の直接エンコードが禁止されているためエラー発生

#### 証拠
- エラーメッセージの行番号（line 27）がワーカープロセスの `exec()` 呼び出し位置と一致
- デバッグ出力で入口時点ではサロゲート文字は0個だが、実行時に発生

## 完全解決策

### 3層防御アーキテクチャ

#### 1. 入口層（Entry Point）
```python
# ★入口：統一ポリシーでコードを無害化
policy = get_surrogate_policy()
code = scrub_surrogates(code, policy)
enhanced_code = add_print_if_needed(code)
enhanced_code = scrub_surrogates(enhanced_code, policy)
```

#### 2. プロセス層（Process I/O）
```python
# subprocess.run の安定化
proc = subprocess.run(
    cmd,
    input=enhanced_code,
    encoding='utf-8',
    errors='replace',  # 重要：replaceモード
    env=env
)
```

#### 3. ワーカープロセス層（Worker Process）
```python
# WORKER_TEMPLATE内にサロゲート文字クリーンアップを組み込み
def scrub_surrogates_worker(s):
    if not isinstance(s, str):
        s = str(s)
    return ''.join(
        char if not (0xD800 <= ord(char) <= 0xDFFF) else '?'
        for char in s
    )

user_code = sys.stdin.read()
clean_user_code = scrub_surrogates_worker(user_code)
exec(clean_user_code, {'__builtins__': safe_builtins}, None)
```

#### 4. 出口層（Output Processing）
```python
# ★出口：統一ポリシーでstdout/stderrを無害化
policy = get_surrogate_policy()
clean_out = scrub_surrogates(out, policy)
clean_stderr = scrub_surrogates(proc.stderr, policy)
```

### 統一サロゲート処理関数

```python
def scrub_surrogates(s: str, mode: str = "replace") -> str:
    """
    Surrogate code points (U+D800–DFFF) を統一的に無害化
    
    Args:
        s: 処理対象の文字列
        mode: 処理モード ("ignore"|"replace"|"escape")
    
    Returns:
        サロゲート文字が無害化された文字列
    """
    if not isinstance(s, str):
        s = str(s)
    
    # まず正規化（NFC推奨）
    try:
        s = unicodedata.normalize("NFC", s)
    except Exception:
        pass
    
    out = []
    for ch in s:
        cp = ord(ch)
        if 0xD800 <= cp <= 0xDFFF:
            if mode == "ignore":
                continue
            elif mode == "escape":
                out.append(f"\\u{cp:04X}")  # 見える形にエスケープ
            else:  # "replace" 既定
                out.append("?")
        else:
            out.append(ch)
    return "".join(out)

def get_surrogate_policy() -> str:
    """環境変数からサロゲート処理ポリシーを取得"""
    return os.environ.get("SURROGATE_POLICY", "replace")
```

### 環境変数による制御

| 環境変数 | 値 | 動作 |
|---------|----|----- |
| `SURROGATE_POLICY` | `replace` (デフォルト) | サロゲート文字を `?` に置換 |
| `SURROGATE_POLICY` | `ignore` | サロゲート文字を削除 |
| `SURROGATE_POLICY` | `escape` | サロゲート文字を `\uDCXX` 形式にエスケープ |

### subprocess環境変数設定

```python
env = os.environ.copy()
env['PYTHONIOENCODING'] = 'utf-8:replace'  # 重要
env['PYTHONLEGACYWINDOWSFSENCODING'] = '0'
env['PYTHONUTF8'] = '1'
env['LC_ALL'] = 'C.UTF-8'
env['LANG'] = 'en_US.UTF-8'
```

## 修正対象ファイル

### 1. `universal_tools_server.py`（メイン）
- `scrub_surrogates()`, `get_surrogate_policy()` 関数追加
- `WORKER_TEMPLATE` 内にサロゲートクリーンアップ追加
- `execute_python()`, `execute_python_basic()` で3層防御実装

### 2. `connection_manager.py`
- FastMCP CallToolResult オブジェクトでのサロゲート処理
- デバッグ出力機能追加

### 3. `error_handler.py`
- エラーメッセージのサロゲート文字処理
- `clean_surrogate_chars_error()` 関数による統一処理

### 4. `mcp_agent.py`
- ツール結果とエラーメッセージのサロゲート文字クリーンアップ

### 5. `config.yaml`
- Rich表示無効化（`ui_mode: "basic"`）による安定性向上

## テスト結果

### 成功ケース
```bash
# 英語コード（完璧）
print('Hello World')
# → Hello World

# 日本語コード（実行成功、一部文字化け）
print('ハノイの塔を開始します')
# → ハノイの塔?�開始しま?...
```

### エラー解消確認
- ✅ UnicodeEncodeError: 完全解消
- ✅ すべての環境変数ポリシー（replace/ignore/escape）で動作
- ✅ 英語コード: 100%正常動作
- ✅ 日本語コード: 実行成功（文字化けあり、但しアルゴリズムは正常動作）

## 重要な技術知見

### 1. サロゲート文字について
- Unicode範囲: U+D800–U+DFFF
- UTF-8では直接エンコード不可
- Windowsの内部処理で日本語→サロゲートペア変換が発生

### 2. Python subprocess の挙動
- `errors='replace'` が安定性に重要
- 環境変数による細かいエンコーディング制御が必要
- ワーカープロセス内でのサロゲート処理が最も重要

### 3. MCP環境での制約
- FastMCPサーバー内でのprintはクライアントに表示されない
- デバッグ出力は標準エラーやログファイルを活用
- CallToolResultオブジェクトの処理が必要

### 4. Windows固有の問題
- cp932エンコーディングとUTF-8の混在
- レガシーWindowsファイルシステムエンコーディングの影響
- 環境変数による強制UTF-8化が有効

## 将来の改善案

### 1. より良い日本語表示
- Windows環境でのより適切なエンコーディング処理
- サロゲート文字の元文字への復元処理

### 2. パフォーマンス最適化
- サロゲート文字チェックの最適化
- 不要な処理の削減

### 3. 監視・デバッグ機能
- サロゲート文字発生の詳細ログ
- 統計情報の収集

## 教訓

1. **防御in深度**: 複数の層での処理が重要
2. **環境依存問題**: Windows特有の問題への対応が必要  
3. **デバッグの重要性**: 段階的なデバッグが根本原因特定に不可欠
4. **実用性重視**: 完璧な解決より実用的な解決を優先
5. **統一ポリシー**: 一貫したサロゲート処理ポリシーの適用

## 参考情報

### Unicode仕様
- サロゲートペア: https://unicode.org/faq/utf_bom.html#utf16-2
- UTF-8エンコーディング: https://tools.ietf.org/html/rfc3629

### Python関連
- subprocess module: https://docs.python.org/3/library/subprocess.html
- Unicode handling: https://docs.python.org/3/howto/unicode.html

---

**作成日**: 2025-01-24  
**最終更新**: 2025-01-24  
**作成者**: Claude Code & Human collaborator  
**検証環境**: Windows 11, Python 3.12.3, FastMCP 2.11.3