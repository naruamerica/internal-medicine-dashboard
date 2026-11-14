"""OpenAlex API client for Internal Medicine Citation & Research Trend Dashboard.

要件 4.2 OpenAlex, 4.3 照合管理, 4.4 引用データの保存 準拠:
- OpenAlex APIから論文の被引用情報、年度別被引用数(counts_by_year)を取得
- DOI照合を最優先、不在時はタイトル等で照合
- レートリミット配慮（Polite pool mailto ヘッダー、待機時間）
- 取得失敗と引用数0の厳密な区別
"""

import json
import logging
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

OPENALEX_BASE_URL = "https://api.openalex.org/works"
USER_AGENT = "InternalMedicineDashboard/1.2 (mailto:ogasa@example.com)"


@dataclass
class OpenAlexWork:
    openalex_id: str
    doi: Optional[str]
    title: str
    publication_year: Optional[int]
    cited_by_count: int
    counts_by_year: List[Dict[str, int]]  # [{'year': 2025, 'cited_by_count': 10}, ...]
    keywords: List[str] = field(default_factory=list)
    raw_data: Optional[Dict[str, Any]] = None


@dataclass
class MatchResult:
    pmid: str
    doi: Optional[str]
    openalex_id: Optional[str]
    match_method: str  # 'DOI', 'Title', 'None'
    match_confidence: float
    match_status: str  # 'Matched', 'Pending', 'Rejected'
    work: Optional[OpenAlexWork] = None
    error_message: Optional[str] = None


class OpenAlexClient:
    """OpenAlex API との安全な通信を行うクライアント。"""

    def __init__(self, email: str = "ogasa@example.com", request_delay: float = 0.15):
        self.email = email
        self.request_delay = request_delay
        self.headers = {
            "User-Agent": f"InternalMedicineDashboard/1.2 (mailto:{email})",
            "Accept": "application/json",
        }

    def _http_get(self, url: str, max_retries: int = 3) -> Optional[Dict[str, Any]]:
        """APIリクエストを安全に実行し、リトライを行う。"""
        req = urllib.request.Request(url, headers=self.headers)
        for attempt in range(max_retries):
            try:
                time.sleep(self.request_delay)
                with urllib.request.urlopen(req, timeout=15) as response:
                    if response.status == 200:
                        content = response.read().decode("utf-8")
                        return json.loads(content)
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return None
                if e.code == 429:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                logger.warning(f"HTTP {e.code} for {url} (attempt {attempt + 1})")
            except Exception as e:
                logger.warning(f"Error fetching {url}: {e} (attempt {attempt + 1})")
                time.sleep(0.5 * (attempt + 1))
        return None

    def fetch_works_by_dois(self, dois: List[str], batch_size: int = 50) -> Dict[str, OpenAlexWork]:
        """複数のDOIに対して一括でOpenAlexからWorkを取得する（高速バッチ処理）。"""
        results_map: Dict[str, OpenAlexWork] = {}
        valid_dois = [d.strip() for d in dois if d and d.strip()]
        if not valid_dois:
            return results_map

        for i in range(0, len(valid_dois), batch_size):
            chunk = valid_dois[i : i + batch_size]
            clean_chunk = []
            for d in chunk:
                c = d
                if c.startswith("https://doi.org/"):
                    c = c.replace("https://doi.org/", "")
                elif c.startswith("http://dx.doi.org/"):
                    c = c.replace("http://dx.doi.org/", "")
                clean_chunk.append(f"https://doi.org/{c}")

            encoded_pipe = "|".join([urllib.parse.quote(c, safe="") for c in clean_chunk])
            url = f"{OPENALEX_BASE_URL}?filter=doi:{encoded_pipe}&per_page={batch_size}"

            data = self._http_get(url)
            if data and data.get("results"):
                for work_data in data["results"]:
                    parsed = self._parse_work(work_data)
                    if parsed.doi:
                        # DOIの小文字・正規化でマッピング
                        raw_d = parsed.doi.lower().replace("https://doi.org/", "").strip()
                        results_map[raw_d] = parsed

        return results_map

    def fetch_work_by_doi(self, doi: str) -> Optional[OpenAlexWork]:
        """DOIを指定してOpenAlexからWorkを取得する。"""
        if not doi:
            return None
        # Clean DOI
        clean_doi = doi.strip()
        if clean_doi.startswith("https://doi.org/"):
            clean_doi = clean_doi.replace("https://doi.org/", "")
        elif clean_doi.startswith("http://dx.doi.org/"):
            clean_doi = clean_doi.replace("http://dx.doi.org/", "")

        encoded_doi = urllib.parse.quote(f"https://doi.org/{clean_doi}", safe="")
        url = f"{OPENALEX_BASE_URL}/{encoded_doi}"
        data = self._http_get(url)
        if not data:
            # 代替: filter=doi:...
            alt_url = f"{OPENALEX_BASE_URL}?filter=doi:https://doi.org/{urllib.parse.quote(clean_doi)}"
            res = self._http_get(alt_url)
            if res and res.get("results"):
                data = res["results"][0]

        if not data:
            return None

        return self._parse_work(data)

    def fetch_work_by_title(self, title: str, year: Optional[int] = None) -> Optional[OpenAlexWork]:
        """タイトルと出版年を用いてOpenAlexからWorkを検索する。"""
        if not title or len(title.strip()) < 5:
            return None
        query = urllib.parse.quote(title.strip())
        url = f"{OPENALEX_BASE_URL}?filter=title.search:{query}"
        if year:
            url += f",publication_year:{year}"

        data = self._http_get(url)
        if not data or not data.get("results"):
            return None

        # 最も関連性の高い結果を精査
        results = data["results"]
        candidate = results[0]
        # タイトルの類似度確認（簡易一致確認）
        c_title = (candidate.get("title") or "").strip().lower()
        orig_title = title.strip().lower()
        if c_title == orig_title or (len(orig_title) > 20 and orig_title in c_title) or (len(c_title) > 20 and c_title in orig_title):
            return self._parse_work(candidate)
        return None

    def match_article(self, pmid: str, doi: Optional[str], title: str, year: Optional[int] = None) -> MatchResult:
        """要件 4.2 / 4.3 に準拠して照合を行う。"""
        # 1. DOIによる照合（最優先）
        if doi:
            work = self.fetch_work_by_doi(doi)
            if work:
                return MatchResult(
                    pmid=pmid,
                    doi=doi,
                    openalex_id=work.openalex_id,
                    match_method="DOI",
                    match_confidence=1.0,
                    match_status="Matched",
                    work=work,
                )

        # 2. タイトルによる照合
        if title:
            work = self.fetch_work_by_title(title, year)
            if work:
                return MatchResult(
                    pmid=pmid,
                    doi=doi,
                    openalex_id=work.openalex_id,
                    match_method="Title",
                    match_confidence=0.85,
                    match_status="Matched",
                    work=work,
                )

        # 3. 照合失敗
        return MatchResult(
            pmid=pmid,
            doi=doi,
            openalex_id=None,
            match_method="None",
            match_confidence=0.0,
            match_status="Pending",
            work=None,
            error_message="Work not found in OpenAlex",
        )

    def _parse_work(self, data: Dict[str, Any]) -> OpenAlexWork:
        """APIレスポンス辞書からOpenAlexWorkオブジェクトを生成する。"""
        counts = []
        for c in data.get("counts_by_year", []):
            counts.append({
                "year": c.get("year"),
                "cited_by_count": c.get("cited_by_count", 0),
            })
        # 年降順にソート
        counts.sort(key=lambda x: x.get("year", 0), reverse=True)

        keywords = []
        for kw in data.get("keywords", []):
            name = kw.get("display_name")
            if name:
                keywords.append(name)

        return OpenAlexWork(
            openalex_id=data.get("id", ""),
            doi=data.get("doi"),
            title=data.get("title", ""),
            publication_year=data.get("publication_year"),
            cited_by_count=data.get("cited_by_count", 0),
            counts_by_year=counts,
            keywords=keywords,
            raw_data=data,
        )
