from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class FileType(str, Enum):
    IMAGE = "image"
    PDF = "pdf"
    OTHER = "other"

class ChatMessage(BaseModel):
    id: str
    session_id: str
    role: MessageRole
    content: str
    timestamp: datetime
    file_attachments: Optional[List[str]] = None

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    active_function: Optional[str] = None  # 'area', 'geo', 'advanced'
    search_radius: Optional[int] = 500  # meters

class PropertyInfo(BaseModel):
    address: str
    price: str
    years: str
    floor_plan: str
    station_info: str
    url: Optional[str] = None

class ChatResponse(BaseModel):
    message_id: str
    session_id: str
    response: str
    timestamp: datetime
    agent_used: Optional[str] = None
    property_table: Optional[List[PropertyInfo]] = None

class FileUploadRequest(BaseModel):
    session_id: Optional[str] = None
    description: Optional[str] = None

class FileUploadResponse(BaseModel):
    file_id: str
    filename: str
    file_type: FileType
    file_size: int
    upload_timestamp: datetime
    session_id: str

class ChatSession(BaseModel):
    session_id: str
    created_at: datetime
    last_activity: datetime
    messages: List[ChatMessage] = []

class AgentResponse(BaseModel):
    agent_name: str
    response: str
    confidence: float
    metadata: Optional[Dict[str, Any]] = None
    property_table: Optional[List[PropertyInfo]] = None

class ErrorResponse(BaseModel):
    error: str
    message: str
    timestamp: datetime