import openai
from typing import Optional, Dict, Any
import logging
from app.config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        if not OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not set. LLM functionality will be disabled.")
            self.client = None
        else:
            self.client = openai.OpenAI(api_key=OPENAI_API_KEY)
            logger.info("OpenAI client initialized successfully")

    async def get_completion(
        self, 
        messages: list, 
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Optional[str]:
        """OpenAI APIでチャット完了を取得"""
        if not self.client:
            logger.error("OpenAI client not initialized")
            return None

        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            content = response.choices[0].message.content
            logger.info(f"OpenAI API call successful. Model: {model}, Tokens: {response.usage.total_tokens}")
            return content

        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            return None
        except openai.RateLimitError as e:
            logger.error(f"OpenAI rate limit error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error calling OpenAI API: {e}")
            return None

    def create_property_search_prompt(self, user_message: str, session_messages: list = None) -> list:
        """物件検索エージェント用のプロンプト作成"""
        messages = [
            {
                "role": "system",
                "content": """あなたは不動産物件検索の専門エージェントです。
ユーザーからの物件検索に関する質問に対して、以下の点を考慮して回答してください：

1. 予算、立地、間取り、設備などの希望条件を整理する
2. 現在はデモ環境のため、実際の物件データベース検索は後で実装予定であることを説明
3. 具体的な検索条件の提案やアドバイスを提供
4. 不動産購入・賃貸のポイントや注意事項を説明
5. 親切で専門的な口調で回答する
6. 過去の会話履歴がある場合は、それを考慮して一貫性のある回答をする

回答は日本語で、親しみやすく分かりやすい文体で行ってください。"""
            }
        ]
        
        # セッション履歴を追加
        if session_messages:
            messages.extend(session_messages)
        
        # 現在のユーザーメッセージを追加
        messages.append({
            "role": "user", 
            "content": user_message
        })
        
        return messages

    def create_recommendation_prompt(self, user_message: str, session_messages: list = None) -> list:
        """推薦エージェント用のプロンプト作成"""
        messages = [
            {
                "role": "system",
                "content": """あなたは不動産推薦の専門エージェントです。
ユーザーのライフスタイルや希望に基づいて、最適な物件タイプや立地を推薦します。

以下の点を考慮して回答してください：

1. ユーザーの家族構成、職業、趣味、ライフスタイルを考慮
2. 予算に応じた現実的な提案
3. 将来の生活変化も見据えた長期的な視点
4. 立地の特徴やメリット・デメリットの説明
5. 具体的で実用的なアドバイス
6. 過去の会話履歴がある場合は、それを考慮して一貫性のある推薦をする

現在はデモ環境ですが、実際の物件情報と連携した推薦システムを構築予定です。
回答は日本語で、温かみのある専門的なアドバイスを心がけてください。"""
            }
        ]
        
        # セッション履歴を追加
        if session_messages:
            messages.extend(session_messages)
        
        # 現在のユーザーメッセージを追加
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        return messages

    def create_general_prompt(self, user_message: str, session_messages: list = None) -> list:
        """一般対話エージェント用のプロンプト作成"""
        messages = [
            {
                "role": "system", 
                "content": """あなたはSumaiAgentの一般対話エージェントです。
不動産に関する一般的な質問や雑談に対応します。

以下の点を心がけて回答してください：

1. 不動産に関する基本的な知識や用語の説明
2. 住まい探しのプロセスや手続きの説明
3. 一般的な住居に関する相談やアドバイス
4. より専門的な質問の場合は、物件検索や推薦エージェントの利用を促す
5. 親しみやすく親切な対応
6. 過去の会話履歴がある場合は、それを考慮して一貫性のある対話をする

専門的な物件検索や推薦が必要な場合は、「物件を探している」「おすすめの物件を教えて」などのキーワードでより専門的なエージェントをご利用いただけることをお伝えください。

回答は日本語で、フレンドリーで分かりやすい文体で行ってください。"""
            }
        ]
        
        # セッション履歴を追加
        if session_messages:
            messages.extend(session_messages)
        
        # 現在のユーザーメッセージを追加
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        return messages

# グローバルインスタンス
llm_service = LLMService()