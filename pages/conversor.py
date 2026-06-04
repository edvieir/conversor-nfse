"""
pages/conversor.py — Tela principal de conversão XML → TXT / XLSX
"""

import streamlit as st
from datetime import datetime
from auth.security import current_user, is_admin, logout
from pages import nav
from core.conversor_txt  import processar_uploads, conversor_disponivel
from core.conversor_xlsx import processar_xlsx_sped
from db.database import log_conversion
from assets.icons import icon


def render():
    _ok, _err = conversor_disponivel()
    if not _ok:
        st.error(f"Nao foi possivel carregar o modulo de conversao:\n\n`{_err}`")
        st.stop()

    nav.render("conversor")

    # Page header
    st.markdown("""
<div style="margin-bottom:2rem;">
  <h1 style="color:#dce1fb;font-size:2rem;font-weight:800;letter-spacing:-.02em;margin:0 0 6px;font-family:Manrope,sans-serif;">Processar Lote NFS-e</h1>
  <p style="color:#849396;font-size:.95rem;margin:0;font-family:Manrope,sans-serif;">Siga o fluxo de 3 passos para validar e converter seus arquivos XML para o formato de destino.</p>
</div>
""", unsafe_allow_html=True)

    # Chave dinâmica para limpeza do uploader
    if "upload_key" not in st.session_state:
        st.session_state["upload_key"] = 0

    # ── ETAPA 1 — Upload ──────────────────────────────────────────────────────
    with st.container(border=True):
        ic_folder = icon("folder", 16, "#00CED1")
        st.markdown(f"""
        <div class="step-header">
            <div class="step-num">1</div>
            <div class="step-info">
                <div class="step-title">{ic_folder}&nbsp; Arquivos XML</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        uploaded = st.file_uploader(
            "xml_upload", type=["xml"],
            accept_multiple_files=True,
            label_visibility="collapsed",
            key=f"uploader_{st.session_state['upload_key']}",
        )

        n_atual = len(uploaded) if uploaded else 0
        if n_atual != st.session_state.get("_n_xml_prev", 0):
            if n_atual > 0:
                st.toast(
                    f"{n_atual} arquivo{'s' if n_atual > 1 else ''} carregado{'s' if n_atual > 1 else ''}",
                )
            st.session_state["_n_xml_prev"] = n_atual

        if uploaded:
            total = len(uploaded)
            col_status, col_limpar = st.columns([5, 1])
            with col_status:
                ic_chk = icon("check-circle", 14, "#10B981")
                st.markdown(
                    f'<div style="color:#10B981;font-size:.82rem;font-weight:600;padding:4px 0;">'
                    f'{ic_chk}&nbsp; {total} arquivo{"s" if total > 1 else ""} '
                    f'selecionado{"s" if total > 1 else ""}</div>',
                    unsafe_allow_html=True,
                )
            with col_limpar:
                if st.button("Limpar", key="btn_clear", use_container_width=True,
                             help="Remover todos os arquivos"):
                    st.session_state["upload_key"] += 1
                    st.session_state["_n_xml_prev"] = 0
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

        col_im, col_comp = st.columns(2, gap="medium")
        with col_im:
            st.markdown(
                '<div style="color:#475569;font-size:.7rem;font-weight:600;'
                'letter-spacing:.4px;text-transform:uppercase;margin-bottom:3px;">'
                'Inscricao Municipal</div>',
                unsafe_allow_html=True,
            )
            im_input = st.text_input("im", placeholder="Ex: 12345678-0",
                                     label_visibility="collapsed")
            if not im_input.strip():
                ic_warn = icon("alert-triangle", 13, "#C97400")
                st.markdown(
                    f'<div style="color:#C97400;font-size:.72rem;margin-top:3px;">'
                    f'{ic_warn}&nbsp; Obrigatoria para gerar TXT (ISS Fortaleza)</div>',
                    unsafe_allow_html=True,
                )
        with col_comp:
            st.markdown(
                '<div style="color:#475569;font-size:.7rem;font-weight:600;'
                'letter-spacing:.4px;text-transform:uppercase;margin-bottom:3px;">'
                'Competencia</div>',
                unsafe_allow_html=True,
            )
            comp_input = st.text_input("comp", placeholder="Ex: 05/2026  (opcional)",
                                       label_visibility="collapsed")

    # ── ETAPA 3 — Gerar arquivo ───────────────────────────────────────────────
    tem_arquivos = bool(uploaded)

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

        if not tem_arquivos:
            ic_info = icon("info", 14, "#484F58")
            st.markdown(
                f'<div style="color:#475569;font-size:.8rem;margin-bottom:.6rem;">'
                f'{ic_info}&nbsp; Faca o upload dos XMLs na etapa 1 para liberar a conversao.</div>',
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
                disabled=not tem_arquivos or not im_input.strip(),
                use_container_width=True, type="primary", key="btn_txt",
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
                disabled=not tem_arquivos,
                use_container_width=True, type="primary", key="btn_xlsx",
            )

    # ── Validação de competência ──────────────────────────────────────────────
    comp_filtro = ""
    if comp_input.strip():
        try:
            parts = comp_input.strip().replace(".", "/").split("/")
            if len(parts) == 2:
                mes, ano = int(parts[0]), int(parts[1])
                if 1 <= mes <= 12 and ano >= 2020:
                    comp_filtro = f"{mes:02d}/{ano}"
        except (ValueError, IndexError):
            pass
        if not comp_filtro:
            ic_warn = icon("alert-triangle", 15, "#C77D0A")
            st.markdown(
                f'<div class="warn-box">{ic_warn}'
                f'<span class="box-text">Competencia invalida — use MM/AAAA (ex: 05/2026).</span></div>',
                unsafe_allow_html=True,
            )

    # ── Processamento ─────────────────────────────────────────────────────────
    if btn_txt or btn_xlsx:
        if not uploaded:
            ic_warn = icon("alert-triangle", 15, "#C77D0A")
            st.markdown(
                f'<div class="warn-box">{ic_warn}'
                f'<span class="box-text">Selecione pelo menos um arquivo XML na Etapa 1.</span></div>',
                unsafe_allow_html=True,
            )
        else:
            modo       = "txt" if btn_txt else "xlsx"
            tipo_label = "ISS Fortaleza (TXT)" if modo == "txt" else "SPED GOV (XLSX)"

            with st.spinner(f"Processando {len(uploaded)} arquivo(s) — {tipo_label}..."):
                if modo == "xlsx":
                    dados_saida, log = processar_xlsx_sped(uploaded, "", comp_filtro)
                else:
                    im = im_input.strip()
                    dados_saida, log = processar_uploads(uploaded, im, modo, comp_filtro)

            # Registra no banco
            log_conversion(
                usuario=user["username"],
                modo=modo,
                qtd=len(uploaded),
                sucesso=bool(dados_saida),
            )

            if dados_saida:
                ext        = "txt" if modo == "txt" else "xlsx"
                mime       = ("text/plain" if modo == "txt"
                              else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                nome       = f"nfse_{modo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
                tamanho_kb = round(len(dados_saida) / 1024, 1)
                ic_file    = icon("file-text" if modo == "txt" else "bar-chart",
                                  18, "#1AB87A")

                st.toast(f"Arquivo {tipo_label} gerado com sucesso!")

                ic_ok = icon("check-circle", 32, "#1AB87A")
                st.markdown(f"""
                <div class="result-success">
                    <div class="result-success-icon">{ic_ok}</div>
                    <div>
                        <div class="result-success-title">Arquivo gerado com sucesso!</div>
                        <div class="result-success-meta">
                            {ic_file} {nome} &nbsp;&middot;&nbsp; {tamanho_kb} KB
                            &nbsp;&middot;&nbsp;
                            {len(uploaded)} XML{'s' if len(uploaded) > 1 else ''} processado{'s' if len(uploaded) > 1 else ''}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                st.download_button(
                    label=f"Baixar  {nome}",
                    data=dados_saida, file_name=nome, mime=mime,
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
                st.code(log.strip() if log.strip() else "(nenhuma saida registrada)", language="")

    st.markdown("""
    <div class="footer">
        Conversor NFS-e &nbsp;v2.0 &nbsp;&middot;&nbsp; Modelo Nacional 2026
        &nbsp;&middot;&nbsp; ISS Fortaleza / SPED GOV
    </div>
    """, unsafe_allow_html=True)
