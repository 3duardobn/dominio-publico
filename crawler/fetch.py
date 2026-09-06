"""Fetch educado: requests primeiro, Playwright como fallback p/ Cloudflare."""
from __future__ import annotations

import time
import random
import logging
from dataclasses import dataclass

import requests

log = logging.getLogger(__name__)

CLOUDFLARE_MARKERS = ("Just a moment", "cf-chl", "challenges.cloudflare.com")


def is_cloudflare_block(html: str, status: int) -> bool:
    return status == 403 and any(m in html for m in CLOUDFLARE_MARKERS)


@dataclass
class Fetcher:
    user_agent: str
    timeout: int = 30
    delay: float = 2.0
    jitter: float = 1.0
    retries: int = 5
    use_playwright: bool = False

    def __post_init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5",
            "Connection": "keep-alive",
        })
        self._pw = None

    def polite_sleep(self) -> None:
        time.sleep(self.delay + random.uniform(0, self.jitter))

    def get(self, url: str, params: dict | None = None) -> str:
        """Retorna HTML decodificado (iso-8859-1 -> str). Respeita retry + backoff."""
        last_err: Exception | None = None
        for attempt in range(1, self.retries + 1):
            self.polite_sleep()
            try:
                r = self.session.get(url, params=params, timeout=self.timeout)
                # Decodifica: site é iso-8859-1, requests às vezes erra o charset
                if "iso-8859" in (r.headers.get("Content-Type", "").lower()) or r.encoding in (None, "ISO-8859-1"):
                    text = r.content.decode("iso-8859-1", errors="replace")
                else:
                    text = r.content.decode(r.encoding or "utf-8", errors="replace")
                if is_cloudflare_block(text, r.status_code):
                    if self.use_playwright:
                        log.warning("Cloudflare 403, tentando Playwright: %s", r.url)
                        return self.get_via_playwright(str(r.url))
                    raise RuntimeError(
                        "Bloqueio Cloudflare (403 'Just a moment'). "
                        "Rode da sua rede residencial com --playwright, "
                        "ou aguarde e tente mais tarde."
                    )
                r.raise_for_status()
                return text
            except RuntimeError:
                raise
            except Exception as e:  # retry com backoff exponencial
                last_err = e
                wait = min(60, (2 ** attempt) + random.uniform(0, 1))
                log.warning("tentativa %d/%d falhou (%s). retry em %.1fs",
                            attempt, self.retries, e, wait)
                time.sleep(wait)
        raise RuntimeError(f"Falha após {self.retries} tentativas: {last_err}")

    def get_via_playwright(self, url: str) -> str:
        from playwright.sync_api import sync_playwright  # import tardio
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=self.user_agent)
            try:
                page.goto(url, timeout=self.timeout * 1000, wait_until="domcontentloaded")
                page.wait_for_timeout(12000)  # dá tempo do challenge JS resolver
                html = page.content()
                if is_cloudflare_block(html, 403):
                    raise RuntimeError("Cloudflare ainda bloqueando mesmo via Playwright.")
                return html
            finally:
                browser.close()
