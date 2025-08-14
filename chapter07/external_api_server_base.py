#!/usr/bin/env python3
"""
外部API連携MCPサーバー
external_api_server_base.py
"""

import os
import requests
import json
from datetime import datetime, timedelta
from typing import Optional
from fastmcp import FastMCP
from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv()

# MCPサーバーを作成
mcp = FastMCP("External API Server")

# APIキーを取得
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

def make_api_request(url: str, params: dict = None, headers: dict = None) -> dict:
    """安全なAPI リクエスト実行"""
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()  # HTTPエラーがあれば例外を発生
        return response.json()
    except requests.exceptions.Timeout:
        raise Exception("APIリクエストがタイムアウトしました")
    except requests.exceptions.HTTPError as e:
        raise Exception(f"APIリクエストエラー: {e}")
    except requests.exceptions.RequestException as e:
        raise Exception(f"ネットワークエラー: {e}")

# ここに今後、各API機能を追加していきます
# 注意: Windows環境でのエンコーディングエラーを防ぐため、print文で絵文字を使用していません

if __name__ == "__main__":
    print("[*] 外部API連携サーバー起動中...")
    print("設定されたAPIキー:")
    print(f"  OpenWeather: {'OK' if OPENWEATHER_API_KEY else 'NG'}")
    print(f"  NewsAPI: {'OK' if NEWS_API_KEY else 'NG'}")
    print()
    print("[!] 実行方法:")
    print("  uvを使用: uv run python external_api_server.py")
    print("  従来方法: python external_api_server.py")
    mcp.run()