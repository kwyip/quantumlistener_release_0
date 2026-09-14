from __future__ import annotations

import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import UTC, datetime

from app.domain.models import Paper

API_URL = "https://export.arxiv.org/api/query"
USER_AGENT = "QuantumListener/0.1 (+https://github.com/quantumlistener; research digest)"
ATOM = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
_VERSION = re.compile(r"^(?P<id>\d{4}\.\d{4,5}|[a-z-]+/\d{7})(?:v(?P<version>\d+))?$")


def exact_week_window(reference: datetime) -> tuple[datetime, datetime]:
    reference = reference.astimezone(UTC)
    start = reference.replace(hour=0, minute=0, second=0, microsecond=0)
    start = start.fromordinal(start.toordinal() - start.weekday()).replace(tzinfo=UTC)
    return start, start.replace(day=start.day) + __import__("datetime").timedelta(days=7)


def resolve_arxiv_version(identifier: str) -> tuple[str, int]:
    value = identifier.rsplit("/abs/", 1)[-1]
    match = _VERSION.match(value)
    if not match:
        raise ValueError("invalid arXiv identifier")
    return match["id"], int(match["version"] or 1)


def normalize_paper(entry: ET.Element, run_id: str, retrieved_at: datetime) -> Paper:
    raw_id = entry.findtext("a:id", namespaces=ATOM) or ""
    arxiv_id, version = resolve_arxiv_version(raw_id)
    links = {
        item.attrib.get("type"): item.attrib.get("href") for item in entry.findall("a:link", ATOM)
    }
    categories = [item.attrib["term"] for item in entry.findall("a:category", ATOM)]
    return Paper(
        arxiv_id=arxiv_id,
        version=version,
        title=" ".join((entry.findtext("a:title", namespaces=ATOM) or "").split()),
        authors=[
            a.findtext("a:name", namespaces=ATOM) or "" for a in entry.findall("a:author", ATOM)
        ],
        abstract=" ".join((entry.findtext("a:summary", namespaces=ATOM) or "").split()),
        submitted_at=datetime.fromisoformat(
            (entry.findtext("a:published", namespaces=ATOM) or "").replace("Z", "+00:00")
        ),
        updated_at=datetime.fromisoformat(
            (entry.findtext("a:updated", namespaces=ATOM) or "").replace("Z", "+00:00")
        ),
        primary_arxiv_category=(
            entry.find("arxiv:primary_category", ATOM).attrib["term"]
            if entry.find("arxiv:primary_category", ATOM) is not None
            else categories[0]
        ),
        all_arxiv_categories=categories,
        pdf_url=links.get("application/pdf", f"https://arxiv.org/pdf/{arxiv_id}"),
        abstract_url=f"https://arxiv.org/abs/{arxiv_id}v{version}",
        doi=entry.findtext("arxiv:doi", namespaces=ATOM),
        journal_reference=entry.findtext("arxiv:journal_ref", namespaces=ATOM),
        comment=entry.findtext("arxiv:comment", namespaces=ATOM),
        ingestion_run_id=run_id,
        retrieved_at=retrieved_at,
    )


def deduplicate_papers(papers: list[Paper]) -> list[Paper]:
    latest: dict[str, Paper] = {}
    for paper in papers:
        if paper.arxiv_id not in latest or paper.version > latest[paper.arxiv_id].version:
            latest[paper.arxiv_id] = paper
    return sorted(latest.values(), key=lambda p: (p.updated_at, p.arxiv_id))


def fetch_arxiv_metadata(identifier: str, opener: Callable = urllib.request.urlopen) -> list[Paper]:
    arxiv_id, _ = resolve_arxiv_version(identifier)
    now = datetime.now(UTC)
    url = f"{API_URL}?id_list={urllib.parse.quote(arxiv_id)}"
    with opener(
        urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=30
    ) as response:
        root = ET.fromstring(response.read())
    return [normalize_paper(entry, "metadata", now) for entry in root.findall("a:entry", ATOM)]


def fetch_quant_ph_papers(
    start: datetime,
    end: datetime,
    run_id: str,
    *,
    page_size: int = 100,
    opener: Callable = urllib.request.urlopen,
    sleep: Callable = time.sleep,
    max_retries: int = 3,
) -> list[Paper]:
    if start >= end or start.tzinfo is None or end.tzinfo is None:
        raise ValueError("an ordered timezone-aware interval is required")
    collected: list[Paper] = []
    offset = 0
    retrieved = datetime.now(UTC)

    def stamp(value: datetime) -> str:
        return value.astimezone(UTC).strftime("%Y%m%d%H%M")

    query = f"cat:quant-ph AND lastUpdatedDate:[{stamp(start)} TO {stamp(end)}]"
    while True:
        params = urllib.parse.urlencode(
            {
                "search_query": query,
                "start": offset,
                "max_results": page_size,
                "sortBy": "lastUpdatedDate",
                "sortOrder": "ascending",
            }
        )
        request = urllib.request.Request(f"{API_URL}?{params}", headers={"User-Agent": USER_AGENT})
        for attempt in range(max_retries):
            try:
                with opener(request, timeout=30) as response:
                    root = ET.fromstring(response.read())
                break
            except (OSError, ET.ParseError):
                if attempt + 1 == max_retries:
                    raise
                sleep(2**attempt)
        entries = root.findall("a:entry", ATOM)
        batch = [normalize_paper(entry, run_id, retrieved) for entry in entries]
        collected.extend(
            p for p in batch if start <= p.updated_at < end and "quant-ph" in p.all_arxiv_categories
        )
        total_text = root.findtext("{http://a9.com/-/spec/opensearch/1.1/}totalResults")
        total = int(total_text or len(entries))
        offset += len(entries)
        if not entries or offset >= total:
            break
        sleep(3)
    return deduplicate_papers(collected)
