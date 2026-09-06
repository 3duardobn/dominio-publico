"""Coletor Hemeroteca Digital BN (DocReader ASP.NET, sem API/OAI/IIIF).

Estratégia:
1. Descoberta: /hdb/periodico.aspx (via iframe DefaultNew.aspx) contém links
   DocReader.aspx?bib=<ID> — um por título de periódico.
2. Metadados: cada página DocReader.aspx?bib=<ID>&PagFis=<n> traz no HTML
   ano/edição e links "Edições em PDF".

Uso: primeiro `listar_bibs()` para mapear títulos, depois `ler_exemplar(bib)`
para uma amostra de metadados. Colheita exaustiva (10M páginas) é inviável
via HTTP — o foco aqui é o catálogo de títulos + amostras.
"""
from __future__ import annotations

import logging
import re
import time
import random
from typing import Iterator
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)
BASE = "https://memoria.bn.gov.br"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}

BIB_RE = re.compile(r"DocReader\.aspx\?bib=([\w]+)", re.IGNORECASE)


def _get(url: str, timeout: int = 30, retries: int = 4) -> str:
    last = None
    for i in range(1, retries + 1):
        try:
            time.sleep(1.5 + random.uniform(0, 1))
            r = requests.get(url, headers=UA, timeout=timeout, verify=False)
            r.raise_for_status()
            # ASP.NET WebForms responde em latin1/utf-8 conforme página
            for enc in ("utf-8", "iso-8859-1"):
                try:
                    return r.content.decode(enc)
                except UnicodeDecodeError:
                    continue
            return r.text
        except Exception as e:
            last = e
            log.warning("hemeroteca GET tentativa %d: %s", i, e)
            time.sleep(min(60, 2 ** i))
    raise RuntimeError(f"Hemeroteca GET falhou {url}: {last}")


def listar_bibs() -> list[dict]:
    """Extrai (bib, titulo) da página de periódicos."""
    bibs: dict[str, str] = {}
    for path in ("/hdb/periodico.aspx", "/hdb/DefaultNew.aspx"):
        try:
            html = _get(urljoin(BASE, path))
        except RuntimeError as e:
            log.warning("%s: %s", path, e)
            continue
        soup = BeautifulSoup(html, "lxml")
        for a in soup.find_all("a", href=True):
            m = BIB_RE.search(a["href"])
            if m:
                titulo = a.get_text(" ", strip=True)
                if m.group(1) not in bibs and titulo:
                    bibs[m.group(1)] = titulo
        # iframes podem conter a lista real
        for fr in soup.find_all("iframe", src=True):
            try:
                sub = _get(urljoin(BASE, fr["src"]))
                for m in BIB_RE.finditer(sub):
                    if m.group(1) not in bibs:
                        bibs[m.group(1)] = ""
            except RuntimeError:
                continue
    return [{"bib": b, "titulo": t} for b, t in sorted(bibs.items())]


def ler_exemplar(bib: str, pagfis: str = "") -> dict:
    """Lê metadados de uma página DocReader (título, anos, edições)."""
    url = f"{BASE}/DocReader/DocReader.aspx?bib={bib}"
    if pagfis:
        url += f"&PagFis={pagfis}"
    html = _get(url)
    soup = BeautifulSoup(html, "lxml")
    titulo = (soup.title.get_text(strip=True) if soup.title else "")[:500]
    texto = soup.get_text(" ", strip=True)
    anos = sorted(set(re.findall(r"Ano\s+(\d{4})", texto)))
    if not anos:  # fallback: primeiro ano avulso plausível (1500–2029)
        m = re.search(r"\b(1[5-9]\d{2}|20[0-2]\d)\b", texto)
        anos = [m.group(1)] if m else []
    edicoes = sorted(set(re.findall(r"Edi[cç][aã]o\s+(\d+)", texto)))
    pdfs = sorted({urljoin(BASE, a["href"]) for a in soup.find_all("a", href=True)
                   if a["href"].lower().endswith(".pdf")})
    return {
        "portal": "hemeroteca",
        "identifier": f"bib={bib}" + (f"&pagfis={pagfis}" if pagfis else ""),
        "title": titulo,
        "creator": "",
        "date": (anos[0] if len(anos) == 1 else f"{anos[0]}-{anos[-1]}") if anos else "",
        "type": "newspaper",
        "rights": "public domain (BN)",
        "subject": "",
        "description": f"anos={','.join(anos[:30])} edicoes_amostra={','.join(edicoes[:30])}"[:2000],
        "url": url,
        "handle": bib,
        "raw": {"pdfs": pdfs[:20], "n_edicoes": len(edicoes)},
    }
