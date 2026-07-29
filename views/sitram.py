"""views/sitram.py — Integração SITRAM (Sistema de Trânsito de Mercadorias)"""
import io
import time

import pandas as pd
import streamlit as st

from auth.security import current_user
from db.database import listar_certificados, carregar_certificado
from views import nav


# ── Constantes ───────────────────────────────────────────────────────────────

UF_SIGLAS = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA",
    "16": "AP", "17": "TO", "21": "MA", "22": "PI", "23": "CE",
    "24": "RN", "25": "PB", "26": "PE", "27": "AL", "28": "SE",
    "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP",
    "41": "PR", "42": "SC", "43": "RS", "50": "MS", "51": "MT",
    "52": "GO", "53": "DF",
}

UFS_SUL_SUDESTE = {"31", "32", "33", "35", "41", "42", "43"}

ALIQ_INTERNA_CE = 20.0

SITRAM_PORTAL = "https://portal-sitram.sefaz.ce.gov.br/sitram-internet"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _fmt_cnpj(c: str) -> str:
    c = (c or "").strip().zfill(14)
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"


def _uf_origem(chave: str) -> str:
    return UF_SIGLAS.get(chave[:2], "??")


def _aliq_inter_padrao(chave: str, cst_a: str = "0") -> float:
    if cst_a in ("1", "2", "3", "8"):
        return 4.0
    return 7.0 if chave[:2] in UFS_SUL_SUDESTE else 12.0


def _classificar_tipo(nome_config: str) -> str:
    nome = (nome_config or "").upper()
    if "ANTECIPADO" in nome or "ANTC" in nome:
        return "ANTECIPADO"
    if "DIFAL" in nome:
        return "DIFAL"
    if "SUBSTITUICAO" in nome or "SUBST" in nome or " ST" in nome:
        return "ST"
    if "CONVENIO" in nome or "CONVÊNIO" in nome:
        return "CONVENIO"
    return "OUTRO"


def _alertas_item(item: dict, regime_empresa: str) -> list[str]:
    alertas = []
    cfop = item.get("cfop", "")
    tipo = _classificar_tipo(item.get("nomeConfiguracao", ""))
    cst_b = item.get("codigoCSTB", "")
    icms = item.get("icms", 0)

    if cfop in ("6556", "6557", "6551", "6552", "6553", "6554"):
        if tipo in ("ANTECIPADO", "ST"):
            alertas.append(
                f"CFOP {cfop} indica uso/consumo ou ativo imobilizado "
                f"mas SITRAM cobrou como {tipo} — deveria ser DIFAL"
            )

    if cst_b in ("40", "41", "50") and icms > 0:
        alertas.append(
            f"CST {cst_b} (isento/não tributado) mas SITRAM cobrou "
            f"ICMS R$ {icms:,.2f}"
        )

    if cst_b == "60" and tipo == "ANTECIPADO":
        alertas.append(
            "CST 60 indica ICMS já recolhido por ST anterior — "
            "verificar se antecipado é devido"
        )

    if regime_empresa == "simples" and tipo == "ST":
        alertas.append(
            "Empresa do Simples Nacional — verificar se há "
            "convênio/protocolo que isente de ST para este NCM"
        )

    if item.get("valorIcmsDestacado", 0) == 0 and icms > 0 and tipo == "ANTECIPADO":
        alertas.append(
            "ICMS destacado na NF-e = R$ 0,00 mas há cobrança antecipada — "
            "verificar se o emitente é isento ou optante SN"
        )

    return alertas


def _aliq_inter_uf(aliq_item: float) -> float:
    """Alíquota interestadual padrão da UF (usada no crédito de frete).
    Se o item usa 4% (importado), a UF de origem ainda cobra 7% ou 12%
    sobre o frete. Retorna a aliq da UF (não a do produto)."""
    if aliq_item == 4.0:
        return 7.0
    return aliq_item


def _link_sitram_pagamento(chave: str) -> str:
    return (
        f"{SITRAM_PORTAL}/#/pagamento-icms/detalhes-lancamentos"
        f"?sistema=10&filtradoPor=1&numeroDanfe={chave}"
    )


def _extrair_chaves(texto: str) -> list[str]:
    """Extrai chaves de 44 dígitos de um texto (uma por linha)."""
    chaves = []
    for linha in texto.strip().splitlines():
        digitos = "".join(c for c in linha if c.isdigit())
        if len(digitos) == 44:
            chaves.append(digitos)
    return chaves


def _consultar_itens_single(user: dict, cnpj: str, chave: str):
    """Consulta itens para uma única chave. Retorna (itens, erro)."""
    resultado_cert = carregar_certificado(user["username"], cnpj)
    if not resultado_cert:
        return None, "Certificado digital não encontrado."

    from core.sitram_sefaz import _sessao, consultar_itens_por_chave
    sessao = _sessao(resultado_cert[0], resultado_cert[1])

    try:
        resultado = consultar_itens_por_chave(sessao, chave)
    except Exception as e:
        return None, str(e)

    itens = resultado.get("content", [])
    return (itens, None) if itens else (None, "Nenhum item encontrado.")


def _consultar_itens_lote(user: dict, cnpj: str, chaves: list[str], progress_cb=None):
    """Consulta itens para múltiplas chaves. Retorna dict {chave: itens_ou_erro}."""
    resultado_cert = carregar_certificado(user["username"], cnpj)
    if not resultado_cert:
        return {}

    from core.sitram_sefaz import _sessao, consultar_itens_por_chave
    sessao = _sessao(resultado_cert[0], resultado_cert[1])

    resultados = {}
    for i, chave in enumerate(chaves):
        try:
            resultado = consultar_itens_por_chave(sessao, chave)
            itens = resultado.get("content", [])
            resultados[chave] = itens if itens else "Nenhum item encontrado"
        except Exception as e:
            resultados[chave] = str(e)

        if progress_cb:
            progress_cb((i + 1) / len(chaves))

        if i < len(chaves) - 1:
            time.sleep(0.3)

    return resultados


def _itens_to_dataframe(itens: list[dict], chave: str = "") -> pd.DataFrame:
    """Converte lista de itens SITRAM em DataFrame."""
    rows = []
    for item in itens:
        tipo = _classificar_tipo(item.get("nomeConfiguracao", ""))
        rows.append({
            "Chave": chave[-10:] + "..." if chave else "",
            "Produto": item.get("descricaoProduto", "?"),
            "NCM": item.get("ncm", ""),
            "CFOP": item.get("cfop", ""),
            "Tipo": tipo,
            "Qtd": item.get("quantidade", 0),
            "Valor Unit.": item.get("valorUnitario", 0),
            "Valor Total": item.get("valorTotal", 0),
            "BC ICMS": item.get("valorBc", 0),
            "Aliq. Inter.": item.get("valorAliquota", 0),
            "ICMS Dest.": item.get("valorIcmsDestacado", 0),
            "ICMS SITRAM": item.get("icms", 0),
            "FECOP": item.get("valorFecop", 0),
            "Regime": item.get("nomeConfiguracao", ""),
            "CST": f"{item.get('codigoCSTA', '')}/{item.get('codigoCSTB', '')}",
        })
    return pd.DataFrame(rows)


def _get_client(user: dict, cnpj: str):
    cache_key = f"_sitram_client_{cnpj}"
    client = st.session_state.get(cache_key)
    if client is not None:
        return client

    resultado = carregar_certificado(user["username"], cnpj)
    if not resultado:
        st.error("Certificado digital não encontrado para este CNPJ.")
        return None

    pfx_bytes, pfx_senha = resultado

    from core.sitram_sefaz import SitramClient
    client = SitramClient(pfx_bytes, pfx_senha)
    try:
        with st.spinner("Autenticando no SITRAM via certificado digital..."):
            client.autenticar()
    except Exception as e:
        st.error(f"Falha na autenticação SITRAM: {e}")
        return None

    st.session_state[cache_key] = client
    return client


# ── Tab 1: Consulta NF ──────────────────────────────────────────────────────

def _tab_consulta_nf(user: dict, cnpj: str):
    st.markdown("### Consulta de Nota Fiscal")
    st.caption(
        "Consulte notas fiscais no SITRAM por chave de acesso. "
        "Classifica itens por regime (Antecipado, DIFAL, ST) e exibe alertas."
    )

    regime_empresa = st.radio(
        "Regime tributário da empresa",
        ["normal", "simples"],
        format_func=lambda r: {"normal": "Regime Normal", "simples": "Simples Nacional"}[r],
        horizontal=True,
        key="sitram_regime",
    )

    modo = st.radio(
        "Modo de consulta",
        ["unica", "lote"],
        format_func=lambda m: {"unica": "Chave única", "lote": "Lote (múltiplas chaves)"}[m],
        horizontal=True,
        key="sitram_modo_consulta",
    )

    if modo == "unica":
        _consulta_nf_unica(user, cnpj, regime_empresa)
    else:
        _consulta_nf_lote(user, cnpj, regime_empresa)


def _consulta_nf_unica(user: dict, cnpj: str, regime_empresa: str):
    chave = st.text_input(
        "Chave de acesso (44 dígitos)",
        max_chars=44,
        placeholder="Digite a chave de acesso da NF-e...",
        key="sitram_chave_nf",
    )

    if st.button("Consultar", type="primary", key="sitram_btn_consultar"):
        chave_limpa = "".join(c for c in chave if c.isdigit())
        if len(chave_limpa) != 44:
            st.warning("Informe uma chave de acesso válida com 44 dígitos.")
            return

        itens, erro = _consultar_itens_single(user, cnpj, chave_limpa)
        if erro:
            st.error(erro)
            return

        _exibir_resultado_consulta(itens, chave_limpa, regime_empresa)


def _consulta_nf_lote(user: dict, cnpj: str, regime_empresa: str):
    chaves_txt = st.text_area(
        "Chaves de acesso (uma por linha)",
        height=150,
        placeholder="Cole aqui as chaves de acesso, uma por linha...",
        key="sitram_chaves_lote",
    )

    uploaded = st.file_uploader(
        "Ou importe um arquivo CSV/Excel com coluna de chaves",
        type=["csv", "xlsx", "xls"],
        key="sitram_upload",
    )

    if uploaded:
        try:
            if uploaded.name.endswith(".csv"):
                df_upload = pd.read_csv(uploaded, dtype=str)
            else:
                df_upload = pd.read_excel(uploaded, dtype=str)
            col_chave = None
            for col in df_upload.columns:
                if "chave" in col.lower():
                    col_chave = col
                    break
            if not col_chave:
                col_chave = df_upload.columns[0]
            chaves_arquivo = _extrair_chaves("\n".join(df_upload[col_chave].dropna().tolist()))
            st.caption(f"{len(chaves_arquivo)} chave(s) encontrada(s) no arquivo (coluna: {col_chave})")
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")
            chaves_arquivo = []
    else:
        chaves_arquivo = []

    if st.button("Consultar Lote", type="primary", key="sitram_btn_lote"):
        chaves = _extrair_chaves(chaves_txt) if chaves_txt.strip() else []
        chaves.extend(chaves_arquivo)
        chaves = list(dict.fromkeys(chaves))

        if not chaves:
            st.warning("Nenhuma chave válida encontrada.")
            return

        st.info(f"Processando **{len(chaves)}** chave(s)...")
        progress = st.progress(0)

        resultados = _consultar_itens_lote(user, cnpj, chaves, progress_cb=progress.progress)
        progress.progress(100)

        todos_itens = []
        erros = []
        for chave, resultado in resultados.items():
            if isinstance(resultado, str):
                erros.append({"Chave": chave, "Erro": resultado})
            else:
                for item in resultado:
                    item["_chave"] = chave
                    todos_itens.append(item)

        if erros:
            st.warning(f"{len(erros)} chave(s) com erro")
            with st.expander("Ver erros"):
                st.dataframe(pd.DataFrame(erros), use_container_width=True, hide_index=True)

        if not todos_itens:
            st.error("Nenhum item encontrado nas chaves informadas.")
            return

        total_icms = sum(i.get("icms", 0) for i in todos_itens)
        total_fecop = sum(i.get("valorFecop", 0) for i in todos_itens)
        total_valor = sum(i.get("valorTotal", 0) for i in todos_itens)
        notas_ok = len(resultados) - len(erros)

        st.success(f"**{notas_ok} nota(s)** com **{len(todos_itens)} item(ns)**")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Notas", notas_ok)
        m2.metric("Total ICMS", f"R$ {total_icms:,.2f}")
        m3.metric("Total FECOP", f"R$ {total_fecop:,.2f}")
        m4.metric("Valor Total", f"R$ {total_valor:,.2f}")

        tipos = {}
        for item in todos_itens:
            t = _classificar_tipo(item.get("nomeConfiguracao", ""))
            tipos[t] = tipos.get(t, 0) + 1
        st.markdown("**Por tipo:** " + " | ".join(f"{t}: {n}" for t, n in tipos.items()))

        alertas_total = 0
        for item in todos_itens:
            alertas_total += len(_alertas_item(item, regime_empresa))
        if alertas_total:
            st.warning(f"**{alertas_total} alerta(s) de atenção** — verifique os itens.")

        df = _itens_to_dataframe(todos_itens)
        for item, row_idx in zip(todos_itens, range(len(todos_itens))):
            df.loc[row_idx, "Chave"] = item["_chave"]

        st.dataframe(df, use_container_width=True, hide_index=True)

        csv = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "Exportar CSV",
            data=csv,
            file_name="sitram_consulta_lote.csv",
            mime="text/csv",
        )


def _exibir_resultado_consulta(itens: list[dict], chave: str, regime_empresa: str):
    uf = _uf_origem(chave)
    aliq_inter = _aliq_inter_padrao(chave)
    st.info(f"UF Origem: **{uf}** | Aliq. interestadual presumida: **{aliq_inter}%**")

    total_icms = sum(i.get("icms", 0) for i in itens)
    total_fecop = sum(i.get("valorFecop", 0) for i in itens)
    total_valor = sum(i.get("valorTotal", 0) for i in itens)

    st.success(f"**{len(itens)} item(ns)** encontrado(s)")

    m1, m2, m3 = st.columns(3)
    m1.metric("Total ICMS", f"R$ {total_icms:,.2f}")
    m2.metric("Total FECOP", f"R$ {total_fecop:,.2f}")
    m3.metric("Valor Total NF", f"R$ {total_valor:,.2f}")

    tipos = {}
    for item in itens:
        t = _classificar_tipo(item.get("nomeConfiguracao", ""))
        tipos[t] = tipos.get(t, 0) + 1
    st.markdown("**Classificação:** " + " | ".join(f"{t}: {n}" for t, n in tipos.items()))

    total_alertas = 0
    for i, item in enumerate(itens, 1):
        tipo = _classificar_tipo(item.get("nomeConfiguracao", ""))
        icms = item.get("icms", 0)
        produto = item.get("descricaoProduto", "?")

        with st.expander(f"Item {i} | [{tipo}] {produto} — ICMS R$ {icms:,.2f}", expanded=(i == 1)):
            alertas = _alertas_item(item, regime_empresa)
            for alerta in alertas:
                st.warning(alerta)
            total_alertas += len(alertas)

            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**Produto:** {produto}")
                st.markdown(f"**NCM:** {item.get('ncm', '—')} | **CFOP:** {item.get('cfop', '—')}")
                st.markdown(
                    f"**Qtd:** {item.get('quantidade', '—')} {item.get('unidade', '')} "
                    f"x R$ {item.get('valorUnitario', 0):,.2f}"
                )
                st.markdown(f"**Valor Total:** R$ {item.get('valorTotal', 0):,.2f}")
            with c2:
                st.markdown(f"**ICMS Cobrado:** R$ {icms:,.2f}")
                st.markdown(f"**Base ICMS:** R$ {item.get('valorBc', 0):,.2f}")
                st.markdown(f"**Aliq. Interestadual:** {item.get('valorAliquota', 0)}%")
                st.markdown(f"**ICMS Destacado NF-e:** R$ {item.get('valorIcmsDestacado', 0):,.2f}")
                st.markdown(f"**FECOP:** R$ {item.get('valorFecop', 0):,.2f}")

            st.markdown(f"**Tipo:** {tipo} | **Regime:** {item.get('nomeConfiguracao', '—')}")
            st.markdown(
                f"**CST:** {item.get('codigoCSTA', '—')}/{item.get('codigoCSTB', '—')} | "
                f"**Cód. Produto:** {item.get('codigoProduto', '—')}"
            )

    if total_alertas:
        st.markdown("---")
        st.warning(f"**{total_alertas} alerta(s) de atenção** encontrado(s).")

    df = _itens_to_dataframe(itens, chave)
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("Exportar CSV", data=csv, file_name=f"sitram_{chave[-10:]}.csv", mime="text/csv")


# ── Tab 2: Conferência ──────────────────────────────────────────────────────

def _estimar_frete_item(item: dict, aliq_interna: float, aliq_inter_default: float) -> float:
    """Engenharia reversa: calcula o frete rateado que o SITRAM usou.
    ICMS = (valor + frete) × aliq_interna - (icms_dest + frete × aliq_uf)
    Resolvendo para frete:
      frete = (ICMS - valor × aliq_interna + icms_dest) / (aliq_interna - aliq_uf)
    """
    tipo = _classificar_tipo(item.get("nomeConfiguracao", ""))
    if tipo not in ("ANTECIPADO", "DIFAL", "ST"):
        return 0.0

    bc = item.get("valorBc", 0)
    icms_dest = item.get("valorIcmsDestacado", 0)
    icms_sitram = item.get("icms", 0)
    aliq_item = item.get("valorAliquota", 0)
    aliq_inter = aliq_item if aliq_item > 0 else aliq_inter_default
    aliq_uf = _aliq_inter_uf(aliq_inter)

    icms_sem_frete = bc * (aliq_interna / 100) - icms_dest
    diferenca = icms_sitram - icms_sem_frete

    divisor = (aliq_interna - aliq_uf) / 100
    if divisor <= 0 or diferenca <= 0.01:
        return 0.0

    return round(diferenca / divisor, 2)


def _tab_conferencia(user: dict, cnpj: str):
    st.markdown("### Conferência de Cálculo SITRAM")
    st.caption(
        "Confira se o ICMS calculado pelo SITRAM está correto. "
        "O frete (CT-e) rateado é estimado automaticamente a partir "
        "dos valores do SITRAM."
    )

    regime_empresa = st.radio(
        "Regime tributário da empresa",
        ["normal", "simples"],
        format_func=lambda r: {"normal": "Regime Normal", "simples": "Simples Nacional"}[r],
        horizontal=True,
        key="sitram_conf_regime",
    )

    aliq_interna = ALIQ_INTERNA_CE

    modo = st.radio(
        "Modo",
        ["unica", "lote"],
        format_func=lambda m: {"unica": "Chave única", "lote": "Lote (múltiplas chaves)"}[m],
        horizontal=True,
        key="sitram_conf_modo",
    )

    if modo == "unica":
        _conferencia_unica(user, cnpj, regime_empresa, aliq_interna)
    else:
        _conferencia_lote(user, cnpj, regime_empresa, aliq_interna)


def _conferencia_df(itens: list[dict], chave: str, aliq_interna: float,
                     regime_empresa: str) -> pd.DataFrame:
    aliq_inter_default = _aliq_inter_padrao(chave)

    rows = []
    for i, item in enumerate(itens, 1):
        tipo = _classificar_tipo(item.get("nomeConfiguracao", ""))
        bc = item.get("valorBc", 0)
        aliq_item = item.get("valorAliquota", 0)
        aliq_inter = aliq_item if aliq_item > 0 else aliq_inter_default
        aliq_uf = _aliq_inter_uf(aliq_inter)
        icms_sitram = item.get("icms", 0)
        icms_dest = item.get("valorIcmsDestacado", 0)

        frete_est = _estimar_frete_item(item, aliq_interna, aliq_inter_default)

        bc_total = bc + frete_est
        credito = icms_dest + (frete_est * aliq_uf / 100)
        icms_recalc = max(bc_total * (aliq_interna / 100) - credito, 0)
        diferenca = round(icms_sitram - icms_recalc, 2)

        rows.append({
            "Chave": chave[-10:] + "...",
            "Item": i,
            "Produto": item.get("descricaoProduto", "?")[:35],
            "Tipo": tipo,
            "BC Produto": bc,
            "Frete Est.": frete_est,
            "BC Total": round(bc_total, 2),
            "ICMS Dest.": icms_dest,
            "Créd.Origem": round(credito, 2),
            "Aliq.Inter.": f"{aliq_inter}%",
            "ICMS SITRAM": icms_sitram,
            "ICMS Recalc.": round(icms_recalc, 2),
            "Diferença": diferenca,
        })

    return pd.DataFrame(rows)


def _conferencia_unica(user: dict, cnpj: str, regime_empresa: str, aliq_interna: float):
    chave = st.text_input(
        "Chave de acesso (44 dígitos)",
        max_chars=44,
        placeholder="Digite a chave de acesso da NF-e...",
        key="sitram_conf_chave",
    )

    if st.button("Conferir", type="primary", key="sitram_btn_conferir"):
        chave_limpa = "".join(c for c in chave if c.isdigit())
        if len(chave_limpa) != 44:
            st.warning("Informe uma chave válida com 44 dígitos.")
            return

        itens, erro = _consultar_itens_single(user, cnpj, chave_limpa)
        if erro:
            st.error(erro)
            return

        uf = _uf_origem(chave_limpa)
        aliq_inter = _aliq_inter_padrao(chave_limpa)
        st.info(f"UF Origem: **{uf}** | Aliq. interestadual padrão UF: **{aliq_inter}%**")

        df = _conferencia_df(itens, chave_limpa, aliq_interna, regime_empresa)
        _exibir_conferencia(df, aliq_interna)


def _conferencia_lote(user: dict, cnpj: str, regime_empresa: str, aliq_interna: float):
    chaves_txt = st.text_area(
        "Chaves de acesso (uma por linha)",
        height=150,
        placeholder="Cole aqui as chaves, uma por linha...",
        key="sitram_conf_chaves_lote",
    )

    uploaded = st.file_uploader(
        "Ou importe um arquivo CSV/Excel",
        type=["csv", "xlsx", "xls"],
        key="sitram_conf_upload",
    )

    chaves_arquivo = []
    if uploaded:
        try:
            if uploaded.name.endswith(".csv"):
                df_up = pd.read_csv(uploaded, dtype=str)
            else:
                df_up = pd.read_excel(uploaded, dtype=str)
            col_chave = None
            for col in df_up.columns:
                if "chave" in col.lower():
                    col_chave = col
                    break
            if not col_chave:
                col_chave = df_up.columns[0]
            chaves_arquivo = _extrair_chaves("\n".join(df_up[col_chave].dropna().tolist()))
            st.caption(f"{len(chaves_arquivo)} chave(s) do arquivo")
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")

    if st.button("Conferir Lote", type="primary", key="sitram_btn_conf_lote"):
        chaves = _extrair_chaves(chaves_txt) if chaves_txt.strip() else []
        chaves.extend(chaves_arquivo)
        chaves = list(dict.fromkeys(chaves))

        if not chaves:
            st.warning("Nenhuma chave válida encontrada.")
            return

        st.info(f"Processando **{len(chaves)}** chave(s)...")
        progress = st.progress(0)
        resultados = _consultar_itens_lote(user, cnpj, chaves, progress_cb=progress.progress)
        progress.progress(100)

        all_dfs = []
        erros = []
        for chave, resultado in resultados.items():
            if isinstance(resultado, str):
                erros.append({"Chave": chave, "Erro": resultado})
            else:
                df_chave = _conferencia_df(resultado, chave, aliq_interna, regime_empresa)
                df_chave["Chave"] = chave
                all_dfs.append(df_chave)

        if erros:
            st.warning(f"{len(erros)} chave(s) com erro")

        if not all_dfs:
            st.error("Nenhum item encontrado.")
            return

        df = pd.concat(all_dfs, ignore_index=True)
        _exibir_conferencia(df, aliq_interna, is_lote=True)


def _exibir_conferencia(df: pd.DataFrame, aliq_interna: float, is_lote: bool = False):
    st.markdown("---")
    st.markdown("#### Comparativo")

    def _highlight_diff(val):
        if isinstance(val, (int, float)) and abs(val) > 0.50:
            return "color: red; font-weight: bold"
        return ""

    st.dataframe(
        df.style.applymap(_highlight_diff, subset=["Diferença"]),
        use_container_width=True,
        hide_index=True,
    )

    total_sitram = df["ICMS SITRAM"].sum()
    total_recalc = df["ICMS Recalc."].sum()
    total_dif = df["Diferença"].sum()
    total_frete = df["Frete Est."].sum()
    divergencias = (df["Diferença"].abs() > 0.50).sum()

    st.markdown("#### Totais")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ICMS SITRAM", f"R$ {total_sitram:,.2f}")
    c2.metric("ICMS Recalculado", f"R$ {total_recalc:,.2f}")
    c3.metric("Frete Estimado", f"R$ {total_frete:,.2f}")
    c4.metric("Diferença", f"R$ {total_dif:,.2f}",
              delta=f"R$ {total_dif:,.2f}" if abs(total_dif) > 0.50 else None)

    if divergencias:
        st.warning(
            f"**{divergencias} item(ns)** com diferença > R$ 0,50 mesmo após estimar o frete. "
            "Possíveis causas: MVA aplicada, regra específica por NCM, ou pauta fiscal."
        )
        resumo_tipo = df[df["Diferença"].abs() > 0.50].groupby("Tipo").agg(
            Itens=("Item", "count"),
            Dif_Total=("Diferença", "sum"),
        ).reset_index()
        st.markdown("**Divergências por tipo:**")
        st.dataframe(resumo_tipo, use_container_width=True, hide_index=True)
    else:
        st.success("Cálculo do SITRAM confere. Nenhuma divergência encontrada.")

    with st.expander("Como o SITRAM calcula o ICMS"):
        st.markdown(
            "**Fórmula do SITRAM (Antecipado/DIFAL):**\n\n"
            "```\n"
            "BC = Valor Mercadoria + Frete Rateado (CT-e)\n"
            "Crédito Origem = ICMS Destacado NF + (Frete × Aliq. Interestadual UF)\n"
            "ICMS = BC × Alíq. Interna − Crédito Origem\n"
            "```\n\n"
            "O **Frete Estimado** é calculado automaticamente por engenharia reversa "
            "a partir do ICMS cobrado pelo SITRAM. Se o frete estimado for R$ 0,00, "
            "significa que o SITRAM não incluiu frete naquele item.\n\n"
            f"**Alíquota interna CE:** {aliq_interna}%"
        )

    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "Exportar Conferência CSV",
        data=csv,
        file_name="sitram_conferencia.csv",
        mime="text/csv",
    )


# ── Tab 3: Manifestação ─────────────────────────────────────────────────────

def _tab_manifestacao(user: dict, cnpj: str):
    st.markdown("### Manifestação do Destinatário")
    st.caption(
        "Registre Ciência da Operação (evento 210210) para NF-e recebidas. "
        "Após manifestar, o XML completo fica disponível para download via consChNFe. "
        "**Só funciona para NF-e (mod 55)** — NFC-e não aceita manifestação."
    )

    tp_evento = st.selectbox(
        "Tipo de evento",
        ["210210", "210200", "210220", "210240"],
        format_func=lambda t: {
            "210210": "210210 — Ciência da Operação (recomendado)",
            "210200": "210200 — Confirmação da Operação",
            "210220": "210220 — Desconhecimento da Operação",
            "210240": "210240 — Operação não Realizada",
        }.get(t, t),
        key="sitram_manif_tipo",
    )

    modo = st.radio(
        "Modo",
        ["Chave única", "Lote (múltiplas chaves)"],
        horizontal=True,
        key="sitram_manif_modo",
    )

    if modo == "Chave única":
        chave = st.text_input(
            "Chave de acesso (44 dígitos)",
            max_chars=44,
            placeholder="Chave de acesso da NF-e...",
            key="sitram_manif_chave",
        )
        if st.button("Manifestar", type="primary", key="sitram_btn_manif"):
            chave_limpa = "".join(c for c in chave if c.isdigit())
            if len(chave_limpa) != 44:
                st.warning("Informe uma chave válida com 44 dígitos.")
                return

            resultado_cert = carregar_certificado(user["username"], cnpj)
            if not resultado_cert:
                st.error("Certificado digital não encontrado.")
                return

            from core.nfe_sefaz import manifestar_ciencia
            with st.spinner("Enviando manifestação à SEFAZ..."):
                res = manifestar_ciencia(
                    resultado_cert[0], resultado_cert[1], cnpj,
                    chave_limpa, tp_evento=tp_evento,
                )

            if res.get("ok"):
                st.success(
                    f"**{res.get('desc_evento', '')}** registrada com sucesso! "
                    f"(cStat={res['cStat']}, protocolo={res.get('nProt', '—')})"
                )
            else:
                st.error(res.get("erro", "Erro desconhecido"))
    else:
        chaves_txt = st.text_area(
            "Cole as chaves de acesso (uma por linha)",
            height=200,
            placeholder="23240100000000000000550010000000011000000001\n"
                        "23240100000000000000550010000000021000000002",
            key="sitram_manif_lote",
        )
        if st.button("Manifestar Lote", type="primary", key="sitram_btn_manif_lote"):
            chaves = _extrair_chaves(chaves_txt)
            if not chaves:
                st.warning("Nenhuma chave válida (44 dígitos) encontrada.")
                return

            resultado_cert = carregar_certificado(user["username"], cnpj)
            if not resultado_cert:
                st.error("Certificado digital não encontrado.")
                return

            from core.nfe_sefaz import manifestar_lote
            log_area = st.empty()

            def _log(msg):
                log_area.caption(msg)

            with st.spinner(f"Manifestando {len(chaves)} chave(s)..."):
                resultados = manifestar_lote(
                    resultado_cert[0], resultado_cert[1], cnpj,
                    chaves, tp_evento=tp_evento, log_cb=_log,
                )

            rows = []
            for r in resultados:
                rows.append({
                    "Chave": r.get("chave", ""),
                    "cStat": r.get("cStat", ""),
                    "Resultado": r.get("xMotivo", r.get("erro", "")),
                    "Protocolo": r.get("nProt", ""),
                })
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

            ok = sum(1 for r in resultados if r.get("ok"))
            st.caption(f"**{ok}/{len(resultados)}** manifestações aceitas")


# ── Tab 4: Pagamentos / DAE ─────────────────────────────────────────────────

def _tab_pagamentos(user: dict, cnpj: str):
    st.markdown("### Pagamentos — DAE / ICMS")
    st.caption(
        "Consulte lançamentos de ICMS por chave de acesso e acesse o portal "
        "SITRAM para gerar DAEs e verificar pagamentos."
    )

    modo = st.radio(
        "Modo",
        ["unica", "lote", "relatorio"],
        format_func=lambda m: {
            "unica": "Chave única",
            "lote": "Lote (múltiplas chaves)",
            "relatorio": "Relatório mensal",
        }[m],
        horizontal=True,
        key="sitram_pag_modo",
    )

    if modo == "unica":
        _pagamentos_unica(user, cnpj)
    elif modo == "lote":
        _pagamentos_lote(user, cnpj)
    else:
        _relatorio_mensal(user, cnpj)


def _consultar_status_pagamento(client, chave: str) -> dict | None:
    """Consulta NF por chave e retorna dados de pagamento (NF + lançamentos)."""
    try:
        nf = client.consultar_nota_por_chave(chave)
        if not nf:
            return None
        id_nota = nf.get("id")
        lancamentos = []
        if id_nota:
            try:
                lancamentos = client.consultar_lancamentos_nf(id_nota)
            except Exception:
                pass
        return {"nf": nf, "lancamentos": lancamentos}
    except Exception:
        return None


def _pagamentos_unica(user: dict, cnpj: str):
    chave = st.text_input(
        "Chave de acesso (44 dígitos)",
        max_chars=44,
        placeholder="Digite a chave de acesso da NF-e...",
        key="sitram_pag_chave",
    )

    if st.button("Consultar", type="primary", key="sitram_btn_pag"):
        chave_limpa = "".join(c for c in chave if c.isdigit())
        if len(chave_limpa) != 44:
            st.warning("Informe uma chave válida com 44 dígitos.")
            return

        itens, erro = _consultar_itens_single(user, cnpj, chave_limpa)
        if erro:
            st.error(erro)
            return

        total_icms = sum(i.get("icms", 0) for i in itens)
        total_fecop = sum(i.get("valorFecop", 0) for i in itens)

        st.success(f"**{len(itens)} item(ns)** encontrado(s)")

        client = _get_client(user, cnpj)
        status_data = None
        if client:
            with st.spinner("Consultando status de pagamento..."):
                status_data = _consultar_status_pagamento(client, chave_limpa)

        nf_info = status_data.get("nf", {}) if status_data else {}
        lancamentos = status_data.get("lancamentos", []) if status_data else []

        sit_imposto = nf_info.get("situacaoDoImposto", "")
        sit_descricao = nf_info.get("situacaoDescricao", "")
        total_valor_lanc = sum(l.get("valor", 0) or 0 for l in lancamentos)
        total_pago_lanc = sum(l.get("valorPago", 0) or 0 for l in lancamentos)
        is_pago = total_pago_lanc > 0 and total_pago_lanc >= total_valor_lanc
        total_pendente = total_valor_lanc - total_pago_lanc

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total ICMS", f"R$ {total_icms:,.2f}")
        m2.metric("Total FECOP", f"R$ {total_fecop:,.2f}")
        if lancamentos:
            m3.metric("Pago", f"R$ {total_pago_lanc:,.2f}")
            m4.metric(
                "Pendente",
                f"R$ {total_pendente:,.2f}",
                delta="Quitado" if total_pendente <= 0 else None,
                delta_color="normal" if total_pendente <= 0 else "off",
            )
        else:
            m3.metric("Status", sit_imposto.strip() if sit_imposto else "—")
            m4.metric("Situação", sit_descricao[:25] if sit_descricao else "—")

        if lancamentos:
            rows_lanc = []
            for lanc in lancamentos:
                sit = lanc.get("siuacaoDescricao", lanc.get("situacaoDescricao", ""))
                rows_lanc.append({
                    "Descrição": lanc.get("descricao", ""),
                    "Código": lanc.get("codigo", ""),
                    "Valor": lanc.get("valor", 0),
                    "Pago": lanc.get("valorPago", 0),
                    "Vencimento": (lanc.get("vencimento", "") or "")[:10],
                    "Situação": sit,
                })

            st.dataframe(
                pd.DataFrame(rows_lanc),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Valor": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Pago": st.column_config.NumberColumn(format="R$ %.2f"),
                },
            )
        else:
            rows = []
            for item in itens:
                tipo = _classificar_tipo(item.get("nomeConfiguracao", ""))
                rows.append({
                    "Produto": item.get("descricaoProduto", "?"),
                    "Tipo": tipo,
                    "ICMS": item.get("icms", 0),
                    "FECOP": item.get("valorFecop", 0),
                    "Total": item.get("icms", 0) + item.get("valorFecop", 0),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        if is_pago:
            st.success(f"NF-e quitada — {sit_imposto.strip()}")
        elif sit_descricao:
            st.warning(f"Situação: {sit_descricao}")

        link = _link_sitram_pagamento(chave_limpa)
        st.markdown(f"[Abrir no Portal SITRAM]({link})")


def _pagamentos_lote(user: dict, cnpj: str):
    chaves_txt = st.text_area(
        "Chaves de acesso (uma por linha)",
        height=150,
        placeholder="Cole aqui as chaves, uma por linha...",
        key="sitram_pag_chaves_lote",
    )

    uploaded = st.file_uploader(
        "Ou importe um arquivo CSV/Excel",
        type=["csv", "xlsx", "xls"],
        key="sitram_pag_upload",
    )

    chaves_arquivo = []
    if uploaded:
        try:
            if uploaded.name.endswith(".csv"):
                df_up = pd.read_csv(uploaded, dtype=str)
            else:
                df_up = pd.read_excel(uploaded, dtype=str)
            col_chave = None
            for col in df_up.columns:
                if "chave" in col.lower():
                    col_chave = col
                    break
            if not col_chave:
                col_chave = df_up.columns[0]
            chaves_arquivo = _extrair_chaves("\n".join(df_up[col_chave].dropna().tolist()))
            st.caption(f"{len(chaves_arquivo)} chave(s) do arquivo")
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")

    if st.button("Consultar Lote", type="primary", key="sitram_btn_pag_lote"):
        chaves = _extrair_chaves(chaves_txt) if chaves_txt.strip() else []
        chaves.extend(chaves_arquivo)
        chaves = list(dict.fromkeys(chaves))

        if not chaves:
            st.warning("Nenhuma chave válida encontrada.")
            return

        st.info(f"Processando **{len(chaves)}** chave(s)...")
        progress = st.progress(0)
        resultados = _consultar_itens_lote(user, cnpj, chaves, progress_cb=progress.progress)
        progress.progress(100)

        client = _get_client(user, cnpj)

        rows = []
        erros = []
        for idx, (chave, resultado) in enumerate(resultados.items()):
            if isinstance(resultado, str):
                erros.append({"Chave": chave, "Erro": resultado})
                continue
            total_icms = sum(i.get("icms", 0) for i in resultado)
            total_fecop = sum(i.get("valorFecop", 0) for i in resultado)
            tipos = set()
            for item in resultado:
                tipos.add(_classificar_tipo(item.get("nomeConfiguracao", "")))

            sit_imposto = ""
            if client:
                try:
                    nf = client.consultar_nota_por_chave(chave)
                    sit_imposto = nf.get("situacaoDoImposto", "") if nf else ""
                except Exception:
                    pass

            rows.append({
                "Chave": chave,
                "Itens": len(resultado),
                "Tipos": ", ".join(tipos),
                "ICMS": total_icms,
                "FECOP": total_fecop,
                "Total": total_icms + total_fecop,
                "Status": sit_imposto.strip() if sit_imposto else "—",
                "Link SITRAM": _link_sitram_pagamento(chave),
            })

        if erros:
            st.warning(f"{len(erros)} chave(s) com erro")

        if not rows:
            st.error("Nenhum resultado encontrado.")
            return

        df = pd.DataFrame(rows)

        total_icms_geral = df["ICMS"].sum()
        total_fecop_geral = df["FECOP"].sum()
        total_geral = df["Total"].sum()

        pagos = df[
            df["Status"].str.contains("Pago", case=False, na=False)
            & ~df["Status"].str.contains("A Pagar", case=False, na=False)
        ]
        pendentes = df[~df.index.isin(pagos.index)]

        st.success(f"**{len(rows)} nota(s)** processada(s)")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total ICMS", f"R$ {total_icms_geral:,.2f}")
        m2.metric("Total FECOP", f"R$ {total_fecop_geral:,.2f}")
        m3.metric("Pagas", str(len(pagos)))
        m4.metric("Pendentes", str(len(pendentes)))

        st.dataframe(
            df.drop(columns=["Link SITRAM"]),
            use_container_width=True,
            hide_index=True,
        )

        csv = df.drop(columns=["Link SITRAM"]).to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "Exportar CSV",
            data=csv,
            file_name="sitram_pagamentos_lote.csv",
            mime="text/csv",
        )


def _is_interestadual(chave: str) -> bool:
    """Verifica se a NF-e é interestadual (emitente fora do CE).
    Primeiros 2 dígitos da chave = UF do emitente. CE = 23.
    SITRAM só trata notas interestaduais."""
    return len(chave) == 44 and chave[:2] != "23"


def _relatorio_mensal(user: dict, cnpj: str):
    """Relatório mensal: busca NF-e do período no banco e verifica status no SITRAM."""
    import datetime
    from db.database import listar_resultados_por_periodo

    st.markdown("#### Relatório Mensal — Status de Pagamento")
    st.caption(
        "Busca NF-e interestaduais recebidas no período (dados do Baixar XML) "
        "e verifica o status de pagamento de cada nota no SITRAM."
    )

    hoje = datetime.date.today()
    col_inicio, col_fim = st.columns(2)
    with col_inicio:
        dt_inicio = st.date_input(
            "Data inicial (emissão)",
            value=hoje.replace(day=1),
            key="sitram_rel_dt_ini",
        )
    with col_fim:
        dt_fim = st.date_input(
            "Data final (emissão)",
            value=hoje,
            key="sitram_rel_dt_fim",
        )

    cnpj_filtro = st.text_input(
        "CNPJ destinatário (matriz ou filial — deixe vazio para todas)",
        placeholder="00.000.000/0000-00 ou só números",
        key="sitram_rel_cnpj",
    )

    if st.button("Gerar Relatório", type="primary", key="sitram_btn_relatorio"):
        with st.spinner("Buscando NF-e do período no banco de dados..."):
            nfes = listar_resultados_por_periodo(
                cnpj,
                dt_inicio.isoformat(),
                dt_fim.isoformat(),
                modelo="55",
                papel="Recebida",
                raiz=True,
            )

        if not nfes:
            st.warning(
                f"Nenhuma NF-e recebida encontrada no período {dt_inicio} a {dt_fim}. "
                "Certifique-se de ter baixado os XMLs na aba **Baixar XML** "
                "(incluindo filiais) para este certificado."
            )
            return

        cnpj_filtro_limpo = "".join(c for c in cnpj_filtro if c.isdigit()) if cnpj_filtro else ""
        if cnpj_filtro_limpo:
            nfes = [
                nf for nf in nfes
                if (nf.get("cnpj_dest") or "").replace(".", "").replace("/", "").replace("-", "") == cnpj_filtro_limpo
            ]
            if not nfes:
                st.warning(f"Nenhuma NF-e encontrada para o CNPJ {cnpj_filtro_limpo}.")
                return

        nfes_inter = [nf for nf in nfes if _is_interestadual(nf.get("chave", ""))]
        n_intra = len(nfes) - len(nfes_inter)

        if not nfes_inter:
            st.info(
                f"{len(nfes)} NF-e encontrada(s), mas todas são internas do CE. "
                "SITRAM só trata notas interestaduais."
            )
            return

        if n_intra > 0:
            st.caption(
                f"{n_intra} NF-e interna(s) do CE excluída(s) — "
                "SITRAM só trata notas interestaduais."
            )

        chaves = [nf["chave"] for nf in nfes_inter]
        st.info(f"**{len(chaves)}** NF-e interestadual(is). Consultando SITRAM...")

        client = _get_client(user, cnpj)
        if not client:
            return

        progress = st.progress(0)
        rows = []
        total = len(chaves)
        nfe_map = {nf["chave"]: nf for nf in nfes_inter}

        for idx, chave in enumerate(chaves):
            progress.progress(int((idx + 1) / total * 100))
            nf_db = nfe_map.get(chave, {})

            try:
                nf_sitram = client.consultar_nota_por_chave(chave)
            except Exception:
                nf_sitram = None

            emissao = (nf_db.get("data_emissao", "") or "")[:10]
            emitente = nf_db.get("nome_emit", "")
            valor_nf = nf_db.get("valor_total", 0) or 0
            uf_emit = UF_SIGLAS.get(chave[:2], chave[:2])

            if nf_sitram:
                sit_imposto = (nf_sitram.get("situacaoDoImposto", "") or "").strip()
                id_nota = nf_sitram.get("id")
                valor_pago = 0.0
                valor_icms = 0.0
                if id_nota:
                    try:
                        lancs = client.consultar_lancamentos_nf(id_nota)
                        valor_icms = sum(l.get("valor", 0) or 0 for l in lancs)
                        valor_pago = sum(l.get("valorPago", 0) or 0 for l in lancs)
                    except Exception:
                        pass
                is_pago = valor_pago > 0 and valor_pago >= valor_icms
            else:
                sit_imposto = "Sem dados SITRAM"
                is_pago = False
                valor_icms = 0.0
                valor_pago = 0.0

            rows.append({
                "Emissão": emissao,
                "NF": nf_db.get("numero", ""),
                "UF": uf_emit,
                "Emitente": emitente,
                "Valor NF": valor_nf,
                "ICMS": valor_icms,
                "Pago": valor_pago,
                "Status": sit_imposto,
                "Situação": "Pago" if is_pago else "Pendente",
                "Chave": chave,
            })

        progress.empty()
        df = pd.DataFrame(rows)

        pagos = df[df["Situação"] == "Pago"]
        pendentes = df[df["Situação"] == "Pendente"]

        st.success(
            f"**{len(df)}** nota(s) interestadual(is) — "
            f"emissão de {dt_inicio} a {dt_fim}"
        )

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Notas", str(len(df)))
        m2.metric("Pagas", str(len(pagos)))
        m3.metric("Pendentes", str(len(pendentes)))
        total_icms_pago = df["Pago"].sum()
        m4.metric("Total ICMS Pago", f"R$ {total_icms_pago:,.2f}")

        col_fmt = {
            "Valor NF": st.column_config.NumberColumn(format="R$ %.2f"),
            "ICMS": st.column_config.NumberColumn(format="R$ %.2f"),
            "Pago": st.column_config.NumberColumn(format="R$ %.2f"),
        }

        if not pagos.empty:
            st.markdown("##### Notas Pagas")
            st.dataframe(
                pagos.drop(columns=["Chave"]),
                use_container_width=True,
                hide_index=True,
                column_config=col_fmt,
            )

        if not pendentes.empty:
            st.markdown("##### Notas Pendentes")
            st.dataframe(
                pendentes.drop(columns=["Chave"]),
                use_container_width=True,
                hide_index=True,
                column_config=col_fmt,
            )

        csv = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "Exportar Relatório CSV",
            data=csv,
            file_name=f"sitram_relatorio_{dt_inicio}_{dt_fim}.csv",
            mime="text/csv",
        )


# ── Render principal ─────────────────────────────────────────────────────────

def render():
    user = current_user()
    nav.render("sitram")

    st.markdown("## SITRAM — Sistema de Trânsito de Mercadorias")
    st.caption(
        "Consulte notas fiscais interestaduais, confira cálculos de ICMS, "
        "gerencie DAEs e manifestações do destinatário."
    )

    certs = listar_certificados(user["username"])
    if not certs:
        st.warning(
            "Nenhum certificado digital cadastrado. "
            "Cadastre um na página **Certificados** para usar o SITRAM."
        )
        return

    opcoes = {f"{c['razao_social']} ({_fmt_cnpj(c['cnpj'])})": c["cnpj"] for c in certs}
    selecionado = st.selectbox("Empresa", list(opcoes.keys()), key="sitram_empresa")
    cnpj = opcoes[selecionado]

    tab1, tab2, tab3, tab4 = st.tabs([
        "Consulta NF",
        "Conferência",
        "Manifestação",
        "Pagamentos / DAE",
    ])

    with tab1:
        _tab_consulta_nf(user, cnpj)
    with tab2:
        _tab_conferencia(user, cnpj)
    with tab3:
        _tab_manifestacao(user, cnpj)
    with tab4:
        _tab_pagamentos(user, cnpj)
