import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from internal_medicine_dashboard.src.database import init_database, get_connection
from internal_medicine_dashboard.src.data_service import DataService
from internal_medicine_dashboard.src.openalex_client import MatchResult, OpenAlexWork

def test_data_service_import():
    init_database()
    service = DataService()
    
    # 既存の安全コピーされたJSONをロード
    json_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data",
        "imported_records_initial.json"
    )
    with open(json_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    # 最初の50件をインポート
    sample_records = records[:50]
    count = service.import_articles_from_records(sample_records)
    print(f"Imported {count} articles successfully.")

    # スナップショット作成テスト
    snap_id = "test_snapshot_2026_q4"
    service.create_snapshot(snap_id, update_type="initial_import", note="Initial test snapshot")

    # 模擬的な引用データ保存テスト
    mock_work = OpenAlexWork(
        openalex_id="https://openalex.org/W42983800",
        doi=sample_records[0].get("doi"),
        title=sample_records[0].get("title"),
        publication_year=sample_records[0].get("publication_year"),
        cited_by_count=15,
        counts_by_year=[
            {"year": 2026, "cited_by_count": 2},
            {"year": 2025, "cited_by_count": 8},
            {"year": 2024, "cited_by_count": 5},
        ]
    )
    mock_match = MatchResult(
        pmid=sample_records[0]["pmid"],
        doi=sample_records[0].get("doi"),
        openalex_id=mock_work.openalex_id,
        match_method="DOI",
        match_confidence=1.0,
        match_status="Matched",
        work=mock_work,
    )
    service.save_citation_data(snap_id, mock_match)
    service.finalize_snapshot(snap_id)

    conn = get_connection()
    c_snap = conn.execute("SELECT * FROM citation_snapshots WHERE snapshot_id = ?;", (snap_id,)).fetchall()
    print("Citation snapshots count:", len(c_snap))
    assert len(c_snap) == 1

    ann_cites = conn.execute("SELECT * FROM annual_citations WHERE pmid = ?;", (sample_records[0]["pmid"],)).fetchall()
    print("Annual citations count:", len(ann_cites))
    assert len(ann_cites) == 3

    print("Data service test passed!")

if __name__ == "__main__":
    test_data_service_import()
