"""
auth/security.py — Autenticação e controle de sessão
Substitui streamlit-authenticator com implementação nativa + bcrypt.
"""

import streamlit as st
import bcrypt
from db.database import get_user, get_user_permissions

# ── CRYPTO ───────────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ── SESSÃO ───────────────────────────────────────────────────────────────────────

def current_user() -> dict:
    return {
        "username": st.session_state.get("username", ""),
        "name":     st.session_state.get("name", ""),
        "role":     st.session_state.get("role", "user"),
    }


def is_admin() -> bool:
    return st.session_state.get("role") == "admin"


def has_permission(pagina: str) -> bool:
    """Admins always have access. Users only see their allowed pages."""
    if is_admin():
        return True
    username = st.session_state.get("username", "")
    perms = get_user_permissions(username)
    return pagina in perms


def logout():
    for key in ("authenticated", "username", "name", "role", "pagina"):
        st.session_state.pop(key, None)
    st.rerun()


# ── LOGIN GUARD ──────────────────────────────────────────────────────────────────

def require_login():
    """Renderiza tela de login e para o app se o usuário não estiver autenticado."""
    if st.session_state.get("authenticated"):
        return
    _render_login()
    st.stop()


def _render_login():
    from assets.icons import SVG_LOGIN_GRAPHIC

    st.markdown("""
    <style>
        [data-testid="stSidebar"],
        [data-testid="stSidebarCollapsedControl"] { display: none !important; }
        .block-container { max-width: 440px !important; }
    </style>""", unsafe_allow_html=True)

    st.markdown('<div style="height:44px"></div>', unsafe_allow_html=True)

    # Ilustração SVG abstrata
    st.markdown(SVG_LOGIN_GRAPHIC, unsafe_allow_html=True)

    # Título
    st.markdown("""
    <div style="text-align:center; margin-bottom:1.8rem;">
        <div style="color:#E6EDF3; font-size:1.4rem; font-weight:800; letter-spacing:-.4px;">
            Conversor NFS-e
        </div>
        <div style="color:#484F58; font-size:.82rem; margin-top:.45rem; letter-spacing:.05px;">
            ISS Fortaleza &nbsp;&middot;&nbsp; SPED GOV &nbsp;&middot;&nbsp; Modelo Nacional 2026
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Formulário
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Usuário", placeholder="seu.login")
        password = st.text_input("Senha", type="password", placeholder="••••••••")
        submitted = st.form_submit_button(
            "Entrar", use_container_width=True, type="primary"
        )

    if submitted:
        _do_login(username.strip().lower(), password)

    st.markdown("""
    <div style="text-align:center; color:#2F3E55; font-size:.71rem; margin-top:1rem;">
        Acesso restrito &mdash; entre com suas credenciais acima
    </div>""", unsafe_allow_html=True)


def _do_login(username: str, password: str):
    user = get_user(username)
    if user and verify_password(password, user["password_hash"]):
        st.session_state["authenticated"] = True
        st.session_state["username"]      = user["username"]
        st.session_state["name"]          = user["name"]
        st.session_state["role"]          = user["role"]
        st.rerun()
    else:
        st.error("Usuário ou senha incorretos.")
