"""
core/conversor_pdf.py — DANFSe v1.0 a partir de XML NFSe nacional
Layout idêntico ao modelo nacional (padrão SPED/NFSe).
"""
from __future__ import annotations
import io
import xml.etree.ElementTree as ET
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.platypus.flowables import Flowable

try:
    import qrcode
    _QR_OK = True
except ImportError:
    _QR_OK = False

# ── Cores ──────────────────────────────────────────────────────────────────────
C_SEC  = colors.HexColor("#1F3864")   # cabeçalho de seção (azul escuro)
C_LBL  = colors.HexColor("#E8EEF4")   # fundo linha de rótulos (azul bem claro)
C_BRD  = colors.HexColor("#AAAAAA")   # bordas
C_WHT  = colors.white
C_BLK  = colors.black
C_GRN  = colors.HexColor("#00AA44")   # verde do "e" no logo

PAGE_W, PAGE_H = A4
M = 10 * mm   # margem
USABLE = PAGE_W - 2 * M


# ── Helpers XML ───────────────────────────────────────────────────────────────

def _t(el, *tags):
    """Busca texto de qualquer tag (sem namespace) dentro de el."""
    if el is None:
        return "-"
    for tag in tags:
        for e in el.iter():
            loc = e.tag.split("}")[-1] if "}" in e.tag else e.tag
            if loc == tag and e.text and e.text.strip():
                return e.text.strip()
    return "-"


def _fmt_cnpj(s):
    d = "".join(c for c in (s or "") if c.isdigit())
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if len(d) == 14 else (s or "-")


def _fmt_cep(s):
    d = "".join(c for c in (s or "") if c.isdigit())
    return f"{d[:5]}-{d[5:]}" if len(d) == 8 else (s or "-")


def _fmt_dt(s):
    if not s or s == "-":
        return "-"
    try:
        return datetime.strptime(s[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return s[:19]


def _fmt_dc(s):
    if not s or s == "-":
        return "-"
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return s


def _fmt_val(s):
    if not s or s == "-":
        return "-"
    try:
        return "R$ {:,.2f}".format(float(s)).replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return s


_MUN = {
    "2307601": "LIMOEIRO DO NORTE", "2304400": "FORTALEZA",
    "3550308": "SÃO PAULO", "3304557": "RIO DE JANEIRO",
    "5300108": "BRASÍLIA", "2304659": "JUAZEIRO DO NORTE",
}

def _mun(cod, uf=""):
    nome = _MUN.get(cod, cod or "-")
    return f"{nome.title()} - {uf}" if uf else nome


def _mun_upper(cod):
    return _MUN.get(cod, cod or "-")


def _simp(cod):
    return {
        "1": "Não optante", "2": "Não optante - Excluído",
        "3": "Optante - ME/EPP", "4": "Optante - MEI",
    }.get(cod, cod or "-")


def _reg_sn(cod):
    return {
        "1": "Regime de apuração dos tributos federais e municipal pelo Simples Nacional",
        "2": "Regime de apuração dos tributos federais pelo Simples Nacional e tributação municipal fora do Simples Nacional",
        "3": "Regime de apuração dos tributos municipais pelo Simples Nacional e tributação federal fora do Simples Nacional",
    }.get(cod, cod or "-")


def _ret_iss(cod):
    return {"1": "Não Retido", "2": "Retido", "3": "Retido pelo Intermediário"}.get(cod, cod or "-")


def _trib_iss(cod):
    return {
        "1": "Operação Tributável", "2": "Imune", "3": "Isenta",
        "4": "Exportação", "5": "Não Incidência",
        "6": "Suspensa - Decisão Judicial", "7": "Suspensa - Processo Adm.",
    }.get(cod, cod or "-")


def _cod_nac(s):
    d = "".join(c for c in (s or "") if c.isdigit())
    return f"{d[:2]}.{d[2:4]}.{d[4:]}" if len(d) == 6 else (s or "-")


# ── Parse XML ─────────────────────────────────────────────────────────────────

def _parse(xml_bytes: bytes) -> dict:
    root = ET.fromstring(xml_bytes)

    # chave de acesso
    chave = "-"
    for el in root.iter():
        if el.tag.split("}")[-1] == "infNFSe":
            id_ = el.get("Id", "")
            chave = id_[3:] if id_.startswith("NFS") else id_
            break

    # emitente (nível NFSe)
    emit = next((e for e in root.iter() if e.tag.split("}")[-1] == "emit"), root)
    ender_e = next((e for e in emit.iter() if e.tag.split("}")[-1] in ("enderNac","enderExt")), None)
    cMun_e = _t(ender_e, "cMun"); uf_e = _t(ender_e, "UF")

    # DPS
    dps = next((e for e in root.iter() if e.tag.split("}")[-1] == "DPS"), root)

    # regTrib
    reg = next((e for e in root.iter() if e.tag.split("}")[-1] == "regTrib"), None)

    # tomador
    toma = next((e for e in root.iter() if e.tag.split("}")[-1] == "toma"), None)
    toma_ender_nac = next((e for e in (toma or root).iter() if e.tag.split("}")[-1] in ("endNac","enderNac")), None)
    cMun_t = _t(toma_ender_nac, "cMun"); uf_t = _t(toma_ender_nac, "UF")
    # UF do tomador pode estar em nível toma direto
    if uf_t == "-":
        uf_t = _t(toma, "UF") if toma is not None else "-"
    toma_xLgr   = _t(toma, "xLgr")
    toma_nro    = _t(toma, "nro")
    toma_xCpl   = _t(toma, "xCpl")
    toma_bairro = _t(toma, "xBairro")
    partes_t = [p for p in [toma_xLgr, toma_nro, toma_xCpl, toma_bairro] if p != "-"]
    toma_end = ", ".join(partes_t) if partes_t else "-"

    # serviço
    serv  = next((e for e in root.iter() if e.tag.split("}")[-1] == "serv"), None)
    cServ = next((e for e in (serv or root).iter() if e.tag.split("}")[-1] == "cServ"), None)
    locPrest = next((e for e in (serv or root).iter() if e.tag.split("}")[-1] == "locPrest"), None)
    cLocPrest = _t(locPrest, "cLocPrestacao")

    # tributação
    trib    = next((e for e in root.iter() if e.tag.split("}")[-1] == "trib"), None)
    tribMun = next((e for e in (trib or root).iter() if e.tag.split("}")[-1] == "tribMun"), None)
    totTrib = next((e for e in (trib or root).iter() if e.tag.split("}")[-1] == "totTrib"), None)

    # valores nível NFSe (vBC, pAliqAplic, vISSQN, vLiq)
    vals_nfse = next(
        (e for e in root.iter()
         if e.tag.split("}")[-1] == "valores"
         and any(c.tag.split("}")[-1] in ("vBC", "vLiq") for c in e)),
        None
    )
    # valores nível DPS (vServ dentro de vServPrest)
    vals_dps  = next(
        (e for e in (dps or root).iter()
         if e.tag.split("}")[-1] == "valores"
         and any(c.tag.split("}")[-1] == "vServPrest" for c in e)),
        None
    )
    vServPrest = next((e for e in (vals_dps or root).iter() if e.tag.split("}")[-1] == "vServPrest"), None)
    vServ_raw  = _t(vServPrest, "vServ")
    vBC_raw    = _t(vals_nfse, "vBC") if vals_nfse else vServ_raw
    vISSQN_raw = _t(vals_nfse, "vISSQN") if vals_nfse else "-"
    vLiq_raw   = _t(vals_nfse, "vLiq") if vals_nfse else vServ_raw

    pAliq_raw = _t(tribMun, "pAliq") if tribMun else _t(vals_nfse, "pAliqAplic")
    try:
        pAliq_fmt = f"{float(pAliq_raw):.2f}%"
    except Exception:
        pAliq_fmt = pAliq_raw or "-"

    cTribNac_raw  = _t(cServ, "cTribNac")
    xTribNac_desc = _t(root, "xTribNac")
    cTribNac_fmt  = _cod_nac(cTribNac_raw)
    cod_nac_label = f"{cTribNac_fmt} - {xTribNac_desc}" if xTribNac_desc != "-" else cTribNac_fmt

    xLocEmi = _t(root, "xLocEmi")
    uf_emit  = uf_e if uf_e != "-" else "CE"

    # endereço emitente
    xLgr_e = _t(ender_e, "xLgr"); nro_e = _t(ender_e, "nro")
    xCpl_e = _t(ender_e, "xCpl"); bairro_e = _t(ender_e, "xBairro")
    partes_e = [p for p in [xLgr_e, nro_e, xCpl_e, bairro_e] if p != "-"]
    emit_end = ", ".join(partes_e) if partes_e else "-"

    indTotTrib = _t(totTrib, "indTotTrib") if totTrib else "0"

    return {
        "chave":       chave,
        "nNFSe":       _t(root, "nNFSe"),
        "competencia": _fmt_dc(_t(dps, "dCompet")),
        "dhProc":      _fmt_dt(_t(root, "dhProc")),
        "nDPS":        _t(root, "nDPS", "nDFSe"),
        "serie":       _t(dps, "serie"),
        "dhEmi":       _fmt_dt(_t(dps, "dhEmi")),
        # emitente
        "emit_cnpj":   _fmt_cnpj(_t(emit, "CNPJ", "CPF")),
        "emit_im":     _t(emit, "IM"),
        "emit_nome":   _t(emit, "xNome"),
        "emit_email":  _t(emit, "email"),
        "emit_fone":   _t(emit, "fone"),
        "emit_end":    emit_end,
        "emit_mun":    _mun(cMun_e, uf_e),
        "emit_cep":    _fmt_cep(_t(ender_e, "CEP")),
        "opSimpNac":   _simp(_t(reg, "opSimpNac")),
        "regApTribSN": _reg_sn(_t(reg, "regApTribSN")),
        # tomador
        "toma_cnpj":   _fmt_cnpj(_t(toma, "CNPJ", "CPF")),
        "toma_im":     _t(toma, "IM"),
        "toma_nome":   _t(toma, "xNome"),
        "toma_email":  _t(toma, "email"),
        "toma_fone":   _t(toma, "fone"),
        "toma_end":    toma_end,
        "toma_mun":    _mun(cMun_t, uf_t),
        "toma_cep":    _fmt_cep(_t(toma_ender_nac, "CEP")),
        # serviço
        "cod_nac":     cod_nac_label,
        "cod_mun":     _t(root, "xTribMun"),
        "loc_prest":   _mun_upper(cLocPrest) if cLocPrest != "-" else _t(root, "xLocPrestacao"),
        "pais_prest":  _t(root, "xPaisPrestacao"),
        "desc_serv":   _t(cServ, "xDescServ"),
        "cNBS":        _t(cServ, "cNBS"),
        # trib mun
        "tribISSQN":   _trib_iss(_t(tribMun, "tribISSQN")),
        "paisResult":  _t(tribMun, "cPaisResult"),
        "munIncid":    _mun_upper(cLocPrest) if cLocPrest != "-" else _t(root, "xLocIncid"),
        "regEsp":      _t(tribMun, "regEspTrib") or "0",
        "tipoImun":    _t(tribMun, "tpImunidade"),
        "suspExig":    "Não",
        "numProc":     _t(root, "nProcesso"),
        "benMun":      _t(root, "xBenMun"),
        "vServ":       _fmt_val(vServ_raw),
        "descIncond":  _fmt_val(_t(vals_dps or root, "vDescIncond")),
        "totDed":      _fmt_val(_t(vals_dps or root, "vDedRed")),
        "calcBM":      _fmt_val(_t(vals_dps or root, "vCalcBM")),
        "vBC":         _fmt_val(vBC_raw),
        "pAliq":       pAliq_fmt,
        "retISSQN":    _ret_iss(_t(tribMun, "tpRetISSQN")),
        "vISSQN":      _fmt_val(vISSQN_raw),
        # trib fed
        "irrf":        _fmt_val(_t(root, "vIRRF")),
        "contPrev":    _fmt_val(_t(root, "vCP")),
        "contSoc":     _fmt_val(_t(root, "vCSLL")),
        "descCont":    _t(root, "xContribSoc"),
        "pis":         _fmt_val(_t(root, "vPIS")),
        "cofins":      _fmt_val(_t(root, "vCOFINS")),
        # valor total
        "vServT":      _fmt_val(vServ_raw),
        "descCond":    _fmt_val(_t(root, "vDescCond")),
        "descIncondT": _fmt_val(_t(root, "vDescIncond")),
        "issqnRet":    _fmt_val(_t(root, "vISSRet")),
        "totRetFed":   _fmt_val(_t(root, "vTotRet")),
        "pisCofins":   "-",
        "vLiq":        _fmt_val(vLiq_raw),
        # tributos aproximados
        "tbFed": "-" if indTotTrib == "0" else _fmt_val(_t(root, "vTotFed")),
        "tbEst": "-" if indTotTrib == "0" else _fmt_val(_t(root, "vTotEst")),
        "tbMun": "-" if indTotTrib == "0" else _fmt_val(_t(root, "vTotMun")),
        # info complementar
        "infoComp":  f"NBS: {_t(cServ, 'cNBS')}" if _t(cServ, "cNBS") != "-" else "-",
        "xLocEmi":   xLocEmi,
        "uf_emit":   uf_emit,
    }


# ── Estilos ───────────────────────────────────────────────────────────────────

def _ps(name, **kw):
    defaults = dict(fontName="Helvetica", fontSize=7, leading=8.5, textColor=C_BLK)
    defaults.update(kw)
    return ParagraphStyle(name, **defaults)


S_LBL  = _ps("lbl",  fontSize=6,   leading=7.5, textColor=colors.HexColor("#444444"))
S_VAL  = _ps("val",  fontSize=7,   leading=8.5)
S_VAL_B= _ps("valb", fontSize=8.5, leading=10,  fontName="Helvetica-Bold")
S_SEC  = _ps("sec",  fontSize=7.5, leading=9,   fontName="Helvetica-Bold", textColor=C_WHT)
S_TTL  = _ps("ttl",  fontSize=13,  leading=16,  fontName="Helvetica-Bold", alignment=TA_CENTER)
S_SUB  = _ps("sub",  fontSize=8.5, leading=10,  alignment=TA_CENTER)
S_PRF  = _ps("prf",  fontSize=7,   leading=9,   fontName="Helvetica-Bold", alignment=TA_RIGHT)
S_NOTE = _ps("note", fontSize=5.5, leading=7,   textColor=colors.HexColor("#555555"), alignment=TA_RIGHT)
S_INTER= _ps("int",  fontSize=7,   leading=9,   fontName="Helvetica-Bold", alignment=TA_CENTER)


# ── Logo NFS-e vetorial ───────────────────────────────────────────────────────

class NfseLogo(Flowable):
    W = 46 * mm
    H = 13 * mm

    def __init__(self):
        super().__init__()
        self.width  = self.W
        self.height = self.H

    def draw(self):
        c = self.canv
        bw = self.W * 0.42   # largura do bloco escuro
        # fundo azul escuro
        c.setFillColor(C_SEC)
        c.rect(0, 0, bw, self.H, fill=1, stroke=0)
        # "NFS" branco
        c.setFillColor(C_WHT)
        c.setFont("Helvetica-Bold", 15)
        c.drawString(1.5 * mm, self.H * 0.28, "NFS")
        # círculo verde com "e"
        cx = bw - 4 * mm
        cy = self.H * 0.55
        r  = 3.8 * mm
        c.setFillColor(C_GRN)
        c.circle(cx, cy, r, fill=1, stroke=0)
        c.setFillColor(C_WHT)
        c.setFont("Helvetica-BoldOblique", 9)
        c.drawCentredString(cx, cy - 3, "e")
        # textos laterais
        c.setFillColor(C_BLK)
        c.setFont("Helvetica", 5)
        tx = bw + 1.5 * mm
        c.drawString(tx, self.H * 0.72, "Nota Fiscal de")
        c.drawString(tx, self.H * 0.50, "Serviço")
        c.drawString(tx, self.H * 0.28, "Eletrônica")


# ── Helpers de tabela ──────────────────────────────────────────────────────────

_STD = TableStyle([
    ("FONTNAME",      (0,0), (-1,-1), "Helvetica"),
    ("FONTSIZE",      (0,0), (-1,-1), 7),
    ("TOPPADDING",    (0,0), (-1,-1), 1.5),
    ("BOTTOMPADDING", (0,0), (-1,-1), 1.5),
    ("LEFTPADDING",   (0,0), (-1,-1), 2.5),
    ("RIGHTPADDING",  (0,0), (-1,-1), 2),
    ("VALIGN",        (0,0), (-1,-1), "TOP"),
    ("BOX",           (0,0), (-1,-1), 0.3, C_BRD),
    ("INNERGRID",     (0,0), (-1,-1), 0.3, C_BRD),
])


def _sec_bar(label: str) -> Table:
    t = Table([[Paragraph(f"<b>{label}</b>", S_SEC)]], colWidths=[USABLE])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), C_SEC),
        ("TOPPADDING",    (0,0), (-1,-1), 2.5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2.5),
        ("LEFTPADDING",   (0,0), (-1,-1), 3),
        ("BOX",           (0,0), (-1,-1), 0.3, C_BRD),
    ]))
    return t


def _grid(cols_data: list[tuple[str,str]], widths: list[float],
          bold_last=False) -> Table:
    """
    cols_data: [(label, value), ...]
    Gera 2 linhas: linha de rótulos (fundo C_LBL) + linha de valores.
    """
    lbl_row = [Paragraph(l, S_LBL) for l, _ in cols_data]
    val_row = []
    for i, (_, v) in enumerate(cols_data):
        s = S_VAL_B if (bold_last and i == len(cols_data)-1) else S_VAL
        val_row.append(Paragraph(v, s))

    t = Table([lbl_row, val_row], colWidths=widths)
    style = TableStyle(list(_STD.getCommands()) + [
        ("BACKGROUND", (0,0), (-1,0), C_LBL),
        ("BACKGROUND", (0,1), (-1,1), C_WHT),
    ])
    t.setStyle(style)
    return t


def _qr_image(chave: str, size_mm: float = 25):
    if not _QR_OK or not chave or chave == "-":
        return None
    try:
        qr = qrcode.QRCode(box_size=6, border=2,
                           error_correction=qrcode.constants.ERROR_CORRECT_M)
        qr.add_data(chave)
        qr.make(fit=True)
        img_pil = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img_pil.save(buf, format="PNG")
        buf.seek(0)
        from reportlab.platypus import Image as RLImage
        return RLImage(buf, width=size_mm * mm, height=size_mm * mm)
    except Exception:
        return None


# ── Geração do PDF ────────────────────────────────────────────────────────────

def gerar_danfse(xml_bytes: bytes) -> bytes:
    d = _parse(xml_bytes)
    buf = io.BytesIO()

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=M, rightMargin=M,
        topMargin=M,  bottomMargin=M,
        title=f"DANFSe - NFS-e {d['nNFSe']}",
    )

    story = []
    W = USABLE

    # ── 1. CABEÇALHO ─────────────────────────────────────────────────────────
    # [Logo | Título | Prefeitura]
    pref_txt = (f"PREFEITURA MUNICIPAL DE<br/>"
                f"<b>{d['xLocEmi'].upper()}</b><br/>{d['uf_emit']}")
    hdr = Table(
        [[NfseLogo(),
          [Paragraph("DANFSe v1.0", S_TTL),
           Paragraph("Documento Auxiliar da NFS-e", S_SUB)],
          Paragraph(pref_txt, S_PRF)]],
        colWidths=[46*mm, W - 46*mm - 38*mm, 38*mm],
    )
    hdr.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN",         (2,0), (2,0),   "RIGHT"),
        ("BOX",           (0,0), (-1,-1), 0.5, C_BRD),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (-1,-1), 3),
        ("RIGHTPADDING",  (0,0), (-1,-1), 3),
    ]))
    story.append(hdr)

    # ── 2. CHAVE DE ACESSO + QR ───────────────────────────────────────────────
    qr = _qr_image(d["chave"])
    qr_col_w = 28 * mm
    chave_w  = W - qr_col_w

    note_p = Paragraph(
        "A autenticidade desta NFS-e pode ser<br/>"
        "verificada pela leitura deste código QR ou<br/>"
        "pela consulta da chave de acesso no portal",
        S_NOTE,
    )

    # Coluna direita: nota + QR juntos em célula única (SPAN das 2 linhas)
    # Colocamos [note_p, qr] como lista na célula (1,0); (1,1) fica vazia pelo SPAN.
    right_cell = [note_p, qr] if qr else note_p

    chave_table = Table(
        [
            [Paragraph("<b>Chave de Acesso da NFS-e</b>", S_LBL), right_cell],
            [Paragraph(d["chave"], S_VAL),                         ""],
        ],
        colWidths=[chave_w, qr_col_w],
    )
    chave_table.setStyle(TableStyle([
        ("SPAN",          (1,0), (1,1)),          # coluna direita: célula única
        ("VALIGN",        (0,0), (0,-1), "MIDDLE"),
        ("VALIGN",        (1,0), (1,0),  "MIDDLE"),
        ("ALIGN",         (1,0), (1,0),  "CENTER"),
        ("BOX",           (0,0), (-1,-1), 0.3, C_BRD),
        ("INNERGRID",     (0,0), (-1,-1), 0.3, C_BRD),
        ("BACKGROUND",    (0,0), (0,0),  C_LBL),   # só a célula do label: azul claro
        ("BACKGROUND",    (0,1), (0,1),  C_WHT),   # célula do valor: branco
        ("BACKGROUND",    (1,0), (1,0),  C_WHT),   # coluna direita: branco
        ("TOPPADDING",    (0,0), (-1,-1), 1.5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 1.5),
        ("LEFTPADDING",   (0,0), (-1,-1), 2.5),
        ("RIGHTPADDING",  (0,0), (-1,-1), 2),
    ]))
    story.append(chave_table)

    # ── 3. NÚMEROS NFS-e e DPS ────────────────────────────────────────────────
    w4 = W / 4
    story.append(_grid([
        ("Número da NFS-e",              d["nNFSe"]),
        ("Competência da NFS-e",         d["competencia"]),
        ("Data e Hora da emissão da NFS-e", d["dhProc"]),
        ("",                             ""),
    ], [w4]*4))
    story.append(_grid([
        ("Número da DPS",               d["nDPS"]),
        ("Série da DPS",                d["serie"]),
        ("Data e Hora da emissão da DPS", d["dhEmi"]),
        ("",                            ""),
    ], [w4]*4))

    # ── 4. EMITENTE ───────────────────────────────────────────────────────────
    story.append(_sec_bar("EMITENTE DA NFS-e"))
    story.append(_grid([
        ("Prestador do Serviço", ""),
        ("CNPJ / CPF / NIF",    d["emit_cnpj"]),
        ("Inscrição Municipal",  d["emit_im"]),
        ("Telefone",             d["emit_fone"]),
    ], [W*0.22, W*0.30, W*0.28, W*0.20]))
    story.append(_grid([
        ("Nome / Nome Empresarial", d["emit_nome"]),
        ("E-mail",                  d["emit_email"]),
    ], [W*0.65, W*0.35]))
    story.append(_grid([
        ("Endereço",  d["emit_end"]),
        ("Município", d["emit_mun"]),
        ("CEP",       d["emit_cep"]),
    ], [W*0.55, W*0.30, W*0.15]))
    story.append(_grid([
        ("Simples Nacional na Data de Competência", d["opSimpNac"]),
        ("Regime de Apuração Tributária pelo SN",   d["regApTribSN"]),
    ], [W*0.38, W*0.62]))

    # ── 5. TOMADOR ────────────────────────────────────────────────────────────
    story.append(_sec_bar("TOMADOR DO SERVIÇO"))
    story.append(_grid([
        ("",                    ""),
        ("CNPJ / CPF / NIF",   d["toma_cnpj"]),
        ("Inscrição Municipal", d["toma_im"]),
        ("Telefone",            d["toma_fone"]),
    ], [W*0.22, W*0.30, W*0.28, W*0.20]))
    story.append(_grid([
        ("Nome / Nome Empresarial", d["toma_nome"]),
        ("E-mail",                  d["toma_email"]),
    ], [W*0.65, W*0.35]))
    story.append(_grid([
        ("Endereço",  d["toma_end"]),
        ("Município", d["toma_mun"]),
        ("CEP",       d["toma_cep"]),
    ], [W*0.55, W*0.30, W*0.15]))

    # ── 6. INTERMEDIÁRIO ──────────────────────────────────────────────────────
    t = Table([[Paragraph("INTERMEDIÁRIO DO SERVIÇO NÃO IDENTIFICADO NA NFS-e", S_INTER)]],
              colWidths=[W])
    t.setStyle(TableStyle([
        ("BOX",           (0,0),(-1,-1), 0.3, C_BRD),
        ("TOPPADDING",    (0,0),(-1,-1), 2.5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 2.5),
    ]))
    story.append(t)

    # ── 7. SERVIÇO PRESTADO ───────────────────────────────────────────────────
    story.append(_sec_bar("SERVIÇO PRESTADO"))
    story.append(_grid([
        ("Código de Tributação Nacional", d["cod_nac"]),
        ("Código de Tributação Municipal", d["cod_mun"]),
        ("Local da Prestação",            d["loc_prest"]),
        ("País da Prestação",             d["pais_prest"]),
    ], [W*0.33, W*0.27, W*0.25, W*0.15]))
    story.append(_grid([
        ("Descrição do Serviço", d["desc_serv"]),
    ], [W]))

    # ── 8. TRIBUTAÇÃO MUNICIPAL ───────────────────────────────────────────────
    story.append(_sec_bar("TRIBUTAÇÃO MUNICIPAL"))
    story.append(_grid([
        ("Tributação do ISSQN",                    d["tribISSQN"]),
        ("País Resultado da Prestação do Serviço", d["paisResult"]),
        ("Município de Incidência do ISSQN",       d["munIncid"]),
        ("Regime Especial de Tributação",          d["regEsp"]),
    ], [w4]*4))
    story.append(_grid([
        ("Tipo de Imunidade",                   d["tipoImun"]),
        ("Suspensão da Exigibilidade do ISSQN", d["suspExig"]),
        ("Número Processo Suspensão",           d["numProc"]),
        ("Benefício Municipal",                 d["benMun"]),
    ], [w4]*4))
    story.append(_grid([
        ("Valor do Serviço",        d["vServ"]),
        ("Desconto Incondicionado", d["descIncond"]),
        ("Total Deduções/Reduções", d["totDed"]),
        ("Cálculo do BM",           d["calcBM"]),
    ], [w4]*4))
    story.append(_grid([
        ("BC ISSQN",        d["vBC"]),
        ("Alíquota Aplicada", d["pAliq"]),
        ("Retenção do ISSQN", d["retISSQN"]),
        ("ISSQN Apurado",    d["vISSQN"]),
    ], [w4]*4))

    # ── 9. TRIBUTAÇÃO FEDERAL ─────────────────────────────────────────────────
    story.append(_sec_bar("TRIBUTAÇÃO FEDERAL"))
    story.append(_grid([
        ("IRRF",                              d["irrf"]),
        ("Contribuição Previdenciária - Retida", d["contPrev"]),
        ("Contribuições Sociais - Retidas",   d["contSoc"]),
        ("Descrição Contrib. Sociais - Retidas", d["descCont"]),
    ], [w4]*4))
    story.append(_grid([
        ("PIS - Débito Apuração Própria",    d["pis"]),
        ("COFINS - Débito Apuração Própria", d["cofins"]),
    ], [W/2, W/2]))

    # ── 10. VALOR TOTAL ───────────────────────────────────────────────────────
    story.append(_sec_bar("VALOR TOTAL DA NFS-E"))
    story.append(_grid([
        ("Valor do Serviço",       d["vServT"]),
        ("Desconto Condicionado",  d["descCond"]),
        ("Desconto Incondicionado",d["descIncondT"]),
        ("ISSQN Retido",           d["issqnRet"]),
    ], [w4]*4))
    story.append(_grid([
        ("Total das Retenções Federais",     d["totRetFed"]),
        ("PIS/COFINS - Débito Apur. Própria",d["pisCofins"]),
        ("",                                 ""),
        ("Valor Líquido da NFS-e",           d["vLiq"]),
    ], [w4]*4, bold_last=True))

    # ── 11. TOTAIS APROXIMADOS ────────────────────────────────────────────────
    story.append(_sec_bar("TOTAIS APROXIMADOS DOS TRIBUTOS"))
    story.append(_grid([
        ("Federais",  d["tbFed"]),
        ("Estaduais", d["tbEst"]),
        ("Municipais",d["tbMun"]),
    ], [W/3, W/3, W/3]))

    # ── 12. INFORMAÇÕES COMPLEMENTARES ───────────────────────────────────────
    story.append(_sec_bar("INFORMAÇÕES COMPLEMENTARES"))
    info = Table([[Paragraph(d["infoComp"], S_VAL)]], colWidths=[W])
    info.setStyle(TableStyle([
        ("BOX",           (0,0),(-1,-1), 0.3, C_BRD),
        ("TOPPADDING",    (0,0),(-1,-1), 3),
        ("BOTTOMPADDING", (0,0),(-1,-1), 3),
        ("LEFTPADDING",   (0,0),(-1,-1), 3),
    ]))
    story.append(info)

    doc.build(story)
    return buf.getvalue()


def gerar_pdf_bytes(xml_bytes: bytes) -> bytes:
    return gerar_danfse(xml_bytes)
