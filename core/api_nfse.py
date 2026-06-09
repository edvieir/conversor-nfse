"""
core/api_nfse.py — Cliente para a API NFS-e ADN Contribuinte
Base: https://adn.nfse.gov.br/contribuintes
Auth: mTLS (certificado A1 .pfx) — sem token, o cert é a autenticação
Ref:  swagger.json v1 / GET /DFe/{NSU}, GET /DANFSe/{chaveAcesso}
"""

import io
import re
import ssl
import base64
import gzip
import zipfile
import tempfile
import os
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
from datetime import date

BASE_URL  = "https://adn.nfse.gov.br/contribuintes"
TIMEOUT   = 90
_RETRIES  = 3


def _limpar_cnpj(cnpj: str) -> str:
    return re.sub(r"\D", "", cnpj)


def _extrair_cert_pfx(pfx_bytes: bytes, senha: str):
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

    cnpj_cert = ""
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

    cert_pem = certificate.public_bytes(Encoding.PEM)
    if additional_certs:
        for ac in additional_certs:
            cert_pem += ac.public_bytes(Encoding.PEM)
    key_pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    cert_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
    key_tmp  = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
    cert_tmp.write(cert_pem); cert_tmp.flush(); cert_tmp.close()
    key_tmp.write(key_pem);   key_tmp.flush(); key_tmp.close()

    return cert_tmp.name, key_tmp.name, cnpj_cert


def extrair_cnpj_do_pfx(pfx_bytes: bytes, senha: str) -> str:
    try:
        c, k, cnpj = _extrair_cert_pfx(pfx_bytes, senha)
        for p in (c, k):
            if os.path.exists(p):
                os.unlink(p)
        return cnpj
    except Exception:
        return ""


def _decodificar_xml(arquivo_xml_b64: str) -> bytes:
    raw = base64.b64decode(arquivo_xml_b64)
    try:
        return gzip.decompress(raw)
    except Exception:
        return raw


class _MTLSAdapter(HTTPAdapter):
    def __init__(self, cert_path: str, key_path: str, **kwargs):
        self._cert_path = cert_path
        self._key_path  = key_path
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.load_cert_chain(self._cert_path, self._key_path)
        kwargs["ssl_context"] = ctx
        super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, proxy, **proxy_kwargs):
        ctx = create_urllib3_context()
        ctx.load_cert_chain(self._cert_path, self._key_path)
        proxy_kwargs["ssl_context"] = ctx
        return super().proxy_manager_for(proxy, **proxy_kwargs)


def _make_session(cert_path: str, key_path: str) -> requests.Session:
    s = requests.Session()
    s.mount("https://", _MTLSAdapter(cert_path, key_path))
    return s


def _consultar_lote(cert_path: str, key_path: str, cnpj: str, nsu: int) -> dict | None:
    url    = f"{BASE_URL}/DFe/{nsu}"
    params = {"cnpjConsulta": cnpj, "lote": "true"}
    ultimo_erro = None
    for tentativa in range(1, _RETRIES + 1):
        try:
            with _make_session(cert_path, key_path) as s:
                resp = s.get(url, params=params, timeout=TIMEOUT)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            ultimo_erro = e
            if tentativa < _RETRIES:
                time.sleep(5 * tentativa)
    raise ultimo_erro


def _baixar_danfse(cert_path: str, key_path: str, cnpj: str, chave: str, log: list) -> bytes | None:
    url    = f"{BASE_URL}/DANFSe/{chave}"
    ultimo_err = None
    for tentativa in range(1, _RETRIES + 1):
        try:
            with _make_session(cert_path, key_path) as s:
                resp = s.get(url, timeout=TIMEOUT)
            if resp.status_code == 404:
                log.append(f"      PDF 404 — chave nao encontrada na API")
                return None
            if resp.status_code == 429:
                espera = 30 * tentativa
                log.append(f"      PDF 429 (rate limit) — aguardando {espera}s")
                time.sleep(espera)
                continue
            if not resp.ok:
                log.append(f"      PDF HTTP {resp.status_code}: {resp.text[:200]}")
                return None
            ct = resp.headers.get("Content-Type", "")
            if "pdf" not in ct.lower() and len(resp.content) < 200:
                log.append(f"      PDF resposta inesperada (Content-Type: {ct}, {len(resp.content)} bytes): {resp.text[:120]}")
                return None
            return resp.content
        except Exception as e:
            ultimo_err = e
            if tentativa < _RETRIES:
                log.append(f"      PDF tentativa {tentativa} falhou: {e} — aguardando {5*tentativa}s")
                time.sleep(5 * tentativa)
    log.append(f"      PDF erro final: {ultimo_err}")
    return None


def baixar_xmls_nfse(
    pfx_bytes: bytes,
    senha: str,
    cnpj: str,
    data_ini: date,
    data_fim: date,
    tipo: str = "tomados",
    formato: str = "xml",
    progress_cb=None,
    log_cb=None,
) -> tuple[bytes, list[str]]:
    log: list[str] = []
    cert_path = key_path = None

    try:
        log.append("Extraindo certificado .pfx...")
        if log_cb: log_cb(log)
        cert_path, key_path, cnpj_cert = _extrair_cert_pfx(pfx_bytes, senha)

        cnpj_uso = _limpar_cnpj(cnpj) if cnpj and cnpj.strip() else cnpj_cert
        if not cnpj_uso:
            raise ValueError("CNPJ nao encontrado no certificado nem informado.")
        log.append(f"CNPJ: {cnpj_uso}  |  Tipo: {tipo}  |  Formato: {formato}")
        log.append("Conectando na API NFS-e (mTLS)...")
        if log_cb: log_cb(log)

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

                if resultado is None:
                    log.append("Sem mais documentos (fim da fila).")
                    break

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
                    data_str = (doc.get("DataHoraGeracao") or "")[:10]

                    log.append(f"    NSU={nsu_doc} tipo={tipo_doc} data={data_str}")

                    if tipo_doc != "NFSE":
                        continue

                    arquivo_b64 = doc.get("ArquivoXml")
                    if not arquivo_b64:
                        log.append(f"    -> sem ArquivoXml, ignorado")
                        continue

                    chave = doc.get("ChaveAcesso") or str(nsu_doc)
                    try:
                        xml_bytes = _decodificar_xml(arquivo_b64)

                        import xml.etree.ElementTree as _ET2
                        try:
                            _root = _ET2.fromstring(xml_bytes)

                            if tipo != "todos":
                                _toma_el  = next((e for e in _root.iter() if e.tag.endswith("toma")), None)
                                _prest_el = next((e for e in _root.iter() if e.tag.endswith("prest")), None)

                                cnpj_toma  = ""
                                cnpj_prest = ""
                                if _toma_el is not None:
                                    cnpj_toma = re.sub(r"\D", "", next(
                                        (e.text or "" for e in _toma_el.iter() if e.tag.endswith("CNPJ")), ""
                                    ))
                                if _prest_el is not None:
                                    cnpj_prest = re.sub(r"\D", "", next(
                                        (e.text or "" for e in _prest_el.iter() if e.tag.endswith("CNPJ")), ""
                                    ))

                                if tipo == "tomados":
                                    if cnpj_toma and cnpj_toma != cnpj_uso:
                                        log.append(f"    -> servico prestado (nao tomado), ignorado")
                                        continue
                                elif tipo == "prestados":
                                    if cnpj_prest and cnpj_prest != cnpj_uso:
                                        log.append(f"    -> servico tomado (nao prestado), ignorado")
                                        continue

                            # Filtra pela competencia (dCompet) — compara apenas ano-mes
                            _el = next((e for e in _root.iter() if e.tag.endswith("dCompet")), None)
                            if _el is not None and _el.text:
                                try:
                                    data_compet = date.fromisoformat(_el.text.strip()[:10])
                                    # Competencia e mes/ano — ignora o dia
                                    compet_ym = (data_compet.year, data_compet.month)
                                    ini_ym    = (data_ini.year,    data_ini.month)
                                    fim_ym    = (data_fim.year,    data_fim.month)
                                    if not (ini_ym <= compet_ym <= fim_ym):
                                        log.append(f"    -> competencia {data_compet.year}-{data_compet.month:02d} fora do periodo, ignorado")
                                        continue
                                except ValueError:
                                    log.append(f"    -> dCompet formato invalido '{_el.text}', incluido")
                            # Se nao tem dCompet: inclui a nota
                        except Exception as parse_err:
                            log.append(f"    -> aviso parse XML: {parse_err}, incluido")

                        if formato in ("xml", "ambos"):
                            zf.writestr(f"xml/nfse_{chave}.xml", xml_bytes)
                            log.append(f"    -> XML salvo: xml/nfse_{chave}.xml")

                        if formato in ("pdf", "ambos"):
                            log.append(f"    -> baixando PDF (DANFSe) chave={chave!r} ({len(chave)} chars)...")
                            time.sleep(1)  # evita rate limit 429
                            pdf_bytes = _baixar_danfse(cert_path, key_path, cnpj_uso, chave, log)
                            if pdf_bytes:
                                zf.writestr(f"pdf/nfse_{chave}.pdf", pdf_bytes)
                                log.append(f"    -> PDF salvo: pdf/nfse_{chave}.pdf")
                            else:
                                log.append(f"    -> PDF nao baixado (ver linha acima)")

                        total_ok += 1

                    except Exception as e:
                        erros += 1
                        log.append(f"    -> ERRO: {e}")

                if nsu_max <= nsu:
                    log.append("NSU nao avancou, encerrando.")
                    if log_cb: log_cb(log)
                    break
                nsu = nsu_max + 1

                if log_cb: log_cb(log)
                if progress_cb:
                    progress_cb(min(lote_num / (lote_num + 1), 0.95))

        if progress_cb:
            progress_cb(1.0)

        log.append(f"Concluido. {total_ok} NFS-e no periodo, {erros} erros.")
        buf.seek(0)
        return (buf.read() if total_ok > 0 else b""), log

    finally:
        for p in (cert_path, key_path):
            if p and os.path.exists(p):
                os.unlink(p)
