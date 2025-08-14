#!/usr/bin/env python3
"""
Step D: プロンプト機能を追加した完全版
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
def get_table_schema(table_name: str) -> Dict[str, Any]:
    """指定したテーブルの詳細なスキーマ情報とサンプルデータを取得。
    
    カラム名、データ型、NULL制約、デフォルト値、プライマリキー情報を含む。
    サンプルデータ（3件）とレコード数も返却。
    例：「usersテーブルの構造を見たい」「商品テーブルには何が入ってる？」
    """
    conn = get_db_connection()
    
    cursor = conn.execute('''
    SELECT name FROM sqlite_master 
    WHERE type='table' AND name=?
    ''', (table_name,))
    
    if not cursor.fetchone():
        conn.close()
        raise ValueError(f"テーブル '{table_name}' は存在しません")
    
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
    
    cursor = conn.execute(f'SELECT * FROM {table_name} LIMIT 3')
    sample_data = [dict(row) for row in cursor.fetchall()]
    
    cursor = conn.execute(f'SELECT COUNT(*) as count FROM {table_name}')
    record_count = cursor.fetchone()["count"]
    
    conn.close()
    
    return {
        "table_name": table_name,
        "columns": columns,
        "record_count": record_count,
        "sample_data": sample_data
    }

@mcp.tool()
def execute_safe_query(sql: str) -> Dict[str, Any]:
    """SELECTクエリのみを安全に実行。データの検索、集計、分析に使用。
    
    INSERT/UPDATE/DELETE/DROPなどの破壊的操作は禁止。
    JOIN、GROUP BY、ORDER BY、WHERE句などはOK。
    結果はJSON形式でカラム名、データ、実行時刻を含む。
    例：「売上トップ10を出して」「今月の売上合計を計算」
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

# プロンプト機能の追加
@mcp.prompt()
def sales_analysis_prompt(month: str, focus_category: str = None) -> str:
    """月次売上分析用のプロンプト
    
    Args:
        month: 分析する月（例：2024年3月）
        focus_category: 特に注目するカテゴリ（省略可）
    """
    prompt = f"""
{month}の売上データを以下の観点で分析してください：

1. 総売上額と前月比
2. カテゴリ別売上ランキング（上位5つ）
3. 最も売れた商品TOP3
4. 在庫回転率の分析
"""
    
    if focus_category:
        prompt += f"5. {focus_category}カテゴリの詳細分析\n"
    
    prompt += """
分析結果は、経営層向けのサマリーとして、
重要なインサイトと改善提案を含めて報告してください。
"""
    return prompt

@mcp.prompt()
def inventory_alert_prompt(threshold: int = 10) -> str:
    """在庫アラート用のプロンプト
    
    Args:
        threshold: 在庫警告の閾値（デフォルト：10）
    """
    return f"""
在庫管理レポートを作成してください：

1. 在庫が{threshold}個以下の商品をリストアップ
2. 各商品の過去30日間の販売ペースを計算
3. このペースで在庫切れになるまでの日数を予測
4. 優先的に補充すべき商品を3つ提案
5. 推奨発注数量を計算

緊急度に応じて、[緊急]、[要注意]、[余裕あり]
のマークを付けて視覚的に分かりやすく表示してください。
"""

@mcp.prompt()
def customer_behavior_prompt(period: str, segment: str = None) -> str:
    """顧客行動分析用のプロンプト
    
    Args:
        period: 分析期間（例：過去3ヶ月）
        segment: 顧客セグメント（新規/既存/VIP）（省略可）
    """
    prompt = f"""
{period}の顧客購買行動を分析してください：

1. 購買頻度の分布
2. 平均購買単価の推移
3. リピート率の計算
"""
    
    if segment:
        prompt += f"4. {segment}顧客の特徴的な行動パターン\n"
    else:
        prompt += "4. 顧客セグメント別の比較\n"
    
    prompt += """5. クロスセル/アップセルの機会

マーケティング施策の提案：
- ターゲット顧客層
- 推奨するキャンペーン内容
- 期待される効果

データに基づいた具体的な数値を使って説明してください。
"""
    return prompt

# サーバー起動
if __name__ == "__main__":
    print("[起動] MCPサーバー（プロンプト機能付き完全版）を起動します...")
    print("[ツール] 利用可能なツール: list_tables, get_table_schema, execute_safe_query")
    print("[プロンプト] 利用可能なプロンプト: sales_analysis_prompt, inventory_alert_prompt, customer_behavior_prompt")
    mcp.run()