#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BAIXADOR AUTOMATICO DA BASE CNPJ - RECEITA FEDERAL
Rodrigues Contabilidade

Roda sozinho. Descobre a competencia mais recente, baixa os arquivos
necessarios, descompacta e organiza na pasta ./dados_rfb.

Uso:
    pip install requests
    python 00_baixar_base.py

Pode interromper (Ctrl+C) e rodar de novo: ele RETOMA de onde parou,
nao baixa novamente o que ja esta completo.

Tempo: 30 a 90 minutos, dependendo da sua internet (~7 GB).
Espaco em disco necessario: ~30 GB livres.
Rode uma vez por mes - a Receita atualiza mensalmente.
"""

import os
import re
import shutil
import sys
import time
import zipfile

import requests

PASTA = "dados_rfb"
BASE = "https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/"
ESPELHO = "https://dadosabertos.rfb.gov.br/CNPJ/"

# Arquivos necessarios para o extrator funcionar
NECESSARIOS = (
    [f"Empresas{i}.zip" for i in range(10)]
    + [f"Estabelecimentos{i}.zip" for i in range(10)]
    + ["Simples.zip", "Municipios.zip", "Cnaes.zip"]
)

HEADERS = {"User-Agent": "Mozilla/5.0 (compativel; leitor-dados-abertos)"}


def descobrir_competencia(base):
    """Le o indice e devolve a pasta AAAA-MM mais recente."""
    r = requests.get(base, headers=HEADERS, timeout=60)
    r.raise_for_status()
    pastas = sorted(set(re.findall(r"(\d{4}-\d{2})/", r.text)))
    if not pastas:
        raise RuntimeError("Nenhuma competencia encontrada no indice.")
    return pastas[-1]


def resolver_url_base():
    """Tenta o dominio principal; se falhar, usa o espelho."""
    for base in (BASE, ESPELHO):
        try:
            comp = descobrir_competencia(base)
            print(f"Fonte: {base}")
            print(f"Competencia mais recente: {comp}\n")
            return f"{base}{comp}/"
        except Exception as e:
            print(f"  [falhou] {base} -> {e}")
    sys.exit("[ERRO] Nenhuma fonte acessivel. Tente novamente mais tarde.")


def formatar(bytes_):
    for u in ("B", "KB", "MB", "GB"):
        if bytes_ < 1024:
            return f"{bytes_:.1f} {u}"
        bytes_ /= 1024
    return f"{bytes_:.1f} TB"


def baixar(url, destino):
    """Download com retomada (HTTP Range) e barra de progresso."""
    ja = os.path.getsize(destino) if os.path.exists(destino) else 0

    cab = dict(HEADERS)
    if ja:
        cab["Range"] = f"bytes={ja}-"

    with requests.get(url, headers=cab, stream=True, timeout=120) as r:
        if r.status_code == 416:      # ja completo
            print("  ja completo")
            return True
        if r.status_code not in (200, 206):
            print(f"  [HTTP {r.status_code}]")
            return False

        total = int(r.headers.get("content-length", 0)) + ja
        modo = "ab" if r.status_code == 206 else "wb"
        if modo == "wb":
            ja = 0

        baixado, t0, ultimo = ja, time.time(), 0
        with open(destino, modo) as f:
            for pedaco in r.iter_content(chunk_size=1 << 20):
                f.write(pedaco)
                baixado += len(pedaco)
                agora = time.time()
                if agora - ultimo > 1:
                    pct = (baixado / total * 100) if total else 0
                    vel = (baixado - ja) / max(agora - t0, 0.1)
                    print(f"\r  {formatar(baixado)} / {formatar(total)} "
                          f"({pct:.1f}%)  {formatar(vel)}/s   ", end="")
                    ultimo = agora
        print()
    return True


def descompactar(caminho_zip, pasta):
    try:
        with zipfile.ZipFile(caminho_zip) as z:
            nomes = z.namelist()
            if all(os.path.exists(os.path.join(pasta, n)) for n in nomes):
                print("  ja descompactado")
                return True
            z.extractall(pasta)
            print(f"  descompactado: {', '.join(nomes)}")
        return True
    except zipfile.BadZipFile:
        print("  [ARQUIVO CORROMPIDO] apagando para baixar de novo")
        os.remove(caminho_zip)
        return False


def main():
    os.makedirs(PASTA, exist_ok=True)

    livre = shutil.disk_usage(PASTA).free
    print(f"Espaco livre: {formatar(livre)}")
    if livre < 30 * 1024**3:
        print("[AVISO] Recomendado 30 GB livres. Voce pode ficar sem espaco.\n")

    url_base = resolver_url_base()

    pendentes = []
    for i, arquivo in enumerate(NECESSARIOS, 1):
        print(f"[{i}/{len(NECESSARIOS)}] {arquivo}")
        destino = os.path.join(PASTA, arquivo)

        ok = False
        for tentativa in range(1, 4):
            try:
                if baixar(url_base + arquivo, destino) and \
                        descompactar(destino, PASTA):
                    ok = True
                    break
            except Exception as e:
                print(f"  [tentativa {tentativa}/3] {e}")
                time.sleep(5)

        if ok:
            os.remove(destino)   # libera espaco: o .zip nao e mais necessario
        else:
            pendentes.append(arquivo)
        print()

    print("=" * 60)
    if pendentes:
        print("Concluido COM PENDENCIAS. Rode de novo para retomar:")
        for p in pendentes:
            print(f"  - {p}")
    else:
        print("Base completa em ./dados_rfb")
        print("Proximo passo:  python 01_extrator_receita_federal.py")


if __name__ == "__main__":
    main()
