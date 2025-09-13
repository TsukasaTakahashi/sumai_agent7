import uuid
from datetime import datetime
from typing import Dict, List, Optional
from app.models import ChatSession, ChatMessage, MessageRole, AgentResponse
from app.llm_service import llm_service

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
    
    async def route_message(self, message: str, session_id: str) -> AgentResponse:
        # 簡単なルーティングロジック（後で改善）
        message_lower = message.lower()
        
        if any(keyword in message_lower for keyword in ["物件", "不動産", "検索", "探す"]):
            return await self.agents["property_search"](message, session_id)
        elif any(keyword in message_lower for keyword in ["おすすめ", "推薦", "提案"]):
            return await self.agents["recommendation"](message, session_id)
        else:
            return await self.agents["general"](message, session_id)
    
    async def _property_search_agent(self, message: str, session_id: str) -> AgentResponse:
        # OpenAI APIを使用した物件検索エージェント
        # セッション履歴を取得して文脈を含める
        session_messages = self._get_session_context(session_id)
        prompt = llm_service.create_property_search_prompt(message, session_messages)
        
        llm_response = await llm_service.get_completion(
            messages=prompt,
            model="gpt-3.5-turbo",
            temperature=0.7
        )
        
        if llm_response:
            return AgentResponse(
                agent_name="property_search",
                response=llm_response,
                confidence=0.9,
                metadata={"agent_type": "property_search", "llm_used": True}
            )
        else:
            # フォールバック応答
            return AgentResponse(
                agent_name="property_search",
                response="申し訳ございません。現在、物件検索サービスに一時的な問題が発生しています。しばらく時間をおいて再度お試しください。",
                confidence=0.3,
                metadata={"agent_type": "property_search", "llm_used": False, "fallback": True}
            )
    
    async def _recommendation_agent(self, message: str, session_id: str) -> AgentResponse:
        # OpenAI APIを使用した推薦エージェント
        # セッション履歴を取得して文脈を含める
        session_messages = self._get_session_context(session_id)
        prompt = llm_service.create_recommendation_prompt(message, session_messages)
        
        llm_response = await llm_service.get_completion(
            messages=prompt,
            model="gpt-3.5-turbo",
            temperature=0.8
        )
        
        if llm_response:
            return AgentResponse(
                agent_name="recommendation",
                response=llm_response,
                confidence=0.9,
                metadata={"agent_type": "recommendation", "llm_used": True}
            )
        else:
            # フォールバック応答
            return AgentResponse(
                agent_name="recommendation",
                response="申し訳ございません。現在、推薦サービスに一時的な問題が発生しています。しばらく時間をおいて再度お試しください。",
                confidence=0.3,
                metadata={"agent_type": "recommendation", "llm_used": False, "fallback": True}
            )
    
    async def _general_agent(self, message: str, session_id: str) -> AgentResponse:
        # OpenAI APIを使用した一般対話エージェント
        # セッション履歴を取得して文脈を含める
        session_messages = self._get_session_context(session_id)
        prompt = llm_service.create_general_prompt(message, session_messages)
        
        llm_response = await llm_service.get_completion(
            messages=prompt,
            model="gpt-3.5-turbo",
            temperature=0.7
        )
        
        if llm_response:
            return AgentResponse(
                agent_name="general",
                response=llm_response,
                confidence=0.8,
                metadata={"agent_type": "general", "llm_used": True}
            )
        else:
            # フォールバック応答
            return AgentResponse(
                agent_name="general",
                response="申し訳ございません。現在、システムに一時的な問題が発生しています。しばらく時間をおいて再度お試しください。基本的なご質問でしたら、お気軽にお聞かせください。",
                confidence=0.3,
                metadata={"agent_type": "general", "llm_used": False, "fallback": True}
            )
    
    def _get_session_context(self, session_id: str) -> List[Dict[str, str]]:
        """セッション履歴を取得してOpenAI API形式に変換"""
        from app.services import chat_service
        import logging
        
        logger = logging.getLogger(__name__)
        
        session_messages = chat_service.get_messages(session_id)
        context_messages = []
        
        logger.info(f"Session {session_id} has {len(session_messages)} messages")
        
        # 最新の10件のメッセージを取得（トークン制限を考慮）
        # 現在のメッセージは除外して、過去のメッセージのみを取得
        if len(session_messages) > 1:
            recent_messages = session_messages[:-1][-10:] if len(session_messages) > 11 else session_messages[:-1]
        else:
            recent_messages = []
        
        logger.info(f"Using {len(recent_messages)} recent messages for context")
        
        for msg in recent_messages:
            role = "user" if msg.role == MessageRole.USER else "assistant"
            context_messages.append({
                "role": role,
                "content": msg.content
            })
            logger.info(f"Added context: {role} - {msg.content[:50]}...")
        
        return context_messages

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