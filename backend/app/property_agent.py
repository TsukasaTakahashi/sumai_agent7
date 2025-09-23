import sqlite3
import json
import logging
from typing import List, Dict, Optional, Tuple
from app.config import DB_PATH
from app.llm_service import llm_service
from app.models import AgentResponse

logger = logging.getLogger(__name__)

class PropertyAnalysisAgent:
    """価格と住所の複雑な分析に特化したAgent"""
    
    def __init__(self):
        self.db_path = DB_PATH
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
                
                return AgentResponse(
                    agent_name="property_analysis",
                    response=response,
                    confidence=0.95,
                    metadata={
                        "agent_type": "property_analysis",
                        "search_count": len(search_results),
                        "query_type": "direct_location_search",
                        "llm_used": True
                    }
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
                }
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

        response_prompt = [
            {
                "role": "system",
                "content": f"""あなたは不動産分析の専門家です。

【重要な指示】
- 総件数が{total_count}件です。この数字は正確です。
- {total_count}件 > 0 の場合は、必ず「物件が見つかりました」と答えてください。
- 「見当たりませんでした」や「見つかりませんでした」と答えてはいけません。

【検索結果データ】
総件数: {total_count}件
価格統計: {json.dumps(analysis_results.get('price_stats', {}), ensure_ascii=False)}
間取り分布: {json.dumps(analysis_results.get('floor_plan_stats', {}), ensure_ascii=False)}

【実際の物件例（最初の5件）】
{chr(10).join(results_summary) if results_summary else "物件データの詳細表示に問題があります"}

{f"【地域補正情報】{location_correction_msg}" if location_correction_msg else ""}

**必須回答形式（UIで読みやすいように改行を含めてください）:**

1. まず検索地域と総件数を明記
2. 価格統計（最安値、最高値、平均価格）を改行して表示
3. 間取り分布を改行して表示
4. 物件例を番号付きリストで改行して表示
5. 最後に簡潔なまとめ

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

以上の情報から、この地域には様々な間取りと価格帯の物件が存在していることが分かります。

**検索結果の状態: {"物件あり" if has_results else "物件なし"}**
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
            params.append(f"%{hierarchy['prefecture']}%")

        elif hierarchy['level'] == 'city' and hierarchy['city']:
            if hierarchy['prefecture']:
                conditions.append("pref LIKE ?")
                params.append(f"%{hierarchy['prefecture']}%")
            conditions.append("municipality_city_name LIKE ?")
            params.append(f"%{hierarchy['city']}%")

        elif hierarchy['level'] == 'ward' and hierarchy['ward']:
            if hierarchy['prefecture']:
                conditions.append("pref LIKE ?")
                params.append(f"%{hierarchy['prefecture']}%")
            if hierarchy['city']:
                conditions.append("municipality_city_name LIKE ?")
                params.append(f"%{hierarchy['city']}%")

            # 東京都の特別区は municipality_name を使用
            if hierarchy['prefecture'] == '東京都':
                conditions.append("municipality_name LIKE ?")
                params.append(f"%{hierarchy['ward']}%")
            else:
                conditions.append("ward_name LIKE ?")
                params.append(f"%{hierarchy['ward']}%")

        elif hierarchy['level'] == 'town' and hierarchy['town']:
            if hierarchy['prefecture']:
                conditions.append("pref LIKE ?")
                params.append(f"%{hierarchy['prefecture']}%")
            if hierarchy['city']:
                conditions.append("municipality_city_name LIKE ?")
                params.append(f"%{hierarchy['city']}%")
            if hierarchy['ward']:
                # 東京都の特別区は municipality_name を使用
                if hierarchy['prefecture'] == '東京都':
                    conditions.append("municipality_name LIKE ?")
                    params.append(f"%{hierarchy['ward']}%")
                else:
                    conditions.append("ward_name LIKE ?")
                    params.append(f"%{hierarchy['ward']}%")
            conditions.append("town_name LIKE ?")
            params.append(f"%{hierarchy['town']}%")

        # フォールバック：addressでの検索
        if not conditions:
            conditions.append("address LIKE ?")
            params.append(f"%{hierarchy.get('prefecture', '') + hierarchy.get('city', '') + hierarchy.get('ward', '') + hierarchy.get('town', '')}%")

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
                        else:
                            fallback_result_list = [{'_total_count': fallback_total_count, '_search_method': 'address_fallback'}]

                        return fallback_result_list

                # 結果を辞書のリストに変換し、総件数を追加
                result_list = [dict(row) for row in results]
                if result_list:
                    result_list[0]['_total_count'] = total_count
                    result_list[0]['_search_method'] = 'hierarchical'
                else:
                    result_list = [{'_total_count': total_count, '_search_method': 'hierarchical'}]

                return result_list

        except Exception as e:
            logger.error(f"Hierarchical location search error: {e}")
            return self._legacy_location_search(message)

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
                    else:
                        result_list = [{'_total_count': total_count, '_search_method': 'exact_address'}]

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

        # サンプル物件（最初の5件）
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