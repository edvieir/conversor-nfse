"""
pages/baixar_xmls.py — Baixar XMLs/PDFs via API NFS-e usando certificado salvo
"""

import streamlit as st
from datetime import date
from auth.security import current_user, is_admin, logout
from assets.icons import icon
from db.database import listar_certificados, carregar_certificado
from views import nav


def _navbar():
    nav.render("baixar_xmls")


def render():
    _navbar()
    user  = current_user()
    certs = listar_certificados(user["username"])

    # ── Sem certificados cadastrados ──────────────────────────────────────────
    if not certs:
        with st.container(border=True):
            ic_warn = icon("alert-triangle", 16, "#C97400")
            st.markdown(f"""
            <div style="text-align:center;padding:2rem 1rem;">
                <div style="font-size:1.1rem;font-weight:700;color:#C97400;margin-bottom:.5rem;">
                    {ic_warn}&nbsp; Nenhum certificado cadastrado
                </div>
                <div style="color:#475569;font-size:.85rem;">
                    Acesse <b>Certificados</b> no menu para adicionar seu certificado digital.
                    Você só precisa fazer isso uma vez por empresa.
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Ir para Certificados", use_container_width=True, type="primary"):
                st.session_state.pagina = "certificados"
                st.rerun()
        return

    # ── ETAPA 1 — Selecionar empresa ─────────────────────────────────────────
    with st.container(border=True):
        ic = icon("shield", 16, "#00CED1")
        st.markdown(f"""
        <div class="step-header">
            <div class="step-num">1</div>
            <div class="step-info">
                <div class="step-title">{ic}&nbsp; Selecionar Empresa</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        opcoes = {
            f"{c['razao_social'] or c['cnpj']} — {_fmt_cnpj(c['cnpj'])}": c["cnpj"]
            for c in certs
        }
        escolha = st.selectbox(
            "empresa", list(opcoes.keys()),
            label_visibility="collapsed",
            key="sel_empresa",
        )
        cnpj_sel = opcoes[escolha]

        ic_ok = icon("check-circle", 13, "#10B981")
        st.markdown(
            f'<div style="color:#10B981;font-size:.78rem;margin-top:2px;">'
            f'{ic_ok}&nbsp; Certificado salvo — sem necessidade de upload</div>',
            unsafe_allow_html=True,
        )

    # ── ETAPA 2 — Período ─────────────────────────────────────────────────────
    with st.container(border=True):
        ic = icon("settings", 16, "#00CED1")
        st.markdown(f"""
        <div class="step-header">
            <div class="step-num">2</div>
            <div class="step-info">
                <div class="step-title">{ic}&nbsp; Periodo de Consulta</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        hoje         = date.today()
        primeiro_mes = hoje.replace(day=1)
        col_ini, col_fim = st.columns(2, gap="medium")

        with col_ini:
            st.markdown(_label("Data Inicial"), unsafe_allow_html=True)
            data_ini = st.date_input("data_ini", value=primeiro_mes,
                                     label_visibility="collapsed", key="api_data_ini")
        with col_fim:
            st.markdown(_label("Data Final"), unsafe_allow_html=True)
            data_fim = st.date_input("data_fim", value=hoje,
                                     label_visibility="collapsed", key="api_data_fim")

    # ── ETAPA 3 — Opções ──────────────────────────────────────────────────────
    with st.container(border=True):
        ic = icon("sliders", 16, "#00CED1")
        st.markdown(f"""
        <div class="step-header">
            <div class="step-num">3</div>
            <div class="step-info">
                <div class="step-title">{ic}&nbsp; Opcoes</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_tipo, col_fmt = st.columns(2, gap="medium")

        with col_tipo:
            st.markdown(_label("Tipo de Serviço"), unsafe_allow_html=True)
            tipo_opcoes = {
                "Serviços Tomados":   "tomados",
                "Serviços Prestados": "prestados",
                "Todos":              "todos",
            }
            tipo_label = st.selectbox(
                "tipo", list(tipo_opcoes.keys()),
                label_visibility="collapsed",
                key="sel_tipo",
            )
            tipo_sel = tipo_opcoes[tipo_label]

        with col_fmt:
            st.markdown(_label("Formato do Arquivo"), unsafe_allow_html=True)
            fmt_opcoes = {
                "XML":       "xml",
                "PDF":       "pdf",
                "XML + PDF": "ambos",
            }
            fmt_label = st.selectbox(
                "formato", list(fmt_opcoes.keys()),
                label_visibility="collapsed",
                key="sel_formato",
            )
            fmt_sel = fmt_opcoes[fmt_label]

        # Dica contextual
        _dicas = {
            "tomados":   "Notas onde a empresa figura como <b>tomadora</b> do serviço.",
            "prestados": "Notas onde a empresa figura como <b>prestadora</b> do serviço.",
            "todos":     "Todas as notas vinculadas ao CNPJ, sem filtrar papel.",
        }
        ic_info = icon("info", 13, "#475569")
        st.markdown(
            f'<div style="color:#475569;font-size:.72rem;margin-top:6px;">'
            f'{ic_info}&nbsp; {_dicas[tipo_sel]}</div>',
            unsafe_allow_html=True,
        )

        if fmt_sel in ("pdf", "ambos"):
            ic_info2 = icon("info", 13, "#475569")
            st.markdown(
                f'<div style="color:#475569;font-size:.72rem;margin-top:4px;">'
                f'{ic_info2}&nbsp; PDF (DANFSe) baixado da API — uma requisição extra por nota.</div>',
                unsafe_allow_html=True,
            )

    # ── ETAPA 4 — Baixar ─────────────────────────────────────────────────────
    with st.container(border=True):
        ic = icon("download", 16, "#00CED1")
        st.markdown(f"""
        <div class="step-header">
            <div class="step-num">4</div>
            <div class="step-info">
                <div class="step-title">{ic}&nbsp; Baixar</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        _fmt_btn = {"xml": "XMLs", "pdf": "PDFs", "ambos": "XMLs e PDFs"}
        btn_baixar = st.button(
            f"Baixar {_fmt_btn[fmt_sel]} via API NFS-e",
            disabled=(data_ini > data_fim),
            use_container_width=True,
            type="primary",
            key="btn_baixar_api",
        )

        if btn_baixar:
            from core.api_nfse import baixar_xmls_nfse

            resultado = carregar_certificado(user["username"], cnpj_sel)
            if not resultado:
                st.error("Certificado não encontrado. Recadastre em Certificados.")
                return

            pfx_bytes, senha = resultado
            progress_bar = st.progress(0, text="Conectando na API NFS-e...")
            log_placeholder = st.empty()

            def atualizar_progress(frac: float):
                progress_bar.progress(frac, text=f"Processando... {int(frac*100)}%")

            def atualizar_log(linhas: list):
                log_placeholder.code("\n".join(linhas[-30:]), language="")

            try:
                zip_bytes, log = baixar_xmls_nfse(
                    pfx_bytes=pfx_bytes,
                    senha=senha,
                    cnpj=cnpj_sel,
                    data_ini=data_ini,
                    data_fim=data_fim,
                    tipo=tipo_sel,
                    formato=fmt_sel,
                    progress_cb=atualizar_progress,
                    log_cb=atualizar_log,
                )
                progress_bar.progress(1.0, text="Concluído!")
                log_placeholder.empty()

                with st.expander("Log de download", expanded=not bool(zip_bytes)):
                    st.code("\n".join(log), language="")

                if zip_bytes:
                    _tipo_nome = {"tomados": "tomados", "prestados": "prestados", "todos": "todos"}
                    _fmt_nome  = {"xml": "xml", "pdf": "pdf", "ambos": "xml_pdf"}
                    nome_zip = (
                        f"nfse_{_tipo_nome[tipo_sel]}_{_fmt_nome[fmt_sel]}_{cnpj_sel[:8]}_"
                        f"{data_ini.strftime('%Y%m%d')}_{data_fim.strftime('%Y%m%d')}.zip"
                    )
                    ic_ok = icon("check-circle", 32, "#1AB87A")
                    st.markdown(f"""
                    <div class="result-success">
                        <div class="result-success-icon">{ic_ok}</div>
                        <div>
                            <div class="result-success-title">Arquivos baixados com sucesso!</div>
                            <div class="result-success-meta">
                                {round(len(zip_bytes)/1024, 1)} KB &nbsp;&middot;&nbsp; {nome_zip}
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.download_button(
                        label=f"Baixar  {nome_zip}",
                        data=zip_bytes,
                        file_name=nome_zip,
                        mime="application/zip",
                        use_container_width=True,
                    )
                else:
                    ic_warn = icon("alert-triangle", 15, "#C77D0A")
                    st.markdown(
                        f'<div class="warn-box">{ic_warn}'
                        f'<span class="box-text">Nenhuma nota encontrada no período.</span></div>',
                        unsafe_allow_html=True,
                    )

            except Exception as exc:
                progress_bar.empty()
                log_placeholder.empty()
                ic_err = icon("x-circle", 15, "#D93025")
                st.markdown(
                    f'<div class="error-box">{ic_err}'
                    f'<span class="box-text">Erro: {exc}</span></div>',
                    unsafe_allow_html=True,
                )

    st.markdown("""
    <div class="footer">
        Conversor NFS-e &nbsp;v2.0 &nbsp;&middot;&nbsp; API NFS-e Nacional
        &nbsp;&middot;&nbsp; adn.nfse.gov.br
    </div>
    """, unsafe_allow_html=True)


def _fmt_cnpj(cnpj: str) -> str:
    if len(cnpj) == 14:
        return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
    return cnpj


def _label(text: str) -> str:
    return (
        '<div style="color:#475569;font-size:.7rem;font-weight:600;'
        'letter-spacing:.4px;text-transform:uppercase;margin-bottom:3px;">'
        f'{text}</div>'
    )
