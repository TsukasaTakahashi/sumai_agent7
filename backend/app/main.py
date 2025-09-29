from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from datetime import datetime

from app import config
from app.models import (
    ChatRequest, ChatResponse, MessageRole, FileUploadResponse, 
    ErrorResponse, FileType
)
from app.services import chat_service, ai_agent_service, file_service
from app.database import database_service

# FastAPIインスタンス作成
app = FastAPI(title="住まいエージェント API", version="1.0.0")

# CORS設定（開発用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    """ヘルスチェックエンドポイント"""
    return {"status": "ok"}

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """チャットメッセージを処理"""
    try:
        # セッションIDが提供されていない場合は新しいセッションを作成
        if not request.session_id:
            session_id = chat_service.create_session()
        else:
            session_id = request.session_id
            # セッションが存在しない場合は新しく作成
            if not chat_service.get_session(session_id):
                session_id = chat_service.create_session()
        
        # ユーザーメッセージを保存
        user_message = chat_service.add_message(
            session_id=session_id,
            role=MessageRole.USER,
            content=request.message
        )
        
        # AI エージェントにメッセージをルーティング
        agent_response = await ai_agent_service.route_message(
            message=request.message,
            session_id=session_id,
            active_function=request.active_function,
            search_radius=request.search_radius
        )
        
        # AIレスポンスを保存
        ai_message = chat_service.add_message(
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content=agent_response.response
        )
        
        return ChatResponse(
            message_id=ai_message.id,
            session_id=session_id,
            response=agent_response.response,
            timestamp=ai_message.timestamp,
            agent_used=agent_response.agent_name,
            property_table=agent_response.property_table
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/chat/{session_id}/messages")
async def get_chat_history(session_id: str):
    """チャット履歴を取得"""
    try:
        messages = chat_service.get_messages(session_id)
        return {"session_id": session_id, "messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    description: Optional[str] = Form(None)
):
    """ファイルをアップロード"""
    try:
        # セッションIDが提供されていない場合は新しいセッションを作成
        if not session_id:
            session_id = chat_service.create_session()
        
        # ファイル情報を保存（実際のファイル保存は後で実装）
        file_id = file_service.save_file_info(
            filename=file.filename,
            file_size=file.size or 0,
            session_id=session_id
        )
        
        # ファイルタイプを判定
        file_type_str = file_service._detect_file_type(file.filename)
        file_type = FileType.IMAGE if file_type_str == "image" else (
            FileType.PDF if file_type_str == "pdf" else FileType.OTHER
        )
        
        return FileUploadResponse(
            file_id=file_id,
            filename=file.filename,
            file_type=file_type,
            file_size=file.size or 0,
            upload_timestamp=datetime.now(),
            session_id=session_id
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions")
async def list_sessions():
    """アクティブなセッション一覧を取得"""
    try:
        sessions = []
        for session_id, session in chat_service.sessions.items():
            sessions.append({
                "session_id": session_id,
                "created_at": session.created_at,
                "last_activity": session.last_activity,
                "message_count": len(session.messages)
            })
        return {"sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/database/test")
async def test_database():
    """データベース接続をテスト"""
    try:
        result = database_service.test_connection()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/database/sample-data")
async def add_sample_data():
    """サンプル物件データを追加"""
    try:
        result = database_service.add_sample_properties()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/properties/search")
async def search_properties(
    area: Optional[str] = None,
    max_price: Optional[int] = None,
    room_type: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    radius_km: Optional[float] = None,
    limit: int = 10
):
    """物件を検索（緯度経度検索対応）"""
    try:
        properties = database_service.search_properties(
            area=area,
            max_price=max_price,
            room_type=room_type,
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            limit=limit
        )
        return {
            "properties": properties,
            "count": len(properties)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/properties/search/geo")
async def search_properties_by_location(
    lat: float,
    lng: float,
    radius_km: float = 5.0,
    max_price: Optional[int] = None,
    room_type: Optional[str] = None,
    limit: int = 10
):
    """指定した地点からの距離で物件を検索"""
    try:
        # より多くのデータを取得（重複削除分を考慮）
        fetch_limit = min(limit * 3, 500)  # 重複削除後にlimit件確保するため

        properties = database_service.search_properties_by_distance(
            center_lat=lat,
            center_lng=lng,
            radius_km=radius_km,
            max_price=max_price,
            room_type=room_type,
            limit=fetch_limit
        )

        # 重複削除を適用
        from app.property_agent import PropertyAnalysisAgent
        agent = PropertyAnalysisAgent()
        if properties:
            properties, dedup_stats = agent._remove_duplicates(properties)
            # limitに制限
            properties = properties[:limit]

            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Geo search duplicate removal: {fetch_limit} fetched -> {len(properties)} returned (after dedup and limit)")

        return {
            "properties": properties,
            "count": len(properties),
            "search_center": {"latitude": lat, "longitude": lng},
            "radius_km": radius_km
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/properties/count")
async def get_filtered_property_count(
    area: Optional[str] = None,
    max_price: Optional[int] = None,
    min_price: Optional[int] = None,
    room_type: Optional[str] = None
):
    """絞り込み条件での物件件数を取得"""
    try:
        count = database_service.get_filtered_count(
            area=area,
            max_price=max_price,
            min_price=min_price,
            room_type=room_type
        )
        return {"count": count, "filters": {"area": area, "max_price": max_price, "min_price": min_price, "room_type": room_type}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/database/stats")
async def get_database_stats():
    """データベース統計情報を取得"""
    try:
        from app.config import DB_PATH
        import sqlite3

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # 全件数を取得
            cursor.execute("SELECT COUNT(*) FROM BUY_data_integrated")
            total_count = cursor.fetchone()[0]

            # 価格統計
            cursor.execute("""
                SELECT
                    MIN(CAST(mi_price AS INTEGER)) as min_price,
                    MAX(CAST(mi_price AS INTEGER)) as max_price,
                    AVG(CAST(mi_price AS INTEGER)) as avg_price
                FROM BUY_data_integrated
                WHERE mi_price IS NOT NULL
                    AND mi_price != ''
                    AND CAST(mi_price AS INTEGER) > 0
            """)
            price_stats = cursor.fetchone()

            # 都道府県別上位10件
            cursor.execute("""
                SELECT
                    CASE
                        WHEN address LIKE '%東京都%' THEN '東京都'
                        WHEN address LIKE '%神奈川県%' THEN '神奈川県'
                        WHEN address LIKE '%千葉県%' THEN '千葉県'
                        WHEN address LIKE '%埼玉県%' THEN '埼玉県'
                        WHEN address LIKE '%大阪府%' THEN '大阪府'
                        WHEN address LIKE '%愛知県%' THEN '愛知県'
                        WHEN address LIKE '%兵庫県%' THEN '兵庫県'
                        WHEN address LIKE '%福岡県%' THEN '福岡県'
                        WHEN address LIKE '%北海道%' THEN '北海道'
                        WHEN address LIKE '%京都府%' THEN '京都府'
                        ELSE 'その他'
                    END as prefecture,
                    COUNT(*) as count
                FROM BUY_data_integrated
                WHERE address IS NOT NULL AND address != ''
                GROUP BY prefecture
                ORDER BY count DESC
                LIMIT 10
            """)
            top_prefs = cursor.fetchall()

            return {
                "total_properties": total_count,
                "price_stats": {
                    "min_price": price_stats[0] if price_stats[0] else 0,
                    "max_price": price_stats[1] if price_stats[1] else 0,
                    "avg_price": int(price_stats[2]) if price_stats[2] else 0
                },
                "top_prefectures": [{"prefecture": row[0], "count": row[1]} for row in top_prefs]
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)