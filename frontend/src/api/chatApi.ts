import { ChatRequest, ChatResponse, FileUploadResponse, ChatMessage } from '../types/chat';

const API_BASE_URL = 'http://127.0.0.1:8001';

export const chatApi = {
  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    const response = await fetch(`${API_BASE_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`Chat API error: ${response.statusText}`);
    }

    return response.json();
  },

  async getChatHistory(sessionId: string): Promise<{ session_id: string; messages: ChatMessage[] }> {
    const response = await fetch(`${API_BASE_URL}/chat/${sessionId}/messages`);

    if (!response.ok) {
      throw new Error(`Chat history API error: ${response.statusText}`);
    }

    return response.json();
  },

  async uploadFile(file: File, sessionId?: string, description?: string): Promise<FileUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    if (sessionId) formData.append('session_id', sessionId);
    if (description) formData.append('description', description);

    const response = await fetch(`${API_BASE_URL}/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`File upload API error: ${response.statusText}`);
    }

    return response.json();
  },

  async getSessions(): Promise<{ sessions: Array<{ session_id: string; created_at: string; last_activity: string; message_count: number }> }> {
    const response = await fetch(`${API_BASE_URL}/sessions`);

    if (!response.ok) {
      throw new Error(`Sessions API error: ${response.statusText}`);
    }

    return response.json();
  }
};