"""pages/nav.py — Sidebar de navegação compartilhada"""
import streamlit as st
from auth.security import current_user, is_admin, logout, has_permission
from assets.icons import icon


# Ícones para cada página
_PAGE_ICONS = {
    "conversor":    ("bar-chart-2", "Converter"),
    "baixar_xmls":  ("download-cloud", "Baixar XML"),
    "certificados": ("shield", "Certificados"),
    "milhao":       ("file-text", "Milhão"),
    "dashboard":    ("activity", "Dashboard"),
    "usuarios":     ("users", "Usuários"),
}


def render(current_page: str = ""):
    user = current_user()

    with st.sidebar:
        # ── Brand ────────────────────────────────────────────────────────────
        ic_brand = icon("zap", 20, "#00e5ff")
        st.markdown(f"""
        <div style="padding:1.4rem 1.2rem .8rem;border-bottom:1px solid #1e2d45;margin-bottom:.8rem;">
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:.2rem;">
                <div style="background:linear-gradient(135deg,#00b8cc,#007a8a);border-radius:8px;
                            width:34px;height:34px;display:flex;align-items:center;justify-content:center;
                            box-shadow:0 0 16px rgba(0,229,255,.3);">
                    {ic_brand}
                </div>
                <div>
                    <div style="color:#e2e8f0;font-weight:800;font-size:.95rem;line-height:1.1;">Fiscal Hub</div>
                    <div style="color:#8b9ab5;font-size:.65rem;font-weight:600;letter-spacing:.5px;">CONVERSOR NFS-e</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── New Conversion / user info ────────────────────────────────────────
        st.markdown(f"""
        <div style="padding:.4rem 1rem .6rem;">
            <div style="color:#4a5568;font-size:.65rem;font-weight:700;letter-spacing:.6px;
                        text-transform:uppercase;margin-bottom:.3rem;">CONTA</div>
            <div style="display:flex;align-items:center;gap:8px;">
                <div style="width:28px;height:28px;border-radius:8px;
                            background:linear-gradient(135deg,#00b8cc,#5b21b6);
                            display:flex;align-items:center;justify-content:center;
                            color:#fff;font-weight:800;font-size:.8rem;flex-shrink:0;">
                    {user["name"][0].upper() if user["name"] else "U"}
                </div>
                <div style="overflow:hidden;">
                    <div style="color:#e2e8f0;font-weight:600;font-size:.78rem;
                                white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
                                max-width:140px;">{user["name"]}</div>
                    <div style="color:#4a5568;font-size:.65rem;">{"Admin" if is_admin() else "Usuário"}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div style="height:.3rem;"></div>', unsafe_allow_html=True)

        # ── Navigation items ──────────────────────────────────────────────────
        st.markdown("""
        <div style="padding:0 .8rem;">
            <div style="color:#4a5568;font-size:.65rem;font-weight:700;letter-spacing:.6px;
                        text-transform:uppercase;padding:.4rem .2rem .3rem;">MENU</div>
        </div>
        """, unsafe_allow_html=True)

        ALL_PAGES = [
            "conversor", "baixar_xmls", "certificados", "milhao", "dashboard"
        ]

        for key in ALL_PAGES:
            if not is_admin() and not has_permission(key):
                continue
            ic_name, label = _PAGE_ICONS[key]
            ic_color = "#00e5ff" if current_page == key else "#8b9ab5"
            ic_svg = icon(ic_name, 15, ic_color)

            if current_page == key:
                # Active state
                st.markdown(f"""
                <div style="background:rgba(0,229,255,.08);border:1px solid rgba(0,229,255,.15);
                            border-radius:8px;padding:.45rem .9rem;margin:.15rem .8rem;
                            display:flex;align-items:center;gap:10px;cursor:default;">
                    {ic_svg}
                    <span style="color:#00e5ff;font-size:.82rem;font-weight:700;">{label}</span>
                </div>
                """, unsafe_allow_html=True)
            else:
                with st.container():
                    if st.button(f"{label}", key=f"nav_{key}_{current_page}", use_container_width=True):
                        st.session_state.pagina = key
                        st.rerun()

        if is_admin():
            key = "usuarios"
            ic_name, label = _PAGE_ICONS[key]
            ic_color = "#00e5ff" if current_page == key else "#8b9ab5"
            ic_svg = icon(ic_name, 15, ic_color)
            if current_page == key:
                st.markdown(f"""
                <div style="background:rgba(0,229,255,.08);border:1px solid rgba(0,229,255,.15);
                            border-radius:8px;padding:.45rem .9rem;margin:.15rem .8rem;
                            display:flex;align-items:center;gap:10px;">
                    {ic_svg}
                    <span style="color:#00e5ff;font-size:.82rem;font-weight:700;">{label}</span>
                </div>
                """, unsafe_allow_html=True)
            else:
                if st.button(label, key=f"nav_{key}_{current_page}", use_container_width=True):
                    st.session_state.pagina = key
                    st.rerun()

        # ── Spacer + footer ───────────────────────────────────────────────────
        st.markdown('<div style="flex:1;"></div>', unsafe_allow_html=True)
        st.markdown("""
        <div style="border-top:1px solid #1e2d45;padding:.6rem 1rem .2rem;margin-top:1rem;">
            <div style="color:#4a5568;font-size:.72rem;font-weight:600;">Help Center</div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Sair", key=f"logout_{current_page}", use_container_width=True):
            logout()
