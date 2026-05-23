#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Conversor NFSe — Interface Web  v1.1
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

# Mock tkinter antes de qualquer import do conversor
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

sys.path.insert(0, str(Path(__file__).parent))

_CONVERSOR_OK  = False
_CONVERSOR_ERR = ""
try:
    import nfse_xml_to_txt as C
    _CONVERSOR_OK = True
except Exception as _e:
    _CONVERSOR_ERR = str(_e)


# ── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* Reset & base */
*, *::before, *::after { box-sizing: border-box; }
html, body, [data-testid="stAppViewContainer"] {
    background: #0d1117 !important;
    font-family: 'Inter', sans-serif;
}
[data-testid="stHeader"]  { background: transparent !important; }
[data-testid="stSidebar"] { background: #161b27 !important; border-right: 1px solid #21273a; }
.block-container          { max-width: 760px; padding: 1.5rem 1.5rem 3rem; }

/* Typography */
body, p, div, span, li { color: #c9d1d9; }
h1,h2,h3,h4            { color: #f0f4ff !important; font-weight: 700; }
label                   { color: #8b949e !important; font-size: .78rem !important; font-weight: 600 !important; letter-spacing: .3px !important; }

/* ── HERO BANNER ── */
.hero {
    background: linear-gradient(135deg, #0f1c3a 0%, #0d2b5e 50%, #0a1f47 100%);
    border: 1px solid #1f3a6e;
    border-radius: 16px;
    padding: 32px 36px 28px;
    margin-bottom: 28px;
    position: relative;
    overflow: hidden;
}
.hero::before {
    content: "";
    position: absolute;
    top: -60px; right: -60px;
    width: 220px; height: 220px;
    background: radial-gradient(circle, #1a4aa840 0%, transparent 70%);
    border-radius: 50%;
}
.hero-badge {
    display: inline-block;
    background: #1a3a6e;
    color: #58a6ff;
    border: 1px solid #2d5fa8;
    border-radius: 20px;
    font-size: .72rem;
    font-weight: 600;
    letter-spacing: .5px;
    padding: 3px 12px;
    margin-bottom: 14px;
    text-transform: uppercase;
}
.hero-title {
    color: #f0f6ff;
    font-size: 1.8rem;
    font-weight: 800;
    letter-spacing: -.3px;
    margin: 0 0 8px;
    line-height: 1.2;
}
.hero-sub {
    color: #7d8fa8;
    font-size: .92rem;
    margin: 0;
}
.hero-chips {
    display: flex;
    gap: 8px;
    margin-top: 18px;
    flex-wrap: wrap;
}
.chip {
    background: #111827;
    border: 1px solid #21273a;
    color: #8b949e;
    border-radius: 20px;
    font-size: .72rem;
    font-weight: 500;
    padding: 4px 12px;
}

/* ── CARDS ── */
.card {
    background: #161b27;
    border: 1px solid #21273a;
    border-radius: 12px;
    padding: 20px 22px;
    margin-bottom: 16px;
}
.card-title {
    color: #e6edf3;
    font-size: .88rem;
    font-weight: 700;
    letter-spacing: .2px;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.card-title .icon {
    width: 28px; height: 28px;
    background: #1a2340;
    border: 1px solid #2a3a5e;
    border-radius: 8px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: .9rem;
}

/* ── BOTÕES ── */
div.stButton > button {
    background: linear-gradient(135deg, #1d6fdb, #1558b8) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: .88rem !important;
    padding: .6rem .9rem !important;
    letter-spacing: .2px !important;
    transition: all .2s ease !important;
    box-shadow: 0 2px 8px #1558b840 !important;
}
div.stButton > button:hover {
    background: linear-gradient(135deg, #2279ec, #1865cc) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 14px #1558b860 !important;
}
div.stButton > button[kind="secondary"] {
    background: linear-gradient(135deg, #1a7a40, #15632f) !important;
    box-shadow: 0 2px 8px #1a7a4040 !important;
}
div.stButton > button[kind="secondary"]:hover {
    background: linear-gradient(135deg, #1f8f4a, #197039) !important;
    box-shadow: 0 4px 14px #1a7a4060 !important;
}
div.stDownloadButton > button {
    background: linear-gradient(135deg, #1a7a40, #15632f) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    font-size: .92rem !important;
    padding: .7rem 1.3rem !important;
    letter-spacing: .2px !important;
    box-shadow: 0 2px 10px #1a7a4050 !important;
    transition: all .2s ease !important;
}
div.stDownloadButton > button:hover {
    background: linear-gradient(135deg, #1f8f4a, #197039) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 16px #1a7a4070 !important;
}

/* ── INPUTS ── */
[data-testid="stTextInput"] input {
    background: #0d1117 !important;
    color: #e6edf3 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px !important;
    font-size: .88rem !important;
    padding: .55rem .85rem !important;
    transition: border-color .2s !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: #58a6ff !important;
    box-shadow: 0 0 0 3px #58a6ff1a !important;
}
[data-testid="stTextInput"] input::placeholder { color: #484f58 !important; }

/* ── FILE UPLOADER ── */
[data-testid="stFileUploader"] {
    background: #0d1117 !important;
    border: 2px dashed #2a3a5e !important;
    border-radius: 10px !important;
    padding: .8rem !important;
    transition: border-color .2s !important;
}
[data-testid="stFileUploader"]:hover { border-color: #4078c8 !important; }
[data-testid="stFileUploader"] * { color: #7d8fa8 !important; }
[data-testid="stFileUploader"] small { color: #484f58 !important; }

/* ── LOG / CODE ── */
[data-testid="stCode"], pre {
    background: #0a0e17 !important;
    border: 1px solid #21273a !important;
    border-radius: 8px !important;
    color: #a8b5c8 !important;
    font-size: .8rem !important;
    line-height: 1.6 !important;
}

/* ── ALERTS ── */
[data-testid="stAlert"]                         { border-radius: 8px !important; border-left-width: 3px !important; }
[data-testid="stAlert"][data-baseweb="notification"] { background: #0d1f0d !important; }

/* ── SUCCESS BOX ── */
.result-box {
    background: linear-gradient(135deg, #0a1f10, #0d2416);
    border: 1px solid #1a5c30;
    border-radius: 10px;
    padding: 16px 20px;
    margin: 12px 0;
    display: flex;
    align-items: center;
    gap: 14px;
}
.result-icon { font-size: 1.6rem; flex-shrink: 0; }
.result-text { flex: 1; }
.result-title { color: #3fb950; font-weight: 700; font-size: .92rem; }
.result-name  { color: #8b949e; font-size: .8rem; margin-top: 2px; }

/* ── DIVIDER ── */
hr { border-color: #21273a !important; margin: 1rem 0 !important; }

/* ── SIDEBAR ── */
[data-testid="stSidebar"] * { color: #8b949e !important; }
[data-testid="stSidebar"] strong { color: #e6edf3 !important; }
.user-info-card {
    background: #0d1117;
    border: 1px solid #21273a;
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 12px;
}
.user-avatar {
    width: 38px; height: 38px;
    background: linear-gradient(135deg, #1d6fdb, #1558b8);
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 1rem; margin-bottom: 10px;
}
.user-name  { color: #e6edf3 !important; font-weight: 700; font-size: .9rem; }
.user-login { color: #484f58 !important; font-size: .75rem; margin-top: 2px; }

/* ── FOOTER ── */
.footer {
    text-align: center;
    color: #2d333b;
    font-size: .72rem;
    margin-top: 2rem;
    padding-top: 1rem;
    border-top: 1px solid #161b27;
}

/* ── SPINNER ── */
[data-testid="stSpinner"] { color: #58a6ff !important; }

/* ── CAPTION ── */
[data-testid="stCaptionContainer"] { color: #8b949e !important; font-size: .78rem !important; }

/* ── LOGIN FORM ── */
[data-testid="stForm"] {
    background: #161b27;
    border: 1px solid #21273a;
    border-radius: 14px;
    padding: 24px 28px !important;
}
</style>
""", unsafe_allow_html=True)


# ── AUTENTICAÇÃO ─────────────────────────────────────────────────────────────
_CFG_PATH = Path(__file__).parent / "config.yaml"


def _carregar_auth():
    if not _CFG_PATH.exists():
        st.error(
            "Arquivo `config.yaml` não encontrado.\n\n"
            "Execute no terminal:\n```\npython gerar_senha.py\n```"
        )
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

# Tela de login
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


# ── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    nome    = st.session_state.get("name", "Usuário")
    usuario = st.session_state.get("username", "")
    inicial = nome[0].upper() if nome else "U"

    st.markdown(f"""
    <div class="user-info-card">
        <div class="user-avatar">{inicial}</div>
        <div class="user-name">{nome}</div>
        <div class="user-login">@{usuario}</div>
    </div>
    """, unsafe_allow_html=True)

    auth.logout("↩  Sair", location="sidebar")
    st.divider()

    st.markdown('<div style="color:#484f58;font-size:.72rem;font-weight:600;letter-spacing:.5px;text-transform:uppercase;margin-bottom:8px;">Sistema</div>', unsafe_allow_html=True)
    st.caption("Conversor NFSe  v1.1")
    st.caption("Modelo Nacional 2026")
    st.caption("ISS Fortaleza / SPED GOV")

# Verificar módulo conversor
if not _CONVERSOR_OK:
    st.error(
        f"Não foi possível carregar `nfse_xml_to_txt.py`:\n\n`{_CONVERSOR_ERR}`\n\n"
        "Verifique se o arquivo está na mesma pasta que `app_web.py`."
    )
    st.stop()


# ── HELPER ───────────────────────────────────────────────────────────────────
def processar_uploads(uploaded_files, im: str, modo: str):
    with tempfile.TemporaryDirectory() as tmp:
        for uf in uploaded_files:
            uf.seek(0)
            with open(os.path.join(tmp, uf.name), "wb") as fh:
                fh.write(uf.read())

        ext   = "txt" if modo == "txt" else "xlsx"
        saida = os.path.join(tmp, f"resultado.{ext}")

        buf = io.StringIO()
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


# ── INTERFACE PRINCIPAL ───────────────────────────────────────────────────────

# Hero
st.markdown("""
<div class="hero">
    <div class="hero-badge">✦ NFSe · Modelo Nacional</div>
    <div class="hero-title">Conversor de Notas Fiscais</div>
    <p class="hero-sub">Transforme XMLs de NFSe no layout do portal ISS Fortaleza ou na planilha SPED GOV — sem instalar nada.</p>
    <div class="hero-chips">
        <span class="chip">📄 ISS Fortaleza</span>
        <span class="chip">📊 SPED GOV</span>
        <span class="chip">🔒 Acesso seguro</span>
        <span class="chip">⚡ Processamento em segundos</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Card: Upload
st.markdown("""
<div class="card-title">
    <span class="icon">📁</span> Arquivos XML
</div>
""", unsafe_allow_html=True)

uploaded = st.file_uploader(
    "xml_upload",
    type=["xml"],
    accept_multiple_files=True,
    label_visibility="collapsed",
    help="Selecione um ou mais arquivos XML de NFSe",
)

if uploaded:
    total = len(uploaded)
    nomes = [u.name for u in uploaded]
    preview = ", ".join(nomes[:4]) + (f"  …+{total-4} mais" if total > 4 else "")
    st.caption(f"✅  {total} arquivo{'s' if total > 1 else ''} carregado{'s' if total > 1 else ''}:  {preview}")

st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

# Card: IM
st.markdown("""
<div class="card-title">
    <span class="icon">🏢</span> Inscrição Municipal Tomadora
</div>
""", unsafe_allow_html=True)

im_input = st.text_input(
    "im",
    placeholder="Ex: 12345678-0  (deixe em branco para usar a do XML)",
    label_visibility="collapsed",
)
st.caption(
    "ℹ️  Notas **emitidas em Fortaleza** são ignoradas no modo TXT "
    "(o portal já as importa automaticamente). Exceção: MEI."
)

st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

# Card: Ações
st.markdown("""
<div class="card-title">
    <span class="icon">⚡</span> Processar
</div>
""", unsafe_allow_html=True)

col1, col2 = st.columns(2, gap="medium")
btn_txt  = col1.button("▶  Gerar Fortaleza (TXT)",  use_container_width=True, type="primary")
btn_xlsx = col2.button("▶  Gerar SPED GOV (XLSX)",  use_container_width=True)

# ── Lógica de processamento ───────────────────────────────────────────────────
if btn_txt or btn_xlsx:
    if not uploaded:
        st.warning("Selecione pelo menos um arquivo XML antes de processar.")
    else:
        modo = "txt" if btn_txt else "xlsx"
        im   = im_input.strip() or "0"

        tipo_label = "ISS Fortaleza (TXT)" if modo == "txt" else "SPED GOV (XLSX)"
        with st.spinner(f"Processando {len(uploaded)} arquivo(s) — {tipo_label}…"):
            dados_saida, log = processar_uploads(uploaded, im, modo)

        # Log
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown("""
        <div class="card-title">
            <span class="icon">📋</span> Log de Processamento
        </div>
        """, unsafe_allow_html=True)
        st.code(log.strip() if log.strip() else "(nenhuma saída registrada)", language="")

        # Resultado
        if dados_saida:
            ext  = "txt" if modo == "txt" else "xlsx"
            mime = (
                "text/plain"
                if modo == "txt"
                else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            nome = f"nfse_{modo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
            tamanho_kb = round(len(dados_saida) / 1024, 1)

            st.markdown(f"""
            <div class="result-box">
                <div class="result-icon">✅</div>
                <div class="result-text">
                    <div class="result-title">Processamento concluído com sucesso!</div>
                    <div class="result-name">{nome} &nbsp;·&nbsp; {tamanho_kb} KB</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.download_button(
                label=f"⬇  Baixar  {nome}",
                data=dados_saida,
                file_name=nome,
                mime=mime,
                use_container_width=True,
            )
        else:
            st.error(
                "Nenhum arquivo foi gerado. "
                "Verifique o log acima para mais detalhes."
            )

# Footer
st.markdown("""
<div class="footer">
    Conversor NFSe v1.1 &nbsp;·&nbsp; Modelo Nacional 2026 &nbsp;·&nbsp;
    ISS Fortaleza / SPED GOV
</div>
""", unsafe_allow_html=True)
