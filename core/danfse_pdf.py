"""
core/danfse_pdf.py — Geração local de DANFSe (PDF) a partir de XML NFS-e
Usa reportlab platypus para layout profissional em A4.
"""

from io import BytesIO
from datetime import datetime
from xml.etree import ElementTree as ET

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

_NS = "http://www.sped.fazenda.gov.br/nfse"

# ── Cores ─────────────────────────────────────────────────────────────────────
DARK_BLUE  = colors.HexColor("#1a3a5c")
MED_BLUE   = colors.HexColor("#2d5f8a")
LIGHT_GRAY = colors.HexColor("#f0f4f8")
BOX_BORDER = colors.HexColor("#c8d8e8")
WHITE      = colors.white
BLACK      = colors.black


def _t(el, tag: str) -> str:
    found = el.find(f".//{{{_NS}}}{tag}")
    return found.text.strip() if found is not None and found.text else ""


def _fmt_cnpj(v: str) -> str:
    d = "".join(c for c in v if c.isdigit())
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return v


def _fmt_chave(v: str) -> str:
    """Formata chave de acesso em grupos de 4."""
    d = "".join(c for c in v if c.isalnum())
    groups = [d[i:i+4] for i in range(0, len(d), 4)]
    return " ".join(groups)


def _fmt_moeda(v: str) -> str:
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return v or "R$ 0,00"


def _fmt_aliq(v: str) -> str:
    try:
        return f"{float(v):.4f} %"
    except (ValueError, TypeError):
        return f"{v} %" if v else "0,0000 %"


def _parse_xml(xml_bytes: bytes) -> dict:
    root = ET.fromstring(xml_bytes)

    inf = root.find(f"{{{_NS}}}infNFSe") or root.find(f".//{{{_NS}}}infNFSe")
    if inf is None:
        raise ValueError("Elemento <infNFSe> não encontrado no XML")

    inf_dps = inf.find(f".//{{{_NS}}}infDPS")

    def tv(tag):
        v = _t(inf, tag)
        if not v and inf_dps is not None:
            v = _t(inf_dps, tag)
        return v

    emit = inf.find(f"{{{_NS}}}emit")
    toma = inf_dps.find(f"{{{_NS}}}toma") if inf_dps is not None else None

    vals_nfse = inf.find(f"{{{_NS}}}valores")

    # Serviço description — várias possibilidades
    xdsc = ""
    for tag in ("xDscServ", "discServ", "xDisc", "xServico"):
        xdsc = tv(tag)
        if xdsc:
            break

    n_nfse   = _t(inf, "nNFSe") or tv("nDPS") or ""
    d_compet = tv("dCompet") or tv("dhEmi") or ""
    if d_compet:
        d_compet = d_compet[:10]

    serie = ""
    if inf_dps is not None:
        serie = _t(inf_dps, "serie")

    chave_acesso = ""
    inf_id = inf.get("Id", "")
    if inf_id.startswith("NFS"):
        chave_acesso = inf_id[3:47]
    elif len(inf_id) >= 44:
        chave_acesso = inf_id[:44]

    emit_nome      = _t(emit, "xNome")   if emit is not None else ""
    emit_cnpj      = _t(emit, "CNPJ")   if emit is not None else ""
    emit_im        = _t(emit, "IM")     if emit is not None else ""
    emit_uf        = _t(emit, "UF")     if emit is not None else ""
    emit_lgr       = _t(emit, "xLgr")  if emit is not None else ""
    emit_nro       = _t(emit, "nro")    if emit is not None else ""
    emit_cpl       = _t(emit, "xCpl")  if emit is not None else ""
    emit_bairro    = _t(emit, "xBairro") if emit is not None else ""
    emit_cmun_nome = _t(emit, "xMun")  if emit is not None else ""

    toma_nome = _t(toma, "xNome") if toma is not None else ""
    toma_doc  = (_t(toma, "CNPJ") or _t(toma, "CPF")) if toma is not None else ""

    v_bc    = (_t(vals_nfse, "vBC")          if vals_nfse is not None else "") or "0.00"
    v_bruto = (_t(vals_nfse, "vServPrest") or _t(vals_nfse, "vBC") or "0.00") if vals_nfse is not None else "0.00"
    v_iss   = (_t(vals_nfse, "vISSQN")       if vals_nfse is not None else "") or "0.00"
    v_liq   = (_t(vals_nfse, "vLiq")         if vals_nfse is not None else "") or v_bc
    p_aliq  = (_t(vals_nfse, "pAliqAplic")   if vals_nfse is not None else "") or ""

    v_ret_cofins = v_ret_pis = v_ret_csl = v_ret_irrf = v_ret_inss = ""
    if inf_dps is not None:
        v_ret_cofins = _t(inf_dps, "vRetCofins") or _t(inf_dps, "vCofins")
        v_ret_pis    = _t(inf_dps, "vRetPis")    or _t(inf_dps, "vPis")
        v_ret_csl    = _t(inf_dps, "vRetCSLL")   or _t(inf_dps, "vRetCsll") or _t(inf_dps, "vCsll")
        v_ret_irrf   = _t(inf_dps, "vRetIRRF")   or _t(inf_dps, "vIRRF")
        v_ret_inss   = _t(inf_dps, "vRetInss")   or _t(inf_dps, "vInss")

    # Endereço prestador
    endereco_parts = []
    if emit_lgr:
        part = emit_lgr
        if emit_nro:
            part += f", {emit_nro}"
        if emit_cpl:
            part += f" - {emit_cpl}"
        endereco_parts.append(part)
    if emit_bairro:
        endereco_parts.append(emit_bairro)
    municipio_uf = ""
    if emit_cmun_nome:
        municipio_uf = emit_cmun_nome
        if emit_uf:
            municipio_uf += f"/{emit_uf}"
    elif emit_uf:
        municipio_uf = emit_uf

    return {
        "n_nfse": n_nfse, "d_compet": d_compet, "serie": serie,
        "chave_acesso": chave_acesso,
        "emit_nome": emit_nome, "emit_cnpj": emit_cnpj,
        "emit_im": emit_im, "municipio_uf": municipio_uf,
        "endereco": ", ".join(endereco_parts),
        "toma_nome": toma_nome, "toma_doc": toma_doc,
        "xdsc": xdsc,
        "v_bruto": v_bruto, "v_bc": v_bc, "p_aliq": p_aliq,
        "v_iss": v_iss, "v_liq": v_liq,
        "v_ret_cofins": v_ret_cofins, "v_ret_pis": v_ret_pis,
        "v_ret_csl": v_ret_csl, "v_ret_irrf": v_ret_irrf, "v_ret_inss": v_ret_inss,
    }


def gerar_danfse_pdf(xml_bytes: bytes) -> bytes:
    """Retorna bytes de um PDF DANFSe gerado localmente a partir do XML."""
    data = _parse_xml(xml_bytes)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )
    W = A4[0] - 24 * mm  # largura útil

    styles = getSampleStyleSheet()

    def style(name, **kw):
        base = styles["Normal"]
        return ParagraphStyle(name, parent=base, **kw)

    s_title    = style("title",    fontSize=11, textColor=WHITE, fontName="Helvetica-Bold",
                       alignment=TA_CENTER, leading=14)
    s_danfse   = style("danfse",   fontSize=16, textColor=WHITE, fontName="Helvetica-Bold",
                       alignment=TA_CENTER, leading=20)
    s_label    = style("label",    fontSize=6.5, textColor=DARK_BLUE, fontName="Helvetica-Bold",
                       leading=9)
    s_value    = style("value",    fontSize=8.5, textColor=BLACK, fontName="Helvetica",
                       leading=11)
    s_desc     = style("desc",     fontSize=8, textColor=BLACK, fontName="Helvetica",
                       leading=11, wordWrap="LTR")
    s_hdr      = style("hdr",      fontSize=7, textColor=WHITE, fontName="Helvetica-Bold",
                       alignment=TA_CENTER, leading=9)
    s_cell     = style("cell",     fontSize=8, textColor=BLACK, fontName="Helvetica",
                       alignment=TA_RIGHT, leading=10)
    s_footer   = style("footer",   fontSize=6.5, textColor=colors.HexColor("#555555"),
                       fontName="Helvetica", leading=9, alignment=TA_CENTER)
    s_chave    = style("chave",    fontSize=7.5, textColor=BLACK, fontName="Courier",
                       alignment=TA_CENTER, leading=10)

    story = []

    # ── Cabeçalho / Título ────────────────────────────────────────────────────
    title_text = "Documento Auxiliar da Nota Fiscal de Serviços Eletrônica"
    header_data = [
        [Paragraph(title_text, s_title), Paragraph("DANFSe", s_danfse)],
    ]
    header_table = Table(header_data, colWidths=[W * 0.78, W * 0.22])
    header_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), DARK_BLUE),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",  (0, 0), (0, 0), 10),
        ("RIGHTPADDING", (-1, 0), (-1, 0), 10),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 4 * mm))

    # ── Número / Data / Série ─────────────────────────────────────────────────
    d_fmt = data["d_compet"]
    if d_fmt and len(d_fmt) == 10:
        d_fmt = f"{d_fmt[8:10]}/{d_fmt[5:7]}/{d_fmt[:4]}"

    s_nnum = style("nnum", fontSize=13, fontName="Helvetica-Bold",
                   textColor=DARK_BLUE, leading=16)
    info_data = [
        [
            Paragraph("NÚMERO DA NFS-e", s_label),
            Paragraph("DATA DE COMPETÊNCIA", s_label),
            Paragraph("SÉRIE", s_label),
        ],
        [
            Paragraph(f"<b>{data['n_nfse'] or '—'}</b>", s_nnum),
            Paragraph(d_fmt or "—", s_value),
            Paragraph(data["serie"] or "—", s_value),
        ],
    ]
    info_table = Table(info_data, colWidths=[W * 0.30, W * 0.45, W * 0.25])
    info_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), LIGHT_GRAY),
        ("BOX",           (0, 0), (-1, -1), 0.5, BOX_BORDER),
        ("GRID",          (0, 0), (-1, -1), 0.3, BOX_BORDER),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 3 * mm))

    # ── Helper: caixa com título ──────────────────────────────────────────────
    def section_header(title):
        t = Table([[Paragraph(title, s_hdr)]], colWidths=[W])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), MED_BLUE),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ]))
        return t

    lw = W * 0.30
    vw = W * 0.70

    box_style = TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), LIGHT_GRAY),
        ("BOX",           (0, 0), (-1, -1), 0.5, BOX_BORDER),
        ("LINEBELOW",     (0, 0), (-1, -2), 0.3, BOX_BORDER),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ])

    # ── Prestador ─────────────────────────────────────────────────────────────
    story.append(section_header("PRESTADOR DE SERVIÇOS"))
    prest_rows = [
        [Paragraph("RAZÃO SOCIAL / NOME", s_label), Paragraph(data["emit_nome"] or "—", s_value)],
        [Paragraph("CNPJ", s_label),
         Paragraph(
             f"{_fmt_cnpj(data['emit_cnpj'])}     IM: {data['emit_im'] or '—'}"
             f"     Município/UF: {data['municipio_uf'] or '—'}",
             s_value,
         )],
        [Paragraph("ENDEREÇO", s_label), Paragraph(data["endereco"] or "—", s_value)],
    ]
    prest_table = Table(prest_rows, colWidths=[lw, vw])
    prest_table.setStyle(box_style)
    story.append(prest_table)
    story.append(Spacer(1, 3 * mm))

    # ── Tomador ───────────────────────────────────────────────────────────────
    story.append(section_header("TOMADOR DE SERVIÇOS"))
    toma_rows = [
        [Paragraph("RAZÃO SOCIAL / NOME", s_label), Paragraph(data["toma_nome"] or "—", s_value)],
        [Paragraph("CNPJ / CPF", s_label),
         Paragraph(_fmt_cnpj(data["toma_doc"]) if data["toma_doc"] else "—", s_value)],
    ]
    toma_table = Table(toma_rows, colWidths=[lw, vw])
    toma_table.setStyle(box_style)
    story.append(toma_table)
    story.append(Spacer(1, 3 * mm))

    # ── Discriminação dos Serviços ────────────────────────────────────────────
    story.append(section_header("DISCRIMINAÇÃO DOS SERVIÇOS"))
    desc_text = data["xdsc"] or "Sem descrição disponível."
    desc_table = Table([[Paragraph(desc_text, s_desc)]], colWidths=[W])
    desc_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), LIGHT_GRAY),
        ("BOX",           (0, 0), (-1, -1), 0.5, BOX_BORDER),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    story.append(desc_table)
    story.append(Spacer(1, 3 * mm))

    # ── Valores ───────────────────────────────────────────────────────────────
    story.append(section_header("VALORES"))
    cw5 = W / 5
    val_header = [
        Paragraph("VALOR BRUTO", s_hdr),
        Paragraph("BASE DE CÁLCULO", s_hdr),
        Paragraph("ALÍQUOTA ISS (%)", s_hdr),
        Paragraph("ISS", s_hdr),
        Paragraph("VALOR LÍQUIDO", s_hdr),
    ]
    val_data = [
        Paragraph(_fmt_moeda(data["v_bruto"]), s_cell),
        Paragraph(_fmt_moeda(data["v_bc"]), s_cell),
        Paragraph(_fmt_aliq(data["p_aliq"]), s_cell),
        Paragraph(_fmt_moeda(data["v_iss"]), s_cell),
        Paragraph(_fmt_moeda(data["v_liq"]), s_cell),
    ]
    val_table = Table([val_header, val_data], colWidths=[cw5] * 5)
    val_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), MED_BLUE),
        ("BACKGROUND",    (0, 1), (-1, 1), LIGHT_GRAY),
        ("BOX",           (0, 0), (-1, -1), 0.5, BOX_BORDER),
        ("GRID",          (0, 0), (-1, -1), 0.3, BOX_BORDER),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    story.append(val_table)
    story.append(Spacer(1, 3 * mm))

    # ── Retenções Federais (se houver) ────────────────────────────────────────
    retencoes = {
        "COFINS": data["v_ret_cofins"],
        "PIS":    data["v_ret_pis"],
        "CSLL":   data["v_ret_csl"],
        "IRRF":   data["v_ret_irrf"],
        "INSS":   data["v_ret_inss"],
    }
    if any(v for v in retencoes.values()):
        story.append(section_header("RETENÇÕES FEDERAIS"))
        ret_keys = list(retencoes.keys())
        ret_hdr  = [Paragraph(k, s_hdr) for k in ret_keys]
        ret_vals = [
            Paragraph(_fmt_moeda(retencoes[k]) if retencoes[k] else "—", s_cell)
            for k in ret_keys
        ]
        cw_ret = W / len(ret_keys)
        ret_table = Table([ret_hdr, ret_vals], colWidths=[cw_ret] * len(ret_keys))
        ret_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), MED_BLUE),
            ("BACKGROUND",    (0, 1), (-1, 1), LIGHT_GRAY),
            ("BOX",           (0, 0), (-1, -1), 0.5, BOX_BORDER),
            ("GRID",          (0, 0), (-1, -1), 0.3, BOX_BORDER),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ]))
        story.append(ret_table)
        story.append(Spacer(1, 3 * mm))

    # ── Chave de Acesso ───────────────────────────────────────────────────────
    if data["chave_acesso"]:
        story.append(section_header("CHAVE DE ACESSO"))
        chave_fmt = _fmt_chave(data["chave_acesso"])
        chave_table = Table([[Paragraph(chave_fmt, s_chave)]], colWidths=[W])
        chave_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), LIGHT_GRAY),
            ("BOX",           (0, 0), (-1, -1), 0.5, BOX_BORDER),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ]))
        story.append(chave_table)
        story.append(Spacer(1, 3 * mm))

    # ── Rodapé ────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width=W, thickness=0.5, color=BOX_BORDER))
    story.append(Spacer(1, 1.5 * mm))
    ts_now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    story.append(Paragraph(
        f"Documento gerado eletronicamente em {ts_now} | "
        "DANFSe — Documento Auxiliar da Nota Fiscal de Serviços Eletrônica",
        s_footer,
    ))

    doc.build(story)
    return buf.getvalue()
