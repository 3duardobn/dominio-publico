# Indexador de metadados — acervos públicos brasileiros

Copia local de **metadados** para análise: SQLite + JSON + CSV.
Começou pelo Portal Domínio Público e agora cobre vários portais (`portais.yaml`).

## Quickstart (após o git clone)

```bash
./setup.sh                  # cria .venv e instala tudo (1x)
source .venv/bin/activate
python -m pytest tests/ -q  # valida (10 testes)

# Amostra rápida (2 min) — valida acesso da sua rede
python cli.py amostra --midia 2 --max-pages 1
python cli.py --out-dir data colher --portal wikisource --limit 5

# Rodar 24h (tudo, com resume — pode interromper e retomar)
nohup ./run_24h.sh > logs/nohup.out 2>&1 &
# ou só os rápidos (~2,5h, ~620k registros):
./run_24h.sh --fast-only

# Atalhos: make test | make quick | make fast | make portals
```

Saída em `data/`: `dominio-publico.db` (tabelas `obras`, `registros`, `paginas`),
`obras.json`, `obras.csv`. Logs em `logs/`.

## Portais mapeados (verificado em 2026-09-06)

| Portal | Plataforma | Como colher | Tamanho aprox. |
|---|---|---|---|
| Domínio Público (MEC) | JSP `iso-8859-1` | `censo` (HTML `table#res`) | ~198k |
| Arca Fiocruz | DSpace 9.3 | `colher --portal arca` (REST ✅) | ~70k |
| SciELO Brasil | própria | `colher --portal scielo` (ArticleMeta ✅, 563k artigos) | ~400k+ docs |
| BDSF Senado | DSpace legado | `colher --portal oai --oai-url .../bdsf/oai/request` (WAF bloqueia robôs; tentar em rede residencial) | ~480k |
| Biblioteca Digital Câmara | DSpace Angular | sem REST/OAI público; crawl HTML futuro | ~6k |
| BBM USP | DSpace 6.3 | sem OAI; crawl `simple-search` futuro | ~4,6k |
| BNDigital | WordPress+SopiA | busca Sophia + `objdigital.bn.br` (403 p/ bots) | ~3M |
| BDTD IBICT | VuFind (agregador) | busca VuFind; texto fica na origem | ~1M |

```bash
# ver registro de portais
python cli.py portais

# Arca (REST, funciona de qualquer rede)
python cli.py --out-dir data colher --portal arca --limit 100

# SciELO (ArticleMeta, idem)
python cli.py --out-dir data colher --portal scielo --limit 100

# OAI-PMH genérico (ex: BDSF, quando a rede permitir)
python cli.py --out-dir data colher --portal oai --nome bdsf \
  --oai-url https://www2.senado.leg.br/bdsf/oai/request --limit 100

# SciELO Livros (OAI dedicado) e IPEA (OAI DSpace) — funcionam de qualquer rede
python cli.py --out-dir data colher --portal scielo-livros --limit 100
python cli.py --out-dir data colher --portal ipea --limit 100

# Wikisource PT (MediaWiki API aberta)
python cli.py --out-dir data colher --portal wikisource --limit 200

# OasisBR (RSS do VuFind; instável — tente em outro horário/rede se falhar)
python cli.py --out-dir data colher --portal oasisbr --busca "machado de assis" --limit 100

# Hemeroteca BN (bibs explícitos; descoberta do catálogo exige navegador)
python cli.py --out-dir data colher --portal hemeroteca --bibs 348970_03,764051
```

Metadados multi-portal vão para a tabela `registros`
(portal, identifier, title, creator, date, type, rights, subject, description, url).

## Outros acervos BR em domínio público / acesso aberto que valem indexar

1. `memoria.bn.gov.br/hdb/` — Hemeroteca Digital BN ✅ coletor (`hemeroteca`: ~10M páginas; metadados por bib, ex: `A Noite 1930–1939` com anos/edições)
2. `oasisbr.ibict.br` — OasisBR ✅ coletor (`oasisbr` via RSS VuFind, ~494k; instável por IP)
3. `books.scielo.org` — SciELO Livros ✅ coletor (`scielo-livros` via OAI dedicado, ~21k capítulos)
4. `bdtd.ibict.br` — BDTD nacional (teses/dissertações)
5. `repositorio.ipea.gov.br` — IPEA ✅ coletor (`ipea` via OAI DSpace 9.2, ~19k itens)
6. `pt.wikisource.org` — Wikisource PT ✅ coletor (`wikisource` via MediaWiki API, ~39k artigos)

---

## Módulo original: Portal Domínio Público

Copia local de **todos os metadados** do acervo (`dominiopublico.gov.br`) para análise:
SQLite (`data/dominio-publico.db`) + `obras.json` + `obras.csv`.

Não existe API oficial. O site é um JSP antigo (`iso-8859-1`) com listagem em
`ResultadoPesquisaObraForm.do` e detalhe em `DetalheObraForm.do?co_obra=ID`.
Este projeto raspa só HTML (metadados), com rate limit educado.

## O que cada fase coleta

| Fase | Endpoint | Volume aprox. | Tempo* | Campos |
|---|---|---|---|---|
| `censo` (lista) | `ResultadoPesquisaObraForm.do?first=50&skip=N&co_midia=M` | ~4.000 págs / ~198k obras | ~3h | co_obra, titulo, autor, fonte, formato, tamanho, detalhe_url, midia |
| `detalhes` | `DetalheObraForm.do?co_obra=ID` | 198k págs | ~130h | + categoria, idioma, instituicao, area, nivel, ano, acessos, resumo, download_url |

\* com `--delay 2 --jitter 1` (1 request por vez, sem paralelismo — de propósito).

## Uso

```bash
pip install -r requirements.txt

# 1. Teste rápido (2 páginas de texto) — valida acesso + parsing
python cli.py amostra --midia 2 --max-pages 2

# 2. Censo completo da fase lista (resume automático via tabela `paginas`)
python cli.py --delay 2 --jitter 1 censo --out-dir data

# 3. Só uma mídia (2=texto, 3=som, 5=imagem, 6=video)
python cli.py censo --out-dir data --midia 2

# 4. Detalhes (caro! use --limit para amostras)
python cli.py detalhes --out-dir data --midia 2 --limit 50

# 5. Reexportar json/csv do sqlite existente
python cli.py --db data/dominio-publico.db --out-dir data exportar
```

## Cloudflare (importante)

Desde 2024 o domínio usa Cloudflare challenge: datacenters e `curl` recebem
`403 Just a moment`. Observado aqui em 2026-09-06 para `requests`, `curl_cffi`
e Playwright headless-shell.

- Rode **da sua rede residencial** — lá o challenge costuma liberar após o JS.
- Se `requests` der 403, rode com `--playwright` (abre Chromium real e espera
  o challenge resolver; requer `pip install playwright && playwright install chrome`).
- Nunca suba `--delay` para <1s nem paralelize: é site público do MEC, pequeno
  e sem CDN de verdade. 1 req / 2–3s é o respeitoso.

## Schema (`obras`)

`co_obra (PK), titulo, autor, fonte, formato, tamanho_txt, tamanho_bytes,
detalhe_url, co_midia, midia_nome, categoria, idioma, instituicao_parceiro,
instituicao_programa, area_conhecimento, nivel, ano_tese, acessos, resumo,
download_url, origem_lista_url`

Checkpoint de resume: tabela `paginas (co_midia, pagina)`.

## Referências de engenharia reversa

- `cookieukw/PocketLibraryAPI` — params da query, `table#res`, `.detalhe_total`,
  `.detalhe1/.detalhe2`, download em comentário HTML (base deste parser).
- `PublicaLivros/scraping-dominio-publico` — ordem das colunas, fallback de
  download `DetalheObraDownload.do` / `bibliotecacomum.com.br`.
