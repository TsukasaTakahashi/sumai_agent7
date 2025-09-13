import uuid
from datetime import datetime
from typing import Dict, List, Optional
from app.models import ChatSession, ChatMessage, MessageRole, AgentResponse

class ChatService:
    def __init__(self):
        self.sessions: Dict[str, ChatSession] = {}
    
    def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        now = datetime.now()
        session = ChatSession(
            session_id=session_id,
            created_at=now,
            last_activity=now,
            messages=[]
        )
        self.sessions[session_id] = session
        return session_id
    
    def get_session(self, session_id: str) -> Optional[ChatSession]:
        return self.sessions.get(session_id)
    
    def add_message(self, session_id: str, role: MessageRole, content: str, file_attachments: Optional[List[str]] = None) -> ChatMessage:
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        message = ChatMessage(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role=role,
            content=content,
            timestamp=datetime.now(),
            file_attachments=file_attachments
        )
        
        session.messages.append(message)
        session.last_activity = datetime.now()
        return message
    
    def get_messages(self, session_id: str) -> List[ChatMessage]:
        session = self.get_session(session_id)
        if not session:
            return []
        return session.messages

class AIAgentService:
    def __init__(self):
        self.agents = {
            "property_search": self._property_search_agent,
            "recommendation": self._recommendation_agent,
            "general": self._general_agent
        }
    
    def route_message(self, message: str, session_id: str) -> AgentResponse:
        # 簡単なルーティングロジック（後で改善）
        message_lower = message.lower()
        
        if any(keyword in message_lower for keyword in ["物件", "不動産", "検索", "探す"]):
            return self.agents["property_search"](message, session_id)
        elif any(keyword in message_lower for keyword in ["おすすめ", "推薦", "提案"]):
            return self.agents["recommendation"](message, session_id)
        else:
            return self.agents["general"](message, session_id)
    
    def _property_search_agent(self, message: str, session_id: str) -> AgentResponse:
        # プレースホルダー：物件検索エージェント
        return AgentResponse(
            agent_name="property_search",
            response=f"物件検索エージェントです。「{message}」について物件データベースを検索中です。現在はデモモードのため、実際の検索結果は後で実装されます。",
            confidence=0.8,
            metadata={"agent_type": "property_search", "keywords_found": ["物件", "検索"]}
        )
    
    def _recommendation_agent(self, message: str, session_id: str) -> AgentResponse:
        # プレースホルダー：推薦エージェント
        return AgentResponse(
            agent_name="recommendation",
            response=f"推薦エージェントです。「{message}」に基づいて最適な物件をお勧めします。個人の好みと条件を分析して、カスタマイズされた提案を準備中です。",
            confidence=0.85,
            metadata={"agent_type": "recommendation", "personalization": "enabled"}
        )
    
    def _general_agent(self, message: str, session_id: str) -> AgentResponse:
        # プレースホルダー：一般対話エージェント
        return AgentResponse(
            agent_name="general",
            response=f"こんにちは！不動産に関するご質問やご相談をお気軽にどうぞ。「{message}」についてお答えします。物件検索や推薦については、より具体的なキーワードを使っていただくと、専門エージェントがサポートいたします。",
            confidence=0.7,
            metadata={"agent_type": "general", "fallback": True}
        )

class FileService:
    def __init__(self):
        self.files: Dict[str, Dict] = {}
    
    def save_file_info(self, filename: str, file_size: int, session_id: str) -> str:
        file_id = str(uuid.uuid4())
        file_type = self._detect_file_type(filename)
        
        self.files[file_id] = {
            "filename": filename,
            "file_size": file_size,
            "file_type": file_type,
            "session_id": session_id,
            "upload_timestamp": datetime.now()
        }
        
        return file_id
    
    def _detect_file_type(self, filename: str) -> str:
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        if ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp']:
            return "image"
        elif ext == 'pdf':
            return "pdf"
        else:
            return "other"
    
    def get_file_info(self, file_id: str) -> Optional[Dict]:
        return self.files.get(file_id)

# グローバルサービスインスタンス
chat_service = ChatService()
ai_agent_service = AIAgentService()
file_service = FileService()