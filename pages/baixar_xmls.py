"""
pages/baixar_xmls.py — Baixar XMLs via API NFS-e usando certificado salvo
"""

import streamlit as st
from datetime import date
from auth.security import current_user, is_admin, logout
from assets.icons import icon
from db.database import listar_certificados, carregar_certificado


def _navbar():
    user    = current_user()
    inicial = user["name"][0].upper() if user["name"] else "U"

    st.markdown(f"""
    <div class="topbar">
        <div class="topbar-logo">{icon("zap", 16, "#fff")}</div>
        <span class="topbar-name">Conversor NFS-e</span>
        <div class="topbar-spacer"></div>
        <div class="topbar-divider"></div>
        <span class="topbar-tag">Baixar XMLs &middot; API NFS-e Nacional</span>
    </div>
    """, unsafe_allow_html=True)

    if is_admin():
        c1, c2, c3, c4, c5, c6, c7 = st.columns([2.2, 1.4, 1.4, 1.2, 1.4, 1.4, 1.0])
    else:
        c1, c2, c3, c4, c5, c6 = st.columns([2.2, 1.4, 1.4, 1.2, 1.4, 1.0])

    with c1:
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:8px;padding:6px 0;">
            <div class="navbar-avatar">{inicial}</div>
            <span class="navbar-name">{user["name"]}</span>
        </div>""", unsafe_allow_html=True)

    with c2:
        if st.button("Conversor", key="nav_conv_bx", use_container_width=True):
            st.session_state.pagina = "conversor"; st.rerun()
    with c3:
        if st.button("Certificados", key="nav_cert_bx", use_container_width=True):
            st.session_state.pagina = "certificados"; st.rerun()
    with c4:
        if st.button("Milhão", key="nav_milhao_bx", use_container_width=True):
            st.session_state.pagina = "milhao"; st.rerun()
    with c5:
        if st.button("Dashboard", key="nav_dash_bx", use_container_width=True):
            st.session_state.pagina = "dashboard"; st.rerun()

    if is_admin():
        with c6:
            if st.button("Usuarios", key="nav_usr_bx", use_container_width=True):
                st.session_state.pagina = "usuarios"; st.rerun()
        with c7:
            if st.button("Sair", key="logout_bx", use_container_width=True):
                logout()
    else:
        with c6:
            if st.button("Sair", key="logout_bx", use_container_width=True):
                logout()

    st.markdown('<div style="height:.6rem;"></div>', unsafe_allow_html=True)


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

        ic_info = icon("info", 13, "#475569")
        st.markdown(
            f'<div style="color:#475569;font-size:.72rem;margin-top:6px;">'
            f'{ic_info}&nbsp; Baixa <b>Servicos Tomados</b> do período selecionado</div>',
            unsafe_allow_html=True,
        )

    # ── ETAPA 3 — Baixar ─────────────────────────────────────────────────────
    with st.container(border=True):
        ic = icon("download", 16, "#00CED1")
        st.markdown(f"""
        <div class="step-header">
            <div class="step-num">3</div>
            <div class="step-info">
                <div class="step-title">{ic}&nbsp; Baixar XMLs</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        btn_baixar = st.button(
            "Baixar XMLs via API NFS-e",
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

            # Log em tempo real
            log_placeholder = st.empty()

            def atualizar_progress(frac: float):
                progress_bar.progress(frac, text=f"Baixando XMLs... {int(frac*100)}%")

            def atualizar_log(linhas: list):
                ultimas = linhas[-30:]  # exibe as últimas 30 linhas para não poluir
                log_placeholder.code("\n".join(ultimas), language="")

            try:
                zip_bytes, log = baixar_xmls_nfse(
                    pfx_bytes=pfx_bytes,
                    senha=senha,
                    cnpj=cnpj_sel,
                    data_ini=data_ini,
                    data_fim=data_fim,
                    tipo="tomadas",
                    progress_cb=atualizar_progress,
                    log_cb=atualizar_log,
                )
                progress_bar.progress(1.0, text="Concluído!")
                log_placeholder.empty()  # limpa log em tempo real

                with st.expander("Log de download", expanded=not bool(zip_bytes)):
                    st.code("\n".join(log), language="")

                if zip_bytes:
                    nome_zip = (
                        f"nfse_tomadas_{cnpj_sel[:8]}_"
                        f"{data_ini.strftime('%Y%m%d')}_{data_fim.strftime('%Y%m%d')}.zip"
                    )
                    ic_ok = icon("check-circle", 32, "#1AB87A")
                    st.markdown(f"""
                    <div class="result-success">
                        <div class="result-success-icon">{ic_ok}</div>
                        <div>
                            <div class="result-success-title">XMLs baixados com sucesso!</div>
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
