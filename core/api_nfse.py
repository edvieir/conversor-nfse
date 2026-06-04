"""
core/api_nfse.py — Cliente para a API REST NFS-e Nacional
"""

import io
import re
import zipfile
import tempfile
import os
import requests
from datetime import date

# URLs oficiais da API NFS-e Nacional (SEFIN / ABRASF)
BASE_URL  = "https://api.nfse.gov.br"
AUTH_URL  = f"{BASE_URL}/v1/autenticacao/certificado"
NFSE_URL  = f"{BASE_URL}/v1"

TIMEOUT = 30


def _limpar_cnpj(cnpj: str) -> str:
    return re.sub(r"\D", "", cnpj)


def _extrair_cert_pfx(pfx_bytes: bytes, senha: str):
    """
    Extrai cert/key do .pfx, escreve em arquivos temporários e retorna
    (cert_path, key_path, cnpj_extraido).
    O CNPJ é lido do campo OID 2.16.76.1.3.3 ou do CN do certificado.
    """
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PrivateFormat, NoEncryption
    )
    from cryptography.hazmat.primitives.serialization.pkcs12 import (
        load_key_and_certificates
    )
    from cryptography.x509 import ObjectIdentifier
    from cryptography.x509.oid import NameOID

    senha_bytes = senha.encode() if isinstance(senha, str) else senha
    private_key, certificate, _ = load_key_and_certificates(pfx_bytes, senha_bytes)

    # ── Extrai CNPJ do certificado ──────────────────────────────────────────
    cnpj_cert = ""
    try:
        # OID CNPJ PJ brasileiro: 2.16.76.1.3.3
        OID_CNPJ = ObjectIdentifier("2.16.76.1.3.3")
        san = certificate.extensions.get_extension_for_oid(
            ObjectIdentifier("2.5.29.17")  # SubjectAltName
        )
        for gn in san.value:
            val = str(gn.value) if hasattr(gn, "value") else ""
            digits = re.sub(r"\D", "", val)
            if len(digits) == 14:
                cnpj_cert = digits
                break
    except Exception:
        pass

    if not cnpj_cert:
        # Tenta extrair do CN: "RAZAO SOCIAL:12345678000199" ou "12345678000199"
        try:
            cn = certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
            digits = re.sub(r"\D", "", cn.split(":")[-1])
            if len(digits) == 14:
                cnpj_cert = digits
        except Exception:
            pass

    if not cnpj_cert:
        # Tenta campo serialNumber
        try:
            sn = certificate.subject.get_attributes_for_oid(NameOID.SERIAL_NUMBER)[0].value
            digits = re.sub(r"\D", "", sn)
            if len(digits) >= 14:
                cnpj_cert = digits[:14]
        except Exception:
            pass

    # ── Salva PEM em arquivos temporários ───────────────────────────────────
    cert_pem = certificate.public_bytes(Encoding.PEM)
    key_pem  = private_key.private_bytes(
        Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()
    )

    cert_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
    key_tmp  = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
    cert_tmp.write(cert_pem); cert_tmp.flush(); cert_tmp.close()
    key_tmp.write(key_pem);   key_tmp.flush(); key_tmp.close()

    return cert_tmp.name, key_tmp.name, cnpj_cert


def extrair_cnpj_do_pfx(pfx_bytes: bytes, senha: str) -> str:
    """Utilitário público: retorna apenas o CNPJ extraído do .pfx."""
    try:
        c, k, cnpj = _extrair_cert_pfx(pfx_bytes, senha)
        for p in (c, k):
            if os.path.exists(p):
                os.unlink(p)
        return cnpj
    except Exception:
        return ""


def _obter_token(cert_path: str, key_path: str) -> str:
    """Autentica via mTLS e retorna JWT."""
    resp = requests.post(
        AUTH_URL,
        cert=(cert_path, key_path),
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    token = (
        data.get("access_token")
        or data.get("token")
        or data.get("accessToken")
    )
    if not token:
        raise ValueError(f"Token não encontrado na resposta: {data}")
    return token


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def _consultar_nfse(
    cnpj: str,
    token: str,
    data_ini: date,
    data_fim: date,
    tipo: str = "tomadas",
    pagina: int = 1,
    por_pagina: int = 50,
) -> dict:
    cnpj = _limpar_cnpj(cnpj)
    url = f"{NFSE_URL}/{cnpj}/nfse/{tipo}"
    params = {
        "dataInicial":    data_ini.strftime("%Y-%m-%d"),
        "dataFinal":      data_fim.strftime("%Y-%m-%d"),
        "pagina":         pagina,
        "quantidadeNfse": por_pagina,
    }
    resp = requests.get(url, headers=_headers(token), params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _baixar_xml_nfse(cnpj: str, chave: str, token: str) -> bytes:
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
    Retorna (zip_bytes, log).
    zip_bytes = ZIP em memória com todos os XMLs, ou b"" se nenhum encontrado.
    """
    log: list[str] = []
    cert_path = key_path = None

    try:
        log.append("Extraindo certificado .pfx...")
        cert_path, key_path, cnpj_cert = _extrair_cert_pfx(pfx_bytes, senha)

        # Usa CNPJ do cert se não foi passado explicitamente
        cnpj_uso = _limpar_cnpj(cnpj) if cnpj.strip() else cnpj_cert
        if not cnpj_uso:
            raise ValueError("CNPJ não encontrado no certificado nem informado manualmente.")
        log.append(f"CNPJ: {cnpj_uso}")

        log.append("Autenticando na API NFS-e...")
        token = _obter_token(cert_path, key_path)
        log.append("Autenticado com sucesso.")

        chaves: list[str] = []
        pagina = 1
        while True:
            log.append(f"Consultando página {pagina}...")
            resultado = _consultar_nfse(cnpj_uso, token, data_ini, data_fim, tipo, pagina)
            notas = resultado.get("nfse") or resultado.get("listaNfse") or []
            if not notas:
                break
            for nota in notas:
                chave = (
                    nota.get("chaveAcesso")
                    or nota.get("nfseId")
                    or nota.get("id")
                )
                if chave:
                    chaves.append(str(chave))
            total_paginas = resultado.get("totalPaginas") or 1
            if pagina >= total_paginas:
                break
            pagina += 1

        log.append(f"{len(chaves)} nota(s) encontrada(s).")
        if not chaves:
            return b"", log

        buf = io.BytesIO()
        erros = 0
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, chave in enumerate(chaves, 1):
                try:
                    xml_bytes = _baixar_xml_nfse(cnpj_uso, chave, token)
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
            if p and p and os.path.exists(p):
                os.unlink(p)
