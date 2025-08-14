#!/usr/bin/env python3
"""
最初のデータベース体験 - 5分版
"""

import sqlite3

print("[開始] 5分でデータベース体験を始めます！")

# 1. データベースファイルを作成
print("[作成] データベースファイルを作成中...")
conn = sqlite3.connect('my_first_database.db')

# 2. 簡単なテーブルを作成
print("[テーブル] テーブルを作成中...")
conn.execute('''
CREATE TABLE IF NOT EXISTS greetings (
    id INTEGER PRIMARY KEY,
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

# 3. データを2つ入れる
print("[保存] データを保存中...")
conn.execute("INSERT INTO greetings (message) VALUES ('Hello Database!')")
conn.execute("INSERT INTO greetings (message) VALUES ('データベースって意外と簡単！')")

# 4. データを取り出す
print("[取得] データを取得中...")
cursor = conn.execute('SELECT message FROM greetings')
results = cursor.fetchall()

print("[結果] 結果:")
for row in results:
    print(f"  - {row[0]}")

# 5. 後片付け
conn.commit()
conn.close()

print("[完了] my_first_database.db ファイルができました")
print("[説明] これがデータベースの基本動作です")