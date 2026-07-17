"""
core/siga_sefaz.py
Cliente para a API REST do SIGA (Painel Indicador) da SEFAZ-CE.
Aceita certificado como bytes (vindo do banco), sem gravar em disco.

Mapeamento de endpoints obtido do OpenAPI publico em
https://siga.sefaz.ce.gov.br/api/v3/api-docs (sem autenticacao).

Login (OIDC/Keycloak com certificado digital) ainda NAO foi validado contra
o site ao vivo -- o SIGA estava fora do ar durante o levantamento. A funcao
`login()` implementa o fluxo Authorization Code + PKCE padrao do Keycloak
com o certificado anexado via mTLS (a especificacao do realm expõe
`tls_client_certificate_bound_access_tokens: true`), mas o passo exato de
"Entrar com Certificado Digital" precisa ser confirmado com uma captura de
rede real antes de considerar este modulo pronto para producao.
"""

import base64
import hashlib
import os
import re
import time
from urllib.parse import urlencode, urlparse, parse_qs

import requests
from requests_pkcs12 import Pkcs12Adapter

SSO_REALM = "https://sso.sefaz.ce.gov.br/auth/realms/sefaz-ad-realm"
SSO_AUTH_ENDPOINT = f"{SSO_REALM}/protocol/openid-connect/auth"
SSO_TOKEN_ENDPOINT = f"{SSO_REALM}/protocol/openid-connect/token"
SSO_CLIENT_ID = "painelind-frontend"
SSO_REDIRECT_URI = "https://siga.sefaz.ce.gov.br/ui/"

# "Entrar com Certificado Digital" é um identity broker do Keycloak que
# delega para um realm dedicado a mTLS em outro host (cert-sso). O TLS
# client cert só é pedido nesse host -- daí a necessidade de montar o
# adapter também nele.
CERT_IDP_ALIAS = "certificado-digital"
CERT_SSO_HOST = "https://cert-sso.sefaz.ce.gov.br"

SIGA_API = "https://siga.sefaz.ce.gov.br/api"

# tipo -> (segmento do path, prefixo do path: "unidades" usa CNPJ completo,
# "empresas" usa CNPJ base de 8 digitos)
TIPOS_DOCUMENTO = {
    "NF_E":  ("nf-e", "unidades"),
    "NFC_E": ("nfc-e", "unidades"),
    "CT_E":  ("ct-e", "unidades"),
    "MDF_E": ("mdf-e", "unidades"),
    "CF_E":  ("cf-e", "unidades"),
    "NF3_E": ("nf3-e", "empresas"),
    "NFS_E": ("nfs-e", "empresas"),
}

STATUS_CONCLUIDO = "CONCLUIDO"
STATUS_ERRO = "ERRO"
STATUS_EM_ANDAMENTO = {"SOLICITADO", "PROCESSANDO", "GERANDO_DADOS"}


def _sessao(pfx_bytes: bytes, pfx_senha: str) -> requests.Session:
    s = requests.Session()
    adapter = Pkcs12Adapter(
        pkcs12_data=pfx_bytes,
        pkcs12_password=pfx_senha.encode() if isinstance(pfx_senha, str) else pfx_senha,
    )
    # mTLS certificate-bound tokens: o certificado precisa ir tanto no login
    # (nos 3 hosts do fluxo de broker) quanto em toda chamada subsequente à API.
    s.mount("https://sso.sefaz.ce.gov.br", adapter)
    s.mount(CERT_SSO_HOST, adapter)
    s.mount("https://siga.sefaz.ce.gov.br", adapter)
    return s


def _pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(os.urandom(40)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


def login(sessao: requests.Session) -> dict:
    """
    Executa o fluxo Authorization Code + PKCE do Keycloak usando o
    certificado digital (mTLS), confirmado via captura de rede real:

    1. GET no endpoint de autorização do realm principal (sefaz-ad-realm)
       -> retorna a página de login (com AUTH_SESSION_ID em cookie) contendo
       um link para o broker "certificado-digital".
    2. GET nesse link de broker (/broker/certificado-digital/login) ->
       Keycloak redireciona (303) para o realm dedicado a mTLS, hospedado
       em outro host (cert-sso.sefaz.ce.gov.br, realm sefaz-x509-realm).
       É *nesse* host que o TLS pede o certificado do cliente.
    3. cert-sso valida o certificado e redireciona (302) de volta para o
       endpoint do broker no realm principal, que por sua vez redireciona
       para SSO_REDIRECT_URI com "#code=...&state=..." -- fluxo OIDC
       original concluído.

    Retorna o dict de resposta do token endpoint (access_token,
    refresh_token, expires_in, ...).
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
            "de login. O layout da tela pode ter mudado -- reinspecionar "
            f"a página em {r.url}."
        )
    broker_url = m.group(1).replace("&amp;", "&")
    if broker_url.startswith("/"):
        broker_url = f"https://sso.sefaz.ce.gov.br{broker_url}"

    # Segue: broker/login -> (mTLS) cert-sso -> broker/endpoint -> SSO_REDIRECT_URI
    r2 = sessao.get(broker_url, timeout=30, allow_redirects=True)
    r2.raise_for_status()

    final_url = r2.url
    fragment = urlparse(final_url).fragment
    qs = parse_qs(fragment)
    code = qs.get("code", [None])[0]
    if not code:
        raise RuntimeError(
            "Não foi possível extrair o 'code' após o broker de certificado. "
            f"URL final: {final_url}."
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


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def solicitar_download(
    sessao: requests.Session,
    token: str,
    cnpj: str,
    tipo: str,
    formato_arquivo: str = "xlsx",
    **filtros,
) -> str:
    """
    Dispara a geração assíncrona de um relatório (NF-e, NFC-e, CT-e, MDF-e,
    CF-e, NF3-e ou NFS-e). Retorna o id da solicitação criada.

    `filtros` aceita os parâmetros de query documentados na API, por
    exemplo: dat_referencia=["2026-06"], tipo_operacao="ENTRADA",
    papel_operacao="DESTINATARIO", resultado_processamento="...".
    Use underscore; a função converte para o formato kebab-case da API.
    """
    if tipo not in TIPOS_DOCUMENTO:
        raise ValueError(f"tipo inválido: {tipo}. Opções: {list(TIPOS_DOCUMENTO)}")

    segmento, prefixo = TIPOS_DOCUMENTO[tipo]
    cnpj_path = cnpj if prefixo == "unidades" else cnpj[:8]
    url = f"{SIGA_API}/v1/{prefixo}/{cnpj_path}/documentos-fiscais/{segmento}/download"

    params = {"formato-arquivo": formato_arquivo}
    for chave, valor in filtros.items():
        params[chave.replace("_", "-")] = valor

    r = sessao.post(
        url, headers=_headers(token), params=params,
        json={"descricao": f"{tipo} {cnpj} {filtros.get('dat_referencia', '')}"},
        timeout=30,
    )
    r.raise_for_status()
    body = r.json()
    return body.get("data", {}).get("id") or body.get("id")


def listar_solicitacoes(sessao: requests.Session, token: str) -> list[dict]:
    r = sessao.get(
        f"{SIGA_API}/v1/solicitacoes",
        headers=_headers(token), params={"sort": "criacao,desc"}, timeout=30,
    )
    r.raise_for_status()
    return r.json().get("data", [])


def baixar_solicitacao(sessao: requests.Session, token: str, solicitacao_id: str) -> bytes:
    r = sessao.get(
        f"{SIGA_API}/v1/solicitacoes/{solicitacao_id}/download",
        headers=_headers(token), timeout=60,
    )
    r.raise_for_status()
    return r.content


def aguardar_e_baixar(
    sessao: requests.Session,
    token: str,
    solicitacao_id: str,
    timeout: int = 180,
    intervalo: int = 3,
) -> bytes:
    """Faz polling em /v1/solicitacoes até o status virar CONCLUIDO e baixa o arquivo."""
    decorrido = 0
    while decorrido < timeout:
        solicitacoes = listar_solicitacoes(sessao, token)
        alvo = next((s for s in solicitacoes if s.get("id") == solicitacao_id), None)
        if alvo:
            status = alvo.get("status")
            if status == STATUS_CONCLUIDO:
                return baixar_solicitacao(sessao, token, solicitacao_id)
            if status == STATUS_ERRO:
                raise RuntimeError(f"Solicitação {solicitacao_id} terminou com erro no SIGA.")
        time.sleep(intervalo)
        decorrido += intervalo
    raise TimeoutError(f"Solicitação {solicitacao_id} não concluiu em {timeout}s.")
