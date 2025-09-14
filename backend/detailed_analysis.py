#!/usr/bin/env python3
import sqlite3
import json
from pathlib import Path
from collections import Counter
import re

def detailed_price_analysis(db_path):
    """価格の詳細分析"""
    print("価格分析（詳細）")
    print("="*50)
    
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 価格データの型確認と変換
        cursor.execute("""
            SELECT mi_price, mx_price, COUNT(*) as count
            FROM BUY_data_url_uniqued 
            WHERE mi_price IS NOT NULL AND mi_price != '' 
            LIMIT 10
        """)
        samples = cursor.fetchall()
        print("価格データサンプル:")
        for s in samples:
            print(f"  {s['mi_price']} - {s['mx_price']} ({s['count']}件)")
        
        # 価格を数値に変換して統計取得
        cursor.execute("""
            SELECT 
                CAST(mi_price AS INTEGER) as price,
                COUNT(*) as count
            FROM BUY_data_url_uniqued 
            WHERE mi_price IS NOT NULL 
                AND mi_price != '' 
                AND CAST(mi_price AS INTEGER) > 0
        """)
        
        prices = cursor.fetchall()
        if prices:
            cursor.execute("""
                SELECT 
                    MIN(CAST(mi_price AS INTEGER)) as min_price,
                    MAX(CAST(mi_price AS INTEGER)) as max_price,
                    AVG(CAST(mi_price AS INTEGER)) as avg_price,
                    COUNT(*) as total_count
                FROM BUY_data_url_uniqued 
                WHERE mi_price IS NOT NULL 
                    AND mi_price != '' 
                    AND CAST(mi_price AS INTEGER) > 0
            """)
            stats = cursor.fetchone()
            print(f"\n価格統計:")
            print(f"  総物件数: {stats['total_count']:,}件")
            print(f"  最低価格: {stats['min_price']:,}円")
            print(f"  最高価格: {stats['max_price']:,}円")
            print(f"  平均価格: {stats['avg_price']:,.0f}円")
            
            # 価格帯別分布
            cursor.execute("""
                SELECT 
                    CASE 
                        WHEN CAST(mi_price AS INTEGER) < 10000000 THEN '1000万円未満'
                        WHEN CAST(mi_price AS INTEGER) < 20000000 THEN '1000-2000万円'
                        WHEN CAST(mi_price AS INTEGER) < 30000000 THEN '2000-3000万円'
                        WHEN CAST(mi_price AS INTEGER) < 50000000 THEN '3000-5000万円'
                        WHEN CAST(mi_price AS INTEGER) < 100000000 THEN '5000万円-1億円'
                        ELSE '1億円以上'
                    END as price_range,
                    COUNT(*) as count
                FROM BUY_data_url_uniqued 
                WHERE mi_price IS NOT NULL 
                    AND mi_price != '' 
                    AND CAST(mi_price AS INTEGER) > 0
                GROUP BY price_range
                ORDER BY MIN(CAST(mi_price AS INTEGER))
            """)
            ranges = cursor.fetchall()
            print("\n価格帯別分布:")
            for r in ranges:
                print(f"  {r['price_range']}: {r['count']:,}件")

def detailed_address_analysis(db_path):
    """住所の詳細分析"""
    print("\n住所分析（詳細）")
    print("="*50)
    
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 都道府県別分布
        cursor.execute("""
            SELECT pref, COUNT(*) as count
            FROM BUY_data_url_uniqued 
            WHERE pref IS NOT NULL AND pref != ''
            GROUP BY pref
            ORDER BY count DESC
            LIMIT 20
        """)
        prefs = cursor.fetchall()
        print("都道府県別件数（上位20）:")
        for p in prefs:
            print(f"  {p['pref']}: {p['count']:,}件")
        
        # 住所サンプル分析（市区町村抽出）
        cursor.execute("""
            SELECT address, COUNT(*) as count
            FROM BUY_data_url_uniqued 
            WHERE address IS NOT NULL AND address != ''
            GROUP BY address
            ORDER BY count DESC
            LIMIT 10
        """)
        addresses = cursor.fetchall()
        print("\n住所別件数（上位10）:")
        for a in addresses:
            print(f"  {a['address']}: {a['count']}件")

def floor_plan_analysis(db_path):
    """間取り分析"""
    print("\n間取り分析")
    print("="*50)
    
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT floor_plan, COUNT(*) as count
            FROM BUY_data_url_uniqued 
            WHERE floor_plan IS NOT NULL AND floor_plan != ''
            GROUP BY floor_plan
            ORDER BY count DESC
            LIMIT 15
        """)
        plans = cursor.fetchall()
        print("間取り別件数（上位15）:")
        for p in plans:
            print(f"  {p['floor_plan']}: {p['count']:,}件")

def traffic_analysis(db_path):
    """交通情報分析"""
    print("\n交通情報分析")
    print("="*50)
    
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 駅名の抽出（traffic1から）
        cursor.execute("""
            SELECT traffic1, COUNT(*) as count
            FROM BUY_data_url_uniqued 
            WHERE traffic1 IS NOT NULL AND traffic1 != ''
            GROUP BY traffic1
            ORDER BY count DESC
            LIMIT 10
        """)
        traffic = cursor.fetchall()
        print("交通情報別件数（上位10）:")
        for t in traffic:
            traffic_info = t['traffic1'][:80] + "..." if len(t['traffic1']) > 80 else t['traffic1']
            print(f"  {traffic_info}: {t['count']}件")

if __name__ == "__main__":
    db_path = "./data/props.db"
    if Path(db_path).exists():
        detailed_price_analysis(db_path)
        detailed_address_analysis(db_path)
        floor_plan_analysis(db_path)
        traffic_analysis(db_path)
    else:
        print(f"データベースファイルが見つかりません: {db_path}")