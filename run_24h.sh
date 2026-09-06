#!/usr/bin/env bash
# Orquestrador 24h: colhe todos os portais em sequência, com resume automático.
# Pode ser interrompido (Ctrl+C) e retomado — nada é refeito.
# Uso:
#   ./run_24h.sh                    # tudo, logs em logs/
#   nohup ./run_24h.sh > logs/nohup.out 2>&1 &   # 24h em background
#   ./run_24h.sh --fast-only         # só os rápidos (~2,5h, ~620k registros)
set -uo pipefail
cd "$(dirname "$0")"
# shellcheck disable=SC1091
source .venv/bin/activate

OUT=data
LOGDIR=logs
FAST_ONLY="${1:-}"
mkdir -p "$OUT" "$LOGDIR"
LOG="$LOGDIR/run_$(date +%Y%m%d_%H%M%S).log"

# run nunca aborta o 24h: registra falha e segue (resume cobre o resto)
run() {
  echo "### $*" | tee -a "$LOG"
  if "$@" 2>&1 | tee -a "$LOG"; then
    echo "[ok] $1" | tee -a "$LOG"
  else
    echo "[FALHOU, seguindo] $*" | tee -a "$LOG"
  fi
}

echo "=== início $(date) ===" | tee "$LOG"

# 1. Rápidos (~2,5h): IPEA, SciELO Livros, Wikisource, SciELO artigos
run python3 cli.py --out-dir "$OUT" colher --portal ipea --limit 100000
run python3 cli.py --out-dir "$OUT" colher --portal scielo-livros --limit 100000
run python3 cli.py --out-dir "$OUT" colher --portal wikisource --limit 200000
run python3 cli.py --out-dir "$OUT" colher --portal scielo --limit 1000000

if [ "$FAST_ONLY" = "--fast-only" ]; then
  echo "=== fast-only concluído $(date) ===" | tee -a "$LOG"
  exit 0
fi

# 2. Médios: Arca (~30h), BDSF/OAI (~4h, pode falhar atrás do WAF)
run python3 cli.py --out-dir "$OUT" colher --portal arca --limit 100000
run python3 cli.py --out-dir "$OUT" colher --portal oai --nome bdsf \
  --oai-url https://www2.senado.leg.br/bdsf/oai/request --limit 1000000

# 3. Domínio Público: lista (~3h) + detalhes (~6 dias). Detalhes por mídia.
run python3 cli.py --delay 2 --jitter 1 --out-dir "$OUT" censo
run python3 cli.py --delay 2 --jitter 1 --out-dir "$OUT" detalhes --midia 2 --limit 1000000

# 4. Export final
run python3 cli.py --db "$OUT/dominio-publico.db" --out-dir "$OUT" exportar

echo "=== fim $(date) ===" | tee -a "$LOG"
