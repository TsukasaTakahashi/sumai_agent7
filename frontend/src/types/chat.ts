export interface ChatMessage {
  id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  file_attachments?: string[] | null;
}

export interface ChatRequest {
  message: string;
  session_id?: string;
}

export interface ChatResponse {
  message_id: string;
  session_id: string;
  response: string;
  timestamp: string;
  agent_used?: string;
}

export interface FileUploadResponse {
  file_id: string;
  filename: string;
  file_type: 'image' | 'pdf' | 'other';
  file_size: number;
  upload_timestamp: string;
  session_id: string;
}