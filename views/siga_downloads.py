"""views/siga_downloads.py — Relatórios do SIGA (SEFAZ-CE): NF-e, NFC-e e índices de malha.

Modelo híbrido: o cron (core/siga_scheduler.py) gera os arquivos de madrugada
em data/siga_downloads/<cnpj>/. Esta tela lista o que já está em cache (rápido,
funciona mesmo com o SIGA fora do ar) e oferece "Atualizar agora" por aba para
buscar ao vivo quando necessário.
"""
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

    st.markdown("---")

    for nome_arquivo, tipo, nome_aba, filtros in _listar_abas():
        label = _LABELS.get(nome_arquivo, nome_arquivo)
        caminho = _caminho_cache(cnpj_sel, nome_arquivo, periodo)

        with st.container(border=True):
            col_info, col_baixar, col_atualizar = st.columns([3, 1, 1])

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
                                st.success(f"{label} atualizado ({len(conteudo)} bytes).")
                            st.rerun()

    # ── XML das notas não escrituradas (fila com limite de 20/hora) ─────────
    caminho_malha = _caminho_cache(cnpj_sel, "INDICADORES_MALHA_pendencias", periodo)
    if caminho_malha.exists():
        st.markdown("---")
        st.markdown("### XML das notas não escrituradas")
        st.caption(
            "O SIGA só traz a chave de acesso de cada nota, não o XML. O XML completo "
            "vem da SEFAZ Nacional, que limita a **20 consultas por hora por certificado** — "
            "por isso o download roda em fila, não na hora."
        )

        from core.siga_sefaz import extrair_chaves_malha

        status = status_fila_xml(cnpj_sel)
        pendente  = status.get("PENDENTE", 0)
        concluido = status.get("CONCLUIDO", 0)
        erro      = status.get("ERRO", 0)

        col_a, col_b, col_c, col_d = st.columns(4)
        col_a.metric("Pendentes", pendente)
        col_b.metric("Concluídos", concluido)
        col_c.metric("Com erro", erro)
        with col_d:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Enfileirar XML de todas as chaves", use_container_width=True):
                chaves = extrair_chaves_malha(caminho_malha.read_bytes())
                qtd = enfileirar_xml(user["username"], cnpj_sel, chaves)
                st.success(f"{qtd} chave(s) verificada(s)/enfileirada(s) ({len(chaves)} encontradas no relatório).")
                st.rerun()

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
                file_name=f"xml_nao_escrituradas_{cnpj_sel}.zip",
                mime="application/zip",
                use_container_width=True,
            )
