"""
views/arquivo_fortes.py — Conversor NFS-e XML → Arquivo Fortes (.fs)
"""

import streamlit as st
from datetime import date
from assets.icons import icon
from views import nav


def _navbar():
    nav.render("arquivo_fortes")


def render():
    _navbar()

    ic_title = icon("file-text", 20, "#00CED1")
    st.markdown(f"""
    <div style="padding:20px 0 4px;">
        <div style="font-size:1.45rem;font-weight:800;color:#E6EDF3;font-family:Manrope,sans-serif;">
            {ic_title}&nbsp; Arquivo Fortes
        </div>
        <div style="color:#8B949E;font-size:.85rem;margin-top:4px;">
            Converte XMLs de NFS-e Nacional para o formato de importação ACFiscal (.fs)
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Step 1: Upload XMLs ────────────────────────────────────────────────
    with st.container(border=True):
        ic = icon("upload", 16, "#00CED1")
        st.markdown(f"""
        <div class="step-header">
            <div class="step-num">1</div>
            <div class="step-info">
                <div class="step-title">{ic}&nbsp; Selecionar XMLs</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        arquivos = st.file_uploader(
            "xmls_upload",
            type=["xml"],
            accept_multiple_files=True,
            label_visibility="collapsed",
            key="fortes_xmls",
        )
        if arquivos:
            ic_ok = icon("check-circle", 13, "#10B981")
            st.markdown(
                f'<div style="color:#10B981;font-size:.78rem;margin-top:2px;">'
                f'{ic_ok}&nbsp; {len(arquivos)} arquivo(s) selecionado(s)</div>',
                unsafe_allow_html=True,
            )

    # ── Step 2: Configurações ──────────────────────────────────────────────
    with st.container(border=True):
        ic = icon("settings", 16, "#00CED1")
        st.markdown(f"""
        <div class="step-header">
            <div class="step-num">2</div>
            <div class="step-info">
                <div class="step-title">{ic}&nbsp; Configurações</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2, gap="medium")
        with col1:
            st.markdown(_label("Nome da Empresa (Tomador)"), unsafe_allow_html=True)
            nome_empresa = st.text_input(
                "nome_empresa",
                placeholder="ex: POSTO CEARA LTDA",
                label_visibility="collapsed",
                key="fortes_nome_empresa",
            )
        with col2:
            st.markdown(_label("Código de Serviço Fortes"), unsafe_allow_html=True)
            cod_servico = st.text_input(
                "cod_servico",
                placeholder="ex: 10001 (deixe em branco se não souber)",
                label_visibility="collapsed",
                key="fortes_cod_servico",
            )

        st.markdown(_label("Observação (opcional)"), unsafe_allow_html=True)
        observacao = st.text_input(
            "observacao",
            value="NFS-e Importacao",
            label_visibility="collapsed",
            key="fortes_observacao",
        )

        ic_info = icon("info", 13, "#475569")
        st.markdown(
            f'<div style="color:#475569;font-size:.72rem;margin-top:6px;">'
            f'{ic_info}&nbsp; O código de serviço é um código interno do sistema Fortes '
            f'(ex.: 10001, 10013). Consulte a tabela de serviços cadastrada no seu Fortes.</div>',
            unsafe_allow_html=True,
        )

    # ── Step 3: Gerar ─────────────────────────────────────────────────────
    with st.container(border=True):
        ic = icon("download", 16, "#00CED1")
        st.markdown(f"""
        <div class="step-header">
            <div class="step-num">3</div>
            <div class="step-info">
                <div class="step-title">{ic}&nbsp; Gerar Arquivo</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        btn_gerar = st.button(
            "Gerar Arquivo Fortes (.fs)",
            disabled=(not arquivos or not nome_empresa.strip()),
            use_container_width=True,
            type="primary",
            key="btn_gerar_fortes",
        )

        if not nome_empresa.strip() and arquivos:
            ic_warn = icon("alert-triangle", 13, "#C97400")
            st.markdown(
                f'<div style="color:#C97400;font-size:.75rem;margin-top:4px;">'
                f'{ic_warn}&nbsp; Preencha o nome da empresa para continuar.</div>',
                unsafe_allow_html=True,
            )

        if btn_gerar:
            from core.fortes_converter import parse_nfse_xml, gerar_fortes

            notas = []
            erros = []

            with st.spinner("Processando XMLs..."):
                for arq in arquivos:
                    try:
                        xml_bytes = arq.read()
                        nota = parse_nfse_xml(xml_bytes)
                        notas.append(nota)
                    except Exception as exc:
                        erros.append(f"{arq.name}: {exc}")

            if erros:
                ic_err = icon("x-circle", 15, "#D93025")
                for e in erros:
                    st.markdown(
                        f'<div class="error-box">{ic_err}'
                        f'<span class="box-text">{e}</span></div>',
                        unsafe_allow_html=True,
                    )

            if notas:
                try:
                    conteudo = gerar_fortes(
                        notas=notas,
                        nome_empresa=nome_empresa.strip(),
                        observacao=observacao.strip() or "NFS-e Importacao",
                        cod_servico=cod_servico.strip(),
                    )

                    hoje = date.today().strftime("%Y%m%d")
                    nome_arq = f"fortes_nfse_{hoje}.fs"
                    tamanho  = len(conteudo.encode("utf-8"))

                    ic_ok = icon("check-circle", 32, "#1AB87A")
                    st.markdown(f"""
                    <div class="result-success">
                        <div class="result-success-icon">{ic_ok}</div>
                        <div>
                            <div class="result-success-title">Arquivo gerado com sucesso!</div>
                            <div class="result-success-meta">
                                {len(notas)} nota(s) &nbsp;&middot;&nbsp;
                                {round(tamanho / 1024, 1)} KB &nbsp;&middot;&nbsp; {nome_arq}
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    st.download_button(
                        label=f"Baixar  {nome_arq}",
                        data=conteudo.encode("utf-8"),
                        file_name=nome_arq,
                        mime="text/plain",
                        use_container_width=True,
                    )

                    # Preview
                    with st.expander("Pré-visualização do arquivo (.fs)", expanded=False):
                        preview_lines = conteudo.splitlines()[:40]
                        st.code("\n".join(preview_lines), language="")
                        if len(conteudo.splitlines()) > 40:
                            st.caption(f"… {len(conteudo.splitlines()) - 40} linhas omitidas")

                except Exception as exc:
                    ic_err = icon("x-circle", 15, "#D93025")
                    st.markdown(
                        f'<div class="error-box">{ic_err}'
                        f'<span class="box-text">Erro ao gerar arquivo: {exc}</span></div>',
                        unsafe_allow_html=True,
                    )
            elif not erros:
                ic_warn = icon("alert-triangle", 15, "#C77D0A")
                st.markdown(
                    f'<div class="warn-box">{ic_warn}'
                    f'<span class="box-text">Nenhuma nota válida encontrada nos arquivos.</span></div>',
                    unsafe_allow_html=True,
                )

    st.markdown("""
    <div class="footer">
        Conversor NFS-e &nbsp;v2.0 &nbsp;&middot;&nbsp; Arquivo Fortes ACFiscal
    </div>
    """, unsafe_allow_html=True)


def _label(text: str) -> str:
    return (
        '<div style="color:#475569;font-size:.7rem;font-weight:600;'
        'letter-spacing:.4px;text-transform:uppercase;margin-bottom:3px;">'
        f'{text}</div>'
    )
