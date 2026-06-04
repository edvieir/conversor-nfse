"""
core/api_nfse.py — Cliente para a API NFS-e ADN Contribuinte
Base: https://adn.nfse.gov.br/contribuintes
Auth: mTLS (certificado A1 .pfx) — sem token, o cert é a autenticação
Ref:  swagger.json v1 / GET /DFe/{NSU}
"""

import io
import re
import base64
import gzip
import zipfile
import tempfile
import os
import requests
from datetime import date

BASE_URL = "https://adn.nfse.gov.br/contribuintes"
TIMEOUT  = 30


def _limpar_cnpj(cnpj: str) -> str:
    return re.sub(r"\D", "", cnpj)


def _extrair_cert_pfx(pfx_bytes: bytes, senha: str):
    """
    Extrai cert/key do .pfx para arquivos temporários PEM.
    Retorna (cert_path, key_path, cnpj_extraido).
    """
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PrivateFormat, NoEncryption,
    )
    from cryptography.hazmat.primitives.serialization.pkcs12 import (
        load_key_and_certificates,
    )
    from cryptography.x509 import ObjectIdentifier
    from cryptography.x509.oid import NameOID

    senha_bytes = senha.encode() if isinstance(senha, str) else senha
    private_key, certificate, additional_certs = load_key_and_certificates(pfx_bytes, senha_bytes)

    # ── Extrai CNPJ do certificado ──────────────────────────────────────────
    cnpj_cert = ""
    # Tenta SubjectAltName OID 2.16.76.1.3.3 (CNPJ ICP-Brasil)
    try:
        from cryptography.x509 import SubjectAlternativeName, OtherName
        san_ext = certificate.extensions.get_extension_for_class(SubjectAlternativeName)
        for gn in san_ext.value:
            val = str(gn.value) if hasattr(gn, "value") else ""
            digits = re.sub(r"\D", "", val)
            if len(digits) == 14:
                cnpj_cert = digits
                break
    except Exception:
        pass

    if not cnpj_cert:
        # Tenta CN: "RAZAO SOCIAL:12345678000199"
        try:
            cn = certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
            digits = re.sub(r"\D", "", cn.split(":")[-1])
            if len(digits) == 14:
                cnpj_cert = digits
        except Exception:
            pass

    if not cnpj_cert:
        try:
            sn = certificate.subject.get_attributes_for_oid(NameOID.SERIAL_NUMBER)[0].value
            digits = re.sub(r"\D", "", sn)
            if len(digits) >= 14:
                cnpj_cert = digits[:14]
        except Exception:
            pass

    # ── Salva PEM (inclui cadeia intermediária ICP-Brasil) ──────────────────
    cert_pem = certificate.public_bytes(Encoding.PEM)
    if additional_certs:
        for ac in additional_certs:
            cert_pem += ac.public_bytes(Encoding.PEM)
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


def _decodificar_xml(arquivo_xml_b64: str) -> bytes:
    """Decodifica ArquivoXml: base64 → gzip decompress → XML bytes."""
    raw = base64.b64decode(arquivo_xml_b64)
    try:
        return gzip.decompress(raw)
    except Exception:
        return raw  # já era XML puro sem compressão


def _consultar_lote(
    cert_path: str,
    key_path: str,
    cnpj: str,
    nsu: int,
) -> dict:
    """GET /DFe/{NSU}?cnpjConsulta={CNPJ}&lote=true"""
    url    = f"{BASE_URL}/DFe/{nsu}"
    params = {"cnpjConsulta": cnpj, "lote": "true"}
    resp   = requests.get(
        url, cert=(cert_path, key_path), params=params, timeout=TIMEOUT
    )
    resp.raise_for_status()
    return resp.json()


def baixar_xmls_nfse(
    pfx_bytes: bytes,
    senha: str,
    cnpj: str,
    data_ini: date,
    data_fim: date,
    tipo: str = "tomadas",   # mantido para compatibilidade, não usado na API
    progress_cb=None,
) -> tuple[bytes, list[str]]:
    """
    Baixa todas as NFS-e via NSU a partir do NSU 0, filtra pelo período
    data_ini..data_fim e retorna (zip_bytes, log).

    A API não tem filtro por data — iteramos os NSUs e filtramos localmente.
    """
    log: list[str] = []
    cert_path = key_path = None

    try:
        log.append("Extraindo certificado .pfx...")
        cert_path, key_path, cnpj_cert = _extrair_cert_pfx(pfx_bytes, senha)

        cnpj_uso = _limpar_cnpj(cnpj) if cnpj and cnpj.strip() else cnpj_cert
        if not cnpj_uso:
            raise ValueError("CNPJ não encontrado no certificado nem informado.")
        log.append(f"CNPJ: {cnpj_uso}")
        log.append("Conectando na API NFS-e (mTLS)...")

        buf      = io.BytesIO()
        nsu      = 0
        total_ok = 0
        erros    = 0
        lote_num = 0

        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            while True:
                lote_num += 1
                log.append(f"Consultando lote a partir do NSU {nsu}...")
                resultado = _consultar_lote(cert_path, key_path, cnpj_uso, nsu)

                status = resultado.get("StatusProcessamento", "")
                if status == "NENHUM_DOCUMENTO_LOCALIZADO":
                    log.append("Sem mais documentos.")
                    break
                if status == "REJEICAO":
                    erros_api = resultado.get("Erros") or []
                    msgs = "; ".join(e.get("Descricao", "") for e in erros_api)
                    raise ValueError(f"API rejeitou a consulta: {msgs}")

                lote = resultado.get("LoteDFe") or []
                log.append(f"  Lote {lote_num}: {len(lote)} documento(s)")

                nsu_max = nsu
                for doc in lote:
                    nsu_doc = doc.get("NSU") or 0
                    if nsu_doc > nsu_max:
                        nsu_max = nsu_doc

                    tipo_doc = doc.get("TipoDocumento", "")
                    if tipo_doc != "NFSE":
                        continue

                    # Filtro por data (campo DataHoraGeracao)
                    data_str = (doc.get("DataHoraGeracao") or "")[:10]
                    if data_str:
                        try:
                            data_doc = date.fromisoformat(data_str)
                            if not (data_ini <= data_doc <= data_fim):
                                continue
                        except ValueError:
                            pass

                    arquivo_b64 = doc.get("ArquivoXml")
                    if not arquivo_b64:
                        continue

                    chave = doc.get("ChaveAcesso") or str(nsu_doc)
                    try:
                        xml_bytes = _decodificar_xml(arquivo_b64)
                        zf.writestr(f"nfse_{chave}.xml", xml_bytes)
                        total_ok += 1
                        log.append(f"  NFS-e {chave} ({data_str}) — OK")
                    except Exception as e:
                        erros += 1
                        log.append(f"  NFS-e {chave} — ERRO ao decodificar: {e}")

                # Avança NSU para o próximo lote
                if nsu_max <= nsu:
                    break  # sem avanço, evita loop infinito
                nsu = nsu_max

                if progress_cb:
                    progress_cb(min(lote_num / (lote_num + 1), 0.95))

        if progress_cb:
            progress_cb(1.0)

        log.append(f"Concluído. {total_ok} NFS-e no período, {erros} erros.")
        buf.seek(0)
        return (buf.read() if total_ok > 0 else b""), log

    finally:
        for p in (cert_path, key_path):
            if p and os.path.exists(p):
                os.unlink(p)
