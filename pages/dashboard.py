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
        <div class="topbar-spacer"></div>
        <div class="topbar-divider"></div>
        <span class="topbar-tag">Dashboard &amp; Estatísticas</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Navbar ───────────────────────────────────────────────────────────────
    if is_admin():
        _nc1, _nc2, _nc3, _nc4, _nc5 = st.columns([2.5, 1.5, 1.9, 1.5, 1.0])
    else:
        _nc1, _nc2, _nc3, _nc4 = st.columns([2.8, 1.5, 1.9, 1.0])

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

    with _nc3:
        if st.button("Notas do Milhao", key="nav_milhao_dash", use_container_width=True):
            st.session_state.pagina = "milhao"
            st.rerun()

    if is_admin():
        with _nc4:
            if st.button("Usuarios", key="nav_users_dash", use_container_width=True):
                st.session_state.pagina = "usuarios"
                st.rerun()
        with _nc5:
            if st.button("Sair", key="logout_dash", use_container_width=True):
                logout()
    else:
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

    # ── Gráficos ──────────────────────────────────────────────────────────────
    if s["total"] > 0:
        import plotly.graph_objects as go

        agora   = datetime.now()
        dias    = [(agora - timedelta(days=i)).date() for i in range(13, -1, -1)]
        por_dia = s.get("por_dia", {})
        labels  = [str(d)[5:] for d in dias]
        values  = [por_dia.get(str(d), 0) for d in dias]

        # ── Gráfico de linha — últimos 14 dias ───────────────────────────────
        st.markdown(
            f'<div class="dash-section-title">{icon("activity", 13, "#8B949E")} '
            f'Conversões nos últimos 14 dias</div>',
            unsafe_allow_html=True,
        )

        fig_linha = go.Figure()
        fig_linha.add_trace(go.Scatter(
            x=labels, y=values,
            mode="lines+markers",
            line=dict(color="#00CED1", width=2.5, shape="spline"),
            marker=dict(color="#00CED1", size=7, line=dict(color="#0A0E1A", width=2)),
            fill="tozeroy",
            fillcolor="rgba(0,206,209,0.08)",
            hovertemplate="<b>%{x}</b><br>%{y} conversão(ões)<extra></extra>",
        ))
        fig_linha.update_layout(
            height=220, margin=dict(l=0, r=0, t=10, b=0),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False, color="#484F58", tickfont=dict(size=11)),
            yaxis=dict(showgrid=True, gridcolor="#1C2333", color="#484F58",
                       tickfont=dict(size=11), rangemode="tozero"),
            font=dict(family="Inter, sans-serif"),
            hoverlabel=dict(bgcolor="#161B27", bordercolor="#2F3E55",
                            font=dict(color="#E6EDF3", size=12)),
        )
        st.plotly_chart(fig_linha, use_container_width=True, config={"displayModeBar": False})

        # ── Linha 2: barras TXT vs XLSX + pizza por formato ──────────────────
        col_bar, col_pie = st.columns([3, 2])

        with col_bar:
            txt_v  = s.get("txt",  0)
            xlsx_v = s.get("xlsx", 0)
            st.markdown(
                f'<div class="dash-section-title">{icon("bar-chart-2", 13, "#8B949E")} '
                f'TXT vs XLSX gerados</div>',
                unsafe_allow_html=True,
            )
            fig_bar = go.Figure(data=[
                go.Bar(name="TXT",  x=["TXT"],  y=[txt_v],
                       marker_color="#00CED1", width=0.4,
                       hovertemplate="<b>TXT</b><br>%{y}<extra></extra>"),
                go.Bar(name="XLSX", x=["XLSX"], y=[xlsx_v],
                       marker_color="#7B3FE4", width=0.4,
                       hovertemplate="<b>XLSX</b><br>%{y}<extra></extra>"),
            ])
            fig_bar.update_layout(
                height=200, margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                showlegend=False, barmode="group",
                xaxis=dict(showgrid=False, color="#484F58"),
                yaxis=dict(showgrid=True, gridcolor="#1C2333", color="#484F58",
                           rangemode="tozero"),
                font=dict(family="Inter, sans-serif"),
                hoverlabel=dict(bgcolor="#161B27", bordercolor="#2F3E55",
                                font=dict(color="#E6EDF3", size=12)),
            )
            st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})

        with col_pie:
            st.markdown(
                f'<div class="dash-section-title">{icon("pie-chart", 13, "#8B949E")} '
                f'Distribuição</div>',
                unsafe_allow_html=True,
            )
            pie_labels = ["TXT", "XLSX"]
            pie_values = [txt_v, xlsx_v]
            fig_pie = go.Figure(data=[go.Pie(
                labels=pie_labels, values=pie_values,
                hole=0.55,
                marker=dict(colors=["#00CED1", "#7B3FE4"],
                            line=dict(color="#0A0E1A", width=2)),
                textfont=dict(color="#E6EDF3", size=12),
                hovertemplate="<b>%{label}</b><br>%{value} (%{percent})<extra></extra>",
            )])
            fig_pie.update_layout(
                height=200, margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                legend=dict(font=dict(color="#8B949E", size=11),
                            bgcolor="rgba(0,0,0,0)"),
                font=dict(family="Inter, sans-serif"),
                hoverlabel=dict(bgcolor="#161B27", bordercolor="#2F3E55",
                                font=dict(color="#E6EDF3", size=12)),
            )
            st.plotly_chart(fig_pie, use_container_width=True, config={"displayModeBar": False})

        # ── Por usuário — só admin vê ─────────────────────────────────────────
        if is_admin() and s["por_usuario"]:
            st.markdown(
                f'<div class="dash-section-title" style="margin-top:6px;">'
                f'{icon("users", 13, "#8B949E")} Uso por usuário</div>',
                unsafe_allow_html=True,
            )
            usr_nomes  = list(s["por_usuario"].keys())
            usr_counts = list(s["por_usuario"].values())
            cores = ["#7B3FE4", "#00CED1", "#2F6FEB", "#F59E0B", "#10B981",
                     "#EF4444", "#8B5CF6", "#06B6D4"]
            fig_usr = go.Figure(go.Bar(
                x=usr_nomes, y=usr_counts,
                marker_color=cores[:len(usr_nomes)],
                hovertemplate="<b>%{x}</b><br>%{y} conversão(ões)<extra></extra>",
            ))
            fig_usr.update_layout(
                height=200, margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=False, color="#484F58"),
                yaxis=dict(showgrid=True, gridcolor="#1C2333", color="#484F58",
                           rangemode="tozero"),
                font=dict(family="Inter, sans-serif"),
                hoverlabel=dict(bgcolor="#161B27", bordercolor="#2F3E55",
                                font=dict(color="#E6EDF3", size=12)),
            )
            st.plotly_chart(fig_usr, use_container_width=True, config={"displayModeBar": False})

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
