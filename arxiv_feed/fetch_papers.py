#!/usr/bin/env python3
"""Fetch the latest arXiv papers matching maternal health & pregnancy keywords and write to papers.json."""

import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

# ── Configuration ──────────────────────────────────────────────────────────────
SEARCH_QUERY = (
    'all:"maternal health" OR all:"maternal mortality" OR all:"maternal morbidity"'
    ' OR all:"pregnancy outcome" OR all:"prenatal care" OR all:"antenatal care"'
    ' OR all:"obstetric" OR all:"preeclampsia" OR all:"gestational diabetes"'
    ' OR all:"postpartum" OR all:"perinatal" OR all:"neonatal mortality"'
    ' OR all:"cesarean" OR all:"preterm birth" OR all:"fetal health"'
    ' OR all:"endometriosis" OR all:"postpartum depression"'
)
MAX_RESULTS = 30
SORT_BY = "submittedDate"
SORT_ORDER = "descending"

ARXIV_API_URL = "http://export.arxiv.org/api/query"
ATOM_NS = "{http://www.w3.org/2005/Atom}"

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_JSON = os.path.join(OUTPUT_DIR, "papers.json")
OUTPUT_JS = os.path.join(OUTPUT_DIR, "papers.js")


def build_query_url() -> str:
    """Build the arXiv API query URL."""
    params = urllib.request.quote(SEARCH_QUERY, safe="")
    return (
        f"{ARXIV_API_URL}?"
        f"search_query={params}"
        f"&sortBy={SORT_BY}"
        f"&sortOrder={SORT_ORDER}"
        f"&start=0"
        f"&max_results={MAX_RESULTS}"
    )


def clean_text(text: str | None) -> str:
    """Collapse whitespace and strip leading/trailing spaces."""
    if text is None:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def parse_entry(entry: ET.Element) -> dict:
    """Extract paper metadata from a single Atom <entry>."""
    # Title
    title = clean_text(entry.findtext(f"{ATOM_NS}title"))

    # Authors
    authors = [
        clean_text(author.findtext(f"{ATOM_NS}name"))
        for author in entry.findall(f"{ATOM_NS}author")
    ]

    # Abstract
    abstract = clean_text(entry.findtext(f"{ATOM_NS}summary"))

    # Published date
    published = entry.findtext(f"{ATOM_NS}published", "")

    # Abstract page URL (the <id> element)
    abstract_url = clean_text(entry.findtext(f"{ATOM_NS}id"))

    # PDF link – look for <link> with title="pdf"
    pdf_url = ""
    for link in entry.findall(f"{ATOM_NS}link"):
        if link.get("title") == "pdf":
            pdf_url = link.get("href", "")
            break

    # Categories
    categories = [
        cat.get("term", "")
        for cat in entry.findall(f"{ATOM_NS}category")
        if cat.get("term")
    ]

    return {
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "published": published,
        "abstract_url": abstract_url,
        "pdf_url": pdf_url,
        "categories": categories,
    }


def fetch_papers() -> list[dict]:
    """Query the arXiv API and return a list of paper dicts."""
    url = build_query_url()
    print(f"Fetching: {url}")

    req = urllib.request.Request(url, headers={"User-Agent": "arXiv-feed-bot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status != 200:
                print(f"Error: HTTP {resp.status}", file=sys.stderr)
                sys.exit(1)
            data = resp.read()
    except Exception as exc:
        print(f"Error fetching arXiv API: {exc}", file=sys.stderr)
        sys.exit(1)

    root = ET.fromstring(data)

    # Check for API-level errors
    # The arXiv API embeds errors inside the feed as entries with <title> starting with "Error"
    entries = root.findall(f"{ATOM_NS}entry")
    if not entries:
        print("Warning: No entries returned by arXiv API.")
        return []

    papers = []
    for entry in entries:
        paper = parse_entry(entry)
        # Skip error pseudo-entries
        if paper["title"].lower().startswith("error"):
            print(f"API error entry: {paper['title']}", file=sys.stderr)
            continue
        papers.append(paper)

    print(f"Fetched {len(papers)} papers.")
    return papers


def main() -> None:
    papers = fetch_papers()

    output = {
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "query": SEARCH_QUERY,
        "papers": papers,
    }

    json_str = json.dumps(output, indent=2, ensure_ascii=False)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        f.write(json_str)

    with open(OUTPUT_JS, "w", encoding="utf-8") as f:
        f.write(f"const PAPERS_DATA = {json_str};\n")

    print(f"Wrote {len(papers)} papers to {OUTPUT_JSON} and {OUTPUT_JS}")


if __name__ == "__main__":
    main()
