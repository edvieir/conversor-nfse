"""views/dashboard.py — Dashboard Fiscal Hub"""

import streamlit as st
from datetime import datetime, timedelta
from auth.security import is_admin, has_permission, current_user
from db.database import get_stats, get_conversions
from views import nav


def render():
    nav.render("dashboard")

    user     = current_user()
    admin    = is_admin()
    filtro   = None if admin else user["username"]

    s = get_stats(usuario=filtro)
    total      = s.get("total", 0)
    hoje       = s.get("hoje", 0)
    mes        = s.get("mes", 0)
    xmls       = s.get("xmls", 0)
    txt_count  = s.get("txt", 0)
    xlsx_count = s.get("xlsx", 0)

    # ── Cabeçalho ─────────────────────────────────────────────────────────
    titulo = "Visão Geral" if admin else f"Meu Painel"
    subtit = "Desempenho global de todos os usuários." if admin else "Suas conversões e atividade recente."

    st.markdown(f"""
<div style="margin-bottom:1.8rem;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
    <div style="width:38px;height:38px;border-radius:10px;background:linear-gradient(135deg,#00b8cc,#0077a8);
                display:flex;align-items:center;justify-content:center;box-shadow:0 0 18px rgba(0,229,255,.25);">
      <span class="ms" style="color:#fff;font-size:20px;">monitoring</span>
    </div>
    <h1 style="color:#dce1fb;font-size:1.75rem;font-weight:800;letter-spacing:-.02em;margin:0;font-family:Manrope,sans-serif;">{titulo}</h1>
  </div>
  <p style="color:#6b7a99;font-size:.85rem;margin:0 0 0 48px;font-family:Manrope,sans-serif;">{subtit}</p>
</div>
""", unsafe_allow_html=True)

    # ── KPI cards ─────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4, gap="medium")

    _kpi(c1,
         icon="sync_alt", icon_color="#00e5ff", bg="#0f2a3f",
         label="Conversões Totais", value=f"{total:,}",
         sub=f"{xmls:,} XMLs processados", sub_color="#10B981")

    _kpi(c2,
         icon="today", icon_color="#a78bfa", bg="#1a1040",
         label="Hoje", value=str(hoje),
         sub=f"Este mês: {mes}", sub_color="#a78bfa")

    _kpi(c3,
         icon="description", icon_color="#34d399", bg="#0d2b20",
         label="Arquivos TXT", value=f"{txt_count:,}",
         sub="Gerados com sucesso", sub_color="#34d399")

    _kpi(c4,
         icon="table_chart", icon_color="#f59e0b", bg="#2b1f06",
         label="Arquivos XLSX", value=f"{xlsx_count:,}",
         sub="Gerados com sucesso", sub_color="#f59e0b")

    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

    # ── Gráfico + lateral ─────────────────────────────────────────────────
    col_chart, col_side = st.columns([3, 1], gap="medium")

    with col_chart:
        import pandas as pd
        agora    = datetime.now()
        dias     = [(agora - timedelta(days=i)).date() for i in range(13, -1, -1)]
        por_dia  = s.get("por_dia", {})
        contagem = [por_dia.get(str(d), 0) for d in dias]
        rotulos  = [str(d)[5:] for d in dias]

        with st.container(border=True):
            st.markdown("""
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;">
  <div style="color:#dce1fb;font-size:.95rem;font-weight:700;font-family:Manrope,sans-serif;">
    Volume de Conversões — últimos 14 dias
  </div>
</div>
""", unsafe_allow_html=True)
            df = pd.DataFrame({"Conversões": contagem}, index=rotulos)
            st.area_chart(df, color="#00e5ff", height=210)

    with col_side:
        with st.container(border=True):
            st.markdown("""
<div style="color:#849396;font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
            margin-bottom:14px;font-family:Manrope,sans-serif;">Status dos Serviços</div>
""", unsafe_allow_html=True)
            _status_dot("API SPED", True)
            st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
            _status_dot("ISS Fortaleza", True)
            st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
            _status_dot("API NFS-e Nacional", True)

        st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown("""
<div style="color:#849396;font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
            margin-bottom:12px;font-family:Manrope,sans-serif;">Ações Rápidas</div>
""", unsafe_allow_html=True)
            if admin or has_permission("conversor"):
                if st.button("📄  Gerar Lote TXT", use_container_width=True, key="dash_txt"):
                    st.session_state.pagina = "conversor"
                    st.rerun()
            if admin or has_permission("baixar_xmls"):
                if st.button("☁️  Baixar XMLs/PDFs", use_container_width=True, key="dash_xml"):
                    st.session_state.pagina = "baixar_xmls"
                    st.rerun()
            if admin or has_permission("certificados"):
                if st.button("🔐  Certificados", use_container_width=True, key="dash_cert"):
                    st.session_state.pagina = "certificados"
                    st.rerun()

    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

    # ── Tabela de atividade ───────────────────────────────────────────────
    recentes = get_conversions(limit=30, usuario=filtro)

    st.markdown("""
<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">
  <span class="ms" style="color:#849396;font-size:18px;">history</span>
  <span style="color:#dce1fb;font-size:1rem;font-weight:700;font-family:Manrope,sans-serif;">Atividade Recente</span>
</div>
""", unsafe_allow_html=True)

    if not recentes:
        st.markdown("""
<div style="background:#111827;border:1px solid rgba(255,255,255,.06);border-radius:12px;
            padding:40px 24px;text-align:center;color:#4a5568;font-family:Manrope,sans-serif;font-size:.88rem;">
  Nenhuma conversão registrada ainda. Use o conversor para ver o histórico aqui.
</div>""", unsafe_allow_html=True)
    else:
        rows = ""
        for conv in recentes:
            ok      = conv.get("sucesso", True)
            modo    = conv.get("modo", "")
            n_arq   = conv.get("arquivos", 0)
            usuario_conv = conv.get("usuario", "?")
            try:
                ts_str = datetime.fromisoformat(conv["ts"]).strftime("%d/%m %H:%M")
            except Exception:
                ts_str = str(conv.get("ts", ""))[:16].replace("T", " ")

            badge = (
                '<span style="background:rgba(16,185,129,.12);color:#10B981;border:1px solid rgba(16,185,129,.25);'
                'border-radius:20px;padding:3px 12px;font-size:.68rem;font-weight:700;text-transform:uppercase;'
                'letter-spacing:.05em;">Concluído</span>'
                if ok else
                '<span style="background:rgba(244,63,94,.12);color:#f43f5e;border:1px solid rgba(244,63,94,.25);'
                'border-radius:20px;padding:3px 12px;font-size:.68rem;font-weight:700;text-transform:uppercase;'
                'letter-spacing:.05em;">Erro</span>'
            )

            icon_modo  = "📄" if modo == "TXT" else "📊" if modo == "XLSX" else "☁️"
            dest       = "ISS Fortaleza" if modo == "TXT" else ("SPED GOV" if modo == "XLSX" else "NFS-e API")

            # admins veem o usuário; usuários comuns veem só os próprios dados
            col_usuario = f'<td style="padding:11px 16px;color:#6b7a99;font-size:.78rem;font-family:Manrope,sans-serif;">{usuario_conv}</td>' if admin else ""

            rows += f"""
<tr style="border-bottom:1px solid rgba(255,255,255,.035);">
  <td style="padding:11px 24px;">
    <div style="display:flex;align-items:center;gap:10px;">
      <div style="width:32px;height:32px;border-radius:8px;background:#1a2235;border:1px solid rgba(255,255,255,.07);
                  display:flex;align-items:center;justify-content:center;font-size:15px;flex-shrink:0;">{icon_modo}</div>
      <span style="color:#dce1fb;font-size:.82rem;font-weight:600;font-family:Manrope,sans-serif;">
        {n_arq} XML{"s" if n_arq != 1 else ""} &rarr; {modo or "—"}
      </span>
    </div>
  </td>
  {col_usuario}
  <td style="padding:11px 16px;color:#6b7a99;font-size:.80rem;font-family:Manrope,sans-serif;">{dest}</td>
  <td style="padding:11px 16px;color:#6b7a99;font-size:.80rem;font-family:Manrope,sans-serif;">{ts_str}</td>
  <td style="padding:11px 24px;text-align:right;">{badge}</td>
</tr>"""

        col_usuario_th = '<th style="padding:9px 16px;color:#849396;font-size:.65rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;text-align:left;font-family:Manrope,sans-serif;">Usuário</th>' if admin else ""

        st.markdown(f"""
<div style="background:#0d1117;border:1px solid rgba(255,255,255,.06);border-radius:14px;overflow:hidden;">
<table style="width:100%;border-collapse:collapse;">
  <thead>
    <tr style="background:rgba(0,0,0,.3);">
      <th style="padding:9px 24px;color:#849396;font-size:.65rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;text-align:left;font-family:Manrope,sans-serif;">Arquivo</th>
      {col_usuario_th}
      <th style="padding:9px 16px;color:#849396;font-size:.65rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;text-align:left;font-family:Manrope,sans-serif;">Destino</th>
      <th style="padding:9px 16px;color:#849396;font-size:.65rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;text-align:left;font-family:Manrope,sans-serif;">Data</th>
      <th style="padding:9px 24px;color:#849396;font-size:.65rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;text-align:right;font-family:Manrope,sans-serif;">Status</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div style="text-align:center;color:#1e2d42;font-size:.7rem;padding:2rem 0 .5rem;font-family:Manrope,sans-serif;">
  © 2026 Fiscal Hub v2.0 &nbsp;&middot;&nbsp; Conversor NFS-e
</div>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _kpi(col, *, icon, icon_color, bg, label, value, sub, sub_color):
    with col:
        st.markdown(f"""
<div style="background:{bg};border:1px solid rgba(255,255,255,.06);border-radius:14px;padding:20px 22px;">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;">
    <span class="ms" style="color:{icon_color};font-size:18px;">{icon}</span>
    <span style="color:#849396;font-size:10px;font-weight:700;letter-spacing:.09em;
                 text-transform:uppercase;font-family:Manrope,sans-serif;">{label}</span>
  </div>
  <div style="font-size:2.2rem;font-weight:800;color:#dce1fb;font-family:Manrope,sans-serif;line-height:1;">{value}</div>
  <div style="color:{sub_color};font-size:.73rem;margin-top:8px;font-family:Manrope,sans-serif;">{sub}</div>
</div>""", unsafe_allow_html=True)


def _status_dot(nome, online: bool):
    cor   = "#10B981" if online else "#ef4444"
    label = "Online"  if online else "Offline"
    st.markdown(f"""
<div style="display:flex;align-items:center;gap:10px;">
  <div style="width:9px;height:9px;border-radius:50%;background:{cor};
              box-shadow:0 0 7px {cor}88;flex-shrink:0;"></div>
  <div>
    <div style="color:#dce1fb;font-size:.82rem;font-weight:600;font-family:Manrope,sans-serif;">{nome}</div>
    <div style="color:{cor};font-size:.68rem;font-family:Manrope,sans-serif;">{label}</div>
  </div>
</div>""", unsafe_allow_html=True)
