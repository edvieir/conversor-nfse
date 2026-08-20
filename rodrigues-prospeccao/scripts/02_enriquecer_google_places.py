#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ENRIQUECIMENTO VIA GOOGLE PLACES API (OFICIAL)
Rodrigues Contabilidade

Para que serve:
    A base da Receita Federal tem CNPJ, Simples e porte - mas o telefone
    cadastrado costuma ser antigo ou fixo. Este script busca o telefone
    ATUAL de atendimento no Google, que e o numero que atende WhatsApp.

    Use como ETAPA 2, sobre a lista ja filtrada pelo script 01.
    Nao use como fonte primaria: o Google nao informa CNPJ nem regime.

Por que a API oficial e nao scraping:
    Scraping do Google Maps viola os Termos de Uso, quebra a cada mudanca
    de layout e bloqueia seu IP depois de algumas centenas de requisicoes.
    A API custa centavos por consulta, tem cota gratuita mensal e devolve
    JSON estruturado que nao quebra.

Como habilitar (10 minutos, uma unica vez):
    1. console.cloud.google.com -> criar projeto
    2. Ativar "Places API (New)"
    3. Criar credencial -> Chave de API
    4. Ativar faturamento (obrigatorio, mesmo dentro da cota gratuita)
    5. Confira o pricing atual antes de rodar em volume alto:
       https://developers.google.com/maps/billing-and-pricing/pricing
    6. Defina a chave no terminal:
         Linux/Mac:  export GOOGLE_MAPS_API_KEY="sua_chave"
         Windows:    set GOOGLE_MAPS_API_KEY=sua_chave

Uso:
    # Modo A - enriquecer a lista vinda da Receita Federal (recomendado)
    python 02_enriquecer_google_places.py --entrada leads_fortaleza.xlsx

    # Modo B - busca livre por termo (prospeccao exploratoria, sem CNPJ)
    python 02_enriquecer_google_places.py --busca "autopecas Fortaleza CE"

Requisitos: pip install requests pandas openpyxl
"""

import argparse
import os
import sys
import time

import pandas as pd
import requests

API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")
URL = "https://places.googleapis.com/v1/places:searchText"

CAMPOS = ",".join([
    "places.displayName",
    "places.formattedAddress",
    "places.nationalPhoneNumber",
    "places.websiteUri",
    "places.businessStatus",
    "nextPageToken",
])

PAUSA = 0.6  # segundos entre chamadas


def buscar(texto, max_paginas=3):
    """Executa uma busca textual e devolve a lista de resultados."""
    if not API_KEY:
        sys.exit("[ERRO] Defina a variavel de ambiente GOOGLE_MAPS_API_KEY.")

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": CAMPOS,
    }

    resultados, token, pagina = [], None, 0
    while pagina < max_paginas:
        corpo = {"textQuery": texto, "languageCode": "pt-BR", "regionCode": "BR"}
        if token:
            corpo["pageToken"] = token

        try:
            r = requests.post(URL, headers=headers, json=corpo, timeout=25)
        except requests.RequestException as e:
            print(f"    [rede] {e}")
            break

        if r.status_code != 200:
            print(f"    [HTTP {r.status_code}] {r.text[:180]}")
            break

        dados = r.json()
        resultados.extend(dados.get("places", []))
        token = dados.get("nextPageToken")
        pagina += 1
        if not token:
            break
        time.sleep(2)  # o token leva ~2s para ficar valido

    return resultados


def extrair_telefone(lugar):
    return (lugar.get("nationalPhoneNumber") or "").strip()


def para_whatsapp(telefone):
    digitos = "".join(filter(str.isdigit, telefone))
    if len(digitos) == 11 and digitos[2] == "9":
        return f"https://wa.me/55{digitos}"
    return ""


def modo_enriquecer(caminho):
    df = pd.read_excel(caminho) if caminho.endswith((".xlsx", ".xls")) \
        else pd.read_csv(caminho, sep=";")

    if "Tel_Google" not in df.columns:
        df["Tel_Google"] = ""
        df["Zap_Google"] = ""
        df["Site"] = ""
        df["Status_Google"] = ""

    for i, linha in df.iterrows():
        nome = str(linha.get("Nome_Fantasia") or linha.get("Razao_Social") or "").strip()
        bairro = str(linha.get("Bairro") or "").strip()
        if not nome:
            continue

        consulta = f"{nome} {bairro} Fortaleza CE".strip()
        print(f"[{i+1}/{len(df)}] {consulta}")

        achados = buscar(consulta, max_paginas=1)
        if achados:
            lugar = achados[0]
            tel = extrair_telefone(lugar)
            df.at[i, "Tel_Google"] = tel
            df.at[i, "Zap_Google"] = para_whatsapp(tel)
            df.at[i, "Site"] = lugar.get("websiteUri", "")
            df.at[i, "Status_Google"] = lugar.get("businessStatus", "")
        else:
            df.at[i, "Status_Google"] = "NAO_ENCONTRADO"

        time.sleep(PAUSA)

        if (i + 1) % 25 == 0:  # salva parcial, para nao perder trabalho
            df.to_excel("saidas/leads_enriquecidos.xlsx", index=False)

    df.to_excel("saidas/leads_enriquecidos.xlsx", index=False)
    print(f"\nPronto: leads_enriquecidos.xlsx")
    print(f"Telefones do Google preenchidos: {(df['Tel_Google'] != '').sum()}")


def modo_busca(termo):
    achados = buscar(termo, max_paginas=3)
    linhas = []
    for lugar in achados:
        tel = extrair_telefone(lugar)
        linhas.append({
            "Empresa": lugar.get("displayName", {}).get("text", ""),
            "Endereco": lugar.get("formattedAddress", ""),
            "Telefone": tel,
            "WhatsApp": para_whatsapp(tel),
            "Site": lugar.get("websiteUri", ""),
            "Status": lugar.get("businessStatus", ""),
        })

    df = pd.DataFrame(linhas)
    saida = "saidas/busca_google.xlsx"
    df.to_excel(saida, index=False)
    print(f"{len(df)} resultados -> {saida}")
    print("\nATENCAO: esta lista NAO tem CNPJ nem confirmacao de Simples "
          "Nacional. Cruze com o script 01 antes de disparar script.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--entrada", help="arquivo de leads gerado pelo script 01")
    p.add_argument("--busca", help="termo de busca livre")
    args = p.parse_args()

    if args.entrada:
        modo_enriquecer(args.entrada)
    elif args.busca:
        modo_busca(args.busca)
    else:
        p.print_help()
