"""Config central do indexador do Portal Domínio Público."""

BASE_URL = "http://www.dominiopublico.gov.br"
BASE_URL_HTTPS = "https://www.dominiopublico.gov.br"

# Endpoint de listagem (GET). Mesmos params usados pelo form JSP + PocketLibraryAPI.
RESULT_URL = f"{BASE_URL}/pesquisa/ResultadoPesquisaObraForm.do"
DETAIL_URL = f"{BASE_URL}/pesquisa/DetalheObraForm.do"

# co_midia conforme tabela do PocketLibraryAPI / form JSP
MEDIAS = {
    2: "texto",
    3: "som",
    5: "imagem",
    6: "video",
}

# Boas práticas de crawling educado (default; sobrescrevível via CLI)
DEFAULT_PAGE_SIZE = 50      # o site usa first=50 por página
DEFAULT_DELAY = 2.0         # segundos entre requests
DEFAULT_JITTER = 1.0        # jitter aleatório somado ao delay (0..jitter)
DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 5
DEFAULT_USER_AGENT = (
    "dominio-publico-metadata-crawler/0.1 "
    "(pesquisa academica; contato: informe seu e-mail) "
    "Python-requests"
)

# Ordenações aceitas pelo JSP (colunaOrdenar)
ORDER_COLUMNS = [
    "DS_TITULO", "NO_AUTOR", "DS_FORMATO",
    "NU_TAMANHO", "NU_PAGE_HITS", "DS_INSTITUICAO",
]
