"""
pages/certificados.py — Gerenciar certificados digitais salvos por usuário
"""

import streamlit as st
from auth.security import current_user, is_admin, logout
from assets.icons import icon
from db.database import salvar_certificado, listar_certificados, remover_certificado
from core.api_nfse import extrair_cnpj_do_pfx


def _navbar():
    user    = current_user()
    inicial = user["name"][0].upper() if user["name"] else "U"

    st.markdown(f"""
    <div class="topbar">
        <div class="topbar-logo">{icon("zap", 16, "#fff")}</div>
        <span class="topbar-name">Conversor NFS-e</span>
        <div class="topbar-spacer"></div>
        <div class="topbar-divider"></div>
        <span class="topbar-tag">Certificados Digitais</span>
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
        if st.button("Conversor", key="nav_conv_cert", use_container_width=True):
            st.session_state.pagina = "conversor"; st.rerun()
    with c3:
        if st.button("Baixar XMLs", key="nav_bx_cert", use_container_width=True):
            st.session_state.pagina = "baixar_xmls"; st.rerun()
    with c4:
        if st.button("Notas do Milhão", key="nav_mil_cert", use_container_width=True):
            st.session_state.pagina = "milhao"; st.rerun()
    with c5:
        if st.button("Dashboard", key="nav_dash_cert", use_container_width=True):
            st.session_state.pagina = "dashboard"; st.rerun()

    if is_admin():
        with c6:
            if st.button("Usuarios", key="nav_usr_cert", use_container_width=True):
                st.session_state.pagina = "usuarios"; st.rerun()
        with c7:
            if st.button("Sair", key="logout_cert", use_container_width=True):
                logout()
    else:
        with c6:
            if st.button("Sair", key="logout_cert", use_container_width=True):
                logout()

    st.markdown('<div style="height:.6rem;"></div>', unsafe_allow_html=True)


def render():
    _navbar()
    user = current_user()

    # ── Lista de certificados salvos ──────────────────────────────────────────
    with st.container(border=True):
        ic = icon("shield", 16, "#00CED1")
        st.markdown(f"""
        <div class="step-header">
            <div class="step-num">1</div>
            <div class="step-info">
                <div class="step-title">{ic}&nbsp; Meus Certificados</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        certs = listar_certificados(user["username"])

        if not certs:
            ic_info = icon("info", 14, "#484F58")
            st.markdown(
                f'<div style="color:#475569;font-size:.8rem;">'
                f'{ic_info}&nbsp; Nenhum certificado salvo ainda. Adicione abaixo.</div>',
                unsafe_allow_html=True,
            )
        else:
            for cert in certs:
                cnpj_fmt = cert["cnpj"]
                if len(cnpj_fmt) == 14:
                    cnpj_fmt = (f"{cnpj_fmt[:2]}.{cnpj_fmt[2:5]}.{cnpj_fmt[5:8]}"
                                f"/{cnpj_fmt[8:12]}-{cnpj_fmt[12:]}")
                col_info, col_btn = st.columns([5, 1])
                with col_info:
                    ic_ok = icon("check-circle", 14, "#10B981")
                    st.markdown(
                        f'<div style="padding:6px 0;font-size:.85rem;">'
                        f'{ic_ok}&nbsp; <b>{cert["razao_social"] or cnpj_fmt}</b>'
                        f' &nbsp;<span style="color:#475569">{cnpj_fmt}</span>'
                        f' &nbsp;<span style="color:#475569;font-size:.75rem;">— salvo em {cert["criado_em"][:10]}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                with col_btn:
                    if st.button("Remover", key=f"rem_{cert['cnpj']}", use_container_width=True):
                        remover_certificado(user["username"], cert["cnpj"])
                        st.toast(f"Certificado {cnpj_fmt} removido.")
                        st.rerun()

    # ── Adicionar certificado ─────────────────────────────────────────────────
    with st.container(border=True):
        ic = icon("plus-circle", 16, "#00CED1")
        st.markdown(f"""
        <div class="step-header">
            <div class="step-num">2</div>
            <div class="step-info">
                <div class="step-title">{ic}&nbsp; Adicionar Certificado</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        ic_info = icon("info", 13, "#475569")
        st.markdown(
            f'<div style="color:#475569;font-size:.75rem;margin-bottom:8px;">'
            f'{ic_info}&nbsp; O certificado é salvo <b>criptografado</b> — '
            f'apenas você pode usá-lo. Faça isso uma vez por empresa.</div>',
            unsafe_allow_html=True,
        )

        pfx_file   = st.file_uploader(
            "pfx_add", type=["pfx", "p12"],
            label_visibility="collapsed",
            key="pfx_add_uploader",
            help="Certificado A1 (.pfx ou .p12)",
        )
        senha_add = st.text_input(
            "Senha do certificado",
            type="password",
            placeholder="Senha do .pfx",
            key="senha_add",
        )

        # Auto-extrai CNPJ e razão social ao preencher cert+senha
        cnpj_detectado   = ""
        razao_detectada  = ""
        if pfx_file and senha_add:
            cache_key = f"_add_{pfx_file.name}_{senha_add}"
            if st.session_state.get("_add_cache_key") != cache_key:
                try:
                    pfx_bytes = pfx_file.read(); pfx_file.seek(0)
                    from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates
                    import re
                    _, cert, _ = load_key_and_certificates(pfx_bytes, senha_add.encode())
                    from cryptography.x509.oid import NameOID
                    cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
                    # CN format: "RAZAO SOCIAL:CNPJ" ou só "RAZAO SOCIAL"
                    parts = cn.split(":")
                    razao_detectada = parts[0].strip()
                    cnpj_detectado  = re.sub(r"\D", "", parts[-1])[:14] if len(parts) > 1 else ""
                    if not cnpj_detectado or len(cnpj_detectado) != 14:
                        cnpj_detectado = extrair_cnpj_do_pfx(pfx_bytes, senha_add)
                    st.session_state["_add_cnpj"]       = cnpj_detectado
                    st.session_state["_add_razao"]      = razao_detectada
                    st.session_state["_add_cache_key"]  = cache_key
                except Exception:
                    pass
            cnpj_detectado  = st.session_state.get("_add_cnpj", "")
            razao_detectada = st.session_state.get("_add_razao", "")

        if cnpj_detectado:
            cnpj_fmt = (f"{cnpj_detectado[:2]}.{cnpj_detectado[2:5]}.{cnpj_detectado[5:8]}"
                        f"/{cnpj_detectado[8:12]}-{cnpj_detectado[12:]}")
            ic_ok = icon("check-circle", 14, "#10B981")
            st.markdown(
                f'<div style="color:#10B981;font-size:.82rem;font-weight:600;padding:4px 0;">'
                f'{ic_ok}&nbsp; {razao_detectada or "—"} &nbsp;·&nbsp; CNPJ: {cnpj_fmt}</div>',
                unsafe_allow_html=True,
            )

        btn_salvar = st.button(
            "Salvar certificado",
            disabled=not (pfx_file and senha_add and cnpj_detectado),
            use_container_width=True,
            type="primary",
            key="btn_salvar_cert",
        )

        if btn_salvar:
            pfx_file.seek(0)
            ok = salvar_certificado(
                usuario=user["username"],
                cnpj=cnpj_detectado,
                razao_social=razao_detectada,
                pfx_bytes=pfx_file.read(),
                senha=senha_add,
            )
            if ok:
                st.toast(f"Certificado salvo com sucesso!")
                # Limpa cache
                for k in ("_add_cnpj", "_add_razao", "_add_cache_key"):
                    st.session_state.pop(k, None)
                st.rerun()
            else:
                st.error("Erro ao salvar certificado.")

    st.markdown("""
    <div class="footer">
        Conversor NFS-e &nbsp;v2.0 &nbsp;&middot;&nbsp; Certificados criptografados com Fernet AES-128
    </div>
    """, unsafe_allow_html=True)
