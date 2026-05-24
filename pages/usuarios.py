"""
pages/usuarios.py — Gerenciamento de usuários (somente admin)
"""

import streamlit as st
from auth.security import current_user, is_admin, logout, hash_password
from db.database import list_users, create_user, delete_user
from assets.icons import icon


def render():
    if not is_admin():
        st.error("Acesso restrito ao administrador.")
        return

    user    = current_user()
    inicial = user["name"][0].upper() if user["name"] else "U"

    # ── Top bar ──────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="topbar">
        <div class="topbar-logo">
            {icon("shield", 16, "#fff")}
        </div>
        <span class="topbar-name">Conversor NFS-e</span>
        <div class="topbar-spacer"></div>
        <div class="topbar-divider"></div>
        <span class="topbar-tag">Painel Administrativo</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Navbar ───────────────────────────────────────────────────────────────
    _ua1, _ua2, _ua3, _ua4 = st.columns([3, 1.6, 1.6, 1.1])

    with _ua1:
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:8px;padding:6px 0;">
            <div class="navbar-avatar">{inicial}</div>
            <span class="navbar-name">{user["name"]}</span>
        </div>""", unsafe_allow_html=True)

    with _ua2:
        if st.button("Conversor", key="nav_conv_admin", use_container_width=True):
            st.session_state.pagina = "conversor"
            st.rerun()

    with _ua3:
        if st.button("Dashboard", key="nav_dash_admin", use_container_width=True):
            st.session_state.pagina = "dashboard"
            st.rerun()

    with _ua4:
        if st.button("Sair", key="logout_admin", use_container_width=True):
            logout()

    st.markdown('<div style="height:.6rem;"></div>', unsafe_allow_html=True)

    # ── Hero ──────────────────────────────────────────────────────────────────
    ic_users = icon("users", 20, "#E6EDF3")
    st.markdown(f"""
    <div class="admin-hero">
        <div class="admin-hero-title">{ic_users}&nbsp; Gerenciar Usuarios</div>
        <div class="admin-hero-sub">Adicione ou remova logins de acesso ao sistema</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Lista de usuários ─────────────────────────────────────────────────────
    st.markdown("#### Usuarios cadastrados")
    usuarios = list_users()

    if not usuarios:
        ic_warn = icon("alert-triangle", 15, "#C77D0A")
        st.markdown(
            f'<div class="warn-box">{ic_warn}'
            f'<span class="box-text">Nenhum usuario cadastrado.</span></div>',
            unsafe_allow_html=True,
        )
    else:
        linhas = ""
        for u in usuarios:
            badge = (
                '<span class="user-badge user-badge-admin">admin</span>'
                if u["role"] == "admin"
                else '<span class="user-badge">usuario</span>'
            )
            linhas += f"""
            <tr>
                <td>{badge} <strong style="color:#e6edf3">{u["username"]}</strong></td>
                <td>{u["name"]}</td>
                <td>{u["email"] or "—"}</td>
            </tr>"""
        st.markdown(f"""
        <table class="user-table">
            <thead><tr>
                <th>Login</th><th>Nome</th><th>E-mail</th>
            </tr></thead>
            <tbody>{linhas}</tbody>
        </table>
        """, unsafe_allow_html=True)

    st.divider()

    # ── Adicionar usuário ─────────────────────────────────────────────────────
    ic_plus = icon("plus-circle", 16, "#E6EDF3")
    st.markdown(f"#### {ic_plus}&nbsp; Adicionar novo usuario", unsafe_allow_html=True)

    with st.form("form_add_user", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            novo_login = st.text_input("Login *", placeholder="ex: joao")
            novo_nome  = st.text_input("Nome completo *", placeholder="ex: Joao Silva")
        with col2:
            novo_email = st.text_input("E-mail", placeholder="ex: joao@empresa.com")
            nova_senha = st.text_input("Senha *  (min. 6 caracteres)", type="password")
        confirmar_senha = st.text_input("Confirmar senha *", type="password")

        submitted = st.form_submit_button(
            "Criar usuario", use_container_width=True, type="primary"
        )

        if submitted:
            erros_form = []
            logins_existentes = {u["username"] for u in usuarios}

            if not novo_login.strip():
                erros_form.append("Login e obrigatorio.")
            elif " " in novo_login.strip():
                erros_form.append("Login nao pode ter espacos.")
            if not novo_nome.strip():
                erros_form.append("Nome completo e obrigatorio.")
            if len(nova_senha) < 6:
                erros_form.append("Senha deve ter pelo menos 6 caracteres.")
            if nova_senha != confirmar_senha:
                erros_form.append("As senhas nao coincidem.")
            if novo_login.strip().lower() in logins_existentes:
                erros_form.append(f"Ja existe um usuario com o login '{novo_login.strip()}'.")

            if erros_form:
                ic_err = icon("x-circle", 15, "#D93025")
                for e in erros_form:
                    st.markdown(
                        f'<div class="error-box">{ic_err}'
                        f'<span class="box-text">{e}</span></div>',
                        unsafe_allow_html=True,
                    )
            else:
                with st.spinner("Gerando hash da senha..."):
                    hashed = hash_password(nova_senha)
                ok = create_user(
                    novo_login.strip().lower(),
                    novo_nome.strip(),
                    novo_email.strip() or f"{novo_login.strip()}@empresa.com",
                    hashed,
                )
                ic_ok = icon("check-circle", 15, "#1AB87A")
                if ok:
                    st.markdown(
                        f'<div class="success-box">{ic_ok}'
                        f'<span class="box-text">Usuario <strong>{novo_login.strip()}</strong> '
                        f'criado com sucesso!</span></div>',
                        unsafe_allow_html=True,
                    )
                    st.rerun()
                else:
                    st.markdown(
                        f'<div class="error-box">{icon("x-circle",15,"#D93025")}'
                        f'<span class="box-text">Erro ao criar usuario (login ja existe).</span></div>',
                        unsafe_allow_html=True,
                    )

    st.divider()

    # ── Remover usuário ───────────────────────────────────────────────────────
    ic_trash = icon("trash-2", 16, "#E6EDF3")
    st.markdown(f"#### {ic_trash}&nbsp; Remover usuario", unsafe_allow_html=True)

    opcoes_remover = [u["username"] for u in usuarios if u["username"] != user["username"]]

    if not opcoes_remover:
        ic_info = icon("info", 15, "#00A8AB")
        st.markdown(
            f'<div class="info-box">{ic_info}'
            f'<span class="box-text">Nao ha outros usuarios para remover.</span></div>',
            unsafe_allow_html=True,
        )
    else:
        nomes_map = {u["username"]: u["name"] for u in usuarios}
        with st.form("form_remove_user"):
            login_remover = st.selectbox(
                "Selecione o usuario a remover",
                options=opcoes_remover,
                format_func=lambda u: f"{u}  —  {nomes_map.get(u,'')}",
            )
            ic_warn = icon("alert-triangle", 15, "#C77D0A")
            st.markdown(
                f'<div class="warn-box">{ic_warn}'
                f'<span class="box-text">Esta acao e irreversivel. '
                f'O usuario perdera o acesso imediatamente.</span></div>',
                unsafe_allow_html=True,
            )
            confirmar_remocao = st.form_submit_button(
                "Remover usuario", type="primary", use_container_width=True
            )
            if confirmar_remocao:
                delete_user(login_remover)
                ic_ok = icon("check-circle", 15, "#1AB87A")
                st.markdown(
                    f'<div class="success-box">{ic_ok}'
                    f'<span class="box-text">Usuario <strong>{login_remover}</strong> '
                    f'removido com sucesso.</span></div>',
                    unsafe_allow_html=True,
                )
                st.rerun()

    st.markdown("""
    <div class="footer">
        Conversor NFS-e &nbsp;v2.0 &nbsp;&middot;&nbsp; Painel Administrativo
    </div>
    """, unsafe_allow_html=True)
