"""Cliente DSpace 7+ REST (verificado contra Arca Fiocruz, DSpace 9.3).

Padrão: GET {api}/discover/search/objects?size=N&page=P&_embed=thumbnail...
Depois GET {api}/core/items/{uuid} para metadados completos.
"""
from __future__ import annotations

import logging
import time
import random
from typing import Iterator

import requests

log = logging.getLogger(__name__)
UA = "dominio-publico-metadata-crawler/0.1"


def _get(session: requests.Session, url: str, timeout: int, retries: int = 5, **kw):
    last = None
    for i in range(1, retries + 1):
        try:
            r = session.get(url, timeout=timeout, **kw)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last = e
            time.sleep(min(60, 2 ** i + random.uniform(0, 1)))
    raise RuntimeError(f"GET {url} falhou após {retries}: {last}")


def iter_items(api_base: str, size: int = 100, max_items: int | None = None,
               delay: float = 1.5, timeout: int = 30) -> Iterator[dict]:
    """Itera objetos do discover; para cada um busca o item completo."""
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "application/json"})
    page, n = 0, 0
    total = None
    while True:
        time.sleep(delay + random.uniform(0, 1))
        data = _get(s, f"{api_base}/discover/search/objects",
                    timeout, params={"size": size, "page": page})
        search_result = data.get("_embedded", {}).get("searchResult", {})
        if total is None:
            total = search_result.get("page", {}).get("totalElements")
            log.info("DSpace REST: total=%s", total)
        objects = search_result.get("_embedded", {}).get("objects", [])
        if not objects:
            return
        for obj in objects:
            href = (obj.get("_links", {}).get("indexableObject", {}) or {}).get("href")
            if not href:
                continue
            time.sleep(delay + random.uniform(0, 1))
            item = _get(s, href, timeout)
            yield {"uuid_href": href, "total": total, "item": item}
            n += 1
            if max_items is not None and n >= max_items:
                return
        page += 1


def flatten_item(item: dict, portal: str, ui_base: str) -> dict:
    """Achata metadados DSpace (metadata dict) para o schema unificado."""
    meta = item.get("metadata", {})
    def first(field: str) -> str:
        vals = meta.get(field, [])
        return (vals[0].get("value", "") if vals else "").strip()
    def all_vals(field: str) -> str:
        return "; ".join(v.get("value", "").strip() for v in meta.get(field, []))
    handle = first("dc.identifier.uri")
    return {
        "portal": portal,
        "identifier": handle or item.get("uuid", ""),
        "title": first("dc.title"),
        "creator": all_vals("dc.contributor.author") or all_vals("dc.creator"),
        "date": first("dc.date.issued") or first("dc.date.available"),
        "type": first("dc.type"),
        "rights": first("dc.rights") or first("dc.rights.uri"),
        "subject": all_vals("dc.subject"),
        "description": first("dc.description.abstract")[:2000],
        "url": handle or f"{ui_base}/entities/publication/{item.get('uuid','')}",
        "handle": handle,
    }
