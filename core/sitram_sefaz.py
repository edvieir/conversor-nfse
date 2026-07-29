"""
core/sitram_sefaz.py
Cliente REST para o SITRAM (Sistema de Trânsito de Mercadorias) da SEFAZ-CE.

Endpoints reverse-engineered do bundle Angular do portal:
  https://portal-sitram.sefaz.ce.gov.br/sitram-internet/

Autenticação via SSO Keycloak (mesmo realm do SIGA, client diferente)
usando certificado digital via mTLS broker.
"""

import base64
import hashlib
import os
import re
import time
from urllib.parse import urlencode, urlparse, parse_qs

import requests
from requests_pkcs12 import Pkcs12Adapter

# ── SSO Keycloak ─────────────────────────────────────────────────────────────

SSO_REALM = "https://sso.sefaz.ce.gov.br/auth/realms/sefaz-ad-realm"
SSO_AUTH_ENDPOINT = f"{SSO_REALM}/protocol/openid-connect/auth"
SSO_TOKEN_ENDPOINT = f"{SSO_REALM}/protocol/openid-connect/token"
SSO_CLIENT_ID = "sitram3-frontend"
SSO_REDIRECT_URI = "https://portal-sitram.sefaz.ce.gov.br/sitram-internet/"

CERT_IDP_ALIAS = "certificado-digital"
CERT_SSO_HOST = "https://cert-sso.sefaz.ce.gov.br"

# ── API base ─────────────────────────────────────────────────────────────────

SITRAM_BASE = "https://portal-sitram.sefaz.ce.gov.br"

API_AUTH         = f"{SITRAM_BASE}/api-auth"
API_NOTA         = f"{SITRAM_BASE}/api-nota"
API_ACAO         = f"{SITRAM_BASE}/api-acao"
API_PAGAMENTO    = f"{SITRAM_BASE}/api-pagamento"
API_CALCULADORA  = f"{SITRAM_BASE}/api-calculadora"
API_CADASTRO     = f"{SITRAM_BASE}/api-cadastro"
API_FRETE        = f"{SITRAM_BASE}/api-frete"
API_INTEGRACAO   = f"{SITRAM_BASE}/api-integracao"
API_CONHECIMENTO = f"{SITRAM_BASE}/api-conhecimento"
API_SIPAJ        = f"{SITRAM_BASE}/api-sipaj"
API_BAIXA        = f"{SITRAM_BASE}/api-baixa"


# ── Sessão e autenticação ────────────────────────────────────────────────────

def _sessao(pfx_bytes: bytes, pfx_senha: str) -> requests.Session:
    s = requests.Session()
    adapter = Pkcs12Adapter(
        pkcs12_data=pfx_bytes,
        pkcs12_password=pfx_senha.encode() if isinstance(pfx_senha, str) else pfx_senha,
    )
    s.mount("https://sso.sefaz.ce.gov.br", adapter)
    s.mount(CERT_SSO_HOST, adapter)
    s.mount(SITRAM_BASE, adapter)
    return s


def _pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(os.urandom(40)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


def login(sessao: requests.Session) -> dict:
    """
    Fluxo Authorization Code + PKCE via broker de certificado digital.
    Mesmo fluxo do SIGA, mas com client_id=sitram3-frontend.
    Retorna dict com access_token, refresh_token, expires_in, etc.
    """
    verifier, challenge = _pkce_pair()
    state = base64.urlsafe_b64encode(os.urandom(16)).rstrip(b"=").decode()
    nonce = base64.urlsafe_b64encode(os.urandom(16)).rstrip(b"=").decode()

    auth_params = {
        "client_id": SSO_CLIENT_ID,
        "redirect_uri": SSO_REDIRECT_URI,
        "state": state,
        "response_mode": "fragment",
        "response_type": "code",
        "scope": "openid",
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    r = sessao.get(
        f"{SSO_AUTH_ENDPOINT}?{urlencode(auth_params)}",
        timeout=30,
        allow_redirects=True,
    )
    r.raise_for_status()

    m = re.search(
        rf'href="([^"]*broker/{CERT_IDP_ALIAS}/login[^"]*)"', r.text,
    )
    if not m:
        raise RuntimeError(
            "Link do broker 'certificado-digital' não encontrado na página "
            f"de login do SITRAM. URL: {r.url}"
        )
    broker_url = m.group(1).replace("&amp;", "&")
    if broker_url.startswith("/"):
        broker_url = f"https://sso.sefaz.ce.gov.br{broker_url}"

    r2 = sessao.get(broker_url, timeout=30, allow_redirects=True)
    r2.raise_for_status()

    final_url = r2.url
    fragment = urlparse(final_url).fragment
    qs = parse_qs(fragment)
    code = qs.get("code", [None])[0]
    if not code:
        raise RuntimeError(
            "Não foi possível extrair o 'code' do SITRAM SSO. "
            f"URL final: {final_url}"
        )

    token_params = {
        "grant_type": "authorization_code",
        "client_id": SSO_CLIENT_ID,
        "redirect_uri": SSO_REDIRECT_URI,
        "code": code,
        "code_verifier": verifier,
    }
    rt = sessao.post(SSO_TOKEN_ENDPOINT, data=token_params, timeout=30)
    rt.raise_for_status()
    return rt.json()


def renovar_token(sessao: requests.Session, token: str) -> dict | None:
    """Tenta renovar o token via endpoint do SITRAM."""
    try:
        r = sessao.get(
            f"{API_AUTH}/renova-token",
            headers=_headers(token),
            timeout=30,
        )
        if r.ok:
            return r.json()
    except Exception:
        pass
    return None


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ── Contribuinte ─────────────────────────────────────────────────────────────

class SitramApiError(Exception):
    """Erro tratado da API SITRAM com mensagem amigável."""
    pass


def _check_sitram_response(r: requests.Response, operacao: str):
    """Verifica resposta HTTP do SITRAM e lança erro amigável."""
    if r.status_code == 200:
        return
    if r.status_code == 404:
        raise SitramApiError(
            f"{operacao}: registro não encontrado no SITRAM. "
            "Verifique se a nota possui trânsito registrado no Ceará."
        )
    if r.status_code == 401:
        raise SitramApiError(
            f"{operacao}: sessão expirada. Recarregue a página para reautenticar."
        )
    if r.status_code == 403:
        raise SitramApiError(
            f"{operacao}: acesso negado. O certificado pode não ter permissão para este recurso."
        )
    if r.status_code >= 500:
        raise SitramApiError(
            f"{operacao}: o servidor SITRAM retornou erro interno (HTTP {r.status_code}). "
            "O portal pode estar instável — tente novamente em alguns minutos."
        )
    r.raise_for_status()


def get_contribuinte(sessao: requests.Session, token: str) -> dict:
    """Retorna dados cadastrais do contribuinte logado."""
    r = sessao.get(f"{API_CADASTRO}/contribuinte", headers=_headers(token), timeout=30)
    _check_sitram_response(r, "Consulta contribuinte")
    return r.json()


# ── Consulta de Notas Fiscais ────────────────────────────────────────────────

def consultar_nota_fiscal(
    sessao: requests.Session,
    token: str,
    chave_acesso: str,
    page: int = 0,
    size: int = 20,
) -> dict:
    """
    Consulta nota fiscal por chave de acesso (ambiente logado).
    Endpoint: POST /api-nota/notafiscal/consulta-nota-fiscal
    """
    chave = "".join(c for c in chave_acesso if c.isdigit())
    r = sessao.post(
        f"{API_NOTA}/notafiscal/consulta-nota-fiscal",
        headers=_headers(token),
        json={"chaveAcesso": chave},
        params={"page": page, "size": size},
        timeout=30,
    )
    _check_sitram_response(r, "Consulta nota fiscal")
    return r.json()


def consultar_itens_por_chave(
    sessao: requests.Session,
    chave_acesso: str,
) -> dict:
    """
    Retorna os itens de uma nota fiscal por chave de acesso.
    Não requer autenticação.
    Endpoint: GET /api-nota/notafiscal/itens-nota-fiscal-por-chave-acesso/{chave}
    """
    chave = "".join(c for c in chave_acesso if c.isdigit())
    r = sessao.get(
        f"{API_NOTA}/notafiscal/itens-nota-fiscal-por-chave-acesso/{chave}",
        timeout=30,
    )
    _check_sitram_response(r, "Consulta itens nota fiscal")
    return r.json()


# ── Lançamentos por Nota Fiscal ──────────────────────────────────────────────
# Endpoints do serviceNotaFiscal (base: /api-nota/notafiscal)

def consultar_icms_nota(
    sessao: requests.Session,
    chave_acesso: str,
) -> list:
    """
    Consulta ICMS total/pago/devido de uma nota fiscal.
    Não requer autenticação.
    Endpoint: GET /api-nota/notafiscal/consulta-icms-nota/{chave}
    """
    chave = "".join(c for c in chave_acesso if c.isdigit())
    r = sessao.get(
        f"{API_NOTA}/notafiscal/consulta-icms-nota/{chave}",
        timeout=30,
    )
    _check_sitram_response(r, "Consulta ICMS nota")
    return r.json()


def consultar_nota_por_chave(
    sessao: requests.Session,
    token: str,
    chave_acesso: str,
) -> dict:
    """
    Retorna dados da NF incluindo situação de pagamento.
    Campos-chave: id, situacaoDescricao, situacaoDoImposto.
    Endpoint: GET /api-nota/notafiscal/por-chave-de-acesso/{chave}
    """
    chave = "".join(c for c in chave_acesso if c.isdigit())
    r = sessao.get(
        f"{API_NOTA}/notafiscal/por-chave-de-acesso/{chave}",
        headers=_headers(token),
        params={"page": 0, "size": 1},
        timeout=30,
    )
    _check_sitram_response(r, "Consulta NF por chave")
    data = r.json()
    content = data.get("content", [])
    return content[0] if content else {}


def consultar_lancamentos_nf(
    sessao: requests.Session,
    token: str,
    id_nota: int,
) -> list:
    """
    Retorna lançamentos de uma NF com status de pagamento.
    Campos-chave: idLancamentoFront, valor, valorPago, situacao, siuacaoDescricao.
    Endpoint: GET /api-nota/notafiscal/lancamentos-nota-fiscal/{idNota}
    """
    r = sessao.get(
        f"{API_NOTA}/notafiscal/lancamentos-nota-fiscal/{id_nota}",
        headers=_headers(token),
        timeout=30,
    )
    _check_sitram_response(r, "Lançamentos da NF")
    return r.json()


def obter_lancamentos_por_nota(
    sessao: requests.Session,
    token: str,
    filtro: dict,
    page: int = 0,
    size: int = 100,
) -> dict:
    """
    Retorna detalhes dos lançamentos (com idLancamentoFront) para uma NF.
    Endpoint: POST /api-nota/notafiscal/obter-detalhes-lancamento-por-notafiscal
    Filtro: {"numeroDanfe": "chave44dig", ...}
    """
    r = sessao.post(
        f"{API_NOTA}/notafiscal/obter-detalhes-lancamento-por-notafiscal",
        headers=_headers(token),
        json=filtro,
        params={"page": page, "size": size},
        timeout=30,
    )
    _check_sitram_response(r, "Lançamentos por nota fiscal")
    return r.json()


def obter_totais_regime_por_nota(
    sessao: requests.Session,
    token: str,
    filtro: dict,
) -> dict:
    """
    Retorna totais agrupados por regime (ANTECIPADO, DIFAL, ST, etc).
    Endpoint: POST /api-nota/notafiscal/obter-totais-por-regime-lancamento-por-notafiscal
    Filtro: {"numeroDanfe": "chave44dig", ...}
    """
    r = sessao.post(
        f"{API_NOTA}/notafiscal/obter-totais-por-regime-lancamento-por-notafiscal",
        headers=_headers(token),
        json=filtro,
        timeout=30,
    )
    _check_sitram_response(r, "Totais regime por NF")
    return r.json()


# ── Simulação de DAE ─────────────────────────────────────────────────────────
# Endpoints confirmados via probing: GET /api-pagamento/dae/simularDae*

def simular_dae(
    sessao: requests.Session,
    token: str,
    ids_lancamento: list[str],
    info: str = "",
) -> list:
    """
    Simula DAE para os IDs informados.
    Retorna lista vazia [] se não há DAE pendente (itens já pagos).
    Retorna dados da simulação se há DAE a gerar.
    Endpoint: GET /api-pagamento/dae/simularDae
    """
    r = sessao.get(
        f"{API_PAGAMENTO}/dae/simularDae",
        headers=_headers(token),
        params={"idsLancamento": ",".join(ids_lancamento), "info": info},
        timeout=30,
    )
    _check_sitram_response(r, "Simular DAE")
    return r.json()


def simular_dae_difal(
    sessao: requests.Session,
    token: str,
    ids_lancamento: list[str],
) -> list:
    """
    Simula DAE DIFAL.
    Endpoint: GET /api-pagamento/dae/simularDaeDifal
    """
    r = sessao.get(
        f"{API_PAGAMENTO}/dae/simularDaeDifal",
        headers=_headers(token),
        params={"idsLancamento": ",".join(ids_lancamento)},
        timeout=30,
    )
    _check_sitram_response(r, "Simular DAE DIFAL")
    return r.json()


def simular_dae_nf_difal(
    sessao: requests.Session,
    token: str,
    ids_lancamento: list[str],
) -> list:
    """
    Simula DAE para NF DIFAL.
    Endpoint: GET /api-pagamento/dae/simularDaeNotaFiscalDifal
    """
    r = sessao.get(
        f"{API_PAGAMENTO}/dae/simularDaeNotaFiscalDifal",
        headers=_headers(token),
        params={"idsLancamento": ",".join(ids_lancamento)},
        timeout=30,
    )
    _check_sitram_response(r, "Simular DAE NF DIFAL")
    return r.json()


def simular_dae_convenio(
    sessao: requests.Session,
    token: str,
    ids_lancamento: list[str],
) -> list:
    """
    Simula DAE Convênio.
    Endpoint: GET /api-pagamento/dae/simularDaeConvenio
    """
    r = sessao.get(
        f"{API_PAGAMENTO}/dae/simularDaeConvenio",
        headers=_headers(token),
        params={"idsLancamento": ",".join(ids_lancamento)},
        timeout=30,
    )
    _check_sitram_response(r, "Simular DAE Convênio")
    return r.json()


def buscar_numero_dae(
    sessao: requests.Session,
    token: str,
    id_lancamento: str,
) -> dict:
    """
    Busca número do DAE para um lançamento.
    Endpoint: GET /api-pagamento/dae/buscarNumeroDae
    """
    r = sessao.get(
        f"{API_PAGAMENTO}/dae/buscarNumeroDae",
        headers=_headers(token),
        params={"idLancamento": id_lancamento},
        timeout=30,
    )
    _check_sitram_response(r, "Buscar número DAE")
    return r.json()


def obter_relatorio_dae(
    sessao: requests.Session,
    token: str,
    id_dae: str,
) -> bytes:
    """
    Baixa relatório/boleto do DAE em PDF.
    Endpoint: GET /api-pagamento/dae/relatorio-dae/{id}
    """
    r = sessao.get(
        f"{API_PAGAMENTO}/dae/relatorio-dae/{id_dae}",
        headers=_headers(token),
        timeout=30,
    )
    _check_sitram_response(r, "Relatório DAE")
    return r.content


def obter_data_pagamento(
    sessao: requests.Session,
    token: str,
    data: str,
) -> dict:
    """
    Valida e retorna data de pagamento.
    Endpoint: GET /api-pagamento/dae/retorna-data-pagamento
    """
    r = sessao.get(
        f"{API_PAGAMENTO}/dae/retorna-data-pagamento",
        headers=_headers(token),
        params={"dataPagamento": data},
        timeout=30,
    )
    _check_sitram_response(r, "Data pagamento")
    return r.json()


# ── Relatórios / CSV ─────────────────────────────────────────────────────────

def gerar_csv(
    sessao: requests.Session,
    token: str,
    payload: dict,
) -> bytes:
    """
    Gera CSV de relatório de pagamentos.
    Endpoint: POST /api-pagamento/gerar-csv
    Retorna bytes do arquivo CSV.
    """
    r = sessao.post(
        f"{API_PAGAMENTO}/gerar-csv",
        headers=_headers(token),
        json=payload,
        timeout=60,
    )
    _check_sitram_response(r, "Gerar CSV")
    return r.content


# ── Função de alto nível: conectar e consultar ───────────────────────────────

class SitramClient:
    """Cliente SITRAM com sessão e token gerenciados."""

    def __init__(self, pfx_bytes: bytes, pfx_senha: str):
        self.sessao = _sessao(pfx_bytes, pfx_senha)
        self.token = ""
        self.token_expiry = 0.0

    def autenticar(self) -> dict:
        """Executa login SSO e armazena o token."""
        dados = login(self.sessao)
        self.token = dados["access_token"]
        self.token_expiry = time.time() + dados.get("expires_in", 300) - 30
        return dados

    def _check_token(self):
        if not self.token:
            raise RuntimeError("Não autenticado. Chame autenticar() primeiro.")
        if time.time() >= self.token_expiry:
            renovado = renovar_token(self.sessao, self.token)
            if renovado and "access_token" in renovado:
                self.token = renovado["access_token"]
                self.token_expiry = time.time() + renovado.get("expires_in", 300) - 30
            else:
                self.autenticar()

    def contribuinte(self) -> dict:
        self._check_token()
        return get_contribuinte(self.sessao, self.token)

    def consultar_nota(self, chave_acesso: str) -> dict:
        self._check_token()
        return consultar_nota_fiscal(self.sessao, self.token, chave_acesso)

    def consultar_itens(self, chave_acesso: str) -> dict:
        return consultar_itens_por_chave(self.sessao, chave_acesso)

    def consultar_icms_nota(self, chave_acesso: str) -> list:
        return consultar_icms_nota(self.sessao, chave_acesso)

    def consultar_nota_por_chave(self, chave_acesso: str) -> dict:
        self._check_token()
        return consultar_nota_por_chave(self.sessao, self.token, chave_acesso)

    def consultar_lancamentos_nf(self, id_nota: int) -> list:
        self._check_token()
        return consultar_lancamentos_nf(self.sessao, self.token, id_nota)

    def lancamentos_por_nota(self, filtro: dict, page: int = 0, size: int = 100) -> dict:
        self._check_token()
        return obter_lancamentos_por_nota(self.sessao, self.token, filtro, page, size)

    def totais_regime_por_nota(self, filtro: dict) -> dict:
        self._check_token()
        return obter_totais_regime_por_nota(self.sessao, self.token, filtro)

    def simular_dae(self, ids: list[str], info: str = "") -> list:
        self._check_token()
        return simular_dae(self.sessao, self.token, ids, info)

    def simular_dae_difal(self, ids: list[str]) -> list:
        self._check_token()
        return simular_dae_difal(self.sessao, self.token, ids)

    def simular_dae_nf_difal(self, ids: list[str]) -> list:
        self._check_token()
        return simular_dae_nf_difal(self.sessao, self.token, ids)

    def simular_dae_convenio(self, ids: list[str]) -> list:
        self._check_token()
        return simular_dae_convenio(self.sessao, self.token, ids)

    def buscar_numero_dae(self, id_lancamento: str) -> dict:
        self._check_token()
        return buscar_numero_dae(self.sessao, self.token, id_lancamento)

    def obter_relatorio_dae(self, id_dae: str) -> bytes:
        self._check_token()
        return obter_relatorio_dae(self.sessao, self.token, id_dae)

    def obter_data_pagamento(self, data: str) -> dict:
        self._check_token()
        return obter_data_pagamento(self.sessao, self.token, data)

    def gerar_csv(self, payload: dict) -> bytes:
        self._check_token()
        return gerar_csv(self.sessao, self.token, payload)
