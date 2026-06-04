"""pages/nav.py — Navbar compartilhada entre todas as páginas"""
import streamlit as st
from auth.security import current_user, is_admin, logout, has_permission
from assets.icons import icon


def render(current_page: str = ""):
    user = current_user()
    inicial = user["name"][0].upper() if user["name"] else "U"

    # Topbar tag por página
    tags = {
        "conversor":    "ISS Fortaleza &middot; SPED GOV &middot; Modelo Nacional 2026",
        "baixar_xmls":  "Baixar XMLs &middot; API NFS-e Nacional",
        "certificados": "Certificados Digitais",
        "milhao":       "Notas do Milhao",
        "dashboard":    "Dashboard",
        "usuarios":     "Painel Administrativo",
    }
    topbar_icon = "shield" if current_page == "usuarios" else "zap"
    tag = tags.get(current_page, "Conversor NFS-e")

    st.markdown(f"""
    <div class="topbar">
        <div class="topbar-logo">{icon(topbar_icon, 16, "#fff")}</div>
        <span class="topbar-name">Conversor NFS-e</span>
        <div class="topbar-spacer"></div>
        <div class="topbar-divider"></div>
        <span class="topbar-tag">{tag}</span>
    </div>
    """, unsafe_allow_html=True)

    # Build button list dynamically based on permissions
    # Each item: (label, pagina_key) — only included if user has permission or is admin
    ALL_PAGES = [
        ("Conversor",    "conversor"),
        ("Baixar XML",   "baixar_xmls"),
        ("Certificados", "certificados"),
        ("Milhão",       "milhao"),
        ("Dashboard",    "dashboard"),
    ]

    # Filter pages based on permission (skip current page's "home" button logic — show all accessible)
    pages_visiveis = [(label, key) for label, key in ALL_PAGES
                     if is_admin() or has_permission(key)]

    # Admin-only pages
    if is_admin():
        pages_visiveis.append(("Usuarios", "usuarios"))

    # Total columns: name col + page buttons + sair
    n_btns = len(pages_visiveis) + 1  # +1 for Sair
    # Name column gets 2.0, each button 1.4, sair 1.0
    ratios = [2.0] + [1.4] * len(pages_visiveis) + [1.0]
    cols = st.columns(ratios)

    with cols[0]:
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:8px;padding:6px 0;">
            <div class="navbar-avatar">{inicial}</div>
            <span class="navbar-name">{user["name"]}</span>
        </div>""", unsafe_allow_html=True)

    for i, (label, key) in enumerate(pages_visiveis):
        with cols[i + 1]:
            if st.button(label, key=f"nav_{key}_{current_page}", use_container_width=True):
                st.session_state.pagina = key
                st.rerun()

    with cols[-1]:
        if st.button("Sair", key=f"logout_{current_page}", use_container_width=True):
            logout()

    st.markdown('<div style="height:.6rem;"></div>', unsafe_allow_html=True)
