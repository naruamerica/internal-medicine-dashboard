"""Database module for Internal Medicine Citation & Research Trend Dashboard.

要件 6. データベース設計 & 5. 調査日時・スナップショット管理 準拠:
- 保存先: internal_medicine_dashboard/database/internal_medicine.db
- テーブル: articles, article_matches, snapshots, citation_snapshots, annual_citations, keywords, update_history
- 過去データの保持、上書き禁止、スナップショット単位での履歴管理
"""

import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "database",
    "internal_medicine.db",
)


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """SQLiteデータベース接続を取得し、外部キー制約を有効化する。"""
    path = db_path or DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_database(db_path: Optional[str] = None):
    """要件定義書に沿った全テーブルとインデックスを作成する。"""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # 1. articles (論文基本情報)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                pmid TEXT PRIMARY KEY,
                doi TEXT,
                openalex_id TEXT,
                title TEXT NOT NULL,
                authors TEXT,
                journal TEXT DEFAULT 'Internal Medicine',
                publication_date TEXT,
                publication_year INTEGER,
                article_type TEXT,
                abstract TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
            """
        )

        # 2. article_matches (PubMedとOpenAlexの照合結果)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS article_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pmid TEXT NOT NULL,
                openalex_id TEXT,
                doi TEXT,
                match_method TEXT NOT NULL,      -- 'DOI', 'Title', 'Manual'
                match_confidence REAL DEFAULT 1.0,
                match_status TEXT NOT NULL,      -- 'Matched', 'Pending', 'Rejected'
                checked_at TEXT DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (pmid) REFERENCES articles(pmid) ON DELETE CASCADE
            );
            """
        )

        # 3. snapshots (調査単位メタデータ)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                snapshot_id TEXT PRIMARY KEY,
                snapshot_datetime TEXT NOT NULL,
                update_type TEXT NOT NULL,       -- 'scheduled', 'manual', 'initial_import'
                status TEXT NOT NULL,            -- 'completed', 'partial', 'failed'
                records_processed INTEGER DEFAULT 0,
                records_failed INTEGER DEFAULT 0,
                note TEXT
            );
            """
        )

        # 4. citation_snapshots (調査日時点の累積被引用回数)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS citation_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id TEXT NOT NULL,
                pmid TEXT NOT NULL,
                openalex_id TEXT,
                snapshot_datetime TEXT NOT NULL,
                cited_by_count INTEGER,          -- 取得失敗時はNULL（0と区別）
                source TEXT DEFAULT 'OpenAlex',
                retrieval_status TEXT NOT NULL,  -- 'success', 'failed', 'not_found'
                FOREIGN KEY (snapshot_id) REFERENCES snapshots(snapshot_id) ON DELETE CASCADE,
                FOREIGN KEY (pmid) REFERENCES articles(pmid) ON DELETE CASCADE
            );
            """
        )

        # 5. annual_citations (年度別被引用回数)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS annual_citations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                citation_snapshot_id INTEGER NOT NULL,
                pmid TEXT NOT NULL,
                snapshot_datetime TEXT NOT NULL,
                citation_year INTEGER NOT NULL,
                citation_count INTEGER NOT NULL,
                FOREIGN KEY (citation_snapshot_id) REFERENCES citation_snapshots(id) ON DELETE CASCADE,
                FOREIGN KEY (pmid) REFERENCES articles(pmid) ON DELETE CASCADE
            );
            """
        )

        # 6. keywords (キーワード & MeSH Terms)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pmid TEXT NOT NULL,
                keyword_original TEXT NOT NULL,
                keyword_normalized TEXT NOT NULL,
                keyword_type TEXT NOT NULL,      -- 'Author Keyword', 'MeSH Descriptor', 'MeSH Qualifier', 'OpenAlex Keyword'
                publication_year INTEGER,
                FOREIGN KEY (pmid) REFERENCES articles(pmid) ON DELETE CASCADE
            );
            """
        )

        # 7. update_history (更新履歴)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS update_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                update_datetime TEXT NOT NULL,
                update_type TEXT NOT NULL,
                status TEXT NOT NULL,
                records_processed INTEGER DEFAULT 0,
                records_failed INTEGER DEFAULT 0,
                error_message TEXT
            );
            """
        )

        # インデックス作成（パフォーマンス向上）
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_doi ON articles(doi);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_year ON articles(publication_year);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_pmid ON article_matches(pmid);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_doi ON article_matches(doi);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cs_snapshot ON citation_snapshots(snapshot_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cs_pmid ON citation_snapshots(pmid);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ac_snapshot_id ON annual_citations(citation_snapshot_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ac_pmid ON annual_citations(pmid);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ac_year ON annual_citations(citation_year);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_kw_pmid ON keywords(pmid);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_kw_norm ON keywords(keyword_normalized);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_kw_type ON keywords(keyword_type);")

        conn.commit()


def get_latest_snapshot_id(conn: Optional[sqlite3.Connection] = None) -> Optional[str]:
    """最新の完了済みスナップショットIDを取得する。"""
    close_at_end = False
    if conn is None:
        conn = get_connection()
        close_at_end = True

    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT snapshot_id FROM snapshots
            WHERE status IN ('completed', 'partial')
            ORDER BY snapshot_datetime DESC LIMIT 1;
            """
        )
        row = cur.fetchone()
        return row["snapshot_id"] if row else None
    finally:
        if close_at_end:
            conn.close()


def list_all_snapshots(conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    """すべてのスナップショット一覧を取得する（過去調査切替用）。"""
    close_at_end = False
    if conn is None:
        conn = get_connection()
        close_at_end = True

    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT snapshot_id, snapshot_datetime, update_type, status, records_processed, records_failed, note
            FROM snapshots
            ORDER BY snapshot_datetime DESC;
            """
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        if close_at_end:
            conn.close()
