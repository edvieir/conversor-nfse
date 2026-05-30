"""
pages/milhao.py — Página "Notas do Milhão"
Converte CSV exportado pelo portal ISS Fortaleza para TXT e XLSX SPED GOV.
Aba completamente separada do Conversor XML existente.
"""

import streamlit as st
from datetime import datetime
from auth.security import current_user, is_admin, logout
from core.conversor_milhao import processar_csv_txt, processar_csv_xlsx
from db.database import log_conversion
from assets.icons import icon


def render():
    user    = current_user()
    inicial = user["name"][0].upper() if user["name"] else "U"

    # ── Top bar ──────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="topbar">
        <div class="topbar-logo">
            {icon("star", 16, "#fff")}
        </div>
        <span class="topbar-name">Conversor NFS-e</span>
        <div class="topbar-spacer"></div>
        <div class="topbar-divider"></div>
        <span class="topbar-tag">Notas do Milhão &middot; CSV ISS Fortaleza</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Navbar ───────────────────────────────────────────────────────────────
    if is_admin():
        _nc1, _nc2, _nc3, _nc4, _nc5 = st.columns([3, 1.3, 1.3, 1.3, 1.1])
    else:
        _nc1, _nc2, _nc3, _nc4 = st.columns([3.5, 1.5, 1.5, 1.1])

    with _nc1:
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:8px;padding:6px 0;">
            <div class="navbar-avatar">{inicial}</div>
            <span class="navbar-name">{user["name"]}</span>
        </div>""", unsafe_allow_html=True)

    with _nc2:
        if st.button("Conversor", key="nav_conv_milhao", use_container_width=True):
            st.session_state.pagina = "conversor"
            st.rerun()

    with _nc3:
        if st.button("Dashboard", key="nav_dash_milhao", use_container_width=True):
            st.session_state.pagina = "dashboard"
            st.rerun()

    if is_admin():
        with _nc4:
            if st.button("Usuarios", key="nav_users_milhao", use_container_width=True):
                st.session_state.pagina = "usuarios"
                st.rerun()
        with _nc5:
            if st.button("Sair", key="logout_milhao", use_container_width=True):
                logout()
    else:
        with _nc4:
            if st.button("Sair", key="logout_milhao", use_container_width=True):
                logout()

    st.markdown('<div style="height:.6rem;"></div>', unsafe_allow_html=True)

    # ── Chave dinâmica do uploader ────────────────────────────────────────────
    if "milhao_upload_key" not in st.session_state:
        st.session_state["milhao_upload_key"] = 0

    # ── ETAPA 1 — Upload CSV ─────────────────────────────────────────────────
    with st.container(border=True):
        ic_folder = icon("folder", 16, "#00CED1")
        st.markdown(f"""
        <div class="step-header">
            <div class="step-num">1</div>
            <div class="step-info">
                <div class="step-title">{ic_folder}&nbsp; Arquivo CSV (Notas do Milhao)</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        uploaded = st.file_uploader(
            "csv_upload",
            type=["csv"],
            accept_multiple_files=False,
            label_visibility="collapsed",
            key=f"milhao_uploader_{st.session_state['milhao_upload_key']}",
        )

        n_atual = 1 if uploaded else 0
        if n_atual != st.session_state.get("_n_csv_prev", 0):
            if n_atual > 0:
                st.toast("Arquivo CSV carregado!")
            st.session_state["_n_csv_prev"] = n_atual

        if uploaded:
            col_status, col_limpar = st.columns([5, 1])
            with col_status:
                ic_chk = icon("check-circle", 14, "#10B981")
                st.markdown(
                    f'<div style="color:#10B981;font-size:.82rem;font-weight:600;'
                    f'padding:4px 0;">'
                    f'{ic_chk}&nbsp; {uploaded.name} selecionado</div>',
                    unsafe_allow_html=True,
                )
            with col_limpar:
                if st.button("Limpar", key="btn_clear_milhao",
                             use_container_width=True, help="Remover o arquivo"):
                    st.session_state["milhao_upload_key"] += 1
                    st.session_state["_n_csv_prev"] = 0
                    st.rerun()

    # ── ETAPA 2 — Parâmetros ─────────────────────────────────────────────────
    with st.container(border=True):
        ic_settings = icon("settings", 16, "#00CED1")
        st.markdown(f"""
        <div class="step-header">
            <div class="step-num">2</div>
            <div class="step-info">
                <div class="step-title">{ic_settings}&nbsp; Parametros</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(
            '<div style="color:#475569;font-size:.7rem;font-weight:600;'
            'letter-spacing:.4px;text-transform:uppercase;margin-bottom:3px;">'
            'Inscricao Municipal (para TXT)</div>',
            unsafe_allow_html=True,
        )
        im_input = st.text_input(
            "im_milhao",
            placeholder="Ex: 12345678-0",
            label_visibility="collapsed",
        )
        if not im_input.strip():
            ic_warn = icon("alert-triangle", 13, "#C97400")
            st.markdown(
                f'<div style="color:#C97400;font-size:.72rem;margin-top:3px;">'
                f'{ic_warn}&nbsp; Obrigatoria para gerar TXT (ISS Fortaleza)</div>',
                unsafe_allow_html=True,
            )

    # ── ETAPA 3 — Gerar ──────────────────────────────────────────────────────
    tem_arquivo = bool(uploaded)

    with st.container(border=True):
        ic_download = icon("download", 16, "#00CED1")
        st.markdown(f"""
        <div class="step-header">
            <div class="step-num">3</div>
            <div class="step-info">
                <div class="step-title">{ic_download}&nbsp; Gerar arquivo</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if not tem_arquivo:
            ic_info = icon("info", 14, "#484F58")
            st.markdown(
                f'<div style="color:#475569;font-size:.8rem;margin-bottom:.6rem;">'
                f'{ic_info}&nbsp; Faca o upload do CSV na etapa 1 para '
                f'liberar a conversao.</div>',
                unsafe_allow_html=True,
            )

        col1, col2 = st.columns(2, gap="medium")
        ic_txt  = icon("file-text", 40, "#00CED1")
        ic_xlsx = icon("bar-chart",  40, "#7B3FE4")

        with col1:
            st.markdown(f"""
            <div class="format-card">
                <div class="format-svg">{ic_txt}</div>
                <div class="format-name">ISS Fortaleza</div>
                <div class="format-desc">Arquivo TXT para importacao no portal ISS Fortaleza</div>
            </div>
            """, unsafe_allow_html=True)
            btn_txt = st.button(
                "Gerar TXT",
                disabled=not tem_arquivo or not im_input.strip(),
                use_container_width=True,
                type="primary",
                key="btn_milhao_txt",
            )

        with col2:
            st.markdown(f"""
            <div class="format-card">
                <div class="format-svg">{ic_xlsx}</div>
                <div class="format-name">SPED GOV</div>
                <div class="format-desc">Planilha XLSX — Servicos Tomados (layout SPED)</div>
            </div>
            """, unsafe_allow_html=True)
            btn_xlsx = st.button(
                "Gerar XLSX",
                disabled=not tem_arquivo,
                use_container_width=True,
                type="primary",
                key="btn_milhao_xlsx",
            )

    # ── Processamento ─────────────────────────────────────────────────────────
    if btn_txt or btn_xlsx:
        modo       = "txt" if btn_txt else "xlsx"
        tipo_label = "ISS Fortaleza (TXT)" if modo == "txt" else "SPED GOV (XLSX)"

        uploaded.seek(0)
        conteudo = uploaded.read()

        with st.spinner(f"Processando CSV — {tipo_label}..."):
            if modo == "txt":
                dados_saida, log = processar_csv_txt(conteudo, im_input.strip())
            else:
                dados_saida, log = processar_csv_xlsx(conteudo)

        log_conversion(
            usuario=user["username"],
            modo=f"milhao_{modo}",
            qtd=1,
            sucesso=bool(dados_saida),
        )

        if dados_saida:
            ext        = "txt" if modo == "txt" else "xlsx"
            mime       = (
                "text/plain" if modo == "txt"
                else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            nome       = f"milhao_{modo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
            tamanho_kb = round(len(dados_saida) / 1024, 1)
            ic_file    = icon("file-text" if modo == "txt" else "bar-chart", 18, "#1AB87A")

            st.toast(f"Arquivo {tipo_label} gerado com sucesso!")

            ic_ok = icon("check-circle", 32, "#1AB87A")
            st.markdown(f"""
            <div class="result-success">
                <div class="result-success-icon">{ic_ok}</div>
                <div>
                    <div class="result-success-title">Arquivo gerado com sucesso!</div>
                    <div class="result-success-meta">
                        {ic_file} {nome} &nbsp;&middot;&nbsp; {tamanho_kb} KB
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.download_button(
                label=f"Baixar  {nome}",
                data=dados_saida,
                file_name=nome,
                mime=mime,
                use_container_width=True,
            )
        else:
            ic_err = icon("x-circle", 15, "#D93025")
            st.markdown(
                f'<div class="error-box">{ic_err}'
                f'<span class="box-text">Nenhum arquivo foi gerado. '
                f'Verifique o log abaixo.</span></div>',
                unsafe_allow_html=True,
            )

        with st.expander("Ver log de processamento"):
            st.code(
                log.strip() if log.strip() else "(nenhuma saida registrada)",
                language="",
            )

    st.markdown("""
    <div class="footer">
        Conversor NFS-e &nbsp;v2.0 &nbsp;&middot;&nbsp; Notas do Milhao
        &nbsp;&middot;&nbsp; CSV ISS Fortaleza
    </div>
    """, unsafe_allow_html=True)
