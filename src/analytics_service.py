"""Analytics and query service for Internal Medicine Citation & Research Trend Dashboard.

要件 3. 各画面の詳細仕様（①Overview 〜 ⑥High Impact Articles）に準拠した
集計・データ抽出サービス。
"""

import sqlite3
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
from datetime import datetime

try:
    from src.database import get_connection, get_latest_snapshot_id
    from src.metrics import (
        calculate_burst_metrics,
        calculate_citation_per_year,
        get_latest_confirmed_year,
    )
except ImportError:
    from internal_medicine_dashboard.src.database import get_connection, get_latest_snapshot_id
    from internal_medicine_dashboard.src.metrics import (
        calculate_burst_metrics,
        calculate_citation_per_year,
        get_latest_confirmed_year,
    )


class AnalyticsService:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def _get_conn(self) -> sqlite3.Connection:
        return get_connection(self.db_path)

    # -------------------------------------------------------------
    # ① Overview 向け集計
    # -------------------------------------------------------------
    def get_available_publication_years(self) -> List[int]:
        """データベース内に登録されている論文の発行年一覧を取得する。"""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT DISTINCT publication_year FROM articles WHERE publication_year IS NOT NULL ORDER BY publication_year ASC;"
            )
            return [r["publication_year"] for r in cur.fetchall()]

    def get_overview_kpis(
        self,
        snapshot_id: Optional[str] = None,
        start_pub_year: Optional[int] = None,
        end_pub_year: Optional[int] = None,
    ) -> Dict[str, Any]:
        """ジャーナル全体の主要KPI（論文数、累積被引用、確定暦年被引用、平均引用数）を取得する。"""
        with self._get_conn() as conn:
            snap_id = snapshot_id or get_latest_snapshot_id(conn)
            confirmed_year = get_latest_confirmed_year()

            # 出版年フィルター条件
            where_pubs = ["1=1"]
            params_pubs: List[Any] = []
            if start_pub_year:
                where_pubs.append("publication_year >= ?")
                params_pubs.append(start_pub_year)
            if end_pub_year:
                where_pubs.append("publication_year <= ?")
                params_pubs.append(end_pub_year)
            where_pub_clause = " AND ".join(where_pubs)

            # 1. Publications 総数
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) as total_pubs FROM articles WHERE {where_pub_clause};", params_pubs)
            total_pubs = cur.fetchone()["total_pubs"]

            # 2. Total Citations (最新スナップショット & 出版年絞り込み)
            total_citations = 0
            if snap_id:
                cur.execute(
                    f"""
                    SELECT SUM(cs.cited_by_count) as total_cites
                    FROM citation_snapshots cs
                    JOIN articles a ON cs.pmid = a.pmid
                    WHERE cs.snapshot_id = ? AND cs.retrieval_status = 'success' AND {where_pub_clause};
                    """,
                    [snap_id] + params_pubs,
                )
                row = cur.fetchone()
                total_citations = row["total_cites"] or 0

            # 3. 最新確定暦年の年間被引用数
            annual_confirmed_cites = 0
            if snap_id:
                cur.execute(
                    f"""
                    SELECT SUM(ac.citation_count) as annual_cites
                    FROM annual_citations ac
                    JOIN citation_snapshots cs ON ac.citation_snapshot_id = cs.id
                    JOIN articles a ON cs.pmid = a.pmid
                    WHERE cs.snapshot_id = ? AND ac.citation_year = ? AND {where_pub_clause};
                    """,
                    [snap_id, confirmed_year] + params_pubs,
                )
                row = cur.fetchone()
                annual_confirmed_cites = row["annual_cites"] or 0

            avg_citations = round(total_citations / total_pubs, 2) if total_pubs > 0 else 0.0

            # 最終更新日時
            last_updated = "未調査"
            if snap_id:
                cur.execute("SELECT snapshot_datetime FROM snapshots WHERE snapshot_id = ?;", (snap_id,))
                row = cur.fetchone()
                if row:
                    last_updated = row["snapshot_datetime"]

            return {
                "snapshot_id": snap_id,
                "total_pubs": total_pubs,
                "total_citations": total_citations,
                "confirmed_year": confirmed_year,
                "annual_confirmed_cites": annual_confirmed_cites,
                "avg_citations": avg_citations,
                "last_updated": last_updated,
            }

    def get_annual_citations_summary(
        self,
        snapshot_id: Optional[str] = None,
        start_pub_year: Optional[int] = None,
        end_pub_year: Optional[int] = None,
    ) -> pd.DataFrame:
        """年度別被引用数、累積被引用数、前年比(YoY)を計算したDataFrameを返す。"""
        with self._get_conn() as conn:
            snap_id = snapshot_id or get_latest_snapshot_id(conn)
            if not snap_id:
                return pd.DataFrame(columns=["Citation Year", "Annual Citations", "Cumulative Citations", "YoY Growth Rate (%)"])

            where_pubs = ["1=1"]
            params: List[Any] = [snap_id]
            if start_pub_year:
                where_pubs.append("a.publication_year >= ?")
                params.append(start_pub_year)
            if end_pub_year:
                where_pubs.append("a.publication_year <= ?")
                params.append(end_pub_year)
            where_pub_clause = " AND ".join(where_pubs)

            query = f"""
                SELECT ac.citation_year, SUM(ac.citation_count) as annual_cites
                FROM annual_citations ac
                JOIN citation_snapshots cs ON ac.citation_snapshot_id = cs.id
                JOIN articles a ON cs.pmid = a.pmid
                WHERE cs.snapshot_id = ? AND {where_pub_clause}
                GROUP BY ac.citation_year
                ORDER BY ac.citation_year ASC;
            """
            df = pd.read_sql_query(query, conn, params=params)
            if df.empty:
                return pd.DataFrame(columns=["Citation Year", "Annual Citations", "Cumulative Citations", "YoY Growth Rate (%)"])

            df = df.rename(columns={"citation_year": "Citation Year", "annual_cites": "Annual Citations"})
            df["Cumulative Citations"] = df["Annual Citations"].cumsum()

            # 前年比
            growth_rates = []
            for i in range(len(df)):
                if i == 0:
                    growth_rates.append(None)
                else:
                    prev = df.loc[i - 1, "Annual Citations"]
                    curr = df.loc[i, "Annual Citations"]
                    if prev > 0:
                        rate = round(((curr - prev) / prev) * 100.0, 1)
                        growth_rates.append(rate)
                    else:
                        growth_rates.append(None)
            df["YoY Growth Rate (%)"] = growth_rates
            return df

    # -------------------------------------------------------------
    # ③ Article Analysis 向け
    # -------------------------------------------------------------
    def search_articles(
        self,
        keyword: str = "",
        author: str = "",
        pmid: str = "",
        doi: str = "",
        pub_year: Optional[int] = None,
        start_pub_year: Optional[int] = None,
        end_pub_year: Optional[int] = None,
        article_type: str = "",
        snapshot_id: Optional[str] = None,
        limit: int = 100,
    ) -> pd.DataFrame:
        """論文を複合条件で検索し、最新被引用回数付きで返す。"""
        with self._get_conn() as conn:
            snap_id = snapshot_id or get_latest_snapshot_id(conn)
            conditions = ["1=1"]
            params: List[Any] = []

            if keyword:
                conditions.append("(a.title LIKE ? OR a.abstract LIKE ?)")
                params.extend([f"%{keyword}%", f"%{keyword}%"])
            if author:
                conditions.append("a.authors LIKE ?")
                params.append(f"%{author}%")
            if pmid:
                conditions.append("a.pmid LIKE ?")
                params.append(f"%{pmid}%")
            if doi:
                conditions.append("a.doi LIKE ?")
                params.append(f"%{doi}%")
            if pub_year:
                conditions.append("a.publication_year = ?")
                params.append(pub_year)
            if start_pub_year:
                conditions.append("a.publication_year >= ?")
                params.append(start_pub_year)
            if end_pub_year:
                conditions.append("a.publication_year <= ?")
                params.append(end_pub_year)
            if article_type and article_type != "すべて":
                conditions.append("a.article_type = ?")
                params.append(article_type)

            where_clause = " AND ".join(conditions)

            query = f"""
                SELECT 
                    a.pmid as PMID,
                    a.title as Title,
                    a.authors as Authors,
                    a.publication_year as "Publication Year",
                    a.article_type as "Article Type",
                    a.doi as DOI,
                    COALESCE(cs.cited_by_count, 0) as "Cited by Count",
                    COALESCE(cs.snapshot_datetime, '-') as "Last Updated"
                FROM articles a
                LEFT JOIN citation_snapshots cs ON a.pmid = cs.pmid AND cs.snapshot_id = ?
                WHERE {where_clause}
                ORDER BY "Cited by Count" DESC, a.publication_year DESC
                LIMIT ?;
            """
            full_params = [snap_id] + params + [limit]
            return pd.read_sql_query(query, conn, params=full_params)

    def get_article_details(self, pmid: str, snapshot_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """特定論文のメタデータ、年度別引用推移、過去スナップショット履歴を取得する。"""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM articles WHERE pmid = ?;", (pmid,))
            article = cur.fetchone()
            if not article:
                return None

            snap_id = snapshot_id or get_latest_snapshot_id(conn)

            # 最新スナップショットでの被引用数
            total_citations = 0
            if snap_id:
                cur.execute(
                    "SELECT cited_by_count, snapshot_datetime, openalex_id FROM citation_snapshots WHERE pmid = ? AND snapshot_id = ?;",
                    (pmid, snap_id),
                )
                row = cur.fetchone()
                if row and row["cited_by_count"] is not None:
                    total_citations = row["cited_by_count"]

            # 年度別被引用履歴
            yearly_cites = {}
            if snap_id:
                cur.execute(
                    """
                    SELECT ac.citation_year, ac.citation_count
                    FROM annual_citations ac
                    JOIN citation_snapshots cs ON ac.citation_snapshot_id = cs.id
                    WHERE cs.pmid = ? AND cs.snapshot_id = ?
                    ORDER BY ac.citation_year ASC;
                    """,
                    (pmid, snap_id),
                )
                for r in cur.fetchall():
                    yearly_cites[r["citation_year"]] = r["citation_count"]

            # スナップショット別調査履歴
            cur.execute(
                """
                SELECT cs.snapshot_datetime, cs.snapshot_id, cs.cited_by_count, cs.source, cs.retrieval_status
                FROM citation_snapshots cs
                WHERE cs.pmid = ?
                ORDER BY cs.snapshot_datetime ASC;
                """,
                (pmid,),
            )
            history = [dict(r) for r in cur.fetchall()]

            return {
                "article": dict(article),
                "total_citations": total_citations,
                "yearly_cites": yearly_cites,
                "history": history,
            }

    # -------------------------------------------------------------
    # ④ Burst Articles 向け
    # -------------------------------------------------------------
    def get_burst_articles(
        self,
        snapshot_id: Optional[str] = None,
        min_recent_citations: int = 1,
        article_type: str = "すべて",
        pub_year_filter: Optional[int] = None,
        start_pub_year: Optional[int] = None,
        end_pub_year: Optional[int] = None,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Burst Articles (通常) および Emerging Articles (掲載後3年以内) の2つのDataFrameを返す。"""
        with self._get_conn() as conn:
            snap_id = snapshot_id or get_latest_snapshot_id(conn)
            if not snap_id:
                return pd.DataFrame(), pd.DataFrame()

            confirmed_year = get_latest_confirmed_year()

            # 対象論文と年度別引用を取得
            cur = conn.cursor()
            cur.execute(
                """
                SELECT a.pmid, a.title, a.publication_year, a.article_type, cs.id as cs_id, cs.cited_by_count
                FROM articles a
                JOIN citation_snapshots cs ON a.pmid = cs.pmid
                WHERE cs.snapshot_id = ? AND cs.retrieval_status = 'success';
                """,
                (snap_id,),
            )
            articles = cur.fetchall()

            burst_rows = []
            emerging_rows = []

            for art in articles:
                pmid = art["pmid"]
                pub_yr = art["publication_year"]
                art_type = art["article_type"]

                if article_type != "すべて" and art_type != article_type:
                    continue
                if pub_year_filter and pub_yr != pub_year_filter:
                    continue
                if start_pub_year and pub_yr and pub_yr < start_pub_year:
                    continue
                if end_pub_year and pub_yr and pub_yr > end_pub_year:
                    continue

                # 年別引用取得
                cur.execute(
                    "SELECT citation_year, citation_count FROM annual_citations WHERE citation_snapshot_id = ?;",
                    (art["cs_id"],),
                )
                counts_by_year = {r["citation_year"]: r["citation_count"] for r in cur.fetchall()}

                metrics = calculate_burst_metrics(counts_by_year, pub_yr, confirmed_year)
                recent_cites = metrics["recent_year_citations"]

                if recent_cites < min_recent_citations:
                    continue

                row_data = {
                    "PMID": pmid,
                    "Title": art["title"],
                    "Publication Year": pub_yr,
                    "Article Type": art_type,
                    "Previous 3-Year Avg": metrics["previous_3yr_avg"],
                    "Recent Year Citations": recent_cites,
                    "Burst Score": metrics["burst_score"],
                    "Growth Rate (%)": metrics["growth_rate"],
                    "Total Citations": art["cited_by_count"],
                    "counts_by_year": counts_by_year,
                }

                if metrics["is_emerging"]:
                    emerging_rows.append(row_data)
                elif metrics["is_calculable"]:
                    burst_rows.append(row_data)

            # DataFrame化とソート
            df_burst = pd.DataFrame(burst_rows)
            if not df_burst.empty:
                df_burst = df_burst.sort_values(by=["Burst Score", "Recent Year Citations"], ascending=[False, False])
                df_burst.reset_index(drop=True, inplace=True)
                df_burst.insert(0, "Rank", range(1, len(df_burst) + 1))

            df_emerging = pd.DataFrame(emerging_rows)
            if not df_emerging.empty:
                df_emerging = df_emerging.sort_values(by=["Recent Year Citations", "Total Citations"], ascending=[False, False])
                df_emerging.reset_index(drop=True, inplace=True)
                df_emerging.insert(0, "Rank", range(1, len(df_emerging) + 1))

            return df_burst, df_emerging

    # -------------------------------------------------------------
    # ⑤ Topic Analysis 向け
    # -------------------------------------------------------------
    def get_topic_frequencies(
        self,
        keyword_type: str = "Author Keyword",
        min_count: int = 2,
        pub_year: Optional[int] = None,
    ) -> pd.DataFrame:
        """キーワードまたはMeSHの頻度ランキングを取得する。"""
        with self._get_conn() as conn:
            params: List[Any] = [keyword_type]
            year_clause = ""
            if pub_year:
                year_clause = "AND k.publication_year = ?"
                params.append(pub_year)

            params.append(min_count)

            query = f"""
                SELECT 
                    k.keyword_normalized as Keyword,
                    MAX(k.keyword_original) as "Original Form",
                    COUNT(*) as Frequency
                FROM keywords k
                WHERE k.keyword_type = ? {year_clause}
                GROUP BY k.keyword_normalized
                HAVING COUNT(*) >= ?
                ORDER BY Frequency DESC;
            """
            return pd.read_sql_query(query, conn, params=params)

    def get_topic_annual_trends(
        self,
        keywords: List[str],
        keyword_type: str = "Author Keyword",
    ) -> pd.DataFrame:
        """指定されたキーワード群の年別出現回数推移を取得する。"""
        if not keywords:
            return pd.DataFrame()

        with self._get_conn() as conn:
            placeholders = ",".join(["?"] * len(keywords))
            params = [keyword_type] + [k.lower() for k in keywords]

            query = f"""
                SELECT 
                    k.publication_year as Year,
                    k.keyword_normalized as Keyword,
                    COUNT(*) as Count
                FROM keywords k
                WHERE k.keyword_type = ? AND k.keyword_normalized IN ({placeholders}) AND k.publication_year IS NOT NULL
                GROUP BY k.publication_year, k.keyword_normalized
                ORDER BY k.publication_year ASC;
            """
            return pd.read_sql_query(query, conn, params=params)

    # -------------------------------------------------------------
    # ⑥ High Impact Articles 向け
    # -------------------------------------------------------------
    def get_high_impact_articles(
        self,
        snapshot_id: Optional[str] = None,
        article_type: str = "すべて",
        pub_year: Optional[int] = None,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """High Impact Articles (Citation per Year) と Early Impact (12ヶ月未満) を返す。"""
        with self._get_conn() as conn:
            snap_id = snapshot_id or get_latest_snapshot_id(conn)
            if not snap_id:
                return pd.DataFrame(), pd.DataFrame()

            cur = conn.cursor()
            cur.execute(
                """
                SELECT a.pmid, a.title, a.publication_date, a.publication_year, a.article_type, a.doi,
                       cs.cited_by_count, cs.snapshot_datetime
                FROM articles a
                JOIN citation_snapshots cs ON a.pmid = cs.pmid
                WHERE cs.snapshot_id = ? AND cs.retrieval_status = 'success' AND cs.cited_by_count > 0;
                """,
                (snap_id,),
            )
            rows = cur.fetchall()

            high_impact_list = []
            early_impact_list = []

            for r in rows:
                if article_type != "すべて" and r["article_type"] != article_type:
                    continue
                if pub_year and r["publication_year"] != pub_year:
                    continue

                total_cites = r["cited_by_count"]
                metrics = calculate_citation_per_year(
                    total_citations=total_cites,
                    publication_date_str=r["publication_date"],
                    publication_year=r["publication_year"],
                )

                cpy = metrics["citation_per_year"]
                if cpy is None:
                    continue

                item = {
                    "PMID": r["pmid"],
                    "Title": r["title"],
                    "Publication Year": r["publication_year"],
                    "Article Type": r["article_type"],
                    "Total Citations": total_cites,
                    "Years Since Publication": metrics["years_since_publication"],
                    "Citation per Year": cpy,
                    "Last Updated": r["snapshot_datetime"],
                }

                if metrics["is_early_impact"]:
                    early_impact_list.append(item)
                else:
                    high_impact_list.append(item)

            df_high = pd.DataFrame(high_impact_list)
            if not df_high.empty:
                df_high = df_high.sort_values(by="Citation per Year", ascending=False)
                df_high.reset_index(drop=True, inplace=True)
                df_high.insert(0, "Rank", range(1, len(df_high) + 1))

            df_early = pd.DataFrame(early_impact_list)
            if not df_early.empty:
                df_early = df_early.sort_values(by="Citation per Year", ascending=False)
                df_early.reset_index(drop=True, inplace=True)
                df_early.insert(0, "Rank", range(1, len(df_early) + 1))

            return df_high, df_early
