"""views/sitram.py — Integração SITRAM (Sistema de Trânsito de Mercadorias)"""
import streamlit as st

from auth.security import current_user
from db.database import listar_certificados, carregar_certificado
from views import nav


def _fmt_cnpj(c: str) -> str:
    c = (c or "").strip().zfill(14)
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"


def _get_client(user: dict, cnpj: str):
    """Cria e autentica o SitramClient; cacheia na sessão."""
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


def _tab_consulta_nf(user: dict, cnpj: str):
    """Consulta de notas fiscais de compras de outros estados."""
    st.markdown("### Consulta de Nota Fiscal")
    st.caption(
        "Consulte notas fiscais no SITRAM por chave de acesso. "
        "Inclui notas de compras de outros estados com trânsito no Ceará."
    )

    chave = st.text_input(
        "Chave de acesso (44 dígitos)",
        max_chars=44,
        placeholder="Digite a chave de acesso da NF-e...",
        key="sitram_chave_nf",
    )

    col1, col2 = st.columns(2)
    modo_logado = col1.checkbox("Consulta autenticada", value=True, key="sitram_logado")

    if col2.button("Consultar", type="primary", key="sitram_btn_consultar"):
        chave_limpa = "".join(c for c in chave if c.isdigit())
        if len(chave_limpa) != 44:
            st.warning("Informe uma chave de acesso válida com 44 dígitos.")
            return

        if modo_logado:
            client = _get_client(user, cnpj)
            if not client:
                return
            try:
                with st.spinner("Consultando nota fiscal no SITRAM..."):
                    resultado = client.consultar_nota(chave_limpa)
                st.success("Nota encontrada!")
                st.json(resultado)
            except Exception as e:
                st.error(f"Erro na consulta: {e}")
        else:
            try:
                from core.sitram_sefaz import _sessao, consultar_nota_fiscal_publica
                resultado_cert = carregar_certificado(user["username"], cnpj)
                if not resultado_cert:
                    st.error("Certificado não encontrado.")
                    return
                sessao = _sessao(resultado_cert[0], resultado_cert[1])
                with st.spinner("Consultando nota fiscal (público)..."):
                    resultado = consultar_nota_fiscal_publica(sessao, chave_limpa)
                st.success("Nota encontrada!")
                st.json(resultado)
            except Exception as e:
                st.error(f"Erro na consulta pública: {e}")


def _tab_consulta_protocolo(user: dict, cnpj: str):
    """Consulta protocolo NF-e/NFC-e diretamente no SVRS."""
    st.markdown("### Consulta de Protocolo — SVRS")
    st.caption(
        "Valida o status de NF-e e NFC-e diretamente no SVRS (autorizador do Ceará). "
        "Retorna protocolo, situação e eventos da nota."
    )

    modo = st.radio(
        "Modo de consulta",
        ["Chave única", "Lote (múltiplas chaves)"],
        horizontal=True,
        key="sitram_protocolo_modo",
    )

    if modo == "Chave única":
        chave = st.text_input(
            "Chave de acesso (44 dígitos)",
            max_chars=44,
            placeholder="Digite a chave de acesso...",
            key="sitram_proto_chave",
        )
        if st.button("Consultar Protocolo", type="primary", key="sitram_btn_proto"):
            chave_limpa = "".join(c for c in chave if c.isdigit())
            if len(chave_limpa) != 44:
                st.warning("Informe uma chave válida com 44 dígitos.")
                return

            resultado_cert = carregar_certificado(user["username"], cnpj)
            if not resultado_cert:
                st.error("Certificado digital não encontrado.")
                return

            from core.nfe_sefaz import consultar_protocolo_svrs
            with st.spinner("Consultando SVRS..."):
                res = consultar_protocolo_svrs(resultado_cert[0], resultado_cert[1], chave_limpa)

            if res.get("ok"):
                st.success(f"**{res['modelo']}** — {res['situacao']} (cStat={res['cStat']})")
            else:
                st.error(f"cStat={res.get('cStat', '?')}: {res.get('xMotivo', res.get('erro', ''))}")

            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("Protocolo", res.get("nProt", "—"))
                st.metric("Modelo", res.get("modelo", "—"))
            with col_b:
                dh = res.get("dhRecbto", "")
                st.metric("Data Autorização", dh[:10] if dh else "—")
                st.metric("cStat", res.get("cStat", "—"))

            if res.get("eventos"):
                st.markdown("**Eventos:**")
                for ev in res["eventos"]:
                    st.markdown(
                        f"- **{ev.get('descricao', ev.get('tipo', '?'))}** "
                        f"— {ev.get('data', '')[:10]} (prot: {ev.get('protocolo', '—')})"
                    )
    else:
        chaves_txt = st.text_area(
            "Cole as chaves de acesso (uma por linha)",
            height=200,
            placeholder="23240100000000000000550010000000011000000001\n23240100000000000000650010000000021000000002",
            key="sitram_proto_lote",
        )
        if st.button("Consultar Lote", type="primary", key="sitram_btn_proto_lote"):
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

            from core.nfe_sefaz import consultar_protocolo_lote
            progress = st.progress(0)
            log_area = st.empty()

            def _log(msg):
                log_area.caption(msg)

            with st.spinner(f"Consultando {len(chaves)} chave(s) no SVRS..."):
                resultados = consultar_protocolo_lote(
                    resultado_cert[0], resultado_cert[1], chaves, log_cb=_log,
                )

            progress.progress(100)

            import pandas as pd
            rows = []
            for r in resultados:
                rows.append({
                    "Chave": r.get("chave", ""),
                    "Modelo": r.get("modelo", ""),
                    "cStat": r.get("cStat", ""),
                    "Situação": r.get("situacao", r.get("xMotivo", "")),
                    "Protocolo": r.get("nProt", ""),
                    "Data": r.get("dhRecbto", "")[:10] if r.get("dhRecbto") else "",
                })
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

            ok = sum(1 for r in resultados if r.get("ok"))
            st.caption(f"**{ok}/{len(resultados)}** autorizadas")


def _tab_difal_calculadora(user: dict, cnpj: str):
    """Calculadora DIFAL / ICMS antecipado."""
    st.markdown("### Calculadora DIFAL / ICMS Antecipado")
    st.caption(
        "Consulte e calcule o DIFAL e ICMS antecipado para notas fiscais "
        "de compras interestaduais destinadas ao Ceará."
    )

    chave = st.text_input(
        "Chave de acesso da NF-e",
        max_chars=44,
        placeholder="Digite a chave de acesso...",
        key="sitram_difal_chave",
    )

    if st.button("Consultar DIFAL", type="primary", key="sitram_btn_difal"):
        chave_limpa = "".join(c for c in chave if c.isdigit())
        if len(chave_limpa) != 44:
            st.warning("Informe uma chave válida com 44 dígitos.")
            return

        client = _get_client(user, cnpj)
        if not client:
            return

        try:
            with st.spinner("Consultando nota no SITRAM..."):
                nota = client.consultar_nota(chave_limpa)

            st.success("Nota localizada no SITRAM!")

            if isinstance(nota, dict):
                col1, col2, col3 = st.columns(3)
                col1.metric("Emitente", nota.get("nomeEmitente", nota.get("cnpjEmitente", "—")))
                col2.metric("UF Origem", nota.get("ufEmitente", "—"))
                col3.metric("Valor NF", f"R$ {nota.get('valorTotal', 0):.2f}")

            st.json(nota)

        except Exception as e:
            st.error(f"Erro ao consultar: {e}")


def _tab_pagamentos(user: dict, cnpj: str):
    """Consulta de DAEs pagos e pendentes + relatórios."""
    st.markdown("### Pagamentos — DAE / ICMS")
    st.caption(
        "Consulte DAEs pagos e pendentes, gere relatórios de pagamentos "
        "realizados no mês e exporte em CSV."
    )

    client = _get_client(user, cnpj)
    if not client:
        return

    st.markdown("---")

    sub_tab = st.radio(
        "Operação",
        ["Contribuinte", "Gerar Relatório CSV"],
        horizontal=True,
        key="sitram_pag_sub",
    )

    if sub_tab == "Contribuinte":
        if st.button("Carregar dados do contribuinte", key="sitram_btn_contrib"):
            try:
                with st.spinner("Carregando dados do contribuinte..."):
                    dados = client.contribuinte()
                st.success("Dados carregados!")
                st.json(dados)
            except Exception as e:
                st.error(f"Erro: {e}")

    elif sub_tab == "Gerar Relatório CSV":
        st.info(
            "O relatório CSV inclui todos os pagamentos (DAE, DIFAL, convênio) "
            "do período selecionado."
        )
        col1, col2 = st.columns(2)
        import datetime
        data_ini = col1.date_input("Data inicial", key="sitram_csv_ini",
                                    value=datetime.date.today().replace(day=1))
        data_fim = col2.date_input("Data final", key="sitram_csv_fim",
                                    value=datetime.date.today())

        if st.button("Gerar CSV", type="primary", key="sitram_btn_csv"):
            try:
                payload = {
                    "dataInicial": data_ini.isoformat(),
                    "dataFinal": data_fim.isoformat(),
                }
                with st.spinner("Gerando relatório CSV..."):
                    csv_bytes = client.gerar_csv(payload)
                st.download_button(
                    "Baixar CSV",
                    data=csv_bytes,
                    file_name=f"sitram_pagamentos_{data_ini}_{data_fim}.csv",
                    mime="text/csv",
                )
                st.success("Relatório gerado!")
            except Exception as e:
                st.error(f"Erro ao gerar relatório: {e}")


def _tab_manifestacao(user: dict, cnpj: str):
    """Manifestação do Destinatário — Ciência da Operação."""
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
            placeholder="23240100000000000000550010000000011000000001\n23240100000000000000550010000000021000000002",
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


def render():
    user = current_user()
    nav.render("sitram")

    st.markdown("## SITRAM — Sistema de Trânsito de Mercadorias")
    st.caption(
        "Consulte notas fiscais interestaduais, calcule DIFAL/ICMS antecipado, "
        "gerencie DAEs e gere relatórios de pagamentos."
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

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Consulta NF",
        "Protocolo SVRS",
        "Manifestação",
        "DIFAL / Calculadora",
        "Pagamentos / DAE",
    ])

    with tab1:
        _tab_consulta_nf(user, cnpj)
    with tab2:
        _tab_consulta_protocolo(user, cnpj)
    with tab3:
        _tab_manifestacao(user, cnpj)
    with tab4:
        _tab_difal_calculadora(user, cnpj)
    with tab5:
        _tab_pagamentos(user, cnpj)
