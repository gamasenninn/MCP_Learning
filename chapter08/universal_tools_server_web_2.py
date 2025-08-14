#!/usr/bin/env python3
"""
汎用MCPツール群 - Stage 1: Web検索 + ページ読取
"""

from fastmcp import FastMCP
import requests
from typing import Dict, Any
from bs4 import BeautifulSoup

mcp = FastMCP("Universal Tools Server")

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

if __name__ == "__main__":
    print("Stage 1: Web検索機能 + ページ読取")
    mcp.run()