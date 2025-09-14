import sqlite3
import logging
from typing import List, Dict, Optional
from pathlib import Path
from app.config import DB_PATH

logger = logging.getLogger(__name__)

class DatabaseService:
    def __init__(self):
        self.db_path = DB_PATH
        self._ensure_database_exists()
        self._create_tables()
    
    def _ensure_database_exists(self):
        """データベースファイルとディレクトリが存在することを確認"""
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Database path: {self.db_path}")
    
    def _create_tables(self):
        """必要なテーブルを作成"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 物件テーブル
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS properties (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    area TEXT NOT NULL,
                    room_type TEXT NOT NULL,
                    size_sqm REAL,
                    station_distance TEXT,
                    age_years INTEGER,
                    description TEXT,
                    image_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # ユーザー検索履歴テーブル
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS search_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    search_query TEXT NOT NULL,
                    search_filters TEXT,
                    result_count INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            logger.info("Database tables created successfully")
    
    def test_connection(self) -> Dict[str, any]:
        """データベース接続をテスト"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                
                # 各テーブルのレコード数を取得
                table_info = {}
                for table in tables:
                    table_name = table[0]
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = cursor.fetchone()[0]
                    table_info[table_name] = count
                
                return {
                    "status": "success",
                    "database_path": self.db_path,
                    "tables": table_info,
                    "message": "Database connection successful"
                }
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return {
                "status": "error",
                "database_path": self.db_path,
                "error": str(e),
                "message": "Database connection failed"
            }
    
    def add_sample_properties(self):
        """サンプル物件データを追加"""
        sample_properties = [
            {
                "title": "渋谷駅徒歩5分 1K マンション",
                "price": 120000,
                "area": "渋谷区",
                "room_type": "1K",
                "size_sqm": 25.5,
                "station_distance": "渋谷駅徒歩5分",
                "age_years": 5,
                "description": "駅近の好立地マンション。コンビニ、スーパー徒歩圏内。",
                "image_url": "/images/property1.jpg"
            },
            {
                "title": "新宿駅徒歩8分 1DK アパート",
                "price": 98000,
                "area": "新宿区",
                "room_type": "1DK",
                "size_sqm": 32.0,
                "station_distance": "新宿駅徒歩8分",
                "age_years": 12,
                "description": "リノベーション済み。オートロック付き。",
                "image_url": "/images/property2.jpg"
            },
            {
                "title": "池袋駅徒歩10分 1LDK マンション",
                "price": 150000,
                "area": "豊島区",
                "room_type": "1LDK",
                "size_sqm": 45.2,
                "station_distance": "池袋駅徒歩10分",
                "age_years": 3,
                "description": "築浅マンション。バス・トイレ別。",
                "image_url": "/images/property3.jpg"
            }
        ]
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for prop in sample_properties:
                    cursor.execute('''
                        INSERT INTO properties 
                        (title, price, area, room_type, size_sqm, station_distance, age_years, description, image_url)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        prop["title"], prop["price"], prop["area"], prop["room_type"],
                        prop["size_sqm"], prop["station_distance"], prop["age_years"],
                        prop["description"], prop["image_url"]
                    ))
                
                conn.commit()
                logger.info(f"Added {len(sample_properties)} sample properties")
                return {"status": "success", "added_count": len(sample_properties)}
        
        except Exception as e:
            logger.error(f"Failed to add sample properties: {e}")
            return {"status": "error", "error": str(e)}
    
    def search_properties(self, 
                         area: Optional[str] = None,
                         max_price: Optional[int] = None,
                         room_type: Optional[str] = None,
                         limit: int = 10) -> List[Dict]:
        """物件を検索"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row  # 辞書形式で結果を取得
                cursor = conn.cursor()
                
                query = "SELECT * FROM properties WHERE 1=1"
                params = []
                
                if area:
                    query += " AND area LIKE ?"
                    params.append(f"%{area}%")
                
                if max_price:
                    query += " AND price <= ?"
                    params.append(max_price)
                
                if room_type:
                    query += " AND room_type = ?"
                    params.append(room_type)
                
                query += " ORDER BY created_at DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                results = cursor.fetchall()
                
                # 辞書のリストに変換
                properties = []
                for row in results:
                    properties.append(dict(row))
                
                return properties
        
        except Exception as e:
            logger.error(f"Property search failed: {e}")
            return []
    
    def save_search_history(self, session_id: str, search_query: str, search_filters: str, result_count: int):
        """検索履歴を保存"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO search_history (session_id, search_query, search_filters, result_count)
                    VALUES (?, ?, ?, ?)
                ''', (session_id, search_query, search_filters, result_count))
                conn.commit()
                logger.info(f"Saved search history for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to save search history: {e}")

# グローバルインスタンス
database_service = DatabaseService()