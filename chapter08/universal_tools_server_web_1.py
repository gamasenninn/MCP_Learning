#!/usr/bin/env python3
"""
汎用MCPツール群 - Stage 1: Web検索（Tavily簡潔版）
"""
import os
import requests
from fastmcp import FastMCP
from typing import Dict, Any
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

if __name__ == "__main__":
    print(f"Tavily API: {'OK' if TAVILY_API_KEY else 'None'}")
    mcp.run()