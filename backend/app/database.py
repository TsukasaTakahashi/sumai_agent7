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
        """既存のデータベースを使用するため、テーブル作成をスキップ"""
        # BUY_data_integrated テーブルが既に存在するデータベースを使用
        # 検索履歴テーブルのみ必要に応じて追加
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # 既存テーブルの確認
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='BUY_data_integrated'")
                if cursor.fetchone():
                    logger.info("BUY_data_integrated table found - using existing data")
                else:
                    logger.warning("BUY_data_integrated table not found in database")

                # 検索履歴テーブルのみ作成
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
                logger.info("Database initialization completed")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
    
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
                         latitude: Optional[float] = None,
                         longitude: Optional[float] = None,
                         radius_km: Optional[float] = None,
                         limit: int = 10) -> List[Dict]:
        """物件を検索（緯度経度検索対応）"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row  # 辞書形式で結果を取得
                cursor = conn.cursor()

                query = "SELECT * FROM BUY_data_integrated WHERE 1=1"
                params = []

                if area:
                    query += " AND address LIKE ?"
                    params.append(f"%{area}%")

                if max_price:
                    # 賃料または価格での絞り込み
                    query += " AND (CAST(rent AS INTEGER) <= ? OR CAST(mi_price AS INTEGER) <= ?)"
                    params.extend([max_price, max_price])

                if room_type:
                    query += " AND floor_plan LIKE ?"
                    params.append(f"%{room_type}%")

                # 緯度経度による距離検索
                if latitude is not None and longitude is not None and radius_km is not None:
                    # Haversine公式を使用した距離計算
                    query += """ AND (
                        6371 * acos(
                            cos(radians(?)) * cos(radians(latitude)) *
                            cos(radians(longitude) - radians(?)) +
                            sin(radians(?)) * sin(radians(latitude))
                        )
                    ) <= ?"""
                    params.extend([latitude, longitude, latitude, radius_km])

                query += " ORDER BY dt DESC LIMIT ?"
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

    def search_properties_by_distance(self,
                                    center_lat: float,
                                    center_lng: float,
                                    radius_km: float,
                                    max_price: Optional[int] = None,
                                    room_type: Optional[str] = None,
                                    limit: int = 10) -> List[Dict]:
        """指定した地点からの距離で物件を検索"""
        return self.search_properties(
            latitude=center_lat,
            longitude=center_lng,
            radius_km=radius_km,
            max_price=max_price,
            room_type=room_type,
            limit=limit
        )
    
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

    def _normalize_location_text(self, text: str) -> str:
        """地域名の表記揺れを正規化"""
        if not text:
            return text

        # よくある表記揺れを修正
        normalized = text.replace('ヶ', 'ケ')  # 保土ヶ谷区 → 保土ケ谷区
        normalized = normalized.replace('が', 'ガ')  # 世田が谷 → 世田ガ谷
        normalized = normalized.replace('ヴ', 'ブ')  # ヴィラ → ビラ

        return normalized

    def get_filtered_count(self,
                         area: Optional[str] = None,
                         max_price: Optional[int] = None,
                         min_price: Optional[int] = None,
                         room_type: Optional[str] = None) -> int:
        """絞り込み条件での物件件数を取得（重複削除適用）"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 重複削除を適用した件数クエリ（住所、価格、間取りの組み合わせでDISTINCT）
                query = "SELECT COUNT(*) FROM (SELECT DISTINCT address, mi_price, floor_plan FROM BUY_data_integrated WHERE 1=1"
                params = []

                if area:
                    # テキスト正規化を適用
                    normalized_area = self._normalize_location_text(area)
                    query += " AND address LIKE ?"
                    params.append(f"%{normalized_area}%")

                if max_price:
                    query += " AND CAST(mi_price AS INTEGER) <= ?"
                    params.append(max_price)

                if min_price:
                    query += " AND CAST(mi_price AS INTEGER) >= ?"
                    params.append(min_price)

                if room_type:
                    query += " AND floor_plan LIKE ?"
                    params.append(f"%{room_type}%")

                # 有効な価格データのみ対象
                query += " AND mi_price IS NOT NULL AND mi_price != '' AND mi_price != '0'"
                query += ")"  # サブクエリを閉じる

                logger.info(f"Count query (with duplicate removal): {query}, Params: {params}")
                cursor.execute(query, params)
                count = cursor.fetchone()[0]

                logger.info(f"Count result after duplicate removal: {count}")
                return count

        except Exception as e:
            logger.error(f"Filtered count query failed: {e}")
            return 0

# グローバルインスタンス
database_service = DatabaseService()