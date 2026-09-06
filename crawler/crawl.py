"""Orquestrador do censo de metadados (fase lista + fase detalhes opcional)."""
from __future__ import annotations

import logging
from pathlib import Path

from .config import RESULT_URL, DETAIL_URL, MEDIAS, DEFAULT_PAGE_SIZE
from .fetch import Fetcher
from .parse import parse_result_page, parse_detail_page
from .store import Store

log = logging.getLogger(__name__)


def build_list_params(co_midia: int, pagina: int, skip: int,
                      page_size: int = DEFAULT_PAGE_SIZE) -> dict:
    return {
        "first": str(page_size),
        "skip": str(skip),
        "ds_titulo": "",
        "co_autor": "",
        "no_autor": "",
        "co_categoria": "",
        "pagina": str(pagina),
        "select_action": "Submit",
        "co_midia": str(co_midia),
        "co_obra": "",
        "co_idioma": "",
        "colunaOrdenar": "DS_TITULO",
        "ordem": "asc",
    }


def crawl_lista(fetcher: Fetcher, store: Store, co_midia: int,
                max_pages: int | None = None,
                page_size: int = DEFAULT_PAGE_SIZE,
                resume: bool = True) -> dict:
    """Varre todas as páginas de listagem de uma mídia. Retorna estatística."""
    midia_nome = MEDIAS[co_midia]
    pagina, skip, total = 1, 0, None
    stats = {"paginas": 0, "obras": 0, "total_reportado": None}
    while True:
        if max_pages is not None and stats["paginas"] >= max_pages:
            break
        if resume and store.pagina_feita(co_midia, pagina):
            log.info("[%s] página %d já feita (resume), pulando", midia_nome, pagina)
            pagina += 1
            skip += page_size
            continue
        params = build_list_params(co_midia, pagina, skip, page_size)
        url = RESULT_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items())
        html = fetcher.get(RESULT_URL, params=params)
        parsed = parse_result_page(html, page_url=url)
        if parsed["total"] is not None:
            total = parsed["total"]
            stats["total_reportado"] = total
        for obra in parsed["obras"]:
            obra["co_midia"] = co_midia
            obra["midia_nome"] = midia_nome
            if obra.get("co_obra"):
                store.upsert_obra(obra)
                stats["obras"] += 1
        store.mark_pagina(co_midia, pagina, skip, total, len(parsed["obras"]), url)
        store.commit()
        stats["paginas"] += 1
        log.info("[%s] pág %d: %d obras (total reportado: %s)",
                 midia_nome, pagina, len(parsed["obras"]), total)
        if not parsed["obras"]:
            break  # fim da paginação
        if total is not None and skip + page_size >= total:
            break
        pagina += 1
        skip += page_size
    return stats


def crawl_detalhes(fetcher: Fetcher, store: Store, co_midia: int | None = None,
                   limit: int | None = None) -> dict:
    """Visita DetalheObraForm.do para cada co_obra sem detalhe. Caro: ~2s/obra."""
    q = "SELECT co_obra FROM obras WHERE download_url IS NULL"
    args: list = []
    if co_midia is not None:
        q += " AND co_midia=?"
        args.append(co_midia)
    q += " ORDER BY co_obra"
    if limit is not None:
        q += " LIMIT ?"
        args.append(limit)
    ids = [r[0] for r in store.conn.execute(q, args).fetchall()]
    n = 0
    for co_obra in ids:
        try:
            html = fetcher.get(DETAIL_URL, params={"select_action": "", "co_obra": co_obra})
            detalhe = parse_detail_page(html, co_obra=co_obra)
            store.merge_detalhe(co_obra, detalhe)
            n += 1
            if n % 20 == 0:
                store.commit()
                log.info("detalhes: %d/%d", n, len(ids))
        except Exception as e:
            log.warning("detalhe %s falhou: %s", co_obra, e)
    store.commit()
    return {"detalhes_ok": n, "detalhes_total": len(ids)}
