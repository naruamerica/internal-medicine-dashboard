import os
import sys

# プロジェクトルートを追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from internal_medicine_dashboard.src.database import init_database, get_connection

def test_db_setup():
    init_database()
    conn = get_connection()
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
    print("Created tables:", tables)
    expected = [
        "articles",
        "article_matches",
        "snapshots",
        "citation_snapshots",
        "annual_citations",
        "keywords",
        "update_history"
    ]
    for exp in expected:
        assert exp in tables, f"Missing table: {exp}"
    print("All required tables verified successfully!")

if __name__ == "__main__":
    test_db_setup()
