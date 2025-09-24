#!/usr/bin/env python3
"""
ヘッダー件数とAgent返答件数の一致性検証スクリプト

使用方法:
python test_count_consistency.py

検証対象:
- 地域名検索における件数の一致性
- ヘッダー（get_filtered_count）とAgent（_search_by_area）の整合性
"""

import sys
import os
import asyncio
import json
import sqlite3
from typing import Dict, List

# プロジェクトルートをパスに追加
sys.path.append('/Users/tsukasa/Arealinks/Apps7/sumai_agent6/backend')

from app.database import database_service
from app.property_agent import PropertyAnalysisAgent
from app.config import DB_PATH

class CountConsistencyTester:
    def __init__(self):
        self.agent = PropertyAnalysisAgent()
        self.test_cases = [
            "東京",
            "神奈川県",
            "神奈川",
            "東京都中央区",
            "東京都中央区晴海",
            "千葉県船橋市上山町",
            "神奈川県川崎市",
            "神奈川県川崎市幸区",
            "神奈川県川崎市幸区幸町"
        ]

    def get_header_count(self, area: str) -> int:
        """ヘッダー側の件数を取得（get_filtered_count）"""
        return database_service.get_filtered_count(area=area)

    async def get_agent_count(self, area: str) -> int:
        """Agent側の件数を取得（_search_by_area経由）"""
        # 地域検索を実行
        search_results = self.agent._search_by_area(area, limit=10)

        # _total_countを取得
        if search_results and '_total_count' in search_results[0]:
            return search_results[0]['_total_count']
        else:
            return 0

    def get_raw_db_count(self, area: str) -> Dict[str, int]:
        """生のDB件数を取得（デバッグ用）"""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()

                # 単純なCOUNT
                cursor.execute("SELECT COUNT(*) FROM BUY_data_integrated WHERE address LIKE ?", [f"%{area}%"])
                raw_count = cursor.fetchone()[0]

                # 有効価格のみ
                cursor.execute("""
                    SELECT COUNT(*) FROM BUY_data_integrated
                    WHERE address LIKE ?
                    AND mi_price IS NOT NULL
                    AND mi_price != ''
                    AND mi_price != '0'
                """, [f"%{area}%"])
                valid_price_count = cursor.fetchone()[0]

                # 重複削除＋有効価格
                cursor.execute("""
                    SELECT COUNT(*) FROM (
                        SELECT DISTINCT address, mi_price, floor_plan
                        FROM BUY_data_integrated
                        WHERE address LIKE ?
                        AND mi_price IS NOT NULL
                        AND mi_price != ''
                        AND mi_price != '0'
                    )
                """, [f"%{area}%"])
                deduplicated_count = cursor.fetchone()[0]

                return {
                    "raw": raw_count,
                    "valid_price": valid_price_count,
                    "deduplicated": deduplicated_count
                }
        except Exception as e:
            print(f"DB count query failed: {e}")
            return {"raw": 0, "valid_price": 0, "deduplicated": 0}

    async def test_single_case(self, area: str) -> Dict:
        """単一ケースの検証"""
        print(f"\n{'='*60}")
        print(f"検証中: '{area}'")
        print(f"{'='*60}")

        # ヘッダー件数を取得
        header_count = self.get_header_count(area)
        print(f"ヘッダー件数 (get_filtered_count): {header_count:,}")

        # Agent件数を取得
        agent_count = await self.get_agent_count(area)
        print(f"Agent件数 (_search_by_area): {agent_count:,}")

        # 生のDB件数を取得（デバッグ用）
        raw_counts = self.get_raw_db_count(area)
        print(f"生データ件数: {raw_counts['raw']:,}")
        print(f"有効価格件数: {raw_counts['valid_price']:,}")
        print(f"重複削除件数: {raw_counts['deduplicated']:,}")

        # 一致性を確認
        is_consistent = (header_count == agent_count)
        status = "✅ 一致" if is_consistent else "❌ 不一致"
        print(f"\n結果: {status}")

        if not is_consistent:
            diff = abs(header_count - agent_count)
            print(f"差分: {diff:,}件")

        return {
            "area": area,
            "header_count": header_count,
            "agent_count": agent_count,
            "raw_counts": raw_counts,
            "is_consistent": is_consistent,
            "difference": abs(header_count - agent_count) if not is_consistent else 0
        }

    async def run_all_tests(self) -> Dict:
        """全テストケースを実行"""
        print("🔍 ヘッダー件数とAgent件数の一致性検証を開始します...")
        print(f"検証ケース数: {len(self.test_cases)}")

        results = []
        failed_cases = []

        for area in self.test_cases:
            try:
                result = await self.test_single_case(area)
                results.append(result)

                if not result["is_consistent"]:
                    failed_cases.append(result)

            except Exception as e:
                print(f"❌ '{area}' の検証中にエラー: {e}")
                failed_cases.append({
                    "area": area,
                    "error": str(e),
                    "is_consistent": False
                })

        # 結果サマリー
        print(f"\n{'='*80}")
        print("🔍 検証結果サマリー")
        print(f"{'='*80}")

        total_cases = len(self.test_cases)
        passed_cases = total_cases - len(failed_cases)

        print(f"総検証ケース: {total_cases}")
        print(f"成功: {passed_cases}")
        print(f"失敗: {len(failed_cases)}")
        print(f"成功率: {(passed_cases/total_cases)*100:.1f}%")

        if failed_cases:
            print(f"\n❌ 失敗したケース:")
            for case in failed_cases:
                if 'error' in case:
                    print(f"  - {case['area']}: エラー ({case['error']})")
                else:
                    print(f"  - {case['area']}: ヘッダー={case['header_count']:,}, Agent={case['agent_count']:,}, 差分={case['difference']:,}")
        else:
            print(f"\n✅ すべてのテストケースが成功しました！")

        return {
            "total_cases": total_cases,
            "passed": passed_cases,
            "failed": len(failed_cases),
            "failed_cases": failed_cases,
            "results": results
        }

async def main():
    """メイン実行関数"""
    tester = CountConsistencyTester()
    results = await tester.run_all_tests()

    # 結果をJSONファイルに保存
    output_file = "/Users/tsukasa/Arealinks/Apps7/sumai_agent6/backend/count_consistency_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n📄 詳細結果は {output_file} に保存されました")

    # 失敗があれば終了コード1
    if results['failed'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())