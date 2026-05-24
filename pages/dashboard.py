"""
pages/dashboard.py — Dashboard de métricas e histórico de conversões
"""

import streamlit as st
from datetime import datetime, timedelta
from auth.security import current_user, is_admin, logout
from db.database import get_stats, get_conversions
from assets.icons import icon


def render():
    user = current_user()
    inicial = user["name"][0].upper() if user["name"] else "U"

    # ── Top bar ──────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="topbar">
        <div class="topbar-logo">
            {icon("bar-chart", 16, "#fff")}
        </div>
        <span class="topbar-name">Conversor NFS-e</span>
        <div class="topbar-divider"></div>
        <span class="topbar-tag">Dashboard &amp; Estatísticas</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Navbar ───────────────────────────────────────────────────────────────
    if is_admin():
        _nc1, _nc2, _nc3, _nc4 = st.columns([4, 1.8, 1.8, 1.2])
    else:
        _nc1, _nc2, _nc4 = st.columns([5, 1.8, 1.2])

    with _nc1:
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:8px;padding:6px 0;">
            <div class="navbar-avatar">{inicial}</div>
            <span class="navbar-name">{user["name"]}</span>
        </div>""", unsafe_allow_html=True)

    with _nc2:
        if st.button("Conversor", key="nav_conv_dash", use_container_width=True):
            st.session_state.pagina = "conversor"
            st.rerun()

    if is_admin():
        with _nc3:
            if st.button("Usuarios", key="nav_users_dash", use_container_width=True):
                st.session_state.pagina = "usuarios"
                st.rerun()

    with _nc4:
        if st.button("Sair", key="logout_dash", use_container_width=True):
            logout()

    st.markdown('<div style="height:.4rem;"></div>', unsafe_allow_html=True)

    # ── Dados ─────────────────────────────────────────────────────────────────
    s = get_stats()

    # ── Cards de métricas ─────────────────────────────────────────────────────
    st.markdown(
        f'<div class="dash-section-title">{icon("activity", 13, "#8B949E")} Visão Geral</div>',
        unsafe_allow_html=True,
    )

    ic_refresh  = icon("refresh-cw",  28, "#00CED1")
    ic_calendar = icon("calendar",    28, "#00CED1")
    ic_grid     = icon("grid",        28, "#00CED1")
    ic_folder   = icon("folder",      28, "#00CED1")
    ic_filetxt  = icon("file-text",   28, "#00CED1")
    ic_barchart = icon("bar-chart",   28, "#00CED1")

    st.markdown(f"""
    <div class="dash-grid">
        <div class="dash-card">
            <div class="dash-card-svg">{ic_refresh}</div>
            <div class="dash-value">{s["total"]}</div>
            <div class="dash-label">Conversões totais</div>
        </div>
        <div class="dash-card">
            <div class="dash-card-svg">{ic_calendar}</div>
            <div class="dash-value">{s["hoje"]}</div>
            <div class="dash-label">Hoje</div>
        </div>
        <div class="dash-card">
            <div class="dash-card-svg">{ic_grid}</div>
            <div class="dash-value">{s["mes"]}</div>
            <div class="dash-label">Este mês</div>
        </div>
        <div class="dash-card">
            <div class="dash-card-svg">{ic_folder}</div>
            <div class="dash-value">{s["xmls"]}</div>
            <div class="dash-label">XMLs processados</div>
        </div>
        <div class="dash-card">
            <div class="dash-card-svg">{ic_filetxt}</div>
            <div class="dash-value">{s["txt"]}</div>
            <div class="dash-label">TXT gerados</div>
        </div>
        <div class="dash-card">
            <div class="dash-card-svg">{ic_barchart}</div>
            <div class="dash-value">{s["xlsx"]}</div>
            <div class="dash-label">XLSX gerados</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Gráfico últimos 14 dias ───────────────────────────────────────────────
    if s["total"] > 0:
        import pandas as _pd

        st.markdown(
            f'<div class="dash-section-title">{icon("activity", 13, "#8B949E")} '
            f'Conversões nos últimos 14 dias</div>',
            unsafe_allow_html=True,
        )

        agora = datetime.now()
        dias  = [(agora - timedelta(days=i)).date() for i in range(13, -1, -1)]
        por_dia = s.get("por_dia", {})
        contagem = {str(d): por_dia.get(str(d), 0) for d in dias}

        df_dias = _pd.DataFrame({
            "Dia":        [str(d)[5:] for d in dias],
            "Conversoes": [contagem[str(d)] for d in dias],
        }).set_index("Dia")

        st.bar_chart(df_dias, color="#00CED1", height=210)

        # Por usuário — só admin vê
        if is_admin() and s["por_usuario"]:
            st.markdown(
                f'<div class="dash-section-title" style="margin-top:14px;">'
                f'{icon("users", 13, "#8B949E")} Uso por usuário</div>',
                unsafe_allow_html=True,
            )
            df_usr = _pd.DataFrame(
                {"Conversoes": list(s["por_usuario"].values())},
                index=list(s["por_usuario"].keys()),
            )
            st.bar_chart(df_usr, color="#7B3FE4", height=175)

    # ── Atividade recente ─────────────────────────────────────────────────────
    st.markdown(
        f'<div class="dash-section-title" style="margin-top:14px;">'
        f'{icon("clipboard", 13, "#8B949E")} Atividade recente</div>',
        unsafe_allow_html=True,
    )

    recentes = get_conversions(limit=20)

    if not recentes:
        ic_info = icon("info", 15, "#00A8AB")
        st.markdown(
            f'<div class="info-box">{ic_info}'
            f'<span class="box-text">Nenhuma conversão registrada ainda. '
            f'Use o conversor para ver o histórico aqui.</span></div>',
            unsafe_allow_html=True,
        )
    else:
        linhas_html = ""
        for c in recentes:
            dot_cls   = "activity-dot-ok"  if c.get("sucesso") else "activity-dot-err"
            badge_cls = "ab-txt"           if c.get("modo") == "TXT" else "ab-xlsx"
            n_arq     = c.get("arquivos", 0)
            label     = f'{c.get("usuario","?")} &mdash; {n_arq} XML{"s" if n_arq != 1 else ""}'
            try:
                ts_str = datetime.fromisoformat(c["ts"]).strftime("%d/%m %H:%M")
            except Exception:
                ts_str = str(c.get("ts", ""))[:16].replace("T", " ")
            linhas_html += f"""
            <div class="activity-row">
                <div class="activity-dot {dot_cls}"></div>
                <span class="activity-label">{label}</span>
                <span class="activity-badge {badge_cls}">{c.get("modo","")}</span>
                <span class="activity-meta">{ts_str}</span>
            </div>"""

        st.markdown(f"""
        <div style="background:#0D1117;border:1px solid #1C2333;
                    border-radius:12px;padding:12px 16px 4px;">
            {linhas_html}
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div class="footer">
        Conversor NFS-e &nbsp;v2.0 &nbsp;&middot;&nbsp; Dashboard
    </div>
    """, unsafe_allow_html=True)
