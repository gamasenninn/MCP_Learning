#!/usr/bin/env python3
"""
database_server.pyを異なるディレクトリから起動してテスト
"""

import asyncio
import os
from pathlib import Path
from fastmcp import Client

async def test_from_different_dirs():
    """異なるディレクトリからdatabase_server.pyを起動"""
    
    server_path = r"C:\MCP_Learning\chapter06\database_server.py"
    
    # 1. chapter09から起動（現在のディレクトリ）
    print("=== Test 1: chapter09から起動 ===")
    print(f"現在のディレクトリ: {os.getcwd()}")
    
    try:
        client = Client(server_path)
        async with client:
            await client.ping()
            print("✅ 接続成功")
            
            # list_tablesを実行
            result = await client.call_tool("list_tables", {})
            print(f"📋 テーブル数: {len(result.data) if hasattr(result, 'data') else 'unknown'}")
            
    except Exception as e:
        print(f"❌ エラー: {e}")
    
    print()
    
    # 2. 一時的にchapter06に移動して起動
    print("=== Test 2: chapter06に移動して起動 ===")
    original_dir = os.getcwd()
    os.chdir(r"C:\MCP_Learning\chapter06")
    print(f"現在のディレクトリ: {os.getcwd()}")
    
    try:
        client = Client("database_server.py")  # 相対パスで指定
        async with client:
            await client.ping()
            print("✅ 接続成功")
            
            # list_tablesを実行
            result = await client.call_tool("list_tables", {})
            print(f"📋 テーブル数: {len(result.data) if hasattr(result, 'data') else 'unknown'}")
            
    except Exception as e:
        print(f"❌ エラー: {e}")
    finally:
        os.chdir(original_dir)  # 元のディレクトリに戻る
    
    print()
    
    # 3. ルートディレクトリから起動
    print("=== Test 3: C:\\MCP_Learningから起動 ===")
    os.chdir(r"C:\MCP_Learning")
    print(f"現在のディレクトリ: {os.getcwd()}")
    
    try:
        client = Client(r"chapter06\database_server.py")  # 相対パスで指定
        async with client:
            await client.ping()
            print("✅ 接続成功")
            
            # list_tablesを実行
            result = await client.call_tool("list_tables", {})
            print(f"📋 テーブル数: {len(result.data) if hasattr(result, 'data') else 'unknown'}")
            
    except Exception as e:
        print(f"❌ エラー: {e}")
    finally:
        os.chdir(original_dir)  # 元のディレクトリに戻る

if __name__ == "__main__":
    print("database_server.pyのパス依存問題テスト")
    print("=" * 50)
    asyncio.run(test_from_different_dirs())
    print("\n✅ テスト完了")