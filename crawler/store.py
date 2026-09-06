"""Persistência: SQLite (principal) + export JSON/CSV."""
from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS obras (
    co_obra TEXT PRIMARY KEY,
    titulo TEXT,
    autor TEXT,
    fonte TEXT,
    formato TEXT,
    tamanho_txt TEXT,
    tamanho_bytes INTEGER,
    detalhe_url TEXT,
    co_midia INTEGER,
    midia_nome TEXT,
    categoria TEXT,
    idioma TEXT,
    instituicao_parceiro TEXT,
    instituicao_programa TEXT,
    area_conhecimento TEXT,
    nivel TEXT,
    ano_tese TEXT,
    acessos TEXT,
    resumo TEXT,
    download_url TEXT,
    origem_lista_url TEXT,
    atualizado_em TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS paginas (
    co_midia INTEGER,
    pagina INTEGER,
    skip INTEGER,
    total_reportado INTEGER,
    n_obras INTEGER,
    url TEXT,
    PRIMARY KEY (co_midia, pagina)
);
CREATE TABLE IF NOT EXISTS registros (
    portal TEXT,
    identifier TEXT,
    title TEXT,
    creator TEXT,
    date TEXT,
    type TEXT,
    rights TEXT,
    subject TEXT,
    description TEXT,
    url TEXT,
    handle TEXT,
    raw_json TEXT,
    PRIMARY KEY (portal, identifier)
);
"""

OBRA_COLS = [
    "co_obra", "titulo", "autor", "fonte", "formato", "tamanho_txt",
    "tamanho_bytes", "detalhe_url", "co_midia", "midia_nome", "categoria",
    "idioma", "instituicao_parceiro", "instituicao_programa",
    "area_conhecimento", "nivel", "ano_tese", "acessos", "resumo",
    "download_url", "origem_lista_url",
]


class Store:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.executescript(SCHEMA)
        self.conn.execute("PRAGMA journal_mode=WAL")

    def upsert_obra(self, obra: dict) -> None:
        row = {c: obra.get(c) for c in OBRA_COLS}
        cols = ",".join(OBRA_COLS)
        placeholders = ",".join("?" for _ in OBRA_COLS)
        updates = ",".join(f"{c}=excluded.{c}" for c in OBRA_COLS if c != "co_obra")
        self.conn.execute(
            f"INSERT INTO obras ({cols}) VALUES ({placeholders}) "
            f"ON CONFLICT(co_obra) DO UPDATE SET {updates}",
            [row[c] for c in OBRA_COLS],
        )

    def merge_detalhe(self, co_obra: str, detalhe: dict) -> None:
        allowed = {"categoria", "idioma", "instituicao_parceiro",
                   "instituicao_programa", "area_conhecimento", "nivel",
                   "ano_tese", "acessos", "resumo", "download_url",
                   "titulo", "autor"}
        sets = {k: v for k, v in detalhe.items() if k in allowed and v}
        if not sets:
            return
        self.conn.execute(
            f"UPDATE obras SET {','.join(f'{k}=?' for k in sets)} WHERE co_obra=?",
            [*sets.values(), co_obra],
        )

    def mark_pagina(self, co_midia: int, pagina: int, skip: int,
                    total: int | None, n: int, url: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO paginas VALUES (?,?,?,?,?,?)",
            (co_midia, pagina, skip, total, n, url),
        )

    def pagina_feita(self, co_midia: int, pagina: int) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM paginas WHERE co_midia=? AND pagina=?", (co_midia, pagina))
        return cur.fetchone() is not None

    def commit(self) -> None:
        self.conn.commit()

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM obras").fetchone()[0]

    def export_json(self, path: Path) -> int:
        cur = self.conn.execute(f"SELECT {','.join(OBRA_COLS)} FROM obras ORDER BY co_obra")
        rows = [dict(zip(OBRA_COLS, r)) for r in cur.fetchall()]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        return len(rows)

    def export_csv(self, path: Path) -> int:
        cur = self.conn.execute(f"SELECT {','.join(OBRA_COLS)} FROM obras ORDER BY co_obra")
        path.parent.mkdir(parents=True, exist_ok=True)
        n = 0
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=OBRA_COLS)
            w.writeheader()
            for r in cur.fetchall():
                w.writerow(dict(zip(OBRA_COLS, r)))
                n += 1
        return n

    # ---- tabela unificada multi-portal ----
    def upsert_registro(self, reg: dict) -> None:
        import json as _json
        cols = ["portal", "identifier", "title", "creator", "date", "type",
                "rights", "subject", "description", "url", "handle", "raw_json"]
        vals = [reg.get(c, "") for c in cols[:-1]]
        vals.append(_json.dumps(reg.get("raw", {}), ensure_ascii=False)[:20000])
        placeholders = ",".join("?" for _ in cols)
        updates = ",".join(f"{c}=excluded.{c}" for c in cols if c not in ("portal", "identifier"))
        self.conn.execute(
            f"INSERT INTO registros ({','.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT(portal, identifier) DO UPDATE SET {updates}", vals)

    def count_registros(self, portal: str | None = None) -> int:
        if portal:
            return self.conn.execute(
                "SELECT COUNT(*) FROM registros WHERE portal=?", (portal,)).fetchone()[0]
        return self.conn.execute("SELECT COUNT(*) FROM registros").fetchone()[0]
