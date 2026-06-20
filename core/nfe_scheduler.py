#!/usr/bin/env python3
"""
core/nfe_scheduler.py — Sincronização automática de NF-e/NFC-e via SEFAZ.

Executado via cron a cada hora. Consulta todos os CNPJs com auto-sync ativo
cujo proxima_consulta já passou, baixa os documentos novos e persiste em
nfe_resultados. Não precisa de interação do usuário.

Configuração cron (rodar como ubuntu no servidor):
  0 * * * * cd /home/ubuntu/conversor-nfse && /home/ubuntu/conversor-nfse/venv/bin/python core/nfe_scheduler.py >> /var/log/nfe_scheduler.log 2>&1
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Garante que o projeto raiz está no path para importações
sys.path.insert(0, str(Path(__file__).parent.parent))

# Carrega .env se existir (desenvolvimento local)
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    for linha in _env_file.read_text().splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#") and "=" in linha:
            k, v = linha.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def _log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def _deve_sincronizar(proxima_consulta: str | None) -> bool:
    if not proxima_consulta:
        return True
    try:
        from datetime import datetime as _dt
        return _dt.fromisoformat(proxima_consulta) <= _dt.now()
    except Exception:
        return True


def main():
    _log("=== NFE Scheduler iniciado ===")

    from db.database import (
        listar_auto_sync_ativos, carregar_certificado,
        get_nsu_cnpj, salvar_resultados_nfe,
    )

    ativos = listar_auto_sync_ativos()
    if not ativos:
        _log("Nenhum CNPJ com auto-sync ativo. Encerrando.")
        return

    _log(f"CNPJs com auto-sync ativo: {len(ativos)}")

    # Deduplica CNPJs (pode haver múltiplos usuários para o mesmo CNPJ)
    cnpjs_processados: set[str] = set()

    for entrada in ativos:
        cnpj     = entrada["cnpj"]
        username = entrada["username"]

        if cnpj in cnpjs_processados:
            continue

        estado = get_nsu_cnpj(cnpj)
        proxima = estado.get("proxima_consulta")

        if not _deve_sincronizar(proxima):
            _log(f"  [{cnpj}] Bloqueado até {proxima} — pulando.")
            continue

        _log(f"  [{cnpj}] Iniciando sincronização (usuário: {username})...")

        resultado_cert = carregar_certificado(username, cnpj)
        if not resultado_cert:
            _log(f"  [{cnpj}] ERRO: certificado não encontrado para {username}.")
            continue

        pfx_bytes, pfx_senha = resultado_cert

        try:
            from core.nfe_sefaz import executar_consulta_sefaz

            docs_coletados: list[dict] = []

            def coletar_log(msg: str):
                _log(f"    {msg}")

            # Roda a consulta sem filtro de período nem de tipo/papel
            # para garantir que tudo seja capturado e persistido
            zip_bytes, log_final = executar_consulta_sefaz(
                pfx_bytes=pfx_bytes,
                pfx_senha=pfx_senha,
                empresas=[{"cnpj": cnpj, "nome": cnpj}],
                ambiente="1",
                uf="CE",
                data_ini=None,
                data_fim=None,
                tipo_doc="ambos",
                papel_filtro="ambos",
                incluir_xml=True,
                incluir_pdf=False,
                incluir_excel=False,
                log_cb=coletar_log,
                progress_cb=None,
            )

            # Extrai XMLs do ZIP e salva no DB via salvar_resultados_nfe
            if zip_bytes:
                import zipfile, io
                import xml.etree.ElementTree as ET

                NS_NFE = "http://www.portalfiscal.inf.br/nfe"

                def _texto(el):
                    return el.text.strip() if el is not None and el.text else ""

                docs_para_salvar = []
                with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                    for nome in zf.namelist():
                        if not nome.endswith(".xml"):
                            continue
                        xml_str = zf.read(nome).decode("utf-8", errors="replace")
                        try:
                            root = ET.fromstring(xml_str)
                            ns   = {"n": NS_NFE}
                            inf  = root.find(".//n:infNFe", ns)
                            ide  = root.find(".//n:ide", ns)
                            emit = root.find(".//n:emit", ns)
                            dest = root.find(".//n:dest", ns)
                            vNF  = root.find(".//n:vNF", ns)
                            chave = (inf.get("Id", "") if inf else "").replace("NFe", "").replace("NFCe", "")
                            cnpj_emit = _texto(emit.find("n:CNPJ", ns)) if emit else ""
                            mod_el = ide.find("n:mod", ns) if ide else None
                            modelo = "NFC-e" if _texto(mod_el) == "65" else "NF-e"
                            papel  = "Emitida" if cnpj_emit == cnpj else "Recebida"
                            dt_emi = (_texto(ide.find("n:dhEmi", ns)) or _texto(ide.find("n:dEmi", ns)))[:10] if ide else ""
                            docs_para_salvar.append({
                                "cnpj_empresa":   cnpj,
                                "chave":          chave,
                                "modelo":         modelo,
                                "papel":          papel,
                                "numero":         _texto(ide.find("n:nNF", ns)) if ide else "",
                                "serie":          _texto(ide.find("n:serie", ns)) if ide else "",
                                "data_emissao":   dt_emi,
                                "cnpj_emitente":  cnpj_emit,
                                "nome_emitente":  _texto(emit.find("n:xNome", ns)) if emit else "",
                                "cnpj_dest_doc":  _texto(dest.find("n:CNPJ", ns)) if dest else "",
                                "nome_dest_doc":  _texto(dest.find("n:xNome", ns)) if dest else "",
                                "valor_total":    float(vNF.text or 0) if vNF else 0.0,
                                "nat_operacao":   _texto(ide.find("n:natOp", ns)) if ide else "",
                                "xml":            xml_str,
                            })
                        except Exception as e_xml:
                            _log(f"    AVISO: erro ao parsear XML {nome}: {e_xml}")

                if docs_para_salvar:
                    salvar_resultados_nfe(docs_para_salvar, baixado_por="auto")
                    _log(f"  [{cnpj}] {len(docs_para_salvar)} documento(s) persistido(s) no acervo.")
                else:
                    _log(f"  [{cnpj}] Nenhum documento novo.")
            else:
                _log(f"  [{cnpj}] Nenhum documento novo retornado pela SEFAZ.")

        except Exception as e:
            _log(f"  [{cnpj}] ERRO na consulta: {e}")

        cnpjs_processados.add(cnpj)

    _log("=== NFE Scheduler concluído ===")


if __name__ == "__main__":
    main()
