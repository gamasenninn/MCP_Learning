#!/usr/bin/env python3
"""
汎用MCPツール群 - Stage 1: Web機能 + Stage 2: コード実行（レベル4：完全サンドボックス）
"""

from fastmcp import FastMCP
import requests
from typing import Dict, Any, Tuple
from bs4 import BeautifulSoup
import subprocess
import sys
import tempfile
import os
import ast
from string import Template

mcp = FastMCP("Universal Tools Server")

# === Stage 1: Web機能 ===

@mcp.tool()
def web_search(query: str, num_results: int = 3) -> Dict[str, Any]:
    """ウェブ検索を実行して関連情報を取得します（Bing使用、APIキー不要）。
    
    情報収集、ファクトチェック、最新情報の確認、関連リンクの取得に使用。
    例：「Pythonの最新バージョン」「MCPの公式ドキュメント」
    
    Args:
        query: 検索クエリ（日本語/英語対応）
        num_results: 取得件数（デフォルト3件）
    
    Returns:
        タイトル、URL、スニペットを含む検索結果のリスト
    """
    try:
        # 検索リクエスト
        response = requests.get(
            "https://www.bing.com/search",
            params={'q': query, 'cc': 'JP'},
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept-Language': 'ja,en;q=0.9'
            },
            timeout=10
        )
        response.raise_for_status()
        
        # HTML解析
        soup = BeautifulSoup(response.text, 'html.parser')
        results = []
        
        # 検索結果を抽出
        for li in soup.find_all('li', class_='b_algo'):
            if len(results) >= num_results:
                break
                
            h2 = li.find('h2')
            if not h2:
                continue
                
            link = h2.find('a', href=True)
            if not link:
                continue
            
            # スニペット取得
            snippet = ''
            caption = li.find('div', class_='b_caption')
            if caption:
                p = caption.find('p')
                if p:
                    snippet = p.get_text(strip=True)
            
            results.append({
                'position': len(results) + 1,
                'title': link.get_text(strip=True),
                'url': link.get('href', ''),
                'snippet': snippet
            })
        
        # 結果を整形
        formatted = '\n\n'.join([
            f"[{r['position']}] {r['title']}\n"
            f"    URL: {r['url']}\n"
            f"    {r['snippet'][:100]}{'...' if len(r['snippet']) > 100 else ''}"
            for r in results
        ]) if results else f'「{query}」の検索結果が見つかりませんでした'
        
        return {
            'success': True,
            'query': query,
            'results_count': len(results),
            'results': results,
            'formatted': formatted
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'query': query
        }

@mcp.tool()
def get_webpage_content(url: str) -> Dict[str, Any]:
    """指定されたURLのウェブページ内容をテキスト形式で取得します。
    
    記事の読み込み、ドキュメント参照、コンテンツ分析などに使用。
    HTMLタグ、JavaScript、CSSを除去して純粋なテキストを抽出。
    例：「このURLの内容を読んで」「ブログ記事を要約して」
    
    Args:
        url: 取得したいウェブページのURL
    
    Returns:
        タイトル、コンテンツ（最大2000文字）を含む辞書
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # なぜスクリプトとスタイルを除去するのか：
        # - <script>: JavaScriptコード（表示されない）
        # - <style>: CSSスタイル（表示されない）
        # これらは見た目の制御用で、内容理解には不要
        for script in soup(['script', 'style']):
            script.decompose()  # 要素を完全に削除
        
        # get_textメソッド：すべてのHTMLタグを除去してテキストだけ取得
        text = soup.get_text()
        
        # テキストのクリーニング処理
        # なぜ必要？HTMLから抽出したテキストは改行や空白が多い
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return {
            'success': True,
            'url': url,
            'title': soup.title.string if soup.title else '',  # <title>タグの内容
            'content': text[:2000],  # 最初の2000文字だけ（長すぎる場合の対策）
            'truncated': len(text) > 2000
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': f'取得エラー: {str(e)}'
        }

# === Stage 2: コード実行（レベル4：完全サンドボックス） ===

# セキュリティ設定
OUTPUT_LIMIT = 200_000      # 出力上限 200KB
TIMEOUT_SEC = 3.0           # タイムアウト 3秒
MEMORY_LIMIT_MB = 256       # メモリ上限 256MB（Unix系のみ）
CPU_LIMIT_SEC = 2           # CPU時間上限 2秒（Unix系のみ）

# 許可する安全なモジュールのみ
ALLOWED_MODULES = {
    'math', 'random', 'datetime', 'collections', 
    'itertools', 're', 'json', 'time'
}

# 禁止する危険な関数
FORBIDDEN_FUNCTIONS = {
    'eval',      # 文字列をコードとして実行（危険）
    'exec',      # 同上
    'open',      # ファイルを開く（情報漏洩リスク）
    '__import__',# モジュールを動的にインポート
    'compile',   # コードをコンパイル
    'input',     # ユーザー入力（永遠に待つ可能性）
}

# 危険な属性（Pythonの内部機構へのアクセス）
FORBIDDEN_ATTRS = {
    '__subclasses__',  # クラス階層を辿って危険なクラスを見つける
    '__globals__',     # グローバル変数へアクセス
    '__dict__',        # オブジェクトの内部辞書
    '__code__',        # 関数のバイトコード
    '__builtins__',    # 組み込み関数へのアクセス
    '__mro__', '__bases__', '__class__',
    '__getattribute__', '__closure__',
    '__loader__', '__package__'
}

# 安全な組み込み関数のみ許可
SAFE_BUILTIN_NAMES = [
    'print', 'len', 'range', 'str', 'int', 'float', 'bool',
    'list', 'dict', 'tuple', 'set', 'sum', 'min', 'max', 
    'abs', 'round', 'divmod', 'all', 'any', 'zip', 'enumerate'
]

def add_print_if_needed(code: str) -> str:
    """
    必要に応じてprint()を自動追加する関数
    
    1. 既にprint()がある場合 → そのまま
    2. 最後の行が式（expression）の場合 → print()でラップ
    3. 最後の行が代入の場合 → その変数をprint()
    4. その他の場合 → そのまま
    """
    try:
        # コードをASTで解析
        tree = ast.parse(code.strip())
        if not tree.body:
            return code
        
        # 既にprint()が含まれているかチェック
        code_lower = code.lower()
        if 'print(' in code_lower:
            return code
        
        last_stmt = tree.body[-1]
        
        # 最後の文が式（Expr）の場合 → print()でラップ
        if isinstance(last_stmt, ast.Expr):
            # 最後の行を取得
            lines = code.strip().split('\n')
            last_line = lines[-1].strip()
            
            # print()でラップ
            lines[-1] = f"print({last_line})"
            return '\n'.join(lines)
        
        # 最後の文が代入（Assign）の場合 → 代入された変数をprint()
        elif isinstance(last_stmt, ast.Assign):
            # 代入されたターゲットを取得
            if last_stmt.targets and isinstance(last_stmt.targets[0], ast.Name):
                var_name = last_stmt.targets[0].id
                return code + f"\nprint({var_name})"
        
        # その他（if、for、def など）の場合 → そのまま
        return code
        
    except (SyntaxError, ValueError):
        # パースエラーの場合はそのまま返す
        return code

def check_code_safety(code: str) -> Tuple[bool, str]:
    """
    コードの安全性をチェック
    
    ASTとは？
    - Abstract Syntax Tree（抽象構文木）の略
    - Pythonコードを木構造で表現したもの
    - 実行せずにコードの構造を解析できる
    
    例：
    code = "print(1 + 2)"
    →
    Module
      └─ Expr
          └─ Call (関数呼び出し)
              ├─ Name: 'print'
              └─ BinOp: 1 + 2
    """
    try:
        # コードをASTに変換（実行はしない）
        tree = ast.parse(code)
        
        # ASTのすべてのノード（要素）を調べる
        for node in ast.walk(tree):
            # インポートのチェック（許可リスト方式）
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name.split('.')[0]
                        if module_name not in ALLOWED_MODULES:
                            return False, f"許可されていないモジュール: {alias.name}"
                else:
                    module_name = (node.module or '').split('.')[0]
                    if module_name not in ALLOWED_MODULES:
                        return False, f"許可されていないモジュール: {node.module}"
            
            # 危険な属性アクセスのチェック
            elif isinstance(node, ast.Attribute):
                if node.attr in FORBIDDEN_ATTRS:
                    return False, f"危険な属性アクセス: {node.attr}"
            
            # 危険な関数呼び出しのチェック
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in FORBIDDEN_FUNCTIONS:
                        return False, f"禁止された関数: {node.func.id}"
            
            # クラス定義の禁止（メタクラス攻撃を防ぐ）
            elif isinstance(node, ast.ClassDef):
                return False, "クラス定義は許可されていません"
        
        return True, "安全です"
        
    except SyntaxError as e:
        # そもそも正しいPythonコードではない
        return False, f"構文エラー: {str(e)}"

# ワーカーテンプレート（簡易版）
WORKER_TEMPLATE_SIMPLE = Template(r"""
import sys, builtins

# 安全な環境を構築
ALLOWED_MODULES = set($ALLOWED_MODULES)
SAFE_BUILTINS = {name: getattr(builtins, name) for name in $SAFE_BUILTIN_NAMES}

def safe_import(name, *args, **kwargs):
    if name.split('.')[0] not in ALLOWED_MODULES:
        raise ImportError(f"モジュール '{name}' は許可されていません")
    return __import__(name, *args, **kwargs)

# ユーザーコードを実行
safe_builtins = dict(SAFE_BUILTINS)
safe_builtins['__import__'] = safe_import
exec(sys.stdin.read(), {'__builtins__': safe_builtins}, None)
""")

# ワーカープロセスのテンプレート（完全版）
WORKER_TEMPLATE = Template(r"""
import sys, builtins, os

# リソース制限（Unix系のみ）
try:
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, ($CPU, $CPU))
    resource.setrlimit(resource.RLIMIT_AS, ($MEM, $MEM))
    resource.setrlimit(resource.RLIMIT_NOFILE, (3, 3))  # stdin/stdout/stderrのみ
    resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))   # 子プロセス生成禁止
except:
    pass  # Windowsでは無視

# 安全な環境を構築
ALLOWED_MODULES = set($ALLOWED_MODULES)
SAFE_BUILTINS = {name: getattr(builtins, name) 
                 for name in $SAFE_BUILTIN_NAMES}

def safe_import(name, *args, **kwargs):
    if name.split('.')[0] not in ALLOWED_MODULES:
        raise ImportError(f"モジュール '{name}' は許可されていません")
    return __import__(name, *args, **kwargs)

# ユーザーコードを実行
safe_builtins = dict(SAFE_BUILTINS)
safe_builtins['__import__'] = safe_import
exec(sys.stdin.read(), {'__builtins__': safe_builtins}, None)
""")

@mcp.tool()
def execute_python(code: str) -> str:
    """最高セキュリティのPythonコード実行（レベル4：完全サンドボックス）。
    
    信頼できないコードの実行、セキュリティ検証、教育目的のコード実行に使用。
    AST検査、プロセス隔離、リソース制限（CPU 2秒、メモリ256MB）付き。
    
    【重要】結果を見るには必ずprint()を使用してください！
    - 計算結果: result = 計算; print(result)
    - 変数の値: x = 42; print(x)
    - 複数の値: print(a, b, c)
    
    例：
    - result = sum(range(100)); print(result)
    - primes = [x for x in range(2, 20) if all(x % y for y in range(2, x))]; print(primes)
    
    Returns:
        実行結果またはエラーメッセージ（文字列）
    """
    # 自動print()追加
    enhanced_code = add_print_if_needed(code)
    
    # 1. 静的解析でコードをチェック
    is_safe, msg = check_code_safety(enhanced_code)
    if not is_safe:
        return f"セキュリティエラー: {msg}"
    
    # 2. ワーカープロセスを生成
    with tempfile.TemporaryDirectory() as tmpdir:
        worker_code = WORKER_TEMPLATE.substitute(
            ALLOWED_MODULES=repr(sorted(ALLOWED_MODULES)),
            SAFE_BUILTIN_NAMES=repr(SAFE_BUILTIN_NAMES),
            CPU=CPU_LIMIT_SEC,
            MEM=MEMORY_LIMIT_MB * 1024 * 1024
        )
        
        # 3. 隔離された環境で実行
        # 環境変数でPythonのエンコーディングを指定（日本語対応）
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        cmd = [sys.executable, "-I", "-S", "-B", "-c", worker_code]
        try:
            # 入力コードをクリーンアップ（サロゲート文字を除去）
            import codecs
            clean_code = codecs.decode(codecs.encode(enhanced_code, 'utf-8', 'surrogateescape'), 'utf-8', 'replace')
            
            proc = subprocess.run(
                cmd,
                input=clean_code,
                text=True,
                capture_output=True,
                cwd=tmpdir,  # 一時ディレクトリに制限
                timeout=TIMEOUT_SEC,
                encoding='utf-8',
                errors='replace',  # エンコードできない文字を?に置換
                env=env
            )
            
            # 4. 出力サイズ制限
            out = proc.stdout[:OUTPUT_LIMIT]
            if len(proc.stdout) > OUTPUT_LIMIT:
                out += "\n... [出力が切り詰められました]"
            
            if proc.returncode == 0:
                if out.strip():
                    return f"成功:\n{out}"
                else:
                    return "成功:\n（出力なし）\nヒント: 結果を表示するには print() を使用してください。例: print(result)"
            else:
                return f"実行エラー:\n{proc.stderr}"
                
        except subprocess.TimeoutExpired:
            return f"タイムアウト（{TIMEOUT_SEC}秒）"

@mcp.tool()
def execute_python_basic(code: str) -> Dict[str, Any]:
    """基本的なPythonコード実行（セキュリティレベル2）。
    
    シンプルな計算、データ処理、スクリプト実行に使用。
    別プロセスで実行するためメイン環境は保護される。
    セキュリティチェックなしのため、信頼できるコードのみ実行推奨。
    
    【重要】結果を見るには必ずprint()を使用してください！
    - 単純な計算: print(1 + 1)
    - 変数の表示: name = 'Hello'; print(name)
    - 複雑な処理: result = 処理; print(result)
    
    例：
    - print(1 + 1)  # → 2
    - nums = [1, 2, 3]; print(sum(nums))  # → 6
    
    Returns:
        成功フラグ、標準出力、エラー出力を含む辞書
    """
    # 自動print()追加
    enhanced_code = add_print_if_needed(code)
    
    try:
        # 環境変数でPythonのエンコーディングを指定（日本語対応）
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        # 標準入力経由でコードを実行
        # なぜこの方法？
        # - ファイルI/Oのオーバーヘッドがない
        # - ウイルス対策ソフトの干渉を受けにくい
        # - より高速で安定
        # 入力コードをクリーンアップ（サロゲート文字を除去）
        import codecs
        clean_code = codecs.decode(codecs.encode(enhanced_code, 'utf-8', 'surrogateescape'), 'utf-8', 'replace')
        
        result = subprocess.run(
            [sys.executable, "-c", "import sys; exec(sys.stdin.read())"],
            input=clean_code,       # クリーンアップされたコードを標準入力として渡す
            capture_output=True,     # 出力をキャプチャ
            text=True,              # テキストとして扱う
            timeout=5,              # 5秒でタイムアウト
            encoding='utf-8',       # UTF-8エンコーディング
            errors='replace',       # エンコードできない文字を?に置換
            env=env                 # 環境変数を渡す
        )
        
        stdout = result.stdout.strip()
        if result.returncode == 0 and not stdout:
            # 成功したが出力がない場合の警告
            stdout = "（出力なし）\nヒント: 結果を表示するには print() を使用してください。例: print(result)"
        
        return {
            'success': result.returncode == 0,  # 0は成功を意味する
            'stdout': stdout,                   # 標準出力（print文の結果）
            'stderr': result.stderr             # エラー出力
        }
        
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': 'タイムアウト（5秒）'
        }

if __name__ == "__main__":
    print("汎用MCPツールサーバー（完全サンドボックス版）")
    print("=" * 50)
    print("Stage 1: Web機能")
    print("  - web_search: Web検索")
    print("  - get_webpage_content: ページ内容取得")
    print()
    print("Stage 2: コード実行")
    print("  - execute_python_basic: 子プロセスで実行（レベル2）")
    print("  - execute_python: AST検査付き実行（レベル3）")
    print("  - execute_python_secure: 完全サンドボックス実行（レベル4）")
    print()
    print("セキュリティレイヤー（レベル4）:")
    print("  1. 静的コード分析（AST）")
    print("  2. プロセス隔離（-I -S -B）")
    print("  3. リソース制限（Unix系）")
    print("     - CPU時間: 2秒")
    print("     - メモリ: 256MB")
    print("     - ファイルディスクリプタ: 3")
    print("  4. 実行環境制限")
    print("     - 許可モジュール: " + ", ".join(sorted(ALLOWED_MODULES)))
    print("     - 安全な組み込み関数のみ")
    print("=" * 50)
    mcp.run()