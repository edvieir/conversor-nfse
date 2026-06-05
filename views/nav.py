"""views/nav.py — Sidebar de navegação compartilhada"""
import streamlit as st
from auth.security import current_user, is_admin, logout, has_permission


_PAGES = [
    ("conversor",    "sync",           "Converter"),
    ("baixar_xmls",  "cloud_download", "Baixar XML"),
    ("certificados", "verified_user",  "Certificados"),
    ("milhao",       "receipt_long",   "Milhão"),
    ("dashboard",    "monitoring",     "Overview"),
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

        # ── Nav items (pure HTML links — no st.button CSS conflicts) ───────
        pages = list(_PAGES)
        if admin:
            pages.append(_ADMIN_PAGE)

        nav_html = ""
        for item in pages:
            key, icon_ms, label = item
            if not admin and not has_permission(key):
                continue

            if key == current_page:
                nav_html += f"""
<div style="display:flex;align-items:center;gap:10px;padding:10px 13px;
            margin:2px 8px;border-radius:8px;border-left:3px solid #00e5ff;
            background:rgba(0,229,255,.08);">
  <span class="ms" style="color:#00e5ff;font-size:20px;">{icon_ms}</span>
  <span style="color:#00e5ff;font-family:Manrope,sans-serif;font-size:13px;font-weight:700;">{label}</span>
</div>"""
            else:
                nav_html += f"""
<a href="?nav={key}" target="_self" style="display:flex;align-items:center;gap:10px;padding:10px 13px;
   margin:2px 8px;border-radius:8px;text-decoration:none;
   color:#bac9cc;font-family:Manrope,sans-serif;font-size:13px;font-weight:600;
   transition:background .15s,color .15s;"
   onmouseover="this.style.background='rgba(255,255,255,.06)';this.style.color='#dce1fb';"
   onmouseout="this.style.background='transparent';this.style.color='#bac9cc';">
  <span class="ms" style="color:#6b7fa3;font-size:20px;">{icon_ms}</span>
  {label}
</a>"""

        st.markdown(nav_html, unsafe_allow_html=True)

        # ── Footer + logout ────────────────────────────────────────────────
        st.markdown("""
<div style="border-top:1px solid rgba(255,255,255,.05);margin-top:24px;padding-top:4px;"></div>
""", unsafe_allow_html=True)

        if st.button("↪  Sair", key=f"logout_{current_page}", use_container_width=True):
            logout()
