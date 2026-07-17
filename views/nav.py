"""views/nav.py — Sidebar de navegação compartilhada"""
import streamlit as st
from auth.security import current_user, is_admin, logout, has_permission


_PAGES = [
    ("conversor",       "sync",           "Converter"),
    ("arquivo_fortes",  "description",    "Arquivo Fortes"),
    ("baixar_xmls",     "cloud_download", "Baixar XML"),
    ("nfe_nfce",        "receipt",        "NFE / NFCE"),
    ("certificados",    "verified_user",  "Certificados"),
    ("milhao",          "receipt_long",   "Notas do Milhão"),
    ("dashboard",       "monitoring",     "Dashboard"),
    ("siga_consulta",  "summarize",      "Consulta DTE"),
    ("siga_downloads", "cloud_sync",     "Relatórios SIGA"),
]
_ADMIN_PAGE = ("usuarios", "manage_accounts", "Usuários")


def render(current_page: str = ""):
    admin = is_admin()

    with st.sidebar:
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
            key, icon_ms, label = item
            if not admin and not has_permission(key):
                continue

            active = (key == current_page)

            if active:
                # Active item: pure HTML, no button needed
                st.markdown(f"""
<div style="display:flex;align-items:center;gap:10px;padding:10px 13px;
            margin:2px 8px;border-radius:8px;border-left:3px solid #00e5ff;
            background:rgba(0,229,255,.08);">
  <span class="ms" style="color:#00e5ff;font-size:20px;">{icon_ms}</span>
  <span style="color:#00e5ff;font-family:Manrope,sans-serif;font-size:13px;font-weight:700;">{label}</span>
</div>""", unsafe_allow_html=True)
            else:
                # Invisible button (absolute, z-index:10) sits on top of overlay
                if st.button("‎", key=f"nb_{key}_{current_page}",
                             use_container_width=True):
                    st.session_state.pagina = key
                    st.rerun()
                # Overlay is in normal flow — takes 38px; button is absolute on top
                st.markdown(f"""
<div style="display:flex;align-items:center;gap:10px;padding:11px 13px;margin:0 8px;
            border-radius:8px;pointer-events:none;position:relative;z-index:1;
            font-family:Manrope,sans-serif;font-size:13px;font-weight:600;color:#bac9cc;
            white-space:nowrap;overflow:hidden;">
  <span class="ms" style="color:#6b7fa3;font-size:20px;">{icon_ms}</span>
  {label}
</div>""", unsafe_allow_html=True)

        # ── Footer + logout ────────────────────────────────────────────────
        if st.button("↪  Sair", key=f"logout_{current_page}", use_container_width=True):
            logout()
        st.markdown("""
<div style="display:flex;align-items:center;justify-content:center;padding:10px 13px;
            margin:20px 8px 4px;border-radius:8px;pointer-events:none;position:relative;z-index:1;
            font-family:Manrope,sans-serif;font-size:13px;font-weight:600;color:#f87171;
            background:rgba(244,63,94,.05);border:1px solid rgba(244,63,94,.15);
            border-top:1px solid rgba(255,255,255,.07);">
  ↪  Sair
</div>
""", unsafe_allow_html=True)
