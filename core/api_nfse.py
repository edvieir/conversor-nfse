"""
core/api_nfse.py — Cliente para a API NFS-e ADN Contribuinte
Base: https://adn.nfse.gov.br/contribuintes
Auth: mTLS (certificado A1 .pfx) — sem token, o cert é a autenticação
Ref:  swagger.json v1 / GET /DFe/{NSU}, GET /DANFSe/{chaveAcesso}
"""

import io
import re
import ssl
import unicodedata
import base64
import gzip
import zipfile
import tempfile
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
from datetime import date

BASE_URL  = "https://adn.nfse.gov.br/contribuintes"
TIMEOUT   = 90
_RETRIES        = 3
_PDF_WORKERS    = 3   # workers paralelos na fila de retry
_PDF_MAX_TRIES  = 10  # máx tentativas por PDF antes de desistir


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


def _is_cancelada(root) -> bool:
    """Detecta nota cancelada: nfseCanc, cStat != 100, ou cSitNFSe/tpSit fora do valor ativo."""
    if any(e.tag.endswith("nfseCanc") for e in root.iter()):
        return True
    el_cstat = next((e for e in root.iter() if e.tag.split("}")[-1] == "cStat"), None)
    if el_cstat is not None and el_cstat.text and el_cstat.text.strip() != "100":
        return True
    for tag in ("cSitNFSe", "tpSit", "cSit"):
        el = next((e for e in root.iter() if e.tag.endswith(tag)), None)
        if el is not None and el.text and el.text.strip() not in ("1", ""):
            return True
    return False


def _nome_arquivo(n_nfse: str, x_nome: str) -> str:
    """Gera identificador legível para nome de arquivo: {nNFSe}_{fornecedor_sanitizado}"""
    # remove CNPJ/CPF que prefixam o xNome (ex: "50.838.797 ANA CRISTINA...")
    nome = re.sub(r"^\d[\d.\-/]+\s*", "", x_nome).strip()
    # remove acentos
    nome = unicodedata.normalize("NFKD", nome)
    nome = "".join(c for c in nome if not unicodedata.combining(c))
    # substitui qualquer char não alfanumérico por underscore e colapsa múltiplos
    nome = re.sub(r"[^\w]", "_", nome)
    nome = re.sub(r"_+", "_", nome).strip("_")
    nome = nome[:40].rstrip("_")
    return f"{n_nfse}_{nome}" if nome else (n_nfse or "sem_identificacao")


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


_DANFSE_URL = "https://adn.nfse.gov.br/danfse"


def _tentar_danfse(cert_path: str, key_path: str, cnpj: str, chave: str) -> tuple[bytes | None, bool]:
    """Uma única tentativa HTTP. Retorna (pdf_bytes, deve_retry)."""
    url = f"{_DANFSE_URL}/{chave}"
    try:
        with _make_session(cert_path, key_path) as s:
            resp = s.get(url, params={"cnpjConsulta": cnpj},
                         headers={"Accept": "application/pdf"}, timeout=TIMEOUT)
        if resp.status_code == 200:
            ct = resp.headers.get("Content-Type", "")
            if "pdf" in ct.lower() or len(resp.content) > 500:
                return resp.content, False
            return None, False  # resposta inesperada mas definitiva
        if resp.status_code == 404:
            return None, False  # chave nao disponivel — definitivo
        # 429, 502, 503 ou qualquer outro erro transitorio
        return None, True
    except Exception:
        return None, True  # timeout / erro de rede — pode tentar de novo


def _baixar_pdfs_paralelo(
    cert_path: str,
    key_path: str,
    cnpj: str,
    tarefas: list[tuple],  # [(chave, nome_arquivo, xml_bytes), ...]
    log: list,
    log_lock: threading.Lock,
    log_cb=None,
) -> dict[str, bytes]:
    """Baixa PDFs com fila de retry compartilhada entre N workers.

    Quando um PDF falha, volta para a fila (outros workers continuam).
    Muito mais rapido que retry sequencial para muitas notas.
    """
    from queue import Queue, Empty

    resultados: dict[str, bytes] = {}
    res_lock   = threading.Lock()
    total      = len(tarefas)
    fila: Queue = Queue()

    # (indice_exibicao, chave, nome_arquivo, tentativas_restantes)
    for i, (chave, nome, _xml_b) in enumerate(tarefas):
        fila.put((i + 1, chave, nome, _PDF_MAX_TRIES))

    concluidos = [0]  # sucessos + falhas definitivas

    def worker():
        while True:
            try:
                idx, chave, nome, restantes = fila.get(timeout=20)
            except Empty:
                break

            deve_retry = False
            try:
                pdf, retry = _tentar_danfse(cert_path, key_path, cnpj, chave)
                tentativa_num = _PDF_MAX_TRIES - restantes + 1

                if pdf:
                    with res_lock:
                        resultados[nome] = pdf
                    with log_lock:
                        concluidos[0] += 1
                        pct = int(concluidos[0] / total * 100)
                        log.append(f"  [{pct:3d}%] PDF {idx}/{total}: OK ({len(pdf)//1024} KB) [{tentativa_num}t]")
                        try:
                            if log_cb: log_cb(log)
                        except Exception:
                            pass
                elif retry and restantes > 1:
                    deve_retry = True
                else:
                    with log_lock:
                        concluidos[0] += 1
                        pct = int(concluidos[0] / total * 100)
                        log.append(f"  [{pct:3d}%] PDF {idx}/{total}: falhou ({tentativa_num}t)")
                        try:
                            if log_cb: log_cb(log)
                        except Exception:
                            pass
            except Exception as exc:
                with log_lock:
                    log.append(f"  PDF {idx}/{total}: erro interno: {exc}")
            finally:
                # task_done SEMPRE chamado — evita fila.join() travar
                if deve_retry:
                    time.sleep(2)
                    fila.put((idx, chave, nome, restantes - 1))
                fila.task_done()

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(_PDF_WORKERS)]
    for t in threads:
        t.start()
    fila.join()
    return resultados


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
        log_lock = threading.Lock()

        # acumula todos os XMLs antes de baixar PDFs em paralelo
        # tupla: (chave, xml_bytes, chave_pdf, cancelada)
        xmls_aprovados: list[tuple[str, bytes, str, bool]] = []

        import defusedxml.ElementTree as _ET2

        while True:
            lote_num += 1
            log.append(f"Consultando lote a partir do NSU {nsu}...")
            if log_cb: log_cb(log)
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

                arquivo_b64 = doc.get("ArquivoXml")
                if not arquivo_b64:
                    # sem XML: documentos que não são NFS-e (ex: DPS sem NFSe) ignorar
                    if tipo_doc != "NFSE":
                        log.append(f"    -> tipo {tipo_doc} sem XML, ignorado")
                    else:
                        log.append(f"    -> sem ArquivoXml, ignorado")
                    continue

                chave = doc.get("ChaveAcesso") or str(nsu_doc)
                nome_arq = chave  # fallback: usa chave de acesso se XML não parsear
                try:
                    xml_bytes = _decodificar_xml(arquivo_b64)

                    try:
                        _root = _ET2.fromstring(xml_bytes)

                        # determina papel (tomados/prestados) para filtro e pasta
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
                            papel = "tomados"
                        elif tipo == "prestados":
                            if cnpj_prest and cnpj_prest != cnpj_uso:
                                log.append(f"    -> servico tomado (nao prestado), ignorado")
                                continue
                            papel = "prestados"
                        else:
                            # "todos" — classifica pela posicao do CNPJ no XML
                            if cnpj_prest and cnpj_prest == cnpj_uso:
                                papel = "prestados"
                            else:
                                papel = "tomados"

                        # filtro de data: usa dCompet do XML; se ausente (ex: evento de cancelamento)
                        # usa DataHoraGeracao da API como fallback
                        _el = next((e for e in _root.iter() if e.tag.endswith("dCompet")), None)
                        _data_filtro = (_el.text.strip()[:10] if _el is not None and _el.text else None) or data_str or None
                        if _data_filtro:
                            try:
                                data_compet = date.fromisoformat(_data_filtro)
                                compet_ym = (data_compet.year, data_compet.month)
                                ini_ym    = (data_ini.year,    data_ini.month)
                                fim_ym    = (data_fim.year,    data_fim.month)
                                if not (ini_ym <= compet_ym <= fim_ym):
                                    log.append(f"    -> competencia {data_compet.year}-{data_compet.month:02d} fora do periodo, ignorado")
                                    continue
                            except ValueError:
                                log.append(f"    -> data formato invalido '{_data_filtro}', incluido")

                        # extrai número da nota e nome do emitente para compor o nome do arquivo
                        _n_nfse = next(
                            (e.text.strip() for e in _root.iter() if e.tag.endswith("nNFSe") and e.text),
                            ""
                        )
                        _emit_el = next((e for e in _root.iter() if e.tag.endswith("emit")), None)
                        _x_nome  = ""
                        if _emit_el is not None:
                            _x_nome = next(
                                (e.text.strip() for e in _emit_el.iter() if e.tag.endswith("xNome") and e.text),
                                ""
                            )
                        nome_arq = _nome_arquivo(_n_nfse, _x_nome)

                    except Exception as parse_err:
                        log.append(f"    -> aviso parse XML: {parse_err}, incluido")

                    # detecta cancelamento: eventos não-NFSE com XML são sempre cancelamentos
                    cancelada = tipo_doc != "NFSE"
                    if not cancelada:
                        try:
                            cancelada = _is_cancelada(_root)
                        except Exception:
                            pass
                    if cancelada:
                        log.append(f"    -> CANCELADA")

                    # determina chave para PDF
                    chave_pdf = chave
                    if formato in ("pdf", "ambos"):
                        try:
                            _rx = _ET2.fromstring(xml_bytes)
                            for _tag in ("chNFSe", "cChaveNFSe", "chAcesso", "chaveAcesso"):
                                _el2 = next((e for e in _rx.iter() if e.tag.endswith(_tag)), None)
                                if _el2 is not None and _el2.text and len(_el2.text.strip()) >= 40:
                                    chave_pdf = _el2.text.strip()
                                    break
                        except Exception:
                            pass

                    xmls_aprovados.append((chave, xml_bytes, chave_pdf, cancelada, papel, nome_arq))
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
                progress_cb(min(lote_num / (lote_num + 3), 0.5))

        total_canc = sum(1 for _, _, _, c, _, _ in xmls_aprovados if c)
        log.append(f"  Total de NFS-e no periodo: {total_ok} ({total_canc} cancelada(s))")
        if log_cb: log_cb(log)

        # ── Monta ZIP ────────────────────────────────────────────────────────
        # Estrutura: cancelados/ | tomados/ | prestados/
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:

            if formato in ("xml", "ambos"):
                for chave, xml_bytes, _, cancelada, papel, nome_arq in xmls_aprovados:
                    if cancelada:
                        zf.writestr(f"cancelados/nfse_{nome_arq}_CANC.xml", xml_bytes)
                    else:
                        zf.writestr(f"{papel}/nfse_{nome_arq}.xml", xml_bytes)
                log.append(f"  {len(xmls_aprovados)} XMLs salvos ({total_canc} em cancelados/).")
                if log_cb: log_cb(log)

            if formato in ("pdf", "ambos") and xmls_aprovados:
                tarefas_pdf = [
                    (chave_pdf,
                     f"cancelados/nfse_{nome_arq}_CANC.pdf" if cancelada else f"{papel}/nfse_{nome_arq}.pdf",
                     xml_b)
                    for chave, xml_b, chave_pdf, cancelada, papel, nome_arq in xmls_aprovados
                ]
                log.append(f"  Baixando {len(tarefas_pdf)} PDFs via API DANFSe...")
                if log_cb: log_cb(log)

                pdfs = _baixar_pdfs_paralelo(cert_path, key_path, cnpj, tarefas_pdf, log, log_lock, log_cb)

                # ondas de rescue com contagem regressiva visivel
                _MAX_ONDAS   = 2
                _ESPERA_ONDA = 30
                for onda in range(1, _MAX_ONDAS + 1):
                    falhas = [(chave, nome, xml_b) for chave, nome, xml_b in tarefas_pdf if nome not in pdfs]
                    if not falhas:
                        break
                    # contagem regressiva: substitui a ultima linha do log a cada 3s
                    log.append("")
                    for seg in range(_ESPERA_ONDA, 0, -3):
                        log[-1] = f"  {len(falhas)} PDFs pendentes — proxima tentativa em {seg}s..."
                        if log_cb: log_cb(log)
                        if progress_cb: progress_cb(0.65 + 0.10 * onda)
                        time.sleep(min(3, seg))
                    log[-1] = f"  Onda {onda+1}/{_MAX_ONDAS+1}: retentando {len(falhas)} PDFs..."
                    if log_cb: log_cb(log)
                    pdfs2 = _baixar_pdfs_paralelo(cert_path, key_path, cnpj, falhas, log, log_lock, log_cb)
                    pdfs.update(pdfs2)

                for nome_pdf, pdf_bytes in pdfs.items():
                    zf.writestr(nome_pdf, pdf_bytes)
                log.append(f"  PDFs baixados: {len(pdfs)}/{len(tarefas_pdf)}")
                if log_cb: log_cb(log)
                if progress_cb:
                    progress_cb(0.95)

        if progress_cb:
            progress_cb(1.0)

        log.append(f"Concluido. {total_ok} NFS-e ({total_canc} cancelada(s)), {erros} erros.")
        buf.seek(0)
        return (buf.read() if total_ok > 0 else b""), log

    finally:
        for p in (cert_path, key_path):
            if p and os.path.exists(p):
                os.unlink(p)
