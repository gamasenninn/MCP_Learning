#!/usr/bin/env python3
"""
Step B: スキーマ取得ツールを追加
"""

import sqlite3
from typing import List, Dict, Any, Optional
from fastmcp import FastMCP

# MCPサーバーを作成
mcp = FastMCP("Database Server - Schema Edition")

# データベースのパス
DB_PATH = 'intelligent_shop.db'

def get_db_connection():
    """データベースに安全に接続する関数"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")  # 外部キー制約を有効化
    conn.row_factory = sqlite3.Row  # 列名でアクセス可能にする
    return conn

# 🔧 ツール1: テーブル一覧を取得（前回と同じ）
@mcp.tool()
def list_tables() -> List[Dict[str, Any]]:
    """データベース内のすべてのテーブルを一覧表示
    
    Returns:
        テーブル名とその説明のリスト
    """
    print("[検索] データベースからテーブル一覧を取得中...")
    
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
    
    print(f"[完了] {len(tables)}個のテーブルを発見しました")
    return tables

# 🆕 ツール2: テーブルの詳細構造を取得（新機能！）
@mcp.tool()
def get_table_schema(table_name: str) -> Dict[str, Any]:
    """指定したテーブルの詳細なスキーマ情報を取得
    
    Args:
        table_name: 調べたいテーブル名
    
    Returns:
        テーブルのスキーマ情報（列、型、制約、サンプルデータなど）
    """
    print(f"[分析] テーブル '{table_name}' のスキーマを分析中...")
    
    conn = get_db_connection()
    
    # 1. テーブルの存在確認
    cursor = conn.execute('''
    SELECT name FROM sqlite_master 
    WHERE type='table' AND name=?
    ''', (table_name,))
    
    if not cursor.fetchone():
        conn.close()
        raise ValueError(f"テーブル '{table_name}' は存在しません")
    
    # 2. 列情報を取得
    print(f"  [列情報] 列情報を取得中...")
    cursor = conn.execute(f'PRAGMA table_info({table_name})')
    columns = []
    
    for row in cursor.fetchall():
        columns.append({
            "name": row[1],
            "type": row[2],
            "not_null": bool(row[3]),
            "default_value": row[4],
            "is_primary_key": bool(row[5])
        })
    
    # 3. 外部キー制約を取得
    print(f"  [外部キー] 外部キー制約を確認中...")
    cursor = conn.execute(f'PRAGMA foreign_key_list({table_name})')
    foreign_keys = []
    
    for row in cursor.fetchall():
        foreign_keys.append({
            "column": row[3],
            "references_table": row[2],
            "references_column": row[4]
        })
    
    # 4. サンプルデータを取得（最大5件）
    print(f"  [サンプル] サンプルデータを取得中...")
    cursor = conn.execute(f'SELECT * FROM {table_name} LIMIT 5')
    sample_data = [dict(row) for row in cursor.fetchall()]
    
    # 5. レコード数を取得
    cursor = conn.execute(f'SELECT COUNT(*) as count FROM {table_name}')
    record_count = cursor.fetchone()["count"]
    
    conn.close()
    
    schema_info = {
        "table_name": table_name,
        "columns": columns,
        "foreign_keys": foreign_keys,
        "record_count": record_count,
        "sample_data": sample_data
    }
    
    print(f"[完了] スキーマ分析完了: {len(columns)}列、{record_count}レコード")
    return schema_info

# サーバー起動
if __name__ == "__main__":
    print("[起動] MCPサーバー（Step B版）を起動します...")
    print("[ツール] 利用可能なツール: list_tables, get_table_schema")
    mcp.run()