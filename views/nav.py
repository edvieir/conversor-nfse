"""views/nav.py — Sidebar de navegação compartilhada"""
import streamlit as st
from auth.security import current_user, is_admin, logout, has_permission


_PAGES = [
    ("conversor",    "sync",           "🔄", "Converter"),
    ("baixar_xmls",  "cloud_download", "⬇️", "Baixar XML"),
    ("certificados", "verified_user",  "🔐", "Certificados"),
    ("milhao",       "receipt_long",   "📋", "Milhão"),
    ("dashboard",    "monitoring",     "📊", "Overview"),
]
_ADMIN_PAGE = ("usuarios", "manage_accounts", "👥", "Usuários")


def render(current_page: str = ""):
    admin = is_admin()

    with st.sidebar:
        # Inject scoped button CSS — overrides global stButton styles inside sidebar
        st.markdown("""<style>
section[data-testid="stSidebar"] button[data-testid="baseButton-secondary"],
section[data-testid="stSidebar"] button[kind="secondary"],
section[data-testid="stSidebar"] div[data-testid="stButton"] > button {
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
section[data-testid="stSidebar"] button[data-testid="baseButton-secondary"]:hover,
section[data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {
    background: rgba(255,255,255,.06) !important;
    color: #dce1fb !important;
    border: none !important;
    box-shadow: none !important;
}
section[data-testid="stSidebar"] div[data-testid="stButton"]:last-of-type > button,
section[data-testid="stSidebar"] button[data-testid="baseButton-secondary"]:last-of-type {
    color: #f87171 !important;
    background: rgba(244,63,94,.05) !important;
    border: 1px solid rgba(244,63,94,.15) !important;
    justify-content: center !important;
    margin-top: 4px !important;
}
</style>""", unsafe_allow_html=True)

        # ── Brand ─────────────────────────────────────────────────────────
        st.markdown("""
<div style="padding:24px 16px 16px;border-bottom:1px solid rgba(255,255,255,.05);margin-bottom:12px;">
  <div style="display:flex;align-items:center;gap:10px;">
    <div style="width:40px;height:40px;border-radius:10px;background:#1E293B;
                border:1px solid rgba(255,255,255,.1);display:flex;align-items:center;justify-content:center;">
      <span class="ms" style="color:#00e5ff;font-size:22px;">hub</span>
    </div>
    <div>
      <div style="color:#00e5ff;font-weight:800;font-size:16px;line-height:1.1;font-family:Manrope,sans-serif;">Fiscal Hub</div>
      <div style="color:#849396;font-size:11px;font-weight:600;letter-spacing:.5px;font-family:Manrope,sans-serif;">Premium SaaS</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

        # ── Nav items ─────────────────────────────────────────────────────
        pages = list(_PAGES)
        if admin:
            pages.append(_ADMIN_PAGE)

        for item in pages:
            key, icon_ms, emoji, label = item
            if not admin and not has_permission(key):
                continue

            active = (key == current_page)

            if active:
                st.markdown(f"""
<div style="display:flex;align-items:center;gap:10px;padding:10px 13px;
            margin:2px 8px;border-radius:8px;border-left:3px solid #00e5ff;
            background:rgba(0,229,255,.08);">
  <span class="ms" style="color:#00e5ff;font-size:20px;">{icon_ms}</span>
  <span style="color:#00e5ff;font-family:Manrope,sans-serif;font-size:13px;font-weight:700;">{label}</span>
</div>""", unsafe_allow_html=True)
            else:
                if st.button(f"{emoji}  {label}", key=f"nb_{key}_{current_page}",
                             use_container_width=True):
                    st.session_state.pagina = key
                    st.rerun()

        # ── Footer ────────────────────────────────────────────────────────
        st.markdown("""
<div style="border-top:1px solid rgba(255,255,255,.05);margin-top:24px;padding-top:4px;">
</div>
""", unsafe_allow_html=True)

        if st.button("↪  Sair", key=f"logout_{current_page}", use_container_width=True):
            logout()
