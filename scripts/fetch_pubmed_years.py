"""Script to fetch papers for specified publication year(s) from PubMed and OpenAlex into SQLite DB.

使用例:
  python fetch_pubmed_years.py 2024 2025
  python fetch_pubmed_years.py 2025
"""

import os
import sys
import time
from datetime import datetime
from typing import Dict, List

# プロジェクトルートを追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from internal_medicine_dashboard.src.database import init_database, get_connection
from internal_medicine_dashboard.src.data_service import DataService
from internal_medicine_dashboard.src.pubmed_client import PubMedClient, JOURNAL_QUERY_TERM
from internal_medicine_dashboard.src.openalex_client import OpenAlexClient, MatchResult


def fetch_and_import_years(start_year: int, end_year: int):
    init_database()
    service = DataService()
    pubmed = PubMedClient()
    openalex = OpenAlexClient()

    if start_year == end_year:
        query = f'{JOURNAL_QUERY_TERM} AND ({start_year}[DP])'
        label = f"{start_year}年"
    else:
        query = f'{JOURNAL_QUERY_TERM} AND ({start_year}[DP] : {end_year}[DP])'
        label = f"{start_year}〜{end_year}年"

    print(f"\n=======================================================")
    print(f"  Internal Medicine データ取得・同期: {label}")
    print(f"=======================================================")

    print(f"[{datetime.now().strftime('%H:%M:%S')}] [1/3] PubMed E-utilities で論文を検索中...")
    pmids = pubmed.search_articles(query=query, retmax=5000)
    print(f"検索結果: {len(pmids)} 件の論文が見つかりました。")

    if not pmids:
        print("取得対象のPMIDがありませんでした。")
        return

    print(f"[{datetime.now().strftime('%H:%M:%S')}] [2/3] 詳細メタデータ（XML）を取得・パース中...")
    articles = pubmed.fetch_article_summaries(pmids, chunk_size=100)
    print(f"パース完了: {len(articles)} 件")

    records = []
    doi_to_pmid: Dict[str, str] = {}
    dois_to_fetch: List[str] = []

    for a in articles:
        records.append({
            "pmid": a.pmid,
            "doi": a.doi,
            "title": a.title,
            "authors": a.authors,
            "journal_title": a.journal_title,
            "retrieved_at": a.publication_date,
            "publication_year": a.publication_year,
            "article_type": a.article_type,
            "abstract": a.abstract,
            "keywords": a.keywords + a.mesh_terms,
        })
        if a.doi:
            clean_doi = a.doi.lower().replace("https://doi.org/", "").strip()
            doi_to_pmid[clean_doi] = a.pmid
            dois_to_fetch.append(a.doi)

    print(f"データベースの articles & keywords テーブルへ登録中...")
    count = service.import_articles_from_records(records)
    print(f"登録・更新完了: {count} 件")

    # スナップショット管理
    snapshot_id = f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    service.create_snapshot(
        snapshot_id=snapshot_id,
        update_type="pubmed_openalex_sync",
        note=f"Sync papers for {label} (Total: {len(records)} papers)",
    )

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] [3/3] OpenAlex API から被引用データを高速バッチ取得中...")
    print(f"対象DOI数: {len(dois_to_fetch)} 件")

    works_by_doi = openalex.fetch_works_by_dois(dois_to_fetch, batch_size=50)
    print(f"OpenAlex から照合・取得成功: {len(works_by_doi)} 件")

    # スナップショット保存
    for a in articles:
        pmid = a.pmid
        doi = a.doi
        clean_doi = doi.lower().replace("https://doi.org/", "").strip() if doi else None
        work = works_by_doi.get(clean_doi) if clean_doi else None

        if work:
            match_res = MatchResult(
                pmid=pmid,
                doi=doi,
                openalex_id=work.openalex_id,
                match_method="DOI",
                match_confidence=1.0,
                match_status="Matched",
                work=work,
            )
        else:
            match_res = MatchResult(
                pmid=pmid,
                doi=doi,
                openalex_id=None,
                match_method="None",
                match_confidence=0.0,
                match_status="Pending",
                work=None,
                error_message="Work not found in batch fetch",
            )
        service.save_citation_data(snapshot_id, match_res)

    service.finalize_snapshot(snapshot_id)

    print(f"\n=======================================================")
    print(f"  同期完了！ 新スナップショット: {snapshot_id}")
    print(f"  対象: {label} ({len(records)} 報)")
    print(f"=======================================================")
    print("ダッシュボード画面をブラウザで再読み込み（F5）すると、新しい年のデータが反映されます。\n")


if __name__ == "__main__":
    if len(sys.argv) == 2:
        y = int(sys.argv[1])
        fetch_and_import_years(y, y)
    elif len(sys.argv) >= 3:
        y1 = int(sys.argv[1])
        y2 = int(sys.argv[2])
        fetch_and_import_years(min(y1, y2), max(y1, y2))
    else:
        print("使用法: python fetch_pubmed_years.py <開始年> [終了年]")
