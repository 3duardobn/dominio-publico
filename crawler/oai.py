"""Colheita OAI-PMH genérica (repositórios DSpace legados, agregadores, RCAAP...).

Funciona com qualquer endpoint que responda ?verb=Identify.
Uso típico: BDSF Senado (se o WAF liberar), BBM (se reativarem), LA Referencia.
"""
from __future__ import annotations

import logging
import time
import random
from typing import Iterator
from urllib.parse import urlencode

import requests
import xml.etree.ElementTree as ET

log = logging.getLogger(__name__)

NS = {"oai": "http://www.openarchives.org/OAI/2.0/",
      "dc": "http://purl.org/dc/elements/1.1/"}


def _text(el: ET.Element | None) -> str:
    return (el.text or "").strip() if el is not None and el.text else ""


def _oai_get(base_url: str, params: dict, timeout: int) -> bytes:
    """GET com fallback verify=False se o cert do servidor estiver vencido.

    Alguns repositórios públicos (ex: oai.books.scielo.org, cert vencido em
    out/2025) não renovam o certificado. Como só colhemos metadados públicos,
    o fallback é aceitável — mas sempre logado como warning.
    """
    headers = {"User-Agent": "dominio-publico-metadata-crawler/0.1"}
    try:
        r = requests.get(base_url, params=params, headers=headers, timeout=timeout)
    except requests.exceptions.SSLError as e:
        log.warning("cert SSL inválido em %s (%s); tentando sem verificação",
                    base_url, str(e)[:120])
        r = requests.get(base_url, params=params, headers=headers,
                         timeout=timeout, verify=False)
    r.raise_for_status()
    return r.content


def identify(base_url: str, timeout: int = 30) -> dict:
    """Testa se o endpoint OAI existe. Levanta RuntimeError se não."""
    content = _oai_get(base_url, {"verb": "Identify"}, timeout)
    root = ET.fromstring(content)
    repo = root.find("oai:Identify", NS)
    if repo is None:
        raise RuntimeError(f"{base_url} não retornou Identify OAI-PMH válido")
    return {
        "repositoryName": _text(repo.find("oai:repositoryName", NS)),
        "baseURL": _text(repo.find("oai:baseURL", NS)),
        "earliestDatestamp": _text(repo.find("oai:earliestDatestamp", NS)),
    }


def parse_record(header_el: ET.Element, meta_el: ET.Element | None) -> dict:
    rec: dict = {
        "identifier": _text(header_el.find("oai:identifier", NS)),
        "datestamp": _text(header_el.find("oai:datestamp", NS)),
        "deleted": header_el.get("status") == "deleted",
    }
    if meta_el is not None:
        dc = meta_el.find(".//{http://www.openarchives.org/OAI/2.0/oai_dc/}dc")
        if dc is None:  # tenta qualquer container dublin core
            dc = meta_el
        for child in dc:
            tag = child.tag.split("}")[-1]  # title, creator, ...
            val = (child.text or "").strip()
            if not val:
                continue
            if tag in rec and isinstance(rec.get(tag), list):
                rec[tag].append(val)
            elif tag in rec:
                rec[tag] = [rec[tag], val]
            else:
                rec[tag] = val
    return rec


def list_records(base_url: str, metadata_prefix: str = "oai_dc",
                 set_spec: str | None = None,
                 delay: float = 2.0, max_records: int | None = None,
                 timeout: int = 30) -> Iterator[dict]:
    """Gerador com resumptionToken + rate limit educado."""
    params: dict = {"verb": "ListRecords", "metadataPrefix": metadata_prefix}
    if set_spec:
        params["set"] = set_spec
    n = 0
    while True:
        time.sleep(delay + random.uniform(0, 1))
        content = _oai_get(base_url, params, timeout)
        root = ET.fromstring(content)
        err = root.find("oai:error", NS)
        if err is not None:
            raise RuntimeError(f"OAI error {err.get('code')}: {err.text}")
        for rec_el in root.findall(".//oai:record", NS):
            header = rec_el.find("oai:header", NS)
            meta = rec_el.find("oai:metadata", NS)
            yield parse_record(header, meta if meta is not None else None)
            n += 1
            if max_records is not None and n >= max_records:
                return
        token_el = root.find(".//oai:resumptionToken", NS)
        token = (token_el.text or "").strip() if token_el is not None else ""
        if not token:
            return
        params = {"verb": "ListRecords", "resumptionToken": token}
