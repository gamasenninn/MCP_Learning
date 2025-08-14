#!/usr/bin/env python3
"""
汎用MCPツール群 - Stage 1: Web機能 + Stage 2: コード実行（レベル2）
"""

from fastmcp import FastMCP
import requests
from typing import Dict, Any
from bs4 import BeautifulSoup
import subprocess
import sys
import tempfile
import os

mcp = FastMCP("Universal Tools Server")

# === Stage 1: Web機能 ===

@mcp.tool()
def web_search(query: str, num_results: int = 3) -> Dict[str, Any]:
    """
    シンプルなWeb検索（Bing使用）
    
    Bingを使う理由：
    - APIキーが不要（無料）
    - 安定したHTML構造
    - 日本語検索に対応
    - 高品質な検索結果
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
    """
    Webページの内容を取得（テキストのみ）
    
    なぜテキストだけ？
    - AIが理解しやすい
    - データ量が少ない
    - 処理が高速
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

# === Stage 2: コード実行（レベル2） ===

@mcp.tool()
def execute_python_basic(code: str) -> Dict[str, Any]:
    """
    Pythonコードを実行（基本版）
    
    subprocess.runの仕組み：
    1. 新しいプロセス（別のプログラム）を起動
    2. そこでPythonコードを実行
    3. 結果を受け取る
    
    なぜ別プロセス？
    - メインプログラムから隔離される
    - エラーが起きてもメインは影響を受けない
    
    改善点：
    - 標準入力経由でコードを渡す（ファイル作成不要）
    - Windows環境でのタイムアウト問題を解決
    - 日本語対応
    """
    try:
        # 環境変数でPythonのエンコーディングを指定（日本語対応）
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        # 標準入力経由でコードを実行
        # なぜこの方法？
        # - ファイルI/Oのオーバーヘッドがない
        # - ウイルス対策ソフトの干渉を受けにくい
        # - より高速で安定
        result = subprocess.run(
            [sys.executable, "-c", "import sys; exec(sys.stdin.read())"],
            input=code,              # コードを標準入力として渡す
            capture_output=True,     # 出力をキャプチャ
            text=True,              # テキストとして扱う
            timeout=5,              # 5秒でタイムアウト
            encoding='utf-8',       # UTF-8エンコーディング
            env=env                 # 環境変数を渡す
        )
        
        return {
            'success': result.returncode == 0,  # 0は成功を意味する
            'stdout': result.stdout,            # 標準出力（print文の結果）
            'stderr': result.stderr             # エラー出力
        }
        
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': 'タイムアウト（5秒）'
        }

if __name__ == "__main__":
    print("汎用MCPツールサーバー")
    print("=" * 50)
    print("Stage 1: Web機能")
    print("  - web_search: Web検索")
    print("  - get_webpage_content: ページ内容取得")
    print()
    print("Stage 2: コード実行（レベル2：基本的な隔離）")
    print("  - execute_python_basic: 子プロセスで実行")
    print("=" * 50)
    mcp.run()