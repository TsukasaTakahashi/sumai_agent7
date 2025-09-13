import React from 'react';
import { ChatMessage as ChatMessageType } from '../types/chat';
import './ChatMessage.css';

interface ChatMessageProps {
  message: ChatMessageType;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const isUser = message.role === 'user';
  const timestamp = new Date(message.timestamp).toLocaleTimeString('ja-JP', {
    hour: '2-digit',
    minute: '2-digit'
  });

  return (
    <div className={`message ${isUser ? 'user-message' : 'assistant-message'}`}>
      <div className="message-content">
        <div className="message-text">{message.content}</div>
        <div className="message-time">{timestamp}</div>
      </div>
    </div>
  );
};