#!/usr/bin/env python3
"""
外部API連携MCPサーバー
external_api_server_news.py
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

# 天気API機能
@mcp.tool()
def get_weather(city: str, country_code: str = "JP") -> dict:
    """指定した都市の現在の天気を取得します
    
    Args:
        city: 都市名（例: Tokyo, Osaka）
        country_code: 国コード（デフォルト: JP）
    """
    if not OPENWEATHER_API_KEY:
        raise ValueError("OpenWeatherMap APIキーが設定されていません")
    
    # HTTPSを使用（セキュリティ改善）
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": f"{city},{country_code}",
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",  # 摂氏温度
        "lang": "ja"        # 日本語
    }
    
    data = make_api_request(url, params)
    
    return {
        "city": data["name"],
        "country": data["sys"]["country"],
        "temperature": data["main"]["temp"],
        "feels_like": data["main"]["feels_like"],
        "humidity": data["main"]["humidity"],
        "pressure": data["main"]["pressure"],
        "weather_main": data["weather"][0]["main"],
        "weather_description": data["weather"][0]["description"],
        "wind_speed": data["wind"]["speed"],
        "visibility": data.get("visibility", 0) / 1000,  # kmに変換
        "timestamp": datetime.now().isoformat()
    }

@mcp.tool()
def get_weather_forecast(city: str, days: int = 5, country_code: str = "JP") -> dict:
    """指定した都市の天気予報を取得します
    
    Args:
        city: 都市名
        days: 予報日数（1-5日）
        country_code: 国コード（デフォルト: JP）
    """
    if not OPENWEATHER_API_KEY:
        raise ValueError("OpenWeatherMap APIキーが設定されていません")
    
    if days < 1 or days > 5:
        raise ValueError("予報日数は1-5日の範囲で指定してください")
    
    # HTTPSを使用（セキュリティ改善）
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "q": f"{city},{country_code}",
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
        "lang": "ja"
    }
    
    data = make_api_request(url, params)
    
    # 日別にデータを整理
    daily_forecasts = []
    current_date = None
    daily_data = []
    
    for item in data["list"][:days * 8]:  # 3時間毎データなので8個/日
        forecast_date = datetime.fromtimestamp(item["dt"]).date()
        
        if current_date != forecast_date:
            if daily_data:  # 前日のデータがあれば追加
                daily_forecasts.append({
                    "date": current_date.isoformat(),
                    "forecasts": daily_data
                })
            current_date = forecast_date
            daily_data = []
        
        daily_data.append({
            "time": datetime.fromtimestamp(item["dt"]).strftime("%H:%M"),
            "temperature": item["main"]["temp"],
            "weather": item["weather"][0]["description"],
            "rain_probability": item.get("pop", 0) * 100  # 降水確率
        })
    
    # 最後の日を追加
    if daily_data:
        daily_forecasts.append({
            "date": current_date.isoformat(),
            "forecasts": daily_data
        })
    
    return {
        "city": data["city"]["name"],
        "country": data["city"]["country"],
        "daily_forecasts": daily_forecasts[:days]
    }

# ニュースAPI機能を追加
@mcp.tool()
def get_latest_news(category: str = "general", country: str = "us", limit: int = 5) -> dict:
    """最新ニュースを取得します
    
    Args:
        category: ニュースカテゴリ（general, business, technology, science, health, sports, entertainment）
        country: 国コード（jp, us, uk等）
        limit: 取得件数（最大20）
    """
    if not NEWS_API_KEY:
        raise ValueError("NewsAPI APIキーが設定されていません")
    
    if limit > 20:
        limit = 20
    
    url = "https://newsapi.org/v2/top-headlines"
    params = {
        "apiKey": NEWS_API_KEY,
        "category": category,
        "country": country,
        "pageSize": limit
    }
    
    data = make_api_request(url, params)
    
    articles = []
    for article in data["articles"]:
        articles.append({
            "title": article["title"],
            "description": article["description"],
            "url": article["url"],
            "source": article["source"]["name"],
            "published_at": article["publishedAt"],
            "author": article.get("author", "不明")
        })
    
    return {
        "category": category,
        "country": country,
        "total_results": data["totalResults"],
        "articles": articles,
        "fetched_at": datetime.now().isoformat()
    }

@mcp.tool()
def search_news(query: str, language: str = "en", limit: int = 5) -> dict:
    """キーワードでニュースを検索します
    
    Args:
        query: 検索キーワード
        language: 言語コード（ja, en等）
        limit: 取得件数（最大20）
    """
    if not NEWS_API_KEY:
        raise ValueError("NewsAPI APIキーが設定されていません")
    
    if limit > 20:
        limit = 20
    
    url = "https://newsapi.org/v2/everything"
    params = {
        "apiKey": NEWS_API_KEY,
        "q": query,
        "language": language,
        "sortBy": "publishedAt",
        "pageSize": limit
    }
    
    data = make_api_request(url, params)
    
    articles = []
    for article in data["articles"]:
        articles.append({
            "title": article["title"],
            "description": article["description"],
            "url": article["url"],
            "source": article["source"]["name"],
            "published_at": article["publishedAt"]
        })
    
    return {
        "query": query,
        "language": language,
        "total_results": data["totalResults"],
        "articles": articles,
        "fetched_at": datetime.now().isoformat()
    }

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