"""views/dashboard.py — Dashboard Fiscal Hub"""

import streamlit as st
from datetime import datetime, timedelta
from auth.security import is_admin, has_permission, current_user
from db.database import get_stats, get_conversions
from views import nav

_MODO_LABEL = {
    "TXT":   ("📄", "ISS Fortaleza",        "#00e5ff"),
    "XLSX":  ("📊", "SPED GOV",              "#a78bfa"),
    "FS":    ("🗂️", "Arquivo Fortes",        "#34d399"),
    "XML":   ("☁️", "Download XML — API",   "#f59e0b"),
    "PDF":   ("📑", "Download PDF — API",   "#fb923c"),
    "AMBOS": ("☁️", "Download XML+PDF — API","#f59e0b"),
}


def render():
    nav.render("dashboard")

    user   = current_user()
    admin  = is_admin()
    filtro = None if admin else user["username"]

    s          = get_stats(usuario=filtro)
    total      = s.get("total", 0)
    hoje       = s.get("hoje", 0)
    mes        = s.get("mes", 0)
    xmls_total = s.get("xmls", 0)
    txt_count  = s.get("txt", 0)
    xlsx_count = s.get("xlsx", 0)
    fs_count   = s.get("fs", 0)
    xml_api    = s.get("xml_api", 0)
    pdf_api    = s.get("pdf_api", 0)

    # ── Cabeçalho ─────────────────────────────────────────────────────────
    titulo = "Visão Geral" if admin else "Meu Painel"
    subtit = "Desempenho global de todos os usuários." if admin else "Suas conversões e atividade recente."

    st.markdown(f"""
<div style="margin-bottom:2rem;">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px;">
    <div style="width:40px;height:40px;border-radius:12px;
                background:linear-gradient(135deg,#00b8cc 0%,#0077a8 100%);
                display:flex;align-items:center;justify-content:center;
                box-shadow:0 0 22px rgba(0,229,255,.3);flex-shrink:0;">
      <span class="ms" style="color:#fff;font-size:22px;">monitoring</span>
    </div>
    <div>
      <h1 style="color:#e2e8f0;font-size:1.7rem;font-weight:800;letter-spacing:-.03em;
                 margin:0;font-family:Manrope,sans-serif;">{titulo}</h1>
      <p style="color:#64748b;font-size:.82rem;margin:2px 0 0;font-family:Manrope,sans-serif;">{subtit}</p>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Faixa de resumo rápido ─────────────────────────────────────────────
    st.markdown(f"""
<div style="background:linear-gradient(90deg,rgba(0,184,204,.08) 0%,rgba(0,119,168,.04) 100%);
            border:1px solid rgba(0,229,255,.12);border-radius:14px;
            padding:14px 24px;margin-bottom:1.2rem;
            display:flex;align-items:center;gap:32px;flex-wrap:wrap;">
  <div style="display:flex;align-items:center;gap:10px;">
    <span class="ms" style="color:#00e5ff;font-size:18px;">bolt</span>
    <div>
      <div style="color:#94a3b8;font-size:.68rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-family:Manrope,sans-serif;">Total de Operações</div>
      <div style="color:#e2e8f0;font-size:1.3rem;font-weight:800;font-family:Manrope,sans-serif;">{total:,}</div>
    </div>
  </div>
  <div style="width:1px;height:36px;background:rgba(255,255,255,.08);"></div>
  <div style="display:flex;align-items:center;gap:10px;">
    <span class="ms" style="color:#a78bfa;font-size:18px;">today</span>
    <div>
      <div style="color:#94a3b8;font-size:.68rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-family:Manrope,sans-serif;">Hoje</div>
      <div style="color:#e2e8f0;font-size:1.3rem;font-weight:800;font-family:Manrope,sans-serif;">{hoje}</div>
    </div>
  </div>
  <div style="width:1px;height:36px;background:rgba(255,255,255,.08);"></div>
  <div style="display:flex;align-items:center;gap:10px;">
    <span class="ms" style="color:#34d399;font-size:18px;">calendar_month</span>
    <div>
      <div style="color:#94a3b8;font-size:.68rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-family:Manrope,sans-serif;">Este Mês</div>
      <div style="color:#e2e8f0;font-size:1.3rem;font-weight:800;font-family:Manrope,sans-serif;">{mes}</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── KPI cards (2 linhas × 3) ───────────────────────────────────────────
    c1, c2, c3 = st.columns(3, gap="medium")
    _kpi(c1, icon="description",   color="#00e5ff", glow="#00e5ff",
         label="Lotes TXT",        value=f"{txt_count:,}",
         sub="Conversões ISS Fortaleza",    sub_color="#00b8cc")
    _kpi(c2, icon="table_chart",   color="#a78bfa", glow="#a78bfa",
         label="Lotes XLSX",       value=f"{xlsx_count:,}",
         sub="Conversões SPED GOV",         sub_color="#8b5cf6")
    _kpi(c3, icon="folder_zip",    color="#34d399", glow="#34d399",
         label="Arquivo Fortes",   value=f"{fs_count:,}",
         sub="Notas exportadas (.fs)",       sub_color="#10b981")

    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)

    c4, c5, c6 = st.columns(3, gap="medium")
    _kpi(c4, icon="cloud_download", color="#f59e0b", glow="#f59e0b",
         label="XMLs via API",     value=f"{xml_api:,}",
         sub="Notas baixadas NFS-e Nacional", sub_color="#d97706")
    _kpi(c5, icon="picture_as_pdf",color="#fb923c", glow="#fb923c",
         label="PDFs via API",     value=f"{pdf_api:,}",
         sub="DANFSe baixados",              sub_color="#ea580c")
    _kpi(c6, icon="inventory_2",   color="#4ade80", glow="#4ade80",
         label="Arquivos Totais",
         value=f"{xmls_total:,}",
         sub="Soma de todos os arquivos",    sub_color="#22c55e")

    st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

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
<div style="display:flex;align-items:center;gap:8px;margin-bottom:2px;">
  <span class="ms" style="color:#00e5ff;font-size:16px;">bar_chart</span>
  <span style="color:#e2e8f0;font-size:.92rem;font-weight:700;font-family:Manrope,sans-serif;">Volume de Operações — últimos 14 dias</span>
</div>
""", unsafe_allow_html=True)
            df = pd.DataFrame({"Operações": contagem}, index=rotulos)
            st.area_chart(df, color="#00e5ff", height=210)

    with col_side:
        with st.container(border=True):
            st.markdown("""
<div style="color:#64748b;font-size:.65rem;font-weight:700;letter-spacing:.1em;
            text-transform:uppercase;margin-bottom:14px;font-family:Manrope,sans-serif;">Serviços</div>
""", unsafe_allow_html=True)
            _dot("API SPED", True)
            st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
            _dot("ISS Fortaleza", True)
            st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
            _dot("API NFS-e Nacional", True)

        st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown("""
<div style="color:#64748b;font-size:.65rem;font-weight:700;letter-spacing:.1em;
            text-transform:uppercase;margin-bottom:12px;font-family:Manrope,sans-serif;">Ações Rápidas</div>
""", unsafe_allow_html=True)
            if admin or has_permission("conversor"):
                if st.button("📄  Gerar Lote TXT", use_container_width=True, key="dash_txt"):
                    st.session_state.pagina = "conversor"
                    st.rerun()
            if admin or has_permission("baixar_xmls"):
                if st.button("☁️  Baixar XMLs/PDFs", use_container_width=True, key="dash_xml"):
                    st.session_state.pagina = "baixar_xmls"
                    st.rerun()
            if admin or has_permission("arquivo_fortes"):
                if st.button("🗂️  Arquivo Fortes", use_container_width=True, key="dash_fs"):
                    st.session_state.pagina = "arquivo_fortes"
                    st.rerun()
            if admin or has_permission("certificados"):
                if st.button("🔐  Certificados", use_container_width=True, key="dash_cert"):
                    st.session_state.pagina = "certificados"
                    st.rerun()

    st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

    # ── Tabela de atividade ───────────────────────────────────────────────
    recentes = get_conversions(limit=30, usuario=filtro)

    st.markdown("""
<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">
  <span class="ms" style="color:#64748b;font-size:18px;">history</span>
  <span style="color:#e2e8f0;font-size:.95rem;font-weight:700;font-family:Manrope,sans-serif;">Atividade Recente</span>
</div>
""", unsafe_allow_html=True)

    if not recentes:
        st.markdown("""
<div style="background:#0d1117;border:1px solid rgba(255,255,255,.05);border-radius:12px;
            padding:40px;text-align:center;color:#374151;font-family:Manrope,sans-serif;font-size:.85rem;">
  Nenhuma operação registrada ainda.
</div>""", unsafe_allow_html=True)
    else:
        rows = ""
        for conv in recentes:
            ok    = bool(conv.get("sucesso", True))
            modo  = (conv.get("modo") or "").upper()
            n_arq = conv.get("arquivos", 0)
            uname = conv.get("usuario", "?")
            try:
                ts_str = datetime.fromisoformat(conv["ts"]).strftime("%d/%m %H:%M")
            except Exception:
                ts_str = str(conv.get("ts", ""))[:16].replace("T", " ")

            emoji, dest, _ = _MODO_LABEL.get(modo, ("📁", modo or "—", "#94a3b8"))

            badge = (
                '<span style="background:rgba(74,222,128,.1);color:#4ade80;'
                'border:1px solid rgba(74,222,128,.2);border-radius:20px;padding:3px 12px;'
                'font-size:.66rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;">Concluído</span>'
                if ok else
                '<span style="background:rgba(248,113,113,.1);color:#f87171;'
                'border:1px solid rgba(248,113,113,.2);border-radius:20px;padding:3px 12px;'
                'font-size:.66rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;">Erro</span>'
            )

            col_u = (
                f'<td style="padding:10px 14px;color:#64748b;font-size:.77rem;'
                f'font-family:Manrope,sans-serif;">{uname}</td>'
            ) if admin else ""

            rows += f"""
<tr style="border-bottom:1px solid rgba(255,255,255,.03);">
  <td style="padding:10px 20px;">
    <div style="display:flex;align-items:center;gap:10px;">
      <div style="width:32px;height:32px;border-radius:8px;background:#151e2d;
                  border:1px solid rgba(255,255,255,.06);
                  display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0;">{emoji}</div>
      <div>
        <div style="color:#e2e8f0;font-size:.82rem;font-weight:600;font-family:Manrope,sans-serif;">
          {n_arq} arquivo{"s" if n_arq != 1 else ""}
        </div>
        <div style="color:#475569;font-size:.71rem;font-family:Manrope,sans-serif;">{modo}</div>
      </div>
    </div>
  </td>
  {col_u}
  <td style="padding:10px 14px;color:#64748b;font-size:.78rem;font-family:Manrope,sans-serif;">{dest}</td>
  <td style="padding:10px 14px;color:#64748b;font-size:.78rem;font-family:Manrope,sans-serif;">{ts_str}</td>
  <td style="padding:10px 20px;text-align:right;">{badge}</td>
</tr>"""

        th_u = (
            '<th style="padding:9px 14px;color:#475569;font-size:.63rem;font-weight:700;'
            'letter-spacing:.08em;text-transform:uppercase;text-align:left;'
            'font-family:Manrope,sans-serif;">Usuário</th>'
        ) if admin else ""

        st.markdown(f"""
<div style="background:#080d17;border:1px solid rgba(255,255,255,.05);border-radius:14px;overflow:hidden;">
<table style="width:100%;border-collapse:collapse;">
  <thead>
    <tr style="background:rgba(0,0,0,.4);">
      <th style="padding:9px 20px;color:#475569;font-size:.63rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;text-align:left;font-family:Manrope,sans-serif;">Arquivo</th>
      {th_u}
      <th style="padding:9px 14px;color:#475569;font-size:.63rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;text-align:left;font-family:Manrope,sans-serif;">Destino</th>
      <th style="padding:9px 14px;color:#475569;font-size:.63rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;text-align:left;font-family:Manrope,sans-serif;">Data</th>
      <th style="padding:9px 20px;color:#475569;font-size:.63rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;text-align:right;font-family:Manrope,sans-serif;">Status</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div style="text-align:center;color:#1e2d42;font-size:.68rem;padding:2rem 0 .5rem;font-family:Manrope,sans-serif;">
  © 2026 Fiscal Hub v2.0 &nbsp;&middot;&nbsp; Conversor NFS-e
</div>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _kpi(col, *, icon, color, glow, label, value, sub, sub_color):
    with col:
        st.markdown(f"""
<div style="background:#0d1220;border:1px solid rgba(255,255,255,.06);border-radius:14px;
            padding:20px 22px;position:relative;overflow:hidden;">
  <div style="position:absolute;top:-20px;right:-20px;width:80px;height:80px;border-radius:50%;
              background:radial-gradient(circle,{glow}18 0%,transparent 70%);"></div>
  <div style="display:flex;align-items:center;gap:7px;margin-bottom:10px;">
    <span class="ms" style="color:{color};font-size:17px;">{icon}</span>
    <span style="color:#64748b;font-size:.68rem;font-weight:700;letter-spacing:.09em;
                 text-transform:uppercase;font-family:Manrope,sans-serif;">{label}</span>
  </div>
  <div style="font-size:2rem;font-weight:800;color:#e2e8f0;font-family:Manrope,sans-serif;
              line-height:1;letter-spacing:-.02em;">{value}</div>
  <div style="color:{sub_color};font-size:.7rem;margin-top:8px;font-family:Manrope,sans-serif;">{sub}</div>
</div>""", unsafe_allow_html=True)


def _dot(nome, online: bool):
    cor   = "#22c55e" if online else "#ef4444"
    label = "Online"  if online else "Offline"
    st.markdown(f"""
<div style="display:flex;align-items:center;gap:10px;">
  <div style="width:8px;height:8px;border-radius:50%;background:{cor};
              box-shadow:0 0 6px {cor};flex-shrink:0;"></div>
  <div>
    <div style="color:#e2e8f0;font-size:.8rem;font-weight:600;font-family:Manrope,sans-serif;">{nome}</div>
    <div style="color:{cor};font-size:.66rem;font-family:Manrope,sans-serif;">{label}</div>
  </div>
</div>""", unsafe_allow_html=True)


