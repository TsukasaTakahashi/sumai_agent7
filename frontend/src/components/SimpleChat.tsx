import React, { useState, useRef, useEffect } from 'react';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  agent?: string;
}

export const SimpleChat: React.FC = () => {
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (message.trim()) {
      const userMessage = message;
      const newUserMessage: Message = {
        id: Date.now().toString(),
        role: 'user',
        content: userMessage
      };
      
      setMessages(prev => [...prev, newUserMessage]);
      setMessage('');
      setIsLoading(true);

      try {
        const response = await fetch('http://127.0.0.1:8000/chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ message: userMessage }),
        });

        if (response.ok) {
          const data = await response.json();
          const aiMessage: Message = {
            id: data.message_id,
            role: 'assistant',
            content: data.response,
            agent: data.agent_used
          };
          setMessages(prev => [...prev, aiMessage]);
        } else {
          const errorMessage: Message = {
            id: Date.now().toString(),
            role: 'assistant',
            content: 'APIの応答に失敗しました'
          };
          setMessages(prev => [...prev, errorMessage]);
        }
      } catch (error) {
        const errorMessage: Message = {
          id: Date.now().toString(),
          role: 'assistant',
          content: `エラー: ${error}`
        };
        setMessages(prev => [...prev, errorMessage]);
      } finally {
        setIsLoading(false);
      }
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div style={{ 
      height: '100vh', 
      display: 'flex', 
      flexDirection: 'column',
      backgroundColor: '#1a1a2e',
      color: '#ffffff',
      fontFamily: 'system-ui, -apple-system, sans-serif'
    }}>
      {/* ヘッダー */}
      <div style={{
        padding: '16px 20px',
        borderBottom: '1px solid #333',
        backgroundColor: '#16213e',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        <h1 style={{ 
          margin: 0, 
          fontSize: '20px', 
          fontWeight: '600',
          color: '#ffffff'
        }}>
          SumaiAgent
        </h1>
      </div>

      {/* メッセージエリア */}
      <div style={{ 
        flex: 1, 
        overflow: 'auto', 
        padding: '20px',
        display: 'flex',
        flexDirection: 'column'
      }}>
        {messages.length === 0 ? (
          <div style={{ 
            textAlign: 'center', 
            marginTop: '50px',
            color: '#888'
          }}>
            <p>SumaiAgentへようこそ</p>
            <p>不動産に関するご質問をお聞かせください</p>
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} style={{ 
              marginBottom: '16px',
              display: 'flex',
              justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start'
            }}>
              <div style={{
                maxWidth: '80%',
                padding: '12px 16px',
                borderRadius: '18px',
                backgroundColor: msg.role === 'user' ? '#22c55e' : '#2d2d2d',
                color: '#ffffff',
                wordWrap: 'break-word',
                lineHeight: '1.4'
              }}>
                {msg.role === 'assistant' && msg.agent && (
                  <div style={{ 
                    fontSize: '12px', 
                    opacity: 0.7, 
                    marginBottom: '4px',
                    color: '#888'
                  }}>
                    {msg.agent} エージェント
                  </div>
                )}
                {msg.content}
              </div>
            </div>
          ))
        )}
        
        {isLoading && (
          <div style={{ 
            marginBottom: '16px',
            display: 'flex',
            justifyContent: 'flex-start'
          }}>
            <div style={{
              padding: '12px 16px',
              borderRadius: '18px',
              backgroundColor: '#2d2d2d',
              color: '#888'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span>●</span>
                <span>●</span>
                <span>●</span>
                <span>応答中...</span>
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>
      
      {/* フッター - 入力エリア */}
      <div style={{
        padding: '20px',
        borderTop: '1px solid #333',
        backgroundColor: '#16213e'
      }}>
        <div style={{ 
          display: 'flex', 
          gap: '12px',
          alignItems: 'flex-end',
          maxWidth: '800px',
          margin: '0 auto'
        }}>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="メッセージを入力してください..."
            disabled={isLoading}
            style={{ 
              flex: 1, 
              padding: '12px 16px',
              borderRadius: '20px',
              border: '1px solid #444',
              backgroundColor: '#2d2d2d',
              color: '#ffffff',
              resize: 'none',
              fontSize: '16px',
              minHeight: '50px',
              maxHeight: '150px',
              outline: 'none'
            }}
            rows={1}
          />
          <button 
            onClick={handleSend} 
            disabled={isLoading || !message.trim()}
            style={{ 
              padding: '12px 20px',
              borderRadius: '20px',
              border: 'none',
              backgroundColor: message.trim() && !isLoading ? '#22c55e' : '#444',
              color: '#ffffff',
              cursor: message.trim() && !isLoading ? 'pointer' : 'not-allowed',
              fontSize: '16px',
              fontWeight: '600',
              minWidth: '80px'
            }}
          >
            {isLoading ? '送信中' : '送信'}
          </button>
        </div>
      </div>
    </div>
  );
};