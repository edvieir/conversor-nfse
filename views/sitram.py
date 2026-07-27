"""views/sitram.py — Integração SITRAM (Sistema de Trânsito de Mercadorias)"""
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


def _consultar_itens(user: dict, cnpj: str, chave: str):
    """Consulta itens SITRAM. Retorna (itens, erro)."""
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
    return (itens, None) if itens else (None, "Nenhum item encontrado para esta chave de acesso.")


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


def _exibir_item_detalhado(item: dict, idx: int, regime_empresa: str, expanded: bool = False):
    tipo = _classificar_tipo(item.get("nomeConfiguracao", ""))
    icms = item.get("icms", 0)
    produto = item.get("descricaoProduto", "?")

    with st.expander(f"Item {idx} | [{tipo}] {produto} — ICMS R$ {icms:,.2f}", expanded=expanded):
        alertas = _alertas_item(item, regime_empresa)
        for alerta in alertas:
            st.warning(alerta)

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

        return alertas


# ── Tab 1: Consulta NF ──────────────────────────────────────────────────────

def _tab_consulta_nf(user: dict, cnpj: str):
    st.markdown("### Consulta de Nota Fiscal")
    st.caption(
        "Consulte notas fiscais no SITRAM por chave de acesso. "
        "Exibe classificação fiscal (Antecipado, DIFAL, ST), alertas de atenção "
        "e detalhamento de ICMS por item."
    )

    regime_empresa = st.radio(
        "Regime tributário da empresa",
        ["normal", "simples"],
        format_func=lambda r: {"normal": "Regime Normal", "simples": "Simples Nacional"}[r],
        horizontal=True,
        key="sitram_regime",
    )

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

        itens, erro = _consultar_itens(user, cnpj, chave_limpa)
        if erro:
            st.error(erro)
            return

        uf = _uf_origem(chave_limpa)
        aliq_inter = _aliq_inter_padrao(chave_limpa)
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
            alertas = _exibir_item_detalhado(item, i, regime_empresa, expanded=(i == 1))
            total_alertas += len(alertas)

        if total_alertas:
            st.markdown("---")
            st.warning(
                f"**{total_alertas} alerta(s) de atenção** — revise os itens sinalizados acima."
            )


# ── Tab 2: Conferência ──────────────────────────────────────────────────────

def _tab_conferencia(user: dict, cnpj: str):
    st.markdown("### Conferência de Cálculo SITRAM")
    st.caption(
        "Confira se o ICMS calculado pelo SITRAM está correto. "
        "Compare com o cálculo esperado usando alíquotas ajustáveis."
    )

    regime_empresa = st.radio(
        "Regime tributário da empresa",
        ["normal", "simples"],
        format_func=lambda r: {"normal": "Regime Normal", "simples": "Simples Nacional"}[r],
        horizontal=True,
        key="sitram_conf_regime",
    )

    chave = st.text_input(
        "Chave de acesso (44 dígitos)",
        max_chars=44,
        placeholder="Digite a chave de acesso da NF-e...",
        key="sitram_conf_chave",
    )

    col_a, col_b = st.columns(2)
    aliq_interna = col_a.number_input(
        "Alíquota interna CE (%)",
        min_value=0.0, max_value=40.0,
        value=ALIQ_INTERNA_CE, step=0.5,
        key="sitram_conf_aliq_interna",
    )

    if st.button("Conferir", type="primary", key="sitram_btn_conferir"):
        chave_limpa = "".join(c for c in chave if c.isdigit())
        if len(chave_limpa) != 44:
            st.warning("Informe uma chave válida com 44 dígitos.")
            return

        itens, erro = _consultar_itens(user, cnpj, chave_limpa)
        if erro:
            st.error(erro)
            return

        uf = _uf_origem(chave_limpa)
        aliq_inter_default = _aliq_inter_padrao(chave_limpa)

        st.info(f"UF Origem: **{uf}** | Aliq. interestadual presumida: **{aliq_inter_default}%**")

        st.markdown("---")
        st.markdown("#### Comparativo item a item")

        total_sitram = 0.0
        total_esperado = 0.0
        total_diferenca = 0.0
        divergencias = 0

        import pandas as pd
        rows = []

        for i, item in enumerate(itens, 1):
            tipo = _classificar_tipo(item.get("nomeConfiguracao", ""))
            bc = item.get("valorBc", 0)
            icms_dest = item.get("valorIcmsDestacado", 0)
            icms_sitram = item.get("icms", 0)
            aliq_item = item.get("valorAliquota", 0)
            fecop = item.get("valorFecop", 0)
            produto = item.get("descricaoProduto", "?")

            aliq_inter_real = aliq_item if aliq_item > 0 else aliq_inter_default

            if tipo in ("ANTECIPADO", "DIFAL"):
                if regime_empresa == "simples":
                    icms_esperado = bc * (aliq_interna / 100) - icms_dest
                else:
                    icms_esperado = bc * ((aliq_interna - aliq_inter_real) / 100)
                icms_esperado = max(icms_esperado, 0)
            elif tipo == "ST":
                icms_esperado = bc * (aliq_interna / 100) - icms_dest
                icms_esperado = max(icms_esperado, 0)
            else:
                icms_esperado = icms_sitram

            diferenca = icms_sitram - icms_esperado

            rows.append({
                "Item": i,
                "Produto": produto[:30],
                "Tipo": tipo,
                "BC": bc,
                "Aliq.Inter.": f"{aliq_inter_real}%",
                "ICMS SITRAM": icms_sitram,
                "ICMS Esperado": round(icms_esperado, 2),
                "Diferença": round(diferenca, 2),
            })

            total_sitram += icms_sitram
            total_esperado += icms_esperado
            total_diferenca += diferenca
            if abs(diferenca) > 0.50:
                divergencias += 1

        df = pd.DataFrame(rows)
        st.dataframe(
            df.style.applymap(
                lambda v: "color: red" if isinstance(v, (int, float)) and abs(v) > 0.50 else "",
                subset=["Diferença"],
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("---")
        st.markdown("#### Totais")

        t1, t2, t3 = st.columns(3)
        t1.metric("ICMS SITRAM", f"R$ {total_sitram:,.2f}")
        t2.metric("ICMS Esperado", f"R$ {total_esperado:,.2f}")
        delta_str = f"R$ {total_diferenca:,.2f}"
        t3.metric("Diferença", delta_str, delta=delta_str if abs(total_diferenca) > 0.50 else None)

        if divergencias:
            st.warning(
                f"**{divergencias} item(ns)** com diferença superior a R$ 0,50. "
                "Ajuste a alíquota interna ou verifique o regime de cada item."
            )
        else:
            st.success("Nenhuma divergência significativa encontrada.")

        st.caption(
            "**Nota:** O cálculo esperado usa a fórmula simplificada "
            f"BC x ({aliq_interna}% - aliq.interestadual) para Antecipado/DIFAL, e "
            f"BC x {aliq_interna}% - ICMS destacado para ST. "
            "O SITRAM pode usar fatores adicionais (MVA, FECOP, arredondamento). "
            "Ajuste a alíquota interna conforme o produto (20%, 25%, 28%, etc.)."
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
            linhas = [l.strip() for l in chaves_txt.strip().splitlines() if l.strip()]
            chaves = ["".join(c for c in l if c.isdigit()) for l in linhas]
            chaves = [c for c in chaves if len(c) == 44]

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

            import pandas as pd
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
        "Gere DAE para pagamento de ICMS por chave de acesso e consulte "
        "lançamentos pagos e em aberto."
    )

    sub = st.radio(
        "Operação",
        ["gerar_dae", "relatorio"],
        format_func=lambda s: {
            "gerar_dae": "Gerar DAE por Chave",
            "relatorio": "Relatório de Pagamentos",
        }[s],
        horizontal=True,
        key="sitram_pag_sub",
    )

    if sub == "gerar_dae":
        _sub_gerar_dae(user, cnpj)
    else:
        _sub_relatorio(user, cnpj)


def _sub_gerar_dae(user: dict, cnpj: str):
    st.markdown("---")
    chave = st.text_input(
        "Chave de acesso (44 dígitos)",
        max_chars=44,
        placeholder="Digite a chave de acesso da NF-e...",
        key="sitram_pag_chave",
    )

    if st.button("Consultar Lançamentos", type="primary", key="sitram_btn_pag_consultar"):
        chave_limpa = "".join(c for c in chave if c.isdigit())
        if len(chave_limpa) != 44:
            st.warning("Informe uma chave válida com 44 dígitos.")
            return

        itens, erro = _consultar_itens(user, cnpj, chave_limpa)
        if erro:
            st.error(erro)
            return

        total_icms = sum(i.get("icms", 0) for i in itens)
        total_fecop = sum(i.get("valorFecop", 0) for i in itens)

        st.success(f"**{len(itens)} lançamento(s)** encontrado(s)")

        m1, m2, m3 = st.columns(3)
        m1.metric("Total ICMS", f"R$ {total_icms:,.2f}")
        m2.metric("Total FECOP", f"R$ {total_fecop:,.2f}")
        m3.metric("Total a Recolher", f"R$ {total_icms + total_fecop:,.2f}")

        ids_lancamento = []
        for i, item in enumerate(itens, 1):
            tipo = _classificar_tipo(item.get("nomeConfiguracao", ""))
            icms = item.get("icms", 0)
            id_lanc = str(item.get("id", ""))
            ids_lancamento.append(id_lanc)
            st.markdown(
                f"**{i}.** [{tipo}] {item.get('descricaoProduto', '?')} — "
                f"ICMS R$ {icms:,.2f} | FECOP R$ {item.get('valorFecop', 0):,.2f}"
            )

        st.session_state["_sitram_ids_lancamento"] = ids_lancamento
        st.session_state["_sitram_pag_chave_atual"] = chave_limpa

    ids = st.session_state.get("_sitram_ids_lancamento", [])
    if ids:
        st.markdown("---")
        st.markdown("#### Gerar DAE")

        tipo_dae = st.selectbox(
            "Tipo de DAE",
            ["antecipado", "difal", "nf_difal", "convenio"],
            format_func=lambda t: {
                "antecipado": "DAE Antecipado",
                "difal": "DAE DIFAL",
                "nf_difal": "DAE NF DIFAL",
                "convenio": "DAE Convênio",
            }[t],
            key="sitram_tipo_dae",
        )

        col1, col2 = st.columns(2)

        if col1.button("Simular DAE", key="sitram_btn_simular_dae"):
            client = _get_client(user, cnpj)
            if not client:
                return
            try:
                with st.spinner("Simulando DAE no SITRAM..."):
                    if tipo_dae == "difal":
                        resultado = client.simular_dae_difal(ids)
                    elif tipo_dae == "nf_difal":
                        resultado = client.simular_dae_nf_difal(ids)
                    elif tipo_dae == "convenio":
                        resultado = client.simular_dae_convenio(ids)
                    else:
                        resultado = client.simular_dae(ids)
                st.success("Simulação concluída!")
                st.json(resultado)
                st.session_state["_sitram_dae_simulacao"] = resultado
            except Exception as e:
                st.error(f"Erro na simulação: {e}")

        simulacao = st.session_state.get("_sitram_dae_simulacao")
        if simulacao and col2.button("Emitir DAE", type="primary", key="sitram_btn_emitir_dae"):
            client = _get_client(user, cnpj)
            if not client:
                return
            try:
                with st.spinner("Emitindo DAE..."):
                    resultado = client.emitir_dae(
                        simulacao,
                        ids=",".join(ids),
                    )
                st.success("DAE emitido com sucesso!")
                st.json(resultado)
            except Exception as e:
                st.error(f"Erro ao emitir DAE: {e}")


def _sub_relatorio(user: dict, cnpj: str):
    st.markdown("---")
    st.info(
        "Consulte lançamentos SITRAM por chave de acesso para verificar "
        "o status de pagamento de cada item."
    )

    chave = st.text_input(
        "Chave de acesso (44 dígitos)",
        max_chars=44,
        placeholder="Digite a chave de acesso...",
        key="sitram_rel_chave",
    )

    if st.button("Consultar Status", type="primary", key="sitram_btn_rel"):
        chave_limpa = "".join(c for c in chave if c.isdigit())
        if len(chave_limpa) != 44:
            st.warning("Informe uma chave válida com 44 dígitos.")
            return

        itens, erro = _consultar_itens(user, cnpj, chave_limpa)
        if erro:
            st.error(erro)
            return

        client = _get_client(user, cnpj)

        import pandas as pd
        rows = []
        for item in itens:
            tipo = _classificar_tipo(item.get("nomeConfiguracao", ""))
            id_lanc = str(item.get("id", ""))

            status = "—"
            valor_pago = 0.0
            if client and id_lanc:
                try:
                    som = client.somatorio_lancamento(id_lanc)
                    status = som.get("situacao", som.get("status", "Consultado"))
                    valor_pago = som.get("valorPago", som.get("totalPago", 0))
                except Exception:
                    status = "Erro ao consultar"

            rows.append({
                "Produto": item.get("descricaoProduto", "?")[:35],
                "Tipo": tipo,
                "ICMS Devido": item.get("icms", 0),
                "FECOP": item.get("valorFecop", 0),
                "Valor Pago": valor_pago,
                "Status": status,
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        total_devido = sum(r["ICMS Devido"] + r["FECOP"] for r in rows)
        total_pago = sum(r["Valor Pago"] for r in rows)
        total_aberto = total_devido - total_pago

        t1, t2, t3 = st.columns(3)
        t1.metric("Total Devido", f"R$ {total_devido:,.2f}")
        t2.metric("Total Pago", f"R$ {total_pago:,.2f}")
        t3.metric("Em Aberto", f"R$ {total_aberto:,.2f}")


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
