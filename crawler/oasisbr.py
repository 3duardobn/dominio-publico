"""Coletor OasisBR (VuFind 7.1.1) via RSS do Search/Results.

OAI-PMH desabilitado ("OAI Server Not Configured"); api/v1/search é
intermitente; o RSS (&view=rss, 50 itens/página) foi o mais estável.
Paginação VuFind: &page=N (1-based).
"""
from __future__ import annotations

import time
import random
import logging
from typing import Iterator
from html import unescape

import requests
import xml.etree.ElementTree as ET

log = logging.getLogger(__name__)
BASE = "https://oasisbr.ibict.br/vufind/Search/Results"
UA = "dominio-publico-metadata-crawler/0.1"
PAGE_SIZE = 50


def _fetch_rss(lookfor: str, search_type: str, page: int,
               timeout: int = 30, retries: int = 5) -> ET.Element:
    """Busca RSS com parser tolerante (VuFind às vezes emite XML inválido)."""
    from bs4 import BeautifulSoup
    params = {"lookfor": lookfor, "type": search_type,
              "view": "rss", "page": page}
    last = None
    for i in range(1, retries + 1):
        try:
            time.sleep(1.5 + random.uniform(0, 1))
            r = requests.get(BASE, params=params,
                             headers={"User-Agent": UA}, timeout=timeout)
            r.raise_for_status()
            if b"<rss" not in r.content[:2000]:
                raise RuntimeError(
                    "OasisBR retornou página de verificação JS (não o RSS). "
                    "Tente mais tarde ou de outra rede; alternativa: OpenAIRE API.")
            try:
                return ET.fromstring(r.content)
            except ET.ParseError:
                # fallback: BeautifulSoup com recovery, reconverte p/ ET
                soup = BeautifulSoup(r.content, "lxml-xml")
                return ET.fromstring(str(soup).encode("utf-8"))
        except Exception as e:
            last = e
            log.warning("oasisbr rss p%d tentativa %d: %s", page, i, e)
            time.sleep(min(60, 2 ** i))
    raise RuntimeError(f"OasisBR RSS falhou: {last}")


def _text(el: ET.Element | None) -> str:
    if el is None or not el.text:
        return ""
    return unescape(el.text).strip()


def parse_rss(root: ET.Element) -> tuple[list[dict], str]:
    """Retorna (itens, total_raw). Namespace-agnóstico via sufixo de tag."""
    def find(parent: ET.Element, name: str) -> ET.Element | None:
        for child in parent.iter():
            if child.tag.split("}")[-1] == name:
                return child
        return None

    channel = None
    for el in root.iter():
        if el.tag.split("}")[-1] == "channel":
            channel = el
            break
    if channel is None:
        return [], ""
    total_raw = ""
    desc = None
    for child in channel:
        if child.tag.split("}")[-1] == "description" and child.text:
            total_raw = _text(child)
            break
    items = []
    for it in channel:
        if it.tag.split("}")[-1] != "item":
            continue
        get = lambda n: _text(find(it, n))  # noqa: E731
        items.append({
            "portal": "oasisbr",
            "identifier": get("guid") or get("link"),
            "title": get("title"),
            "creator": get("author") or get("creator"),
            "date": get("pubDate"),
            "type": "",
            "rights": "",
            "subject": "",
            "description": get("description")[:2000],
            "url": get("link"),
            "handle": get("guid") or get("link"),
            "raw": {},
        })
    return items, total_raw


def iter_search(lookfor: str = "*:*", search_type: str = "AllFields",
                max_items: int | None = 100) -> Iterator[dict]:
    page, n = 1, 0
    while True:
        root = _fetch_rss(lookfor, search_type, page)
        items, total_raw = parse_rss(root)
        if not items:
            return
        for it in items:
            if it["title"]:  # pula itens vazios
                yield it
                n += 1
                if max_items is not None and n >= max_items:
                    return
        if len(items) < PAGE_SIZE:
            return
        page += 1
