"""Cliente ArticleMeta SciELO (REST verificado: articlemeta.scielo.org).

Coleções: scl=Brasil. Endpoints: /api/v1/journal, /issue, /article.
"""
from __future__ import annotations

import time
import random
from typing import Iterator

import requests

BASE = "http://articlemeta.scielo.org/api/v1"
UA = "dominio-publico-metadata-crawler/0.1"


def _get(path: str, params: dict, timeout: int = 30) -> list | dict:
    r = requests.get(f"{BASE}/{path}", params=params,
                     headers={"User-Agent": UA}, timeout=timeout)
    r.raise_for_status()
    return r.json()


def iter_journals(collection: str = "scl", limit: int = 100,
                  delay: float = 1.0) -> Iterator[dict]:
    offset, n = 0, 0
    while True:
        time.sleep(delay + random.uniform(0, 0.5))
        data = _get("journal", {"collection": collection, "limit": limit, "offset": offset})
        if not data:
            return
        for j in data:
            yield j
            n += 1
        offset += limit


def iter_articles(collection: str = "scl", limit: int = 100,
                  max_items: int | None = None, delay: float = 1.0) -> Iterator[dict]:
    offset, n = 0, 0
    while True:
        time.sleep(delay + random.uniform(0, 0.5))
        data = _get("articles", {"collection": collection, "limit": limit, "offset": offset})
        objs = data.get("objects", []) if isinstance(data, dict) else data
        if not objs:
            return
        for a in objs:
            yield flatten_article(a, collection)
            n += 1
            if max_items is not None and n >= max_items:
                return
        offset += limit


def flatten_article(a: dict, collection: str) -> dict:
    code = a.get("code", "")
    return {
        "portal": "scielo",
        "identifier": code,
        "title": (a.get("title") or "")[:500] if isinstance(a.get("title"), str) else "",
        "creator": "; ".join(
            x.get("given_names", "") + " " + x.get("surname", "")
            for x in (a.get("authors") or []) if isinstance(x, dict))[:1000],
        "date": a.get("publication_date", "") or a.get("processing_date", ""),
        "type": "article",
        "rights": "open access",
        "subject": "; ".join(a.get("subject_areas", []) or [])[:500],
        "description": "",
        "url": f"https://www.scielo.br/j/{code}/" if code else "",
        "handle": code,
    }
