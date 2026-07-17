"""views/siga_downloads.py — Relatórios do SIGA (SEFAZ-CE): NF-e, NFC-e e índices de malha.

Modelo híbrido: o cron (core/siga_scheduler.py) gera os arquivos de madrugada
em data/siga_downloads/<cnpj>/. Esta tela lista o que já está em cache (rápido,
funciona mesmo com o SIGA fora do ar) e oferece "Atualizar agora" por aba para
buscar ao vivo quando necessário.
"""
import calendar
import datetime
import io
import zipfile
from pathlib import Path

import streamlit as st

from auth.security import current_user
from assets.icons import icon
from db.database import (
    listar_certificados, carregar_certificado,
    enfileirar_xml, status_fila_xml,
    listar_xmls_por_periodo, listar_resultados_por_periodo,
)
from views import nav
from core.siga_scheduler import ABAS as _ABAS_DOCUMENTOS, SAIDA_DIR

XML_DIR = Path(__file__).parent.parent / "data" / "siga_xml"

_LABELS = {
    "NF_E_emitidas":               "NF-e Emitidas",
    "NF_E_recebidas":              "NF-e Recebidas",
    "NF_E_canceladas":             "NF-e Canceladas",
    "NFC_E_emitidas":              "NFC-e Emitidas",
    "INDICADORES_MALHA_pendencias":"Índices de Malha (pendências / não escrituradas)",
}


def _fmt_cnpj(c: str) -> str:
    c = (c or "").strip().zfill(14)
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"


def _mes_corrente() -> str:
    return datetime.date.today().strftime("%Y-%m")


def _listar_abas() -> list[tuple[str, str, str, dict]]:
    """Retorna (nome_arquivo, tipo_ou_None, nome_aba_ou_None, filtros_ou_None)."""
    abas = []
    for tipo, itens in _ABAS_DOCUMENTOS.items():
        for nome_aba, filtros in itens:
            abas.append((f"{tipo}_{nome_aba}", tipo, nome_aba, filtros))
    abas.append(("INDICADORES_MALHA_pendencias", None, None, None))
    return abas


def _caminho_cache(cnpj: str, nome_arquivo: str, periodo: str) -> Path:
    return SAIDA_DIR / cnpj / f"{nome_arquivo}_{periodo}.xlsx"


def _gerar_ao_vivo(usuario: str, cnpj: str, nome_arquivo: str, tipo, nome_aba, filtros, periodo: str) -> bytes | None:
    """Busca ao vivo no SIGA. Retorna None se não houver dado (ex.: sem pendências)."""
    from core import siga_sefaz

    cert = carregar_certificado(usuario, cnpj)
    if not cert:
        raise RuntimeError("Certificado não encontrado para esta empresa.")
    pfx_bytes, senha = cert
    sessao = siga_sefaz._sessao(pfx_bytes, senha)
    token = siga_sefaz.login(sessao)["access_token"]

    if tipo is None:  # índices de malha
        indicadores = siga_sefaz.listar_indicadores_malha(sessao, token, cnpj)
        if not indicadores:
            return None
        sid = siga_sefaz.solicitar_download_indicadores(sessao, token, cnpj)
    else:
        sid = siga_sefaz.solicitar_download(
            sessao, token, cnpj, tipo, dat_referencia=[periodo], **filtros,
        )

    return siga_sefaz.aguardar_e_baixar(sessao, token, sid)


def _segundos_restantes(proxima_consulta: str | None) -> int:
    if not proxima_consulta:
        return 0
    try:
        dt = datetime.datetime.fromisoformat(proxima_consulta)
        return max(0, int((dt - datetime.datetime.now()).total_seconds()))
    except Exception:
        return 0


def _secao_baixar_tudo(user: dict, cnpj: str, razao_social: str):
    """Baixa o XML completo (NF-e + NFC-e, emitidas e recebidas) via distribuição
    NSU da SEFAZ Nacional -- mesmo motor da página NFE/NFCE, sem o limite de
    20/hora (esse aqui é 1 consulta/hora por CNPJ, controlado por NSU)."""
    from db.database import get_nsu_cnpj

    with st.container(border=True):
        st.markdown("**Baixar tudo (XML completo via SEFAZ Nacional)**")
        st.caption(
            "NF-e e NFC-e, emitidas e recebidas, direto em XML (não resumo). "
            "Limite da SEFAZ: 1 consulta por hora por CNPJ."
        )

        estado_nsu = get_nsu_cnpj(cnpj)
        seg_rest = _segundos_restantes(estado_nsu.get("proxima_consulta"))

        if seg_rest > 0:
            minutos = seg_rest // 60
            st.warning(f"Bloqueado pela SEFAZ — tente novamente em ~{minutos} min.")
            return

        col_ini, col_fim, col_btn = st.columns([1, 1, 1])
        with col_ini:
            data_ini = st.date_input("De", value=datetime.date.today().replace(day=1), key="siga_dl_tudo_ini")
        with col_fim:
            data_fim = st.date_input("Até", value=datetime.date.today(), key="siga_dl_tudo_fim")
        with col_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            disparar = st.button("Baixar tudo", type="primary", use_container_width=True, key="siga_dl_tudo_btn")

        if disparar:
            cert = carregar_certificado(user["username"], cnpj)
            if not cert:
                st.error("Certificado não encontrado para esta empresa.")
                return
            pfx_bytes, pfx_senha = cert

            progress_bar = st.progress(0, text="Conectando na SEFAZ Nacional...")
            log_placeholder = st.empty()

            def on_progress(frac: float):
                progress_bar.progress(min(frac, 1.0), text=f"Processando... {int(min(frac,1.0)*100)}%")

            def on_log(linhas: list):
                log_placeholder.code("\n".join(linhas[-30:]), language="")

            try:
                from core.nfe_sefaz import executar_consulta_sefaz

                zip_bytes, log_final = executar_consulta_sefaz(
                    pfx_bytes=pfx_bytes,
                    pfx_senha=pfx_senha,
                    empresas=[{"cnpj": cnpj, "nome": razao_social}],
                    ambiente="1",
                    uf="CE",
                    data_ini=data_ini,
                    data_fim=data_fim,
                    tipo_doc="ambos",
                    papel_filtro="ambos",
                    incluir_xml=True,
                    incluir_pdf=False,
                    incluir_excel=False,
                    log_cb=on_log,
                    progress_cb=on_progress,
                    salvar_db=True,
                )
                progress_bar.progress(1.0, text="Concluído!")
                log_placeholder.empty()

                with st.expander("Log da consulta", expanded=not bool(zip_bytes)):
                    st.code("\n".join(log_final), language="")

                if zip_bytes:
                    st.success(f"{len(zip_bytes) // 1024} KB de XML baixados.")
                    st.download_button(
                        "Baixar ZIP com os XMLs",
                        data=zip_bytes,
                        file_name=f"xml_completo_{cnpj}_{data_ini}_{data_fim}.zip",
                        mime="application/zip",
                        use_container_width=True,
                    )
                else:
                    st.info("Nenhum documento novo encontrado no período (ou já sincronizado antes).")
            except Exception as e:
                progress_bar.empty()
                log_placeholder.empty()
                st.error(f"Erro: {e}")


def _periodo_para_datas(periodo: str) -> tuple[str, str] | None:
    try:
        ano, mes = periodo.split("-")
        ano, mes = int(ano), int(mes)
        ultimo_dia = calendar.monthrange(ano, mes)[1]
        return f"{ano}-{mes:02d}-01", f"{ano}-{mes:02d}-{ultimo_dia}"
    except Exception:
        return None


def _secao_acervo_local(cnpj: str, razao_social: str, periodo: str):
    """XML e planilha do que já está sincronizado no acervo local -- sem
    chamar SEFAZ nem SIGA de novo, então sem limite de consulta."""
    datas = _periodo_para_datas(periodo)
    if not datas:
        return
    data_ini_str, data_fim_str = datas

    with st.container(border=True):
        st.markdown("**Acervo local já sincronizado**")
        st.caption(
            "XML e planilha do que já está salvo no banco para o período — "
            "não chama SEFAZ nem SIGA de novo, sem limite de consulta."
        )

        col_xml, col_xlsx = st.columns(2)

        with col_xml:
            xmls = listar_xmls_por_periodo(cnpj, data_ini_str, data_fim_str)
            st.metric("Documentos no acervo", len(xmls))
            if xmls:
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    for r in xmls:
                        pasta = f"{r.get('modelo','NF-e')}_{r.get('papel','?')}"
                        chave = r.get("chave", "x")
                        xml = r.get("xml_conteudo", "")
                        if xml:
                            zf.writestr(f"XMLs/{pasta}/{chave}.xml", xml)
                st.download_button(
                    "Baixar XMLs do acervo (.zip)",
                    data=buf.getvalue(),
                    file_name=f"acervo_xml_{cnpj}_{periodo}.zip",
                    mime="application/zip",
                    use_container_width=True,
                    key="siga_acervo_xml_dl",
                )

        with col_xlsx:
            rec  = listar_resultados_por_periodo(cnpj, data_ini_str, data_fim_str, modelo="55", papel="Recebida")
            emit = listar_resultados_por_periodo(cnpj, data_ini_str, data_fim_str, modelo="55", papel="Emitida")
            nfce = listar_resultados_por_periodo(cnpj, data_ini_str, data_fim_str, modelo="65")
            total = len(rec) + len(emit) + len(nfce)
            st.metric("Notas para planilha DTE", total)
            if total:
                from views.siga_consulta import _gerar_excel
                xlsx_bytes = _gerar_excel(rec, emit, nfce, cnpj, razao_social, periodo)
                st.download_button(
                    "Baixar planilha Excel (DTE)",
                    data=xlsx_bytes,
                    file_name=f"DTE_{cnpj}_{periodo}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="siga_acervo_xlsx_dl",
                )


def render():
    user = current_user()
    nav.render("siga_downloads")

    st.markdown("## Relatórios SIGA — SEFAZ-CE")
    st.caption(
        "NF-e, NFC-e e índices de malha fiscal direto do SIGA. "
        "Os arquivos são atualizados automaticamente todo dia; use **Atualizar agora** "
        "numa aba específica se precisar de algo mais recente."
    )

    certs = listar_certificados(user["username"])
    if not certs:
        st.warning(
            "Nenhum certificado digital cadastrado. "
            "Acesse a página **Certificados** para adicionar."
        )
        return

    opcoes = {
        f"{c['razao_social']} ({_fmt_cnpj(c['cnpj'])})": c["cnpj"]
        for c in certs
    }

    c1, c2 = st.columns([3, 1])
    with c1:
        empresa_label = st.selectbox("Empresa", list(opcoes.keys()), key="siga_dl_empresa")
    with c2:
        periodo = st.text_input(
            "Período (AAAA-MM)", value=_mes_corrente(), key="siga_dl_periodo",
            help="Só afeta NF-e/NFC-e. Índices de malha são sempre a situação atual.",
        )

    cnpj_sel = opcoes[empresa_label]
    razao_sel = next(c["razao_social"] for c in certs if c["cnpj"] == cnpj_sel)

    st.markdown("---")

    _secao_baixar_tudo(user, cnpj_sel, razao_sel)

    st.markdown("---")

    _secao_acervo_local(cnpj_sel, razao_sel, periodo)

    st.markdown("---")

    from core.siga_sefaz import extrair_chaves_xlsx

    for nome_arquivo, tipo, nome_aba, filtros in _listar_abas():
        label = _LABELS.get(nome_arquivo, nome_arquivo)
        caminho = _caminho_cache(cnpj_sel, nome_arquivo, periodo)

        with st.container(border=True):
            col_info, col_baixar, col_fila, col_atualizar = st.columns([3, 1, 1, 1])

            with col_info:
                if caminho.exists():
                    mtime = datetime.datetime.fromtimestamp(caminho.stat().st_mtime)
                    tamanho = caminho.stat().st_size
                    tamanho_fmt = f"{tamanho} bytes" if tamanho < 1024 else f"{tamanho / 1024:.1f} KB"
                    ic = icon("check-circle", 16, "#10B981")
                    st.markdown(
                        f"**{label}**<br>"
                        f'<span style="color:#64748B;font-size:.8rem;">{ic} '
                        f'Atualizado em {mtime.strftime("%d/%m/%Y %H:%M")} '
                        f'({tamanho_fmt})</span>',
                        unsafe_allow_html=True,
                    )
                else:
                    ic = icon("alert-triangle", 16, "#C97400")
                    st.markdown(
                        f"**{label}**<br>"
                        f'<span style="color:#C97400;font-size:.8rem;">{ic} '
                        f'Ainda não gerado para este período.</span>',
                        unsafe_allow_html=True,
                    )

            with col_baixar:
                if caminho.exists():
                    st.download_button(
                        "Baixar",
                        data=caminho.read_bytes(),
                        file_name=caminho.name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key=f"dl_{nome_arquivo}",
                    )

            with col_fila:
                if caminho.exists():
                    if st.button("Enfileirar XML", key=f"fila_{nome_arquivo}", use_container_width=True):
                        chaves = extrair_chaves_xlsx(caminho.read_bytes())
                        qtd = enfileirar_xml(user["username"], cnpj_sel, chaves)
                        st.success(f"{qtd} chave(s) enfileirada(s) ({len(chaves)} encontradas em {label}).")
                        st.rerun()

            with col_atualizar:
                if st.button("Atualizar agora", key=f"upd_{nome_arquivo}", use_container_width=True):
                    with st.spinner(f"Buscando {label} no SIGA..."):
                        try:
                            conteudo = _gerar_ao_vivo(
                                user["username"], cnpj_sel, nome_arquivo, tipo, nome_aba, filtros, periodo,
                            )
                        except Exception as e:
                            st.error(f"Erro: {e}")
                        else:
                            if conteudo is None:
                                st.info("Sem dados para esta aba (ex.: sem pendências de malha).")
                                caminho.unlink(missing_ok=True)
                            else:
                                caminho.parent.mkdir(parents=True, exist_ok=True)
                                caminho.write_bytes(conteudo)
                                try:
                                    from core.siga_sefaz import persistir_relatorio
                                    persistir_relatorio(cnpj_sel, nome_arquivo, tipo, conteudo, periodo)
                                except Exception as e_db:
                                    st.warning(f"Salvo em cache, mas falhou ao persistir no banco (Power BI): {e_db}")
                                st.success(f"{label} atualizado ({len(conteudo)} bytes).")
                            st.rerun()

    # ── Fila de XML avulso (limite de 20/hora) ───────────────────────────────
    st.markdown("---")
    st.markdown("### Fila de XML avulso")
    st.caption(
        "Os relatórios do SIGA acima só trazem a chave de acesso de cada nota, não "
        "o XML. Use \"Enfileirar XML\" em qualquer aba pra buscar o XML completo "
        "dessas chaves na SEFAZ Nacional — limite de **20 consultas por hora por "
        "certificado**, por isso roda em fila, não na hora."
    )

    status = status_fila_xml(cnpj_sel)
    pendente  = status.get("PENDENTE", 0)
    concluido = status.get("CONCLUIDO", 0)
    erro      = status.get("ERRO", 0)

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Pendentes", pendente)
    col_b.metric("Concluídos", concluido)
    col_c.metric("Com erro", erro)

    if pendente:
        horas = -(-pendente // 20)  # arredonda pra cima
        st.info(f"Fila roda a cada hora (até 20 por vez) — previsão de ~{horas}h para concluir os {pendente} pendentes.")

    pasta_xml = XML_DIR / cnpj_sel
    arquivos_xml = sorted(pasta_xml.glob("*.xml")) if pasta_xml.exists() else []
    if arquivos_xml:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in arquivos_xml:
                zf.write(f, arcname=f.name)
        st.download_button(
            f"Baixar {len(arquivos_xml)} XML(s) prontos (.zip)",
            data=buf.getvalue(),
            file_name=f"xml_fila_{cnpj_sel}.zip",
            mime="application/zip",
            use_container_width=True,
        )
