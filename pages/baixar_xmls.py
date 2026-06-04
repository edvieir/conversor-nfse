"""
pages/baixar_xmls.py — Tela "Baixar XMLs" via API NFS-e Nacional
"""

import streamlit as st
from datetime import date
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
        c1, c2, c3, c4, c5, c6 = st.columns([2.8, 1.3, 1.3, 1.3, 1.3, 1.0])
    else:
        c1, c2, c3, c4, c5 = st.columns([2.8, 1.3, 1.3, 1.3, 1.0])

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
        if st.button("Milhao", key="nav_milhao_bx", use_container_width=True):
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
                <div class="step-title">{ic}&nbsp; Certificado Digital (A1)</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        pfx_file = st.file_uploader(
            "pfx_upload", type=["pfx", "p12"],
            label_visibility="collapsed",
            key="pfx_uploader",
            help="Certificado A1 — arquivo .pfx ou .p12",
        )

        senha_cert = st.text_input(
            "Senha do certificado",
            type="password",
            placeholder="Senha do .pfx",
            key="senha_pfx",
        )

        # Auto-extrai CNPJ assim que cert + senha estão preenchidos
        cnpj_auto = ""
        if pfx_file and senha_cert:
            if st.session_state.get("_pfx_nome") != pfx_file.name or \
               st.session_state.get("_pfx_senha") != senha_cert:
                from core.api_nfse import extrair_cnpj_do_pfx
                cnpj_auto = extrair_cnpj_do_pfx(pfx_file.read(), senha_cert)
                pfx_file.seek(0)
                st.session_state["_cnpj_cert"] = cnpj_auto
                st.session_state["_pfx_nome"]  = pfx_file.name
                st.session_state["_pfx_senha"] = senha_cert
            else:
                cnpj_auto = st.session_state.get("_cnpj_cert", "")

        if pfx_file:
            ic_ok = icon("check-circle", 14, "#10B981")
            cnpj_fmt = (
                f"{cnpj_auto[:2]}.{cnpj_auto[2:5]}.{cnpj_auto[5:8]}"
                f"/{cnpj_auto[8:12]}-{cnpj_auto[12:]}"
                if len(cnpj_auto) == 14 else "CNPJ não encontrado no cert"
            )
            st.markdown(
                f'<div style="color:#10B981;font-size:.82rem;font-weight:600;padding:4px 0;">'
                f'{ic_ok}&nbsp; {pfx_file.name}'
                + (f' &nbsp;&middot;&nbsp; CNPJ: <b>{cnpj_fmt}</b>' if cnpj_auto else "")
                + '</div>',
                unsafe_allow_html=True,
            )

    # ── ETAPA 2 — Parâmetros ─────────────────────────────────────────────────
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

        ic_info = icon("info", 13, "#475569")
        st.markdown(
            f'<div style="color:#475569;font-size:.72rem;margin-top:6px;">'
            f'{ic_info}&nbsp; Sempre baixa <b>Servicos Tomados</b> — tipo definido pelo certificado</div>',
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

        tudo_ok = pfx_file and senha_cert and data_ini <= data_fim

        if not tudo_ok:
            ic_info = icon("info", 14, "#484F58")
            st.markdown(
                f'<div style="color:#475569;font-size:.8rem;margin-bottom:.6rem;">'
                f'{ic_info}&nbsp; Faca o upload do certificado e informe a senha para liberar.</div>',
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

            progress_bar = st.progress(0, text="Conectando na API NFS-e...")

            def atualizar_progress(frac: float):
                progress_bar.progress(frac, text=f"Baixando XMLs... {int(frac*100)}%")

            try:
                pfx_file.seek(0)
                zip_bytes, log = baixar_xmls_nfse(
                    pfx_bytes=pfx_file.read(),
                    senha=senha_cert,
                    cnpj=cnpj_auto,
                    data_ini=data_ini,
                    data_fim=data_fim,
                    tipo="tomadas",
                    progress_cb=atualizar_progress,
                )

                progress_bar.progress(1.0, text="Concluído!")

                with st.expander("Log de download", expanded=not bool(zip_bytes)):
                    st.code("\n".join(log), language="")

                if zip_bytes:
                    cnpj_id  = cnpj_auto[:8] if cnpj_auto else "cnpj"
                    nome_zip = (
                        f"nfse_tomadas_{cnpj_id}_"
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
                    f'<span class="box-text">Erro: {exc}</span></div>',
                    unsafe_allow_html=True,
                )

    st.markdown("""
    <div class="footer">
        Conversor NFS-e &nbsp;v2.0 &nbsp;&middot;&nbsp; API NFS-e Nacional
        &nbsp;&middot;&nbsp; api.nfse.gov.br
    </div>
    """, unsafe_allow_html=True)
