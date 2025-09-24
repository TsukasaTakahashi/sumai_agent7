import sqlite3
import json
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from app.config import DB_PATH
from app.llm_service import llm_service
from app.models import AgentResponse

logger = logging.getLogger(__name__)

class PropertyRecommendationScorer:
    """物件のおすすめ度を計算するクラス（将来的な拡張性を考慮した設計）"""

    def __init__(self):
        self.scoring_methods = [
            self._score_by_listing_date,
            # 将来的に追加される評価メソッド:
            # self._score_by_price_value,
            # self._score_by_location_popularity,
            # self._score_by_property_features,
        ]

    def calculate_recommendation_score(self, property_data: Dict) -> float:
        """物件のおすすめ度を計算（0-100のスケール）"""
        total_score = 0.0
        max_possible_score = 0.0

        for scoring_method in self.scoring_methods:
            try:
                score, weight = scoring_method(property_data)
                total_score += score * weight
                max_possible_score += 100 * weight
                logger.debug(f"Scoring method {scoring_method.__name__}: score={score}, weight={weight}")
            except Exception as e:
                logger.warning(f"Scoring method {scoring_method.__name__} failed: {e}")
                continue

        if max_possible_score == 0:
            return 0.0

        # 0-100のスケールに正規化
        normalized_score = (total_score / max_possible_score) * 100
        return min(100.0, max(0.0, normalized_score))

    def _score_by_listing_date(self, property_data: Dict) -> Tuple[float, float]:
        """掲載日による評価（新しいほど高スコア）"""
        try:
            last_listed_date = property_data.get('last_listed_date')
            if not last_listed_date:
                return 50.0, 1.0  # デフォルトスコア、重み1.0

            # 日付文字列をパース
            if isinstance(last_listed_date, str):
                try:
                    listed_date = datetime.strptime(last_listed_date, '%Y-%m-%d')
                except ValueError:
                    # 異なる日付フォーマットの場合の処理
                    try:
                        listed_date = datetime.strptime(last_listed_date.split()[0], '%Y-%m-%d')
                    except ValueError:
                        return 50.0, 1.0
            else:
                return 50.0, 1.0

            current_date = datetime.now()
            days_since_listing = (current_date - listed_date).days

            # スコア計算ロジック：
            # 0日前（今日）: 100点
            # 7日前: 80点
            # 30日前: 50点
            # 90日前: 20点
            # 180日以上前: 10点
            if days_since_listing <= 0:
                score = 100.0
            elif days_since_listing <= 7:
                score = 100.0 - (days_since_listing * 2.86)  # 7日で20点減
            elif days_since_listing <= 30:
                score = 80.0 - ((days_since_listing - 7) * 1.30)  # 23日で30点減
            elif days_since_listing <= 90:
                score = 50.0 - ((days_since_listing - 30) * 0.50)  # 60日で30点減
            elif days_since_listing <= 180:
                score = 20.0 - ((days_since_listing - 90) * 0.11)  # 90日で10点減
            else:
                score = 10.0

            weight = 1.0  # 現在の重み（将来的に調整可能）
            return max(0.0, score), weight

        except Exception as e:
            logger.warning(f"Listing date scoring failed: {e}")
            return 50.0, 1.0

    # 将来追加される評価メソッドの例:
    # def _score_by_price_value(self, property_data: Dict) -> Tuple[float, float]:
    #     """価格対価値による評価"""
    #     # 実装例: 周辺相場との比較、㎡単価評価など
    #     pass
    #
    # def _score_by_location_popularity(self, property_data: Dict) -> Tuple[float, float]:
    #     """立地人気度による評価"""
    #     # 実装例: 駅からの距離、周辺施設、治安指数など
    #     pass

class PropertyAnalysisAgent:
    """価格と住所の複雑な分析に特化したAgent"""

    def __init__(self):
        self.db_path = DB_PATH
        self.recommendation_scorer = PropertyRecommendationScorer()
        self.session_data = {}  # セッション毎のデータ保存
        
    async def analyze_query(self, message: str, session_id: str) -> AgentResponse:
        """ユーザーの複雑な問い合わせを分析して適切な検索を実行"""
        try:
            # セッション履歴を取得
            session_context = self._get_session_context(session_id)
            
            # 件数のみの問い合わせかチェック
            if self._is_count_only_query(message):
                total_count = self._get_total_count()
                response = f"物件のデータベースには合計{total_count:,}件の物件が登録されています。"
                return AgentResponse(
                    agent_name="property_analysis",
                    response=response,
                    confidence=1.0,
                    metadata={
                        "agent_type": "property_analysis",
                        "query_type": "count_only",
                        "total_count": total_count
                    }
                )
            
            # エリア関連クエリの前処理
            location_preprocessing = await self._preprocess_location_query(message, session_context)
            
            # 直接的な地域クエリかチェック（LLM解析をスキップして確実に動作させる）
            direct_location_result = self._check_direct_location_query(message)
            if direct_location_result:
                search_results = direct_location_result
                analysis_results = self._analyze_search_results(search_results, {"query_type": "location_analysis"})
                
                # セッションデータを保存
                self._save_session_data(session_id, {
                    "last_query": message,
                    "last_search_results": search_results,
                    "last_analysis": analysis_results,
                    "location_preprocessing": location_preprocessing
                })
                
                # AI応答生成
                response = await self._generate_ai_response(
                    message, search_results, analysis_results, session_context, location_preprocessing
                )

                # 物件テーブルデータを生成
                property_table_data = []
                if search_results and analysis_results.get('total_count', 0) > 0:
                    recommended_properties = self._get_recommended_properties(search_results, limit=50)
                    property_table_data = self._format_property_table_data(recommended_properties)

                return AgentResponse(
                    agent_name="property_analysis",
                    response=response,
                    confidence=0.95,
                    metadata={
                        "agent_type": "property_analysis",
                        "search_count": len(search_results),
                        "query_type": "direct_location_search",
                        "llm_used": True
                    },
                    property_table=property_table_data
                )
            
            # 問い合わせ内容を分析（前処理結果を含める）
            query_analysis = await self._analyze_user_query(message, session_context, location_preprocessing)
            
            # 検索実行
            search_results = self._execute_complex_search(query_analysis)
            
            # 結果の統計分析
            analysis_results = self._analyze_search_results(search_results, query_analysis)
            
            # セッションデータを保存（検索結果を次回の会話で利用）
            self._save_session_data(session_id, {
                "last_query": message,
                "last_search_results": search_results,
                "last_analysis": analysis_results,
                "location_preprocessing": location_preprocessing
            })
            
            # AI応答生成
            response = await self._generate_ai_response(
                message, search_results, analysis_results, session_context, location_preprocessing
            )

            # 物件テーブルデータを生成（最大50件まで取得）
            property_table_data = []
            if search_results and analysis_results.get('total_count', 0) > 0:
                recommended_properties = self._get_recommended_properties(search_results, limit=50)
                property_table_data = self._format_property_table_data(recommended_properties)

            return AgentResponse(
                agent_name="property_analysis",
                response=response,
                confidence=0.95,
                metadata={
                    "agent_type": "property_analysis",
                    "search_count": len(search_results),
                    "query_type": query_analysis.get("query_type", "complex"),
                    "llm_used": True,
                    "location_correction": location_preprocessing.get("correction_made", False)
                },
                property_table=property_table_data
            )
            
        except Exception as e:
            logger.error(f"PropertyAnalysisAgent error: {e}")
            return AgentResponse(
                agent_name="property_analysis",
                response="申し訳ございません。物件分析中にエラーが発生しました。再度お試しください。",
                confidence=0.3,
                metadata={"agent_type": "property_analysis", "error": str(e)}
            )
    
    async def _analyze_user_query(self, message: str, session_context: List[Dict], location_preprocessing: Dict = None) -> Dict:
        """ユーザーの問い合わせ内容をAIで分析"""
        analysis_prompt = [
            {
                "role": "system",
                "content": """あなたは不動産検索クエリの分析専門家です。
ユーザーの質問を分析して、以下のJSON形式で回答してください：

{
    "query_type": "price_analysis|location_analysis|market_analysis|comparison|complex_search",
    "price_conditions": {
        "min_price": 数値またはnull,
        "max_price": 数値またはnull,
        "price_range": "価格帯の説明"
    },
    "location_conditions": {
        "prefectures": ["都道府県名のリスト"],
        "cities": ["市区町村名のリスト"],
        "areas": ["地域名のリスト"],
        "stations": ["駅名のリスト"]
    },
    "other_conditions": {
        "floor_plan": "間取り条件",
        "years": "築年数条件",
        "traffic": "交通条件"
    },
    "analysis_type": "statistical|comparison|trend|recommendation"
}

重要な指示：
- 地域名、市区町村名、駅名を必ず適切に抽出してください
- 価格は万円単位で入力された場合は適切に変換してください
- 「何件」「件数」などの問い合わせには必ず location_analysis または complex_search を設定してください
- 駅名が含まれている場合は必ず stations フィールドに追加してください"""
            }
        ]
        
        # セッション履歴を追加
        if session_context:
            analysis_prompt.extend(session_context)
        
        # 地域前処理情報があれば含める
        user_content = f"この質問を分析してください: {message}"
        if location_preprocessing and location_preprocessing.get("normalized_locations"):
            user_content += f"\n\n地域情報の前処理結果: {json.dumps(location_preprocessing, ensure_ascii=False)}"
        
        analysis_prompt.append({
            "role": "user",
            "content": user_content
        })
        
        ai_response = await llm_service.get_completion(
            messages=analysis_prompt,
            temperature=0.3
        )
        
        try:
            if ai_response is None:
                logger.error("LLM service returned None - API key likely not set")
                # LLMが使えない場合のフォールバック（基本的な地域解析）
                return self._fallback_query_analysis(message)
            
            result = json.loads(ai_response)
            logger.info(f"Query analysis result: {result}")
            return result
        except Exception as e:
            logger.error(f"Query analysis JSON parse error: {e}, response: {ai_response}")
            # フォールバック
            return self._fallback_query_analysis(message)
    
    def _execute_complex_search(self, query_analysis: Dict) -> List[Dict]:
        """複雑な検索条件でデータベース検索を実行"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # 基本クエリ
                base_query = "SELECT * FROM BUY_data_integrated WHERE 1=1"
                params = []
                conditions = []
                
                # 価格条件
                price_cond = query_analysis.get("price_conditions", {})
                if price_cond.get("min_price"):
                    conditions.append("CAST(mi_price AS INTEGER) >= ?")
                    params.append(price_cond["min_price"])
                if price_cond.get("max_price"):
                    conditions.append("CAST(mi_price AS INTEGER) <= ?")
                    params.append(price_cond["max_price"])
                
                # 住所条件（拡張版：複数カラムでの曖昧検索）
                location_cond = query_analysis.get("location_conditions", {})
                
                # 都道府県での検索
                if location_cond.get("prefectures"):
                    pref_conditions = []
                    for pref in location_cond["prefectures"]:
                        # pref カラムと address カラムの両方で検索
                        pref_conditions.append("(pref LIKE ? OR address LIKE ?)")
                        params.extend([f"%{pref}%", f"%{pref}%"])
                    
                    if pref_conditions:
                        conditions.append(f"({' OR '.join(pref_conditions)})")
                
                # 市区町村・エリアでの検索
                if location_cond.get("cities") or location_cond.get("areas"):
                    areas = (location_cond.get("cities", []) + location_cond.get("areas", []))
                    area_conditions = []
                    for area in areas:
                        # address, pref, traffic1 カラムで曖昧検索
                        area_conditions.append("(address LIKE ? OR pref LIKE ? OR traffic1 LIKE ?)")
                        params.extend([f"%{area}%", f"%{area}%", f"%{area}%"])
                    
                    if area_conditions:
                        conditions.append(f"({' OR '.join(area_conditions)})")
                
                # 駅名での検索
                if location_cond.get("stations"):
                    station_conditions = []
                    for station in location_cond["stations"]:
                        # traffic1 カラムで駅名検索
                        station_conditions.append("traffic1 LIKE ?")
                        params.append(f"%{station}%")
                    
                    if station_conditions:
                        conditions.append(f"({' OR '.join(station_conditions)})")
                
                # その他の条件
                other_cond = query_analysis.get("other_conditions", {})
                if other_cond.get("floor_plan"):
                    conditions.append("floor_plan LIKE ?")
                    params.append(f"%{other_cond['floor_plan']}%")
                
                # 条件を組み合わせ
                if conditions:
                    base_query += " AND " + " AND ".join(conditions)
                
                # まず総件数を取得
                count_query = "SELECT COUNT(*) as total_count FROM BUY_data_integrated WHERE 1=1"
                if conditions:
                    count_query += " AND " + " AND ".join(conditions)

                logger.info(f"Executing count query: {count_query}")
                logger.info(f"Parameters: {params}")

                cursor.execute(count_query, params)
                total_count = cursor.fetchone()[0]

                # 次にサンプルデータを取得（制限付き）
                sample_query = "SELECT * FROM BUY_data_integrated WHERE 1=1"
                if conditions:
                    sample_query += " AND " + " AND ".join(conditions)

                logger.info(f"Executing sample query: {sample_query}")
                cursor.execute(sample_query, params)
                results = cursor.fetchall()

                logger.info(f"Total count: {total_count}, Sample results: {len(results)}")

                # 辞書形式に変換し、total_countを追加
                result_list = [dict(row) for row in results]

                # 結果の最初に総件数情報を追加
                if result_list:
                    result_list[0]['_total_count'] = total_count
                else:
                    # 結果が0件の場合も総件数を返す
                    result_list = [{'_total_count': total_count}]

                return result_list
                
        except Exception as e:
            logger.error(f"Search execution error: {e}")
            return []
    
    def _analyze_search_results(self, results: List[Dict], query_analysis: Dict) -> Dict:
        """検索結果の統計分析"""
        if not results:
            return {"total_count": 0}
        
        # 総件数を取得（_total_countが設定されている場合はそれを使用）
        total_count = len(results)
        if results and '_total_count' in results[0]:
            total_count = results[0]['_total_count']

        analysis = {
            "total_count": total_count,
            "price_stats": {},
            "location_stats": {},
            "floor_plan_stats": {}
        }
        
        # 価格統計
        prices = []
        for result in results:
            try:
                price = int(result.get("mi_price", 0))
                if price > 0:
                    prices.append(price)
            except:
                continue
        
        if prices:
            analysis["price_stats"] = {
                "min_price": min(prices),
                "max_price": max(prices),
                "avg_price": sum(prices) / len(prices),
                "count": len(prices)
            }
        
        # 都道府県分布
        pref_count = {}
        for result in results:
            pref = result.get("pref", "")
            if pref:
                pref_count[pref] = pref_count.get(pref, 0) + 1
        analysis["location_stats"]["prefecture_distribution"] = dict(sorted(pref_count.items(), key=lambda x: x[1], reverse=True)[:10])
        
        # 間取り分布
        plan_count = {}
        for result in results:
            plan = result.get("floor_plan", "")
            if plan:
                plan_count[plan] = plan_count.get(plan, 0) + 1
        analysis["floor_plan_stats"]["distribution"] = dict(sorted(plan_count.items(), key=lambda x: x[1], reverse=True)[:10])
        
        return analysis
    
    def _extract_search_area_from_message(self, message: str) -> str:
        """ユーザーメッセージから検索対象の地域を抽出"""
        import re

        # 東京都のパターン
        if "東京都" in message or "東京" in message:
            return "東京都"
        # 船橋のパターン
        elif "船橋法典" in message:
            return "船橋法典駅周辺"
        elif "船橋" in message:
            return "船橋市"
        # その他の都道府県パターン
        else:
            # 県名を抽出する簡単なパターンマッチング
            patterns = [r'([^\s]+県)', r'([^\s]+府)', r'([^\s]+都)', r'([^\s]+道)']
            for pattern in patterns:
                match = re.search(pattern, message)
                if match:
                    return match.group(1)

        return "指定地域"

    async def _generate_ai_response(self, user_message: str, search_results: List[Dict],
                                   analysis_results: Dict, session_context: List[Dict], location_preprocessing: Dict = None) -> str:
        """検索結果と分析結果を基にAI応答を生成"""

        # 総件数を取得
        total_count = analysis_results.get('total_count', 0)

        # 検索結果のサマリーを作成（最初の5件）
        sample_results = search_results[:5]
        results_summary = []

        if total_count == 0:
            # 0件の場合の専用メッセージ
            results_summary.append("該当する物件が見つかりませんでした")
        else:
            for result in sample_results:
                price = result.get("mi_price", "不明")
                address = result.get("address", "不明")
                floor_plan = result.get("floor_plan", "不明")
                results_summary.append(f"・{address} {floor_plan} {price}円")

        # 地域補正メッセージの作成
        location_correction_msg = ""
        if location_preprocessing and location_preprocessing.get("correction_made"):
            original = location_preprocessing.get("original_input", "")
            corrected = location_preprocessing.get("normalized_locations", [])
            if corrected:
                location_correction_msg = f"\n※「{original}」を「{', '.join(corrected)}」で検索しました。"

        # デバッグ: LLMに渡すデータを確認
        logger.info(f"LLM prompt data - Total count: {total_count}, Results length: {len(search_results)}")
        logger.info(f"Sample results summary: {results_summary}")

        # ユーザーの質問から検索対象の地域を抽出
        search_area = self._extract_search_area_from_message(user_message)

        # データ整合性の確認
        has_results = total_count > 0 and len(results_summary) > 0

        # 件数チェック：100件を超える場合の絞り込み推奨
        refinement_suggestion = ""
        if total_count > 100:
            refinement_suggestion = f"""

【絞り込み推奨】
検索結果が{total_count}件と多いため、より具体的な条件での絞り込みをお勧めします。
以下の条件で絞り込んでみてください：
- より具体的な地域名（○○町、○○駅周辺など）
- 価格帯（例：5000万円以下、1億円以下など）
- 間取り（例：3LDK、4LDKなど）
- 築年数（例：築10年以内など）

もう少し絞り込んでいただけると、より適切な物件をご提案できます。"""

        response_prompt = [
            {
                "role": "system",
                "content": f"""あなたは不動産分析の専門家です。

【重要な指示】
- 総件数が{total_count}件です。この数字は正確です。
- {total_count}件 = 0 の場合は、「該当する物件が見つかりませんでした」と明確に答えてください。
- {total_count}件 > 0 の場合は、必ず「物件が見つかりました」と答えてください。
- {total_count}件 > 100の場合は、必ず絞り込み推奨メッセージを含めてください。

【検索結果データ】
総件数: {total_count}件
価格統計: {json.dumps(analysis_results.get('price_stats', {}), ensure_ascii=False)}
間取り分布: {json.dumps(analysis_results.get('floor_plan_stats', {}), ensure_ascii=False)}

【実際の物件例（最初の5件）】
{chr(10).join(results_summary)}

{f"【地域補正情報】{location_correction_msg}" if location_correction_msg else ""}

**必須回答形式（UIで読みやすいように改行を含めてください）:**

1. まず検索地域と総件数を明記
2. 価格統計（最安値、最高値、平均価格）を改行して表示
3. 間取り分布を改行して表示
4. 物件例を番号付きリストで改行して表示
5. {total_count}件 > 100の場合は絞り込み推奨メッセージを必ず含める
6. 最後に簡潔なまとめ

以下の形式で回答してください：

{search_area}に関する不動産物件の検索結果は以下の通りです。

【検索結果データ】
- 総件数: X件
- 価格統計: 最安値 X円、最高値 X円、平均価格 X円
- 主な間取り: 3LDK (X件)、2LDK (X件) など

【実際の物件例】
1. 住所 間取り 価格
2. 住所 間取り 価格
...

{refinement_suggestion}

以上の情報から、この地域には様々な間取りと価格帯の物件が存在していることが分かります。

**検索結果の状態: {"物件あり" if has_results else "物件なし"}**
**件数チェック: {"絞り込み推奨" if total_count > 100 else "適切な件数"}**
"""
            }
        ]
        
        # セッション履歴を追加
        if session_context:
            response_prompt.extend(session_context)
        
        response_prompt.append({
            "role": "user",
            "content": user_message
        })
        
        llm_response = await llm_service.get_completion(
            messages=response_prompt,
            temperature=0.7
        )
        
        # LLMが使えない場合のフォールバック応答
        if llm_response is None:
            logger.error("LLM service unavailable for response generation, using fallback")
            return self._generate_fallback_response(user_message, search_results, analysis_results, location_preprocessing)

        # 応答の妥当性チェック
        if total_count > 0 and ("見当たりませんでした" in llm_response or "見つかりませんでした" in llm_response):
            logger.warning(f"LLM generated incorrect response for {total_count} results, using fallback")
            return self._generate_fallback_response(user_message, search_results, analysis_results, location_preprocessing)

        return llm_response
    
    def _normalize_location_text(self, text: str) -> str:
        """地域名の表記揺れを正規化"""
        if not text:
            return text

        # よくある表記揺れを修正
        normalized = text.replace('ヶ', 'ケ')  # 保土ヶ谷区 → 保土ケ谷区
        normalized = normalized.replace('が', 'ガ')  # 世田が谷 → 世田ガ谷
        normalized = normalized.replace('ヴ', 'ブ')  # ヴィラ → ビラ

        return normalized

    async def _preprocess_location_query(self, message: str, session_context: List[Dict]) -> Dict:
        """地域クエリの前処理（タイポ補正・正規化）"""
        preprocessing_prompt = [
            {
                "role": "system",
                "content": """あなたは地域名の正規化と補正の専門家です。
ユーザーの入力から地域名を抽出し、タイポや表記揺れを補正して、以下のJSON形式で回答してください：

{
    "has_location": true/false,
    "original_input": "元の入力から抽出した地域名",
    "normalized_locations": ["正規化された地域名のリスト"],
    "correction_made": true/false,
    "confidence": 0.0-1.0
}

補正ルール：
- ひらがな/カタカナ → 漢字に変換（例：「かながわけん」→「神奈川県」）
- 略称 → 正式名称（例：「神奈川」→「神奈川県」）
- タイポ補正（例：「かんんがわけん」→「神奈川県」）
- 表記揺れの統一（例：「保土ヶ谷区」→「保土ケ谷区」、「ヶ」→「ケ」、「が」→「ガ」）
- 一般的な表記揺れの統一

地域名が含まれていない場合は has_location: false を返してください。"""
            }
        ]
        
        # セッション履歴を追加
        if session_context:
            preprocessing_prompt.extend(session_context[-3:])  # 最新の3件のみ
        
        preprocessing_prompt.append({
            "role": "user",
            "content": f"この入力から地域名を抽出・補正してください: {message}"
        })
        
        try:
            ai_response = await llm_service.get_completion(
                messages=preprocessing_prompt,
                temperature=0.2
            )
            
            result = json.loads(ai_response)
            return result
        except Exception as e:
            logger.error(f"Location preprocessing error: {e}")
            return {
                "has_location": False,
                "original_input": "",
                "normalized_locations": [],
                "correction_made": False,
                "confidence": 0.0
            }
    
    def _save_session_data(self, session_id: str, data: Dict):
        """セッションデータを保存"""
        if session_id not in self.session_data:
            self.session_data[session_id] = {}
        
        self.session_data[session_id].update(data)
        
        # 古いデータをクリーンアップ（最新の5セッションのみ保持）
        if len(self.session_data) > 5:
            oldest_session = min(self.session_data.keys())
            del self.session_data[oldest_session]
    
    def _get_session_data(self, session_id: str) -> Dict:
        """セッションデータを取得"""
        return self.session_data.get(session_id, {})
    
    def _identify_location_hierarchy(self, location_text: str) -> Dict:
        """地域の階層レベルを識別"""
        import re
        hierarchy = {
            'prefecture': None,
            'city': None,
            'ward': None,
            'town': None,
            'level': None
        }

        # 都道府県パターン（県、都、府、道で終わる）
        prefecture_patterns = [
            r'(北海道)',
            r'(.+県)',
            r'(.+都)',
            r'(.+府)'
        ]

        for pattern in prefecture_patterns:
            match = re.search(pattern, location_text)
            if match:
                hierarchy['prefecture'] = match.group(1)
                hierarchy['level'] = 'prefecture'

                # 市区町村が続く場合
                after_pref = location_text[match.end():]
                if after_pref:
                    # 市レベル
                    city_match = re.search(r'([^区町村]+市)', after_pref)
                    if city_match:
                        hierarchy['city'] = city_match.group(1)
                        hierarchy['level'] = 'city'

                        # 区レベル
                        after_city = after_pref[city_match.end():]
                        if after_city:
                            ward_match = re.search(r'([^町村]+区)', after_city)
                            if ward_match:
                                hierarchy['ward'] = ward_match.group(1)
                                hierarchy['level'] = 'ward'

                                # 町レベル
                                after_ward = after_city[ward_match.end():]
                                if after_ward:
                                    town_match = re.search(r'([^。、\\s]{2,})', after_ward)
                                    if town_match:
                                        town_name = town_match.group(1)
                                        # 不適切な語尾を除外
                                        invalid_suffixes = ['で絞って', 'で絞る', 'について', 'に関して', 'の情報', 'のデータ']
                                        is_valid = True
                                        for suffix in invalid_suffixes:
                                            if town_name.endswith(suffix):
                                                town_name = town_name[:-len(suffix)]
                                                if len(town_name) < 2:
                                                    is_valid = False
                                                break
                                        # 数字のみや短すぎる場合は除外
                                        if is_valid and not town_name.isdigit() and len(town_name) >= 2:
                                            hierarchy['town'] = town_name
                                            hierarchy['level'] = 'town'
                    else:
                        # 区が直接続く場合（政令指定都市以外）
                        ward_match = re.search(r'([^町村]+区)', after_pref)
                        if ward_match:
                            hierarchy['ward'] = ward_match.group(1)
                            hierarchy['level'] = 'ward'

                            # 区の後に町名が続く場合をチェック
                            after_ward = after_pref[ward_match.end():]
                            if after_ward:
                                town_match = re.search(r'([^。、\\s]{2,})', after_ward)
                                if town_match:
                                    town_name = town_match.group(1)
                                    # 不適切な語尾を除外
                                    invalid_suffixes = ['で絞って', 'で絞る', 'について', 'に関して', 'の情報', 'のデータ']
                                    is_valid = True
                                    for suffix in invalid_suffixes:
                                        if town_name.endswith(suffix):
                                            town_name = town_name[:-len(suffix)]
                                            if len(town_name) < 2:
                                                is_valid = False
                                            break
                                    # 数字のみや短すぎる場合は除外
                                    if is_valid and not town_name.isdigit() and len(town_name) >= 2:
                                        hierarchy['town'] = town_name
                                        hierarchy['level'] = 'town'
                        else:
                            # 町村レベル（町村以外の地名も含む）
                            town_match = re.search(r'([^。、\\s]{2,})', after_pref)
                            if town_match:
                                town_name = town_match.group(1)
                                # 不適切な語尾を除外
                                invalid_suffixes = ['で絞って', 'で絞る', 'について', 'に関して', 'の情報', 'のデータ']
                                is_valid = True
                                for suffix in invalid_suffixes:
                                    if town_name.endswith(suffix):
                                        town_name = town_name[:-len(suffix)]
                                        if len(town_name) < 2:
                                            is_valid = False
                                        break
                                # 数字のみや短すぎる場合は除外
                                if is_valid and not town_name.isdigit() and len(town_name) >= 2:
                                    hierarchy['town'] = town_name
                                    hierarchy['level'] = 'town'
                break

        return hierarchy

    def _build_hierarchical_query(self, hierarchy: Dict) -> tuple:
        """階層に応じたクエリを構築"""
        conditions = []
        params = []

        if hierarchy['level'] == 'prefecture' and hierarchy['prefecture']:
            conditions.append("pref LIKE ?")
            params.append(f"%{self._normalize_location_text(hierarchy['prefecture'])}%")

        elif hierarchy['level'] == 'city' and hierarchy['city']:
            if hierarchy['prefecture']:
                conditions.append("pref LIKE ?")
                params.append(f"%{self._normalize_location_text(hierarchy['prefecture'])}%")
            conditions.append("municipality_name LIKE ?")
            params.append(f"%{self._normalize_location_text(hierarchy['city'])}%")

        elif hierarchy['level'] == 'ward' and hierarchy['ward']:
            if hierarchy['prefecture']:
                conditions.append("pref LIKE ?")
                params.append(f"%{self._normalize_location_text(hierarchy['prefecture'])}%")
            if hierarchy['city']:
                conditions.append("municipality_name LIKE ?")
                params.append(f"%{self._normalize_location_text(hierarchy['city'])}%")

            # 東京都の特別区は municipality_name を使用
            if hierarchy['prefecture'] == '東京都':
                conditions.append("municipality_name LIKE ?")
                params.append(f"%{self._normalize_location_text(hierarchy['ward'])}%")
            else:
                conditions.append("ward_name LIKE ?")
                params.append(f"%{self._normalize_location_text(hierarchy['ward'])}%")

        elif hierarchy['level'] == 'town' and hierarchy['town']:
            if hierarchy['prefecture']:
                conditions.append("pref LIKE ?")
                params.append(f"%{self._normalize_location_text(hierarchy['prefecture'])}%")
            if hierarchy['city']:
                conditions.append("municipality_name LIKE ?")
                params.append(f"%{self._normalize_location_text(hierarchy['city'])}%")
            if hierarchy['ward']:
                # 東京都の特別区は municipality_name を使用
                if hierarchy['prefecture'] == '東京都':
                    conditions.append("municipality_name LIKE ?")
                    params.append(f"%{self._normalize_location_text(hierarchy['ward'])}%")
                else:
                    conditions.append("ward_name LIKE ?")
                    params.append(f"%{self._normalize_location_text(hierarchy['ward'])}%")
            conditions.append("town_name LIKE ?")
            params.append(f"%{self._normalize_location_text(hierarchy['town'])}%")

        # フォールバック：addressでの検索
        if not conditions:
            normalized_location = (
                self._normalize_location_text(hierarchy.get('prefecture', '')) +
                self._normalize_location_text(hierarchy.get('city', '')) +
                self._normalize_location_text(hierarchy.get('ward', '')) +
                self._normalize_location_text(hierarchy.get('town', ''))
            )
            conditions.append("address LIKE ?")
            params.append(f"%{normalized_location}%")

        where_clause = " AND ".join(conditions)
        return where_clause, params

    def _check_direct_location_query(self, message: str) -> List[Dict]:
        """階層的地域検索による直接検索"""
        try:
            # まず完全一致での検索を試す（ユーザー入力をそのまま使用）
            exact_match_results = self._try_exact_address_search(message.strip())
            if exact_match_results:
                return exact_match_results

            # 地域階層を識別
            hierarchy = self._identify_location_hierarchy(message)

            if not hierarchy['level']:
                # 従来のキーワード検索にフォールバック
                return self._legacy_location_search(message)

            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # 階層的クエリを構築
                where_clause, params = self._build_hierarchical_query(hierarchy)

                # 正確なカウントを取得
                count_query = f"SELECT COUNT(*) as total_count FROM BUY_data_integrated WHERE {where_clause} AND mi_price IS NOT NULL AND mi_price != '' AND mi_price != '0'"
                logger.info(f"Hierarchical count query: {count_query}, Params: {params}")
                cursor.execute(count_query, params)
                total_count = cursor.fetchone()[0]

                # サンプルデータを取得
                sample_query = f"SELECT * FROM BUY_data_integrated WHERE {where_clause} AND mi_price IS NOT NULL AND mi_price != '' AND mi_price != '0'"
                logger.info(f"Hierarchical sample query: {sample_query}, Params: {params}")
                cursor.execute(sample_query, params)
                results = cursor.fetchall()

                logger.info(f"Hierarchical search - Total count: {total_count}, Sample results: {len(results)}")

                # 階層検索で結果が0件の場合、address列での部分一致検索にフォールバック
                if total_count == 0:
                    logger.info("Hierarchical search returned 0 results, falling back to address search")
                    # 元のメッセージから検索キーワードを作成
                    search_term = f"{hierarchy.get('prefecture', '')}{hierarchy.get('city', '')}{hierarchy.get('ward', '')}{hierarchy.get('town', '')}"
                    if search_term:
                        fallback_count_query = "SELECT COUNT(*) as total_count FROM BUY_data_integrated WHERE address LIKE ? AND mi_price IS NOT NULL AND mi_price != '' AND mi_price != '0'"
                        fallback_params = [f"%{search_term}%"]
                        logger.info(f"Fallback count query: {fallback_count_query}, Params: {fallback_params}")
                        cursor.execute(fallback_count_query, fallback_params)
                        fallback_total_count = cursor.fetchone()[0]

                        fallback_sample_query = "SELECT * FROM BUY_data_integrated WHERE address LIKE ? AND mi_price IS NOT NULL AND mi_price != '' AND mi_price != '0'"
                        logger.info(f"Fallback sample query: {fallback_sample_query}, Params: {fallback_params}")
                        cursor.execute(fallback_sample_query, fallback_params)
                        fallback_results = cursor.fetchall()

                        logger.info(f"Fallback address search - Total count: {fallback_total_count}, Sample results: {len(fallback_results)}")

                        # フォールバック結果を返す
                        fallback_result_list = [dict(row) for row in fallback_results]
                        if fallback_result_list:
                            fallback_result_list[0]['_total_count'] = fallback_total_count
                            fallback_result_list[0]['_search_method'] = 'address_fallback'
                        # 0件の場合は空のリストを返す（ダミーデータを作成しない）

                        # 重複削除を適用
                        fallback_result_list = self._remove_duplicates(fallback_result_list)
                        return fallback_result_list

                # 結果を辞書のリストに変換し、総件数を追加
                result_list = [dict(row) for row in results]
                if result_list:
                    result_list[0]['_total_count'] = total_count
                    result_list[0]['_search_method'] = 'hierarchical'
                # 0件の場合は空のリストを返す（ダミーデータを作成しない）

                # 重複削除を適用
                result_list = self._remove_duplicates(result_list)
                return result_list

        except Exception as e:
            logger.error(f"Hierarchical location search error: {e}")
            return self._legacy_location_search(message)

    def _remove_duplicates(self, results: List[Dict]) -> List[Dict]:
        """重複物件を削除し、おすすめ度順にソートする"""
        if not results:
            return results

        # 重複チェック用のキーとなるフィールド
        seen = set()
        unique_results = []

        for result in results:
            # 重複判定キー：住所、価格、間取り
            duplicate_key = (
                result.get("address", ""),
                result.get("mi_price", ""),
                result.get("floor_plan", "")
            )

            if duplicate_key not in seen:
                seen.add(duplicate_key)
                # おすすめ度スコアを計算
                recommendation_score = self.recommendation_scorer.calculate_recommendation_score(result)
                result['_recommendation_score'] = recommendation_score
                unique_results.append(result)
            else:
                logger.debug(f"Duplicate property filtered: {duplicate_key}")

        # おすすめ度順にソート（スコア高い順）
        unique_results.sort(key=lambda x: x.get('_recommendation_score', 0), reverse=True)

        # 重複削除後の総件数情報を更新
        if results and unique_results and '_total_count' in results[0]:
            # 重複削除後の実際の件数を総件数として設定
            unique_results[0]['_total_count'] = len(unique_results)
            if '_search_method' in results[0]:
                unique_results[0]['_search_method'] = results[0]['_search_method']
        elif unique_results:
            # メタデータがない場合は新しく追加
            unique_results[0]['_total_count'] = len(unique_results)
            unique_results[0]['_search_method'] = 'duplicate_removed'

        logger.info(f"Duplicate removal and scoring: {len(results)} -> {len(unique_results)} properties")
        if unique_results:
            scores = [f"{r.get('_recommendation_score', 0):.1f}" for r in unique_results[:3]]
            logger.info(f"Top 3 recommendation scores: {scores}")

        return unique_results

    def _try_exact_address_search(self, query: str) -> List[Dict]:
        """ユーザー入力をそのまま使用した完全一致検索"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # ユーザー入力をそのままLIKE検索で使用
                search_pattern = f"%{query}%"

                # 正確なカウントを取得
                count_query = "SELECT COUNT(*) as total_count FROM BUY_data_integrated WHERE address LIKE ? AND mi_price IS NOT NULL AND mi_price != '' AND mi_price != '0'"
                logger.info(f"Exact address search count query: {count_query}, Pattern: {search_pattern}")
                cursor.execute(count_query, [search_pattern])
                total_count = cursor.fetchone()[0]

                # 結果が存在する場合のみサンプルデータを取得
                if total_count > 0:
                    sample_query = "SELECT * FROM BUY_data_integrated WHERE address LIKE ? AND mi_price IS NOT NULL AND mi_price != '' AND mi_price != '0'"
                    logger.info(f"Exact address search sample query: {sample_query}, Pattern: {search_pattern}")
                    cursor.execute(sample_query, [search_pattern])
                    results = cursor.fetchall()

                    logger.info(f"Exact address search - Total count: {total_count}, Sample results: {len(results)}")

                    # 結果を辞書のリストに変換し、総件数を追加
                    result_list = [dict(row) for row in results]
                    if result_list:
                        result_list[0]['_total_count'] = total_count
                        result_list[0]['_search_method'] = 'exact_address'
                    # 0件の場合は空のリストを返す（ダミーデータを作成しない）

                    # 重複削除を適用
                    result_list = self._remove_duplicates(result_list)
                    return result_list

                return []

        except Exception as e:
            logger.error(f"Exact address search error: {e}")
            return []

    def _legacy_location_search(self, message: str) -> List[Dict]:
        """従来の地域検索（フォールバック用）"""
        message_lower = message.lower()

        # 特定のキーワードパターンでの検索
        search_patterns = [
            ("東京", "%東京%"),
            ("船橋法典", "%船橋法典%"),
            ("船橋", "%船橋%"),
            ("千葉", "%千葉%")
        ]

        for keyword, pattern in search_patterns:
            if keyword in message_lower:
                try:
                    with sqlite3.connect(self.db_path) as conn:
                        conn.row_factory = sqlite3.Row
                        cursor = conn.cursor()

                        # 正確なカウントを取得
                        count_query = "SELECT COUNT(*) as total_count FROM BUY_data_integrated WHERE address LIKE ? AND mi_price IS NOT NULL AND mi_price != '' AND mi_price != '0'"
                        cursor.execute(count_query, [pattern])
                        total_count = cursor.fetchone()[0]

                        # サンプルデータを取得
                        query = "SELECT * FROM BUY_data_integrated WHERE address LIKE ? AND mi_price IS NOT NULL AND mi_price != '' AND mi_price != '0'"
                        params = [pattern]

                        logger.info(f"Legacy search - SQL: {query}, Params: {params}")
                        cursor.execute(query, params)
                        results = cursor.fetchall()
                        logger.info(f"Legacy search - Total count: {total_count}, Sample results: {len(results)}")

                        # 結果を辞書のリストに変換し、総件数を追加
                        result_list = [dict(row) for row in results]
                        if result_list:
                            result_list[0]['_total_count'] = total_count
                        else:
                            result_list = [{'_total_count': total_count}]

                        # 重複削除を適用
                        result_list = self._remove_duplicates(result_list)
                        return result_list

                except Exception as e:
                    logger.error(f"Legacy location search error: {e}")
                    continue

        return []
    
    def _fallback_query_analysis(self, message: str) -> Dict:
        """LLMが使えない場合の基本的なクエリ解析"""
        message_lower = message.lower()
        analysis = {
            "query_type": "complex_search",
            "price_conditions": {},
            "location_conditions": {
                "prefectures": [],
                "cities": [],
                "areas": [],
                "stations": []
            },
            "other_conditions": {},
            "analysis_type": "statistical"
        }
        
        # 基本的な地域キーワード検出
        if "船橋法典" in message_lower:
            analysis["location_conditions"]["stations"] = ["船橋法典"]
            analysis["query_type"] = "location_analysis"
        elif "船橋" in message_lower:
            analysis["location_conditions"]["cities"] = ["船橋"]
            analysis["query_type"] = "location_analysis"
        elif "千葉" in message_lower:
            analysis["location_conditions"]["prefectures"] = ["千葉"]
            analysis["query_type"] = "location_analysis"
        
        # 基本的な価格キーワード検出
        import re
        price_patterns = [
            r'(\d+)万円以下',
            r'(\d+)万円以上',
            r'(\d+)円以下',
            r'(\d+)円以上'
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, message_lower)
            if match:
                price = int(match.group(1))
                if "万円" in pattern:
                    price *= 10000
                
                if "以下" in pattern:
                    analysis["price_conditions"]["max_price"] = price
                elif "以上" in pattern:
                    analysis["price_conditions"]["min_price"] = price
                
                analysis["query_type"] = "complex_search"
        
        logger.info(f"Fallback query analysis: {analysis}")
        return analysis

    def _get_recommended_properties(self, search_results, limit=10):
        """おすすめ物件を取得（価格、築年数、間取りを考慮したソート）"""
        if not search_results:
            return []

        # メタデータを除外
        properties = [prop for prop in search_results if '_total_count' not in prop]

        # スコア計算とソート
        def calculate_score(prop):
            score = 0

            # 価格スコア（安い方が高スコア、but 極端に安いものは除外）
            try:
                price = int(prop.get('mi_price', 0))
                if 1000000 <= price <= 200000000:  # 100万〜2億円の範囲
                    # 価格が平均的な範囲内でより安いものを優先
                    if price <= 50000000:  # 5000万円以下
                        score += 30
                    elif price <= 80000000:  # 8000万円以下
                        score += 20
                    else:
                        score += 10
            except:
                score -= 10  # 価格不明はペナルティ

            # 築年数スコア（新しい方が高スコア）
            try:
                years = int(prop.get('years', 999))
                if years <= 5:
                    score += 25
                elif years <= 10:
                    score += 20
                elif years <= 20:
                    score += 15
                elif years <= 30:
                    score += 10
                else:
                    score += 5
            except:
                score += 5  # 築年数不明は中程度

            # 間取りスコア（人気の間取りを優先）
            floor_plan = prop.get('floor_plan', '')
            if '3LDK' in floor_plan or '4LDK' in floor_plan:
                score += 15
            elif '2LDK' in floor_plan or '1LDK' in floor_plan:
                score += 10
            elif 'LDK' in floor_plan:
                score += 5

            # 駅情報があるかどうか（traffic1を優先）
            if prop.get('traffic1') or prop.get('station_name') or prop.get('dp1'):
                score += 10

            return score

        # スコアでソートして上位を取得
        properties_with_score = [(prop, calculate_score(prop)) for prop in properties]
        properties_with_score.sort(key=lambda x: x[1], reverse=True)

        return [prop for prop, score in properties_with_score[:limit]]

    def _extract_station_info_from_traffic(self, traffic1_data):
        """traffic1フィールドから駅情報を抽出"""
        if not traffic1_data:
            return ""

        import json
        import re

        try:
            # JSONの配列として解析
            if isinstance(traffic1_data, str):
                traffic_list = json.loads(traffic1_data)
            else:
                traffic_list = traffic1_data

            if not traffic_list or len(traffic_list) == 0:
                return ""

            # 最初の交通情報を使用
            traffic_info = traffic_list[0]

            # パターン1: 「駅名」徒歩X分
            pattern1 = r'「([^」]+)」徒歩(\d+)分'
            match1 = re.search(pattern1, traffic_info)
            if match1:
                station_name = match1.group(1)
                walk_time = match1.group(2)
                return f"{station_name}駅徒歩{walk_time}分"

            # パターン2: 「駅名」バスX分停歩Y分
            pattern2 = r'「([^」]+)」バス(\d+)分停歩(\d+)分'
            match2 = re.search(pattern2, traffic_info)
            if match2:
                station_name = match2.group(1)
                bus_time = match2.group(2)
                walk_time = match2.group(3)
                return f"{station_name}駅バス{bus_time}分+徒歩{walk_time}分"

            # パターン3: 路線名を含む形式から駅名を抽出
            pattern3 = r'([^「]*線)?「([^」]+)」'
            match3 = re.search(pattern3, traffic_info)
            if match3:
                station_name = match3.group(2)
                # 徒歩時間を探す
                walk_match = re.search(r'徒歩(\d+)分', traffic_info)
                if walk_match:
                    walk_time = walk_match.group(1)
                    return f"{station_name}駅徒歩{walk_time}分"
                else:
                    return f"{station_name}駅"

            return ""

        except (json.JSONDecodeError, IndexError, AttributeError) as e:
            # JSONパースエラーの場合はフォールバック
            return ""

    def _extract_station_info(self, dp1_text):
        """dp1フィールドから駅情報を抽出（フォールバック用）"""
        if not dp1_text:
            return ""

        import re
        # 「駅名」徒歩X分 のパターンを抽出
        station_pattern = r'「([^」]+)駅?」徒歩(\d+)分'
        match = re.search(station_pattern, dp1_text)
        if match:
            station_name = match.group(1)
            walk_time = match.group(2)
            return f"{station_name}駅徒歩{walk_time}分"

        # その他のパターンも試す
        station_pattern2 = r'([^「」\s]+駅).*?徒歩(\d+)分'
        match2 = re.search(station_pattern2, dp1_text)
        if match2:
            station_name = match2.group(1)
            walk_time = match2.group(2)
            return f"{station_name}駅徒歩{walk_time}分"

        return ""

    def _format_property_table_data(self, properties):
        """物件情報を構造化データとして整形"""
        if not properties:
            return []

        property_list = []

        for prop in properties:
            # 住所（短縮）- 都道府県と市を除いて区以降のみ表示
            address = prop.get('address', '住所不明')
            import re
            match = re.search(r'([^都道府県市]+(?:区|町|村).*)', address)
            if match:
                address = match.group(1)

            if len(address) > 25:
                address = address[:22] + "..."

            # 価格
            try:
                price = int(prop.get('mi_price', 0))
                price_display = f"{price//10000:,}万円"
            except:
                price_display = "価格不明"

            # 築年数
            try:
                years = int(prop.get('years', 0))
                if years == 0:
                    years_display = "新築"
                else:
                    years_display = f"築{years}年"
            except:
                years_display = "築年数不明"

            # 間取り
            floor_plan = prop.get('floor_plan', '間取り不明')

            # 最寄り駅情報（traffic1を優先）
            station_info = ""

            # まずtraffic1から抽出を試す
            traffic1_station = self._extract_station_info_from_traffic(prop.get('traffic1', ''))
            if traffic1_station:
                station_info = traffic1_station
            else:
                # traffic1がない場合はstation_nameを使用
                if prop.get('station_name'):
                    station_info = f"{prop.get('station_name')}駅"
                else:
                    # dp1から駅情報を抽出（フォールバック）
                    dp1_station = self._extract_station_info(prop.get('dp1', ''))
                    if dp1_station:
                        station_info = dp1_station

            if not station_info:
                station_info = "駅情報なし"

            # URL
            url = prop.get('url', '')

            property_info = {
                "address": address,
                "price": price_display,
                "years": years_display,
                "floor_plan": floor_plan,
                "station_info": station_info,
                "url": url
            }
            property_list.append(property_info)

        return property_list

    def _generate_fallback_response(self, user_message: str, search_results: List[Dict],
                                   analysis_results: Dict, location_preprocessing: Dict = None) -> str:
        """LLMが使えない場合のフォールバック応答生成"""
        total_count = analysis_results.get('total_count', 0)
        price_stats = analysis_results.get('price_stats', {})
        floor_plan_stats = analysis_results.get('floor_plan_stats', {})

        if total_count == 0:
            return f"申し訳ございませんが、指定された条件に合う物件は見つかりませんでした。検索条件を変更して再度お試しください。"

        response_parts = []

        # 地域補正メッセージ
        if location_preprocessing and location_preprocessing.get("correction_made"):
            original = location_preprocessing.get("original_input", "")
            corrected = location_preprocessing.get("normalized_locations", [])
            if corrected:
                response_parts.append(f"「{original}」を「{', '.join(corrected)}」で検索しました。")

        # 検索結果の明確な表示
        search_area = self._extract_search_area_from_message(user_message)
        response_parts.append(f"{search_area}に関する不動産物件の検索結果は以下の通りです。")
        response_parts.append(f"")  # 空行
        response_parts.append(f"【検索結果データ】")
        response_parts.append(f"- 総件数: {total_count:,}件")

        # 価格統計があれば追加
        if price_stats:
            min_price = price_stats.get('min_price')
            max_price = price_stats.get('max_price')
            avg_price = price_stats.get('avg_price')
            count = price_stats.get('count')

            if min_price and max_price and avg_price:
                min_price_man = int(min_price / 10000)
                max_price_man = int(max_price / 10000)
                avg_price_man = int(avg_price / 10000)
                response_parts.append(f"- 価格統計: 最安値 {min_price_man:,}万円、最高値 {max_price_man:,}万円、平均価格 {avg_price_man:,}万円")

        # 間取り分布があれば追加（上位5つのみ）
        if floor_plan_stats and floor_plan_stats.get('distribution'):
            distribution = floor_plan_stats['distribution']
            top_plans = list(distribution.items())[:5]
            plan_str = "、".join([f"{plan} ({count}件)" for plan, count in top_plans])
            response_parts.append(f"- 主な間取り: {plan_str}")

        # おすすめ物件（テキストの物件例は残す）
        if search_results and len(search_results) > 0:
            response_parts.append(f"")  # 空行
            response_parts.append(f"【実際の物件例】")
            for i, result in enumerate(search_results[:5], 1):
                address = result.get("address", "住所不明")
                price = result.get("mi_price", "価格不明")
                floor_plan = result.get("floor_plan", "間取り不明")
                try:
                    price_man = int(int(price) / 10000)
                    price_display = f"{price_man:,}万円"
                except:
                    price_display = f"{price}円"
                response_parts.append(f"{i}. {address} {floor_plan} {price_display}")

        response_parts.append(f"")  # 空行

        # 100件を超える場合の絞り込み推奨メッセージ
        if total_count > 100:
            response_parts.append(f"【絞り込み推奨】")
            response_parts.append(f"検索結果が{total_count:,}件と多いため、より具体的な条件での絞り込みをお勧めします。")
            response_parts.append(f"以下の条件で絞り込んでみてください：")
            response_parts.append(f"- より具体的な地域名（○○町、○○駅周辺など）")
            response_parts.append(f"- 価格帯（例：5000万円以下、1億円以下など）")
            response_parts.append(f"- 間取り（例：3LDK、4LDKなど）")
            response_parts.append(f"- 築年数（例：築10年以内など）")
            response_parts.append(f"")
            response_parts.append(f"もう少し絞り込んでいただけると、より適切な物件をご提案できます。")
            response_parts.append(f"")  # 空行

        response_parts.append(f"以上の情報から、{search_area}には様々な間取りと価格帯の物件が存在していることが分かります。")

        return "\n".join(response_parts)
    
    def _is_count_only_query(self, message: str) -> bool:
        """件数のみの問い合わせかどうかを判定"""
        message_lower = message.lower()
        count_keywords = [
            "何件", "件数", "総数", "合計", "全体", "全部で", "トータル",
            "登録されて", "データベース", "db", "全物件", "物件数"
        ]
        
        # 件数を聞く質問パターン
        count_patterns = [
            any(keyword in message_lower for keyword in count_keywords),
            ("物件" in message_lower and ("何" in message_lower or "いくつ" in message_lower)),
            ("データベース" in message_lower and ("何" in message_lower or "いくつ" in message_lower))
        ]
        
        # 複雑な条件が含まれていないかチェック（価格、住所、間取りなどの条件）
        complex_keywords = [
            "価格", "円", "万円", "億円", "予算", "相場", "安い", "高い",
            "都道府県", "市", "区", "エリア", "地域", "駅", "沿線",
            "間取り", "ldk", "dk", "築年", "新築", "中古"
        ]
        has_complex_conditions = any(keyword in message_lower for keyword in complex_keywords)
        
        return any(count_patterns) and not has_complex_conditions
    
    def _get_total_count(self) -> int:
        """データベースの総物件数を取得"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM BUY_data_integrated")
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Failed to get total count: {e}")
            return 0
    
    def _get_session_context(self, session_id: str) -> List[Dict[str, str]]:
        """セッション履歴を取得（簡易版）"""
        # 実装は既存のservices.pyと同様
        try:
            from app.services import chat_service
            from app.models import MessageRole
            
            session_messages = chat_service.get_messages(session_id)
            context_messages = []
            
            # 最新の5件のメッセージを取得
            recent_messages = session_messages[-5:] if len(session_messages) > 5 else session_messages
            
            for msg in recent_messages:
                role = "user" if msg.role == MessageRole.USER else "assistant"
                context_messages.append({
                    "role": role,
                    "content": msg.content
                })
            
            return context_messages
        except:
            return []

# グローバルインスタンス
property_analysis_agent = PropertyAnalysisAgent()