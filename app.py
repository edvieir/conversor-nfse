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
    layout="centered",
    initial_sidebar_state="collapsed",
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

# ── AUTENTICAÇÃO ───────────────────────────────────────────────────────────────
from auth.security import require_login
require_login()   # para o app se nao autenticado e exibe tela de login

# ── ESTADO INICIAL DA SESSÃO ───────────────────────────────────────────────────
if "pagina" not in st.session_state:
    st.session_state["pagina"] = "conversor"

# ── ROTEADOR ───────────────────────────────────────────────────────────────────
from pages import conversor, dashboard, usuarios, milhao, baixar_xmls, certificados

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
