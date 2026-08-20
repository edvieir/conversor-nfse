#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EXTRATOR DE LEADS - BASE PUBLICA CNPJ / RECEITA FEDERAL
Rodrigues Contabilidade

O que faz:
    Le os arquivos publicos do CNPJ (Dados Abertos da RFB) e devolve uma lista
    de empresas ATIVAS, no SIMPLES NACIONAL, porte ME ou EPP, no municipio e
    nos CNAEs que voce escolher - com CNPJ, razao social, nome fantasia,
    endereco, bairro, telefone e e-mail.

Por que essa base e nao o Google Maps:
    - E a fonte oficial. Tem CNPJ, porte e opcao pelo Simples: os 3 filtros
      que o Google Maps NAO tem.
    - E gratuita, publica e nao quebra quando o Google muda o layout do site.
    - Scraping do Google Maps viola os Termos de Uso e derruba seu IP em
      poucas centenas de requisicoes.

PASSO 1 - BAIXAR OS ARQUIVOS
    Acesse: https://dadosabertos.rfb.gov.br/CNPJ/
    Entre na pasta da competencia mais recente (ex.: 2026-07/) e baixe:
        Empresas0.zip ... Empresas9.zip          (~1.5 GB no total)
        Estabelecimentos0.zip ... Estabelecimentos9.zip  (~5 GB no total)
        Simples.zip                              (~250 MB)
        Municipios.zip                           (alguns KB)
        Cnaes.zip                                (alguns KB)
    Descompacte TUDO dentro da pasta definida em PASTA_DADOS abaixo.
    Os arquivos saem sem extensao (.EMPRECSV, .ESTABELE, .SIMPLES etc).
    O script encontra sozinho.

PASSO 2 - AJUSTAR A CONFIGURACAO ABAIXO

PASSO 3 - RODAR
    python 01_extrator_receita_federal.py

Requisitos: pandas  ->  pip install pandas openpyxl
Tempo de execucao: 10 a 25 minutos (le ~20 GB em blocos, usa pouca RAM).
"""

import glob
import os
import sys
import unicodedata

import pandas as pd

# =============================================================================
# CONFIGURACAO - EDITE APENAS ESTE BLOCO
# =============================================================================

PASTA_DADOS = r"dados_rfb"          # onde voce descompactou os arquivos
ARQUIVO_SAIDA = "saidas/leads_fortaleza.xlsx"

UF_ALVO = "CE"
MUNICIPIO_ALVO = "FORTALEZA"           # o script converte para o codigo da RFB

# Empresa aberta ha no minimo / no maximo X meses (None = sem limite).
# Use IDADE_MAX_MESES = 12 para prospectar so empresas recem-abertas.
IDADE_MIN_MESES = None
IDADE_MAX_MESES = None

# CNAEs alvo. Formato: 7 digitos, sem ponto, sem barra, sem traco.
# Comente/descomente conforme a cunha que voce escolheu no mes.
CNAES_ALVO = {
    # --- CUNHA A: MONOFASICO (comercio) ---
    "4530703": "Autopecas - varejo",
    "4530705": "Pneus e camaras de ar - varejo",
    "4530701": "Autopecas - atacado",
    "4635402": "Bebidas - atacado (cerveja/chope/refrigerante)",
    "4723700": "Bebidas - varejo",
    "4772500": "Cosmeticos, perfumaria e higiene pessoal",
    "4771701": "Farmacia sem manipulacao",
    "4771702": "Farmacia com manipulacao",
    "4712100": "Minimercado / mercearia / armazem",
    "4731800": "Combustiveis - varejo",
    "4732600": "Lubrificantes - varejo",

    # --- CUNHA B: FATOR R (servicos) - descomente para usar ---
    # "8630504": "Clinica odontologica",
    # "8650004": "Fisioterapia",
    # "9602501": "Salao de beleza / estetica",
    # "9313100": "Academia / condicionamento fisico",
    # "6201501": "Desenvolvimento de software sob encomenda",
    # "7020400": "Consultoria em gestao empresarial",
    # "7311400": "Agencia de publicidade",
    # "8630501": "Clinica medica",
}

# Porte: 01 = ME, 03 = EPP, 05 = Demais, 00 = nao informado
PORTES_ALVO = {"01", "03"}

# Situacao cadastral: 02 = ATIVA (nunca mude isso)
SITUACAO_ALVO = "02"

# Exigir opcao ativa pelo Simples Nacional
EXIGIR_SIMPLES = True

# Excluir MEI (MEI nao interessa: nao tem folha, nao tem escrituracao)
EXCLUIR_MEI = True

# Exigir telefone preenchido
EXIGIR_TELEFONE = True

CHUNK = 300_000  # linhas por bloco de leitura. Baixe para 100_000 se faltar RAM.

# =============================================================================
# LAYOUTS OFICIAIS DOS ARQUIVOS (nao mexa)
# =============================================================================

COLS_EMPRESAS = [
    "cnpj_basico", "razao_social", "natureza_juridica",
    "qualificacao_responsavel", "capital_social", "porte", "ente_federativo",
]

COLS_ESTABELECIMENTOS = [
    "cnpj_basico", "cnpj_ordem", "cnpj_dv", "matriz_filial", "nome_fantasia",
    "situacao_cadastral", "data_situacao_cadastral", "motivo_situacao",
    "cidade_exterior", "pais", "data_inicio_atividade", "cnae_principal",
    "cnae_secundaria", "tipo_logradouro", "logradouro", "numero",
    "complemento", "bairro", "cep", "uf", "municipio", "ddd1", "telefone1",
    "ddd2", "telefone2", "ddd_fax", "fax", "email", "situacao_especial",
    "data_situacao_especial",
]

COLS_SIMPLES = [
    "cnpj_basico", "opcao_simples", "data_opcao_simples",
    "data_exclusao_simples", "opcao_mei", "data_opcao_mei",
    "data_exclusao_mei",
]

COLS_MUNICIPIOS = ["codigo", "descricao"]

LEITURA = dict(sep=";", encoding="latin-1", dtype=str, header=None,
               quotechar='"', on_bad_lines="skip")


# =============================================================================
# FUNCOES AUXILIARES
# =============================================================================

def normalizar(texto):
    """Remove acentos e coloca em maiusculas, para comparar nomes de cidade."""
    if not isinstance(texto, str):
        return ""
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return sem_acento.upper().strip()


def achar_arquivos(padroes):
    """Encontra os arquivos da RFB independente da extensao usada."""
    encontrados = []
    for padrao in padroes:
        encontrados += glob.glob(os.path.join(PASTA_DADOS, padrao))
    return sorted(set(encontrados))


def formatar_cnpj(basico, ordem, dv):
    return f"{basico[:2]}.{basico[2:5]}.{basico[5:8]}/{ordem}-{dv}"


def montar_telefone(ddd, numero):
    ddd = (ddd or "").strip()
    numero = (numero or "").strip()
    if not ddd or not numero:
        return ""
    return f"({ddd}) {numero}"


def link_whatsapp(ddd, numero):
    ddd = "".join(filter(str.isdigit, ddd or ""))
    numero = "".join(filter(str.isdigit, numero or ""))
    if not ddd or len(numero) < 8:
        return ""
    # Celular no Brasil tem 9 digitos. Fixo (8 digitos) nao tem WhatsApp.
    if len(numero) != 9:
        return ""
    return f"https://wa.me/55{ddd}{numero}"


# =============================================================================
# ETAPA 1 - DESCOBRIR O CODIGO DO MUNICIPIO
# =============================================================================

def obter_codigo_municipio():
    arquivos = achar_arquivos(["*MUNIC*", "*Munic*", "*municipio*"])
    if not arquivos:
        sys.exit(f"[ERRO] Arquivo de Municipios nao encontrado em {PASTA_DADOS}")

    df = pd.read_csv(arquivos[0], names=COLS_MUNICIPIOS, **LEITURA)
    df["norm"] = df["descricao"].map(normalizar)
    alvo = normalizar(MUNICIPIO_ALVO)
    achado = df[df["norm"] == alvo]

    if achado.empty:
        sys.exit(f"[ERRO] Municipio '{MUNICIPIO_ALVO}' nao encontrado.")

    codigo = achado.iloc[0]["codigo"]
    print(f"[1/5] Municipio {MUNICIPIO_ALVO} = codigo RFB {codigo}")
    return codigo


# =============================================================================
# ETAPA 2 - CARREGAR OPTANTES DO SIMPLES
# =============================================================================

def carregar_simples():
    if not EXIGIR_SIMPLES:
        return None, set()

    arquivos = achar_arquivos(["*SIMPLES*", "*Simples*"])
    if not arquivos:
        sys.exit(f"[ERRO] Arquivo Simples nao encontrado em {PASTA_DADOS}")

    optantes, meis = set(), set()
    for arq in arquivos:
        for bloco in pd.read_csv(arq, names=COLS_SIMPLES, chunksize=CHUNK, **LEITURA):
            sim = bloco[bloco["opcao_simples"] == "S"]
            # data_exclusao 0 ou vazia = ainda optante
            sim = sim[sim["data_exclusao_simples"].isin(["0", "00000000", "", None])
                      | sim["data_exclusao_simples"].isna()]
            optantes.update(sim["cnpj_basico"])

            if EXCLUIR_MEI:
                mei = bloco[bloco["opcao_mei"] == "S"]
                mei = mei[mei["data_exclusao_mei"].isin(["0", "00000000", "", None])
                          | mei["data_exclusao_mei"].isna()]
                meis.update(mei["cnpj_basico"])

    print(f"[2/5] Optantes do Simples: {len(optantes):,} | MEIs a excluir: {len(meis):,}")
    return optantes, meis


# =============================================================================
# ETAPA 3 - CARREGAR EMPRESAS ME/EPP
# =============================================================================

def carregar_empresas():
    arquivos = achar_arquivos(["*EMPRE*", "*Empre*"])
    if not arquivos:
        sys.exit(f"[ERRO] Arquivos de Empresas nao encontrados em {PASTA_DADOS}")

    mapa = {}
    for arq in arquivos:
        for bloco in pd.read_csv(arq, names=COLS_EMPRESAS, chunksize=CHUNK, **LEITURA):
            filtrado = bloco[bloco["porte"].isin(PORTES_ALVO)]
            for basico, razao, porte in zip(filtrado["cnpj_basico"],
                                            filtrado["razao_social"],
                                            filtrado["porte"]):
                mapa[basico] = (razao, "ME" if porte == "01" else "EPP")

    print(f"[3/5] Empresas ME/EPP no pais: {len(mapa):,}")
    return mapa


# =============================================================================
# ETAPA 4 - VARRER ESTABELECIMENTOS E FILTRAR
# =============================================================================

def varrer_estabelecimentos(cod_municipio, optantes, meis, empresas):
    arquivos = achar_arquivos(["*ESTABELE*", "*Estabele*"])
    if not arquivos:
        sys.exit(f"[ERRO] Arquivos de Estabelecimentos nao encontrados em {PASTA_DADOS}")

    hoje = pd.Timestamp.today().normalize()
    leads = []

    for i, arq in enumerate(arquivos, 1):
        print(f"[4/5] Lendo {os.path.basename(arq)} ({i}/{len(arquivos)})...")
        for bloco in pd.read_csv(arq, names=COLS_ESTABELECIMENTOS,
                                 chunksize=CHUNK, **LEITURA):

            b = bloco[
                (bloco["uf"] == UF_ALVO)
                & (bloco["municipio"] == cod_municipio)
                & (bloco["situacao_cadastral"] == SITUACAO_ALVO)
                & (bloco["cnae_principal"].isin(CNAES_ALVO.keys()))
            ]
            if b.empty:
                continue

            b = b[b["cnpj_basico"].isin(empresas.keys())]
            if EXIGIR_SIMPLES and optantes is not None:
                b = b[b["cnpj_basico"].isin(optantes)]
            if EXCLUIR_MEI and meis:
                b = b[~b["cnpj_basico"].isin(meis)]
            if b.empty:
                continue

            for r in b.itertuples(index=False):
                tel = montar_telefone(r.ddd1, r.telefone1)
                if not tel:
                    tel = montar_telefone(r.ddd2, r.telefone2)
                if EXIGIR_TELEFONE and not tel:
                    continue

                zap = link_whatsapp(r.ddd1, r.telefone1) or \
                    link_whatsapp(r.ddd2, r.telefone2)

                abertura = pd.to_datetime(r.data_inicio_atividade,
                                          format="%Y%m%d", errors="coerce")
                if pd.isna(abertura):
                    idade = None
                else:
                    idade = (hoje.year - abertura.year) * 12 + \
                        (hoje.month - abertura.month)
                    if IDADE_MIN_MESES is not None and idade < IDADE_MIN_MESES:
                        continue
                    if IDADE_MAX_MESES is not None and idade > IDADE_MAX_MESES:
                        continue

                razao, porte = empresas[r.cnpj_basico]
                endereco = " ".join(x for x in [r.tipo_logradouro, r.logradouro,
                                                r.numero] if x).strip()

                leads.append({
                    "CNPJ": formatar_cnpj(r.cnpj_basico, r.cnpj_ordem, r.cnpj_dv),
                    "Razao_Social": razao,
                    "Nome_Fantasia": (r.nome_fantasia or "").strip(),
                    "Segmento": CNAES_ALVO.get(r.cnae_principal, ""),
                    "CNAE": r.cnae_principal,
                    "Porte": porte,
                    "Bairro": (r.bairro or "").strip().title(),
                    "Endereco": endereco.title(),
                    "CEP": r.cep,
                    "Telefone": tel,
                    "WhatsApp": zap,
                    "Email": (r.email or "").strip().lower(),
                    "Data_Abertura": abertura.strftime("%d/%m/%Y")
                    if pd.notna(abertura) else "",
                    "Idade_Meses": idade if idade is not None else "",
                })

    return pd.DataFrame(leads)


# =============================================================================
# ETAPA 5 - EXPORTAR
# =============================================================================

def exportar(df):
    if df.empty:
        print("\n[AVISO] Nenhum lead encontrado. Revise CNAES_ALVO e MUNICIPIO_ALVO.")
        return

    df = df.drop_duplicates(subset=["CNPJ"])
    # Prioriza quem tem celular (WhatsApp), depois ordena por bairro
    df["_tem_zap"] = df["WhatsApp"].ne("").astype(int)
    df = df.sort_values(["_tem_zap", "Bairro", "Razao_Social"],
                        ascending=[False, True, True]).drop(columns="_tem_zap")

    df.to_excel(ARQUIVO_SAIDA, index=False)
    df.to_csv(ARQUIVO_SAIDA.replace(".xlsx", ".csv"), index=False,
              sep=";", encoding="utf-8-sig")

    print(f"\n[5/5] {len(df):,} leads exportados para {ARQUIVO_SAIDA}")
    print(f"       Com WhatsApp (celular): {(df['WhatsApp'] != '').sum():,}")
    print("\nPor segmento:")
    print(df["Segmento"].value_counts().to_string())
    print("\nTop 15 bairros:")
    print(df["Bairro"].value_counts().head(15).to_string())


def main():
    if not os.path.isdir(PASTA_DADOS):
        sys.exit(f"[ERRO] Pasta '{PASTA_DADOS}' nao existe. "
                 "Baixe e descompacte os arquivos da RFB antes de rodar.")

    cod = obter_codigo_municipio()
    optantes, meis = carregar_simples()
    empresas = carregar_empresas()
    df = varrer_estabelecimentos(cod, optantes, meis, empresas)
    exportar(df)


if __name__ == "__main__":
    main()
