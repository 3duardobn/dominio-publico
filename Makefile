.PHONY: setup test quick fast portals help

help:
	@echo "make setup   - cria .venv e instala dependências"
	@echo "make test    - roda a suíte de testes"
	@echo "make quick   - amostra rápida (valida acesso)"
	@echo "make fast    - portais rápidos (~2,5h)"
	@echo "make portals - lista portais mapeados"

setup:
	./setup.sh

test:
	.venv/bin/python -m pytest tests/ -q

quick:
	.venv/bin/python cli.py amostra --midia 2 --max-pages 1 || true
	.venv/bin/python cli.py --out-dir data colher --portal wikisource --limit 5
	.venv/bin/python cli.py --out-dir data colher --portal ipea --limit 3

fast:
	./run_24h.sh --fast-only

portals:
	.venv/bin/python cli.py portais
