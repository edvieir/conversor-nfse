#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py — Entry point do Conversor NFS-e v2.0
Responsabilidades: configuração inicial, CSS, autenticação e roteamento.
"""

import sys
import os
from pathlib import Path
from unittest.mock import MagicMock

# ── MOCK tkinter ANTES de qualquer import que carregue nfse_xml_to_txt ────────
# nfse_xml_to_txt.py usa tkinter para sua interface desktop.
# Como rodamos em modo web (Streamlit), substituímos por mocks para evitar erros.
for _mod in (
    "tkinter", "tkinter.simpledialog", "tkinter.filedialog",
    "tkinter.messagebox", "tkinter.ttk", "tkinter.font",
):
    sys.modules.setdefault(_mod, MagicMock())

# Adiciona a raiz do projeto ao path (garante importação de nfse_xml_to_txt)
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

# set_page_config DEVE ser a primeira chamada Streamlit
st.set_page_config(
    page_title="Conversor NFS-e  |  ISS Fortaleza",
    page_icon="assets/app_icon.ico" if Path("assets/app_icon.ico").exists() else None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── BANCO DE DADOS ─────────────────────────────────────────────────────────────
from db.database import init_db
init_db()   # cria tabelas, migra config.yaml, aplica bootstrap admin

# ── CSS ────────────────────────────────────────────────────────────────────────
def _load_css():
    css_path = Path(__file__).parent / "assets" / "style.css"
    if css_path.exists():
        with open(css_path, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        st.warning("assets/style.css nao encontrado.")

_load_css()
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet">
<style>
.ms {
    font-family: 'Material Symbols Outlined' !important;
    font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
    font-size: 20px; line-height: 1; font-style: normal;
    display: inline-block; flex-shrink: 0;
}
/* Sidebar nav buttons — override global stButton styles */
[data-testid="stSidebar"] [data-testid="stButton"] > button,
[data-testid="stSidebar"] button[kind="secondary"],
[data-testid="stSidebar"] button[data-testid="baseButton-secondary"] {
    background: transparent !important;
    color: #bac9cc !important;
    border: none !important;
    border-radius: 8px !important;
    font-size: .86rem !important;
    font-weight: 600 !important;
    height: 2.4rem !important;
    width: calc(100% - 16px) !important;
    margin: 1px 8px !important;
    text-align: left !important;
    justify-content: flex-start !important;
    padding-left: 12px !important;
    box-shadow: none !important;
    display: flex !important;
    align-items: center !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] > button:hover,
[data-testid="stSidebar"] button[data-testid="baseButton-secondary"]:hover {
    background: rgba(255,255,255,.06) !important;
    color: #dce1fb !important;
    border: none !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] [data-testid="stButton"]:last-of-type > button {
    color: #f87171 !important;
    background: rgba(244,63,94,.05) !important;
    border: 1px solid rgba(244,63,94,.15) !important;
    justify-content: center !important;
    margin-top: 4px !important;
}
</style>
""", unsafe_allow_html=True)

# ── AUTENTICAÇÃO ───────────────────────────────────────────────────────────────
from auth.security import require_login
require_login()   # para o app se nao autenticado e exibe tela de login

# ── ESTADO INICIAL DA SESSÃO ───────────────────────────────────────────────────
if "pagina" not in st.session_state:
    st.session_state["pagina"] = "conversor"

# ── ROTEADOR ───────────────────────────────────────────────────────────────────
from views import conversor, dashboard, usuarios, milhao, baixar_xmls, certificados

pagina = st.session_state.get("pagina", "conversor")

if pagina == "dashboard":
    dashboard.render()
elif pagina == "usuarios":
    usuarios.render()
elif pagina == "milhao":
    milhao.render()
elif pagina == "baixar_xmls":
    baixar_xmls.render()
elif pagina == "certificados":
    certificados.render()
else:
    conversor.render()
