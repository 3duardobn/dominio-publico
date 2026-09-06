from pathlib import Path
from crawler.parse import parse_result_page, parse_detail_page, convert_to_bytes

FIX = Path(__file__).parent.parent / "fixtures"


def test_lista():
    html = (FIX / "lista.html").read_text(encoding="utf-8")
    parsed = parse_result_page(html, page_url="http://x")
    assert parsed["total"] == 182453, parsed
    assert len(parsed["obras"]) == 2
    o1 = parsed["obras"][0]
    assert o1["co_obra"] == "12345", o1
    assert o1["titulo"] == "Dom Casmurro"
    assert o1["autor"] == "Machado de Assis"
    assert o1["tamanho_bytes"] == convert_to_bytes("407,36 KB")
    o2 = parsed["obras"][1]
    assert o2["tamanho_bytes"] == int(1.2 * 1024 * 1024)


def test_detalhe():
    html = (FIX / "detalhe.html").read_text(encoding="utf-8")
    d = parse_detail_page(html, co_obra="12345")
    assert d["titulo"] == "Dom Casmurro", d
    assert d["categoria"] == "Literatura", d
    assert d["download_url"].endswith("/texto/machado.pdf"), d
    assert len(d.get("resumo", "")) > 100


def test_store_roundtrip(tmp_path):
    from crawler.store import Store
    s = Store(tmp_path / "t.db")
    s.upsert_obra({"co_obra": "1", "titulo": "T", "autor": "A", "co_midia": 2,
                   "midia_nome": "texto"})
    s.merge_detalhe("1", {"categoria": "Literatura"})
    s.commit()
    assert s.count() == 1
    assert s.export_json(tmp_path / "o.json") == 1
    assert s.export_csv(tmp_path / "o.csv") == 1
