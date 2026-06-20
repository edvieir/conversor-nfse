"""views/nfe_nfce.py — Consulta NF-e e NFC-e via SEFAZ Nacional"""

import streamlit as st
from datetime import datetime, date, timedelta
from auth.security import current_user, is_admin
from assets.icons import icon
from db.database import listar_certificados, carregar_certificado, log_conversion
from views import nav


def _fmt_cnpj(cnpj: str) -> str:
    c = "".join(d for d in cnpj if d.isdigit())
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c) == 14 else cnpj


def _label(text: str) -> str:
    return (
        '<div style="color:#475569;font-size:.7rem;font-weight:600;'
        'letter-spacing:.4px;text-transform:uppercase;margin-bottom:3px;">'
        f'{text}</div>'
    )


def render():
    nav.render("nfe_nfce")
    user = current_user()

    # ── Cabeçalho ─────────────────────────────────────────────────────────────
    ic_head = icon("receipt", 20, "#00e5ff")
    st.markdown(f"""
<div style="display:flex;align-items:center;gap:10px;padding:4px 0 18px;">
  <div style="width:40px;height:40px;border-radius:10px;background:#111827;
              border:1px solid rgba(0,229,255,.15);display:flex;align-items:center;justify-content:center;">
    {ic_head}
  </div>
  <div>
    <div style="color:#e2e8f0;font-weight:800;font-size:1.15rem;font-family:Manrope,sans-serif;line-height:1.1;">
      NFE / NFCE
    </div>
    <div style="color:#475569;font-size:.75rem;font-family:Manrope,sans-serif;">
      Consulta automática na SEFAZ Nacional · NF-e e NFC-e emitidas e recebidas
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Verifica certificados ─────────────────────────────────────────────────
    certs = listar_certificados(user["username"])
    if not certs:
        with st.container(border=True):
            ic_warn = icon("alert-triangle", 16, "#C97400")
            st.markdown(f"""
<div style="text-align:center;padding:2rem 1rem;">
  <div style="font-size:1rem;font-weight:700;color:#C97400;margin-bottom:.5rem;">
    {ic_warn}&nbsp; Nenhum certificado cadastrado
  </div>
  <div style="color:#475569;font-size:.85rem;">
    Acesse <b>Certificados</b> no menu para adicionar seu certificado digital A1 (.pfx).
  </div>
</div>
""", unsafe_allow_html=True)
            if st.button("Ir para Certificados", use_container_width=True, type="primary"):
                st.session_state.pagina = "certificados"
                st.rerun()
        return

    # ── PASSO 1 — Empresa / Certificado ──────────────────────────────────────
    with st.container(border=True):
        ic = icon("shield", 16, "#00CED1")
        st.markdown(f"""
<div class="step-header">
  <div class="step-num">1</div>
  <div class="step-info">
    <div class="step-title">{ic}&nbsp; Empresa / Certificado</div>
  </div>
</div>
""", unsafe_allow_html=True)

        opcoes = {
            f"{c['razao_social'] or c['cnpj']}  —  {_fmt_cnpj(c['cnpj'])}": c
            for c in certs
        }
        escolha = st.selectbox("empresa", list(opcoes.keys()),
                               label_visibility="collapsed", key="nfe_sel_empresa")
        cert_sel = opcoes[escolha]
        cnpj_principal = "".join(d for d in cert_sel["cnpj"] if d.isdigit())
        nome_principal = cert_sel["razao_social"] or cnpj_principal

        ic_ok = icon("check-circle", 13, "#10B981")
        st.markdown(
            f'<div style="color:#10B981;font-size:.78rem;margin-top:2px;">'
            f'{ic_ok}&nbsp; Certificado salvo — autenticação mTLS automática</div>',
            unsafe_allow_html=True,
        )

    # ── PASSO 2 — Período ─────────────────────────────────────────────────────
    with st.container(border=True):
        ic = icon("calendar", 16, "#00CED1")
        st.markdown(f"""
<div class="step-header">
  <div class="step-num">2</div>
  <div class="step-info">
    <div class="step-title">{ic}&nbsp; Período de Consulta</div>
    <div class="step-desc">Filtra os documentos retornados pela SEFAZ pela data de emissão.</div>
  </div>
</div>
""", unsafe_allow_html=True)

        hoje = date.today()
        col_ini, col_fim = st.columns(2, gap="medium")
        with col_ini:
            st.markdown(_label("Data Inicial"), unsafe_allow_html=True)
            data_ini = st.date_input("data_ini", value=hoje.replace(day=1),
                                     label_visibility="collapsed", key="nfe_data_ini")
        with col_fim:
            st.markdown(_label("Data Final"), unsafe_allow_html=True)
            data_fim = st.date_input("data_fim", value=hoje,
                                     label_visibility="collapsed", key="nfe_data_fim")

        if data_ini > data_fim:
            ic_e = icon("alert-triangle", 13, "#C97400")
            st.markdown(
                f'<div style="color:#C97400;font-size:.75rem;margin-top:4px;">'
                f'{ic_e}&nbsp; Data inicial deve ser anterior à data final.</div>',
                unsafe_allow_html=True,
            )

        ic_info = icon("info", 13, "#475569")
        st.markdown(
            f'<div style="color:#475569;font-size:.72rem;margin-top:6px;">'
            f'{ic_info}&nbsp; A SEFAZ retorna documentos por NSU sequencial. '
            f'O filtro de datas é aplicado sobre os resultados recebidos.</div>',
            unsafe_allow_html=True,
        )

    # ── PASSO 3 — O que baixar ────────────────────────────────────────────────
    with st.container(border=True):
        ic = icon("sliders", 16, "#00CED1")
        st.markdown(f"""
<div class="step-header">
  <div class="step-num">3</div>
  <div class="step-info">
    <div class="step-title">{ic}&nbsp; O que Consultar / Baixar</div>
  </div>
</div>
""", unsafe_allow_html=True)

        col_tipo, col_papel, col_saida = st.columns(3, gap="medium")

        with col_tipo:
            st.markdown(_label("Tipo de Documento"), unsafe_allow_html=True)
            tipo_opcoes = {
                "NF-e e NFC-e": "ambos",
                "Somente NF-e":  "nfe",
                "Somente NFC-e": "nfce",
            }
            tipo_label = st.selectbox("tipo_doc", list(tipo_opcoes.keys()),
                                      label_visibility="collapsed", key="nfe_tipo")
            tipo_doc = tipo_opcoes[tipo_label]

        with col_papel:
            st.markdown(_label("Papel"), unsafe_allow_html=True)
            papel_opcoes = {
                "Emitidas e Recebidas": "ambos",
                "Somente Recebidas":    "recebidas",
                "Somente Emitidas":     "emitidas",
            }
            papel_label = st.selectbox("papel", list(papel_opcoes.keys()),
                                       label_visibility="collapsed", key="nfe_papel")
            papel_filtro = papel_opcoes[papel_label]

        with col_saida:
            st.markdown(_label("Conteúdo do Download"), unsafe_allow_html=True)
            saida_opcoes = {
                "XMLs + Relatório Excel": "xml_excel",
                "Somente XMLs":           "xml",
                "Somente Relatório Excel":"excel",
            }
            saida_label = st.selectbox("saida", list(saida_opcoes.keys()),
                                       label_visibility="collapsed", key="nfe_saida")
            saida_sel = saida_opcoes[saida_label]

    # ── PASSO 4 — Configurações ───────────────────────────────────────────────
    with st.container(border=True):
        ic = icon("settings", 16, "#00CED1")
        st.markdown(f"""
<div class="step-header">
  <div class="step-num">4</div>
  <div class="step-info">
    <div class="step-title">{ic}&nbsp; Configurações</div>
  </div>
</div>
""", unsafe_allow_html=True)

        col_amb, col_uf = st.columns(2, gap="medium")
        with col_amb:
            st.markdown(_label("Ambiente"), unsafe_allow_html=True)
            amb_opcoes = {"Produção (real)": "1", "Homologação (teste)": "2"}
            amb_label = st.selectbox("ambiente", list(amb_opcoes.keys()),
                                     label_visibility="collapsed", key="nfe_ambiente")
            ambiente = amb_opcoes[amb_label]

        with col_uf:
            st.markdown(_label("UF Autor"), unsafe_allow_html=True)
            uf_lista = ["CE","SP","RJ","MG","BA","PR","RS","PE","GO","SC",
                        "MA","AM","ES","PB","RN","MT","AL","PI","DF","MS",
                        "SE","RO","PA","TO","AP","RR","AC"]
            uf_sel = st.selectbox("uf", uf_lista, index=0,
                                  label_visibility="collapsed", key="nfe_uf")

        if ambiente == "2":
            ic_warn = icon("alert-triangle", 13, "#C97400")
            st.markdown(
                f'<div style="color:#C97400;font-size:.72rem;margin-top:4px;">'
                f'{ic_warn}&nbsp; Homologação: SEFAZ retorna dados de teste, não reais.</div>',
                unsafe_allow_html=True,
            )

    # ── PASSO 5 — Executar ────────────────────────────────────────────────────
    with st.container(border=True):
        ic = icon("zap", 16, "#00CED1")
        st.markdown(f"""
<div class="step-header">
  <div class="step-num">5</div>
  <div class="step-info">
    <div class="step-title">{ic}&nbsp; Consultar SEFAZ</div>
    <div class="step-desc">
      Consulta: <b>{nome_principal}</b> ({_fmt_cnpj(cnpj_principal)}) ·
      {data_ini.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')} ·
      {tipo_label} · {papel_label}
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

        btn_ok = data_ini <= data_fim
        btn_executar = st.button(
            "Consultar SEFAZ agora",
            type="primary",
            use_container_width=True,
            disabled=not btn_ok,
            key="nfe_btn_exec",
        )

        if btn_executar:
            resultado = carregar_certificado(user["username"], cnpj_principal)
            if not resultado:
                st.error("Certificado não encontrado. Recadastre em Certificados.")
                return

            pfx_bytes, pfx_senha = resultado
            empresas_lista = [{"cnpj": cnpj_principal, "nome": nome_principal}]

            progress_bar = st.progress(0, text="Iniciando consulta na SEFAZ...")
            log_placeholder = st.empty()
            log_lines: list[str] = []

            def on_log(msg: str):
                log_lines.append(msg)
                log_placeholder.code("\n".join(log_lines[-30:]), language="")

            def on_progress(frac: float):
                progress_bar.progress(min(frac, 1.0),
                                      text=f"Processando... {int(min(frac,1.0)*100)}%")

            try:
                from core.nfe_sefaz import executar_consulta_sefaz

                zip_bytes, log_final = executar_consulta_sefaz(
                    pfx_bytes=pfx_bytes,
                    pfx_senha=pfx_senha,
                    empresas=empresas_lista,
                    ambiente=ambiente,
                    uf=uf_sel,
                    data_ini=data_ini,
                    data_fim=data_fim,
                    tipo_doc=tipo_doc,
                    papel_filtro=papel_filtro,
                    incluir_xml=(saida_sel in ("xml", "xml_excel")),
                    incluir_excel=(saida_sel in ("excel", "xml_excel")),
                    log_cb=on_log,
                    progress_cb=on_progress,
                )

                progress_bar.progress(1.0, text="Concluído!")
                log_placeholder.empty()

                with st.expander("Log de consulta", expanded=not bool(zip_bytes)):
                    st.code("\n".join(log_final), language="")

                if zip_bytes:
                    import zipfile as _zf, io as _io
                    with _zf.ZipFile(_io.BytesIO(zip_bytes)) as _z:
                        nomes = _z.namelist()
                        qt_xml = len([n for n in nomes if n.endswith(".xml")])
                        qt_xlsx = len([n for n in nomes if n.endswith(".xlsx")])

                    log_conversion(user["username"], "NFE_NFCE", qt_xml or qt_xlsx, True)

                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    nome_zip = (
                        f"nfe_nfce_{cnpj_principal[:8]}_"
                        f"{data_ini.strftime('%Y%m%d')}_{data_fim.strftime('%Y%m%d')}_{ts}.zip"
                    )

                    ic_ok = icon("check-circle", 32, "#1AB87A")
                    partes = []
                    if qt_xml:
                        partes.append(f"{qt_xml} XML(s)")
                    if qt_xlsx:
                        partes.append(f"{qt_xlsx} relatório Excel")
                    st.markdown(f"""
<div class="result-success">
  <div class="result-success-icon">{ic_ok}</div>
  <div>
    <div class="result-success-title">Consulta concluída com sucesso!</div>
    <div class="result-success-meta">
      {' &nbsp;·&nbsp; '.join(partes)} &nbsp;·&nbsp; {round(len(zip_bytes)/1024, 1)} KB
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

                    st.download_button(
                        label=f"⬇  Baixar  {nome_zip}",
                        data=zip_bytes,
                        file_name=nome_zip,
                        mime="application/zip",
                        use_container_width=True,
                    )
                else:
                    ic_warn = icon("alert-triangle", 15, "#C77D0A")
                    st.markdown(
                        f'<div class="warn-box">{ic_warn}'
                        f'<span class="box-text">Nenhum documento encontrado no período '
                        f'{data_ini.strftime("%d/%m/%Y")} a {data_fim.strftime("%d/%m/%Y")}.'
                        f'</span></div>',
                        unsafe_allow_html=True,
                    )

            except Exception as exc:
                progress_bar.empty()
                log_placeholder.empty()
                log_conversion(user["username"], "NFE_NFCE", 0, False)
                ic_err = icon("x-circle", 15, "#D93025")
                st.markdown(
                    f'<div class="error-box">{ic_err}'
                    f'<span class="box-text">Erro: {exc}</span></div>',
                    unsafe_allow_html=True,
                )

    st.markdown("""
<div class="footer">
  Fiscal Hub &nbsp;v2.0 &nbsp;·&nbsp; NFE / NFCE Nacional
  &nbsp;·&nbsp; WebService NFeDistribuicaoDFe · SEFAZ Nacional
</div>
""", unsafe_allow_html=True)
