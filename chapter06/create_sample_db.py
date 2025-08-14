#!/usr/bin/env python3
"""
現代版MCPデータベース・サンプル作成
- 実際のビジネスを模したリアルなデータ
- AIが分析しやすい構造
- 100件の売上データと10の商品データ
"""

import sqlite3
from datetime import datetime, timedelta
import random

def create_modern_sample_database():
    """AIが理解しやすいサンプルデータベースを作成"""
    conn = sqlite3.connect('intelligent_shop.db')
    cursor = conn.cursor()
    
    # productsテーブル（商品情報）
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        price INTEGER NOT NULL CHECK(price > 0),
        stock INTEGER NOT NULL CHECK(stock >= 0),
        category TEXT NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # salesテーブル（売上記録）
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL CHECK(quantity > 0),
        unit_price INTEGER NOT NULL CHECK(unit_price > 0),
        total_amount INTEGER NOT NULL CHECK(total_amount > 0),
        sale_date DATE NOT NULL,
        customer_id INTEGER NOT NULL,
        sales_person TEXT,
        notes TEXT,
        FOREIGN KEY (product_id) REFERENCES products (id),
        FOREIGN KEY (customer_id) REFERENCES customers (id)
    )
    ''')
    
    # customersテーブル（顧客情報）
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE,
        phone TEXT,
        address TEXT,
        customer_type TEXT CHECK(customer_type IN ('individual', 'business')),
        registration_date DATE DEFAULT (date('now')),
        total_purchases INTEGER DEFAULT 0,
        last_purchase_date DATE
    )
    ''')
    
    # 商品データ（実際のApple製品を模倣）
    products = [
        ('iPhone 15 Pro', 159800, 15, 'スマートフォン', 'A17 Proチップ搭載の最新iPhone'),
        ('MacBook Air M3', 134800, 8, 'ノートPC', '13インチ、8GB RAM、256GB SSD'),
        ('iPad Pro 12.9', 128800, 12, 'タブレット', 'M2チップ搭載、12.9インチLiquid Retina XDRディスプレイ'),
        ('AirPods Pro 第3世代', 39800, 2, 'オーディオ', 'アクティブノイズキャンセリング搭載'),
        ('Apple Watch Series 9', 59800, 5, 'ウェアラブル', 'GPSモデル、45mm'),
        ('Magic Keyboard', 19800, 8, 'アクセサリ', 'iPad Pro用、バックライト付き'),
        ('iPhone 15', 124800, 25, 'スマートフォン', 'A16 Bionicチップ搭載'),
        ('iPad Air', 98800, 18, 'タブレット', 'M1チップ搭載、10.9インチ'),
        ('MacBook Pro 14インチ', 248800, 3, 'ノートPC', 'M3 Proチップ、16GB RAM、512GB SSD'),
        ('AirPods 第3世代', 19800, 30, 'オーディオ', '空間オーディオ対応')
    ]
    
    cursor.executemany('''
    INSERT OR IGNORE INTO products (name, price, stock, category, description) 
    VALUES (?, ?, ?, ?, ?)
    ''', products)
    
    # 顧客データ（個人・法人のミックス）
    customers = [
        ('田中太郎', 'tanaka@example.com', '090-1234-5678', '東京都渋谷区', 'individual'),
        ('佐藤商事株式会社', 'sato@business.com', '03-1234-5678', '大阪府大阪市', 'business'),
        ('山田花子', 'yamada@example.com', '080-9876-5432', '愛知県名古屋市', 'individual'),
        ('鈴木システム', 'suzuki@tech.com', '045-111-2222', '神奈川県横浜市', 'business'),
        ('高橋一郎', 'takahashi@gmail.com', '070-5555-6666', '福岡県福岡市', 'individual')
    ]
    
    cursor.executemany('''
    INSERT OR IGNORE INTO customers (name, email, phone, address, customer_type)
    VALUES (?, ?, ?, ?, ?)
    ''', customers)
    
    # ランダムな売上データ生成（リアルな販売パターンを模倣）
    sales_data = []
    
    for i in range(100):  # 100件の売上データ
        product_id = random.randint(1, 10)
        quantity = random.randint(1, 5)
        
        # 商品の単価を取得
        cursor.execute('SELECT price FROM products WHERE id = ?', (product_id,))
        unit_price = cursor.fetchone()[0]
        total_amount = unit_price * quantity
        
        # ランダムな日付（過去90日間）
        days_ago = random.randint(0, 90)
        sale_date = (datetime.now() - timedelta(days=days_ago)).date()
        
        customer_id = random.randint(1, 5)
        sales_person = random.choice(['田中', '佐藤', '山田', '鈴木'])
        
        sales_data.append((
            product_id, customer_id, quantity, unit_price, total_amount, 
            sale_date, sales_person, None
        ))
    
    cursor.executemany('''
    INSERT INTO sales 
    (product_id, customer_id, quantity, unit_price, total_amount, sale_date, sales_person, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', sales_data)
    
    conn.commit()
    conn.close()
    print("[完了] インテリジェント・ショップのデータベース作成完了: intelligent_shop.db")
    print("[準備] AIが分析可能なリッチなデータが準備されました")
    print("[データ] 3ヶ月分のビジネスデータ（100取引、10商品、5顧客）")

if __name__ == "__main__":
    create_modern_sample_database()