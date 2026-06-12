"""
core/danfse_pdf.py — Geração local de DANFSe v1.0 (PDF) a partir de XML NFS-e Nacional
Layout fiel ao padrão nacional oficial (referência 333_WF_513.pdf).
"""

from io import BytesIO
from xml.etree import ElementTree as ET

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

_NS = "http://www.sped.fazenda.gov.br/nfse"

# ── Cores ─────────────────────────────────────────────────────────────────────
BRD = colors.HexColor("#999999")   # bordas
SBG = colors.HexColor("#d9d9d9")   # fundo cabeçalho de seção
WBG = colors.white


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
        return f"{float(v):.2f}%"
    except (ValueError, TypeError):
        return f"{v}%"


def _fmt_dt(v: str) -> str:
    if not v:
        return "-"
    v = v.replace("T", " ")
    parts = v.split(" ")
    d = parts[0]
    t = parts[1][:8] if len(parts) > 1 else ""
    if len(d) == 10 and d[4] == "-":
        d = f"{d[8:10]}/{d[5:7]}/{d[:4]}"
    return f"{d} {t}".strip()


def _fmt_dt_date(v: str) -> str:
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
        "1": "Operação Tributável",
        "2": "Isenta/Não Tributável",
        "3": "Exportação",
        "4": "Imune",
        "5": "Exigibilidade Suspensa",
        "6": "Não Incidência",
    }
    return m.get(v, _dash(v))


def _map_ret_iss(v: str) -> str:
    m = {"1": "Retido", "2": "Não Retido", "3": "Substituição Tributária"}
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

    n_nfse     = _t(inf, "nNFSe")
    dh_emi     = _t(inf, "dhEmi") or tv("dhEmi")
    d_compet   = tv("dCompet")
    n_dps = serie = dh_emi_dps = ""
    if inf_dps is not None:
        n_dps      = _t(inf_dps, "nDPS")
        serie      = _t(inf_dps, "serie")
        dh_emi_dps = _t(inf_dps, "dhEmi") or dh_emi

    chave_acesso = ""
    inf_id = inf.get("Id", "")
    if inf_id.startswith("NFS"):
        chave_acesso = inf_id[3:]
    elif len(inf_id) >= 44:
        chave_acesso = inf_id

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
    emit_bairro= _t(emit, "xBairro") if emit is not None else ""
    emit_mun   = _t(emit, "xMun")  if emit is not None else ""
    emit_uf    = _t(emit, "UF")    if emit is not None else ""
    emit_cep   = _t(emit, "CEP")   if emit is not None else ""

    end_parts = [emit_lgr]
    if emit_nro: end_parts.append(emit_nro)
    if emit_cpl: end_parts.append(emit_cpl)
    if emit_bairro: end_parts.append(emit_bairro)
    emit_end = ", ".join(p for p in end_parts if p)

    op_sn    = tv("opSN") or tv("optSN")
    reg_trib = tv("regTrib")

    prest_el = inf_dps.find(f"{{{_NS}}}prest") if inf_dps is not None else None
    prest_mun = _t(prest_el, "xMun") if prest_el is not None else ""
    trib_early = inf_dps.find(f".//{{{_NS}}}tribMun") if inf_dps is not None else None
    x_mun_early = (
        (_t(trib_early, "xMunIncid") if trib_early is not None else "")
        or tv("xMunIncid") or tv("xMunPrest")
    )
    city_name = emit_mun or prest_mun or x_mun_early or ""
    emit_mun_uf = (f"{city_name} - {emit_uf}" if city_name and emit_uf
                   else city_name or emit_uf or "")
    uf = emit_uf or ""

    toma = inf_dps.find(f"{{{_NS}}}toma") if inf_dps is not None else None
    toma_doc   = (_t(toma, "CNPJ") or _t(toma, "CPF")) if toma is not None else ""
    toma_im    = _t(toma, "IM")    if toma is not None else ""
    toma_fone  = (_t(toma, "fone") or _t(toma, "tel")) if toma is not None else ""
    toma_nome  = _t(toma, "xNome") if toma is not None else ""
    toma_email = (_t(toma, "email") or _t(toma, "xEmail")) if toma is not None else ""
    toma_lgr   = _t(toma, "xLgr") if toma is not None else ""
    toma_nro   = _t(toma, "nro")  if toma is not None else ""
    toma_cpl   = _t(toma, "xCpl") if toma is not None else ""
    toma_bairro= _t(toma, "xBairro") if toma is not None else ""
    toma_mun   = _t(toma, "xMun") if toma is not None else ""
    toma_uf    = _t(toma, "UF")   if toma is not None else ""
    toma_cep   = _t(toma, "CEP")  if toma is not None else ""
    toma_end_parts = [toma_lgr]
    if toma_nro: toma_end_parts.append(toma_nro)
    if toma_cpl: toma_end_parts.append(toma_cpl)
    if toma_bairro: toma_end_parts.append(toma_bairro)
    toma_end = ", ".join(p for p in toma_end_parts if p)
    toma_mun_uf = (f"{toma_mun} - {toma_uf}" if toma_mun and toma_uf
                   else toma_mun or toma_uf or "")

    c_trib_nac = tv("cTribNac")
    x_trib_nac = tv("xTribNac")
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

    trib_mun_node = inf_dps.find(f".//{{{_NS}}}tribMun") if inf_dps is not None else None
    tp_trib      = _t(trib_mun_node, "tpTrib") or tv("tpTrib")
    x_pais_res   = tv("xPaisResultado") or tv("cPaisResultado")
    x_mun_incid  = tv("xMunIncid") or tv("cMunIncid")
    city = city_name or x_mun_incid or x_mun_prest or ""
    reg_esp_trib = tv("regEspTrib")
    tp_imun      = tv("tpImun")
    x_mot_sust   = tv("xMotDesonSusp") or tv("motDesonSusp")
    n_proc_susp  = tv("nProcessoSusp")
    c_benef      = tv("cBenef")
    tp_ret_iss   = _t(trib_mun_node, "tpRetISSQN") or tv("tpRetISSQN")

    vals = inf.find(f"{{{_NS}}}valores")
    def _v(tag, fallback=""):
        return (_t(vals, tag) or fallback) if vals is not None else fallback
    v_serv_prest  = _v("vServPrest") or _v("vBC")
    v_desc_incond = _v("vDescIncond")
    v_ded         = _v("vDed")
    v_bc          = _v("vBC")
    p_aliq        = _v("pAliqAplic")
    v_issqn       = _v("vISSQN")
    v_liq         = _v("vLiq") or v_bc
    v_desc_cond   = _v("vDescCond")
    v_ret_issqn   = _v("vRetISSQN")
    v_calc_bm     = _v("vCalcBM")

    v_ret_irrf = v_ret_cp = v_ret_csll = v_ret_pis = v_ret_cofins = ""
    v_pis_prop = v_cof_prop = ""
    if inf_dps is not None:
        v_ret_irrf   = _t(inf_dps, "vRetIRRF")    or _t(inf_dps, "vIRRF")
        v_ret_cp     = _t(inf_dps, "vRetCP")       or _t(inf_dps, "vInss")
        v_ret_csll   = _t(inf_dps, "vRetCSLL")     or _t(inf_dps, "vRetCsll") or _t(inf_dps, "vCsll")
        v_ret_pis    = _t(inf_dps, "vRetPis")      or _t(inf_dps, "vPis")
        v_ret_cofins = _t(inf_dps, "vRetCofins")   or _t(inf_dps, "vCofins")
        v_pis_prop   = _t(inf_dps, "vPisAprop")    or _t(inf_dps, "vPisProp")
        v_cof_prop   = _t(inf_dps, "vCofinsAprop") or _t(inf_dps, "vCofinsProp")

    v_trib_fed  = tv("vTribFed")  or tv("vAprofFed")
    v_trib_est  = tv("vTribEst")  or tv("vAprofEst")
    v_trib_mun2 = tv("vTribMun")  or tv("vAprofMun")

    nbs_code  = tv("NBS") or tv("cNBS")
    inf_compl = tv("infCompl") or tv("xInfComp") or tv("infAdic") or ""
    if nbs_code and not inf_compl:
        inf_compl = f"NBS: {nbs_code}"
    elif nbs_code and "NBS" not in inf_compl:
        inf_compl = f"NBS: {nbs_code} | {inf_compl}"

    return {
        "n_nfse": n_nfse, "dh_emi": dh_emi, "d_compet": d_compet,
        "n_dps": n_dps, "serie": serie, "dh_emi_dps": dh_emi_dps,
        "chave_acesso": chave_acesso, "city": city, "uf": uf,
        "emit_cnpj": emit_cnpj, "emit_im": emit_im, "emit_fone": emit_fone,
        "emit_nome": emit_nome, "emit_email": emit_email,
        "emit_end": emit_end, "emit_mun_uf": emit_mun_uf, "emit_cep": emit_cep,
        "op_sn": op_sn, "reg_trib": reg_trib,
        "toma_doc": toma_doc, "toma_im": toma_im, "toma_fone": toma_fone,
        "toma_nome": toma_nome, "toma_email": toma_email,
        "toma_end": toma_end, "toma_mun_uf": toma_mun_uf, "toma_cep": toma_cep,
        "c_trib_nac": c_trib_nac_fmt, "c_trib_mun": c_trib_mun,
        "x_mun_prest": x_mun_prest, "x_pais_prest": x_pais_prest, "xdsc": xdsc,
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
    try:
        import qrcode
        qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M,
                           box_size=3, border=2)
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
    """Retorna bytes de um PDF DANFSe v1.0 no padrão nacional."""
    data = _parse_xml(xml_bytes)

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=8*mm, rightMargin=8*mm,
                            topMargin=8*mm, bottomMargin=8*mm)
    W = A4[0] - 16*mm

    styles = getSampleStyleSheet()
    def ps(n, **kw):
        return ParagraphStyle(n, parent=styles["Normal"], **kw)

    # ── Helpers ───────────────────────────────────────────────────────────────
    _BASE_TS = [
        ("BOX",           (0, 0), (-1, -1), 0.5, BRD),
        ("INNERGRID",     (0, 0), (-1, -1), 0.3, BRD),
        ("BACKGROUND",    (0, 0), (-1, -1), WBG),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING",   (0, 0), (-1, -1), 2),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 2),
    ]

    def mk(rows, cws, extra=None):
        t = Table(rows, colWidths=cws)
        t.setStyle(TableStyle(_BASE_TS + (extra or [])))
        return t

    def lv(label, val, fs=7, lfs=5):
        return Paragraph(
            f'<font name="Helvetica-Bold" size="{lfs}" color="#555555">{label.upper()}</font><br/>'
            f'<font name="Helvetica" size="{fs}">{_dash(val)}</font>',
            ps(f"lv{abs(hash(label))%9999}", leading=max(fs+2, 9), wordWrap="LTR"),
        )

    def sec(title, subtitle=""):
        txt = f'<font name="Helvetica-Bold" size="7">{title}</font>'
        if subtitle:
            txt += f'<br/><font name="Helvetica" size="5.5" color="#444444">{subtitle}</font>'
        return Paragraph(txt, ps("sec", leading=9))

    story = []
    cw3 = [W / 3] * 3
    cw4 = [W / 4] * 4
    # EMITENTE/TOMADOR column widths: título | CNPJ | IM | Tel
    CWE = [W * 0.20, W * 0.37, W * 0.25, W * 0.18]

    # ═══════════════════════════════════════════════════════════════
    # CABEÇALHO  (logo | título | prefeitura+QR)
    # ═══════════════════════════════════════════════════════════════
    qr_buf = _make_qr(data["chave_acesso"] or "")

    logo_p = Paragraph(
        '<font name="Helvetica-Bold" size="17" color="#0056b3">NFS</font>'
        '<font name="Helvetica-Bold" size="13" color="#0056b3">e</font><br/>'
        '<font name="Helvetica" size="5.5">Nota Fiscal de<br/>Serviço Eletrônica</font>',
        ps("logo", alignment=TA_LEFT, leading=14),
    )
    title_p = Paragraph(
        '<font name="Helvetica-Bold" size="14">DANFSe v1.0</font><br/>'
        '<font name="Helvetica" size="8">Documento Auxiliar da NFS-e</font>',
        ps("title", alignment=TA_CENTER, leading=15),
    )

    city_up = (data["city"] or "").upper()
    uf_up   = (data["uf"]   or "").upper()
    pref_p = Paragraph(
        '<font name="Helvetica-Bold" size="6">PREFEITURA MUNICIPAL DE</font><br/>'
        f'<font name="Helvetica-Bold" size="7">{city_up}</font><br/>'
        f'<font name="Helvetica-Bold" size="6">{uf_up}</font>',
        ps("pref", alignment=TA_RIGHT, leading=9),
    )
    auth_p = Paragraph(
        '<font name="Helvetica" size="5" color="#555555">'
        'A autenticidade desta NFS-e pode ser<br/>'
        'verificada pela leitura deste código QR ou<br/>'
        'pela consulta da chave de acesso no portal'
        '</font>',
        ps("auth", alignment=TA_RIGHT, leading=6),
    )

    RW = W * 0.27
    if qr_buf:
        from reportlab.platypus import Image as RLImage
        qr_sz = 20 * mm
        right_inner = Table(
            [[pref_p], [RLImage(qr_buf, width=qr_sz, height=qr_sz)], [auth_p]],
            colWidths=[RW],
        )
        right_inner.setStyle(TableStyle([
            ("ALIGN",         (0, 0), (-1, -1), "RIGHT"),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",    (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 1),
        ]))
        right_cell = right_inner
    else:
        right_cell = pref_p

    LW = W - RW
    hdr = Table(
        [[logo_p, title_p, right_cell]],
        colWidths=[LW * 0.20, LW * 0.80, RW],
    )
    hdr.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.5, BRD),
        ("INNERGRID",     (0, 0), (-1, -1), 0.3, BRD),
        ("BACKGROUND",    (0, 0), (-1, -1), WBG),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",         (1, 0), (1, 0), "CENTER"),
        ("ALIGN",         (2, 0), (2, 0), "RIGHT"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 3),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 3),
    ]))
    story.append(hdr)

    # ═══════════════════════════════════════════════════════════════
    # CHAVE DE ACESSO
    # ═══════════════════════════════════════════════════════════════
    story.append(mk([[lv("Chave de Acesso da NFS-e", data["chave_acesso"] or "-")]], [W]))

    # ═══════════════════════════════════════════════════════════════
    # IDs NFS-e / DPS
    # ═══════════════════════════════════════════════════════════════
    story.append(mk([
        [lv("Número da NFS-e",                data["n_nfse"]),
         lv("Competência da NFS-e",            _fmt_dt_date(data["d_compet"])),
         lv("Data e Hora da emissão da NFS-e", _fmt_dt(data["dh_emi"]))],
        [lv("Número da DPS",                  data["n_dps"]),
         lv("Série da DPS",                   data["serie"]),
         lv("Data e Hora da emissão da DPS",  _fmt_dt(data["dh_emi_dps"]))],
    ], cw3))

    # ═══════════════════════════════════════════════════════════════
    # EMITENTE DA NFS-e
    # ═══════════════════════════════════════════════════════════════
    story.append(mk([
        # linha cabeçalho cinza: título + CNPJ/IM/Tel
        [sec("EMITENTE DA NFS-e", "Prestador do Serviço"),
         lv("CNPJ / CPF / NIF",   _fmt_cnpj(data["emit_cnpj"])),
         lv("Inscrição Municipal", data["emit_im"]),
         lv("Telefone",           data["emit_fone"])],
        # Nome (span 3 cols) | E-mail
        [lv("Nome / Nome Empresarial", data["emit_nome"]), "", "",
         lv("E-mail", data["emit_email"])],
        # Endereço (span 2 cols) | Município | CEP
        [lv("Endereço", data["emit_end"]), "",
         lv("Município", data["emit_mun_uf"]),
         lv("CEP", _fmt_cep(data["emit_cep"]))],
        # Simples (span 2) | Regime (span 2)
        [lv("Simples Nacional na Data de Competência", _map_op_sn(data["op_sn"])), "",
         lv("Regime de Apuração Tributária pelo SN", _dash(data["reg_trib"])), ""],
    ], CWE, [
        ("BACKGROUND", (0, 0), (3, 0), SBG),
        ("SPAN",       (0, 1), (2, 1)),
        ("SPAN",       (0, 2), (1, 2)),
        ("SPAN",       (0, 3), (1, 3)),
        ("SPAN",       (2, 3), (3, 3)),
    ]))

    # ═══════════════════════════════════════════════════════════════
    # TOMADOR DO SERVIÇO
    # ═══════════════════════════════════════════════════════════════
    story.append(mk([
        [sec("TOMADOR DO SERVIÇO"),
         lv("CNPJ / CPF / NIF",   _fmt_cnpj(data["toma_doc"])),
         lv("Inscrição Municipal", data["toma_im"]),
         lv("Telefone",           data["toma_fone"])],
        [lv("Nome / Nome Empresarial", data["toma_nome"]), "", "",
         lv("E-mail", data["toma_email"])],
        [lv("Endereço", data["toma_end"]), "",
         lv("Município", data["toma_mun_uf"]),
         lv("CEP", _fmt_cep(data["toma_cep"]))],
    ], CWE, [
        ("BACKGROUND", (0, 0), (3, 0), SBG),
        ("SPAN",       (0, 1), (2, 1)),
        ("SPAN",       (0, 2), (1, 2)),
    ]))

    # Intermediário
    story.append(mk([[Paragraph(
        '<font name="Helvetica-Bold" size="6">'
        'INTERMEDIÁRIO DO SERVIÇO NÃO IDENTIFICADO NA NFS-e</font>',
        ps("interm", alignment=TA_CENTER, leading=8),
    )]], [W]))

    # ═══════════════════════════════════════════════════════════════
    # SERVIÇO PRESTADO
    # ═══════════════════════════════════════════════════════════════
    story.append(mk([
        [sec("SERVIÇO PRESTADO"), "", "", ""],
        [lv("Código de Tributação Nacional",  data["c_trib_nac"], fs=6),
         lv("Código de Tributação Municipal", data["c_trib_mun"]),
         lv("Local da Prestação",             data["x_mun_prest"]),
         lv("País da Prestação",              data["x_pais_prest"])],
        [lv("Descrição do Serviço", data["xdsc"]), "", "", ""],
    ], cw4, [
        ("BACKGROUND", (0, 0), (3, 0), SBG),
        ("SPAN",       (0, 0), (3, 0)),
        ("SPAN",       (0, 2), (3, 2)),
    ]))

    # ═══════════════════════════════════════════════════════════════
    # TRIBUTAÇÃO MUNICIPAL
    # ═══════════════════════════════════════════════════════════════
    story.append(mk([
        [sec("TRIBUTAÇÃO MUNICIPAL"), "", "", ""],
        [lv("Tributação do ISSQN",                    _map_tp_trib(data["tp_trib"])),
         lv("País Resultado da Prestação do Serviço", data["x_pais_res"]),
         lv("Município de Incidência do ISSQN",       data["x_mun_incid"]),
         lv("Regime Especial de Tributação",          data["reg_esp_trib"])],
        [lv("Tipo de Imunidade",                   data["tp_imun"]),
         lv("Suspensão da Exigibilidade do ISSQN", data["x_mot_sust"]),
         lv("Número Processo Suspensão",           data["n_proc_susp"]),
         lv("Benefício Municipal",                 data["c_benef"])],
        [lv("Valor do Serviço",        _fmt_moeda(data["v_serv_prest"])),
         lv("Desconto Incondicionado", _fmt_moeda(data["v_desc_incond"])),
         lv("Total Deduções/Reduções", _fmt_moeda(data["v_ded"])),
         lv("Cálculo do BM",           _fmt_moeda(data["v_calc_bm"]))],
        [lv("BC ISSQN",          _fmt_moeda(data["v_bc"])),
         lv("Alíquota Aplicada", _fmt_aliq(data["p_aliq"])),
         lv("Retenção do ISSQN", _map_ret_iss(data["tp_ret_iss"])),
         lv("ISSQN Apurado",     _fmt_moeda(data["v_issqn"]))],
    ], cw4, [
        ("BACKGROUND", (0, 0), (3, 0), SBG),
        ("SPAN",       (0, 0), (3, 0)),
    ]))

    # ═══════════════════════════════════════════════════════════════
    # TRIBUTAÇÃO FEDERAL
    # ═══════════════════════════════════════════════════════════════
    parts = []
    if data["v_ret_pis"]:    parts.append(f"PIS: {_fmt_moeda(data['v_ret_pis'])}")
    if data["v_ret_cofins"]: parts.append(f"COFINS: {_fmt_moeda(data['v_ret_cofins'])}")
    if data["v_ret_csll"]:   parts.append(f"CSLL: {_fmt_moeda(data['v_ret_csll'])}")
    desc_csll = " | ".join(parts) if parts else "-"

    story.append(mk([
        [sec("TRIBUTAÇÃO FEDERAL"), "", "", ""],
        [lv("IRRF",                                 _fmt_moeda(data["v_ret_irrf"])),
         lv("Contribuição Previdenciária - Retida", _fmt_moeda(data["v_ret_cp"])),
         lv("Contribuições Sociais - Retidas",      _fmt_moeda(data["v_ret_csll"])),
         lv("Descrição Contrib. Sociais - Retidas", desc_csll)],
        [lv("PIS - Débito Apuração Própria",    _fmt_moeda(data["v_pis_prop"])), "",
         lv("COFINS - Débito Apuração Própria", _fmt_moeda(data["v_cof_prop"])), ""],
    ], cw4, [
        ("BACKGROUND", (0, 0), (3, 0), SBG),
        ("SPAN",       (0, 0), (3, 0)),
        ("SPAN",       (0, 2), (1, 2)),
        ("SPAN",       (2, 2), (3, 2)),
    ]))

    # ═══════════════════════════════════════════════════════════════
    # VALOR TOTAL DA NFS-E
    # ═══════════════════════════════════════════════════════════════
    v_tot_ret = ""
    try:
        s = sum(float(data[k] or 0)
                for k in ("v_ret_irrf", "v_ret_cp", "v_ret_csll", "v_ret_pis", "v_ret_cofins"))
        v_tot_ret = str(s) if s > 0 else ""
    except (ValueError, TypeError):
        pass

    pis_cof = ""
    try:
        pc = float(data["v_pis_prop"] or 0) + float(data["v_cof_prop"] or 0)
        pis_cof = str(pc) if pc > 0 else ""
    except (ValueError, TypeError):
        pass

    val_liq_p = Paragraph(
        '<font name="Helvetica-Bold" size="5" color="#555555">VALOR LÍQUIDO DA NFS-E</font><br/>'
        f'<font name="Helvetica-Bold" size="8">{_fmt_moeda(data["v_liq"])}</font>',
        ps("vliq", leading=10),
    )

    story.append(mk([
        [sec("VALOR TOTAL DA NFS-E"), "", "", ""],
        [lv("Valor do Serviço",        _fmt_moeda(data["v_serv_total"])),
         lv("Desconto Condicionado",   _fmt_moeda(data["v_desc_cond"])),
         lv("Desconto Incondicionado", _fmt_moeda(data["v_desc_incond"])),
         lv("ISSQN Retido",            _fmt_moeda(data["v_ret_issqn"]))],
        [lv("Total das Retenções Federais",      _fmt_moeda(v_tot_ret)),
         lv("PIS/COFINS - Débito Apur. Própria", _fmt_moeda(pis_cof)),
         "", val_liq_p],
    ], cw4, [
        ("BACKGROUND", (0, 0), (3, 0), SBG),
        ("SPAN",       (0, 0), (3, 0)),
        ("SPAN",       (1, 2), (2, 2)),
    ]))

    # ═══════════════════════════════════════════════════════════════
    # TOTAIS APROXIMADOS DOS TRIBUTOS
    # ═══════════════════════════════════════════════════════════════
    story.append(mk([
        [sec("TOTAIS APROXIMADOS DOS TRIBUTOS"), "", ""],
        [lv("Federais",   _fmt_moeda(data["v_trib_fed"]), fs=8),
         lv("Estaduais",  _fmt_moeda(data["v_trib_est"]), fs=8),
         lv("Municipais", _fmt_moeda(data["v_trib_mun2"]), fs=8)],
    ], cw3, [
        ("BACKGROUND", (0, 0), (2, 0), SBG),
        ("SPAN",       (0, 0), (2, 0)),
        ("ALIGN",      (0, 1), (2, 1), "CENTER"),
    ]))

    # ═══════════════════════════════════════════════════════════════
    # INFORMAÇÕES COMPLEMENTARES
    # ═══════════════════════════════════════════════════════════════
    story.append(mk([
        [sec("INFORMAÇÕES COMPLEMENTARES")],
        [Paragraph(
            f'<font name="Helvetica" size="7">{_dash(data["inf_compl"])}</font>',
            ps("ic", leading=9, wordWrap="LTR"),
        )],
    ], [W], [
        ("BACKGROUND", (0, 0), (0, 0), SBG),
    ]))

    doc.build(story)
    return buf.getvalue()
