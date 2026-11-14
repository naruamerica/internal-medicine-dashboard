"""Full test suite for Internal Medicine Citation & Research Trend Dashboard.

要件 10. Phase 4 検証項目 準拠:
- 認証ロジック
- DB整合性とテーブル
- スナップショット履歴
- Burst Score & Emerging 分類
- Citation per Year & Early Impact 分類
- 各種集計・CSV出力
"""

import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from internal_medicine_dashboard.src.auth import verify_login, _hash_password
from internal_medicine_dashboard.src.database import get_connection, init_database
from internal_medicine_dashboard.src.metrics import (
    calculate_burst_metrics,
    calculate_citation_per_year,
    get_latest_confirmed_year,
)
from internal_medicine_dashboard.src.analytics_service import AnalyticsService
from internal_medicine_dashboard.src.exporter import export_dataframe_to_csv_bytes
import pandas as pd


class TestDashboardSuite(unittest.TestCase):
    def setUp(self):
        init_database()
        self.svc = AnalyticsService()

    def test_01_auth_verification(self):
        """0. ログイン認証の検証"""
        # 正しい資格情報
        self.assertTrue(verify_login("n-ogasawara", "2020408"))
        # 誤ったパスワード
        self.assertFalse(verify_login("n-ogasawara", "wrong_password"))
        # 誤ったID
        self.assertFalse(verify_login("wrong_user", "2020408"))
        # 空文字
        self.assertFalse(verify_login("", ""))

    def test_02_database_tables(self):
        """6. データベーステーブルの検証"""
        conn = get_connection()
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
        required = ["articles", "article_matches", "snapshots", "citation_snapshots", "annual_citations", "keywords", "update_history"]
        for tbl in required:
            self.assertIn(tbl, tables)

    def test_03_burst_metrics_calculation(self):
        """4.1 / 4.2 Burst Score および Emerging 分類の検証"""
        counts = {2022: 8, 2023: 10, 2024: 12, 2025: 30}
        # 2020年出版（掲載後3年を超えている）
        metrics = calculate_burst_metrics(counts, publication_year=2020, confirmed_year=2025)
        self.assertEqual(metrics["recent_year_citations"], 30)
        self.assertEqual(metrics["previous_3yr_avg"], 10.0)
        self.assertEqual(metrics["burst_score"], 3.0)
        self.assertEqual(metrics["growth_rate"], 200.0)
        self.assertFalse(metrics["is_emerging"])

        # 2024年出版（掲載後3年以内 -> Emerging Articles）
        emerging_metrics = calculate_burst_metrics(counts, publication_year=2024, confirmed_year=2025)
        self.assertTrue(emerging_metrics["is_emerging"])

    def test_04_citation_per_year_calculation(self):
        """6.1 / 6.2 Citation per Year および Early Impact 分類の検証"""
        # 掲載2年前の論文 (730.5日経過 -> 約2年)
        res = calculate_citation_per_year(
            total_citations=20,
            publication_date_str="2024-11-14",
            publication_year=2024,
            reference_date=pd.Timestamp("2026-11-14"),
        )
        self.assertAlmostEqual(res["years_since_publication"], 2.0, delta=0.05)
        self.assertAlmostEqual(res["citation_per_year"], 10.0, delta=0.5)
        self.assertFalse(res["is_early_impact"])

        # 掲載後6ヶ月の論文 -> Early Impact
        res_early = calculate_citation_per_year(
            total_citations=5,
            publication_date_str="2026-05-14",
            publication_year=2026,
            reference_date=pd.Timestamp("2026-11-14"),
        )
        self.assertTrue(res_early["is_early_impact"])

    def test_05_overview_kpis(self):
        """① Overview KPI 集計の検証"""
        kpis = self.svc.get_overview_kpis()
        self.assertGreater(kpis["total_pubs"], 0)
        self.assertIn("total_citations", kpis)
        self.assertIn("confirmed_year", kpis)

    def test_06_csv_export_utf8_bom(self):
        """7. CSV出力 UTF-8 BOM の検証"""
        test_df = pd.DataFrame([{"ID": "123", "Title": "テスト論文タイトル", "Citations": 10}])
        csv_bytes = export_dataframe_to_csv_bytes(test_df)
        # UTF-8 BOM の先頭3バイト: 0xEF, 0xBB, 0xBF
        self.assertTrue(csv_bytes.startswith(b"\xef\xbb\xbf"))


if __name__ == "__main__":
    unittest.main()
