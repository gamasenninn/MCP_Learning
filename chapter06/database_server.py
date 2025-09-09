#!/usr/bin/env python3
"""
Database Server 完全版ソース
"""

import sqlite3
import re
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastmcp import FastMCP

# MCPサーバーを作成
mcp = FastMCP("Database Server - Prompt Edition")

# データベースのパス（スクリプトと同じディレクトリのDBファイルを参照）
DB_PATH = os.path.join(os.path.dirname(__file__), 'intelligent_shop.db')

def get_db_connection():
    """データベースに安全に接続する関数"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

def validate_sql_safety(sql: str) -> bool:
    """SQLクエリの安全性をチェック"""
    sql_upper = sql.upper().strip()
    
    if not sql_upper.startswith('SELECT'):
        return False
    
    dangerous_keywords = [
        'DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 
        'CREATE', 'TRUNCATE', 'REPLACE', 'PRAGMA',
        'ATTACH', 'DETACH', 'VACUUM'
    ]
    
    for keyword in dangerous_keywords:
        if keyword in sql_upper:
            return False
    
    dangerous_patterns = [
        r';\s*(DROP|DELETE|INSERT|UPDATE)',
        r'--',
        r'/\*.*\*/',
        r'UNION.*SELECT',
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, sql_upper):
            return False
    
    return True

# 既存のツール（前回と同じ）
@mcp.tool()
def list_tables() -> List[Dict[str, Any]]:
    """データベース内のすべてのテーブルとスキーマ情報を一覧表示。
    
    テーブル構造の把握、データベース全体の理解、クエリ作成の準備に使用。
    各テーブルのCREATE文も含むJSON形式で返却。
    例：「どんなテーブルがある？」「データベースの構造を教えて」
    """
    conn = get_db_connection()
    cursor = conn.execute('''
    SELECT name, sql 
    FROM sqlite_master 
    WHERE type='table' AND name NOT LIKE 'sqlite_%'
    ORDER BY name
    ''')
    
    tables = []
    for row in cursor.fetchall():
        tables.append({
            "table_name": row["name"],
            "creation_sql": row["sql"]
        })
    
    conn.close()
    return tables

@mcp.tool()
def execute_safe_query(sql: str) -> Dict[str, Any]:
    """SELECTクエリのみを安全に実行。データの検索、集計、分析に使用。
    
    INSERT/UPDATE/DELETE/DROPなどの破壊的操作は禁止。
    JOIN、GROUP BY、ORDER BY、WHERE句などはOK。
    結果はJSON形式でカラム名、データ、実行時刻を含む。
    
    重要：まずlist_tablesでテーブル構造を確認してからSQLを作成すること。
    例：「売上合計を計算」→salesテーブルを使用、「商品一覧」→productsテーブルを使用
    """
    if not validate_sql_safety(sql):
        raise ValueError("安全でないSQL文です。SELECT文のみ実行可能です。")
    
    conn = get_db_connection()
    
    try:
        cursor = conn.execute(sql)
        results = [dict(row) for row in cursor.fetchall()]
        column_names = [description[0] for description in cursor.description] if cursor.description else []
        
        query_result = {
            "sql": sql,
            "results": results,
            "column_names": column_names,
            "row_count": len(results),
            "executed_at": datetime.now().isoformat()
        }
        
        conn.close()
        return query_result
        
    except sqlite3.Error as e:
        conn.close()
        raise ValueError(f"SQLエラー: {str(e)}")

# サーバー起動
if __name__ == "__main__":
    print("[起動] MCPサーバー（プロンプト機能付き完全版）を起動します...")
    print("[ツール] 利用可能なツール: list_tables, execute_safe_query")
    mcp.run()