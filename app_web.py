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
    page_title="Conversor NFS-e  |  ISS Fortaleza",
    page_icon="📊",
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

/* Ocultar elementos padrão do Streamlit */
#MainMenu {visibility: hidden;}
footer    {visibility: hidden;}

*, *::before, *::after { box-sizing: border-box; }
html, body, [data-testid="stAppViewContainer"] {
    background: #0F172A !important;
    font-family: 'Inter', sans-serif;
}
[data-testid="stHeader"]  { background: transparent !important; }
[data-testid="stSidebar"] { background: #1E293B !important; border-right: 1px solid #334155; }
.block-container          { max-width: 700px; padding: 2rem 1.5rem 4rem; }

body, p, div, span, li { color: #CBD5E1; }
h1,h2,h3,h4            { color: #F8FAFC !important; font-weight: 700; }
label                   { color: #94A3B8 !important; font-size: .78rem !important;
                          font-weight: 600 !important; letter-spacing: .3px !important; }

/* ── STEP CONTAINERS (st.container border=True) ── */
[data-testid="stVerticalBlockBorderWrapper"] {
    border: 1px solid #334155 !important;
    border-left: 4px solid #10B981 !important;
    border-radius: 12px !important;
    background: #1E293B !important;
    padding: 6px 14px 14px !important;
    margin-bottom: 18px !important;
    box-shadow: 0 4px 24px rgba(0,0,0,.25) !important;
}

/* ── LOGIN FORM ── */
[data-testid="stForm"] {
    max-width: 400px !important;
    margin: 0 auto !important;
    background: #1E293B !important;
    border: 1px solid #334155 !important;
    border-radius: 16px !important;
    padding: 32px 36px !important;
    box-shadow: 0 24px 60px rgba(0,0,0,.5) !important;
}
/* Ocultar título "Login" gerado pelo streamlit-authenticator */
[data-testid="stForm"] h2 { display: none !important; }

/* Botão de submit do formulário de login */
[data-testid="stFormSubmitButton"] > button {
    background: #10B981 !important;
    color: #fff !important; border: none !important;
    border-radius: 8px !important; width: 100% !important;
    padding: .75rem 1rem !important; font-weight: 700 !important;
    font-size: .95rem !important; letter-spacing: .3px !important;
    box-shadow: 0 2px 12px #10B98135 !important; transition: all .25s !important;
    margin-top: .5rem !important;
}
[data-testid="stFormSubmitButton"] > button:hover {
    background: #D97706 !important;
    box-shadow: 0 4px 18px #D9770645 !important;
    transform: translateY(-1px) !important;
}

/* ── BADGE ── */
.badge {
    display: inline-block;
    background: #1E293B; color: #10B981;
    border: 1px solid #334155; border-radius: 20px;
    font-size: .7rem; font-weight: 700; letter-spacing: .6px;
    padding: 3px 12px; margin-bottom: 12px; text-transform: uppercase;
}

/* ── HERO ── */
.hero {
    background: #1E293B;
    border: 1px solid #334155;
    border-left: 4px solid #10B981;
    border-radius: 12px;
    padding: 28px 32px 24px;
    margin-bottom: 28px;
}
.hero-title {
    color: #F8FAFC; font-size: 1.75rem; font-weight: 800;
    letter-spacing: -.3px; margin: 0 0 8px; line-height: 1.2;
}
.hero-sub { color: #64748B; font-size: .88rem; margin: 0 0 16px; }
.hero-chips { display: flex; gap: 8px; flex-wrap: wrap; }
.chip {
    background: #0F172A; border: 1px solid #334155; color: #64748B;
    border-radius: 20px; font-size: .7rem; font-weight: 500; padding: 4px 11px;
}

/* ── ADMIN HERO ── */
.admin-hero {
    background: #1E293B;
    border: 1px solid #334155;
    border-left: 4px solid #10B981;
    border-radius: 12px;
    padding: 24px 32px 20px;
    margin-bottom: 24px;
}
.admin-hero-title {
    color: #F8FAFC; font-size: 1.4rem; font-weight: 800;
    letter-spacing: -.3px; margin: 0 0 6px;
}
.admin-hero-sub { color: #64748B; font-size: .85rem; }

/* ── ETAPAS ── */
.step-header {
    display: flex; align-items: flex-start; gap: 14px;
    margin: 24px 0 12px;
}
.step-num {
    min-width: 32px; height: 32px;
    background: #10B981;
    color: #fff; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: .85rem; font-weight: 800; flex-shrink: 0;
    box-shadow: 0 2px 8px #10B98140;
}
.step-title { color: #F8FAFC; font-weight: 700; font-size: .95rem; }
.step-desc  { color: #475569; font-size: .78rem; margin-top: 2px; }

/* ── CARDS DE FORMATO ── */
.format-card {
    background: #1E293B; border: 1px solid #334155;
    border-radius: 10px; padding: 14px 16px; margin-bottom: 10px;
    text-align: center;
    transition: border-color .2s;
}
.format-card:hover { border-color: #10B981; }
.format-icon { font-size: 1.6rem; margin-bottom: 6px; }
.format-name { color: #F8FAFC; font-weight: 700; font-size: .9rem; }
.format-desc { color: #475569; font-size: .75rem; margin-top: 4px; line-height: 1.4; }

/* ── LISTA DE ARQUIVOS ── */
.file-list {
    background: #0F172A; border: 1px solid #334155;
    border-left: 3px solid #10B981;
    border-radius: 8px; padding: 12px 14px; margin: 8px 0 4px;
}
.file-list-header { color: #10B981; font-size: .78rem; font-weight: 700; margin-bottom: 8px; }
.file-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.file-chip {
    background: #1E293B; border: 1px solid #334155; color: #94A3B8;
    border-radius: 6px; font-size: .72rem; padding: 3px 10px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 220px;
}
.file-chip-more {
    background: #1E293B; border: 1px solid #10B98160; color: #10B981;
    border-radius: 6px; font-size: .72rem; padding: 3px 10px;
}

/* ── INFO / WARN / ERROR / SUCCESS ── */
.info-box {
    background: #0F172A; border: 1px solid #334155; border-left: 3px solid #38BDF8;
    border-radius: 6px; padding: 10px 14px; margin: 8px 0;
    color: #7BA7C0; font-size: .8rem; line-height: 1.5;
}
.warn-box {
    background: #1C1A0D; border: 1px solid #4A3E00; border-left: 3px solid #D97706;
    border-radius: 6px; padding: 10px 14px; margin: 12px 0;
    color: #D97706; font-size: .82rem;
}
.error-box {
    background: #1A0D0D; border: 1px solid #4A1515; border-left: 3px solid #EF4444;
    border-radius: 6px; padding: 10px 14px; margin: 12px 0;
    color: #EF4444; font-size: .82rem;
}
.success-box {
    background: #0A1F10; border: 1px solid #166534; border-left: 3px solid #10B981;
    border-radius: 6px; padding: 10px 14px; margin: 12px 0;
    color: #10B981; font-size: .82rem;
}

/* ── TABELA DE USUÁRIOS ── */
.user-table {
    width: 100%; border-collapse: collapse;
    background: #1E293B; border-radius: 10px; overflow: hidden;
    border: 1px solid #334155; margin: 12px 0 20px;
}
.user-table th {
    background: #0F172A; color: #475569; font-size: .72rem;
    font-weight: 700; letter-spacing: .5px; text-transform: uppercase;
    padding: 10px 14px; border-bottom: 1px solid #334155; text-align: left;
}
.user-table td {
    padding: 10px 14px; border-bottom: 1px solid #334155;
    color: #CBD5E1; font-size: .83rem;
}
.user-table tr:last-child td { border-bottom: none; }
.user-table tr:hover td { background: #0F172A; }
.user-badge {
    display: inline-block; background: #0F172A; color: #10B981;
    border: 1px solid #10B98160; border-radius: 12px;
    font-size: .65rem; font-weight: 700; padding: 2px 9px;
}
.user-badge-admin {
    background: #0F172A; color: #D97706; border-color: #D9770660;
}

/* ── RESULTADO ── */
.result-success {
    background: #1E293B;
    border: 1px solid #334155; border-left: 4px solid #10B981;
    border-radius: 12px;
    padding: 18px 22px; margin: 16px 0 12px;
    display: flex; align-items: center; gap: 16px;
}
.result-success-icon { font-size: 2rem; flex-shrink: 0; }
.result-success-title { color: #10B981; font-weight: 700; font-size: .95rem; }
.result-success-meta  { color: #475569; font-size: .78rem; margin-top: 4px; }

/* ── BOTÕES PRIMÁRIOS (navegação, ações gerais) ── */
div.stButton > button {
    background: #1E293B !important;
    color: #CBD5E1 !important; border: 1px solid #334155 !important;
    border-radius: 8px !important; font-weight: 600 !important;
    font-size: .85rem !important; padding: .55rem .9rem !important;
    letter-spacing: .2px !important; transition: all .2s !important;
    width: 100% !important;
}
div.stButton > button:hover {
    background: #10B981 !important; color: #fff !important;
    border-color: #10B981 !important;
    transform: translateY(-1px) !important; box-shadow: 0 4px 14px #10B98130 !important;
}

/* ── BOTÕES DE AÇÃO (Gerar TXT / XLSX) — type=primary ── */
div.stButton > button[kind="primary"] {
    background: #10B981 !important;
    color: #fff !important; border: none !important;
    font-weight: 700 !important; font-size: .9rem !important;
    padding: .7rem 1rem !important;
    box-shadow: 0 2px 10px #10B98128 !important;
}
div.stButton > button[kind="primary"]:hover {
    background: #059669 !important;
    box-shadow: 0 4px 18px #10B98140 !important;
    color: #fff !important; border-color: transparent !important;
}

/* ── BOTÃO DOWNLOAD ── */
div.stDownloadButton > button {
    background: #10B981 !important;
    color: #fff !important; border: none !important; border-radius: 8px !important;
    font-weight: 700 !important; font-size: .92rem !important;
    padding: .7rem 1.2rem !important;
    box-shadow: 0 2px 10px #10B98128 !important; transition: all .25s !important;
}
div.stDownloadButton > button:hover {
    background: #D97706 !important;
    transform: translateY(-1px) !important; box-shadow: 0 4px 16px #D9770645 !important;
}

/* ── INPUTS ── */
[data-testid="stTextInput"] input {
    background: #1E293B !important; color: #F8FAFC !important;
    border: 1px solid #334155 !important; border-radius: 8px !important;
    font-size: .88rem !important; padding: .55rem .85rem !important;
    transition: border-color .2s, box-shadow .2s !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: #D97706 !important; box-shadow: 0 0 0 2px #D9770630 !important;
}
[data-testid="stTextInput"] input::placeholder { color: #475569 !important; }

/* ── FILE UPLOADER ── */
[data-testid="stFileUploader"] {
    background: #0F172A !important; border: 2px dashed #334155 !important;
    border-radius: 10px !important; padding: .6rem !important; transition: border-color .2s !important;
}
[data-testid="stFileUploader"]:hover { border-color: #10B981 !important; }
[data-testid="stFileUploader"] * { color: #64748B !important; }

/* ── LOG / CODE ── */
[data-testid="stCode"], pre {
    background: #0F172A !important; border: 1px solid #334155 !important;
    border-radius: 8px !important; color: #94A3B8 !important;
    font-size: .78rem !important; line-height: 1.6 !important;
}

/* ── EXPANDER ── */
[data-testid="stExpander"] {
    background: #1E293B !important; border: 1px solid #334155 !important;
    border-radius: 8px !important;
}

/* ── SIDEBAR ── */
[data-testid="stSidebar"] * { color: #94A3B8 !important; }
[data-testid="stSidebar"] strong { color: #F8FAFC !important; }
.user-info-card {
    background: #0F172A; border: 1px solid #334155;
    border-radius: 10px; padding: 14px 16px; margin-bottom: 12px;
}
.user-avatar {
    width: 38px; height: 38px;
    background: #10B981;
    border-radius: 50%; display: flex; align-items: center;
    justify-content: center; font-size: 1rem; margin-bottom: 10px;
}
.user-name  { color: #F8FAFC !important; font-weight: 700; font-size: .9rem; }
.user-login { color: #475569 !important; font-size: .75rem; margin-top: 2px; }

/* ── FOOTER ── */
.footer {
    text-align: center; color: #334155; font-size: .72rem;
    margin-top: 2.5rem; padding-top: 1rem; border-top: 1px solid #1E293B;
}

/* ── LOGIN FORM ── */
[data-testid="stForm"] {
    background: #1E293B; border: 1px solid #334155;
    border-radius: 14px; padding: 24px 28px !important;
}
[data-testid="stCaptionContainer"] { color: #94A3B8 !important; font-size: .78rem !important; }
hr { border-color: #334155 !important; margin: 1rem 0 !important; }

/* ── SELECT BOX ── */
[data-testid="stSelectbox"] > div > div {
    background: #1E293B !important; border: 1px solid #334155 !important;
    border-radius: 8px !important; color: #F8FAFC !important;
}
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
    <div style="text-align:center; padding: 2.5rem 0 1.5rem;">
        <div style="font-size:3.2rem; margin-bottom:.5rem;">📊</div>
        <span class="badge">Autenticação</span>
        <div style="color:#F8FAFC; font-size:1.5rem; font-weight:800; letter-spacing:-.3px; margin-top:.4rem;">
            🛡️ Acesso Restrito
        </div>
        <div style="color:#475569; font-size:.88rem; margin-top:.4rem;">
            Identifique-se para acessar o sistema.
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
    <div style="text-align:center; color:#334155; font-size:.75rem; margin-top:1.5rem;">
        🔒 Acesso restrito · Entre com suas credenciais acima
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
    st.caption("Conversor NFS-e  v1.4")
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


def processar_xlsx_sped(uploaded_files, im: str):
    """Gera XLSX no layout exato do SPED GOV — aba 'Serviços Tomados', 43 colunas."""
    import glob as _glob
    import openpyxl
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    # Cabeçalhos e larguras exatas do SPED GOV
    COLUNAS = [
        ("Tipo Doc.",                       24.14),
        ("Número",                          10.28),
        ("Código de Verificação",           23.57),
        ("Competência",                     14.57),
        ("Data",                            11.42),
        ("Vencimento",                      13.42),
        ("Número RPS",                      18.42),
        ("Série RPS",                       11.14),
        ("Tipo RPS",                        10.28),
        ("Natureza da Operação",            27.71),
        ("Regime Especial Tributação",      52.14),
        ("Operação Simples Nacional",       29.28),
        ("Incentivador Cultural",           22.85),
        ("Item da Lista",                   14.57),
        ("CNAE",                           123.14),
        ("ART",                              5.28),
        ("Código Obra",                     13.85),
        ("Número Empenho",                  19.42),
        ("Discriminação dos Serviços",     141.14),
        ("Valor dos Serviços",              20.28),
        ("Deduções Permitidas em Lei",      30.42),
        ("Desconto Condicionado",           25.28),
        ("Desconto Incondicionado",         27.00),
        ("Retenções Federais",              21.28),
        ("Outras Retenções",               19.42),
        ("PIS",                              4.42),
        ("COFINS",                           8.85),
        ("IRRF",                             5.71),
        ("CSLL",                             6.14),
        ("INSS",                             5.85),
        ("Base de Cálculo",                 17.28),
        ("Alíquota",                         9.85),
        ("Local da Prestação",              22.14),
        ("ISS Retido",                      11.71),
        ("Valor do ISS",                    13.85),
        ("Valor Líquido",                   14.85),
        ("Status Doc.",                     13.00),
        ("Inscrição Prestador",             21.14),
        ("CPF/CNPJ Prestador",              21.42),
        ("Razão Social/Nome do Prestador",  58.57),
        ("Escrituração",                    13.85),
        ("Origem",                           9.71),
        ("Status Aceite",                   14.85),
    ]

    IBGE_FORTALEZA = "2304400"

    def _float(v):
        try:
            return float(v) if v else 0.0
        except Exception:
            return 0.0

    def _str(v):
        return str(v).strip() if v else ""

    def _data_fmt(iso, fmt):
        """Converte ISO date para DD/MM/YYYY ou MM/YYYY."""
        if not iso:
            return ""
        data_part = iso[:10]  # YYYY-MM-DD
        try:
            partes = data_part.split("-")
            if fmt == "mes":
                return f"{partes[1]}/{partes[0]}"
            else:
                return f"{partes[2]}/{partes[1]}/{partes[0]}"
        except Exception:
            return iso

    def _local_prestacao(d):
        # Tenta xLP (nome do município de prestação), depois lookup pelo código IBGE, depois xMun (emitente)
        uf   = _str(d.get("uf", ""))
        xLP  = _str(d.get("xLP", ""))
        cLP  = _str(d.get("cLP", ""))
        xMun = _str(d.get("xMun", ""))
        nome_mun = (
            xLP
            or getattr(C, "IBGE_TO_NOME", {}).get(cLP, "")
            or xMun
        )
        if nome_mun and uf:
            return f"{nome_mun.upper()} - {uf.upper()}"
        return nome_mun.upper() if nome_mun else ""

    def _cnae_desc(cnae9):
        desc = getattr(C, "CNAE9_TO_DESC", {}).get(cnae9, "")
        return f"{cnae9} - {desc}" if desc else cnae9

    with tempfile.TemporaryDirectory() as tmp:
        for uf_file in uploaded_files:
            uf_file.seek(0)
            with open(os.path.join(tmp, uf_file.name), "wb") as fh:
                fh.write(uf_file.read())

        arquivos = sorted(_glob.glob(os.path.join(tmp, "*.xml")))

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Serviços Tomados"

        # Cabeçalho — bold, tamanho 11, fill indexado 55 (igual ao original)
        header_fill = PatternFill(fill_type="solid", fgColor="C0C0C0")  # cinza prata próximo ao original
        header_font = Font(bold=True, size=11)

        for col_idx, (titulo, largura) in enumerate(COLUNAS, 1):
            cell = ws.cell(row=1, column=col_idx, value=titulo)
            cell.font = header_fill and header_font
            cell.fill = header_fill
            letra = get_column_letter(col_idx)
            ws.column_dimensions[letra].width = largura

        buf   = io.StringIO()
        total = 0
        erros = []

        with contextlib.redirect_stdout(buf):
            for xml_path in arquivos:
                nome_arq = os.path.basename(xml_path)
                try:
                    d = C.parse_nfse(xml_path)

                    if im:
                        d["im"] = im

                    cnae9, item, aliq_cnae = C.resolver_cnae9(d)
                    dhEmi = _str(d.get("dhEmi", ""))

                    # Fixo para SPED GOV — serviços tomados de outros municípios
                    tipo_doc = "NFS-e de Outro Município"
                    natureza = "Tributação Fora do Município"

                    vS      = _float(d.get("vS"))
                    vISS    = _float(d.get("vISS"))
                    vPIS    = _float(d.get("vPIS"))
                    vCOFINS = _float(d.get("vCOFINS"))
                    vINSS   = _float(d.get("vINSS"))
                    # Alíquota: usa o valor do XML; se vazio/zero, usa sugerido pela tabela CNAE
                    aliq    = _float(d.get("aliq")) or float(aliq_cnae or 0)
                    tpRet   = _str(d.get("tpRet", "1"))
                    iss_retido = (tpRet == "2")

                    # Retenções federais: soma numérica (0 se nenhuma)
                    ret_federais = vPIS + vCOFINS + vINSS

                    # Valor do ISS: só mostra se o tomador retém (tpRet=2), senão 0
                    valor_iss_col = vISS if iss_retido else 0

                    ws.append([
                        "NFS-e de Outro Município",        # A  Tipo Doc.        (FIXO)
                        _str(d.get("nDFSe")),             # B  Número           (XML)
                        None,                              # C  Cód. Verificação (FIXO vazio)
                        _data_fmt(dhEmi, "mes"),           # D  Competência      (XML MM/AAAA)
                        _data_fmt(dhEmi, "dia"),           # E  Data             (XML DD/MM/AAAA)
                        "",                                # F  Vencimento       (FIXO vazio)
                        "",                                # G  Número RPS       (FIXO vazio)
                        "",                                # H  Série RPS        (FIXO vazio)
                        "",                                # I  Tipo RPS         (FIXO vazio)
                        "Tributação Fora do Município",    # J  Natureza         (FIXO)
                        "",                                # K  Regime Especial  (FIXO vazio)
                        "Não",                             # L  Simples Nacional (FIXO)
                        None,                              # M  Incentivador     (FIXO vazio)
                        item,                              # N  Item da Lista    (XML)
                        _cnae_desc(cnae9),                 # O  CNAE             (XML cnae9+desc)
                        "",                                # P  ART              (FIXO vazio)
                        "",                                # Q  Código Obra      (FIXO vazio)
                        "",                                # R  Nº Empenho       (FIXO vazio)
                        _str(d.get("desc")),               # S  Discriminação    (XML)
                        vS,                                # T  Valor Serviços   (XML float)
                        "",                                # U  Deduções         (FIXO vazio)
                        "",                                # V  Desc. Condic.    (FIXO vazio)
                        "",                                # W  Desc. Incondic.  (FIXO vazio)
                        ret_federais,                      # X  Ret. Federais    (XML soma, 0 se nenhuma)
                        "",                                # Y  Outras Retenções (FIXO vazio)
                        vPIS    if vPIS    else "",        # Z  PIS              (XML, vazio se 0)
                        vCOFINS if vCOFINS else "",        # AA COFINS           (XML, vazio se 0)
                        "",                                # AB IRRF             (FIXO vazio)
                        "",                                # AC CSLL             (FIXO vazio)
                        vINSS   if vINSS   else "",        # AD INSS             (XML, vazio se 0)
                        vS,                                # AE Base de Cálculo  (XML = vS)
                        aliq,                              # AF Alíquota         (XML ou CNAE)
                        _local_prestacao(d),               # AG Local Prestação  (XML município+UF)
                        "Sim" if iss_retido else "Não",    # AH ISS Retido       (XML tpRet)
                        valor_iss_col,                     # AI Valor do ISS     (XML se retido, 0 se não)
                        vS,                                # AJ Valor Líquido    (XML = vS)
                        "NORMAL",                          # AK Status Doc.      (FIXO)
                        "",                                # AL Inscrição Prest. (FIXO vazio)
                        _str(d.get("cnpj")),               # AM CPF/CNPJ Prest.  (XML)
                        _str(d.get("nome")),               # AN Razão Social     (XML)
                        "Atual",                           # AO Escrituração     (FIXO)
                        "Prestador",                       # AP Origem           (FIXO)
                        "Não informada",                   # AQ Status Aceite    (FIXO)
                    ])

                    # Formatação numérica com 2 casas decimais nas colunas monetárias
                    r = ws.max_row
                    for col_mon in [20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 35, 36]:
                        ws.cell(row=r, column=col_mon).number_format = '#,##0.00'
                    ws.cell(row=r, column=32).number_format = '0.00'  # Alíquota

                    total += 1
                    print(f"  OK   {nome_arq}")
                    print(f"       NFSe {d.get('nDFSe','')} | {d.get('nome','')[:35]}")
                except Exception as exc:
                    erros.append((nome_arq, str(exc)))
                    print(f"  ERRO {nome_arq}: {exc}")

        print(f"\n  Processadas: {total} nota(s)")
        if erros:
            print(f"  Com erro:    {len(erros)}")
            for n, e in erros:
                print(f"    - {n}: {e}")

        log   = buf.getvalue()
        saida = os.path.join(tmp, "resultado.xlsx")
        wb.save(saida)

        data = b""
        if os.path.exists(saida):
            with open(saida, "rb") as fh:
                data = fh.read()

    return data, log


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

    st.divider()

    # ── Salvar logins permanentemente ──
    st.markdown("#### 💾 Salvar logins permanentemente")
    st.markdown("""
    <div class="warn-box">
        ⚠️ <strong>Importante:</strong> Logins criados aqui ficam salvos enquanto o servidor estiver rodando.
        Para que não se percam após atualizações do sistema, baixe o arquivo abaixo e envie para o administrador técnico commitar no repositório.
    </div>
    """, unsafe_allow_html=True)

    with open(_CFG_PATH, "rb") as f_cfg:
        cfg_bytes = f_cfg.read()

    st.download_button(
        label="⬇  Baixar config.yaml atualizado",
        data=cfg_bytes,
        file_name="config.yaml",
        mime="text/plain",
        use_container_width=True,
    )

    st.markdown("""
    <div class="footer">
        Conversor NFS-e v1.4&nbsp;·&nbsp; Painel Administrativo
    </div>
    """, unsafe_allow_html=True)


# ── PÁGINA: CONVERSOR ─────────────────────────────────────────────────────────
def pagina_conversor():
    st.markdown("""
    <div style="text-align:center; padding: 1rem 0 .5rem;">
        <span class="badge">✦ NFS-e · Modelo Nacional 2026</span>
        <div style="color:#F8FAFC; font-size:1.65rem; font-weight:800; letter-spacing:-.3px; margin:.4rem 0 .3rem;">
            📊 Conversor Inteligente NFS-e
        </div>
        <div style="color:#475569; font-size:.88rem; margin-bottom:1.4rem;">
            Processamento e Estruturação de Lotes XML
        </div>
    </div>
    <div class="hero">
        <div class="hero-title" style="font-size:1rem; margin-bottom:6px;">Sobre o sistema</div>
        <p class="hero-sub">Transforme XMLs de NFS-e no layout do portal ISS Fortaleza ou na planilha SPED GOV — direto do navegador, sem instalar nada.</p>
        <div class="hero-chips">
            <span class="chip">📄 ISS Fortaleza</span>
            <span class="chip">📊 SPED GOV</span>
            <span class="chip">🔒 Acesso seguro</span>
            <span class="chip">⚡ Processamento rápido</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── ETAPA 1 ────────────────────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown("""
        <div class="step-header">
            <div class="step-num">1</div>
            <div class="step-info">
                <div class="step-title">Selecione os arquivos XML</div>
                <div class="step-desc">Arraste ou clique para carregar um ou mais XMLs de NFS-e</div>
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
    with st.container(border=True):
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
    with st.container(border=True):
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
            btn_txt = st.button("Gerar TXT", use_container_width=True, type="primary", key="btn_txt")

        with col2:
            st.markdown("""
            <div class="format-card">
                <div class="format-icon">📊</div>
                <div class="format-name">SPED GOV</div>
                <div class="format-desc">Planilha XLSX para o sistema SPED do governo federal</div>
            </div>
            """, unsafe_allow_html=True)
            btn_xlsx = st.button("Gerar XLSX", use_container_width=True, type="primary", key="btn_xlsx")

    # ── Processamento ──────────────────────────────────────────────────────────
    if btn_txt or btn_xlsx:
        if not uploaded:
            st.markdown("""<div class="warn-box">⚠️ Selecione pelo menos um arquivo XML na Etapa 1 antes de processar.</div>""", unsafe_allow_html=True)
        else:
            modo       = "txt" if btn_txt else "xlsx"
            im         = im_input.strip() or "0"
            tipo_label = "ISS Fortaleza (TXT)" if modo == "txt" else "SPED GOV (XLSX)"

            with st.spinner(f"⏳  Processando {len(uploaded)} arquivo(s) — {tipo_label}…"):
                if modo == "xlsx":
                    dados_saida, log = processar_xlsx_sped(uploaded, im_input.strip())
                else:
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
        Conversor NFS-e v1.4&nbsp;·&nbsp; Modelo Nacional 2026 &nbsp;·&nbsp; ISS Fortaleza / SPED GOV
    </div>
    """, unsafe_allow_html=True)


# ── ROTEADOR ─────────────────────────────────────────────────────────────────
pagina = st.session_state.get("pagina", "conversor")

if pagina == "usuarios":
    pagina_usuarios()
else:
    pagina_conversor()
