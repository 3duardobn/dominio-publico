import xml.etree.ElementTree as ET
from crawler.oai import parse_record, NS
from crawler.dspace_rest import flatten_item
from crawler.scielo_meta import flatten_article
from tests.fixtures_portais import OAI_SAMPLE, DSPACE_ITEM_SAMPLE


def test_oai_parse():
    root = ET.fromstring(OAI_SAMPLE)
    recs = root.findall(".//oai:record", NS)
    assert len(recs) == 2
    r1 = parse_record(recs[0].find("oai:header", NS), recs[0].find("oai:metadata", NS))
    assert r1["identifier"] == "oai:teste:1"
    assert r1["title"] == "Obra de Teste"
    assert r1["creator"] == "Autor Teste"


def test_dspace_flatten():
    reg = flatten_item(DSPACE_ITEM_SAMPLE, "arca", "https://arca.fiocruz.br")
    assert reg["title"] == "Tese de Teste"
    assert reg["creator"] == "Maria Silva"
    assert reg["handle"] == "https://arca.fiocruz.br/handle/icict/999"
    assert reg["portal"] == "arca"


def test_scielo_flatten():
    a = {"code": "S0100-001", "title": "Artigo X",
         "authors": [{"given_names": "Ana", "surname": "Souza"}],
         "publication_date": "2024-01-01", "subject_areas": ["Saúde"]}
    reg = flatten_article(a, "scl")
    assert reg["identifier"] == "S0100-001"
    assert "Souza" in reg["creator"]


def test_registros_store(tmp_path):
    from crawler.store import Store
    s = Store(tmp_path / "t.db")
    s.upsert_registro({"portal": "arca", "identifier": "h1", "title": "T",
                       "creator": "C", "url": "u"})
    s.commit()
    assert s.count_registros("arca") == 1
