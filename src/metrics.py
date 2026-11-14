"""Metrics and analysis calculation engine for Internal Medicine Citation & Research Trend Dashboard.

要件 4. Burst Articles, 6. High Impact Articles, 3. 各画面仕様 準拠:
- 確定暦年 (Confirmed Year) と年途中 (In-progress Year) の厳密な分離
- Burst Score & Growth Rate 計算
- Emerging Articles 分類 (掲載後3年以内)
- Citation per Year 計算 (経過日数 / 365.25)
- Early Impact Articles 分類 (掲載後12ヶ月未満)
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


def get_latest_confirmed_year(reference_date: Optional[datetime] = None) -> int:
    """基準日における最新の確定暦年を算出する（現在年 - 1）。"""
    dt = reference_date or datetime.now()
    # 暦年が終了している直近の完了年
    return dt.year - 1


def calculate_burst_metrics(
    counts_by_year: Dict[int, int],
    publication_year: Optional[int],
    confirmed_year: Optional[int] = None,
) -> Dict[str, Any]:
    """要件 4.1 / 4.2 に準拠して Burst Score, Growth Rate, Emerging分類を計算する。"""
    c_year = confirmed_year or get_latest_confirmed_year()

    # 掲載後3年以内判定 (例: c_year=2025 で pub_year >= 2023 は掲載後3年以内)
    is_emerging = False
    if publication_year is not None:
        if publication_year >= (c_year - 2):
            is_emerging = True

    c_recent = counts_by_year.get(c_year, 0)
    c_y1 = counts_by_year.get(c_year - 1, 0)
    c_y2 = counts_by_year.get(c_year - 2, 0)
    c_y3 = counts_by_year.get(c_year - 3, 0)

    prev_3yr_avg = (c_y1 + c_y2 + c_y3) / 3.0

    burst_score = None
    growth_rate = None

    if prev_3yr_avg > 0:
        burst_score = c_recent / prev_3yr_avg
        growth_rate = ((c_recent - prev_3yr_avg) / prev_3yr_avg) * 100.0

    return {
        "confirmed_year": c_year,
        "recent_year_citations": c_recent,
        "previous_3yr_citations": [c_y3, c_y2, c_y1],
        "previous_3yr_avg": round(prev_3yr_avg, 2),
        "burst_score": round(burst_score, 2) if burst_score is not None else None,
        "growth_rate": round(growth_rate, 1) if growth_rate is not None else None,
        "is_emerging": is_emerging,
        "is_calculable": prev_3yr_avg > 0,
    }


def calculate_citation_per_year(
    total_citations: int,
    publication_date_str: Optional[str],
    publication_year: Optional[int],
    reference_date: Optional[datetime] = None,
) -> Dict[str, Any]:
    """要件 6.1 / 6.2 に準拠して Citation per Year および Early Impact 判定を行う。"""
    ref_dt = reference_date or datetime.now()

    pub_dt = None
    if publication_date_str:
        # 様々な日付形式のパースを試みる
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m", "%Y"):
            try:
                pub_dt = datetime.strptime(publication_date_str[:10].strip(), fmt)
                break
            except Exception:
                continue

    if pub_dt is None and publication_year:
        # 年のみの場合、年の真ん中(7月1日)として概算
        pub_dt = datetime(publication_year, 7, 1)

    if pub_dt is None:
        return {
            "years_since_publication": None,
            "citation_per_year": None,
            "is_early_impact": False,
        }

    diff_days = (ref_dt - pub_dt).days
    if diff_days < 0:
        diff_days = 1

    years_since = diff_days / 365.25
    is_early_impact = years_since < 1.0  # 掲載後12か月未満

    cpy = total_citations / years_since if years_since > 0 else 0.0

    return {
        "days_since_publication": diff_days,
        "years_since_publication": round(years_since, 2),
        "citation_per_year": round(cpy, 2),
        "is_early_impact": is_early_impact,
    }
