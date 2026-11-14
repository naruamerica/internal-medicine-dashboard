"""PubMed E-utilities client for Internal Medicine Citation & Research Trend Dashboard.

要件 4.1 PubMed 準拠:
- 検索式: "Intern Med"[Journal]
- ISSN検証: 1349-7235 (Online), 0918-2918 (Print)
- 取得項目: PMID, Title, Author, Journal, Publication Date, DOI, Abstract, Publication Type, Author Keywords, MeSH Terms
"""

import datetime
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

JOURNAL_QUERY_TERM = '"Intern Med"[Journal]'
TARGET_ISSNS: Set[str] = {"1349-7235", "0918-2918"}
EUTILS_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


@dataclass
class PubMedArticle:
    pmid: str
    doi: Optional[str]
    title: str
    authors: str
    affiliations: str
    publication_date: Optional[str]
    publication_year: Optional[int]
    article_type: str
    abstract: str
    journal_title: str
    keywords: List[str] = field(default_factory=list)
    mesh_terms: List[str] = field(default_factory=list)


class PubMedClient:
    def __init__(self, email: str = "ogasa@example.com", api_key: Optional[str] = None):
        self.email = email
        self.api_key = api_key
        self.request_interval = 0.34 if api_key else 0.4

    def search_articles(self, query: str = JOURNAL_QUERY_TERM, retmax: int = 500) -> List[str]:
        """PubMedで検索を実行し、PMIDリストを取得する。"""
        url = (
            f"{EUTILS_BASE_URL}/esearch.fcgi?db=pubmed&term={urllib.parse.quote(query)}"
            f"&retmode=json&retmax={retmax}&usehistory=y&email={self.email}"
        )
        if self.api_key:
            url += f"&api_key={self.api_key}"

        time.sleep(self.request_interval)
        req = urllib.request.Request(url, headers={"User-Agent": "InternalMedicineDashboard/1.2"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("esearchresult", {}).get("idlist", [])
        except Exception as e:
            logger.error(f"PubMed search failed: {e}")
            return []

    def fetch_article_summaries(self, pmids: List[str], chunk_size: int = 100) -> List[PubMedArticle]:
        """PMIDリストに対して efetch (XML) を実行し、詳細情報をパースする。"""
        articles: List[PubMedArticle] = []
        for i in range(0, len(pmids), chunk_size):
            chunk = pmids[i : i + chunk_size]
            url = f"{EUTILS_BASE_URL}/efetch.fcgi?db=pubmed&id={','.join(chunk)}&retmode=xml&email={self.email}"
            if self.api_key:
                url += f"&api_key={self.api_key}"

            time.sleep(self.request_interval)
            req = urllib.request.Request(url, headers={"User-Agent": "InternalMedicineDashboard/1.2"})
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    xml_content = resp.read()
                    root = ET.fromstring(xml_content)
                    for art_elem in root.findall(".//PubmedArticle"):
                        parsed = self._parse_article(art_elem)
                        if parsed:
                            articles.append(parsed)
            except Exception as e:
                logger.error(f"efetch failed for chunk {i}: {e}")

        return articles

    def _parse_article(self, elem: ET.Element) -> Optional[PubMedArticle]:
        """PubmedArticle XML 要素をパースする。"""
        pmid_elem = elem.find(".//MedlineCitation/PMID")
        if pmid_elem is None or not pmid_elem.text:
            return None
        pmid = pmid_elem.text.strip()

        article_elem = elem.find(".//MedlineCitation/Article")
        if article_elem is None:
            return None

        # Title
        title_elem = article_elem.find("ArticleTitle")
        title = "".join(title_elem.itertext()).strip() if title_elem is not None else ""

        # Journal / ISSN
        journal_elem = article_elem.find("Journal")
        journal_title = "Internal Medicine"
        if journal_elem is not None:
            jt_elem = journal_elem.find("Title")
            if jt_elem is not None and jt_elem.text:
                journal_title = jt_elem.text.strip()

        # DOI
        doi = None
        for eid in article_elem.findall("ELocationID"):
            if eid.get("EIdType") == "doi" and eid.text:
                doi = eid.text.strip()
                break
        if not doi:
            for aid in elem.findall(".//PubmedData/ArticleIdList/ArticleId"):
                if aid.get("IdType") == "doi" and aid.text:
                    doi = aid.text.strip()
                    break

        # Authors & Affiliations
        authors_list = []
        affils_list = []
        for author in article_elem.findall(".//AuthorList/Author"):
            last_name = author.find("LastName")
            fore_name = author.find("ForeName")
            if last_name is not None and last_name.text:
                fname = fore_name.text.strip() if fore_name is not None and fore_name.text else ""
                authors_list.append(f"{last_name.text.strip()} {fname}".strip())
            for aff in author.findall(".//AffiliationInfo/Affiliation"):
                if aff.text:
                    affils_list.append(aff.text.strip())

        authors_str = "; ".join(authors_list)
        affils_str = "; ".join(set(affils_list))

        # Publication Date & Year
        pub_year = None
        pub_date_str = None
        journal_issue = article_elem.find(".//Journal/JournalIssue/PubDate")
        if journal_issue is not None:
            y = journal_issue.find("Year")
            if y is not None and y.text and y.text.strip().isdigit():
                pub_year = int(y.text.strip())
            m = journal_issue.find("Month")
            d = journal_issue.find("Day")
            if pub_year:
                m_str = m.text.strip() if m is not None and m.text else "01"
                d_str = d.text.strip() if d is not None and d.text else "01"
                pub_date_str = f"{pub_year}-{m_str:>02}-{d_str:>02}"

        # Publication Types
        pub_types = [pt.text.strip() for pt in article_elem.findall(".//PublicationTypeList/PublicationType") if pt.text]
        # 代表的なタイプ決定
        article_type = "Journal Article"
        if "Case Reports" in pub_types:
            article_type = "Case Report"
        elif "Review" in pub_types or "Systematic Review" in pub_types:
            article_type = "Review"
        elif "Editorial" in pub_types:
            article_type = "Editorial"
        elif "Letter" in pub_types:
            article_type = "Letter"

        # Abstract
        abstract_parts = []
        for ab in article_elem.findall(".//Abstract/AbstractText"):
            if ab.text:
                label = ab.get("Label")
                text = "".join(ab.itertext()).strip()
                if label:
                    abstract_parts.append(f"[{label}] {text}")
                else:
                    abstract_parts.append(text)
        abstract = "\n\n".join(abstract_parts)

        # Keywords & MeSH
        keywords = []
        for kw in elem.findall(".//MedlineCitation/KeywordList/Keyword"):
            if kw.text:
                keywords.append(kw.text.strip())

        mesh_terms = []
        for mh in elem.findall(".//MedlineCitation/MeshHeadingList/MeshHeading"):
            desc = mh.find("DescriptorName")
            if desc is not None and desc.text:
                is_major = desc.get("MajorTopicYN") == "Y"
                prefix = "*" if is_major else ""
                mesh_terms.append(f"{prefix}{desc.text.strip()}")

        return PubMedArticle(
            pmid=pmid,
            doi=doi,
            title=title,
            authors=authors_str,
            affiliations=affils_str,
            publication_date=pub_date_str,
            publication_year=pub_year,
            article_type=article_type,
            abstract=abstract,
            journal_title=journal_title,
            keywords=keywords,
            mesh_terms=mesh_terms,
        )
