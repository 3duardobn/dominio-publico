"""Colheita multi-portal para a tabela unificada `registros`."""
from __future__ import annotations

import logging

from . import dspace_rest, scielo_meta, oai as oai_mod
from . import wikisource as wiki_mod
from . import oasisbr as oasis_mod
from . import hemeroteca as heme_mod
from .store import Store

log = logging.getLogger(__name__)


def colher_arca(store: Store, api_base: str, ui_base: str,
                max_items: int | None = 100, size: int = 20) -> int:
    n = 0
    for entry in dspace_rest.iter_items(api_base, size=size,
                                        max_items=max_items, delay=1.0):
        reg = dspace_rest.flatten_item(entry["item"], "arca", ui_base)
        reg["raw"] = {"uuid_href": entry["uuid_href"]}
        store.upsert_registro(reg)
        n += 1
        if n % 20 == 0:
            store.commit()
    store.commit()
    return n


def colher_scielo(store: Store, collection: str = "scl",
                  max_items: int | None = 100) -> int:
    n = 0
    for reg in scielo_meta.iter_articles(collection, max_items=max_items):
        reg["raw"] = {}
        store.upsert_registro(reg)
        n += 1
        if n % 50 == 0:
            store.commit()
    store.commit()
    return n


def _flat(v) -> str:
    if isinstance(v, list):
        return "; ".join(str(x) for x in v)[:1000]
    return str(v or "")


def colher_oai(store: Store, portal: str, oai_url: str,
               max_records: int | None = 100) -> int:
    n = 0
    for rec in oai_mod.list_records(oai_url, max_records=max_records):
        if rec.get("deleted"):
            continue
        ident = _flat(rec.get("identifier"))
        reg = {
            "portal": portal,
            "identifier": ident[:500],
            "title": _flat(rec.get("title"))[:500],
            "creator": _flat(rec.get("creator")),
            "date": _flat(rec.get("date")),
            "type": _flat(rec.get("type")),
            "rights": _flat(rec.get("rights")),
            "subject": _flat(rec.get("subject"))[:500],
            "description": _flat(rec.get("description"))[:2000],
            "url": ident[:500],
            "handle": ident[:500],
            "raw": rec,
        }
        store.upsert_registro(reg)
        n += 1
        if n % 50 == 0:
            store.commit()
    store.commit()
    return n


def colher_wikisource(store: Store, max_items: int | None = 100) -> int:
    n = 0
    for reg in wiki_mod.iter_pages(max_pages=max_items):
        reg["raw"] = reg.get("raw", {})
        store.upsert_registro(reg)
        n += 1
        if n % 100 == 0:
            store.commit()
    store.commit()
    return n


def colher_oasisbr(store: Store, lookfor: str = "*:*",
                   max_items: int | None = 100) -> int:
    n = 0
    for reg in oasis_mod.iter_search(lookfor, max_items=max_items):
        store.upsert_registro(reg)
        n += 1
        if n % 50 == 0:
            store.commit()
    store.commit()
    return n


def colher_hemeroteca(store: Store, max_titulos: int | None = 50,
                     bibs: list[str] | None = None) -> int:
    if bibs:
        entries = [{"bib": b, "titulo": ""} for b in bibs]
    else:
        entries = heme_mod.listar_bibs()
        entries = entries[:max_titulos] if max_titulos else entries
    n = 0
    for entry in entries:
        try:
            reg = heme_mod.ler_exemplar(entry["bib"])
            if entry.get("titulo") and not reg["title"]:
                reg["title"] = entry["titulo"]
            store.upsert_registro(reg)
            n += 1
            if n % 20 == 0:
                store.commit()
        except Exception as e:
            log.warning("hemeroteca bib %s: %s", entry["bib"], e)
    store.commit()
    return n
