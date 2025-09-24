import React, { useState, useRef, useEffect } from 'react';

interface PropertyInfo {
  address: string;
  price: string;
  years: string;
  floor_plan: string;
  station_info: string;
  url?: string;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  agent?: string;
  property_table?: PropertyInfo[];
}

interface PropertyCount {
  count: number;
  filters: {
    area: string | null;
    max_price: number | null;
    min_price: number | null;
    room_type: string | null;
  };
}

// 物件テーブルコンポーネント
const PropertyTable: React.FC<{
  properties: PropertyInfo[],
  displayCount: number,
  onDisplayCountChange: (count: number) => void
}> = ({ properties, displayCount, onDisplayCountChange }) => {
  if (!properties || properties.length === 0) {
    return null;
  }

  // 表示件数に応じてデータを制限
  const displayedProperties = properties.slice(0, displayCount);

  return (
    <div style={{
      marginTop: '16px',
      backgroundColor: '#2d2d2d',
      borderRadius: '12px',
      padding: '16px',
      border: '1px solid #444'
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '12px'
      }}>
        <h3 style={{
          color: '#22c55e',
          margin: '0',
          fontSize: '16px',
          fontWeight: '600'
        }}>
          おすすめ物件一覧
        </h3>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '14px', color: '#888' }}>表示件数:</span>
          <select
            value={displayCount}
            onChange={(e) => onDisplayCountChange(Number(e.target.value))}
            style={{
              backgroundColor: '#1a1a2e',
              color: '#ffffff',
              border: '1px solid #444',
              borderRadius: '4px',
              padding: '4px 8px',
              fontSize: '14px',
              outline: 'none'
            }}
          >
            <option value={5}>5件</option>
            <option value={10}>10件</option>
            <option value={20}>20件</option>
            <option value={50}>50件</option>
          </select>
        </div>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: '14px',
          color: '#ffffff'
        }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #444' }}>
              <th style={{ padding: '8px 12px', textAlign: 'left', color: '#22c55e' }}>住所</th>
              <th style={{ padding: '8px 12px', textAlign: 'left', color: '#22c55e' }}>価格</th>
              <th style={{ padding: '8px 12px', textAlign: 'left', color: '#22c55e' }}>築年数</th>
              <th style={{ padding: '8px 12px', textAlign: 'left', color: '#22c55e' }}>間取り</th>
              <th style={{ padding: '8px 12px', textAlign: 'left', color: '#22c55e' }}>最寄り駅</th>
              <th style={{ padding: '8px 12px', textAlign: 'left', color: '#22c55e' }}>詳細</th>
            </tr>
          </thead>
          <tbody>
            {displayedProperties.map((property, index) => (
              <tr key={index} style={{
                borderBottom: '1px solid #444'
              }}>
                <td style={{ padding: '8px 12px' }}>{property.address}</td>
                <td style={{ padding: '8px 12px', fontWeight: '600', color: '#22c55e' }}>{property.price}</td>
                <td style={{ padding: '8px 12px' }}>{property.years}</td>
                <td style={{ padding: '8px 12px' }}>{property.floor_plan}</td>
                <td style={{ padding: '8px 12px' }}>{property.station_info}</td>
                <td style={{ padding: '8px 12px' }}>
                  {property.url ? (
                    <a
                      href={property.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        color: '#22c55e',
                        textDecoration: 'none',
                        fontSize: '12px',
                        padding: '4px 8px',
                        backgroundColor: '#1a1a2e',
                        borderRadius: '4px',
                        border: '1px solid #22c55e'
                      }}
                    >
                      詳細を見る
                    </a>
                  ) : (
                    <span style={{ color: '#888', fontSize: '12px' }}>-</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export const SimpleChat: React.FC = () => {
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [propertyCount, setPropertyCount] = useState<PropertyCount | null>(null);
  const [showPropertyTable, setShowPropertyTable] = useState(false);
  const [latestPropertyTable, setLatestPropertyTable] = useState<PropertyInfo[] | null>(null);
  const [displayCount, setDisplayCount] = useState(10);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 初期ロード時に物件数を取得
  useEffect(() => {
    fetchPropertyCount();
  }, []);

  const fetchPropertyCount = async (filters: Partial<PropertyCount['filters']> = {}) => {
    try {
      const params = new URLSearchParams();
      if (filters.area) params.append('area', filters.area);
      if (filters.max_price) params.append('max_price', filters.max_price.toString());
      if (filters.min_price) params.append('min_price', filters.min_price.toString());
      if (filters.room_type) params.append('room_type', filters.room_type);

      const response = await fetch(`http://127.0.0.1:8000/properties/count?${params}`);
      if (response.ok) {
        const data = await response.json();
        setPropertyCount(data);
      }
    } catch (error) {
      console.error('Failed to fetch property count:', error);
    }
  };

  // フィルタークリア機能
  const clearFilters = async () => {
    await fetchPropertyCount({});
  };

  // メッセージから地域情報を抽出する関数（リセット対応）
  const extractAreaFromMessage = (message: string): string | null => {
    // 全国リセットキーワードをチェック
    const resetKeywords = [
      '全国', '全て', 'すべて', 'クリア', 'リセット', '全体', '制限なし', '絞り込みなし',
      '全国を対象', '全国に戻', '全国で検索', '条件をクリア', '地域を解除'
    ];

    for (const keyword of resetKeywords) {
      if (message.includes(keyword)) {
        return ''; // 空文字列で全国リセットを表現
      }
    }

    // 都道府県パターン
    const prefectures = [
      '北海道', '青森県', '岩手県', '宮城県', '秋田県', '山形県', '福島県',
      '茨城県', '栃木県', '群馬県', '埼玉県', '千葉県', '東京都', '神奈川県',
      '新潟県', '富山県', '石川県', '福井県', '山梨県', '長野県', '岐阜県',
      '静岡県', '愛知県', '三重県', '滋賀県', '京都府', '大阪府', '兵庫県',
      '奈良県', '和歌山県', '鳥取県', '島根県', '岡山県', '広島県', '山口県',
      '徳島県', '香川県', '愛媛県', '高知県', '福岡県', '佐賀県', '長崎県',
      '熊本県', '大分県', '宮崎県', '鹿児島県', '沖縄県'
    ];

    // より詳細な地域指定をチェック（市区町村レベル）
    for (const pref of prefectures) {
      if (message.includes(pref)) {
        // 都道府県名以降の文字列もチェック
        const prefIndex = message.indexOf(pref);
        const afterPref = message.substring(prefIndex);

        // 市区町村が続く場合はフルパスで返す（例：千葉県船橋市、東京都世田谷区）
        const cityMatch = afterPref.match(new RegExp(`${pref}([^。、\\s]*(?:市|区|町|村))`));
        if (cityMatch) {
          const baseLocation = cityMatch[0]; // 例：東京都世田谷区

          // 東京都の特別区の場合、町名もチェック
          if (pref === '東京都' && baseLocation.includes('区')) {
            const baseIndex = afterPref.indexOf(baseLocation);
            const afterBase = afterPref.substring(baseIndex + baseLocation.length);

            // 区名の後に続く文字列から町名を抽出（で絞って等の余分な文字は除外）
            const townMatch = afterBase.match(/^([^で。、\s]+)/);
            if (townMatch && townMatch[1]) {
              // 無効な接尾語を除外
              const invalidSuffixes = ['で絞って', 'で絞る', 'で検索', 'について', 'に関して', 'の情報'];
              const townName = townMatch[1];

              if (!invalidSuffixes.some(suffix => townName.includes(suffix))) {
                return baseLocation + townName; // 例：東京都世田谷区南烏山
              }
            }
          }

          return baseLocation; // 例：千葉県船橋市、東京都世田谷区
        }

        return pref; // 都道府県のみ
      }
    }

    return null;
  };

  const handleSend = async () => {
    if (message.trim()) {
      const userMessage = message;

      // メッセージから地域情報を抽出
      const extractedArea = extractAreaFromMessage(userMessage);
      console.log('Extracted area:', extractedArea);

      // 地域関連の処理
      if (extractedArea !== null) {
        if (extractedArea === '') {
          // 空文字列の場合は全国にリセット
          await fetchPropertyCount({});
        } else {
          // 地域が指定された場合、その地域で絞り込み（前の条件をクリア）
          await fetchPropertyCount({ area: extractedArea });
        }
      }

      const newUserMessage: Message = {
        id: Date.now().toString(),
        role: 'user',
        content: userMessage
      };

      setMessages(prev => [...prev, newUserMessage]);
      setMessage('');
      setIsLoading(true);

      try {
        const requestBody = sessionId
          ? { message: userMessage, session_id: sessionId }
          : { message: userMessage };

        console.log('Sending request:', requestBody);

        const response = await fetch('http://127.0.0.1:8000/chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(requestBody),
        });

        if (response.ok) {
          const data = await response.json();
          console.log('Received response:', data);

          // セッションIDを保存（初回のみ）
          if (!sessionId) {
            setSessionId(data.session_id);
            console.log('Session ID saved:', data.session_id);
          }

          // 物件テーブルデータがあれば保存し、表示状態をリセット
          if (data.property_table && data.property_table.length > 0) {
            setLatestPropertyTable(data.property_table);
            setShowPropertyTable(false); // 新しい検索結果が来たらリセット
          }

          const aiMessage: Message = {
            id: data.message_id,
            role: 'assistant',
            content: data.response,
            agent: data.agent_used,
            property_table: data.property_table
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
        position: 'relative'
      }}>
        <h1 style={{
          margin: 0,
          fontSize: '20px',
          fontWeight: '600',
          color: '#ffffff',
          position: 'absolute',
          left: '50%',
          transform: 'translateX(-50%)'
        }}>
          SumaiAgent
        </h1>
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'flex-end',
          fontSize: '14px',
          color: '#888',
          marginLeft: 'auto'
        }}>
          <div style={{ fontWeight: '600', color: '#22c55e' }}>
            {propertyCount ? propertyCount.count.toLocaleString() : '---'} 件
          </div>
          {propertyCount?.filters && (
            <div style={{ fontSize: '12px', marginTop: '2px', display: 'flex', alignItems: 'center', gap: '4px' }}>
              {propertyCount.filters.area && (
                <span style={{
                  background: '#333',
                  padding: '2px 6px',
                  borderRadius: '4px',
                  color: '#fff'
                }}>
                  {propertyCount.filters.area}
                </span>
              )}
              {propertyCount.filters.max_price && (
                <span style={{
                  background: '#333',
                  padding: '2px 6px',
                  borderRadius: '4px',
                  color: '#fff'
                }}>
                  ≤{(propertyCount.filters.max_price / 10000).toLocaleString()}万円
                </span>
              )}
              {propertyCount.filters.room_type && (
                <span style={{
                  background: '#333',
                  padding: '2px 6px',
                  borderRadius: '4px',
                  color: '#fff'
                }}>
                  {propertyCount.filters.room_type}
                </span>
              )}
              {(propertyCount.filters.area || propertyCount.filters.max_price || propertyCount.filters.room_type) && (
                <button
                  onClick={clearFilters}
                  style={{
                    background: '#dc2626',
                    border: 'none',
                    borderRadius: '4px',
                    color: '#fff',
                    fontSize: '10px',
                    padding: '2px 4px',
                    cursor: 'pointer',
                    lineHeight: '1'
                  }}
                  title="フィルターをクリア"
                >
                  ×
                </button>
              )}
            </div>
          )}
        </div>
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
                lineHeight: '1.4',
                whiteSpace: 'pre-wrap'
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

        {/* おすすめ物件テーブル（ボタンで表示切り替え） */}
        {showPropertyTable && latestPropertyTable && latestPropertyTable.length > 0 && (
          <div style={{ padding: '0 20px' }}>
            <PropertyTable
              properties={latestPropertyTable}
              displayCount={displayCount}
              onDisplayCountChange={setDisplayCount}
            />
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

          {/* おすすめ物件を表示するボタン */}
          {latestPropertyTable && latestPropertyTable.length > 0 && (
            <button
              onClick={() => setShowPropertyTable(!showPropertyTable)}
              style={{
                padding: '12px 16px',
                borderRadius: '20px',
                border: '1px solid #22c55e',
                backgroundColor: showPropertyTable ? '#22c55e' : 'transparent',
                color: showPropertyTable ? '#ffffff' : '#22c55e',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: '600',
                whiteSpace: 'nowrap'
              }}
            >
              {showPropertyTable ? '物件を非表示' : 'おすすめ物件を表示'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};