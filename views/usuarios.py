"""
pages/usuarios.py — Gerenciamento de usuários (somente admin)
"""

import streamlit as st
from auth.security import current_user, is_admin, logout, hash_password
from db.database import list_users, create_user, delete_user
from assets.icons import icon
from views import nav


def render():
    if not is_admin():
        st.error("Acesso restrito ao administrador.")
        return

    user = current_user()

    nav.render("usuarios")

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
            # Escapa & para evitar HTML inválido em logins como "p&p"
            _login = u["username"].replace("&", "&amp;")
            _nome  = u["name"].replace("&", "&amp;")
            _email = (u["email"] or "—").replace("&", "&amp;")
            linhas += f"""
            <tr>
                <td>{badge} <strong style="color:#e6edf3">{_login}</strong></td>
                <td>{_nome}</td>
                <td>{_email}</td>
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

    st.divider()

    ic_perm = icon("sliders", 16, "#E6EDF3")
    st.markdown(f"#### {ic_perm}&nbsp; Permissoes por usuario", unsafe_allow_html=True)

    ALL_PAGES_PERMS = [
        ("conversor",    "Conversor XML"),
        ("baixar_xmls",  "Baixar XML"),
        ("certificados", "Certificados"),
        ("milhao",       "Milhão"),
        ("dashboard",    "Dashboard"),
    ]

    usuarios_nao_admin = [u for u in usuarios if u["role"] != "admin"]
    if not usuarios_nao_admin:
        st.markdown('<div style="color:#475569;font-size:.85rem;">Nenhum usuario comum cadastrado.</div>', unsafe_allow_html=True)
    else:
        from db.database import get_user_permissions, set_user_permissions
        usuario_sel = st.selectbox(
            "Selecionar usuario",
            [u["username"] for u in usuarios_nao_admin],
            format_func=lambda u: f"{u}  —  {next((x['name'] for x in usuarios if x['username']==u), u)}",
            key="perm_sel_usuario",
        )
        perms_atuais = get_user_permissions(usuario_sel)

        st.markdown('<div style="color:#8B949E;font-size:.78rem;margin:6px 0 10px;">Marque as paginas que este usuario pode acessar:</div>', unsafe_allow_html=True)

        novas_perms = []
        cols_perm = st.columns(len(ALL_PAGES_PERMS))
        for i, (key, label) in enumerate(ALL_PAGES_PERMS):
            with cols_perm[i]:
                if st.checkbox(label, value=(key in perms_atuais), key=f"perm_{usuario_sel}_{key}"):
                    novas_perms.append(key)

        if st.button("Salvar permissoes", type="primary", use_container_width=True, key="btn_salvar_perms"):
            set_user_permissions(usuario_sel, novas_perms)
            st.toast(f"Permissoes de '{usuario_sel}' atualizadas.")
            st.rerun()

    st.markdown("""
    <div class="footer">
        Conversor NFS-e &nbsp;v2.0 &nbsp;&middot;&nbsp; Painel Administrativo
    </div>
    """, unsafe_allow_html=True)
