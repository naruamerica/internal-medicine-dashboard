"""Data service for managing snapshots, articles, citations, and matches.

要件 4. データ取得・更新仕様, 5. 調査日時・スナップショット管理, 6. データベース設計 準拠:
- 一意の snapshot_id を発行
- 過去の調査データを上書きせず、履歴として蓄積
- 取得失敗時は被引用数0とせず、NULL / 'failed' として記録
- 同一スナップショット内の整合性を担保
"""

import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    from src.database import get_connection
    from src.openalex_client import MatchResult, OpenAlexClient
except ImportError:
    from internal_medicine_dashboard.src.database import get_connection
    from internal_medicine_dashboard.src.openalex_client import MatchResult, OpenAlexClient

logger = logging.getLogger(__name__)


class DataService:
    """データベースの読み書き・スナップショット操作を統括するサービスクラス。"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def _get_conn(self) -> sqlite3.Connection:
        return get_connection(self.db_path)

    def import_articles_from_records(self, records: List[Dict[str, Any]]) -> int:
        """PubMedレコード群を articles テーブルおよび keywords テーブルへ安全に登録・更新する。"""
        inserted_count = 0
        with self._get_conn() as conn:
            cursor = conn.cursor()
            for r in records:
                pmid = str(r.get("pmid", "")).strip()
                if not pmid:
                    continue

                title = r.get("title", "")
                doi = r.get("doi") or None
                authors = r.get("authors", "")
                journal = r.get("journal_title") or "Internal Medicine"
                pub_year = r.get("publication_year")
                pub_date = r.get("retrieved_at", "")[:10] if r.get("retrieved_at") else None
                article_type = r.get("article_type", "")
                abstract = r.get("abstract", "")

                cursor.execute(
                    """
                    INSERT INTO articles (pmid, doi, title, authors, journal, publication_date, publication_year, article_type, abstract)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(pmid) DO UPDATE SET
                        doi = COALESCE(excluded.doi, articles.doi),
                        title = excluded.title,
                        authors = excluded.authors,
                        publication_year = COALESCE(excluded.publication_year, articles.publication_year),
                        article_type = excluded.article_type,
                        abstract = COALESCE(excluded.abstract, articles.abstract);
                    """,
                    (pmid, doi, title, authors, journal, pub_date, pub_year, article_type, abstract),
                )
                inserted_count += 1

                # キーワード登録
                raw_keywords = r.get("keywords", [])
                for kw in raw_keywords:
                    if not kw:
                        continue
                    kw_str = str(kw).strip()
                    # 分類（MeSH or Author Keyword）
                    kw_type = "MeSH Descriptor" if "*" in kw_str or "/" in kw_str else "Author Keyword"
                    norm = kw_str.strip("*").lower()

                    cursor.execute(
                        """
                        INSERT INTO keywords (pmid, keyword_original, keyword_normalized, keyword_type, publication_year)
                        VALUES (?, ?, ?, ?, ?);
                        """,
                        (pmid, kw_str, norm, kw_type, pub_year),
                    )

            conn.commit()
        return inserted_count

    def create_snapshot(
        self,
        snapshot_id: str,
        update_type: str = "manual",
        note: str = "",
    ) -> str:
        """新しいスナップショットレコードを作成する。"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO snapshots (snapshot_id, snapshot_datetime, update_type, status, records_processed, records_failed, note)
                VALUES (?, ?, ?, 'processing', 0, 0, ?)
                ON CONFLICT(snapshot_id) DO UPDATE SET
                    snapshot_datetime = excluded.snapshot_datetime,
                    status = 'processing',
                    note = excluded.note;
                """,
                (snapshot_id, now_str, update_type, note),
            )
            conn.commit()
        return snapshot_id

    def save_citation_data(
        self,
        snapshot_id: str,
        match_result: MatchResult,
    ) -> bool:
        """照合結果およびOpenAlex被引用データを citation_snapshots & annual_citations に保存する。"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pmid = match_result.pmid
        doi = match_result.doi

        with self._get_conn() as conn:
            cursor = conn.cursor()

            # 1. article_matches 記録
            cursor.execute(
                """
                INSERT INTO article_matches (pmid, openalex_id, doi, match_method, match_confidence, match_status, checked_at)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    pmid,
                    match_result.openalex_id,
                    doi,
                    match_result.match_method,
                    match_result.match_confidence,
                    match_result.match_status,
                    now_str,
                ),
            )

            # 2. OpenAlex ID を articles にも反映
            if match_result.openalex_id:
                cursor.execute(
                    "UPDATE articles SET openalex_id = ? WHERE pmid = ?;",
                    (match_result.openalex_id, pmid),
                )

            # 3. citation_snapshots 記録
            if match_result.work is not None:
                total_cites = match_result.work.cited_by_count
                retrieval_status = "success"
                openalex_id = match_result.work.openalex_id

                cursor.execute(
                    """
                    INSERT INTO citation_snapshots (snapshot_id, pmid, openalex_id, snapshot_datetime, cited_by_count, source, retrieval_status)
                    VALUES (?, ?, ?, ?, ?, 'OpenAlex', ?);
                    """,
                    (snapshot_id, pmid, openalex_id, now_str, total_cites, retrieval_status),
                )
                citation_snapshot_id = cursor.lastrowid

                # 4. annual_citations 記録
                for yearly in match_result.work.counts_by_year:
                    y = yearly.get("year")
                    c = yearly.get("cited_by_count", 0)
                    if y is not None:
                        cursor.execute(
                            """
                            INSERT INTO annual_citations (citation_snapshot_id, pmid, snapshot_datetime, citation_year, citation_count)
                            VALUES (?, ?, ?, ?, ?);
                            """,
                            (citation_snapshot_id, pmid, now_str, int(y), int(c)),
                        )
            else:
                # 取得失敗または未検出
                retrieval_status = "failed" if match_result.error_message else "not_found"
                cursor.execute(
                    """
                    INSERT INTO citation_snapshots (snapshot_id, pmid, openalex_id, snapshot_datetime, cited_by_count, source, retrieval_status)
                    VALUES (?, ?, NULL, ?, NULL, 'OpenAlex', ?);
                    """,
                    (snapshot_id, pmid, now_str, retrieval_status),
                )

            conn.commit()
            return True

    def finalize_snapshot(self, snapshot_id: str, status: str = "completed"):
        """スナップショットの処理集計数を計算し、確定ステータスに更新する。"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 
                    COUNT(CASE WHEN retrieval_status = 'success' THEN 1 END) as success_count,
                    COUNT(CASE WHEN retrieval_status != 'success' THEN 1 END) as failed_count
                FROM citation_snapshots
                WHERE snapshot_id = ?;
                """,
                (snapshot_id,),
            )
            row = cursor.fetchone()
            success_count = row["success_count"] if row else 0
            failed_count = row["failed_count"] if row else 0

            cursor.execute(
                """
                UPDATE snapshots
                SET status = ?, records_processed = ?, records_failed = ?
                WHERE snapshot_id = ?;
                """,
                (status, success_count, failed_count, snapshot_id),
            )
            conn.commit()
