"""
core/danfse_pdf.py — Geração local de DANFSe v1.0 (PDF) a partir de XML NFS-e Nacional
Layout oficial DANFSe v1.0 conforme padrão SPED/Fazenda.
Usa reportlab platypus com Tables para reproduzir o grid oficial.
"""

from io import BytesIO
from datetime import datetime
from xml.etree import ElementTree as ET

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

_NS = "http://www.sped.fazenda.gov.br/nfse"

# ── Cores padrão DANFSe Nacional ─────────────────────────────────────────────
SEC_HDR_BG  = colors.HexColor("#d9d9d9")  # fundo dos cabeçalhos de seção (cinza)
SEC_HDR_TXT = colors.HexColor("#1a1a1a")  # texto dos cabeçalhos (quase preto)
DATA_BG     = colors.white                # fundo das células de dados
BOX_BORDER  = colors.HexColor("#808080")  # bordas
WHITE       = colors.white
BLACK       = colors.black
LABEL_CLR   = colors.HexColor("#555555")


def _t(el, tag: str) -> str:
    if el is None:
        return ""
    found = el.find(f".//{{{_NS}}}{tag}")
    return found.text.strip() if found is not None and found.text else ""


def _fmt_cnpj(v: str) -> str:
    d = "".join(c for c in v if c.isdigit())
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return v or "-"


def _fmt_cep(v: str) -> str:
    d = "".join(c for c in v if c.isdigit())
    if len(d) == 8:
        return f"{d[:5]}-{d[5:]}"
    return v or "-"


def _fmt_moeda(v: str) -> str:
    if not v:
        return "-"
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return v or "-"


def _fmt_aliq(v: str) -> str:
    if not v:
        return "-"
    try:
        return f"{float(v):.4f}%"
    except (ValueError, TypeError):
        return f"{v}%"


def _fmt_dt(v: str) -> str:
    """Formata string ISO (YYYY-MM-DDTHH:MM:SS) → DD/MM/YYYY HH:MM:SS"""
    if not v:
        return "-"
    v = v.replace("T", " ")
    parts = v.split(" ")
    date_part = parts[0]
    time_part = parts[1][:8] if len(parts) > 1 else ""
    if len(date_part) == 10 and date_part[4] == "-":
        date_part = f"{date_part[8:10]}/{date_part[5:7]}/{date_part[:4]}"
    return f"{date_part} {time_part}".strip()


def _fmt_dt_date(v: str) -> str:
    """Formata somente a data"""
    if not v:
        return "-"
    d = v[:10]
    if len(d) == 10 and d[4] == "-":
        return f"{d[8:10]}/{d[5:7]}/{d[:4]}"
    return d


def _dash(v: str) -> str:
    return v if v else "-"


def _map_tp_trib(v: str) -> str:
    m = {
        "1": "1 - Operação Tributável",
        "2": "2 - Operação Isenta/Não Tributável",
        "3": "3 - Exportação",
        "4": "4 - Imune",
        "5": "5 - Exigibilidade Suspensa",
        "6": "6 - Não Incidência",
    }
    return m.get(v, _dash(v))


def _map_ret_iss(v: str) -> str:
    m = {
        "1": "1 - Retido",
        "2": "2 - Não Retido",
        "3": "3 - Substituição Tributária",
    }
    return m.get(v, _dash(v))


def _map_op_sn(v: str) -> str:
    m = {"1": "Optante", "2": "Não Optante"}
    return m.get(v, _dash(v))


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

    # ── Identificação da NFS-e ────────────────────────────────────────────────
    n_nfse      = _t(inf, "nNFSe")
    dh_emi      = _t(inf, "dhEmi") or tv("dhEmi")
    d_compet    = tv("dCompet")

    n_dps       = ""
    serie       = ""
    dh_emi_dps  = ""
    if inf_dps is not None:
        n_dps      = _t(inf_dps, "nDPS")
        serie      = _t(inf_dps, "serie")
        dh_emi_dps = _t(inf_dps, "dhEmi") or dh_emi

    # Chave de Acesso
    chave_acesso = ""
    inf_id = inf.get("Id", "")
    if inf_id.startswith("NFS"):
        chave_acesso = inf_id[3:]
    elif len(inf_id) >= 44:
        chave_acesso = inf_id

    # ── Emitente ──────────────────────────────────────────────────────────────
    emit = inf.find(f"{{{_NS}}}emit")
    if emit is None and inf_dps is not None:
        emit = inf_dps.find(f"{{{_NS}}}emit")

    emit_cnpj  = (_t(emit, "CNPJ") or _t(emit, "CPF")) if emit is not None else ""
    emit_im    = _t(emit, "IM")    if emit is not None else ""
    emit_fone  = (_t(emit, "fone") or _t(emit, "tel")) if emit is not None else ""
    emit_nome  = _t(emit, "xNome") if emit is not None else ""
    emit_email = (_t(emit, "email") or _t(emit, "xEmail")) if emit is not None else ""
    emit_lgr   = _t(emit, "xLgr")  if emit is not None else ""
    emit_nro   = _t(emit, "nro")   if emit is not None else ""
    emit_cpl   = _t(emit, "xCpl")  if emit is not None else ""
    emit_mun   = _t(emit, "xMun")  if emit is not None else ""
    emit_uf    = _t(emit, "UF")    if emit is not None else ""
    emit_cep   = _t(emit, "CEP")   if emit is not None else ""

    emit_end_parts = []
    if emit_lgr:
        p = emit_lgr
        if emit_nro:
            p += f", {emit_nro}"
        if emit_cpl:
            p += f" - {emit_cpl}"
        emit_end_parts.append(p)
    emit_end = ", ".join(emit_end_parts)

    op_sn    = tv("opSN") or tv("optSN")
    reg_trib = tv("regTrib")

    # Fallback para nome do município: tenta elemento prest e xMunIncid antecipadamente
    prest_el = inf_dps.find(f"{{{_NS}}}prest") if inf_dps is not None else None
    prest_mun = _t(prest_el, "xMun") if prest_el is not None else ""
    trib_mun_early = inf_dps.find(f".//{{{_NS}}}tribMun") if inf_dps is not None else None
    x_mun_incid_early = (
        (_t(trib_mun_early, "xMunIncid") if trib_mun_early is not None else "")
        or tv("xMunIncid") or tv("xMunPrest")
    )

    city_name = emit_mun or prest_mun or x_mun_incid_early or ""
    emit_mun_uf = city_name
    if emit_uf:
        emit_mun_uf = f"{city_name} - {emit_uf}" if city_name else emit_uf

    uf   = emit_uf  or ""

    # ── Tomador ───────────────────────────────────────────────────────────────
    toma = inf_dps.find(f"{{{_NS}}}toma") if inf_dps is not None else None
    toma_doc   = (_t(toma, "CNPJ") or _t(toma, "CPF")) if toma is not None else ""
    toma_im    = _t(toma, "IM")    if toma is not None else ""
    toma_fone  = (_t(toma, "fone") or _t(toma, "tel")) if toma is not None else ""
    toma_nome  = _t(toma, "xNome") if toma is not None else ""
    toma_email = (_t(toma, "email") or _t(toma, "xEmail")) if toma is not None else ""
    toma_lgr   = _t(toma, "xLgr") if toma is not None else ""
    toma_nro   = _t(toma, "nro")  if toma is not None else ""
    toma_mun   = _t(toma, "xMun") if toma is not None else ""
    toma_uf    = _t(toma, "UF")   if toma is not None else ""
    toma_cep   = _t(toma, "CEP")  if toma is not None else ""

    toma_end = toma_lgr
    if toma_nro and toma_end:
        toma_end += f", {toma_nro}"
    elif toma_nro:
        toma_end = toma_nro
    toma_mun_uf = toma_mun
    if toma_uf:
        toma_mun_uf = f"{toma_mun} - {toma_uf}" if toma_mun else toma_uf

    # ── Serviço ───────────────────────────────────────────────────────────────
    c_trib_nac  = tv("cTribNac")
    x_trib_nac  = tv("xTribNac")
    c_trib_nac_fmt = (f"{c_trib_nac} - {x_trib_nac}" if c_trib_nac and x_trib_nac
                      else _dash(c_trib_nac or x_trib_nac))

    c_trib_mun   = tv("cTribMun")
    x_mun_prest  = tv("xMunPrest") or tv("cMunPrest")
    x_pais_prest = tv("xPaisPrest") or tv("cPaisPrest")

    xdsc = ""
    for tag in ("xDscServ", "discServ", "xDisc", "xServico", "xDescServ"):
        xdsc = tv(tag)
        if xdsc:
            break

    # ── Tributação Municipal ──────────────────────────────────────────────────
    trib_mun_node = inf_dps.find(f".//{{{_NS}}}tribMun") if inf_dps is not None else None
    tp_trib       = _t(trib_mun_node, "tpTrib") or tv("tpTrib")
    x_pais_res    = tv("xPaisResultado") or tv("cPaisResultado")
    x_mun_incid   = tv("xMunIncid") or tv("cMunIncid")
    city = city_name or x_mun_incid or x_mun_prest or ""
    reg_esp_trib  = tv("regEspTrib")
    tp_imun       = tv("tpImun")
    x_mot_sust    = tv("xMotDesonSusp") or tv("motDesonSusp")
    n_proc_susp   = tv("nProcessoSusp")
    c_benef       = tv("cBenef")
    tp_ret_iss    = _t(trib_mun_node, "tpRetISSQN") or tv("tpRetISSQN")

    # ── Valores ───────────────────────────────────────────────────────────────
    vals_nfse = inf.find(f"{{{_NS}}}valores")
    v_serv_prest  = (_t(vals_nfse, "vServPrest") or _t(vals_nfse, "vBC") or "") if vals_nfse is not None else ""
    v_desc_incond = (_t(vals_nfse, "vDescIncond") or "")   if vals_nfse is not None else ""
    v_ded         = (_t(vals_nfse, "vDed")         or "")  if vals_nfse is not None else ""
    v_bc          = (_t(vals_nfse, "vBC")           or "")  if vals_nfse is not None else ""
    p_aliq        = (_t(vals_nfse, "pAliqAplic")    or "")  if vals_nfse is not None else ""
    v_issqn       = (_t(vals_nfse, "vISSQN")        or "")  if vals_nfse is not None else ""
    v_liq         = (_t(vals_nfse, "vLiq")          or v_bc or "") if vals_nfse is not None else ""
    v_desc_cond   = (_t(vals_nfse, "vDescCond")     or "")  if vals_nfse is not None else ""
    v_ret_issqn   = (_t(vals_nfse, "vRetISSQN")     or "")  if vals_nfse is not None else ""
    v_calc_bm     = (_t(vals_nfse, "vCalcBM")       or "")  if vals_nfse is not None else ""

    # ── Tributação Federal ────────────────────────────────────────────────────
    v_ret_irrf   = ""
    v_ret_cp     = ""
    v_ret_csll   = ""
    v_ret_pis    = ""
    v_ret_cofins = ""
    v_pis_prop   = ""
    v_cof_prop   = ""
    if inf_dps is not None:
        v_ret_irrf   = _t(inf_dps, "vRetIRRF")     or _t(inf_dps, "vIRRF")
        v_ret_cp     = _t(inf_dps, "vRetCP")        or _t(inf_dps, "vInss")
        v_ret_csll   = _t(inf_dps, "vRetCSLL")      or _t(inf_dps, "vRetCsll") or _t(inf_dps, "vCsll")
        v_ret_pis    = _t(inf_dps, "vRetPis")       or _t(inf_dps, "vPis")
        v_ret_cofins = _t(inf_dps, "vRetCofins")    or _t(inf_dps, "vCofins")
        v_pis_prop   = _t(inf_dps, "vPisAprop")     or _t(inf_dps, "vPisProp")
        v_cof_prop   = _t(inf_dps, "vCofinsAprop")  or _t(inf_dps, "vCofinsProp")

    # ── Tributos Aproximados ──────────────────────────────────────────────────
    v_trib_fed  = tv("vTribFed")  or tv("vAprofFed")
    v_trib_est  = tv("vTribEst")  or tv("vAprofEst")
    v_trib_mun2 = tv("vTribMun")  or tv("vAprofMun")

    # ── Informações Complementares ────────────────────────────────────────────
    nbs_code = tv("NBS") or tv("cNBS")
    inf_compl = tv("infCompl") or tv("xInfComp") or tv("infAdic") or ""
    if nbs_code and not inf_compl:
        inf_compl = f"NBS: {nbs_code}"
    elif nbs_code and "NBS" not in inf_compl:
        inf_compl = f"NBS: {nbs_code} | {inf_compl}"

    return {
        "n_nfse": n_nfse, "dh_emi": dh_emi, "d_compet": d_compet,
        "n_dps": n_dps, "serie": serie, "dh_emi_dps": dh_emi_dps,
        "chave_acesso": chave_acesso,
        "city": city, "uf": uf,

        "emit_cnpj": emit_cnpj, "emit_im": emit_im, "emit_fone": emit_fone,
        "emit_nome": emit_nome, "emit_email": emit_email,
        "emit_end": emit_end, "emit_mun_uf": emit_mun_uf, "emit_cep": emit_cep,
        "op_sn": op_sn, "reg_trib": reg_trib,

        "toma_doc": toma_doc, "toma_im": toma_im, "toma_fone": toma_fone,
        "toma_nome": toma_nome, "toma_email": toma_email,
        "toma_end": toma_end, "toma_mun_uf": toma_mun_uf, "toma_cep": toma_cep,

        "c_trib_nac": c_trib_nac_fmt, "c_trib_mun": c_trib_mun,
        "x_mun_prest": x_mun_prest, "x_pais_prest": x_pais_prest,
        "xdsc": xdsc,

        "tp_trib": tp_trib, "x_pais_res": x_pais_res, "x_mun_incid": x_mun_incid,
        "reg_esp_trib": reg_esp_trib, "tp_imun": tp_imun,
        "x_mot_sust": x_mot_sust, "n_proc_susp": n_proc_susp, "c_benef": c_benef,
        "v_serv_prest": v_serv_prest, "v_desc_incond": v_desc_incond,
        "v_ded": v_ded, "v_calc_bm": v_calc_bm,
        "v_bc": v_bc, "p_aliq": p_aliq, "tp_ret_iss": tp_ret_iss, "v_issqn": v_issqn,

        "v_ret_irrf": v_ret_irrf, "v_ret_cp": v_ret_cp, "v_ret_csll": v_ret_csll,
        "v_ret_pis": v_ret_pis, "v_ret_cofins": v_ret_cofins,
        "v_pis_prop": v_pis_prop, "v_cof_prop": v_cof_prop,

        "v_serv_total": v_serv_prest, "v_desc_cond": v_desc_cond,
        "v_ret_issqn": v_ret_issqn, "v_liq": v_liq,

        "v_trib_fed": v_trib_fed, "v_trib_est": v_trib_est, "v_trib_mun2": v_trib_mun2,

        "inf_compl": inf_compl,
    }


def _make_qr(data_str: str):
    """Gera imagem QR code como ImageReader. Retorna None se qrcode não disponível."""
    try:
        import qrcode
        
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=3,
            border=2,
        )
        qr.add_data(data_str)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf
    except Exception:
        return None


def gerar_danfse_pdf(xml_bytes: bytes) -> bytes:
    """Retorna bytes de um PDF DANFSe v1.0 gerado localmente."""
    data = _parse_xml(xml_bytes)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )
    W = A4[0] - 20 * mm

    styles = getSampleStyleSheet()

    def ps(name, **kw):
        return ParagraphStyle(name, parent=styles["Normal"], **kw)

    # ── Estilos ───────────────────────────────────────────────────────────────
    s_lbl = ps("lbl", fontSize=6, textColor=colors.HexColor("#555555"),
                fontName="Helvetica-Bold", leading=7)
    s_val = ps("val", fontSize=8, textColor=BLACK, fontName="Helvetica",
                leading=10, wordWrap="LTR")
    s_val_b = ps("valb", fontSize=8, textColor=BLACK, fontName="Helvetica-Bold",
                  leading=10)
    s_sec = ps("sec", fontSize=7, textColor=SEC_HDR_TXT, fontName="Helvetica-Bold",
                alignment=TA_LEFT, leading=9)
    s_ctr = ps("ctr", fontSize=7, textColor=SEC_HDR_TXT, fontName="Helvetica-Bold",
                alignment=TA_CENTER, leading=9)

    BASE_TS = TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.5, BOX_BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.3, BOX_BORDER),
        ("BACKGROUND",    (0, 0), (-1, -1), DATA_BG),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 3),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 3),
    ])

    def lv(label: str, value: str, bold_val: bool = False) -> Paragraph:
        val_font = "Helvetica-Bold" if bold_val else "Helvetica"
        val_size = "9" if bold_val else "8"
        txt = (
            f'<font name="Helvetica-Bold" size="6" color="#555555">{label.upper()}</font><br/>'
            f'<font name="{val_font}" size="{val_size}">{_dash(value)}</font>'
        )
        return Paragraph(txt, s_val)

    def sec_hdr(title: str, subtitle: str = "") -> Table:
        """Cabeçalho de seção cinza claro com texto escuro (padrão nacional)."""
        inner = f'<font name="Helvetica-Bold" size="7">{title}</font>'
        if subtitle:
            inner += f'<br/><font name="Helvetica" size="6">{subtitle}</font>'
        t = Table([[Paragraph(inner, s_sec)]], colWidths=[W])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), SEC_HDR_BG),
            ("TOPPADDING",    (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("BOX",           (0, 0), (-1, -1), 0.5, BOX_BORDER),
        ]))
        return t

    story = []
    cw3 = W / 3
    cw4 = W / 4

    # ═════════════════════════════════════════════════════════════════════════
    # CABEÇALHO: Logo NFS-e | DANFSe v1.0 | Prefeitura + QR
    # ═════════════════════════════════════════════════════════════════════════
    qr_img = _make_qr(data["chave_acesso"] or "")

    # Logo oficial NFSe (letras coloridas N=azul, F=verde, S=laranja, e=azul)
    logo_txt = (
        '<font name="Helvetica-Bold" size="16" color="#0066cc">N</font>'
        '<font name="Helvetica-Bold" size="16" color="#009933">F</font>'
        '<font name="Helvetica-Bold" size="16" color="#ff6600">S</font>'
        '<font name="Helvetica-Bold" size="16" color="#0066cc">e</font><br/>'
        '<font name="Helvetica" size="6">Nota Fiscal Eletrônica</font>'
    )
    left_cell = Paragraph(logo_txt, ps("logo", alignment=TA_CENTER, leading=14))

    center_cell = Paragraph(
        '<font name="Helvetica-Bold" size="13">DANFSe v1.0</font><br/>'
        '<font name="Helvetica" size="8">Documento Auxiliar da NFS-e</font>',
        ps("dc", alignment=TA_CENTER, leading=14),
    )

    city_txt = data["city"].upper() if data["city"] else ""
    uf_txt   = data["uf"].upper()   if data["uf"]   else ""
    pref_txt = (
        '<font name="Helvetica-Bold" size="6">PREFEITURA MUNICIPAL DE</font><br/>'
        f'<font name="Helvetica-Bold" size="7">{city_txt}</font><br/>'
        f'<font name="Helvetica-Bold" size="6">{uf_txt}</font>'
    )
    pref_p = Paragraph(pref_txt, ps("pref", alignment=TA_CENTER, leading=8))

    auth_txt = (
        '<font name="Helvetica" size="5" color="#555555">'
        'A autenticidade desta NFS-e pode ser<br/>'
        'verificada pela leitura deste código QR ou<br/>'
        'pela consulta da chave de acesso no portal'
        '</font>'
    )
    auth_p = Paragraph(auth_txt, ps("auth", alignment=TA_CENTER, leading=6))

    if qr_img:
        from reportlab.platypus import Image as RLImage
        qr_size = 16 * mm
        right_inner = Table(
            [[pref_p], [RLImage(qr_img, width=qr_size, height=qr_size)], [auth_p]],
            colWidths=[W * 0.28],
        )
        right_inner.setStyle(TableStyle([
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ]))
        right_cell = right_inner
    else:
        right_cell = pref_p

    hdr_table = Table(
        [[left_cell, center_cell, right_cell]],
        colWidths=[W * 0.14, W * 0.58, W * 0.28],
    )
    hdr_table.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.5, BOX_BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.4, BOX_BORDER),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND",    (0, 0), (-1, -1), DATA_BG),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(hdr_table)

    # ═════════════════════════════════════════════════════════════════════════
    # CHAVE DE ACESSO
    # ═════════════════════════════════════════════════════════════════════════
    chave_val = data["chave_acesso"] or "-"
    chave_t = Table([[lv("Chave de Acesso da NFS-e", chave_val)]], colWidths=[W])
    chave_t.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.5, BOX_BORDER),
        ("BACKGROUND",    (0, 0), (-1, -1), DATA_BG),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 3),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 3),
    ]))
    story.append(chave_t)

    # ═════════════════════════════════════════════════════════════════════════
    # IDs NFS-e / DPS
    # ═════════════════════════════════════════════════════════════════════════
    ids_t = Table([
        [
            lv("Número da NFS-e",                data["n_nfse"]),
            lv("Competência da NFS-e",            _fmt_dt_date(data["d_compet"])),
            lv("Data e Hora da emissão da NFS-e", _fmt_dt(data["dh_emi"])),
        ],
        [
            lv("Número da DPS",                  data["n_dps"]),
            lv("Série da DPS",                   data["serie"]),
            lv("Data e Hora da emissão da DPS",  _fmt_dt(data["dh_emi_dps"])),
        ],
    ], colWidths=[cw3, cw3, cw3])
    ids_t.setStyle(BASE_TS)
    story.append(ids_t)

    # ═════════════════════════════════════════════════════════════════════════
    # EMITENTE
    # ═════════════════════════════════════════════════════════════════════════
    story.append(sec_hdr("EMITENTE DA NFS-e", "Prestador do Serviço"))

    emit_cnpj_fmt = _fmt_cnpj(data["emit_cnpj"]) if data["emit_cnpj"] else "-"
    emit_cep_fmt  = _fmt_cep(data["emit_cep"])   if data["emit_cep"]  else "-"

    emit_t = Table([
        [
            lv("CNPJ / CPF / NIF",   emit_cnpj_fmt),
            lv("Inscrição Municipal", data["emit_im"]),
            lv("Telefone",           data["emit_fone"]),
        ],
        [
            lv("Nome / Nome Empresarial", data["emit_nome"]),
            lv("", ""),
            lv("E-mail", data["emit_email"]),
        ],
        [
            lv("Endereço", data["emit_end"]),
            lv("Município", data["emit_mun_uf"]),
            lv("CEP", emit_cep_fmt),
        ],
        [
            lv("Simples Nacional na Data de Competência", _map_op_sn(data["op_sn"])),
            lv("Regime de Apuração Tributária pelo SN",   _dash(data["reg_trib"])),
            lv("", ""),
        ],
    ], colWidths=[cw3, cw3, cw3])
    emit_t.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.5, BOX_BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.3, BOX_BORDER),
        ("BACKGROUND",    (0, 0), (-1, -1), DATA_BG),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 3),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 3),
        ("SPAN",          (0, 1), (1, 1)),
        ("SPAN",          (0, 2), (0, 2)),
    ]))
    story.append(emit_t)

    # ═════════════════════════════════════════════════════════════════════════
    # TOMADOR
    # ═════════════════════════════════════════════════════════════════════════
    story.append(sec_hdr("TOMADOR DO SERVIÇO"))

    toma_cnpj_fmt = _fmt_cnpj(data["toma_doc"]) if data["toma_doc"] else "-"
    toma_cep_fmt  = _fmt_cep(data["toma_cep"])  if data["toma_cep"]  else "-"

    toma_t = Table([
        [
            lv("CNPJ / CPF / NIF",        toma_cnpj_fmt),
            lv("Inscrição Municipal",      data["toma_im"]),
            lv("Telefone",                 data["toma_fone"]),
        ],
        [
            lv("Nome / Nome Empresarial",  data["toma_nome"]),
            lv("", ""),
            lv("E-mail", data["toma_email"]),
        ],
        [
            lv("Endereço",  data["toma_end"]),
            lv("Município", data["toma_mun_uf"]),
            lv("CEP",       toma_cep_fmt),
        ],
    ], colWidths=[cw3, cw3, cw3])
    toma_t.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.5, BOX_BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.3, BOX_BORDER),
        ("BACKGROUND",    (0, 0), (-1, -1), DATA_BG),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 3),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 3),
        ("SPAN",          (0, 1), (1, 1)),
    ]))
    story.append(toma_t)

    # Intermediário
    interm_t = Table(
        [[Paragraph("INTERMEDIÁRIO DO SERVIÇO NÃO IDENTIFICADO NA NFS-e", s_ctr)]],
        colWidths=[W],
    )
    interm_t.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.5, BOX_BORDER),
        ("BACKGROUND",    (0, 0), (-1, -1), DATA_BG),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(interm_t)

    # ═════════════════════════════════════════════════════════════════════════
    # SERVIÇO PRESTADO
    # ═════════════════════════════════════════════════════════════════════════
    story.append(sec_hdr("SERVIÇO PRESTADO"))

    serv_t = Table([
        [
            lv("Código de Tributação Nacional",  data["c_trib_nac"]),
            lv("Código de Tributação Municipal", data["c_trib_mun"]),
            lv("Local da Prestação",             data["x_mun_prest"]),
            lv("País da Prestação",              data["x_pais_prest"]),
        ],
        [
            Paragraph(
                '<font name="Helvetica-Bold" size="6" color="#555555">DESCRIÇÃO DO SERVIÇO</font><br/>'
                f'<font name="Helvetica" size="8">{_dash(data["xdsc"])}</font>',
                s_val,
            ),
            "", "", "",
        ],
    ], colWidths=[cw4, cw4, cw4, cw4])
    serv_t.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.5, BOX_BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.3, BOX_BORDER),
        ("BACKGROUND",    (0, 0), (-1, -1), DATA_BG),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 3),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 3),
        ("SPAN",          (0, 1), (3, 1)),
    ]))
    story.append(serv_t)

    # ═════════════════════════════════════════════════════════════════════════
    # TRIBUTAÇÃO MUNICIPAL
    # ═════════════════════════════════════════════════════════════════════════
    story.append(sec_hdr("TRIBUTAÇÃO MUNICIPAL"))

    trib_mun_t = Table([
        [
            lv("Tributação do ISSQN",                    _map_tp_trib(data["tp_trib"])),
            lv("País Resultado da Prestação do Serviço", data["x_pais_res"]),
            lv("Município de Incidência do ISSQN",       data["x_mun_incid"]),
            lv("Regime Especial de Tributação",          data["reg_esp_trib"]),
        ],
        [
            lv("Tipo de Imunidade",                   data["tp_imun"]),
            lv("Suspensão da Exigibilidade do ISSQN", data["x_mot_sust"]),
            lv("Número Processo Suspensão",           data["n_proc_susp"]),
            lv("Benefício Municipal",                 data["c_benef"]),
        ],
        [
            lv("Valor do Serviço",        _fmt_moeda(data["v_serv_prest"])),
            lv("Desconto Incondicionado", _fmt_moeda(data["v_desc_incond"])),
            lv("Total Deduções/Reduções", _fmt_moeda(data["v_ded"])),
            lv("Cálculo do BM",           _fmt_moeda(data["v_calc_bm"])),
        ],
        [
            lv("BC ISSQN",          _fmt_moeda(data["v_bc"])),
            lv("Alíquota Aplicada", _fmt_aliq(data["p_aliq"])),
            lv("Retenção do ISSQN", _map_ret_iss(data["tp_ret_iss"])),
            lv("ISSQN Apurado",     _fmt_moeda(data["v_issqn"])),
        ],
    ], colWidths=[cw4, cw4, cw4, cw4])
    trib_mun_t.setStyle(BASE_TS)
    story.append(trib_mun_t)

    # ═════════════════════════════════════════════════════════════════════════
    # TRIBUTAÇÃO FEDERAL
    # ═════════════════════════════════════════════════════════════════════════
    story.append(sec_hdr("TRIBUTAÇÃO FEDERAL"))

    parts_csll = []
    if data["v_ret_pis"]:    parts_csll.append(f"PIS: {_fmt_moeda(data['v_ret_pis'])}")
    if data["v_ret_cofins"]: parts_csll.append(f"COFINS: {_fmt_moeda(data['v_ret_cofins'])}")
    if data["v_ret_csll"]:   parts_csll.append(f"CSLL: {_fmt_moeda(data['v_ret_csll'])}")
    desc_csll = " | ".join(parts_csll) if parts_csll else "-"

    trib_fed_t = Table([
        [
            lv("IRRF",                                  _fmt_moeda(data["v_ret_irrf"])),
            lv("Contribuição Previdenciária - Retida",  _fmt_moeda(data["v_ret_cp"])),
            lv("Contribuições Sociais - Retidas",       _fmt_moeda(data["v_ret_csll"])),
            lv("Descrição Contrib. Sociais - Retidas",  desc_csll),
        ],
        [
            lv("PIS - Débito Apuração Própria",         _fmt_moeda(data["v_pis_prop"])),
            lv("", ""),
            lv("COFINS - Débito Apuração Própria",      _fmt_moeda(data["v_cof_prop"])),
            lv("", ""),
        ],
    ], colWidths=[cw4, cw4, cw4, cw4])
    trib_fed_t.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.5, BOX_BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.3, BOX_BORDER),
        ("BACKGROUND",    (0, 0), (-1, -1), DATA_BG),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 3),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 3),
        ("SPAN",          (0, 1), (1, 1)),
        ("SPAN",          (2, 1), (3, 1)),
    ]))
    story.append(trib_fed_t)

    # ═════════════════════════════════════════════════════════════════════════
    # VALOR TOTAL
    # ═════════════════════════════════════════════════════════════════════════
    story.append(sec_hdr("VALOR TOTAL DA NFS-E"))

    v_tot_ret_fed = ""
    try:
        s = sum(float(data[k] or 0) for k in
                ("v_ret_irrf", "v_ret_cp", "v_ret_csll", "v_ret_pis", "v_ret_cofins"))
        v_tot_ret_fed = str(s) if s > 0 else ""
    except (ValueError, TypeError):
        pass

    pis_cof_prop = ""
    try:
        pc = float(data["v_pis_prop"] or 0) + float(data["v_cof_prop"] or 0)
        pis_cof_prop = str(pc) if pc > 0 else ""
    except (ValueError, TypeError):
        pass

    val_liq_cell = Paragraph(
        '<font name="Helvetica-Bold" size="6" color="#555555">VALOR LÍQUIDO DA NFS-E</font><br/>'
        f'<font name="Helvetica-Bold" size="10">{_fmt_moeda(data["v_liq"])}</font>',
        s_val,
    )

    val_tot_t = Table([
        [
            lv("Valor do Serviço",        _fmt_moeda(data["v_serv_total"])),
            lv("Desconto Condicionado",   _fmt_moeda(data["v_desc_cond"])),
            lv("Desconto Incondicionado", _fmt_moeda(data["v_desc_incond"])),
            lv("ISSQN Retido",            _fmt_moeda(data["v_ret_issqn"])),
        ],
        [
            lv("Total das Retenções Federais",      _fmt_moeda(v_tot_ret_fed)),
            lv("PIS/COFINS - Débito Apur. Própria", _fmt_moeda(pis_cof_prop)),
            lv("", ""),
            val_liq_cell,
        ],
    ], colWidths=[cw4, cw4, cw4, cw4])
    val_tot_t.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.5, BOX_BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.3, BOX_BORDER),
        ("BACKGROUND",    (0, 0), (-1, -1), DATA_BG),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 3),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 3),
        ("SPAN",          (1, 1), (2, 1)),
    ]))
    story.append(val_tot_t)

    # ═════════════════════════════════════════════════════════════════════════
    # TOTAIS APROXIMADOS DOS TRIBUTOS
    # ═════════════════════════════════════════════════════════════════════════
    story.append(sec_hdr("TOTAIS APROXIMADOS DOS TRIBUTOS"))

    trib_aprox_t = Table([
        [
            lv("Federais",   _fmt_moeda(data["v_trib_fed"])),
            lv("Estaduais",  _fmt_moeda(data["v_trib_est"])),
            lv("Municipais", _fmt_moeda(data["v_trib_mun2"])),
        ],
    ], colWidths=[cw3, cw3, cw3])
    trib_aprox_t.setStyle(BASE_TS)
    story.append(trib_aprox_t)

    # ═════════════════════════════════════════════════════════════════════════
    # INFORMAÇÕES COMPLEMENTARES
    # ═════════════════════════════════════════════════════════════════════════
    story.append(sec_hdr("INFORMAÇÕES COMPLEMENTARES"))

    inf_compl_txt = data["inf_compl"] or "-"
    inf_compl_t = Table(
        [[Paragraph(
            f'<font name="Helvetica" size="7">{inf_compl_txt}</font>',
            ps("ic", leading=10, wordWrap="LTR"),
        )]],
        colWidths=[W],
    )
    inf_compl_t.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.5, BOX_BORDER),
        ("BACKGROUND",    (0, 0), (-1, -1), DATA_BG),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 3),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 3),
    ]))
    story.append(inf_compl_t)

    doc.build(story)
    return buf.getvalue()
