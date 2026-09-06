#!/usr/bin/env python3
"""CLI do indexador de metadados do Portal Domínio Público.

Exemplos:
  # Amostra rápida (2 páginas de texto, sem detalhes) — valida acesso/parse
  python cli.py amostra --midia 2 --max-pages 2

  # Censo completo da fase lista (todas as mídias, ~4k páginas, ~3h com delay 2s)
  python cli.py censo --out-dir data

  # Detalhes de 50 obras de texto (fase cara; full = 100h+)
  python cli.py detalhes --midia 2 --limit 50

  # Exportar o que já está no sqlite
  python cli.py exportar --db data/dominio-publico.db --out-dir data
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from crawler.config import (
    MEDIAS, DEFAULT_PAGE_SIZE, DEFAULT_DELAY, DEFAULT_JITTER,
    DEFAULT_TIMEOUT, DEFAULT_RETRIES, DEFAULT_USER_AGENT,
)
from crawler.crawl import crawl_lista, crawl_detalhes
from crawler.fetch import Fetcher
from crawler.store import Store
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def make_store_fetcher(args) -> tuple[Store, Fetcher]:
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    db = Path(args.db) if args.db else out / "dominio-publico.db"
    store = Store(db)
    fetcher = Fetcher(
        user_agent=args.user_agent,
        timeout=args.timeout,
        delay=args.delay,
        jitter=args.jitter,
        retries=args.retries,
        use_playwright=args.playwright,
    )
    return store, fetcher


def cmd_amostra(args) -> int:
    store, fetcher = make_store_fetcher(args)
    stats = crawl_lista(fetcher, store, args.midia, max_pages=args.max_pages,
                        page_size=args.page_size, resume=False)
    print(stats, f"total_no_banco={store.count()}")
    return 0


def cmd_censo(args) -> int:
    store, fetcher = make_store_fetcher(args)
    midias = [args.midia] if args.midia else sorted(MEDIAS)
    for m in midias:
        stats = crawl_lista(fetcher, store, m, max_pages=None,
                            page_size=args.page_size, resume=not args.no_resume)
        print(f"midia {m} ({MEDIAS[m]}): {stats}")
    print(f"banco: {store.count()} obras")
    do_export(store, Path(args.out_dir))
    return 0


def cmd_detalhes(args) -> int:
    store, fetcher = make_store_fetcher(args)
    stats = crawl_detalhes(fetcher, store, co_midia=args.midia, limit=args.limit)
    print(stats)
    do_export(store, Path(args.out_dir))
    return 0


def do_export(store: Store, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    n1 = store.export_json(out_dir / "obras.json")
    n2 = store.export_csv(out_dir / "obras.csv")
    print(f"exportado: {n1} linhas em obras.json, {n2} em obras.csv (+ sqlite)")


def cmd_exportar(args) -> int:
    store = Store(Path(args.db))
    do_export(store, Path(args.out_dir))
    return 0


def cmd_portais(args) -> int:
    print(Path("portais.yaml").read_text(encoding="utf-8"))
    return 0


def cmd_colher(args) -> int:
    from crawler import portais as P
    store, _ = make_store_fetcher(args)
    if args.portal == "arca":
        n = P.colher_arca(store, "https://api.arca.fiocruz.br/api",
                          "https://arca.fiocruz.br", max_items=args.limit)
    elif args.portal == "scielo":
        n = P.colher_scielo(store, max_items=args.limit)
    elif args.portal == "scielo-livros":
        n = P.colher_oai(store, "scielo-livros",
                         "https://oai.books.scielo.org/oai-pmh",
                         max_records=args.limit)
    elif args.portal == "ipea":
        n = P.colher_oai(store, "ipea",
                         "https://repositorio.ipea.gov.br/server/oai/request",
                         max_records=args.limit)
    elif args.portal == "wikisource":
        n = P.colher_wikisource(store, max_items=args.limit)
    elif args.portal == "oasisbr":
        n = P.colher_oasisbr(store, lookfor=args.busca or "*:*",
                             max_items=args.limit)
    elif args.portal == "hemeroteca":
        n = P.colher_hemeroteca(store, max_titulos=args.limit,
                                bibs=args.bibs.split(",") if args.bibs else None)
    elif args.portal == "oai":
        n = P.colher_oai(store, args.nome or "oai", args.oai_url,
                         max_records=args.limit)
    else:
        print(f"portal '{args.portal}' ainda sem coletor automático; ver portais.yaml")
        return 1
    print(f"coletados: {n} registros ({args.portal}); total={store.count_registros(args.portal)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Indexador de metadados do Domínio Público")
    p.add_argument("--out-dir", default="data")
    p.add_argument("--db", default=None)
    p.add_argument("--delay", type=float, default=DEFAULT_DELAY)
    p.add_argument("--jitter", type=float, default=DEFAULT_JITTER)
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    p.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    p.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    p.add_argument("--playwright", action="store_true",
                   help="usa Chromium como fallback se Cloudflare bloquear requests")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("amostra", help="poucas páginas, sem resume (teste)")
    a.add_argument("--midia", type=int, default=2, choices=sorted(MEDIAS))
    a.add_argument("--max-pages", type=int, default=2)
    a.set_defaults(func=cmd_amostra)

    c = sub.add_parser("censo", help="fase lista completa (todas as páginas)")
    c.add_argument("--midia", type=int, default=None, choices=sorted(MEDIAS))
    c.add_argument("--no-resume", action="store_true")
    c.set_defaults(func=cmd_censo)

    d = sub.add_parser("detalhes", help="fase detalhes (cara, use --limit)")
    d.add_argument("--midia", type=int, default=None, choices=sorted(MEDIAS))
    d.add_argument("--limit", type=int, default=50)
    d.set_defaults(func=cmd_detalhes)

    e = sub.add_parser("exportar", help="gera json+csv a partir do sqlite")
    e.set_defaults(func=cmd_exportar)

    pl = sub.add_parser("portais", help="mostra o registro de portais (portais.yaml)")
    pl.set_defaults(func=cmd_portais)

    ch = sub.add_parser("colher", help="coleta metadados de outro portal p/ tabela registros")
    ch.add_argument("--portal", required=True,
                    choices=["arca", "scielo", "scielo-livros", "ipea",
                             "wikisource", "oasisbr", "hemeroteca", "oai"])
    ch.add_argument("--limit", type=int, default=100)
    ch.add_argument("--nome", default=None, help="nome do portal (modo oai)")
    ch.add_argument("--oai-url", default=None, help="endpoint OAI (modo oai)")
    ch.add_argument("--busca", default=None, help="termo de busca (oasisbr)")
    ch.add_argument("--bibs", default=None,
                    help="lista de bibs p/ hemeroteca, ex: --bibs 348970_03,764051")
    ch.set_defaults(func=cmd_colher)
    return p


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
