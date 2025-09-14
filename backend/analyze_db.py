#!/usr/bin/env python3
import sqlite3
import json
from pathlib import Path

def analyze_database(db_path):
    """データベースの詳細解析"""
    print(f"データベース解析: {db_path}")
    print("="*50)
    
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 全テーブル一覧
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"テーブル数: {len(tables)}")
        print("テーブル一覧:")
        for table in tables:
            print(f"  - {table[0]}")
        print()
        
        # 各テーブルの詳細解析
        for table in tables:
            table_name = table[0]
            if table_name.startswith('sqlite_'):
                continue
                
            print(f"テーブル: {table_name}")
            print("-"*30)
            
            # スキーマ情報
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            
            print("カラム構成:")
            for col in columns:
                print(f"  {col['name']:15} {col['type']:10} {'NOT NULL' if col['notnull'] else 'NULL'} {'PK' if col['pk'] else ''}")
            
            # レコード数
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"レコード数: {count}")
            
            # サンプルデータ（最初の3件）
            if count > 0:
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
                samples = cursor.fetchall()
                print("サンプルデータ:")
                for i, row in enumerate(samples, 1):
                    print(f"  レコード{i}:")
                    for key in row.keys():
                        value = row[key]
                        if isinstance(value, str) and len(value) > 50:
                            value = value[:50] + "..."
                        print(f"    {key}: {value}")
                    print()
            
            # 特定カラムの値分析（価格、住所関連）
            if table_name == 'properties':
                print("価格分析:")
                cursor.execute("SELECT MIN(price) as min_price, MAX(price) as max_price, AVG(price) as avg_price FROM properties WHERE price IS NOT NULL")
                price_stats = cursor.fetchone()
                if price_stats:
                    print(f"  最小価格: {price_stats['min_price']:,}円")
                    print(f"  最大価格: {price_stats['max_price']:,}円") 
                    print(f"  平均価格: {price_stats['avg_price']:,.0f}円")
                
                # 住所関連カラムの確認
                address_columns = []
                for col in columns:
                    col_name = col['name'].lower()
                    if any(keyword in col_name for keyword in ['address', 'area', 'location', '住所', '所在', '地域', 'prefecture', 'city', 'ward']):
                        address_columns.append(col['name'])
                
                if address_columns:
                    print("住所関連カラム:")
                    for addr_col in address_columns:
                        cursor.execute(f"SELECT DISTINCT {addr_col} FROM properties WHERE {addr_col} IS NOT NULL LIMIT 10")
                        values = cursor.fetchall()
                        print(f"  {addr_col}: {[v[0] for v in values]}")
                
                # 間取りの分析
                cursor.execute("SELECT room_type, COUNT(*) as count FROM properties WHERE room_type IS NOT NULL GROUP BY room_type")
                room_types = cursor.fetchall()
                if room_types:
                    print("間取り分布:")
                    for rt in room_types:
                        print(f"  {rt['room_type']}: {rt['count']}件")
            
            print("="*50)

if __name__ == "__main__":
    db_path = "./data/props.db"
    if Path(db_path).exists():
        analyze_database(db_path)
    else:
        print(f"データベースファイルが見つかりません: {db_path}")