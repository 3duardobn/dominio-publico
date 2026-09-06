"""Parsing das páginas JSP (iso-8859-1) do Domínio Público.

Estrutura descoberta via código do PocketLibraryAPI + scraping-dominio-publico:
- Lista: table#res > thead th (Título, Autor, Fonte, Formato, Tamanho, Download)
         + tbody tr > td (col 2 tem <a href> p/ detalhe com co_obra=ID)
         + .detalhe_total com "X a Y de Z itens"
- Detalhe: DetalheObraForm.do?select_action=&co_obra=ID
         + linhas .detalhe1 (chave) / .detalhe2 (valor)
         + resumo em span.detalhe2 separado
         + URL de download escondida em comentário HTML na última <tr>
"""
from __future__ import annotations

import re
from html import unescape
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup, Comment

from .config import BASE_URL

CO_OBRA_RE = re.compile(r"co_obra=(\d+)")
TOTAL_RE = re.compile(r"de\s*([\d\.]+)", re.IGNORECASE)

# Mapeamento JSP (label .detalhe1) -> chave canônica (igual ao PocketLibraryAPI)
KEY_MAP = {
    "titulo": "titulo",
    "título": "titulo",
    "autor": "autor",
    "categoria": "categoria",
    "idioma": "idioma",
    "instituicao_parceiro": "instituicao_parceiro",
    "instituicao_programa": "instituicao_programa",
    "instituição": "instituicao_parceiro",
    "area_conhecimento": "area_conhecimento",
    "nivel": "nivel",
    "ano_da_tese": "ano_tese",
    "acessos": "acessos",
    "resumo": "resumo",
}


def clear(text: str | None) -> str:
    """Normaliza texto raspado (trim + collapse whitespace + unescape)."""
    if not text:
        return ""
    text = unescape(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def normalize_key(label: str) -> str:
    slug = clear(label).lower()
    slug = (
        slug.replace("ã", "a").replace("á", "a").replace("à", "a")
        .replace("é", "e").replace("ê", "e").replace("í", "i")
        .replace("ó", "o").replace("õ", "o").replace("ç", "c")
        .replace(" ", "_").replace("/", "_")
    )
    slug = re.sub(r"[^a-z0-9_]", "", slug)
    return KEY_MAP.get(slug, slug)


def convert_to_bytes(size_str: str) -> int | None:
    """'407,36 KB' / '1.2 MB' -> bytes. Retorna None se desconhecido."""
    if not size_str:
        return None
    s = size_str.strip().upper().replace(",", ".")
    m = re.match(r"([\d\.]+)\s*([KMGT]?B)?", s)
    if not m:
        return None
    try:
        value = float(m.group(1))
    except ValueError:
        return None
    unit = (m.group(2) or "B").upper()
    mult = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
    return int(value * mult.get(unit, 1))


def co_obra_from_url(href: str | None) -> str | None:
    if not href:
        return None
    m = CO_OBRA_RE.search(href)
    return m.group(1) if m else None


def parse_result_page(html: str, page_url: str = "") -> dict[str, Any]:
    """Extrai obras + total de uma página de ResultadoPesquisaObraForm."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one("table#res")
    obras: list[dict[str, Any]] = []
    if table is None:
        return {"obras": [], "total": None, "total_raw": clear(
            soup.select_one(".detalhe_total").get_text() if soup.select_one(".detalhe_total") else "")}

    # Mapeia cabeçalhos -> índice de coluna (robusto a reordenação)
    header_map: dict[str, int] = {}
    for i, th in enumerate(table.select("thead th")):
        h = clear(th.get_text()).lower()
        if "tít" in h or "tit" in h:
            header_map["titulo"] = i
        elif "autor" in h:
            header_map["autor"] = i
        elif "fonte" in h or "institui" in h:
            header_map["fonte"] = i
        elif "formato" in h or "tipo" in h:
            header_map["formato"] = i
        elif "tamanho" in h:
            header_map["tamanho"] = i

    for tr in table.select("tbody tr"):
        tds = tr.find_all("td")
        if not tds:
            continue

        def cell(name: str) -> str:
            idx = header_map.get(name)
            if idx is None or idx >= len(tds):
                return ""
            return clear(tds[idx].get_text())

        # Título + link de detalhe (coluna 2 no layout original)
        title_idx = header_map.get("titulo", 1)
        title_td = tds[title_idx] if title_idx < len(tds) else None
        titulo = clear(title_td.get_text()) if title_td else ""
        if not titulo:
            continue
        link_el = title_td.find("a", href=True) if title_td else None
        href = link_el["href"] if link_el else ""
        # href vem relativo tipo "../../pesquisa/DetalheObraForm.do?..."
        detalhe_url = urljoin(BASE_URL + "/pesquisa/", href.lstrip("./")) if href else ""
        co_obra = co_obra_from_url(href)

        tamanho = cell("tamanho")
        obras.append({
            "co_obra": co_obra,
            "titulo": titulo,
            "autor": cell("autor"),
            "fonte": cell("fonte"),
            "formato": cell("formato"),
            "tamanho_txt": tamanho,
            "tamanho_bytes": convert_to_bytes(tamanho),
            "detalhe_url": detalhe_url,
            "origem_lista_url": page_url,
        })

    total_raw = ""
    total = None
    el = soup.select_one(".detalhe_total")
    if el:
        total_raw = clear(el.get_text())
        m = TOTAL_RE.search(total_raw)
        if m:
            try:
                total = int(m.group(1).replace(".", ""))
            except ValueError:
                total = None
    return {"obras": obras, "total": total, "total_raw": total_raw}


def parse_detail_page(html: str, co_obra: str | None = None) -> dict[str, Any]:
    """Extrai metadados ricos da página DetalheObraForm.do."""
    soup = BeautifulSoup(html, "lxml")
    data: dict[str, Any] = {"co_obra": co_obra}

    # Tabela de info: a original usa tables aninhadas; busca genérica por .detalhe1/.detalhe2
    for tr in soup.select("tr"):
        k_el = tr.select_one(".detalhe1")
        v_el = tr.select_one(".detalhe2")
        if k_el and v_el and tr.find_parent("table"):
            key = normalize_key(k_el.get_text())
            val = clear(v_el.get_text())
            if key and val and key not in data:
                data[key] = val

    # Resumo pode estar em span.detalhe2 separado
    spans = [clear(s.get_text()) for s in soup.select("span.detalhe2")]
    long_spans = [s for s in spans if len(s) > 120]
    if long_spans and "resumo" not in data:
        data["resumo"] = max(long_spans, key=len)

    # Download escondido em comentário HTML: <!-- <a href="/texto/xx.pdf"> -->
    download_url = ""
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        frag = BeautifulSoup(str(comment), "lxml")
        a = frag.find("a", href=True)
        if a:
            href = a["href"]
            if href.startswith("/download"):
                download_url = urljoin(BASE_URL, href)
            elif href.startswith("/"):
                download_url = urljoin(BASE_URL + "/download", href)
            else:
                download_url = urljoin(BASE_URL + "/download/", href)
            break
    # Fallback: link direto visível para /download/
    if not download_url:
        a = soup.select_one("a[href*='/download/']")
        if a:
            download_url = urljoin(BASE_URL, a["href"])
    if download_url:
        data["download_url"] = download_url

    return data
