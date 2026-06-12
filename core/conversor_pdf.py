"""
core/conversor_pdf.py — Geração de DANFSe v1.0 a partir de XML NFSe nacional
Layout idêntico ao modelo nacional (Padrão SPED/NFSe).
"""
from __future__ import annotations
import io
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    HRFlowable, KeepTogether
)
from reportlab.graphics.shapes import Drawing, Rect, String, Circle
from reportlab.graphics import renderPDF
from reportlab.platypus.flowables import Flowable

try:
    import qrcode
    from PIL import Image as PILImage
    import tempfile, os
    _QR_OK = True
except ImportError:
    _QR_OK = False

# ── Cores DANFSe nacional ──────────────────────────────────────────────────────
COR_HEADER_BG   = colors.HexColor("#1F3864")   # azul escuro cabeçalho de seção
COR_HEADER_TEXT = colors.white
COR_LABEL_BG    = colors.HexColor("#DDEEFF")   # azul claro rótulos
COR_BORDA       = colors.HexColor("#AAAAAA")
COR_VERDE_NFS   = colors.HexColor("#00AA44")
COR_DARK_LOGO   = colors.HexColor("#1F3864")

NS = {"nfse": "http://www.sped.fazenda.gov.br/nfse"}

PAGE_W, PAGE_H = A4
MARGIN = 12 * mm


# ── Helpers XML ───────────────────────────────────────────────────────────────

def _tag(root: ET.Element, *tags: str) -> str:
    """Busca o primeiro texto encontrado para qualquer das tags (sem namespace)."""
    for tag in tags:
        for el in root.iter():
            local = el.tag.split("}")[-1] if "}" in el.tag else el.tag
            if local == tag and el.text and el.text.strip():
                return el.text.strip()
    return "-"


def _fmt_cnpj(s: str) -> str:
    d = "".join(c for c in s if c.isdigit())
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    return s


def _fmt_cep(s: str) -> str:
    d = "".join(c for c in s if c.isdigit())
    if len(d) == 8:
        return f"{d[:5]}-{d[5:]}"
    return s


def _fmt_data(s: str) -> str:
    """ISO 8601 → dd/MM/yyyy HH:mm:ss"""
    if not s or s == "-":
        return "-"
    try:
        s2 = s[:19].replace("T", " ")
        dt = datetime.strptime(s2, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return s


def _fmt_data_curta(s: str) -> str:
    """ISO 8601 yyyy-MM-dd → dd/MM/yyyy"""
    if not s or s == "-":
        return "-"
    try:
        dt = datetime.strptime(s[:10], "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return s


def _fmt_valor(s: str) -> str:
    if not s or s == "-":
        return "-"
    try:
        return f"R$ {float(s):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return s


def _municipio_nome(cod: str, uf: str = "") -> str:
    tabela = {
        "2307601": "Limoeiro do Norte", "2304400": "Fortaleza",
        "3550308": "São Paulo", "3304557": "Rio de Janeiro",
        "5300108": "Brasília",
    }
    nome = tabela.get(cod, cod)
    return f"{nome} - {uf}" if uf else nome


def _opcao_simpnac(cod: str) -> str:
    mapa = {
        "1": "Não optante",
        "2": "Não optante - Excluído no ano-calendário",
        "3": "Optante - ME/EPP",
        "4": "Optante - MEI",
    }
    return mapa.get(cod, cod if cod else "-")


def _reg_trib_sn(cod: str) -> str:
    mapa = {
        "1": "Regime de apuração dos tributos federais e municipal pelo Simples Nacional",
        "2": "Regime de apuração dos tributos federais pelo Simples Nacional e tributação municipal fora do Simples Nacional",
        "3": "Regime de apuração dos tributos municipais pelo Simples Nacional e tributação federal fora do Simples Nacional",
    }
    return mapa.get(cod, cod if cod else "-")


def _retencao_issqn(cod: str) -> str:
    return {"1": "Não Retido", "2": "Retido", "3": "Retido pelo Intermediário"}.get(cod, cod if cod else "-")


def _tributacao_issqn(cod: str) -> str:
    return {"1": "Operação Tributável", "2": "Imune", "3": "Isenta", "4": "Exportação",
            "5": "Não Incidência", "6": "Suspensa - Decisão Judicial",
            "7": "Suspensa - Processo Administrativo"}.get(cod, cod if cod else "-")


def _cod_trib_nac(cod: str) -> str:
    """Formata código de tributação nacional: '010801' → '01.08.01'"""
    c = "".join(ch for ch in (cod or "") if ch.isdigit())
    if len(c) == 6:
        return f"{c[:2]}.{c[2:4]}.{c[4:]}"
    return cod if cod else "-"


# ── Extração de dados do XML ───────────────────────────────────────────────────

def _parse_xml(xml_bytes: bytes) -> dict:
    root = ET.fromstring(xml_bytes)
    g = lambda *tags: _tag(root, *tags)

    # DPS
    dps_el = next((e for e in root.iter() if e.tag.split("}")[-1] == "DPS"), None)
    dps = dps_el if dps_el is not None else root

    # Emitente (NFSe level)
    emit_el = next((e for e in root.iter() if e.tag.split("}")[-1] == "emit"), root)

    # Endereço emitente
    ender_el = next((e for e in emit_el.iter() if e.tag.split("}")[-1] in ("enderNac", "enderExt")), None)
    def _ender_txt(el) -> tuple[str, str, str]:
        if el is None:
            return "-", "-", "-"
        xLgr  = _tag(el, "xLgr")
        nro   = _tag(el, "nro")
        xCpl  = _tag(el, "xCpl")
        bairro= _tag(el, "xBairro")
        cMun  = _tag(el, "cMun")
        uf    = _tag(el, "UF")
        cep   = _fmt_cep(_tag(el, "CEP"))
        partes = [p for p in [xLgr, nro, xCpl, bairro] if p and p != "-"]
        end_str = ", ".join(partes)
        mun_str = _municipio_nome(cMun, uf)
        return end_str, mun_str, cep

    emit_end, emit_mun, emit_cep = _ender_txt(ender_el)

    # Tomador
    toma_el = next((e for e in root.iter() if e.tag.split("}")[-1] == "toma"), None)
    toma_cnpj_raw = _tag(toma_el, "CNPJ", "CPF") if toma_el else "-"
    toma_end_el = next((e for e in (toma_el or root).iter() if e.tag.split("}")[-1] in ("endNac", "endExt", "end")), None)
    # end dentro de toma
    if toma_el is not None:
        # xLgr pode estar direto em toma_el ou dentro de end
        toma_xLgr   = _tag(toma_el, "xLgr")
        toma_nro    = _tag(toma_el, "nro")
        toma_xCpl   = _tag(toma_el, "xCpl")
        toma_bairro = _tag(toma_el, "xBairro")
        inner_end   = next((e for e in toma_el.iter() if e.tag.split("}")[-1] in ("endNac","endExt")), None)
        toma_cMun   = _tag(inner_end or toma_el, "cMun")
        toma_uf     = _tag(toma_el, "UF") or _tag(inner_end or toma_el, "UF")
        toma_cep    = _fmt_cep(_tag(inner_end or toma_el, "CEP"))
        partes_t = [p for p in [toma_xLgr, toma_nro, toma_xCpl, toma_bairro] if p and p != "-"]
        toma_end_str = ", ".join(partes_t) if partes_t else "-"
        toma_mun     = _municipio_nome(toma_cMun, toma_uf) if toma_cMun != "-" else "-"
    else:
        toma_end_str = toma_mun = toma_cep = "-"

    # Serviço
    serv_el  = next((e for e in root.iter() if e.tag.split("}")[-1] == "serv"), None)
    cServ_el = next((e for e in (serv_el or root).iter() if e.tag.split("}")[-1] == "cServ"), None)

    # Tributação
    trib_el    = next((e for e in root.iter() if e.tag.split("}")[-1] == "trib"), None)
    tribMun_el = next((e for e in (trib_el or root).iter() if e.tag.split("}")[-1] == "tribMun"), None)
    totTrib_el = next((e for e in (trib_el or root).iter() if e.tag.split("}")[-1] == "totTrib"), None)

    # regTrib (emitente)
    regTrib_el = next((e for e in root.iter() if e.tag.split("}")[-1] == "regTrib"), None)
    opSimpNac  = _tag(regTrib_el, "opSimpNac") if regTrib_el else "-"
    regApTribSN= _tag(regTrib_el, "regApTribSN") if regTrib_el else "-"
    regEspTrib = _tag(regTrib_el, "regEspTrib") if regTrib_el else "-"

    # valores NFSe (nivel raiz)
    vals_el = next((e for e in root.iter() if e.tag.split("}")[-1] == "valores"
                    and any(c.tag.split("}")[-1] == "vBC" for c in e)), None)
    # valores DPS
    vals_dps = next((e for e in (dps or root).iter() if e.tag.split("}")[-1] == "valores"
                     and any(c.tag.split("}")[-1] in ("vServPrest",) for c in e)), None)
    vServ_el = next((e for e in (vals_dps or root).iter() if e.tag.split("}")[-1] == "vServPrest"), None)

    # chave de acesso — Id do infNFSe
    chave = "-"
    for el in root.iter():
        local = el.tag.split("}")[-1]
        if local == "infNFSe":
            id_attr = el.get("Id", "")
            if id_attr.startswith("NFS"):
                chave = id_attr[3:]
            break

    # locPrest
    locPrest_el = next((e for e in root.iter() if e.tag.split("}")[-1] == "locPrest"), None)
    cLocPrest = _tag(locPrest_el, "cLocPrestacao") if locPrest_el else "-"
    xLocPrest = _municipio_nome(cLocPrest) if cLocPrest != "-" else _tag(root, "xLocPrestacao")

    pAliq_raw = (_tag(tribMun_el, "pAliq") if tribMun_el else None) or _tag(vals_el, "pAliqAplic") if vals_el else "-"
    try:
        pAliq_fmt = f"{float(pAliq_raw):.2f}%"
    except Exception:
        pAliq_fmt = pAliq_raw if pAliq_raw else "-"

    vServ_raw = _tag(vServ_el, "vServ") if vServ_el else (_tag(vals_el, "vBC") if vals_el else "-")
    vISSQN_raw= _tag(vals_el, "vISSQN") if vals_el else "-"
    vLiq_raw  = _tag(vals_el, "vLiq") if vals_el else vServ_raw
    vBC_raw   = _tag(vals_el, "vBC") if vals_el else vServ_raw

    indTotTrib = _tag(totTrib_el, "indTotTrib") if totTrib_el else "0"

    cTribNac_raw = _tag(cServ_el, "cTribNac") if cServ_el else g("cTribNac")
    cTribNac_fmt = _cod_trib_nac(cTribNac_raw)
    xTribNac_desc = g("xTribNac")
    # Formata como "01.08.01 - 108 / descrição"
    if xTribNac_desc and xTribNac_desc != "-":
        cod_trib_label = f"{cTribNac_fmt} - {xTribNac_desc}"
    else:
        cod_trib_label = cTribNac_fmt

    return {
        "chave":         chave,
        "nNFSe":         g("nNFSe"),
        "competencia":   _fmt_data_curta(g("dCompet")),
        "dhProc":        _fmt_data(g("dhProc")),
        "nDPS":          g("nDPS", "nDFSe"),
        "serie":         g("serie"),
        "dhEmi":         _fmt_data(g("dhEmi")),
        # emitente
        "emit_cnpj":     _fmt_cnpj(g("CNPJ") if _tag(emit_el,"CNPJ") != "-" else g("CNPJ")),
        "emit_im":       _tag(emit_el, "IM"),
        "emit_nome":     _tag(emit_el, "xNome"),
        "emit_email":    _tag(emit_el, "email"),
        "emit_end":      emit_end,
        "emit_mun":      emit_mun,
        "emit_cep":      emit_cep,
        "emit_fone":     _tag(emit_el, "fone"),
        "opSimpNac":     _opcao_simpnac(opSimpNac),
        "regApTribSN":   _reg_trib_sn(regApTribSN),
        # tomador
        "toma_cnpj":     _fmt_cnpj(toma_cnpj_raw),
        "toma_im":       _tag(toma_el, "IM") if toma_el else "-",
        "toma_nome":     _tag(toma_el, "xNome") if toma_el else "-",
        "toma_email":    _tag(toma_el, "email") if toma_el else "-",
        "toma_end":      toma_end_str,
        "toma_mun":      toma_mun,
        "toma_cep":      toma_cep,
        "toma_fone":     _tag(toma_el, "fone") if toma_el else "-",
        # serviço
        "cod_trib_nac":  cod_trib_label,
        "cod_trib_mun":  g("xTribMun") or "-",
        "loc_prest":     xLocPrest,
        "pais_prest":    g("xPaisPrestacao", "cPaisPrestacao"),
        "desc_serv":     _tag(cServ_el, "xDescServ") if cServ_el else g("xDescServ"),
        "cNBS":          _tag(cServ_el, "cNBS") if cServ_el else g("cNBS"),
        # trib municipal
        "tribISSQN":     _tributacao_issqn(_tag(tribMun_el, "tribISSQN") if tribMun_el else "-"),
        "paisResult":    g("cPaisResult"),
        "munIncid":      _municipio_nome(_tag(tribMun_el, "cMunFG") if tribMun_el else cLocPrest),
        "regEspTrib":    regEspTrib,
        "tipoImun":      g("tpImunidade"),
        "suspExig":      "Não",
        "numProc":       g("nProcesso"),
        "benMun":        g("xBenMun"),
        "vServ":         _fmt_valor(vServ_raw),
        "descIncond":    _fmt_valor(g("vDescIncond")),
        "totDed":        _fmt_valor(g("vDedRed")),
        "calcBM":        _fmt_valor(g("vCalcBM")),
        "vBC":           _fmt_valor(vBC_raw),
        "pAliq":         pAliq_fmt,
        "retISSQN":      _retencao_issqn(_tag(tribMun_el, "tpRetISSQN") if tribMun_el else "-"),
        "vISSQN":        _fmt_valor(vISSQN_raw),
        # trib federal
        "irrf":          _fmt_valor(g("vIRRF")),
        "contribPrev":   _fmt_valor(g("vCP")),
        "contribSoc":    _fmt_valor(g("vCSLL","vPISPASEP")),
        "descContrib":   g("xContribSoc"),
        "pis":           _fmt_valor(g("vPIS")),
        "cofins":        _fmt_valor(g("vCOFINS")),
        # valor total
        "vServTotal":    _fmt_valor(vServ_raw),
        "descCond":      _fmt_valor(g("vDescCond")),
        "descIncondT":   _fmt_valor(g("vDescIncond")),
        "issqnRetido":   _fmt_valor(g("vISSRet")),
        "totRetFed":     _fmt_valor(g("vTotRet")),
        "pisCofins":     "-",
        "vLiq":          _fmt_valor(vLiq_raw),
        # tributos aproximados
        "tribFed":       "-" if indTotTrib == "0" else _fmt_valor(g("vTotFed")),
        "tribEst":       "-" if indTotTrib == "0" else _fmt_valor(g("vTotEst")),
        "tribMun_val":   "-" if indTotTrib == "0" else _fmt_valor(g("vTotMun")),
        # info complementar
        "cNBS_fmt":      f"NBS: {_tag(cServ_el, 'cNBS')}" if cServ_el and _tag(cServ_el,"cNBS") != "-" else "",
        # prefeitura
        "xLocEmi":       g("xLocEmi"),
        "uf_emit":       g("UF") or "CE",
    }


# ── Logo NFS-e (vetorial) ──────────────────────────────────────────────────────

class NfseLogo(Flowable):
    """Logo vetorial do DANFSe idêntico ao modelo nacional."""
    W = 52 * mm
    H = 14 * mm

    def __init__(self):
        super().__init__()
        self.width  = self.W
        self.height = self.H

    def draw(self):
        c = self.canv
        w, h = self.W, self.H
        # fundo azul escuro
        c.setFillColor(COR_DARK_LOGO)
        c.rect(0, 0, w * 0.35, h, fill=1, stroke=0)
        # texto "NFS" branco
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(2 * mm, h * 0.32, "NFS")
        # círculo verde com "e"
        cx = w * 0.35 - 5 * mm
        cy = h * 0.52
        r  = 4 * mm
        c.setFillColor(COR_VERDE_NFS)
        c.circle(cx, cy, r, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-BoldOblique", 10)
        c.drawCentredString(cx, cy - 3.5, "e")
        # texto lateral
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 5.5)
        c.drawString(w * 0.36, h * 0.72, "Nota Fiscal de")
        c.drawString(w * 0.36, h * 0.48, "Serviço")
        c.drawString(w * 0.36, h * 0.24, "Eletrônica")


# ── Estilos de parágrafo ───────────────────────────────────────────────────────

def _styles():
    label = ParagraphStyle("label", fontName="Helvetica", fontSize=6.5, leading=8,
                           textColor=colors.HexColor("#444444"))
    value = ParagraphStyle("value", fontName="Helvetica", fontSize=7.5, leading=9.5,
                           textColor=colors.black)
    sec   = ParagraphStyle("sec", fontName="Helvetica-Bold", fontSize=7.5, leading=9.5,
                           textColor=COR_HEADER_TEXT)
    title = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=13, leading=16,
                           textColor=colors.black, alignment=TA_CENTER)
    sub   = ParagraphStyle("sub", fontName="Helvetica", fontSize=8.5, leading=10,
                           textColor=colors.black, alignment=TA_CENTER)
    pref  = ParagraphStyle("pref", fontName="Helvetica-Bold", fontSize=7.5, leading=9.5,
                           textColor=colors.black, alignment=TA_RIGHT)
    big   = ParagraphStyle("big", fontName="Helvetica-Bold", fontSize=9, leading=11,
                           textColor=colors.black)
    return label, value, sec, title, sub, pref, big


# ── Construção do PDF ──────────────────────────────────────────────────────────

def _qr_image(chave: str):
    if not _QR_OK or chave == "-":
        return None
    try:
        qr = qrcode.QRCode(box_size=2, border=1,
                           error_correction=qrcode.constants.ERROR_CORRECT_M)
        qr.add_data(chave)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        from reportlab.platypus import Image as RLImage
        return RLImage(buf, width=22 * mm, height=22 * mm)
    except Exception:
        return None


def _sec_header(label: str, sec_style) -> Table:
    """Linha de cabeçalho de seção (fundo azul escuro, texto branco em negrito)."""
    p = Paragraph(f"<b>{label}</b>", sec_style)
    t = Table([[p]], colWidths=[PAGE_W - 2 * MARGIN])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COR_HEADER_BG),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("BOX", (0, 0), (-1, -1), 0.3, COR_BORDA),
    ]))
    return t


def _grid(rows: list[list], col_widths: list[float],
          label_style, value_style,
          highlight_last_value: bool = False) -> Table:
    """
    Constrói uma tabela de grid com rótulo (linha 0) e valor (linha 1)
    para cada grupo de colunas passado como [[label, value], ...].

    rows: lista de linhas, cada linha é lista de (label, value).
    """
    usable = PAGE_W - 2 * MARGIN
    total_cols = len(col_widths)
    assert sum(col_widths) <= usable + 1, f"colunas excedem largura: {sum(col_widths)} > {usable}"

    tbl_rows = []
    for row in rows:
        label_row = []
        value_row = []
        for lbl, val in row:
            label_row.append(Paragraph(lbl, label_style))
            if highlight_last_value and (lbl, val) == row[-1]:
                value_row.append(Paragraph(f"<b>{val}</b>",
                    ParagraphStyle("bv", parent=value_style, fontSize=9)))
            else:
                value_row.append(Paragraph(val, value_style))
        tbl_rows.append(label_row)
        tbl_rows.append(value_row)

    t = Table(tbl_rows, colWidths=col_widths)
    style_cmds = [
        ("FONTNAME",  (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE",  (0, 0), (-1, -1), 7),
        ("TOPPADDING",    (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 3),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 2),
        ("VALIGN",    (0, 0), (-1, -1), "TOP"),
        ("BOX",       (0, 0), (-1, -1), 0.3, COR_BORDA),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, COR_BORDA),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [COR_LABEL_BG, colors.white]),
    ]
    t.setStyle(TableStyle(style_cmds))
    return t


def gerar_danfse(xml_bytes: bytes) -> bytes:
    """Recebe bytes de um XML NFSe nacional e retorna bytes do PDF DANFSe v1.0."""
    d = _parse_xml(xml_bytes)
    label_s, value_s, sec_s, title_s, sub_s, pref_s, big_s = _styles()
    buf = io.BytesIO()
    usable = PAGE_W - 2 * MARGIN

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN,  bottomMargin=MARGIN,
        title=f"DANFSe - NFS-e {d['nNFSe']}",
    )

    story = []

    # ── CABEÇALHO ──────────────────────────────────────────────────────────────
    qr = _qr_image(d["chave"])
    qr_cell = qr if qr else Paragraph("", value_s)

    logo_cell = NfseLogo()

    title_cell = [
        Paragraph("DANFSe v1.0", title_s),
        Paragraph("Documento Auxiliar da NFS-e", sub_s),
    ]

    pref_txt = (f"PREFEITURA MUNICIPAL DE<br/>"
                f"<b>{d['xLocEmi'].upper()}</b><br/>{d['uf_emit']}")
    pref_cell = Paragraph(pref_txt, pref_s)

    header_table = Table(
        [[logo_cell, title_cell, pref_cell]],
        colWidths=[52 * mm, usable - 52 * mm - 35 * mm, 35 * mm],
    )
    header_table.setStyle(TableStyle([
        ("VALIGN",  (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",   (1, 0), (1, 0),   "CENTER"),
        ("ALIGN",   (2, 0), (2, 0),   "RIGHT"),
        ("BOX",     (0, 0), (-1, -1), 0.5, COR_BORDA),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
    ]))
    story.append(header_table)

    # ── CHAVE DE ACESSO + QR ───────────────────────────────────────────────────
    qr_note = Paragraph(
        "<i>A autenticidade desta NFS-e pode ser<br/>"
        "verificada pela leitura deste código QR ou<br/>"
        "pela consulta da chave de acesso no portal</i>",
        ParagraphStyle("qrnote", fontName="Helvetica", fontSize=5.8, leading=7.5,
                       alignment=TA_RIGHT, textColor=colors.HexColor("#555555")),
    )
    qr_block = [[qr_note], [qr_cell]] if qr else [[qr_note]]
    chave_w = usable - 42 * mm

    chave_table = Table(
        [[Paragraph(f"<b>Chave de Acesso da NFS-e</b>", label_s),
          Table(qr_block, colWidths=[42 * mm])],
         [Paragraph(d["chave"], value_s), ""]],
        colWidths=[chave_w, 42 * mm],
        rowHeights=[None, None],
    )
    chave_table.setStyle(TableStyle([
        ("SPAN",    (1, 0), (1, 1)),
        ("VALIGN",  (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",   (1, 0), (1, -1), "CENTER"),
        ("BOX",     (0, 0), (-1, -1), 0.3, COR_BORDA),
        ("INNERGRID",(0, 0), (-1, -1), 0.3, COR_BORDA),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING",   (0, 0), (-1, -1), 3),
        ("BACKGROUND", (0, 0), (0, 0), COR_LABEL_BG),
        ("BACKGROUND", (0, 1), (0, 1), colors.white),
    ]))
    story.append(chave_table)

    # ── LINHA: Número NFS-e / Competência / Emissão NFS-e ─────────────────────
    w4 = usable / 4
    grid1 = _grid(
        [[("Número da NFS-e", d["nNFSe"]),
          ("Competência da NFS-e", d["competencia"]),
          ("Data e Hora da emissão da NFS-e", d["dhProc"]),
          ("", "")]],
        [w4, w4, w4, w4], label_s, value_s,
    )
    story.append(grid1)

    grid2 = _grid(
        [[("Número da DPS", d["nDPS"]),
          ("Série da DPS", d["serie"]),
          ("Data e Hora da emissão da DPS", d["dhEmi"]),
          ("", "")]],
        [w4, w4, w4, w4], label_s, value_s,
    )
    story.append(grid2)

    # ── EMITENTE ───────────────────────────────────────────────────────────────
    story.append(_sec_header("EMITENTE DA NFS-e", sec_s))
    w3 = usable / 3
    story.append(_grid(
        [[("Prestador do Serviço", ""),
          ("CNPJ / CPF / NIF", d["emit_cnpj"]),
          ("Inscrição Municipal", d["emit_im"]),
          ("Telefone", d["emit_fone"])]],
        [w3 * 0.3, w3 * 0.7, w3 * 0.6, w3 * 0.4],
        label_s, value_s,
    ))
    story.append(_grid(
        [[("Nome / Nome Empresarial", d["emit_nome"]),
          ("E-mail", d["emit_email"])]],
        [usable * 0.65, usable * 0.35], label_s, value_s,
    ))
    story.append(_grid(
        [[("Endereço", d["emit_end"]),
          ("Município", d["emit_mun"]),
          ("CEP", d["emit_cep"])]],
        [usable * 0.55, usable * 0.30, usable * 0.15], label_s, value_s,
    ))
    story.append(_grid(
        [[("Simples Nacional na Data de Competência", d["opSimpNac"]),
          ("Regime de Apuração Tributária pelo SN", d["regApTribSN"])]],
        [usable * 0.40, usable * 0.60], label_s, value_s,
    ))

    # ── TOMADOR ────────────────────────────────────────────────────────────────
    story.append(_sec_header("TOMADOR DO SERVIÇO", sec_s))
    story.append(_grid(
        [[("", ""),
          ("CNPJ / CPF / NIF", d["toma_cnpj"]),
          ("Inscrição Municipal", d["toma_im"]),
          ("Telefone", d["toma_fone"])]],
        [w3 * 0.3, w3 * 0.7, w3 * 0.6, w3 * 0.4],
        label_s, value_s,
    ))
    story.append(_grid(
        [[("Nome / Nome Empresarial", d["toma_nome"]),
          ("E-mail", d["toma_email"])]],
        [usable * 0.65, usable * 0.35], label_s, value_s,
    ))
    story.append(_grid(
        [[("Endereço", d["toma_end"]),
          ("Município", d["toma_mun"]),
          ("CEP", d["toma_cep"])]],
        [usable * 0.55, usable * 0.30, usable * 0.15], label_s, value_s,
    ))

    # ── INTERMEDIÁRIO ──────────────────────────────────────────────────────────
    inter = Table(
        [[Paragraph("INTERMEDIÁRIO DO SERVIÇO NÃO IDENTIFICADO NA NFS-e",
                    ParagraphStyle("inter", fontName="Helvetica-Bold", fontSize=7,
                                   alignment=TA_CENTER, textColor=colors.black, leading=9))]],
        colWidths=[usable],
    )
    inter.setStyle(TableStyle([
        ("BOX",  (0, 0), (-1, -1), 0.3, COR_BORDA),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(inter)

    # ── SERVIÇO PRESTADO ───────────────────────────────────────────────────────
    story.append(_sec_header("SERVIÇO PRESTADO", sec_s))
    story.append(_grid(
        [[("Código de Tributação Nacional", d["cod_trib_nac"]),
          ("Código de Tributação Municipal", d["cod_trib_mun"]),
          ("Local da Prestação", d["loc_prest"]),
          ("País da Prestação", d["pais_prest"])]],
        [usable * 0.35, usable * 0.25, usable * 0.25, usable * 0.15],
        label_s, value_s,
    ))
    story.append(_grid(
        [[("Descrição do Serviço", d["desc_serv"])]],
        [usable], label_s, value_s,
    ))

    # ── TRIBUTAÇÃO MUNICIPAL ───────────────────────────────────────────────────
    story.append(_sec_header("TRIBUTAÇÃO MUNICIPAL", sec_s))
    story.append(_grid(
        [[("Tributação do ISSQN", d["tribISSQN"]),
          ("País Resultado da Prestação do Serviço", d["paisResult"]),
          ("Município de Incidência do ISSQN", d["munIncid"]),
          ("Regime Especial de Tributação", d["regEspTrib"])]],
        [usable / 4] * 4, label_s, value_s,
    ))
    story.append(_grid(
        [[("Tipo de Imunidade", d["tipoImun"]),
          ("Suspensão da Exigibilidade do ISSQN", d["suspExig"]),
          ("Número Processo Suspensão", d["numProc"]),
          ("Benefício Municipal", d["benMun"])]],
        [usable / 4] * 4, label_s, value_s,
    ))
    story.append(_grid(
        [[("Valor do Serviço", d["vServ"]),
          ("Desconto Incondicionado", d["descIncond"]),
          ("Total Deduções/Reduções", d["totDed"]),
          ("Cálculo do BM", d["calcBM"])]],
        [usable / 4] * 4, label_s, value_s,
    ))
    story.append(_grid(
        [[("BC ISSQN", d["vBC"]),
          ("Alíquota Aplicada", d["pAliq"]),
          ("Retenção do ISSQN", d["retISSQN"]),
          ("ISSQN Apurado", d["vISSQN"])]],
        [usable / 4] * 4, label_s, value_s,
    ))

    # ── TRIBUTAÇÃO FEDERAL ─────────────────────────────────────────────────────
    story.append(_sec_header("TRIBUTAÇÃO FEDERAL", sec_s))
    story.append(_grid(
        [[("IRRF", d["irrf"]),
          ("Contribuição Previdenciária - Retida", d["contribPrev"]),
          ("Contribuições Sociais - Retidas", d["contribSoc"]),
          ("Descrição Contrib. Sociais - Retidas", d["descContrib"])]],
        [usable / 4] * 4, label_s, value_s,
    ))
    story.append(_grid(
        [[("PIS - Débito Apuração Própria", d["pis"]),
          ("COFINS - Débito Apuração Própria", d["cofins"])]],
        [usable / 2, usable / 2], label_s, value_s,
    ))

    # ── VALOR TOTAL ────────────────────────────────────────────────────────────
    story.append(_sec_header("VALOR TOTAL DA NFS-E", sec_s))
    story.append(_grid(
        [[("Valor do Serviço", d["vServTotal"]),
          ("Desconto Condicionado", d["descCond"]),
          ("Desconto Incondicionado", d["descIncondT"]),
          ("ISSQN Retido", d["issqnRetido"])]],
        [usable / 4] * 4, label_s, value_s,
    ))
    story.append(_grid(
        [[("Total das Retenções Federais", d["totRetFed"]),
          ("PIS/COFINS - Débito Apur. Própria", d["pisCofins"]),
          ("", ""),
          ("Valor Líquido da NFS-e", d["vLiq"])]],
        [usable / 4] * 4, label_s, value_s,
        highlight_last_value=True,
    ))

    # ── TOTAIS APROXIMADOS ─────────────────────────────────────────────────────
    story.append(_sec_header("TOTAIS APROXIMADOS DOS TRIBUTOS", sec_s))
    story.append(_grid(
        [[("Federais", d["tribFed"]),
          ("Estaduais", d["tribEst"]),
          ("Municipais", d["tribMun_val"])]],
        [usable / 3, usable / 3, usable / 3], label_s, value_s,
    ))

    # ── INFORMAÇÕES COMPLEMENTARES ─────────────────────────────────────────────
    story.append(_sec_header("INFORMAÇÕES COMPLEMENTARES", sec_s))
    info_txt = d["cNBS_fmt"] or "-"
    info_t = Table(
        [[Paragraph(info_txt, value_s)]],
        colWidths=[usable],
    )
    info_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.3, COR_BORDA),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
    ]))
    story.append(info_t)

    doc.build(story)
    return buf.getvalue()


# ── Interface de uso (linha de comando / Streamlit) ────────────────────────────

def gerar_pdf_bytes(xml_bytes: bytes) -> bytes:
    return gerar_danfse(xml_bytes)
