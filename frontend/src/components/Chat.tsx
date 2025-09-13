import React, { useState, useEffect, useRef } from 'react';
import { ChatMessage as ChatMessageComponent } from './ChatMessage';
import { chatApi } from '../api/chatApi';
import { ChatMessage } from '../types/chat';
import './Chat.css';

export const Chat: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [sessionId, setSessionId] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async () => {
    if (!inputMessage.trim() && !selectedFile) return;

    setIsLoading(true);

    try {
      // ファイルアップロード（もしあれば）
      if (selectedFile) {
        const uploadResponse = await chatApi.uploadFile(selectedFile, sessionId);
        console.log('File uploaded:', uploadResponse);
        
        // ファイルアップロード通知をメッセージとして追加
        const fileMessage: ChatMessage = {
          id: `file-${Date.now()}`,
          session_id: uploadResponse.session_id,
          role: 'user',
          content: `📎 ${selectedFile.name} をアップロードしました`,
          timestamp: new Date().toISOString(),
        };
        setMessages(prev => [...prev, fileMessage]);
        setSessionId(uploadResponse.session_id);
      }

      // テキストメッセージ送信
      if (inputMessage.trim()) {
        // ユーザーメッセージをUIに即座に追加
        const userMessage: ChatMessage = {
          id: `user-${Date.now()}`,
          session_id: sessionId,
          role: 'user',
          content: inputMessage,
          timestamp: new Date().toISOString(),
        };
        setMessages(prev => [...prev, userMessage]);

        // APIに送信
        const response = await chatApi.sendMessage({
          message: inputMessage,
          session_id: sessionId || undefined,
        });

        // セッションIDを設定（初回の場合）
        if (!sessionId) {
          setSessionId(response.session_id);
        }

        // AIレスポンスを追加
        const aiMessage: ChatMessage = {
          id: response.message_id,
          session_id: response.session_id,
          role: 'assistant',
          content: response.response,
          timestamp: response.timestamp,
        };
        setMessages(prev => [...prev, aiMessage]);
      }

      // 入力をクリア
      setInputMessage('');
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (error) {
      console.error('Error sending message:', error);
      // エラーメッセージを表示
      const errorMessage: ChatMessage = {
        id: `error-${Date.now()}`,
        session_id: sessionId,
        role: 'assistant',
        content: 'エラーが発生しました。もう一度お試しください。',
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
    }
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        <h1>住まいエージェント</h1>
        <p>不動産に関するご質問をお気軽にどうぞ</p>
      </div>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="welcome-message">
            <p>こんにちは！不動産に関するご質問やご相談をお聞かせください。</p>
            <p>物件の検索、推薦、一般的な質問など、なんでもお答えします。</p>
          </div>
        )}
        
        {messages.map((message) => (
          <ChatMessageComponent key={message.id} message={message} />
        ))}
        
        {isLoading && (
          <div className="loading-message">
            <div className="typing-indicator">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-container">
        {selectedFile && (
          <div className="selected-file">
            <span>📎 {selectedFile.name}</span>
            <button onClick={() => setSelectedFile(null)}>×</button>
          </div>
        )}
        
        <div className="chat-input">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileSelect}
            style={{ display: 'none' }}
            accept="image/*,.pdf"
          />
          
          <button 
            className="file-button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isLoading}
          >
            📎
          </button>
          
          <textarea
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="メッセージを入力してください..."
            disabled={isLoading}
            rows={1}
          />
          
          <button 
            onClick={handleSendMessage}
            disabled={isLoading || (!inputMessage.trim() && !selectedFile)}
            className="send-button"
          >
            送信
          </button>
        </div>
      </div>
    </div>
  );
};