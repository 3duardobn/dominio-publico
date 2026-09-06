import xml.etree.ElementTree as ET
from crawler.wikisource import flatten_page
from crawler.oasisbr import parse_rss
from tests.fixtures_novos import MW_PAGES_SAMPLE, RSS_SAMPLE, DOCREADER_SAMPLE


def test_wikisource_flatten():
    page = MW_PAGES_SAMPLE["query"]["pages"]["42"]
    reg = flatten_page(page)
    assert reg["portal"] == "wikisource"
    assert reg["identifier"] == "42"
    assert reg["title"] == "Os Lusíadas"
    assert reg["creator"] == "Editor"
    assert reg["url"].startswith("https://pt.wikisource.org/wiki/")


def test_oasisbr_rss():
    items, total = parse_rss(ET.fromstring(RSS_SAMPLE))
    assert len(items) == 2
    assert items[0]["title"] == "Tese de Teste"
    assert items[0]["creator"] == "Autora, Maria"
    assert "493655" in total


def test_hemeroteca_parse(monkeypatch):
    from crawler import hemeroteca as H
    monkeypatch.setattr(H, "_get", lambda url, **kw: DOCREADER_SAMPLE)
    reg = H.ler_exemplar("348970_03", "57116")
    assert reg["portal"] == "hemeroteca"
    assert "Jornal" in reg["title"]
    assert reg["date"] == "1889"
    assert any(u.endswith(".pdf") for u in reg["raw"]["pdfs"])
