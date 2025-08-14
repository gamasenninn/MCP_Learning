#!/usr/bin/env python3
"""
Step C: 安全なクエリ実行機能を追加
"""

import sqlite3
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastmcp import FastMCP

# MCPサーバーを作成
mcp = FastMCP("Database Server - Safe Query Edition")

# データベースのパス
DB_PATH = 'intelligent_shop.db'

def get_db_connection():
    """データベースに安全に接続する関数"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")  # 外部キー制約を有効化
    conn.row_factory = sqlite3.Row  # 列名でアクセス可能にする
    return conn

# 🛡️ セキュリティ機能：SQLの安全性をチェック
def validate_sql_safety(sql: str) -> bool:
    """多層防御でSQLクエリの安全性をチェック
    
    Args:
        sql: チェックするSQLクエリ
        
    Returns:
        安全ならTrue、危険ならFalse
    """
    sql_upper = sql.upper().strip()
    
    # 第1層：ホワイトリスト方式 - SELECT文のみ許可
    if not sql_upper.startswith('SELECT'):
        print("[ERROR] セキュリティチェック失敗: SELECT文以外は禁止")
        return False
    
    # 第2層：ブラックリスト - 危険なキーワードを禁止
    dangerous_keywords = [
        'DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 
        'CREATE', 'TRUNCATE', 'REPLACE', 'PRAGMA',
        'ATTACH', 'DETACH', 'VACUUM'
    ]
    
    for keyword in dangerous_keywords:
        if keyword in sql_upper:
            print(f"[ERROR] セキュリティチェック失敗: 危険なキーワード '{keyword}' を検出")
            return False
    
    # 第3層：パターンチェック - 悪意のある構文を検出
    dangerous_patterns = [
        r';\s*(DROP|DELETE|INSERT|UPDATE)',  # セミコロン後の危険文
        r'--',  # SQLコメント（コメントアウト攻撃）
        r'/\*.*\*/',  # ブロックコメント
        r'UNION.*SELECT',  # UNION攻撃
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, sql_upper):
            print(f"[ERROR] セキュリティチェック失敗: 危険なパターンを検出")
            return False
    
    print("[OK] セキュリティチェック通過")
    return True

# 🔧 ツール1: テーブル一覧を取得（前回と同じ）
@mcp.tool()
def list_tables() -> List[Dict[str, Any]]:
    """データベース内のすべてのテーブルを一覧表示"""
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

# 🔧 ツール2: スキーマ取得（前回と同じ）
@mcp.tool()
def get_table_schema(table_name: str) -> Dict[str, Any]:
    """指定したテーブルの詳細なスキーマ情報を取得"""
    print(f"[分析] テーブル '{table_name}' のスキーマを分析中...")
    
    conn = get_db_connection()
    
    # テーブル存在確認
    cursor = conn.execute('''
    SELECT name FROM sqlite_master 
    WHERE type='table' AND name=?
    ''', (table_name,))
    
    if not cursor.fetchone():
        conn.close()
        raise ValueError(f"テーブル '{table_name}' は存在しません")
    
    # 列情報取得
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
    
    # サンプルデータ取得
    cursor = conn.execute(f'SELECT * FROM {table_name} LIMIT 3')
    sample_data = [dict(row) for row in cursor.fetchall()]
    
    # レコード数取得
    cursor = conn.execute(f'SELECT COUNT(*) as count FROM {table_name}')
    record_count = cursor.fetchone()["count"]
    
    conn.close()
    
    print(f"[完了] スキーマ分析完了: {len(columns)}列、{record_count}レコード")
    return {
        "table_name": table_name,
        "columns": columns,
        "record_count": record_count,
        "sample_data": sample_data
    }

# 🆕 ツール3: 安全なクエリ実行（新機能！）
@mcp.tool()
def execute_safe_query(sql: str) -> Dict[str, Any]:
    """安全なSELECTクエリのみを実行
    
    Args:
        sql: 実行するSQLクエリ（SELECT文のみ許可）
    
    Returns:
        クエリ結果とメタデータ
    """
    print(f"[準備] SQLクエリの実行準備中...")
    print(f"[SQL] 実行予定のSQL: {sql}")
    
    # セキュリティチェック
    if not validate_sql_safety(sql):
        raise ValueError("× 安全でないSQL文です。SELECT文のみ実行可能です。")
    
    conn = get_db_connection()
    
    try:
        print("[実行] クエリ実行中...")
        cursor = conn.execute(sql)
        results = [dict(row) for row in cursor.fetchall()]
        
        # クエリのメタデータを収集
        column_names = [description[0] for description in cursor.description] if cursor.description else []
        
        query_result = {
            "sql": sql,
            "results": results,
            "column_names": column_names,
            "row_count": len(results),
            "executed_at": datetime.now().isoformat()
        }
        
        conn.close()
        
        print(f"[完了] クエリ実行完了: {len(results)}件の結果を取得")
        return query_result
        
    except sqlite3.Error as e:
        conn.close()
        print(f"[ERROR] SQLエラーが発生: {str(e)}")
        raise ValueError(f"SQLエラー: {str(e)}")

# サーバー起動
if __name__ == "__main__":
    print("[起動] MCPサーバー（Step C版）を起動します...")
    print("[ツール] 利用可能なツール: list_tables, get_table_schema, execute_safe_query")
    print("[セキュリティ] セキュリティ機能: 多層防御でSQLインジェクション対策")
    mcp.run()