"""pages/nav.py — Sidebar de navegação compartilhada"""
import streamlit as st
from auth.security import current_user, is_admin, logout, has_permission


# Material Symbols icon name + Portuguese label for each page
_PAGES = [
    ("conversor",    "sync",           "Converter"),
    ("baixar_xmls",  "cloud_download", "Baixar XML"),
    ("certificados", "verified_user",  "Certificados"),
    ("milhao",       "receipt_long",   "Milhão"),
    ("dashboard",    "monitoring",     "Overview"),
]
_ADMIN_PAGE = ("usuarios", "manage_accounts", "Usuários")


def render(current_page: str = ""):
    user = current_user()
    admin = is_admin()

    with st.sidebar:
        # Inject Material Symbols font + nav CSS
        st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet"/>
<style>
.ms { font-family:'Material Symbols Outlined'; font-variation-settings:'FILL' 0,'wght' 400,'GRAD' 0,'opsz' 24;
      font-size:20px; line-height:1; font-style:normal; }
.nav-item {
    display:flex; align-items:center; gap:12px;
    padding:10px 16px; border-radius:8px; margin:2px 8px;
    cursor:pointer; transition:background .15s;
    font-family:Manrope,sans-serif; font-size:13px; font-weight:600;
    color:#bac9cc; text-decoration:none;
}
.nav-item:hover { background:rgba(255,255,255,.05); color:#dce1fb; }
.nav-active {
    background:rgba(0,229,255,.08) !important;
    border-left:3px solid #00e5ff !important;
    color:#00e5ff !important;
    padding-left:13px !important;
}
.nav-active .ms { color:#00e5ff; }
</style>
""", unsafe_allow_html=True)

        # ── Brand ──────────────────────────────────────────────────────────
        st.markdown("""
<div style="padding:24px 16px 16px; border-bottom:1px solid rgba(255,255,255,.05); margin-bottom:8px;">
  <div style="display:flex;align-items:center;gap:10px;">
    <div style="width:40px;height:40px;border-radius:10px;background:#1E293B;
                border:1px solid rgba(255,255,255,.1);display:flex;align-items:center;
                justify-content:center;">
      <span class="ms" style="color:#00e5ff;font-size:22px;">hub</span>
    </div>
    <div>
      <div style="color:#00e5ff;font-weight:800;font-size:16px;line-height:1.1;font-family:Manrope,sans-serif;">Fiscal Hub</div>
      <div style="color:#849396;font-size:11px;font-weight:600;letter-spacing:.5px;font-family:Manrope,sans-serif;">Premium SaaS</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

        # ── New Conversion button (visual only) ────────────────────────────
        st.markdown("""
<div style="padding:8px 16px 12px;">
  <div style="background:#00e5ff;color:#00363d;border-radius:8px;padding:10px 16px;
              display:flex;align-items:center;justify-content:center;gap:6px;
              font-family:Manrope,sans-serif;font-weight:700;font-size:13px;
              box-shadow:0 0 15px rgba(0,229,255,.2);cursor:pointer;">
    <span class="ms" style="font-size:18px;color:#00363d;">add</span>
    Nova Conversão
  </div>
</div>
""", unsafe_allow_html=True)

        st.markdown('<div style="height:4px;"></div>', unsafe_allow_html=True)

        # ── Nav items ──────────────────────────────────────────────────────
        pages = list(_PAGES)
        if admin:
            pages.append(_ADMIN_PAGE)

        for key, icon_name, label in pages:
            if not admin and not has_permission(key):
                continue

            active = (key == current_page)
            cls = "nav-item nav-active" if active else "nav-item"

            st.markdown(f"""
<div class="{cls}">
  <span class="ms">{icon_name}</span>
  <span>{label}</span>
</div>
""", unsafe_allow_html=True)

            if not active:
                # Invisible secondary button overlapping the HTML div above
                if st.button("nav", key=f"nb_{key}_{current_page}",
                             use_container_width=True, type="secondary"):
                    st.session_state.pagina = key
                    st.rerun()

        # ── Footer ─────────────────────────────────────────────────────────
        st.markdown("""
<div style="flex:1;min-height:40px;"></div>
<div style="border-top:1px solid rgba(255,255,255,.05);margin-top:16px;padding-top:8px;">
  <div class="nav-item" style="color:#849396;">
    <span class="ms">help</span>
    <span>Help Center</span>
  </div>
</div>
""", unsafe_allow_html=True)

        if st.button("Sair", key=f"logout_{current_page}",
                     use_container_width=True, type="primary"):
            logout()
