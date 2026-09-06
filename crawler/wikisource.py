"""Coletor Wikisource PT via MediaWiki API pública.

Docs: https://www.mediawiki.org/wiki/API:Allpages
- Lista: list=allpages, apnamespace=0, aplimit=max (500), paginação via apcontinue
- Metadados: prop=info|revisions (inprop=url, rvprop=ids|timestamp|user|size)
"""
from __future__ import annotations

import time
import random
from typing import Iterator

import requests

API = "https://pt.wikisource.org/w/api.php"
UA = "dominio-publico-metadata-crawler/0.1 (pesquisa; contato via repo)"
LIMIT = 500


def _get(params: dict, timeout: int = 30) -> dict:
    r = requests.get(API, params={"format": "json", **params},
                     headers={"User-Agent": UA}, timeout=timeout)
    r.raise_for_status()
    return r.json()


def site_stats() -> dict:
    data = _get({"action": "query", "meta": "siteinfo", "siprop": "statistics"})
    return data["query"]["statistics"]


def iter_pages(max_pages: int | None = None, delay: float = 0.5,
               namespace: int = 0) -> Iterator[dict]:
    """Itera páginas do namespace com metadados (info+revisão atual)."""
    params: dict = {
        "action": "query",
        "generator": "allpages",
        "gapnamespace": namespace,
        "gaplimit": 50,  # generator limita a 50 com prop
        "prop": "info|revisions",
        "inprop": "url",
        "rvprop": "ids|timestamp|user|size|comment",
    }
    n = 0
    while True:
        time.sleep(delay + random.uniform(0, 0.5))
        data = _get(params)
        for page in data.get("query", {}).get("pages", {}).values():
            yield flatten_page(page)
            n += 1
            if max_pages is not None and n >= max_pages:
                return
        cont = data.get("continue", {}).get("gapcontinue")
        if not cont:
            return
        params["gapcontinue"] = cont


def flatten_page(page: dict) -> dict:
    revs = page.get("revisions") or [{}]
    rev = revs[0]
    return {
        "portal": "wikisource",
        "identifier": str(page.get("pageid", "")),
        "title": page.get("title", ""),
        "creator": rev.get("user", ""),
        "date": (rev.get("timestamp", "") or "")[:10],
        "type": "text",
        "rights": "public domain / free license",
        "subject": "",
        "description": f"len={page.get('length', '')} lastrevid={rev.get('revid', '')}",
        "url": page.get("fullurl", "") or page.get("canonicalurl", ""),
        "handle": page.get("title", ""),
        "raw": {"pageid": page.get("pageid"), "ns": page.get("ns"),
                "touched": page.get("touched")},
    }
