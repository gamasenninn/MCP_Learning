#!/usr/bin/env python3
"""
汎用MCPツール群 - Stage 1: Web検索 + ページ読取
"""

import os
import requests
from fastmcp import FastMCP
from typing import Dict, Any
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
mcp = FastMCP("Universal Tools Server")

TAVILY_API_KEY = os.getenv('TAVILY_API_KEY', '')

@mcp.tool()
def web_search(query: str, num_results: int = 3) -> Dict[str, Any]:
    """
    TavilyでWeb検索を実行
    """
    if not TAVILY_API_KEY:
        return {'success': False, 'error': 'APIキーが未設定です'}

    try:
        response = requests.post(
            'https://api.tavily.com/search',
            json={
                'api_key': TAVILY_API_KEY,
                'query': query,
                'max_results': num_results
            },
            timeout=10
        )
        data = response.json()

        # エラーチェック
        if 'error' in data:
            return {'success': False, 'error': data['error']}

        # 結果を簡潔に整形
        results = [{
            'title': r['title'],
            'url': r['url'],
            'snippet': r['content'][:400]
        } for r in data.get('results', [])]

        return {
            'success': True,
            'answer': data.get('answer', ''),  # AI生成の要約
            'results': results,
            'query': query
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}

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
    print(f"Tavily API: {'OK' if TAVILY_API_KEY else 'None'}")
    print("Stage 1: Web検索機能 + ページ読取")
    mcp.run()