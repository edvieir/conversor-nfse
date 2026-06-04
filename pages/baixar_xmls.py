"""
pages/baixar_xmls.py — Tela "Baixar XMLs" via API NFS-e Nacional
"""

import streamlit as st
from datetime import date, timedelta
from auth.security import current_user, is_admin, logout
from assets.icons import icon


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
        c1, c2, c3, c4, c5, c6 = st.columns([2.5, 1.6, 1.6, 1.5, 1.5, 1.0])
    else:
        c1, c2, c3, c4, c5 = st.columns([2.5, 1.6, 1.6, 1.5, 1.0])

    with c1:
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:8px;padding:6px 0;">
            <div class="navbar-avatar">{inicial}</div>
            <span class="navbar-name">{user["name"]}</span>
        </div>""", unsafe_allow_html=True)

    with c2:
        if st.button("Conversor", key="nav_conv_bx", use_container_width=True):
            st.session_state.pagina = "conversor"
            st.rerun()
    with c3:
        if st.button("Notas do Milhao", key="nav_milhao_bx", use_container_width=True):
            st.session_state.pagina = "milhao"
            st.rerun()
    with c4:
        if st.button("Dashboard", key="nav_dash_bx", use_container_width=True):
            st.session_state.pagina = "dashboard"
            st.rerun()

    if is_admin():
        with c5:
            if st.button("Usuarios", key="nav_usr_bx", use_container_width=True):
                st.session_state.pagina = "usuarios"
                st.rerun()
        with c6:
            if st.button("Sair", key="logout_bx", use_container_width=True):
                logout()
    else:
        with c5:
            if st.button("Sair", key="logout_bx", use_container_width=True):
                logout()

    st.markdown('<div style="height:.6rem;"></div>', unsafe_allow_html=True)


def render():
    _navbar()

    # ── ETAPA 1 — Certificado ─────────────────────────────────────────────────
    with st.container(border=True):
        ic = icon("shield", 16, "#00CED1")
        st.markdown(f"""
        <div class="step-header">
            <div class="step-num">1</div>
            <div class="step-info">
                <div class="step-title">{ic}&nbsp; Certificado Digital</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        pfx_file = st.file_uploader(
            "pfx_upload", type=["pfx", "p12"],
            label_visibility="collapsed",
            key="pfx_uploader",
            help="Certificado A1 (.pfx ou .p12)",
        )

        senha_cert = st.text_input(
            "Senha do certificado",
            type="password",
            placeholder="Senha do .pfx",
            key="senha_pfx",
        )

        if pfx_file:
            ic_ok = icon("check-circle", 14, "#10B981")
            st.markdown(
                f'<div style="color:#10B981;font-size:.82rem;font-weight:600;padding:4px 0;">'
                f'{ic_ok}&nbsp; {pfx_file.name} carregado</div>',
                unsafe_allow_html=True,
            )

    # ── ETAPA 2 — Parâmetros ─────────────────────────────────────────────────
    with st.container(border=True):
        ic = icon("settings", 16, "#00CED1")
        st.markdown(f"""
        <div class="step-header">
            <div class="step-num">2</div>
            <div class="step-info">
                <div class="step-title">{ic}&nbsp; Parametros de Consulta</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_cnpj, col_tipo = st.columns(2, gap="medium")
        with col_cnpj:
            st.markdown(
                '<div style="color:#475569;font-size:.7rem;font-weight:600;'
                'letter-spacing:.4px;text-transform:uppercase;margin-bottom:3px;">'
                'CNPJ do Tomador / Prestador</div>',
                unsafe_allow_html=True,
            )
            cnpj_input = st.text_input(
                "cnpj", placeholder="Ex: 12.345.678/0001-90",
                label_visibility="collapsed", key="cnpj_api",
            )

        with col_tipo:
            st.markdown(
                '<div style="color:#475569;font-size:.7rem;font-weight:600;'
                'letter-spacing:.4px;text-transform:uppercase;margin-bottom:3px;">'
                'Tipo de Nota</div>',
                unsafe_allow_html=True,
            )
            tipo_nota = st.selectbox(
                "tipo", ["tomadas", "emitidas"],
                label_visibility="collapsed", key="tipo_nota",
                format_func=lambda x: "Servicos Tomados" if x == "tomadas" else "Servicos Emitidos",
            )

        col_ini, col_fim = st.columns(2, gap="medium")
        hoje = date.today()
        primeiro_mes = hoje.replace(day=1)

        with col_ini:
            st.markdown(
                '<div style="color:#475569;font-size:.7rem;font-weight:600;'
                'letter-spacing:.4px;text-transform:uppercase;margin-bottom:3px;">'
                'Data Inicial</div>',
                unsafe_allow_html=True,
            )
            data_ini = st.date_input(
                "data_ini", value=primeiro_mes,
                label_visibility="collapsed", key="api_data_ini",
            )

        with col_fim:
            st.markdown(
                '<div style="color:#475569;font-size:.7rem;font-weight:600;'
                'letter-spacing:.4px;text-transform:uppercase;margin-bottom:3px;">'
                'Data Final</div>',
                unsafe_allow_html=True,
            )
            data_fim = st.date_input(
                "data_fim", value=hoje,
                label_visibility="collapsed", key="api_data_fim",
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

        tudo_ok = pfx_file and senha_cert and cnpj_input.strip() and data_ini <= data_fim

        if not tudo_ok:
            ic_info = icon("info", 14, "#484F58")
            st.markdown(
                f'<div style="color:#475569;font-size:.8rem;margin-bottom:.6rem;">'
                f'{ic_info}&nbsp; Preencha certificado, senha, CNPJ e periodo para liberar o download.</div>',
                unsafe_allow_html=True,
            )

        btn_baixar = st.button(
            "Baixar XMLs via API NFS-e",
            disabled=not tudo_ok,
            use_container_width=True,
            type="primary",
            key="btn_baixar_api",
        )

        if btn_baixar:
            from core.api_nfse import baixar_xmls_nfse
            from datetime import datetime

            progress_bar = st.progress(0, text="Conectando na API NFS-e...")
            log_placeholder = st.empty()

            def atualizar_progress(frac: float):
                pct = int(frac * 100)
                progress_bar.progress(frac, text=f"Baixando XMLs... {pct}%")

            try:
                zip_bytes, log = baixar_xmls_nfse(
                    pfx_bytes=pfx_file.read(),
                    senha=senha_cert,
                    cnpj=cnpj_input.strip(),
                    data_ini=data_ini,
                    data_fim=data_fim,
                    tipo=tipo_nota,
                    progress_cb=atualizar_progress,
                )

                progress_bar.progress(1.0, text="Concluído!")

                with st.expander("Log de download", expanded=True):
                    st.code("\n".join(log), language="")

                if zip_bytes:
                    nome_zip = (
                        f"nfse_{tipo_nota}_{cnpj_input[:8]}_"
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
                        f'<span class="box-text">Nenhuma nota encontrada no período informado.</span></div>',
                        unsafe_allow_html=True,
                    )

            except Exception as exc:
                progress_bar.empty()
                ic_err = icon("x-circle", 15, "#D93025")
                st.markdown(
                    f'<div class="error-box">{ic_err}'
                    f'<span class="box-text">Erro ao conectar na API: {exc}</span></div>',
                    unsafe_allow_html=True,
                )

    st.markdown("""
    <div class="footer">
        Conversor NFS-e &nbsp;v2.0 &nbsp;&middot;&nbsp; API NFS-e Nacional
        &nbsp;&middot;&nbsp; webservices.nfse.gov.br
    </div>
    """, unsafe_allow_html=True)
