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

def get_contribuinte(sessao: requests.Session, token: str) -> dict:
    """Retorna dados cadastrais do contribuinte logado."""
    r = sessao.get(f"{API_CADASTRO}/contribuinte", headers=_headers(token), timeout=30)
    r.raise_for_status()
    return r.json()


# ── Consulta de Notas Fiscais ────────────────────────────────────────────────

def consultar_nota_fiscal(
    sessao: requests.Session,
    token: str,
    chave_acesso: str,
) -> dict:
    """
    Consulta nota fiscal por chave de acesso (ambiente logado).
    Endpoint: GET /api-nota/nota-fiscal-ambiente-logado/consultar
    """
    chave = "".join(c for c in chave_acesso if c.isdigit())
    r = sessao.get(
        f"{API_NOTA}/nota-fiscal-ambiente-logado/consultar",
        headers=_headers(token),
        params={"chaveAcesso": chave},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def consultar_nota_fiscal_publica(
    sessao: requests.Session,
    chave_acesso: str,
) -> dict:
    """
    Consulta nota fiscal por chave (sem login, dados limitados).
    Endpoint: GET /api-nota/nota-fiscal/consulta
    """
    chave = "".join(c for c in chave_acesso if c.isdigit())
    r = sessao.get(
        f"{API_NOTA}/nota-fiscal/consulta",
        params={"chaveAcesso": chave},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def detalhar_nota_fiscal(
    sessao: requests.Session,
    token: str,
    id_nota: str,
    chave_acesso: str,
    sistema_origem: str = "SITRAM",
) -> dict:
    """
    Detalha uma nota fiscal específica.
    Endpoint: GET /api-nota/nota-fiscal-ambiente-logado/detalhe/{id}/{chave}/{sistema}
    """
    r = sessao.get(
        f"{API_NOTA}/nota-fiscal-ambiente-logado/detalhe/{id_nota}/{chave_acesso}/{sistema_origem}",
        headers=_headers(token),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


# ── Calculadora DIFAL / ICMS ─────────────────────────────────────────────────

def simular_dae(
    sessao: requests.Session,
    token: str,
    ids_lancamento: list[str],
    info: str = "",
) -> dict:
    """
    Simula DAE para os lançamentos informados.
    Endpoint: GET /api-calculadora/simularDae
    """
    r = sessao.get(
        f"{API_CALCULADORA}/simularDae",
        headers=_headers(token),
        params={"idsLancamento": ",".join(ids_lancamento), "info": info},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def simular_dae_difal(
    sessao: requests.Session,
    token: str,
    ids_lancamento: list[str],
) -> dict:
    """
    Simula DAE DIFAL.
    Endpoint: GET /api-calculadora/simularDaeDifal
    """
    r = sessao.get(
        f"{API_CALCULADORA}/simularDaeDifal",
        headers=_headers(token),
        params={"idsLancamento": ",".join(ids_lancamento)},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def simular_dae_nf_difal(
    sessao: requests.Session,
    token: str,
    ids_lancamento: list[str],
) -> dict:
    """
    Simula DAE para NF DIFAL.
    Endpoint: GET /api-calculadora/simularDaeNotaFiscalDifal
    """
    r = sessao.get(
        f"{API_CALCULADORA}/simularDaeNotaFiscalDifal",
        headers=_headers(token),
        params={"idsLancamento": ",".join(ids_lancamento)},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def simular_dae_convenio(
    sessao: requests.Session,
    token: str,
    ids_lancamento: list[str],
) -> dict:
    """
    Simula DAE Convênio.
    Endpoint: GET /api-calculadora/simularDaeConvenio
    """
    r = sessao.get(
        f"{API_CALCULADORA}/simularDaeConvenio",
        headers=_headers(token),
        params={"idsLancamento": ",".join(ids_lancamento)},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def emitir_difal(
    sessao: requests.Session,
    token: str,
    payload: dict,
) -> dict:
    """
    Emite DIFAL.
    Endpoint: POST /api-calculadora/difal/emitir
    """
    r = sessao.post(
        f"{API_CALCULADORA}/difal/emitir",
        headers=_headers(token),
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


# ── Pagamentos / DAE ─────────────────────────────────────────────────────────

def emitir_dae(
    sessao: requests.Session,
    token: str,
    payload: dict,
    ids_lancamento: str = "",
    info: str = "",
) -> dict:
    """
    Emite DAE.
    Endpoint: POST /api-pagamento/emitir-dae
    """
    params = {}
    if ids_lancamento:
        params["idsLancamento"] = ids_lancamento
    if info:
        params["info"] = info
    r = sessao.post(
        f"{API_PAGAMENTO}/emitir-dae",
        headers=_headers(token),
        json=payload,
        params=params,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def emitir_dae_convenio(
    sessao: requests.Session,
    token: str,
) -> dict:
    """
    Emite DAE Convênio.
    Endpoint: GET /api-calculadora/emitir-dae-convenio
    """
    r = sessao.get(
        f"{API_CALCULADORA}/emitir-dae-convenio",
        headers=_headers(token),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def simular_dae_sanfit(
    sessao: requests.Session,
    token: str,
    payload: dict,
) -> dict:
    """
    Simula DAE SANFIT.
    Endpoint: POST /api-pagamento/simular-dae-sanfit
    """
    r = sessao.post(
        f"{API_PAGAMENTO}/simular-dae-sanfit",
        headers=_headers(token),
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
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
    r.raise_for_status()
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

    def consultar_nota_publica(self, chave_acesso: str) -> dict:
        return consultar_nota_fiscal_publica(self.sessao, chave_acesso)

    def detalhar_nota(self, id_nota: str, chave: str, sistema: str = "SITRAM") -> dict:
        self._check_token()
        return detalhar_nota_fiscal(self.sessao, self.token, id_nota, chave, sistema)

    def simular_dae(self, ids: list[str], info: str = "") -> dict:
        self._check_token()
        return simular_dae(self.sessao, self.token, ids, info)

    def simular_dae_difal(self, ids: list[str]) -> dict:
        self._check_token()
        return simular_dae_difal(self.sessao, self.token, ids)

    def simular_dae_nf_difal(self, ids: list[str]) -> dict:
        self._check_token()
        return simular_dae_nf_difal(self.sessao, self.token, ids)

    def simular_dae_convenio(self, ids: list[str]) -> dict:
        self._check_token()
        return simular_dae_convenio(self.sessao, self.token, ids)

    def emitir_difal(self, payload: dict) -> dict:
        self._check_token()
        return emitir_difal(self.sessao, self.token, payload)

    def emitir_dae(self, payload: dict, ids: str = "", info: str = "") -> dict:
        self._check_token()
        return emitir_dae(self.sessao, self.token, payload, ids, info)

    def emitir_dae_convenio(self) -> dict:
        self._check_token()
        return emitir_dae_convenio(self.sessao, self.token)

    def simular_dae_sanfit(self, payload: dict) -> dict:
        self._check_token()
        return simular_dae_sanfit(self.sessao, self.token, payload)

    def gerar_csv(self, payload: dict) -> bytes:
        self._check_token()
        return gerar_csv(self.sessao, self.token, payload)
