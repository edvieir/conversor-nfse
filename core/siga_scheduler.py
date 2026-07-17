#!/usr/bin/env python3
"""
core/siga_scheduler.py — Sincronização automática de relatórios do SIGA (SEFAZ-CE).

Percorre TODOS os certificados salvos em `certificados` (todos os usuários,
sem exigir opt-in) e baixa os relatórios configurados em DEFAULT_TIPOS para
o mês corrente. Sequencial por empresa (não paralelo) para não sobrecarregar
o servidor da SEFAZ. Um certificado com erro não interrompe os demais.

Dentro de cada empresa usa duas passadas: solicita todos os tipos primeiro,
depois espera/baixa -- assim o SIGA processa os relatórios em paralelo do
lado dele enquanto o script não fica bloqueado esperando um de cada vez.

Configuração cron (rodar como ubuntu no servidor):
  0 3 * * * cd /home/ubuntu/conversor-nfse && /home/ubuntu/conversor-nfse/venv/bin/python core/siga_scheduler.py >> /var/log/siga_scheduler.log 2>&1
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

# Cada "aba" é (nome_do_arquivo, filtros extras passados a solicitar_download).
ABAS = {
    "NF_E": [
        ("emitidas",   {"papel_operacao": "EMITENTE"}),
        ("recebidas",  {"papel_operacao": "DESTINATARIO"}),
        ("canceladas", {"papel_operacao": "EMITENTE", "resultado_processamento": "CANCELADA"}),
    ],
    "NFC_E": [
        ("emitidas", {"papel_operacao": "EMITENTE"}),
    ],
}
SAIDA_DIR = Path(__file__).parent.parent / "data" / "siga_downloads"


def _log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def _mes_corrente() -> str:
    return datetime.now().strftime("%Y-%m")


def _processar_empresa(usuario: str, cnpj: str, razao_social: str, periodo: str):
    from db.database import carregar_certificado
    from core import siga_sefaz

    cert = carregar_certificado(usuario, cnpj)
    if not cert:
        _log(f"  [{cnpj}] ERRO: certificado não encontrado para {usuario}.")
        return

    pfx_bytes, pfx_senha = cert
    sessao = siga_sefaz._sessao(pfx_bytes, pfx_senha)

    try:
        token_resp = siga_sefaz.login(sessao)
    except Exception as e:
        _log(f"  [{cnpj}] ERRO no login: {e}")
        return

    token = token_resp["access_token"]

    # 1ª passada: dispara a solicitação de cada aba (tipo x papel/resultado)
    pendentes = []  # (nome_arquivo, solicitacao_id)
    for tipo, abas in ABAS.items():
        for nome_aba, filtros in abas:
            try:
                solicitacao_id = siga_sefaz.solicitar_download(
                    sessao, token, cnpj, tipo, dat_referencia=[periodo], **filtros,
                )
                pendentes.append((f"{tipo}_{nome_aba}", solicitacao_id))
                _log(f"  [{cnpj}] {tipo} ({nome_aba}): solicitação {solicitacao_id} criada.")
            except Exception as e:
                _log(f"  [{cnpj}] ERRO ao solicitar {tipo} ({nome_aba}): {e}")

    # Índices de malha (pendências) -- só baixa se houver algo; senão fica em branco.
    try:
        indicadores = siga_sefaz.listar_indicadores_malha(sessao, token, cnpj)
        if indicadores:
            solicitacao_id = siga_sefaz.solicitar_download_indicadores(
                sessao, token, cnpj, dat_referencia=[periodo],
            )
            pendentes.append(("INDICADORES_MALHA_pendencias", solicitacao_id))
            _log(f"  [{cnpj}] Indicadores de malha: {len(indicadores)} pendência(s), solicitação {solicitacao_id} criada.")
        else:
            _log(f"  [{cnpj}] Indicadores de malha: sem pendências, nada a baixar.")
    except Exception as e:
        _log(f"  [{cnpj}] ERRO ao consultar indicadores de malha: {e}")

    if not pendentes:
        return

    # 2ª passada: espera cada uma concluir e baixa
    destino = SAIDA_DIR / cnpj
    destino.mkdir(parents=True, exist_ok=True)

    for nome_arquivo, solicitacao_id in pendentes:
        try:
            conteudo = siga_sefaz.aguardar_e_baixar(sessao, token, solicitacao_id)
            arquivo = destino / f"{nome_arquivo}_{periodo}.xlsx"
            arquivo.write_bytes(conteudo)
            _log(f"  [{cnpj}] {nome_arquivo}: salvo em {arquivo} ({len(conteudo)} bytes).")
        except Exception as e:
            _log(f"  [{cnpj}] ERRO ao baixar {nome_arquivo} (solicitação {solicitacao_id}): {e}")


def main():
    _log("=== SIGA Scheduler iniciado ===")

    from db.database import listar_todos_certificados

    certificados = listar_todos_certificados()
    if not certificados:
        _log("Nenhum certificado cadastrado. Encerrando.")
        return

    _log(f"Certificados encontrados: {len(certificados)}")
    periodo = _mes_corrente()

    cnpjs_processados: set[str] = set()

    for c in certificados:
        cnpj = c["cnpj"]
        if cnpj in cnpjs_processados:
            continue
        cnpjs_processados.add(cnpj)

        _log(f"[{cnpj}] {c.get('razao_social', '')} — iniciando (usuário: {c['usuario']})...")
        _processar_empresa(c["usuario"], cnpj, c.get("razao_social", ""), periodo)

    _log("=== SIGA Scheduler concluído ===")


if __name__ == "__main__":
    main()
