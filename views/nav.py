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
    user  = current_user()
    admin = is_admin()

    with st.sidebar:
        # ── Brand ─────────────────────────────────────────────────────────
        st.markdown("""
<div style="padding:24px 16px 16px;border-bottom:1px solid rgba(255,255,255,.05);margin-bottom:8px;">
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

        # ── Nova Conversão (visual) ────────────────────────────────────────
        st.markdown("""
<div style="padding:8px 16px 12px;">
  <div style="background:#00e5ff;color:#00363d;border-radius:8px;padding:10px 16px;
              display:flex;align-items:center;justify-content:center;gap:6px;
              font-family:Manrope,sans-serif;font-weight:700;font-size:13px;
              box-shadow:0 0 15px rgba(0,229,255,.2);">
    <span class="ms" style="color:#00363d;font-size:18px;">add</span>
    Nova Conversão
  </div>
</div>
""", unsafe_allow_html=True)

        # ── Nav items ─────────────────────────────────────────────────────
        pages = list(_PAGES)
        if admin:
            pages.append(_ADMIN_PAGE)

        for key, icon_name, label in pages:
            if not admin and not has_permission(key):
                continue

            active = (key == current_page)

            if active:
                st.markdown(f"""
<div style="display:flex;align-items:center;gap:10px;padding:10px 16px;
            margin:2px 8px;border-radius:8px;border-left:3px solid #00e5ff;
            background:rgba(0,229,255,.08);padding-left:13px;">
  <span class="ms" style="color:#00e5ff;">{icon_name}</span>
  <span style="color:#00e5ff;font-family:Manrope,sans-serif;font-size:13px;font-weight:700;">{label}</span>
</div>
""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
<div style="display:flex;align-items:center;gap:10px;padding:10px 16px;
            margin:2px 8px;border-radius:8px;">
  <span class="ms" style="color:#849396;">{icon_name}</span>
  <span style="color:#bac9cc;font-family:Manrope,sans-serif;font-size:13px;font-weight:600;">{label}</span>
</div>
""", unsafe_allow_html=True)
                # Botão invisível sobreposto ao item HTML acima
                if st.button(label, key=f"nb_{key}_{current_page}", use_container_width=True):
                    st.session_state.pagina = key
                    st.rerun()

        # ── Footer ────────────────────────────────────────────────────────
        st.markdown("""
<div style="border-top:1px solid rgba(255,255,255,.05);margin-top:24px;padding-top:8px;">
  <div style="display:flex;align-items:center;gap:10px;padding:10px 16px;margin:2px 8px;border-radius:8px;">
    <span class="ms" style="color:#849396;">help</span>
    <span style="color:#849396;font-family:Manrope,sans-serif;font-size:13px;font-weight:600;">Help Center</span>
  </div>
</div>
""", unsafe_allow_html=True)

        if st.button("Sair", key=f"logout_{current_page}", use_container_width=True):
            logout()
