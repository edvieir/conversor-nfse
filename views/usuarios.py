"""
pages/usuarios.py — Gerenciamento de usuários (somente admin)
"""

import streamlit as st
from datetime import date
from html import escape
from auth.security import current_user, is_admin, logout, hash_password
from db.database import (
    list_users, create_user, delete_user,
    update_password, update_validade,
)
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
        hoje = date.today()
        linhas = ""
        for u in usuarios:
            badge = (
                '<span class="user-badge user-badge-admin">admin</span>'
                if u["role"] == "admin"
                else '<span class="user-badge">usuario</span>'
            )
            _login = escape(u["username"])
            _nome  = escape(u["name"])
            _email = escape(u["email"] or "—")

            val = u.get("validade")
            if val:
                try:
                    val_date = val if isinstance(val, date) else date.fromisoformat(str(val)[:10])
                    if val_date < hoje:
                        _val = f'<span style="color:#D93025;font-weight:600">{val_date} ⛔</span>'
                    else:
                        _val = str(val_date)
                except Exception:
                    _val = str(val)
            else:
                _val = "—"

            linhas += f"""
            <tr>
                <td>{badge} <strong style="color:#e6edf3">{_login}</strong></td>
                <td>{_nome}</td>
                <td>{_email}</td>
                <td>{_val}</td>
            </tr>"""
        st.markdown(f"""
        <table class="user-table">
            <thead><tr>
                <th>Login</th><th>Nome</th><th>E-mail</th><th>Validade</th>
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

        col_val1, col_val2 = st.columns([1, 2])
        with col_val1:
            usar_validade = st.checkbox("Definir prazo de validade", value=True)
        with col_val2:
            data_validade = st.date_input(
                "Validade até",
                value=date.today().replace(year=date.today().year + 1),
                min_value=date.today(),
                disabled=not usar_validade,
                format="DD/MM/YYYY",
            )

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
                val = data_validade if usar_validade else None
                ok = create_user(
                    novo_login.strip().lower(),
                    novo_nome.strip(),
                    novo_email.strip() or f"{novo_login.strip()}@empresa.com",
                    hashed,
                    validade=val,
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

    # ── Alterar senha ─────────────────────────────────────────────────────────
    ic_key = icon("key", 16, "#E6EDF3")
    st.markdown(f"#### {ic_key}&nbsp; Alterar senha de usuario", unsafe_allow_html=True)

    opcoes_senha = [u["username"] for u in usuarios if u["username"] != user["username"]]
    if not opcoes_senha:
        ic_info = icon("info", 15, "#00A8AB")
        st.markdown(
            f'<div class="info-box">{ic_info}'
            f'<span class="box-text">Nao ha outros usuarios para alterar a senha.</span></div>',
            unsafe_allow_html=True,
        )
    else:
        nomes_map = {u["username"]: u["name"] for u in usuarios}
        with st.form("form_change_password"):
            login_senha = st.selectbox(
                "Selecione o usuario",
                options=opcoes_senha,
                format_func=lambda u: f"{u}  —  {nomes_map.get(u, '')}",
                key="sel_change_pw",
            )
            col_pw1, col_pw2 = st.columns(2)
            with col_pw1:
                nova_pw = st.text_input("Nova senha *  (min. 6 caracteres)", type="password", key="nova_pw")
            with col_pw2:
                conf_pw = st.text_input("Confirmar nova senha *", type="password", key="conf_pw")

            btn_pw = st.form_submit_button("Alterar senha", type="primary", use_container_width=True)
            if btn_pw:
                erros_pw = []
                if len(nova_pw) < 6:
                    erros_pw.append("Senha deve ter pelo menos 6 caracteres.")
                if nova_pw != conf_pw:
                    erros_pw.append("As senhas nao coincidem.")
                if erros_pw:
                    ic_err = icon("x-circle", 15, "#D93025")
                    for e in erros_pw:
                        st.markdown(
                            f'<div class="error-box">{ic_err}'
                            f'<span class="box-text">{e}</span></div>',
                            unsafe_allow_html=True,
                        )
                else:
                    with st.spinner("Atualizando senha..."):
                        hashed = hash_password(nova_pw)
                        update_password(login_senha, hashed)
                    ic_ok = icon("check-circle", 15, "#1AB87A")
                    st.markdown(
                        f'<div class="success-box">{ic_ok}'
                        f'<span class="box-text">Senha de <strong>{login_senha}</strong> '
                        f'alterada com sucesso.</span></div>',
                        unsafe_allow_html=True,
                    )

    st.divider()

    # ── Alterar prazo de validade ─────────────────────────────────────────────
    ic_cal = icon("calendar", 16, "#E6EDF3")
    st.markdown(f"#### {ic_cal}&nbsp; Alterar prazo de validade", unsafe_allow_html=True)

    usuarios_nao_admin_val = [u for u in usuarios if u["role"] != "admin"]
    if not usuarios_nao_admin_val:
        ic_info = icon("info", 15, "#00A8AB")
        st.markdown(
            f'<div class="info-box">{ic_info}'
            f'<span class="box-text">Nao ha usuarios comuns cadastrados.</span></div>',
            unsafe_allow_html=True,
        )
    else:
        nomes_map2 = {u["username"]: u["name"] for u in usuarios}
        with st.form("form_validade"):
            login_val = st.selectbox(
                "Selecione o usuario",
                options=[u["username"] for u in usuarios_nao_admin_val],
                format_func=lambda u: f"{u}  —  {nomes_map2.get(u, '')}",
                key="sel_validade",
            )
            col_v1, col_v2 = st.columns([1, 2])
            with col_v1:
                sem_limite = st.checkbox("Sem prazo (acesso permanente)")
            with col_v2:
                val_data = st.date_input(
                    "Nova validade",
                    value=date.today().replace(year=date.today().year + 1),
                    key="val_data_input",
                    disabled=sem_limite,
                )

            btn_val = st.form_submit_button("Salvar validade", type="primary", use_container_width=True)
            if btn_val:
                nova_val = None if sem_limite else val_data
                update_validade(login_val, nova_val)
                ic_ok = icon("check-circle", 15, "#1AB87A")
                msg = "sem prazo definido" if nova_val is None else f"validade até {nova_val}"
                st.markdown(
                    f'<div class="success-box">{ic_ok}'
                    f'<span class="box-text">Validade de <strong>{login_val}</strong> '
                    f'atualizada: {msg}.</span></div>',
                    unsafe_allow_html=True,
                )
                st.rerun()

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
        nomes_map3 = {u["username"]: u["name"] for u in usuarios}
        with st.form("form_remove_user"):
            login_remover = st.selectbox(
                "Selecione o usuario a remover",
                options=opcoes_remover,
                format_func=lambda u: f"{u}  —  {nomes_map3.get(u,'')}",
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
        ("conversor",      "Conversor XML"),
        ("arquivo_fortes", "Arquivo Fortes"),
        ("baixar_xmls",    "Baixar XML"),
        ("nfe_nfce",       "NFE / NFCE"),
        ("siga_consulta",  "Consulta DTE"),
        ("siga_downloads", "Relatórios SIGA"),
        ("certificados",   "Certificados"),
        ("milhao",         "Milhão"),
        ("dashboard",      "Dashboard"),
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
