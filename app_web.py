#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Conversor NFSe — Interface Web  v1.3
Uso: streamlit run app_web.py
"""

import sys
import os
import io
import tempfile
import contextlib
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

for _mod in (
    "tkinter", "tkinter.simpledialog", "tkinter.filedialog",
    "tkinter.messagebox", "tkinter.ttk", "tkinter.font",
):
    sys.modules.setdefault(_mod, MagicMock())

import streamlit as st

st.set_page_config(
    page_title="Conversor NFSe  |  ISS Fortaleza",
    page_icon="📄",
    layout="centered",
    initial_sidebar_state="collapsed",
)

import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
import bcrypt

sys.path.insert(0, str(Path(__file__).parent))

_CONVERSOR_OK  = False
_CONVERSOR_ERR = ""
try:
    import nfse_xml_to_txt as C
    _CONVERSOR_OK = True
except Exception as _e:
    _CONVERSOR_ERR = str(_e)


# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

*, *::before, *::after { box-sizing: border-box; }
html, body, [data-testid="stAppViewContainer"] {
    background: #0d1117 !important;
    font-family: 'Inter', sans-serif;
}
[data-testid="stHeader"]  { background: transparent !important; }
[data-testid="stSidebar"] { background: #161b27 !important; border-right: 1px solid #21273a; }
.block-container          { max-width: 760px; padding: 1.5rem 1.5rem 3rem; }

body, p, div, span, li { color: #c9d1d9; }
h1,h2,h3,h4            { color: #f0f4ff !important; font-weight: 700; }
label                   { color: #8b949e !important; font-size: .78rem !important;
                          font-weight: 600 !important; letter-spacing: .3px !important; }

/* ── HERO ── */
.hero {
    background: linear-gradient(135deg, #0f1c3a 0%, #0d2b5e 55%, #0a1f47 100%);
    border: 1px solid #1f3a6e;
    border-radius: 16px;
    padding: 30px 34px 26px;
    margin-bottom: 32px;
    position: relative;
    overflow: hidden;
}
.hero::before {
    content: "";
    position: absolute; top: -50px; right: -50px;
    width: 200px; height: 200px;
    background: radial-gradient(circle, #1a4aa840 0%, transparent 70%);
    border-radius: 50%;
}
.hero-badge {
    display: inline-block;
    background: #1a3a6e; color: #58a6ff;
    border: 1px solid #2d5fa8; border-radius: 20px;
    font-size: .7rem; font-weight: 700; letter-spacing: .6px;
    padding: 3px 12px; margin-bottom: 12px; text-transform: uppercase;
}
.hero-title {
    color: #f0f6ff; font-size: 1.75rem; font-weight: 800;
    letter-spacing: -.3px; margin: 0 0 8px; line-height: 1.2;
}
.hero-sub { color: #7d8fa8; font-size: .88rem; margin: 0 0 16px; }
.hero-chips { display: flex; gap: 8px; flex-wrap: wrap; }
.chip {
    background: #0d1117; border: 1px solid #21273a; color: #8b949e;
    border-radius: 20px; font-size: .7rem; font-weight: 500; padding: 4px 11px;
}

/* ── ADMIN HERO ── */
.admin-hero {
    background: linear-gradient(135deg, #1a0f2e 0%, #2d1b4e 55%, #1a0f3a 100%);
    border: 1px solid #3d2a6e;
    border-radius: 16px;
    padding: 26px 34px 22px;
    margin-bottom: 28px;
}
.admin-hero-title {
    color: #d2b4ff; font-size: 1.4rem; font-weight: 800;
    letter-spacing: -.3px; margin: 0 0 6px;
}
.admin-hero-sub { color: #6a5a8a; font-size: .85rem; }

/* ── ETAPAS ── */
.step-header {
    display: flex; align-items: flex-start; gap: 14px;
    margin: 24px 0 12px;
}
.step-num {
    min-width: 32px; height: 32px;
    background: linear-gradient(135deg, #1d6fdb, #1558b8);
    color: #fff; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: .85rem; font-weight: 800; flex-shrink: 0;
    box-shadow: 0 2px 8px #1558b840;
}
.step-title { color: #e6edf3; font-weight: 700; font-size: .95rem; }
.step-desc  { color: #484f58; font-size: .78rem; margin-top: 2px; }

/* ── CARDS DE FORMATO ── */
.format-card {
    background: #161b27; border: 1px solid #21273a;
    border-radius: 10px; padding: 14px 16px; margin-bottom: 10px;
    text-align: center;
}
.format-icon { font-size: 1.6rem; margin-bottom: 6px; }
.format-name { color: #e6edf3; font-weight: 700; font-size: .9rem; }
.format-desc { color: #484f58; font-size: .75rem; margin-top: 4px; line-height: 1.4; }

/* ── LISTA DE ARQUIVOS ── */
.file-list {
    background: #0d1117; border: 1px solid #1f3a6e;
    border-radius: 8px; padding: 12px 14px; margin: 8px 0 4px;
}
.file-list-header { color: #3fb950; font-size: .78rem; font-weight: 700; margin-bottom: 8px; }
.file-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.file-chip {
    background: #161b27; border: 1px solid #21273a; color: #8b949e;
    border-radius: 6px; font-size: .72rem; padding: 3px 10px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 220px;
}
.file-chip-more {
    background: #1a2340; border: 1px solid #2a3a5e; color: #58a6ff;
    border-radius: 6px; font-size: .72rem; padding: 3px 10px;
}

/* ── INFO / WARN / ERROR ── */
.info-box {
    background: #0d1f2d; border: 1px solid #1a3a5e; border-left: 3px solid #58a6ff;
    border-radius: 6px; padding: 10px 14px; margin: 8px 0;
    color: #7d9fc0; font-size: .8rem; line-height: 1.5;
}
.warn-box {
    background: #1c1a0d; border: 1px solid #4a3e00; border-left: 3px solid #d29922;
    border-radius: 6px; padding: 10px 14px; margin: 12px 0;
    color: #b08020; font-size: .82rem;
}
.error-box {
    background: #1a0d0d; border: 1px solid #4a1515; border-left: 3px solid #f85149;
    border-radius: 6px; padding: 10px 14px; margin: 12px 0;
    color: #c04040; font-size: .82rem;
}
.success-box {
    background: #0a1f10; border: 1px solid #1a5c30; border-left: 3px solid #3fb950;
    border-radius: 6px; padding: 10px 14px; margin: 12px 0;
    color: #3fb950; font-size: .82rem;
}

/* ── TABELA DE USUÁRIOS ── */
.user-table {
    width: 100%; border-collapse: collapse;
    background: #161b27; border-radius: 10px; overflow: hidden;
    border: 1px solid #21273a; margin: 12px 0 20px;
}
.user-table th {
    background: #0d1117; color: #484f58; font-size: .72rem;
    font-weight: 700; letter-spacing: .5px; text-transform: uppercase;
    padding: 10px 14px; border-bottom: 1px solid #21273a; text-align: left;
}
.user-table td {
    padding: 10px 14px; border-bottom: 1px solid #21273a;
    color: #c9d1d9; font-size: .83rem;
}
.user-table tr:last-child td { border-bottom: none; }
.user-table tr:hover td { background: #1a2035; }
.user-badge {
    display: inline-block; background: #0d2040; color: #58a6ff;
    border: 1px solid #2d5fa8; border-radius: 12px;
    font-size: .65rem; font-weight: 700; padding: 2px 9px;
}
.user-badge-admin {
    background: #2d1b4e; color: #b17aff; border-color: #6a3fa8;
}

/* ── RESULTADO ── */
.result-success {
    background: linear-gradient(135deg, #0a1f10, #0d2416);
    border: 1px solid #1a5c30; border-radius: 12px;
    padding: 18px 22px; margin: 16px 0 12px;
    display: flex; align-items: center; gap: 16px;
}
.result-success-icon { font-size: 2rem; flex-shrink: 0; }
.result-success-title { color: #3fb950; font-weight: 700; font-size: .95rem; }
.result-success-meta  { color: #484f58; font-size: .78rem; margin-top: 4px; }

/* ── BOTÕES ── */
div.stButton > button {
    background: linear-gradient(135deg, #1d6fdb, #1558b8) !important;
    color: #fff !important; border: none !important; border-radius: 8px !important;
    font-weight: 600 !important; font-size: .88rem !important;
    padding: .65rem .9rem !important; letter-spacing: .2px !important;
    box-shadow: 0 2px 8px #1558b840 !important; transition: all .2s !important;
}
div.stButton > button:hover {
    background: linear-gradient(135deg, #2279ec, #1865cc) !important;
    transform: translateY(-1px) !important; box-shadow: 0 4px 14px #1558b860 !important;
}
div.stDownloadButton > button {
    background: linear-gradient(135deg, #1a7a40, #15632f) !important;
    color: #fff !important; border: none !important; border-radius: 8px !important;
    font-weight: 700 !important; font-size: .95rem !important;
    padding: .75rem 1.3rem !important;
    box-shadow: 0 2px 10px #1a7a4050 !important; transition: all .2s !important;
}
div.stDownloadButton > button:hover {
    background: linear-gradient(135deg, #1f8f4a, #197039) !important;
    transform: translateY(-1px) !important; box-shadow: 0 4px 16px #1a7a4070 !important;
}

/* ── INPUTS ── */
[data-testid="stTextInput"] input {
    background: #0d1117 !important; color: #e6edf3 !important;
    border: 1px solid #30363d !important; border-radius: 8px !important;
    font-size: .88rem !important; padding: .55rem .85rem !important;
    transition: border-color .2s !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: #58a6ff !important; box-shadow: 0 0 0 3px #58a6ff1a !important;
}
[data-testid="stTextInput"] input::placeholder { color: #484f58 !important; }

/* ── FILE UPLOADER ── */
[data-testid="stFileUploader"] {
    background: #0d1117 !important; border: 2px dashed #2a3a5e !important;
    border-radius: 10px !important; padding: .6rem !important; transition: border-color .2s !important;
}
[data-testid="stFileUploader"]:hover { border-color: #4078c8 !important; }
[data-testid="stFileUploader"] * { color: #7d8fa8 !important; }

/* ── LOG / CODE ── */
[data-testid="stCode"], pre {
    background: #0a0e17 !important; border: 1px solid #21273a !important;
    border-radius: 8px !important; color: #a8b5c8 !important;
    font-size: .78rem !important; line-height: 1.6 !important;
}

/* ── EXPANDER ── */
[data-testid="stExpander"] {
    background: #161b27 !important; border: 1px solid #21273a !important;
    border-radius: 8px !important;
}

/* ── SIDEBAR ── */
[data-testid="stSidebar"] * { color: #8b949e !important; }
[data-testid="stSidebar"] strong { color: #e6edf3 !important; }
.user-info-card {
    background: #0d1117; border: 1px solid #21273a;
    border-radius: 10px; padding: 14px 16px; margin-bottom: 12px;
}
.user-avatar {
    width: 38px; height: 38px;
    background: linear-gradient(135deg, #1d6fdb, #1558b8);
    border-radius: 50%; display: flex; align-items: center;
    justify-content: center; font-size: 1rem; margin-bottom: 10px;
}
.user-name  { color: #e6edf3 !important; font-weight: 700; font-size: .9rem; }
.user-login { color: #484f58 !important; font-size: .75rem; margin-top: 2px; }

/* ── NAV ── */
.nav-btn {
    display: block; width: 100%;
    background: transparent; border: 1px solid #21273a;
    border-radius: 8px; padding: 9px 14px; margin-bottom: 6px;
    color: #8b949e; font-size: .82rem; font-weight: 500;
    cursor: pointer; text-align: left; transition: all .18s;
}
.nav-btn:hover  { background: #1a2035; color: #c9d1d9; border-color: #2d3a5e; }
.nav-btn.active { background: #0d2040; color: #58a6ff; border-color: #2d5fa8; font-weight: 700; }

/* ── FOOTER ── */
.footer {
    text-align: center; color: #2d333b; font-size: .72rem;
    margin-top: 2.5rem; padding-top: 1rem; border-top: 1px solid #161b27;
}

/* ── LOGIN FORM ── */
[data-testid="stForm"] {
    background: #161b27; border: 1px solid #21273a;
    border-radius: 14px; padding: 24px 28px !important;
}
[data-testid="stCaptionContainer"] { color: #8b949e !important; font-size: .78rem !important; }
hr { border-color: #21273a !important; margin: 1rem 0 !important; }
</style>
""", unsafe_allow_html=True)


# ── AUTENTICAÇÃO ──────────────────────────────────────────────────────────────
_CFG_PATH = Path(__file__).parent / "config.yaml"


def _carregar_auth():
    if not _CFG_PATH.exists():
        st.error("Arquivo `config.yaml` não encontrado.\n\nExecute: `python gerar_senha.py`")
        st.stop()
    with open(_CFG_PATH) as f:
        cfg = yaml.load(f, Loader=SafeLoader)
    if not cfg.get("credentials", {}).get("usernames"):
        st.warning("Nenhum usuário cadastrado. Execute: `python gerar_senha.py`")
        st.stop()
    return stauth.Authenticate(
        cfg["credentials"],
        cfg["cookie"]["name"],
        cfg["cookie"]["key"],
        cfg["cookie"]["expiry_days"],
    )


auth = _carregar_auth()

if st.session_state.get("authentication_status") is not True:
    st.markdown("""
    <div style="text-align:center; padding: 2.5rem 0 1rem;">
        <div style="font-size:3.5rem; margin-bottom:.6rem;">📄</div>
        <div style="color:#f0f6ff; font-size:1.35rem; font-weight:800; letter-spacing:-.3px;">
            Conversor NFSe
        </div>
        <div style="color:#484f58; font-size:.88rem; margin-top:.4rem;">
            ISS Fortaleza &nbsp;·&nbsp; SPED GOV &nbsp;·&nbsp; Modelo Nacional 2026
        </div>
    </div>
    """, unsafe_allow_html=True)

auth.login()

_status = st.session_state.get("authentication_status")

if _status is False:
    st.error("Usuário ou senha incorretos. Tente novamente.")
    st.stop()

if _status is None:
    st.markdown("""
    <div style="text-align:center; color:#2d333b; font-size:.75rem; margin-top:2rem;">
        Acesso restrito · Entre com suas credenciais acima
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# ── SIDEBAR ───────────────────────────────────────────────────────────────────
_usuario_atual = st.session_state.get("username", "")
_nome_atual    = st.session_state.get("name", "Usuário")
_is_admin      = (_usuario_atual == "admin")

with st.sidebar:
    inicial = _nome_atual[0].upper() if _nome_atual else "U"
    st.markdown(f"""
    <div class="user-info-card">
        <div class="user-avatar">{inicial}</div>
        <div class="user-name">{_nome_atual}</div>
        <div class="user-login">@{_usuario_atual}</div>
    </div>
    """, unsafe_allow_html=True)

    auth.logout("↩  Sair", location="sidebar")
    st.divider()

    # Navegação
    st.markdown('<div style="color:#484f58;font-size:.72rem;font-weight:600;letter-spacing:.5px;text-transform:uppercase;margin-bottom:8px;">Navegação</div>', unsafe_allow_html=True)

    if "pagina" not in st.session_state:
        st.session_state.pagina = "conversor"

    if st.button("📄  Conversor", use_container_width=True, key="nav_conversor"):
        st.session_state.pagina = "conversor"

    if _is_admin:
        if st.button("👥  Gerenciar Usuários", use_container_width=True, key="nav_usuarios"):
            st.session_state.pagina = "usuarios"

    st.divider()
    st.markdown('<div style="color:#484f58;font-size:.72rem;font-weight:600;letter-spacing:.5px;text-transform:uppercase;margin-bottom:8px;">Sistema</div>', unsafe_allow_html=True)
    st.caption("Conversor NFSe  v1.3")
    st.caption("Modelo Nacional 2026")
    st.caption("ISS Fortaleza / SPED GOV")

if not _CONVERSOR_OK and st.session_state.pagina == "conversor":
    st.error(f"Não foi possível carregar `nfse_xml_to_txt.py`:\n\n`{_CONVERSOR_ERR}`")
    st.stop()


# ── HELPER ────────────────────────────────────────────────────────────────────
def processar_uploads(uploaded_files, im: str, modo: str):
    with tempfile.TemporaryDirectory() as tmp:
        for uf in uploaded_files:
            uf.seek(0)
            with open(os.path.join(tmp, uf.name), "wb") as fh:
                fh.write(uf.read())
        ext   = "txt" if modo == "txt" else "xlsx"
        saida = os.path.join(tmp, f"resultado.{ext}")
        buf   = io.StringIO()
        with contextlib.redirect_stdout(buf):
            try:
                if modo == "txt":
                    C.processar(tmp, saida, im_padrao=im)
                else:
                    C.processar_sped(tmp, saida, im_padrao=im)
            except Exception as exc:
                print(f"\nERRO FATAL: {exc}")
        log  = buf.getvalue()
        data = b""
        if os.path.exists(saida):
            with open(saida, "rb") as fh:
                data = fh.read()
    return data, log


def _carregar_cfg() -> dict:
    with open(_CFG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _salvar_cfg(cfg: dict):
    with open(_CFG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def _hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


# ── PÁGINA: GERENCIAR USUÁRIOS ─────────────────────────────────────────────────
def pagina_usuarios():
    if not _is_admin:
        st.error("Acesso restrito ao administrador.")
        return

    st.markdown("""
    <div class="admin-hero">
        <div class="admin-hero-title">👥 Gerenciar Usuários</div>
        <div class="admin-hero-sub">Adicione ou remova logins de acesso ao sistema</div>
    </div>
    """, unsafe_allow_html=True)

    cfg = _carregar_cfg()
    usuarios = cfg.get("credentials", {}).get("usernames", {})

    # ── Lista de usuários ──
    st.markdown("#### Usuários cadastrados")

    if not usuarios:
        st.markdown('<div class="warn-box">⚠️ Nenhum usuário cadastrado.</div>', unsafe_allow_html=True)
    else:
        linhas = ""
        for login, dados in usuarios.items():
            badge = '<span class="user-badge user-badge-admin">admin</span>' if login == "admin" else '<span class="user-badge">usuário</span>'
            nome_u = dados.get("name", "—")
            email_u = dados.get("email", "—")
            linhas += f"""
            <tr>
                <td>{badge} <strong style="color:#e6edf3">{login}</strong></td>
                <td>{nome_u}</td>
                <td>{email_u}</td>
            </tr>"""
        st.markdown(f"""
        <table class="user-table">
            <thead><tr>
                <th>Login</th>
                <th>Nome</th>
                <th>E-mail</th>
            </tr></thead>
            <tbody>{linhas}</tbody>
        </table>
        """, unsafe_allow_html=True)

    st.divider()

    # ── Adicionar usuário ──
    st.markdown("#### ➕ Adicionar novo usuário")

    with st.form("form_add_user", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            novo_login = st.text_input("Login *", placeholder="ex: joao")
            novo_nome  = st.text_input("Nome completo *", placeholder="ex: João Silva")
        with col2:
            novo_email = st.text_input("E-mail", placeholder="ex: joao@empresa.com")
            nova_senha = st.text_input("Senha *  (mín. 6 caracteres)", type="password")

        confirmar_senha = st.text_input("Confirmar senha *", type="password")

        submitted = st.form_submit_button("✅  Criar usuário", use_container_width=True, type="primary")

        if submitted:
            erros = []
            if not novo_login.strip():
                erros.append("Login é obrigatório.")
            elif " " in novo_login.strip():
                erros.append("Login não pode ter espaços.")
            if not novo_nome.strip():
                erros.append("Nome completo é obrigatório.")
            if len(nova_senha) < 6:
                erros.append("Senha deve ter pelo menos 6 caracteres.")
            if nova_senha != confirmar_senha:
                erros.append("As senhas não coincidem.")
            if novo_login.strip() in usuarios:
                erros.append(f"Já existe um usuário com o login '{novo_login.strip()}'.")

            if erros:
                for e in erros:
                    st.markdown(f'<div class="error-box">❌ {e}</div>', unsafe_allow_html=True)
            else:
                with st.spinner("Gerando hash da senha…"):
                    hashed = _hash_senha(nova_senha)

                cfg["credentials"]["usernames"][novo_login.strip()] = {
                    "name": novo_nome.strip(),
                    "email": novo_email.strip() or f"{novo_login.strip()}@exemplo.com",
                    "password": hashed,
                    "failed_login_attempts": 0,
                    "logged_in": False,
                }
                _salvar_cfg(cfg)
                st.markdown(f'<div class="success-box">✅ Usuário <strong>{novo_login.strip()}</strong> criado com sucesso!</div>', unsafe_allow_html=True)
                st.rerun()

    st.divider()

    # ── Remover usuário ──
    st.markdown("#### 🗑️ Remover usuário")

    opcoes_remover = [u for u in usuarios.keys() if u != _usuario_atual]

    if not opcoes_remover:
        st.markdown('<div class="info-box">💡 Não há outros usuários para remover.</div>', unsafe_allow_html=True)
    else:
        with st.form("form_remove_user"):
            login_remover = st.selectbox(
                "Selecione o usuário a remover",
                options=opcoes_remover,
                format_func=lambda u: f"{u}  —  {usuarios[u].get('name', '')}",
            )
            st.markdown('<div class="warn-box">⚠️ Esta ação é irreversível. O usuário perderá o acesso imediatamente.</div>', unsafe_allow_html=True)
            confirmar_remocao = st.form_submit_button("🗑️  Remover usuário", type="primary", use_container_width=True)

            if confirmar_remocao:
                del cfg["credentials"]["usernames"][login_remover]
                _salvar_cfg(cfg)
                st.markdown(f'<div class="success-box">✅ Usuário <strong>{login_remover}</strong> removido com sucesso.</div>', unsafe_allow_html=True)
                st.rerun()

    st.markdown("""
    <div class="footer">
        Conversor NFSe v1.3 &nbsp;·&nbsp; Painel Administrativo
    </div>
    """, unsafe_allow_html=True)


# ── PÁGINA: CONVERSOR ─────────────────────────────────────────────────────────
def pagina_conversor():
    st.markdown("""
    <div class="hero">
        <div class="hero-badge">✦ NFSe · Modelo Nacional 2026</div>
        <div class="hero-title">Conversor de Notas Fiscais</div>
        <p class="hero-sub">Transforme XMLs de NFSe no layout do portal ISS Fortaleza ou na planilha SPED GOV — direto do navegador, sem instalar nada.</p>
        <div class="hero-chips">
            <span class="chip">📄 ISS Fortaleza</span>
            <span class="chip">📊 SPED GOV</span>
            <span class="chip">🔒 Acesso seguro</span>
            <span class="chip">⚡ Segundos</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── ETAPA 1 ────────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="step-header">
        <div class="step-num">1</div>
        <div class="step-info">
            <div class="step-title">Selecione os arquivos XML</div>
            <div class="step-desc">Arraste ou clique para carregar um ou mais XMLs de NFSe</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "xml_upload", type=["xml"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    if uploaded:
        total = len(uploaded)
        chips = "".join(
            f'<span class="file-chip">📄 {u.name}</span>'
            for u in uploaded[:8]
        )
        extra = f'<span class="file-chip-more">+{total - 8} mais</span>' if total > 8 else ""
        st.markdown(f"""
        <div class="file-list">
            <div class="file-list-header">✅ {total} arquivo{'s' if total > 1 else ''} selecionado{'s' if total > 1 else ''}</div>
            <div class="file-chips">{chips}{extra}</div>
        </div>
        """, unsafe_allow_html=True)

    # ── ETAPA 2 ────────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="step-header">
        <div class="step-num">2</div>
        <div class="step-info">
            <div class="step-title">Inscrição Municipal Tomadora</div>
            <div class="step-desc">Opcional — deixe em branco para usar a do próprio XML</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    im_input = st.text_input("im", placeholder="Ex: 12345678-0", label_visibility="collapsed")

    st.markdown("""
    <div class="info-box">
        💡 Notas <strong>emitidas em Fortaleza</strong> são ignoradas no modo TXT — o portal ISS já as importa automaticamente. Exceção: MEI.
    </div>
    """, unsafe_allow_html=True)

    # ── ETAPA 3 ────────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="step-header">
        <div class="step-num">3</div>
        <div class="step-info">
            <div class="step-title">Gerar o arquivo de saída</div>
            <div class="step-desc">Escolha o formato e clique para processar</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="medium")

    with col1:
        st.markdown("""
        <div class="format-card">
            <div class="format-icon">📄</div>
            <div class="format-name">ISS Fortaleza</div>
            <div class="format-desc">Layout TXT para importação no portal da prefeitura de Fortaleza</div>
        </div>
        """, unsafe_allow_html=True)
        btn_txt = st.button("▶  Gerar TXT", use_container_width=True, type="primary", key="btn_txt")

    with col2:
        st.markdown("""
        <div class="format-card">
            <div class="format-icon">📊</div>
            <div class="format-name">SPED GOV</div>
            <div class="format-desc">Planilha XLSX para o sistema SPED do governo federal</div>
        </div>
        """, unsafe_allow_html=True)
        btn_xlsx = st.button("▶  Gerar XLSX", use_container_width=True, key="btn_xlsx")

    # ── Processamento ──────────────────────────────────────────────────────────
    if btn_txt or btn_xlsx:
        if not uploaded:
            st.markdown("""<div class="warn-box">⚠️ Selecione pelo menos um arquivo XML na Etapa 1 antes de processar.</div>""", unsafe_allow_html=True)
        else:
            modo       = "txt" if btn_txt else "xlsx"
            im         = im_input.strip() or "0"
            tipo_label = "ISS Fortaleza (TXT)" if modo == "txt" else "SPED GOV (XLSX)"

            with st.spinner(f"⏳  Processando {len(uploaded)} arquivo(s) — {tipo_label}…"):
                dados_saida, log = processar_uploads(uploaded, im, modo)

            if dados_saida:
                ext        = "txt" if modo == "txt" else "xlsx"
                mime       = "text/plain" if modo == "txt" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                nome       = f"nfse_{modo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
                tamanho_kb = round(len(dados_saida) / 1024, 1)
                icone      = "📄" if modo == "txt" else "📊"

                st.markdown(f"""
                <div class="result-success">
                    <div class="result-success-icon">✅</div>
                    <div class="result-success-body">
                        <div class="result-success-title">Arquivo gerado com sucesso!</div>
                        <div class="result-success-meta">
                            {icone} {nome} &nbsp;·&nbsp; {tamanho_kb} KB &nbsp;·&nbsp;
                            {len(uploaded)} XML{'s' if len(uploaded) > 1 else ''} processado{'s' if len(uploaded) > 1 else ''}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                st.download_button(
                    label=f"⬇  Baixar  {nome}",
                    data=dados_saida, file_name=nome, mime=mime,
                    use_container_width=True,
                )
            else:
                st.markdown("""<div class="error-box">❌ Nenhum arquivo foi gerado. Verifique o log abaixo.</div>""", unsafe_allow_html=True)

            with st.expander("📋  Ver log de processamento"):
                st.code(log.strip() if log.strip() else "(nenhuma saída registrada)", language="")

    st.markdown("""
    <div class="footer">
        Conversor NFSe v1.3 &nbsp;·&nbsp; Modelo Nacional 2026 &nbsp;·&nbsp; ISS Fortaleza / SPED GOV
    </div>
    """, unsafe_allow_html=True)


# ── ROTEADOR ─────────────────────────────────────────────────────────────────
pagina = st.session_state.get("pagina", "conversor")

if pagina == "usuarios":
    pagina_usuarios()
else:
    pagina_conversor()
