"""Sync service for fetching papers and citations from PubMed & OpenAlex into SQLite DB."""

import logging
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

try:
    from src.database import get_connection, init_database
    from src.data_service import DataService
    from src.openalex_client import MatchResult, OpenAlexClient
    from src.pubmed_client import JOURNAL_QUERY_TERM, PubMedClient
except ImportError:
    from internal_medicine_dashboard.src.database import get_connection, init_database
    from internal_medicine_dashboard.src.data_service import DataService
    from internal_medicine_dashboard.src.openalex_client import MatchResult, OpenAlexClient
    from internal_medicine_dashboard.src.pubmed_client import JOURNAL_QUERY_TERM, PubMedClient

logger = logging.getLogger(__name__)


def sync_papers_for_years(
    start_year: int,
    end_year: int,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Tuple[int, int, str]:
    """指定された発行年の論文をPubMedから取得し、OpenAlexから被引用データをバッチ取得してDBに登録する。"""
    init_database()
    service = DataService()
    pubmed = PubMedClient()
    openalex = OpenAlexClient()

    if start_year == end_year:
        query = f"{JOURNAL_QUERY_TERM} AND ({start_year}[DP])"
        label = f"{start_year}年"
    else:
        query = f"{JOURNAL_QUERY_TERM} AND ({start_year}[DP] : {end_year}[DP])"
        label = f"{start_year}〜{end_year}年"

    if progress_callback:
        progress_callback(f"PubMedで「{label}」の論文を検索中...")
    pmids = pubmed.search_articles(query=query, retmax=5000)

    if not pmids:
        return 0, 0, f"対象の論文が見つかりませんでした ({label})"

    if progress_callback:
        progress_callback(f"PubMedから詳細情報（{len(pmids)} 件）を取得・パース中...")
    articles = pubmed.fetch_article_summaries(pmids, chunk_size=100)

    records = []
    dois_to_fetch: List[str] = []
    for a in articles:
        records.append(
            {
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
            }
        )
        if a.doi:
            dois_to_fetch.append(a.doi)

    imported_count = service.import_articles_from_records(records)

    # スナップショット作成
    snapshot_id = f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    service.create_snapshot(
        snapshot_id=snapshot_id,
        update_type="pubmed_openalex_sync",
        note=f"Sync papers for {label} (Total: {len(records)} papers)",
    )

    if progress_callback:
        progress_callback(f"OpenAlex から被引用データをバッチ取得中（対象: {len(dois_to_fetch)} 件）...")
    works_by_doi = openalex.fetch_works_by_dois(dois_to_fetch, batch_size=50)

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
    return imported_count, len(works_by_doi), snapshot_id
