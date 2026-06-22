"""views/nfe_nfce.py — Consulta NF-e e NFC-e via SEFAZ Nacional"""

import io
import zipfile as _zf
from datetime import datetime, date
import streamlit as st
import streamlit.components.v1 as _components

from auth.security import current_user
from assets.icons import icon
from db.database import (
    listar_certificados, carregar_certificado, log_conversion,
    get_nsu_cnpj, reset_nsu_cnpj, set_auto_sync, get_auto_sync,
    listar_resultados_nfe, contar_resultados_nfe, listar_xmls_resultados,
)
from views import nav


def _fmt_cnpj(cnpj: str) -> str:
    c = "".join(d for d in cnpj if d.isdigit())
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c) == 14 else cnpj


def _label(text: str) -> str:
    return (
        '<div style="color:#475569;font-size:.7rem;font-weight:600;'
        'letter-spacing:.4px;text-transform:uppercase;margin-bottom:3px;">'
        f'{text}</div>'
    )


def _segundos_restantes(proxima_consulta: str | None) -> int:
    if not proxima_consulta:
        return 0
    try:
        dt = datetime.fromisoformat(proxima_consulta)
        return max(0, int((dt - datetime.now()).total_seconds()))
    except Exception:
        return 0


def _countdown_html(segundos: int) -> str:
    return f"""
<div style="background:#1a1f2e;border:1px solid rgba(245,158,11,.3);border-radius:8px;
            padding:12px 16px;display:flex;align-items:center;gap:14px;margin:8px 0;">
  <span style="font-size:1.6rem;">⏳</span>
  <div>
    <div style="color:#94a3b8;font-size:.7rem;font-weight:600;text-transform:uppercase;
                letter-spacing:.5px;">Consulta bloqueada — aguarde</div>
    <div id="nfe_cd" style="color:#F59E0B;font-size:1.15rem;font-weight:700;
                             font-family:monospace;margin-top:2px;">calculando...</div>
    <div style="color:#475569;font-size:.7rem;margin-top:2px;">
      Limite SEFAZ: 1 consulta por hora por CNPJ · <i>NT 2014.002</i>
    </div>
  </div>
</div>
<script>
  let r = {segundos};
  function tick() {{
    if (r <= 0) {{
      document.getElementById('nfe_cd').textContent = '✓ Liberado! Recarregue a página.';
      document.getElementById('nfe_cd').style.color = '#10B981';
      return;
    }}
    const h = Math.floor(r/3600), m = Math.floor((r%3600)/60), s = r%60;
    document.getElementById('nfe_cd').textContent =
      (h ? h+'h ' : '') + m + 'min ' + String(s).padStart(2,'0') + 's';
    r--;
    setTimeout(tick, 1000);
  }}
  tick();
</script>
"""


def _render_tab_lote(user, certs):
    """Tab 1 — Consulta em Lote (distNSU)"""

    # ── Passo 1 — Empresa / Certificado ───────────────────────────────────────
    with st.container(border=True):
        ic = icon("shield", 16, "#00CED1")
        st.markdown(f"""
<div class="step-header">
  <div class="step-num">1</div>
  <div class="step-info"><div class="step-title">{ic}&nbsp; Empresa / Certificado</div></div>
</div>""", unsafe_allow_html=True)

        opcoes = {
            f"{c['razao_social'] or c['cnpj']}  —  {_fmt_cnpj(c['cnpj'])}": c
            for c in certs
        }
        escolha = st.selectbox("empresa", list(opcoes.keys()),
                               label_visibility="collapsed", key="nfe_sel_empresa")
        cert_sel         = opcoes[escolha]
        cnpj_principal   = "".join(d for d in cert_sel["cnpj"] if d.isdigit())
        nome_principal   = cert_sel["razao_social"] or cnpj_principal

        estado_nsu       = get_nsu_cnpj(cnpj_principal)
        nsu_salvo        = estado_nsu["ultimo_nsu"]
        ultima_consulta  = estado_nsu.get("atualizado_em") or "nunca"
        proxima_consulta = estado_nsu.get("proxima_consulta")
        nsu_zero         = nsu_salvo == "000000000000000"
        seg_rest         = _segundos_restantes(proxima_consulta)
        bloqueado        = seg_rest > 0

        col_info, col_reset = st.columns([4, 1], gap="small")
        with col_info:
            if not bloqueado:
                if nsu_zero:
                    ic_info = icon("info", 13, "#475569")
                    st.markdown(
                        f'<div style="color:#475569;font-size:.78rem;margin-top:4px;">'
                        f'{ic_info}&nbsp; Primeira consulta — buscará todos os documentos disponíveis.</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    ic_ok = icon("check-circle", 13, "#10B981")
                    st.markdown(
                        f'<div style="color:#10B981;font-size:.78rem;margin-top:4px;">'
                        f'{ic_ok}&nbsp; Continuando da última consulta em <b>{ultima_consulta}</b> '
                        f'(NSU {nsu_salvo}) — buscará apenas documentos <b>novos</b>.</div>',
                        unsafe_allow_html=True,
                    )
        with col_reset:
            if not nsu_zero:
                if st.button("Reiniciar do zero", key="nfe_reset_nsu",
                             use_container_width=True, type="secondary"):
                    reset_nsu_cnpj(cnpj_principal)
                    st.toast("NSU resetado — próxima consulta buscará tudo do início.", icon="🔄")
                    st.rerun()

        if bloqueado:
            _components.html(_countdown_html(seg_rest), height=100)

    # ── Passo 2 — Período ─────────────────────────────────────────────────────
    with st.container(border=True):
        ic = icon("calendar", 16, "#00CED1")
        st.markdown(f"""
<div class="step-header">
  <div class="step-num">2</div>
  <div class="step-info">
    <div class="step-title">{ic}&nbsp; Período de Consulta</div>
    <div class="step-desc">Filtra os documentos retornados pela SEFAZ pela data de emissão.</div>
  </div>
</div>""", unsafe_allow_html=True)

        hoje = date.today()
        col_ini, col_fim = st.columns(2, gap="medium")
        with col_ini:
            st.markdown(_label("Data Inicial"), unsafe_allow_html=True)
            data_ini = st.date_input("data_ini", value=hoje.replace(day=1),
                                     label_visibility="collapsed", key="nfe_data_ini")
        with col_fim:
            st.markdown(_label("Data Final"), unsafe_allow_html=True)
            data_fim = st.date_input("data_fim", value=hoje,
                                     label_visibility="collapsed", key="nfe_data_fim")

        if data_ini > data_fim:
            ic_e = icon("alert-triangle", 13, "#C97400")
            st.markdown(
                f'<div style="color:#C97400;font-size:.75rem;margin-top:4px;">'
                f'{ic_e}&nbsp; Data inicial deve ser anterior à data final.</div>',
                unsafe_allow_html=True,
            )

    # ── Passo 3 — O que baixar ────────────────────────────────────────────────
    with st.container(border=True):
        ic = icon("sliders", 16, "#00CED1")
        st.markdown(f"""
<div class="step-header">
  <div class="step-num">3</div>
  <div class="step-info"><div class="step-title">{ic}&nbsp; O que Consultar / Baixar</div></div>
</div>""", unsafe_allow_html=True)

        col_tipo, col_papel, col_saida = st.columns(3, gap="medium")

        with col_tipo:
            st.markdown(_label("Tipo de Documento"), unsafe_allow_html=True)
            tipo_opcoes = {
                "NF-e e NFC-e":  "ambos",
                "Somente NF-e":  "nfe",
                "Somente NFC-e": "nfce",
            }
            tipo_label = st.selectbox("tipo_doc", list(tipo_opcoes.keys()),
                                      label_visibility="collapsed", key="nfe_tipo")
            tipo_doc = tipo_opcoes[tipo_label]

        with col_papel:
            st.markdown(_label("Papel"), unsafe_allow_html=True)
            papel_opcoes = {
                "Emitidas e Recebidas": "ambos",
                "Somente Recebidas":    "recebidas",
                "Somente Emitidas":     "emitidas",
            }
            papel_label = st.selectbox("papel", list(papel_opcoes.keys()),
                                       label_visibility="collapsed", key="nfe_papel")
            papel_filtro = papel_opcoes[papel_label]

        with col_saida:
            st.markdown(_label("Conteúdo do Download"), unsafe_allow_html=True)
            saida_opcoes = {
                "XMLs + Relatório Excel":     "xml_excel",
                "XMLs + DANFE (PDF) + Excel": "xml_pdf_excel",
                "Somente XMLs":               "xml",
                "XMLs + DANFE (PDF)":         "xml_pdf",
                "Somente Relatório Excel":    "excel",
            }
            saida_label = st.selectbox("saida", list(saida_opcoes.keys()),
                                       label_visibility="collapsed", key="nfe_saida")
            saida_sel = saida_opcoes[saida_label]

    # ── Passo 4 — Executar ────────────────────────────────────────────────────
    with st.container(border=True):
        ic = icon("zap", 16, "#00CED1")

        desc_nsu = (
            "primeira consulta — buscará todos os documentos disponíveis"
            if nsu_zero else
            f"continuando do NSU {nsu_salvo} — somente documentos novos"
        )

        st.markdown(f"""
<div class="step-header">
  <div class="step-num">4</div>
  <div class="step-info">
    <div class="step-title">{ic}&nbsp; Consultar SEFAZ</div>
    <div class="step-desc">
      <b>{nome_principal}</b> ({_fmt_cnpj(cnpj_principal)}) ·
      {data_ini.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')} ·
      {tipo_label} · {papel_label} · {desc_nsu}
    </div>
  </div>
</div>""", unsafe_allow_html=True)

        if bloqueado:
            st.button(
                "⏳  Consulta bloqueada — aguarde a liberação",
                type="primary", use_container_width=True,
                disabled=True, key="nfe_btn_exec_disabled",
            )
        else:
            btn_executar = st.button(
                "Consultar SEFAZ agora",
                type="primary", use_container_width=True,
                disabled=(data_ini > data_fim),
                key="nfe_btn_exec",
            )

            if btn_executar:
                resultado = carregar_certificado(user["username"], cnpj_principal)
                if not resultado:
                    st.error("Certificado não encontrado. Recadastre em Certificados.")
                    return

                pfx_bytes, pfx_senha = resultado
                empresas_lista = [{"cnpj": cnpj_principal, "nome": nome_principal}]

                progress_bar = st.progress(0, text="Iniciando consulta na SEFAZ...")
                log_placeholder = st.empty()
                log_lines: list[str] = []

                def on_log(msg: str):
                    log_lines.append(msg)
                    log_placeholder.code("\n".join(log_lines[-30:]), language="")

                def on_progress(frac: float):
                    progress_bar.progress(min(frac, 1.0),
                                          text=f"Processando... {int(min(frac,1.0)*100)}%")

                try:
                    from core.nfe_sefaz import executar_consulta_sefaz

                    zip_bytes, log_final = executar_consulta_sefaz(
                        pfx_bytes=pfx_bytes,
                        pfx_senha=pfx_senha,
                        empresas=empresas_lista,
                        ambiente="1",
                        uf="CE",
                        data_ini=data_ini,
                        data_fim=data_fim,
                        tipo_doc=tipo_doc,
                        papel_filtro=papel_filtro,
                        incluir_xml=(saida_sel in ("xml", "xml_excel", "xml_pdf", "xml_pdf_excel")),
                        incluir_pdf=(saida_sel in ("xml_pdf", "xml_pdf_excel")),
                        incluir_excel=(saida_sel in ("excel", "xml_excel", "xml_pdf_excel")),
                        log_cb=on_log,
                        progress_cb=on_progress,
                    )

                    progress_bar.progress(1.0, text="Concluído!")
                    log_placeholder.empty()

                    with st.expander("Log de consulta", expanded=not bool(zip_bytes)):
                        st.code("\n".join(log_final), language="")

                    if zip_bytes:
                        with _zf.ZipFile(io.BytesIO(zip_bytes)) as _z:
                            nomes   = _z.namelist()
                            qt_xml  = len([n for n in nomes if n.endswith(".xml")])
                            qt_pdf  = len([n for n in nomes if n.endswith(".pdf")])
                            qt_xlsx = len([n for n in nomes if n.endswith(".xlsx")])

                        log_conversion(user["username"], "NFE_NFCE", qt_xml or qt_xlsx, True)

                        ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
                        nome_zip = (
                            f"nfe_nfce_{cnpj_principal[:8]}_"
                            f"{data_ini.strftime('%Y%m%d')}_{data_fim.strftime('%Y%m%d')}_{ts}.zip"
                        )

                        ic_ok  = icon("check-circle", 32, "#1AB87A")
                        partes = []
                        if qt_xml:  partes.append(f"{qt_xml} XML(s)")
                        if qt_pdf:  partes.append(f"{qt_pdf} DANFE(s) PDF")
                        if qt_xlsx: partes.append(f"{qt_xlsx} relatório Excel")
                        st.markdown(f"""
<div class="result-success">
  <div class="result-success-icon">{ic_ok}</div>
  <div>
    <div class="result-success-title">Consulta concluída com sucesso!</div>
    <div class="result-success-meta">
      {' &nbsp;·&nbsp; '.join(partes)} &nbsp;·&nbsp; {round(len(zip_bytes)/1024, 1)} KB
    </div>
  </div>
</div>""", unsafe_allow_html=True)

                        st.download_button(
                            label=f"⬇  Baixar  {nome_zip}",
                            data=zip_bytes,
                            file_name=nome_zip,
                            mime="application/zip",
                            use_container_width=True,
                        )
                    else:
                        ic_warn = icon("alert-triangle", 15, "#C77D0A")
                        st.markdown(
                            f'<div class="warn-box">{ic_warn}'
                            f'<span class="box-text">Nenhum documento novo encontrado no período '
                            f'{data_ini.strftime("%d/%m/%Y")} a {data_fim.strftime("%d/%m/%Y")}.'
                            f'</span></div>',
                            unsafe_allow_html=True,
                        )

                    st.rerun()

                except Exception as exc:
                    progress_bar.empty()
                    log_placeholder.empty()
                    log_conversion(user["username"], "NFE_NFCE", 0, False)
                    ic_err = icon("x-circle", 15, "#D93025")
                    st.markdown(
                        f'<div class="error-box">{ic_err}'
                        f'<span class="box-text">Erro: {exc}</span></div>',
                        unsafe_allow_html=True,
                    )


def _render_tab_chave(user, certs):
    """Tab 2 — Consulta por Chave de Acesso (consChNFe) · limite separado 20/hora"""

    st.markdown("""
<div style="background:#0f172a;border:1px solid rgba(0,229,255,.1);border-radius:8px;
            padding:12px 16px;margin-bottom:16px;">
  <div style="color:#94a3b8;font-size:.8rem;line-height:1.6;">
    📌 <b>Consulta independente</b> — usa o endpoint <code>consChNFe</code> da SEFAZ,
    com contador <b>separado</b> do limite de 1 hora do distNSU.
    Permite até <b>20 consultas por hora</b> por CNPJ. Ideal para buscar uma
    NF-e específica sem comprometer a janela de sincronização em lote.
  </div>
</div>
""", unsafe_allow_html=True)

    with st.container(border=True):
        ic = icon("shield", 16, "#00CED1")
        st.markdown(f"""
<div class="step-header">
  <div class="step-num">1</div>
  <div class="step-info"><div class="step-title">{ic}&nbsp; Empresa / Certificado</div></div>
</div>""", unsafe_allow_html=True)

        opcoes = {
            f"{c['razao_social'] or c['cnpj']}  —  {_fmt_cnpj(c['cnpj'])}": c
            for c in certs
        }
        escolha  = st.selectbox("empresa_chave", list(opcoes.keys()),
                                label_visibility="collapsed", key="nfe_ch_empresa")
        cert_sel = opcoes[escolha]
        cnpj_ch  = "".join(d for d in cert_sel["cnpj"] if d.isdigit())

    with st.container(border=True):
        ic = icon("hash", 16, "#00CED1")
        st.markdown(f"""
<div class="step-header">
  <div class="step-num">2</div>
  <div class="step-info">
    <div class="step-title">{ic}&nbsp; Chave de Acesso</div>
    <div class="step-desc">44 dígitos numéricos da NF-e ou NFC-e.</div>
  </div>
</div>""", unsafe_allow_html=True)

        chave_input  = st.text_input(
            "chave_acesso", label_visibility="collapsed",
            placeholder="Ex: 23240612345678000100550010000001231234567890",
            max_chars=44, key="nfe_ch_chave",
        )
        chave_digits = "".join(c for c in (chave_input or "") if c.isdigit())
        qtd = len(chave_digits)
        cor = "#10B981" if qtd == 44 else ("#F59E0B" if qtd > 0 else "#475569")
        st.markdown(
            f'<div style="color:{cor};font-size:.72rem;margin-top:2px;">'
            f'{qtd}/44 dígitos</div>',
            unsafe_allow_html=True,
        )

    btn_ch = st.button(
        "Consultar Chave",
        type="primary", use_container_width=True,
        disabled=(qtd != 44),
        key="nfe_btn_chave",
    )

    if btn_ch:
        dados = None
        erro  = ""
        fonte = ""

        # ── 1. Verifica primeiro no banco local (notas já sincronizadas) ──────
        from db.database import carregar_xml_resultado
        from core.nfe_sefaz import _extrair_dados
        xml_local = carregar_xml_resultado(cnpj_ch, chave_digits)
        if xml_local:
            dados = _extrair_dados(xml_local, cnpj_ch)
            dados["xml"] = xml_local
            fonte = "local"
        else:
            # ── 2. Tenta na SEFAZ ─────────────────────────────────────────────
            resultado_cert = carregar_certificado(user["username"], cnpj_ch)
            if not resultado_cert:
                st.error("Certificado não encontrado.")
                return
            pfx_bytes, pfx_senha = resultado_cert
            with st.spinner("Consultando SEFAZ..."):
                from core.nfe_sefaz import consultar_chave_avulsa
                dados, erro = consultar_chave_avulsa(pfx_bytes, pfx_senha, cnpj_ch, chave_digits)
            if dados:
                fonte = "sefaz"

        if erro:
            partes = erro.split("\n\n", 1)
            titulo = partes[0]
            detalhe = partes[1].replace("\n", "<br>") if len(partes) > 1 else ""
            ic_err = icon("x-circle", 15, "#D93025")
            st.markdown(
                f'<div class="error-box" style="flex-direction:column;align-items:flex-start;gap:6px;">'
                f'<div style="display:flex;align-items:center;gap:8px;">{ic_err}'
                f'<span class="box-text"><b>{titulo}</b></span></div>'
                + (f'<div style="color:#94a3b8;font-size:.8rem;padding-left:23px;line-height:1.7;">{detalhe}</div>' if detalhe else "")
                + '</div>',
                unsafe_allow_html=True,
            )
            return

        modelo = dados.get("modelo", "NF-e")
        papel  = dados.get("papel", "?")
        ic_ok  = icon("check-circle", 15, "#10B981")
        fonte_label = "📦 acervo local" if fonte == "local" else "🌐 SEFAZ"
        st.markdown(f"""
<div style="background:#0a2a1a;border:1px solid rgba(16,185,129,.3);border-radius:8px;
            padding:14px 18px;margin:12px 0;">
  <div style="color:#10B981;font-weight:700;font-size:.95rem;margin-bottom:10px;">
    {ic_ok}&nbsp; {modelo} encontrada — {papel}
    <span style="font-size:.72rem;font-weight:400;color:#475569;margin-left:8px;">
      via {fonte_label}
    </span>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;">
    <div><div style="color:#475569;font-size:.68rem;text-transform:uppercase;letter-spacing:.4px;">Número / Série</div>
         <div style="color:#e2e8f0;font-weight:600;">{dados.get('numero','?')} / {dados.get('serie','?')}</div></div>
    <div><div style="color:#475569;font-size:.68rem;text-transform:uppercase;letter-spacing:.4px;">Data Emissão</div>
         <div style="color:#e2e8f0;font-weight:600;">{dados.get('data_emissao','?')}</div></div>
    <div><div style="color:#475569;font-size:.68rem;text-transform:uppercase;letter-spacing:.4px;">Valor Total</div>
         <div style="color:#e2e8f0;font-weight:600;">R$ {dados.get('valor_total',0):,.2f}</div></div>
    <div><div style="color:#475569;font-size:.68rem;text-transform:uppercase;letter-spacing:.4px;">Emitente</div>
         <div style="color:#e2e8f0;font-weight:600;">{dados.get('nome_emitente','?')}</div></div>
    <div><div style="color:#475569;font-size:.68rem;text-transform:uppercase;letter-spacing:.4px;">Destinatário</div>
         <div style="color:#e2e8f0;font-weight:600;">{dados.get('nome_dest_doc','?')}</div></div>
    <div><div style="color:#475569;font-size:.68rem;text-transform:uppercase;letter-spacing:.4px;">Natureza</div>
         <div style="color:#e2e8f0;font-weight:600;">{dados.get('nat_operacao','?')}</div></div>
  </div>
</div>
""", unsafe_allow_html=True)

        xml_bytes = dados["xml"].encode("utf-8")
        col_xml, col_pdf = st.columns(2)
        with col_xml:
            st.download_button(
                label="⬇  Baixar XML",
                data=xml_bytes,
                file_name=f"{chave_digits}.xml",
                mime="application/xml",
                use_container_width=True,
            )
        with col_pdf:
            try:
                from brazilfiscalreport.danfe import Danfe
                buf_pdf = io.BytesIO()
                Danfe(xml=xml_bytes).output(buf_pdf)
                st.download_button(
                    label="⬇  Baixar DANFE (PDF)",
                    data=buf_pdf.getvalue(),
                    file_name=f"{chave_digits}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except Exception as e_pdf:
                st.caption(f"DANFE não disponível: {e_pdf}")

        log_conversion(user["username"], "NFE_NFCE", 1, True)


def _render_tab_auto(user, certs):
    """Tab 3 — Sincronização Automática + acervo acumulado"""

    st.markdown("""
<div style="background:#0f172a;border:1px solid rgba(0,229,255,.1);border-radius:8px;
            padding:12px 16px;margin-bottom:16px;">
  <div style="color:#94a3b8;font-size:.8rem;line-height:1.6;">
    ⚙️ <b>Como funciona:</b> o servidor executa automaticamente uma consulta na SEFAZ
    a cada hora para os CNPJs com sincronização ativada. Os XMLs baixados ficam
    acumulados aqui e podem ser baixados a qualquer momento como ZIP —
    sem precisar esperar nem correr risco de cStat=656.
  </div>
</div>
""", unsafe_allow_html=True)

    for cert in certs:
        cnpj_c = "".join(d for d in cert["cnpj"] if d.isdigit())
        nome_c = cert.get("razao_social") or cnpj_c
        ativo  = get_auto_sync(cnpj_c, user["username"])
        total  = contar_resultados_nfe(cnpj_c)

        with st.container(border=True):
            col_head, col_toggle = st.columns([5, 1], gap="small")

            with col_head:
                estado_nsu   = get_nsu_cnpj(cnpj_c)
                proxima_c    = estado_nsu.get("proxima_consulta")
                ultima_c     = estado_nsu.get("atualizado_em") or "nunca consultado"
                seg_rest_c   = _segundos_restantes(proxima_c)
                status_cor   = "#10B981" if ativo else "#475569"
                status_txt   = "ATIVO" if ativo else "INATIVO"
                ic_s         = icon("check-circle" if ativo else "circle", 13, status_cor)
                prox_txt     = (
                    f" · Próxima em: {seg_rest_c//60}min {seg_rest_c%60:02d}s"
                    if seg_rest_c > 0 else ""
                )

                st.markdown(f"""
<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
  <span style="color:#e2e8f0;font-weight:700;font-size:.95rem;">{nome_c}</span>
  <span style="color:#475569;font-size:.8rem;">{_fmt_cnpj(cnpj_c)}</span>
  <span style="background:rgba({'16,185,129' if ativo else '71,85,105'},.15);
               color:{status_cor};font-size:.65rem;font-weight:700;
               padding:2px 7px;border-radius:4px;letter-spacing:.5px;">
    {ic_s}&nbsp;{status_txt}
  </span>
</div>
<div style="color:#475569;font-size:.75rem;">
  {total} documento(s) acumulado(s) · Última sincronização: {ultima_c}{prox_txt}
</div>
""", unsafe_allow_html=True)

            with col_toggle:
                novo_estado = st.toggle(
                    "sync", value=ativo,
                    key=f"nfe_sync_{cnpj_c}",
                    label_visibility="collapsed",
                )
                if novo_estado != ativo:
                    set_auto_sync(cnpj_c, user["username"], novo_estado)
                    st.rerun()

            if total > 0:
                col_dl, col_prev = st.columns([2, 3], gap="small")

                with col_dl:
                    if st.button(
                        f"⬇  Baixar acervo ({total} docs)",
                        key=f"nfe_dl_{cnpj_c}",
                        use_container_width=True,
                    ):
                        with st.spinner("Gerando ZIP..."):
                            xmls = listar_xmls_resultados(cnpj_c)
                            buf  = io.BytesIO()
                            with _zf.ZipFile(buf, "w", _zf.ZIP_DEFLATED) as zf:
                                for row in xmls:
                                    pasta = f"{row.get('modelo','NF-e')}_{row.get('papel','?')}"
                                    zf.writestr(
                                        f"XMLs/{pasta}/{row['chave']}.xml",
                                        row["xml_conteudo"],
                                    )
                            ts_dl   = datetime.now().strftime("%Y%m%d_%H%M%S")
                            nome_dl = f"acervo_nfe_{cnpj_c[:8]}_{ts_dl}.zip"

                        st.download_button(
                            label=f"⬇  {nome_dl}",
                            data=buf.getvalue(),
                            file_name=nome_dl,
                            mime="application/zip",
                            use_container_width=True,
                            key=f"nfe_dl_btn_{cnpj_c}",
                        )

                with col_prev:
                    ultimos = listar_resultados_nfe(cnpj_c, limit=5)
                    if ultimos:
                        rows_html = "".join(
                            f'<tr>'
                            f'<td style="color:#e2e8f0;padding:2px 4px">{r.get("data_emissao","?")}</td>'
                            f'<td style="color:#94a3b8;padding:2px 4px">{r.get("modelo","?")}</td>'
                            f'<td style="color:{"#10B981" if r.get("papel")=="Recebida" else "#60a5fa"};padding:2px 4px">'
                            f'{r.get("papel","?")}</td>'
                            f'<td style="color:#e2e8f0;font-family:monospace;font-size:.7rem;padding:2px 4px">'
                            f'{r.get("chave","")[:20]}...</td>'
                            f'</tr>'
                            for r in ultimos
                        )
                        st.markdown(f"""
<table style="width:100%;border-collapse:collapse;font-size:.75rem;margin-top:4px;">
  <thead><tr>
    <th style="color:#475569;text-align:left;padding:2px 4px">Data</th>
    <th style="color:#475569;text-align:left;padding:2px 4px">Modelo</th>
    <th style="color:#475569;text-align:left;padding:2px 4px">Papel</th>
    <th style="color:#475569;text-align:left;padding:2px 4px">Chave</th>
  </tr></thead>
  <tbody>{rows_html}</tbody>
</table>""", unsafe_allow_html=True)

    st.markdown("""
<div style="background:#0f172a;border:1px solid rgba(99,102,241,.2);border-radius:8px;
            padding:10px 14px;margin-top:16px;">
  <div style="color:#818cf8;font-size:.75rem;font-weight:600;">⚙️ Agendamento no Servidor</div>
  <div style="color:#475569;font-size:.72rem;margin-top:4px;line-height:1.6;">
    O scheduler roda automaticamente via cron a cada hora.
    Log disponível em <code>/var/log/nfe_scheduler.log</code>.
  </div>
</div>
""", unsafe_allow_html=True)


def render():
    nav.render("nfe_nfce")
    user = current_user()

    ic_head = icon("receipt", 20, "#00e5ff")
    st.markdown(f"""
<div style="display:flex;align-items:center;gap:10px;padding:4px 0 18px;">
  <div style="width:40px;height:40px;border-radius:10px;background:#111827;
              border:1px solid rgba(0,229,255,.15);display:flex;align-items:center;justify-content:center;">
    {ic_head}
  </div>
  <div>
    <div style="color:#e2e8f0;font-weight:800;font-size:1.15rem;font-family:Manrope,sans-serif;line-height:1.1;">
      NFE / NFCE
    </div>
    <div style="color:#475569;font-size:.75rem;font-family:Manrope,sans-serif;">
      Consulta automática na SEFAZ Nacional · NF-e e NFC-e emitidas e recebidas
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    certs = listar_certificados(user["username"])
    if not certs:
        with st.container(border=True):
            ic_warn = icon("alert-triangle", 16, "#C97400")
            st.markdown(f"""
<div style="text-align:center;padding:2rem 1rem;">
  <div style="font-size:1rem;font-weight:700;color:#C97400;margin-bottom:.5rem;">
    {ic_warn}&nbsp; Nenhum certificado cadastrado
  </div>
  <div style="color:#475569;font-size:.85rem;">
    Acesse <b>Certificados</b> no menu para adicionar seu certificado digital A1 (.pfx).
  </div>
</div>
""", unsafe_allow_html=True)
            if st.button("Ir para Certificados", use_container_width=True, type="primary"):
                st.session_state.pagina = "certificados"
                st.rerun()
        return

    tab_lote, tab_chave, tab_auto = st.tabs([
        "📦  Consulta em Lote",
        "🔍  Por Chave de Acesso",
        "⚙️  Sincronização Automática",
    ])

    with tab_lote:
        _render_tab_lote(user, certs)

    with tab_chave:
        _render_tab_chave(user, certs)

    with tab_auto:
        _render_tab_auto(user, certs)

    st.markdown("""
<div class="footer">
  Fiscal Hub &nbsp;v2.0 &nbsp;·&nbsp; NFE / NFCE Nacional
  &nbsp;·&nbsp; WebService NFeDistribuicaoDFe · SEFAZ Nacional
</div>
""", unsafe_allow_html=True)
