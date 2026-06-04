"""
core/api_nfse.py — Cliente para a API REST NFS-e Nacional (webservices.nfse.gov.br)

Fluxo:
  1. Usuário sobe certificado .pfx + senha
  2. Extraímos cert/key em arquivos temporários para mTLS
  3. Obtemos token JWT via POST /nfse-auth/api/v1/auth/token
  4. Consultamos NFS-e emitidas/tomadas por CNPJ + período
  5. Baixamos cada XML e devolvemos como ZIP em memória
"""

import io
import re
import zipfile
import tempfile
import os
import requests
from datetime import datetime, date

BASE_URL = "https://webservices.nfse.gov.br"
AUTH_URL = f"{BASE_URL}/nfse-auth/api/v1/auth/token"
NFSE_URL = f"{BASE_URL}/nfse/1"

TIMEOUT = 30


def _limpar_cnpj(cnpj: str) -> str:
    return re.sub(r"\D", "", cnpj)


def _extrair_cert_pfx(pfx_bytes: bytes, senha: str):
    """
    Extrai certificado e chave privada do .pfx e escreve em arquivos
    temporários. Retorna (cert_path, key_path, [tmpfiles]).
    """
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PrivateFormat, NoEncryption
    )
    from cryptography.hazmat.primitives.serialization.pkcs12 import (
        load_key_and_certificates
    )

    senha_bytes = senha.encode() if isinstance(senha, str) else senha
    private_key, certificate, _ = load_key_and_certificates(pfx_bytes, senha_bytes)

    cert_pem = certificate.public_bytes(Encoding.PEM)
    key_pem  = private_key.private_bytes(Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption())

    cert_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
    key_tmp  = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
    cert_tmp.write(cert_pem); cert_tmp.flush(); cert_tmp.close()
    key_tmp.write(key_pem);   key_tmp.flush(); key_tmp.close()

    return cert_tmp.name, key_tmp.name


def _obter_token(cert_path: str, key_path: str) -> str:
    """Autentica via mTLS e retorna JWT."""
    resp = requests.post(
        AUTH_URL,
        cert=(cert_path, key_path),
        json={"grant_type": "client_credentials"},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data.get("access_token") or data.get("token")
    if not token:
        raise ValueError(f"Token não encontrado na resposta: {data}")
    return token


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/xml"}


def _consultar_nfse(
    cnpj: str,
    token: str,
    data_ini: date,
    data_fim: date,
    tipo: str = "tomadas",
    pagina: int = 1,
    por_pagina: int = 50,
) -> dict:
    """
    Consulta lista de NFS-e.
    tipo: 'tomadas' | 'emitidas'
    """
    cnpj = _limpar_cnpj(cnpj)
    url = f"{NFSE_URL}/{cnpj}/nfse/{tipo}"
    params = {
        "dataInicial": data_ini.strftime("%Y-%m-%d"),
        "dataFinal":   data_fim.strftime("%Y-%m-%d"),
        "pagina":      pagina,
        "quantidadeNfse": por_pagina,
    }
    resp = requests.get(url, headers=_headers(token), params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _baixar_xml_nfse(cnpj: str, chave: str, token: str) -> bytes:
    """Baixa o XML de uma NFS-e pela chave de acesso."""
    cnpj = _limpar_cnpj(cnpj)
    url  = f"{NFSE_URL}/{cnpj}/nfse/{chave}/xml"
    resp = requests.get(url, headers=_headers(token), timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.content


def baixar_xmls_nfse(
    pfx_bytes: bytes,
    senha: str,
    cnpj: str,
    data_ini: date,
    data_fim: date,
    tipo: str = "tomadas",
    progress_cb=None,
) -> tuple[bytes, list[str]]:
    """
    Ponto de entrada principal.

    Retorna:
        zip_bytes  — arquivo ZIP em memória com todos os XMLs
        log        — lista de strings de log
    """
    log: list[str] = []
    cert_path = key_path = None

    try:
        log.append("Extraindo certificado .pfx...")
        cert_path, key_path = _extrair_cert_pfx(pfx_bytes, senha)

        log.append("Autenticando na API NFS-e...")
        token = _obter_token(cert_path, key_path)
        log.append("Token obtido com sucesso.")

        # Coleta todas as páginas
        chaves: list[str] = []
        pagina = 1
        while True:
            log.append(f"Consultando página {pagina}...")
            resultado = _consultar_nfse(cnpj, token, data_ini, data_fim, tipo, pagina)
            notas = resultado.get("nfse") or resultado.get("listaNfse") or []
            if not notas:
                break
            for nota in notas:
                chave = nota.get("chaveAcesso") or nota.get("nfseId") or nota.get("id")
                if chave:
                    chaves.append(str(chave))
            total_paginas = resultado.get("totalPaginas") or 1
            if pagina >= total_paginas:
                break
            pagina += 1

        log.append(f"{len(chaves)} nota(s) encontrada(s).")

        if not chaves:
            return b"", log

        # Baixa XMLs e compacta em ZIP
        buf = io.BytesIO()
        erros = 0
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, chave in enumerate(chaves, 1):
                try:
                    xml_bytes = _baixar_xml_nfse(cnpj, chave, token)
                    zf.writestr(f"nfse_{chave}.xml", xml_bytes)
                    log.append(f"[{i}/{len(chaves)}] {chave} — OK")
                except Exception as e:
                    erros += 1
                    log.append(f"[{i}/{len(chaves)}] {chave} — ERRO: {e}")
                if progress_cb:
                    progress_cb(i / len(chaves))

        buf.seek(0)
        log.append(f"Concluído. {len(chaves) - erros} XMLs baixados, {erros} erros.")
        return buf.read(), log

    finally:
        for p in (cert_path, key_path):
            if p and os.path.exists(p):
                os.unlink(p)
