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
        listar_auto_sync_ativos, carregar_certificado, get_nsu_cnpj,
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

            # salvar_db=True: salva TODOS os docs diretamente no acervo (sem filtro de período)
            _zip, log_final = executar_consulta_sefaz(
                pfx_bytes=pfx_bytes,
                pfx_senha=pfx_senha,
                empresas=[{"cnpj": cnpj, "nome": cnpj}],
                ambiente="1",
                uf="CE",
                data_ini=None,
                data_fim=None,
                tipo_doc="ambos",
                papel_filtro="ambos",
                incluir_xml=False,
                incluir_pdf=False,
                incluir_excel=False,
                log_cb=coletar_log,
                progress_cb=None,
                salvar_db=True,
            )

        except Exception as e:
            _log(f"  [{cnpj}] ERRO na consulta: {e}")

        cnpjs_processados.add(cnpj)

    _log("=== NFE Scheduler concluído ===")


if __name__ == "__main__":
    main()
