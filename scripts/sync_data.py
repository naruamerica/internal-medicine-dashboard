"""Initial DB populate script.

安全にコピーした imported_records_initial.json の実データを SQLite データベースに登録し、
OpenAlex との照合および初期スナップショットを構築する。
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from internal_medicine_dashboard.src.database import init_database, get_connection
from internal_medicine_dashboard.src.data_service import DataService
from internal_medicine_dashboard.src.openalex_client import OpenAlexClient


def populate_initial_db(fetch_openalex_limit: int = 25):
    """初期DB作成およびサンプル/実在データのOpenAlex照合スナップショット作成。"""
    init_database()
    service = DataService()

    data_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data",
        "imported_records_initial.json",
    )
    if not os.path.exists(data_path):
        print(f"File not found: {data_path}")
        return

    with open(data_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    print(f"Loading {len(records)} records into articles and keywords tables...")
    service.import_articles_from_records(records)
    print("Articles and keywords populated.")

    # 最初の実データスナップショットを作成
    snapshot_id = "snapshot_2026_q4"
    service.create_snapshot(
        snapshot_id=snapshot_id,
        update_type="initial_import",
        note="Initial database import with OpenAlex verified citation data",
    )

    openalex = OpenAlexClient()
    print(f"Fetching OpenAlex citation data for top {fetch_openalex_limit} records to build initial verified snapshot...")

    # DOIがあるものを優先して取得
    records_with_doi = [r for r in records if r.get("doi")]
    target_records = records_with_doi[:fetch_openalex_limit]

    for idx, r in enumerate(target_records, start=1):
        pmid = r["pmid"]
        doi = r.get("doi")
        title = r.get("title", "")
        year = r.get("publication_year")

        print(f"[{idx}/{len(target_records)}] Matching PMID: {pmid}, DOI: {doi}...")
        match_res = openalex.match_article(pmid=pmid, doi=doi, title=title, year=year)
        service.save_citation_data(snapshot_id, match_res)
        time.sleep(0.1)

    service.finalize_snapshot(snapshot_id)
    print(f"Snapshot {snapshot_id} finalized successfully!")


if __name__ == "__main__":
    populate_initial_db(fetch_openalex_limit=20)
