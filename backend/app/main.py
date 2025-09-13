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
        agent_response = ai_agent_service.route_message(request.message, session_id)
        
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
            agent_used=agent_response.agent_name
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)