#!/usr/bin/env python3
"""
core/siga_xml_worker.py — Processa a fila de XML avulso por chave de acesso.

Origem típica das chaves: relatório de índices de malha do SIGA (notas não
escrituradas). Busca o XML completo via consultar_chave_avulsa() (SEFAZ
Nacional), que tem limite de 20 consultas/hora POR CERTIFICADO -- por isso
este worker processa no máximo LIMITE_POR_HORA chaves por CNPJ a cada
execução.

Configuração cron (rodar a cada hora, como ubuntu no servidor):
  0 * * * * cd /home/ubuntu/conversor-nfse && /home/ubuntu/conversor-nfse/venv/bin/python core/siga_xml_worker.py >> /var/log/siga_xml_worker.log 2>&1
"""

import sys
import os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    for linha in _env_file.read_text().splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#") and "=" in linha:
            k, v = linha.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

LIMITE_POR_HORA = 20
SAIDA_DIR = Path(__file__).parent.parent / "data" / "siga_xml"


def _log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def _processar_cnpj(cnpj: str):
    from db.database import proximos_pendentes, marcar_fila_concluido, marcar_fila_erro, carregar_certificado
    from core.nfe_sefaz import consultar_chave_avulsa

    pendentes = proximos_pendentes(cnpj, LIMITE_POR_HORA)
    if not pendentes:
        return

    usuario = pendentes[0]["usuario"]
    cert = carregar_certificado(usuario, cnpj)
    if not cert:
        _log(f"  [{cnpj}] ERRO: certificado não encontrado para {usuario}. Marcando {len(pendentes)} item(ns) com erro.")
        for item in pendentes:
            marcar_fila_erro(item["id"], "certificado não encontrado")
        return

    pfx_bytes, pfx_senha = cert
    destino = SAIDA_DIR / cnpj
    destino.mkdir(parents=True, exist_ok=True)

    _log(f"  [{cnpj}] Processando {len(pendentes)} chave(s) pendente(s)...")
    for item in pendentes:
        chave = item["chave"]
        try:
            dados, erro = consultar_chave_avulsa(pfx_bytes, pfx_senha, cnpj, chave)
            if dados and dados.get("xml"):
                (destino / f"{chave}.xml").write_text(dados["xml"], encoding="utf-8")
                marcar_fila_concluido(item["id"])
                _log(f"    [{chave}] OK")
            else:
                marcar_fila_erro(item["id"], erro or "sem XML retornado")
                _log(f"    [{chave}] ERRO: {erro}")
        except Exception as e:
            marcar_fila_erro(item["id"], str(e))
            _log(f"    [{chave}] EXCEÇÃO: {e}")


def main():
    _log("=== SIGA XML Worker iniciado ===")

    from db.database import cnpjs_com_fila_pendente

    cnpjs = cnpjs_com_fila_pendente()
    if not cnpjs:
        _log("Fila vazia. Encerrando.")
        return

    _log(f"CNPJs com fila pendente: {len(cnpjs)}")
    for cnpj in cnpjs:
        try:
            _processar_cnpj(cnpj)
        except Exception as e:
            _log(f"  [{cnpj}] ERRO inesperado, pulando para o próximo: {e}")

    _log("=== SIGA XML Worker concluído ===")


if __name__ == "__main__":
    main()
