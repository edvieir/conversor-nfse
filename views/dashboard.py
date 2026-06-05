"""views/dashboard.py — Dashboard Fiscal Hub (layout modelo Stitch)"""

import streamlit as st
from datetime import datetime, timedelta
from auth.security import is_admin, has_permission
from db.database import get_stats, get_conversions
from views import nav


def render():
    nav.render("dashboard")

    s = get_stats()
    total      = s.get("total", 0)
    hoje       = s.get("hoje", 0)
    mes        = s.get("mes", 0)
    xmls       = s.get("xmls", 0)
    txt_count  = s.get("txt", 0)
    xlsx_count = s.get("xlsx", 0)

    # ── Page header ───────────────────────────────────────────────────────
    st.markdown("""
<div style="margin-bottom:1.5rem;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
    <span class="ms" style="color:#00e5ff;font-size:32px;">monitoring</span>
    <h1 style="color:#dce1fb;font-size:2rem;font-weight:800;letter-spacing:-.02em;margin:0;font-family:Manrope,sans-serif;">Visão Geral</h1>
  </div>
  <p style="color:#849396;font-size:.95rem;margin:0 0 0 42px;font-family:Manrope,sans-serif;">Monitore o desempenho e o status das suas conversões.</p>
</div>
""", unsafe_allow_html=True)

    # ── KPI cards ─────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3, gap="medium")

    with c1:
        st.markdown(f"""
<div style="background:#1E293B;border:1px solid rgba(255,255,255,.06);border-radius:14px;padding:24px;">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;">
    <span class="ms" style="color:#00e5ff;font-size:20px;">sync_alt</span>
    <span style="color:#849396;font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-family:Manrope,sans-serif;">Conversões Totais</span>
  </div>
  <div style="font-size:2.6rem;font-weight:800;color:#dce1fb;font-family:Manrope,sans-serif;line-height:1;">{total:,}</div>
  <div style="color:#10B981;font-size:.78rem;margin-top:8px;font-family:Manrope,sans-serif;">
    XMLs processados: {xmls:,}
  </div>
</div>""", unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
<div style="background:#1E293B;border:1px solid rgba(255,255,255,.06);border-radius:14px;padding:24px;">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;">
    <span class="ms" style="color:#99d9ff;font-size:20px;">today</span>
    <span style="color:#849396;font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-family:Manrope,sans-serif;">Processamento Hoje</span>
  </div>
  <div style="font-size:2.6rem;font-weight:800;color:#dce1fb;font-family:Manrope,sans-serif;line-height:1;">{hoje}</div>
  <div style="color:#849396;font-size:.78rem;margin-top:8px;font-family:Manrope,sans-serif;">Este mês: {mes}</div>
</div>""", unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
<div style="background:#1E293B;border:1px solid rgba(255,255,255,.06);border-radius:14px;padding:24px;">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;">
    <span class="ms" style="color:#bec6e0;font-size:20px;">schedule</span>
    <span style="color:#849396;font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-family:Manrope,sans-serif;">Formatos Gerados</span>
  </div>
  <div style="font-size:2.6rem;font-weight:800;color:#dce1fb;font-family:Manrope,sans-serif;line-height:1;">{txt_count + xlsx_count}</div>
  <div style="color:#849396;font-size:.78rem;margin-top:8px;font-family:Manrope,sans-serif;">TXT: {txt_count} &nbsp;&middot;&nbsp; XLSX: {xlsx_count}</div>
</div>""", unsafe_allow_html=True)

    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)

    # ── Gráfico + Status/Ações ────────────────────────────────────────────
    col_chart, col_side = st.columns([2, 1], gap="medium")

    with col_chart:
        import pandas as pd
        agora    = datetime.now()
        dias     = [(agora - timedelta(days=i)).date() for i in range(13, -1, -1)]
        por_dia  = s.get("por_dia", {})
        contagem = [por_dia.get(str(d), 0) for d in dias]
        rotulos  = [str(d)[5:] for d in dias]

        with st.container(border=True):
            st.markdown('<div style="color:#dce1fb;font-size:1rem;font-weight:700;margin-bottom:4px;font-family:Manrope,sans-serif;">Volume de Notas Processadas</div>', unsafe_allow_html=True)
            df = pd.DataFrame({"Conversões": contagem}, index=rotulos)
            st.area_chart(df, color="#00e5ff", height=200)

    with col_side:
        with st.container(border=True):
            st.markdown("""
<h4 style="color:#849396;font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
           margin:0 0 14px;font-family:Manrope,sans-serif;">Status do Sistema</h4>
<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
  <div style="width:10px;height:10px;border-radius:50%;background:#10B981;box-shadow:0 0 8px rgba(16,185,129,.6);flex-shrink:0;"></div>
  <div>
    <div style="color:#dce1fb;font-size:.85rem;font-weight:600;font-family:Manrope,sans-serif;">API SPED</div>
    <div style="color:#10B981;font-size:.72rem;font-family:Manrope,sans-serif;">Online</div>
  </div>
</div>
<div style="display:flex;align-items:center;gap:10px;">
  <div style="width:10px;height:10px;border-radius:50%;background:#10B981;box-shadow:0 0 8px rgba(16,185,129,.6);flex-shrink:0;"></div>
  <div>
    <div style="color:#dce1fb;font-size:.85rem;font-weight:600;font-family:Manrope,sans-serif;">ISS Fortaleza</div>
    <div style="color:#10B981;font-size:.72rem;font-family:Manrope,sans-serif;">Online</div>
  </div>
</div>
""", unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown('<h4 style="color:#849396;font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;margin:0 0 12px;font-family:Manrope,sans-serif;">Ações Rápidas</h4>', unsafe_allow_html=True)
            if is_admin() or has_permission("conversor"):
                if st.button("📄  Gerar Lote TXT", use_container_width=True, key="dash_txt"):
                    st.session_state.pagina = "conversor"
                    st.rerun()
            if is_admin() or has_permission("certificados"):
                if st.button("🔐  Atualizar Certificado", use_container_width=True, key="dash_cert"):
                    st.session_state.pagina = "certificados"
                    st.rerun()

    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)

    # ── Activity table ────────────────────────────────────────────────────
    recentes = get_conversions(limit=20)

    st.markdown("""
<div style="background:rgba(30,41,59,.4);border:1px solid rgba(255,255,255,.05);border-radius:14px;overflow:hidden;">
  <div style="padding:18px 24px;border-bottom:1px solid rgba(255,255,255,.05);">
    <h3 style="color:#dce1fb;font-size:1rem;font-weight:700;margin:0;font-family:Manrope,sans-serif;
               display:flex;align-items:center;gap:8px;">
      <span class="ms" style="color:#849396;font-size:20px;">history</span> Atividade Recente
    </h3>
  </div>
""", unsafe_allow_html=True)

    if not recentes:
        st.markdown("""
<div style="padding:32px 24px;text-align:center;color:#4a5568;font-family:Manrope,sans-serif;font-size:.88rem;">
  Nenhuma conversão registrada ainda. Use o conversor para ver o histórico aqui.
</div></div>""", unsafe_allow_html=True)
    else:
        rows = ""
        for c in recentes:
            ok      = c.get("sucesso", True)
            modo    = c.get("modo", "")
            n_arq   = c.get("arquivos", 0)
            usuario = c.get("usuario", "?")
            try:
                ts_str = datetime.fromisoformat(c["ts"]).strftime("%d/%m %H:%M")
            except Exception:
                ts_str = str(c.get("ts", ""))[:16].replace("T", " ")

            if ok:
                badge = '<span style="background:rgba(16,185,129,.1);color:#10B981;border:1px solid rgba(16,185,129,.2);border-radius:20px;padding:3px 10px;font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em;">Concluído</span>'
            else:
                badge = '<span style="background:rgba(244,63,94,.1);color:#f43f5e;border:1px solid rgba(244,63,94,.2);border-radius:20px;padding:3px 10px;font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em;">Erro</span>'

            dest = "ISS Fortaleza" if modo == "TXT" else "SPED GOV"
            rows += f"""
<tr style="border-bottom:1px solid rgba(255,255,255,.04);">
  <td style="padding:12px 24px;">
    <div style="display:flex;align-items:center;gap:10px;">
      <div style="width:30px;height:30px;border-radius:8px;background:#191f31;border:1px solid rgba(255,255,255,.06);
                  display:flex;align-items:center;justify-content:center;flex-shrink:0;">
        <span class="ms" style="color:#00e5ff;font-size:15px;">description</span>
      </div>
      <span style="color:#dce1fb;font-size:.83rem;font-weight:600;font-family:Manrope,sans-serif;">
        {usuario} — {n_arq} XML{"s" if n_arq != 1 else ""}
      </span>
    </div>
  </td>
  <td style="padding:12px 16px;color:#849396;font-size:.82rem;font-family:Manrope,sans-serif;">{dest}</td>
  <td style="padding:12px 16px;color:#849396;font-size:.82rem;font-family:Manrope,sans-serif;">{ts_str}</td>
  <td style="padding:12px 24px;text-align:right;">{badge}</td>
</tr>"""

        st.markdown(f"""
<table style="width:100%;border-collapse:collapse;">
  <thead>
    <tr style="background:rgba(7,13,31,.5);">
      <th style="padding:10px 24px;color:#849396;font-size:.68rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;text-align:left;font-family:Manrope,sans-serif;">Arquivo</th>
      <th style="padding:10px 16px;color:#849396;font-size:.68rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;text-align:left;font-family:Manrope,sans-serif;">Destino</th>
      <th style="padding:10px 16px;color:#849396;font-size:.68rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;text-align:left;font-family:Manrope,sans-serif;">Data</th>
      <th style="padding:10px 24px;color:#849396;font-size:.68rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;text-align:right;font-family:Manrope,sans-serif;">Status</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table></div>
""", unsafe_allow_html=True)

    st.markdown("""
<div style="text-align:center;color:#2f3e55;font-size:.72rem;padding:2rem 0 .5rem;font-family:Manrope,sans-serif;">
  © 2026 Conversor NFS-e v2.0 &nbsp;&middot;&nbsp; Advanced Fiscal Logic
</div>
""", unsafe_allow_html=True)
