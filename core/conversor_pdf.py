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
from pathlib import Path

from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image,
)
from reportlab.platypus.flowables import Flowable

try:
    import qrcode
    _QR_OK = True
except ImportError:
    _QR_OK = False

from core.ibge_municipios import municipio as _municipio_ibge

# ── Cores ──────────────────────────────────────────────────────────────────────
# O DANFSe oficial é monocromático: cinzas e preto, cor só no logo.
C_SEC  = colors.HexColor("#D9D9D9")   # célula do título de seção (cinza)
C_LBL  = colors.white                 # linha de rótulos — sem fundo no modelo oficial
C_BRD  = colors.HexColor("#AAAAAA")   # bordas
C_WHT  = colors.white
C_BLK  = colors.black
C_GRN  = colors.HexColor("#00AA44")   # verde do "e" no logo

PAGE_W, PAGE_H = A4
M = 7 * mm    # margem — apertada para o DANFSe caber em 1 página, como manda o modelo
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
    """"Município / Sigla UF" — a UF do XML tem prioridade sobre a da tabela."""
    nome, uf_tab = _municipio_ibge(cod)
    sigla = uf if uf and uf != "-" else uf_tab
    return f"{nome} / {sigla}" if sigla else (nome or "-")


def _mun_upper(cod):
    nome, uf = _municipio_ibge(cod)
    return f"{nome.upper()} / {uf}" if uf else (nome.upper() if nome else "-")


def _fmt_fone(s):
    """(85) 99637-7390 — o XML entrega só dígitos."""
    d = "".join(c for c in (s or "") if c.isdigit())
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return s or "-"


def _simp(cod):
    """Texto por extenso, como no DANFSe oficial."""
    return {
        "1": "Não optante",
        "2": "Não optante - Excluído",
        "3": "Optante - Microempresa ou Empresa de Pequeno Porte",
        "4": "Optante - Microempreendedor Individual",
    }.get(cod, cod or "-")


def _reg_sn(cod):
    """Texto por extenso, como no DANFSe oficial."""
    return {
        "1": "Regime de apuração dos tributos federais e municipal pelo Simples Nacional",
        "2": "Regime de apuração dos tributos federais pelo Simples Nacional e o ISSQN "
             "pela tributação municipal fora do Simples Nacional",
        "3": "Regime de apuração dos tributos federais fora do Simples Nacional e o ISSQN "
             "pelo Simples Nacional",
    }.get(cod, cod or "-")


def _amb_ger(cod):
    """Ambiente gerador da NFS-e (cabeçalho do DANFSe)."""
    return {
        "1": "Sistema Próprio do Município",
        "2": "Sistema Nacional da NFS-e",
    }.get(cod, cod or "-")


def _tp_amb(cod):
    return {"1": "Produção", "2": "Homologação"}.get(cod, cod or "-")


def _tp_emit(cod):
    """Quem emitiu a NFS-e."""
    return {
        "1": "Prestador",
        "2": "Tomador",
        "3": "Intermediário",
    }.get(cod, cod or "-")


def _situacao(cstat, cancelada):
    """Situação da NFS-e, na redação do DANFSe oficial."""
    if cancelada or cstat in ("101", "108"):
        return "NFS-e Cancelada"
    if cstat in ("100", "107"):
        return "NFS-e Gerada"
    return "-"


def _reg_esp(cod):
    """Regime Especial de Tributação do ISSQN. 0 (ou ausente) = Nenhum."""
    return {
        "0": "Nenhum",
        "1": "Ato Cooperado",
        "2": "Estimativa",
        "3": "Microempresa Municipal",
        "4": "Notário ou Registrador",
        "5": "Profissional Autônomo",
        "6": "Sociedade de Profissionais",
    }.get(_norm_cod(cod) or "0", cod or "Nenhum")


def _norm_cod(cod):
    """'-' e vazio significam ausente; _t devolve '-' quando a tag não existe."""
    c = (cod or "").strip()
    return "" if c == "-" else c


def _ret_iss(cod):
    return {"1": "Não Retido", "2": "Retido", "3": "Retido pelo Intermediário"}.get(cod, cod or "-")


def _trib_iss(cod):
    return {
        "1": "Operação Tributável", "2": "Imune", "3": "Isenta",
        "4": "Exportação", "5": "Não Incidência",
        "6": "Suspensa - Decisão Judicial", "7": "Suspensa - Processo Adm.",
    }.get(cod, cod or "-")


def _fmt_ibge_cep(cod_mun, cep):
    """"23.04400 / 60.165-078" — pontuação do DANFSe oficial."""
    d = "".join(c for c in (cod_mun or "") if c.isdigit())
    ibge = f"{d[:2]}.{d[2:]}" if len(d) == 7 else (d or "-")
    c = "".join(ch for ch in (cep or "") if ch.isdigit())
    cep_fmt = f"{c[:2]}.{c[2:5]}-{c[5:]}" if len(c) == 8 else (cep or "-")
    return f"{ibge} / {cep_fmt}"


def _fmt_nbs(s):
    """Código NBS: 114061100 -> 1.1406.11.00"""
    d = "".join(c for c in (s or "") if c.isdigit())
    return f"{d[0]}.{d[1:5]}.{d[5:7]}.{d[7:]}" if len(d) == 9 else (s or "-")


def _corta(texto: str, limite: int) -> str:
    """Trunca preservando a última palavra inteira e sinalizando o corte."""
    if not texto or len(texto) <= limite:
        return texto or "-"
    corte = texto[:limite].rsplit(" ", 1)[0].rstrip(" ,;.-")
    return corte + " […]"


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

    # A alíquota pode estar em <tribMun><pAliq> ou em <valores><pAliqAplic>;
    # tentar só a primeira deixava o campo vazio na maioria das notas.
    pAliq_raw = "-"
    for _origem, _tag in ((tribMun, "pAliq"), (vals_nfse, "pAliqAplic"), (root, "pAliqAplic")):
        _v = _t(_origem, _tag) if _origem is not None else "-"
        if _v not in ("-", ""):
            pAliq_raw = _v
            break
    try:
        # Formato brasileiro, como no DANFSe oficial: "2,17 %"
        pAliq_fmt = f"{float(pAliq_raw):.2f}".replace(".", ",") + " %"
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

    # ── Cabeçalho v2.0: ambiente, emitente, situação ─────────────────────────
    cancelada = any(e.tag.split("}")[-1] == "nfseCanc" for e in root.iter())
    cstat = _t(root, "cStat")
    if cstat == "-":
        cstat = ""

    # ── IBS/CBS ──────────────────────────────────────────────────────────────
    # Bloco da reforma tributária. Ausente nos XMLs antigos — a NT-008 manda
    # imprimir o bloco mesmo assim, com traço nos campos sem informação.
    ibscbs = next((e for e in root.iter() if e.tag.split("}")[-1] == "IBSCBS"), None)
    gibscbs = next((e for e in root.iter() if e.tag.split("}")[-1] == "gIBSCBS"), None)
    tot_cibs = next((e for e in root.iter() if e.tag.split("}")[-1] == "totCIBS"), None)
    uf_ibs = next((e for e in (ibscbs or root).iter() if e.tag.split("}")[-1] == "uf"), None)
    mun_ibs = next((e for e in (ibscbs or root).iter() if e.tag.split("}")[-1] == "mun"), None)
    fed_ibs = next((e for e in (ibscbs or root).iter() if e.tag.split("}")[-1] == "fed"), None)

    def _pct(el, tag):
        v = _t(el, tag) if el is not None else "-"
        try:
            return f"{float(v):.2f}%"
        except Exception:
            return "-"

    vIBSTot = _t(tot_cibs, "vIBSTot") if tot_cibs is not None else "-"
    vCBSTot = _t(tot_cibs, "vCBS") if tot_cibs is not None else "-"
    total_ibscbs = "-"
    try:
        total_ibscbs = _fmt_val(str(float(vIBSTot) + float(vCBSTot)))
    except Exception:
        pass
    liq_mais_ibscbs = "-"
    try:
        liq_mais_ibscbs = _fmt_val(str(float(vLiq_raw) + float(vIBSTot) + float(vCBSTot)))
    except Exception:
        pass

    return {
        # cabeçalho v2.0
        "ambGer":     _amb_ger(_t(root, "ambGer")),
        "tpAmb":      _tp_amb(_t(root, "tpAmb")),
        "tpEmit":     _tp_emit(_t(root, "tpEmit")),
        "situacao":   _situacao(cstat, cancelada),
        "cancelada":  cancelada or cstat in ("101", "108"),
        "finalidade": "NFS-e",
        # IBS/CBS
        "ibs_cst":        _t(gibscbs, "CST"),
        "ibs_classtrib":  _t(gibscbs, "cClassTrib"),
        "ibs_indop":      _t(root, "cIndOp"),
        "ibs_mun_incid":  _t(ibscbs, "xLocalidadeIncid"),
        "ibs_cod_incid":  _t(ibscbs, "cLocalidadeIncid"),
        "ibs_exclusoes":  _fmt_val(_t(ibscbs, "vCalcReeRepRes")) if ibscbs is not None else "-",
        "ibs_bc":         _fmt_val(_t(ibscbs, "vBC")) if ibscbs is not None else "-",
        "ibs_aliq_uf":    _pct(uf_ibs, "pIBSUF"),
        "ibs_aliq_mun":   _pct(mun_ibs, "pIBSMun"),
        "ibs_efet_uf":    _pct(uf_ibs, "pAliqEfetUF"),
        "ibs_efet_mun":   _pct(mun_ibs, "pAliqEfetMun"),
        "ibs_val_uf":     _fmt_val(_t(root, "vIBSUF")),
        "ibs_val_mun":    _fmt_val(_t(root, "vIBSMun")),
        "ibs_val_tot":    _fmt_val(vIBSTot),
        "cbs_aliq":       _pct(fed_ibs, "pCBS"),
        "cbs_efet":       _pct(fed_ibs, "pAliqEfetCBS"),
        "cbs_val_tot":    _fmt_val(vCBSTot),
        "total_ibscbs":   total_ibscbs,
        "liq_mais_ibscbs": liq_mais_ibscbs,
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
        "emit_fone":   _fmt_fone(_t(emit, "fone")),
        "emit_end":    emit_end,
        "emit_mun":    _mun(cMun_e, uf_e),
        "emit_cep":    _fmt_ibge_cep(cMun_e, _t(ender_e, "CEP")),
        "opSimpNac":   _simp(_t(reg, "opSimpNac")),
        "regApTribSN": _reg_sn(_t(reg, "regApTribSN")),
        # tomador
        "toma_cnpj":   _fmt_cnpj(_t(toma, "CNPJ", "CPF")),
        "toma_im":     _t(toma, "IM"),
        "toma_nome":   _t(toma, "xNome"),
        "toma_email":  _t(toma, "email"),
        "toma_fone":   _fmt_fone(_t(toma, "fone")),
        "toma_end":    toma_end,
        "toma_mun":    _mun(cMun_t, uf_t),
        "toma_cep":    _fmt_ibge_cep(cMun_t, _t(toma_ender_nac, "CEP")),
        # serviço
        "cod_nac":     cod_nac_label,
        "cod_nac_mun": f"{cTribNac_fmt} / {_t(root, 'cTribMun') if _t(root, 'cTribMun') != '-' else _t(cServ, 'cTribMun')}",
        "cod_mun":     _t(root, "xTribMun"),
        # O oficial imprime "MUNICÍPIO / UF / País"; sem país no XML, fica o traço.
        "loc_prest":   ((_mun_upper(cLocPrest) if cLocPrest != "-"
                         else _t(root, "xLocPrestacao"))
                        + f" / {_t(root, 'xPaisPrestacao')}"),
        "pais_prest":  _t(root, "xPaisPrestacao"),
        # O DANFSe é documento de "consulta resumida" (NT-008, item 2); descrições
        # muito longas são cortadas para o documento caber em 1 página, com
        # reticências sinalizando que o texto integral está no XML.
        "desc_serv":   _corta(_t(cServ, "xDescServ"), 480),
        "cNBS":        _fmt_nbs(_t(cServ, "cNBS")),
        # trib mun
        "tribISSQN":   _trib_iss(_t(tribMun, "tribISSQN")),
        "paisResult":  _t(tribMun, "cPaisResult"),
        "munIncid":    ((_mun_upper(cLocPrest) if cLocPrest != "-"
                         else _t(root, "xLocIncid"))
                        + f" / {_t(root, 'xPaisIncid')}"),
        "regEsp":      _reg_esp(_t(tribMun, "regEspTrib") if tribMun is not None
                                else _t(reg, "regEspTrib")),
        "tipoImun":    _t(tribMun, "tpImunidade"),
        "suspExig":    "Não",
        "numProc":     _t(root, "nProcesso"),
        "benMun":      _t(root, "xBenMun"),
        "vServ":       _fmt_val(vServ_raw),
        "descIncond":  _fmt_val(_t(vals_dps or root, "vDescIncond")),
        # O total de deduções vem em <vDedRed><vDR>; ler <vDedRed> direto pega
        # o container e devolve vazio.
        "totDed":      _fmt_val(_t(root, "vDR") if _t(root, "vDR") != "-"
                                else _t(vals_dps or root, "vDedRed")),
        "calcBM":      _fmt_val(_t(vals_dps or root, "vCalcBM")),
        "vBC":         _fmt_val(vBC_raw),
        "pAliq":       pAliq_fmt,
        "retISSQN":    _ret_iss(_t(tribMun, "tpRetISSQN")),
        "vISSQN":      _fmt_val(vISSQN_raw),
        # trib fed
        "irrf":        _fmt_val(_t(root, "vIRRF")),
        "contPrev":    _fmt_val(_t(root, "vCP")),
        "contSoc":     _fmt_val(_t(root, "vCSLL")),
        # Sem nenhuma retenção federal informada, o modelo oficial declara isso
        # por extenso em vez de deixar o campo com traço.
        "descCont":    (_t(root, "xContribSoc") if _t(root, "xContribSoc") != "-"
                        else (f"{_norm_cod(_t(root, 'tpRetPisCofins')) or '0'} - "
                              "PIS/COFINS/CSLL Não Retidos"
                              if _t(root, "vTotRet") in ("-", "", "0.00", "0")
                              else "-")),
        # No XML as tags são vPis/vCofins (e não vPIS/vCOFINS); _t é sensível a caixa.
        "pis":         _fmt_val(_t(root, "vPis", "vPIS")),
        "cofins":      _fmt_val(_t(root, "vCofins", "vCOFINS")),
        # valor total
        "vServT":      _fmt_val(vServ_raw),
        "descCond":    _fmt_val(_t(root, "vDescCond")),
        "descIncondT": _fmt_val(_t(root, "vDescIncond")),
        "issqnRet":    _fmt_val(_t(root, "vISSRet")),
        "totRetFed":   _fmt_val(_t(root, "vTotRet")),
        "pisCofins":   "-",
        "vLiq":        _fmt_val(vLiq_raw),
        # Tributos aproximados (Lei 12.741/2012). As tags corretas são
        # vTotTribFed/Est/Mun — ler vTotFed/Est/Mun deixava os três vazios.
        "tbFed": _fmt_val(_t(root, "vTotTribFed", "vTotFed")),
        "tbEst": _fmt_val(_t(root, "vTotTribEst", "vTotEst")),
        "tbMun": _fmt_val(_t(root, "vTotTribMun", "vTotMun")),
        # info complementar
        "infoComp":  (f"<b>NBS:</b> {_fmt_nbs(_t(cServ, 'cNBS'))} - {_t(root, 'xNBS')}"
                      if _t(cServ, "cNBS") != "-" else "-"),
        "xTribNac_desc": xTribNac_desc,
        "xLocEmi":   xLocEmi,
        "uf_emit":   uf_emit,
    }


# ── Estilos ───────────────────────────────────────────────────────────────────

def _ps(name, **kw):
    defaults = dict(fontName="Helvetica", fontSize=7, leading=8.5, textColor=C_BLK)
    defaults.update(kw)
    return ParagraphStyle(name, **defaults)


# No modelo oficial o rótulo é preto e em negrito; o valor é que vem sem peso.
S_LBL  = _ps("lbl",  fontSize=6,   leading=6.6, fontName="Helvetica-Bold")
S_VAL  = _ps("val",  fontSize=7,   leading=7.7)
S_VAL_B= _ps("valb", fontSize=8.5, leading=10,  fontName="Helvetica-Bold")
S_SEC  = _ps("sec",  fontSize=7,   leading=8,   fontName="Helvetica-Bold", textColor=C_BLK)
S_TTL  = _ps("ttl",  fontSize=11,  leading=13,  fontName="Helvetica-Bold", alignment=TA_CENTER)
S_SUB  = _ps("sub",  fontSize=8.5, leading=10,  alignment=TA_CENTER)
S_PRF  = _ps("prf",  fontSize=6,   leading=7.6, alignment=TA_RIGHT)
S_NOTE = _ps("note", fontSize=5.5, leading=7,   textColor=colors.HexColor("#555555"), alignment=TA_RIGHT)
S_INTER= _ps("int",  fontSize=7,   leading=9,   fontName="Helvetica-Bold", alignment=TA_CENTER)


# ── Logo NFS-e vetorial ───────────────────────────────────────────────────────

_LOGO_PNG = Path(__file__).resolve().parent.parent / "assets" / "nfse_logo.png"


def _logo_oficial(largura_mm: float = 42):
    """Logo oficial da NFS-e como imagem, igual ao DANFSe do padrão nacional.

    Desenhar a marca à mão nunca fica igual — e quebrava junto com a paleta.
    Se o arquivo faltar, cai no desenho antigo para não derrubar a geração.
    """
    if not _LOGO_PNG.exists():
        return NfseLogo()
    larg = largura_mm * mm
    return Image(str(_LOGO_PNG), width=larg, height=larg * 105 / 533)


class NfseLogo(Flowable):
    """Fallback desenhado — só entra em uso se o PNG oficial sumir."""
    W = 40 * mm
    H = 10 * mm

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
    # Padding mínimo: são ~25 grades de 2 linhas, e cada ponto aqui vira
    # 50 pontos de altura no documento — é o que decide 1 ou 2 páginas.
    ("TOPPADDING",    (0,0), (-1,-1), 0.6),
    ("BOTTOMPADDING", (0,0), (-1,-1), 0.6),
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
        ("TOPPADDING",    (0,0), (-1,-1), 1.2),
        ("BOTTOMPADDING", (0,0), (-1,-1), 1.2),
        ("LEFTPADDING",   (0,0), (-1,-1), 3),
        ("BOX",           (0,0), (-1,-1), 0.3, C_BRD),
    ]))
    return t


SEC_W = 48 * mm   # largura da célula de título de seção, como no modelo oficial


def _grid(cols_data: list[tuple[str,str]], widths: list[float],
          bold_last=False, secao: str | None = None,
          bold: tuple[int, ...] = ()) -> Table:
    """
    cols_data: [(label, value), ...]
    Gera 2 linhas: rótulos em cima, valores embaixo.

    `secao` desenha o título da seção como uma célula cinza à esquerda, ocupando
    as duas linhas — é assim que o DANFSe oficial marca as seções, e não como
    uma barra de largura total.
    """
    lbl_row = [Paragraph(l, S_LBL) for l, _ in cols_data]
    val_row = []
    for i, (_, v) in enumerate(cols_data):
        destacado = (bold_last and i == len(cols_data) - 1) or i in bold
        val_row.append(Paragraph(v, S_VAL_B if destacado else S_VAL))

    extra = []
    if secao is not None:
        lbl_row = [Paragraph(secao, S_SEC)] + lbl_row
        val_row = [""] + val_row
        widths = [SEC_W] + list(widths)
        extra = [
            ("SPAN",       (0,0), (0,1)),
            ("BACKGROUND", (0,0), (0,1), C_SEC),
            ("VALIGN",     (0,0), (0,1), "MIDDLE"),
        ]

    t = Table([lbl_row, val_row], colWidths=widths)
    t.setStyle(TableStyle(list(_STD.getCommands()) + extra))
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

def _marca_dagua(canvas, doc, texto="CANCELADA"):
    """Carimbo diagonal para NFS-e cancelada ou substituída.

    A nota cancelada continua tendo DANFSe — o documento existe e precisa ser
    arquivado; o que muda e que ele ostenta a situacao de forma inequivoca.
    """
    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 68)
    canvas.setFillColorRGB(0.85, 0.15, 0.15, alpha=0.22)
    canvas.translate(A4[0] / 2, A4[1] / 2)
    canvas.rotate(45)
    canvas.drawCentredString(0, 0, texto)
    canvas.restoreState()


def _rodape(canvas, d, largura):
    """Caixa de 3 colunas ancorada no pé da página, como no modelo oficial."""
    alt = 13 * mm
    y = M
    x = M
    c1, c2 = largura * 0.30, largura * 0.30
    canvas.saveState()
    canvas.setStrokeColor(C_BRD)
    canvas.setLineWidth(0.3)
    canvas.rect(x, y, largura, alt, fill=0, stroke=1)
    canvas.line(x + c1, y, x + c1, y + alt)
    canvas.line(x + c1 + c2, y, x + c1 + c2, y + alt)
    canvas.setFillColor(C_BLK)
    canvas.setFont("Helvetica-Bold", 6)
    topo = y + alt - 4
    canvas.drawString(x + 2, topo, "**** DATA CIENTIFICAÇÃO:")
    canvas.drawString(x + c1 + 2, topo, "IDENTIFICAÇÃO E ASSINATURA")
    canvas.drawString(x + c1 + c2 + 2, topo, "Nº NFS-e / CHAVE NFS-e")
    canvas.setFont("Helvetica", 6.5)
    canvas.drawString(x + c1 + c2 + 2, y + 3, f"{d['nNFSe']} / {d['chave']}")
    canvas.restoreState()


def gerar_danfse(xml_bytes: bytes, cancelada: bool | None = None) -> bytes:
    """Gera o DANFSe conforme a NT-008 v1.02 (layout DANFSe v2.0).

    `cancelada` força o carimbo quando o cancelamento só é conhecido por fora
    do XML — que é o caso normal: a NFS-e cancelada mantém cStat=100, e o
    cancelamento chega num documento <evento> separado (ver core/api_nfse.py).
    """
    d = _parse(xml_bytes)
    if cancelada is not None:
        d["cancelada"] = cancelada
    buf = io.BytesIO()

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=M, rightMargin=M,
        topMargin=M,  bottomMargin=M + 15 * mm,   # espaço reservado ao rodapé
        title=f"DANFSe - NFS-e {d['nNFSe']}",
    )

    story = []
    W = USABLE
    WS = W - SEC_W   # largura restante nas linhas que levam título de seção

    # ── 1. CABEÇALHO ─────────────────────────────────────────────────────────
    # [Logo | Título | Prefeitura]
    pref_txt = (f"Município: <b>{d['xLocEmi'].upper()} / {d['uf_emit']}</b><br/>"
                f"Ambiente Gerador: {d['ambGer']}<br/>"
                f"Tipo de Ambiente: {d['tpAmb']}")
    hdr = Table(
        [[_logo_oficial(),
          [Paragraph("DANFSe v2.0", S_TTL),
           Paragraph("Documento Auxiliar da NFS-e", S_SUB)],
          Paragraph(pref_txt, S_PRF)]],
        colWidths=[40*mm, W - 40*mm - 50*mm, 50*mm],
    )
    hdr.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN",         (2,0), (2,0),   "RIGHT"),
        # Faixa cinza sem moldura, fechada só pela linha de baixo — é assim no
        # modelo oficial; a caixa em volta do logo não existe lá.
        ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor("#F0F0F0")),
        ("LINEBELOW",     (0,0), (-1,-1), 0.6, C_BLK),
        ("TOPPADDING",    (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("LEFTPADDING",   (0,0), (-1,-1), 3),
        ("RIGHTPADDING",  (0,0), (-1,-1), 3),
    ]))
    story.append(hdr)

    # ── 2. CHAVE DE ACESSO + QR ───────────────────────────────────────────────
    qr = _qr_image(d["chave"], 20)
    qr_col_w = 48 * mm
    chave_w  = W - qr_col_w

    note_p = Paragraph(
        "A autenticidade desta NFS-e pode ser verificada pela leitura "
        "deste código QR ou pela consulta da chave de acesso no portal "
        "nacional da NFS-e",
        S_NOTE,
    )

    # Chave + numeração à esquerda; QR e a nota de autenticidade à direita,
    # abrangendo todas essas linhas — é esse SPAN que elimina o vazio e dá ao
    # cabeçalho a densidade do modelo oficial.
    w3 = chave_w / 3
    esquerda = [
        Table([[Paragraph("<b>CHAVE DE ACESSO DA NFS-e</b>", S_LBL)],
               [Paragraph(d["chave"], S_VAL)]], colWidths=[chave_w]),
        _grid([
            ("NÚMERO DA NFS-e",                 d["nNFSe"]),
            ("COMPETÊNCIA DA NFS-e",            d["competencia"]),
            ("DATA E HORA DA EMISSÃO DA NFS-e", d["dhProc"]),
        ], [w3]*3),
        _grid([
            ("NÚMERO DA DPS",                  d["nDPS"]),
            ("SÉRIE DA DPS",                   d["serie"]),
            ("DATA E HORA DA EMISSÃO DA DPS",  d["dhEmi"]),
        ], [w3]*3),
        _grid([
            ("EMITENTE DA NFS-e", d["tpEmit"]),
            ("SITUAÇÃO DA NFS-e", d["situacao"]),
            ("FINALIDADE",        d["finalidade"]),
        ], [w3]*3),
    ]
    esquerda[0].setStyle(TableStyle(list(_STD.getCommands())))

    topo = Table([[esquerda, [qr, note_p] if qr else note_p]],
                 colWidths=[chave_w, qr_col_w])
    topo.setStyle(TableStyle([
        ("VALIGN",        (0,0), (0,0), "TOP"),
        ("VALIGN",        (1,0), (1,0), "TOP"),
        ("ALIGN",         (1,0), (1,0), "CENTER"),
        ("BOX",           (0,0), (-1,-1), 0.3, C_BRD),
        ("INNERGRID",     (0,0), (-1,-1), 0.3, C_BRD),
        ("TOPPADDING",    (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
        ("LEFTPADDING",   (0,0), (0,0), 0),
        ("RIGHTPADDING",  (0,0), (0,0), 0),
        ("LEFTPADDING",   (1,0), (1,0), 2),
        ("RIGHTPADDING",  (1,0), (1,0), 2),
    ]))
    story.append(topo)
    w4 = W / 4

    # ── 4. PRESTADOR / FORNECEDOR ─────────────────────────────────────────────
    story.append(_grid([
        ("CNPJ / CPF / NIF",                d["emit_cnpj"]),
        ("Indicador Municipal (Inscrição)", d["emit_im"]),
        ("Telefone",                        d["emit_fone"]),
    ], [WS*0.34, WS*0.33, WS*0.33], secao="PRESTADOR / FORNECEDOR"))
    story.append(_grid([
        ("Nome / Nome Empresarial", d["emit_nome"]),
        ("Município / Sigla UF",    d["emit_mun"]),
        ("Código IBGE / CEP",       d["emit_cep"]),
    ], [W*0.50, W*0.25, W*0.25]))
    story.append(_grid([
        ("Endereço", d["emit_end"]),
        ("E-mail",    d["emit_email"]),
    ], [W*0.50, W*0.50]))
    story.append(_grid([
        ("Simples Nacional na Data de Competência", d["opSimpNac"]),
        ("Regime de Apuração Tributária pelo SN",   d["regApTribSN"]),
    ], [W*0.45, W*0.55]))

    # ── 5. TOMADOR / ADQUIRENTE ───────────────────────────────────────────────
    story.append(_grid([
        ("CNPJ / CPF / NIF",                d["toma_cnpj"]),
        ("Indicador Municipal (Inscrição)", d["toma_im"]),
        ("Telefone",                        d["toma_fone"]),
    ], [WS*0.34, WS*0.33, WS*0.33], secao="TOMADOR / ADQUIRENTE"))
    story.append(_grid([
        ("Nome / Nome Empresarial", d["toma_nome"]),
        ("Município / Sigla UF",    d["toma_mun"]),
        ("Código IBGE / CEP",       d["toma_cep"]),
    ], [W*0.50, W*0.25, W*0.25]))
    story.append(_grid([
        ("Endereço", d["toma_end"]),
        ("E-mail",    d["toma_email"]),
    ], [W*0.50, W*0.50]))

    # ── 6. DESTINATÁRIO E INTERMEDIÁRIO ───────────────────────────────────────
    # Blocos opcionais (regra 11 da NT): ausentes do XML, viram apenas a barra
    # declarando a ausência — o DANFSe nunca omite a informação em silêncio.
    for _rotulo in ("DESTINATÁRIO DA OPERAÇÃO NÃO IDENTIFICADO NA NFS-e",
                    "INTERMEDIÁRIO DA OPERAÇÃO NÃO IDENTIFICADO NA NFS-e"):
        t = Table([[Paragraph(_rotulo, S_INTER)]], colWidths=[W])
        t.setStyle(TableStyle([
            ("BOX",           (0,0),(-1,-1), 0.3, C_BRD),
            ("TOPPADDING",    (0,0),(-1,-1), 1.2),
            ("BOTTOMPADDING", (0,0),(-1,-1), 1.2),
        ]))
        story.append(t)

    # ── 7. SERVIÇO PRESTADO ───────────────────────────────────────────────────
    story.append(_grid([
        ("Código de Tributação Nacional / Municipal", d["cod_nac_mun"]),
        ("Código da NBS",                             d["cNBS"]),
        ("Local da Prestação / Sigla UF / País",      d["loc_prest"]),
    ], [WS*0.34, WS*0.28, WS*0.38], secao="SERVIÇO PRESTADO"))
    desc_cod = Table([[Paragraph(d["xTribNac_desc"], S_VAL)]], colWidths=[W])
    desc_cod.setStyle(TableStyle([
        ("BOX",           (0,0),(-1,-1), 0.3, C_BRD),
        ("TOPPADDING",    (0,0),(-1,-1), 1),
        ("BOTTOMPADDING", (0,0),(-1,-1), 1),
        ("LEFTPADDING",   (0,0),(-1,-1), 3),
    ]))
    story.append(desc_cod)
    story.append(_grid([
        ("Descrição do Serviço", d["desc_serv"]),
    ], [W]))

    # ── 8. TRIBUTAÇÃO MUNICIPAL (ISSQN) ───────────────────────────────────────
    story.append(_grid([
        ("Tipo de Tributação do ISSQN",                        d["tribISSQN"]),
        ("Município / Sigla UF / País de Incidência do ISSQN", d["munIncid"]),
    ], [WS*0.42, WS*0.58], secao="TRIBUTAÇÃO MUNICIPAL (ISSQN)"))
    story.append(_grid([
        ("Regime Especial de Tributação do ISSQN", d["regEsp"]),
        ("Tipo de Imunidade do ISSQN",             d["tipoImun"]),
        ("Suspensão da Exigibilidade do ISSQN",    d["suspExig"]),
        ("Número Processo Suspensão",              d["numProc"]),
    ], [w4]*4))
    story.append(_grid([
        ("Benefício Municipal",     d["benMun"]),
        ("Cálculo do BM",           d["calcBM"]),
        ("Total Deduções/Reduções", d["totDed"]),
        ("Desconto Incondicionado", d["descIncond"]),
    ], [w4]*4))
    story.append(_grid([
        ("BC ISSQN",        d["vBC"]),
        ("Alíquota Aplicada", d["pAliq"]),
        ("Retenção do ISSQN", d["retISSQN"]),
        ("ISSQN Apurado",    d["vISSQN"]),
    ], [w4]*4))

    # ── 9. TRIBUTAÇÃO FEDERAL (EXCETO CBS) ────────────────────────────────────
    story.append(_grid([
        ("IRRF",                                 d["irrf"]),
        ("Contribuição Previdenciária - Retida", d["contPrev"]),
        ("Contribuições Sociais - Retidas",      d["contSoc"]),
    ], [WS/3]*3, secao="TRIBUTAÇÃO FEDERAL (EXCETO CBS)"))
    story.append(_grid([
        ("PIS - Débito Apuração Própria",         d["pis"]),
        ("COFINS - Débito Apuração Própria",      d["cofins"]),
        ("Descrição Contrib. Sociais - Retidas",  d["descCont"]),
    ], [W/3, W/3, W/3]))

    # ── 9b. TRIBUTAÇÃO IBS / CBS ──────────────────────────────────────────────
    # Bloco da reforma tributária, exigido pela NT-008 v1.02. Os XMLs anteriores
    # à reforma não o trazem; nesse caso os campos saem com traço.
    story.append(_grid([
        ("CST / cClassTrib", f"{d['ibs_cst']} / {d['ibs_classtrib']}"),
        ("Indicador de Operação / Código IBGE Incidência / Município Incidência / Sigla UF",
         f"{d['ibs_indop']} / {d['ibs_cod_incid']} / {d['ibs_mun_incid']}"),
    ], [WS*0.30, WS*0.70], secao="TRIBUTAÇÃO IBS / CBS"))
    story.append(_grid([
        ("Exclusões e Reduções da Base de Cálculo",   d["ibs_exclusoes"]),
        ("Base de Cálculo Após Exclusões e Reduções", d["ibs_bc"]),
        ("Red. Alíquota IBS / Red. Alíquota CBS",     "-"),
        ("Alíquota – IBS UF / IBS Mun",
         f"{d['ibs_aliq_uf']} / {d['ibs_aliq_mun']}"),
    ], [w4]*4))
    story.append(_grid([
        ("Alíq. Efetiva Municipal – IBS", d["ibs_efet_mun"]),
        ("Valor Apurado Municipal – IBS", d["ibs_val_mun"]),
        ("Alíq. Efetiva Estadual – IBS",  d["ibs_efet_uf"]),
        ("Valor Apurado Estadual – IBS",  d["ibs_val_uf"]),
    ], [w4]*4))
    story.append(_grid([
        ("Valor Total Apurado – IBS", d["ibs_val_tot"]),
        ("Alíquota - CBS",            d["cbs_aliq"]),
        ("Alíquota Efetiva – CBS",    d["cbs_efet"]),
        ("Valor Total Apurado – CBS", d["cbs_val_tot"]),
    ], [w4]*4))

    # ── 10. VALOR TOTAL DA NFS-E ──────────────────────────────────────────────
    story.append(_grid([
        ("VALOR DA OPERAÇÃO / SERVIÇO", d["vServT"]),
        ("Desconto Incondicionado",     d["descIncondT"]),
        ("Desconto Condicionado",       d["descCond"]),
    ], [WS/3]*3, secao="VALOR TOTAL DA NFS-E"))
    story.append(_grid([
        ("Total das Retenções (ISSQN / Federais)", d["totRetFed"]),
        ("VALOR LÍQUIDO DA NFS-e",                 d["vLiq"]),
        ("Total do IBS/CBS",                       d["total_ibscbs"]),
        ("VALOR LÍQUIDO DA NFS-e + IBS/CBS",       d["liq_mais_ibscbs"]),
    ], [w4]*4, bold=(1, 3)))

    # ── 11. INFORMAÇÕES COMPLEMENTARES ───────────────────────────────────────
    story.append(_sec_bar("INFORMAÇÕES COMPLEMENTARES"))
    _linhas_info = [d["infoComp"]]
    _linhas_info.append(
        "<b>Totais Aproximados dos Tributos cfe. Lei nº 12.741/2012:</b> "
        f"Federais: {d['tbFed']}; Estaduais: {d['tbEst']}; Municipais: {d['tbMun']}"
    )
    info = Table([[Paragraph("<br/>".join(_linhas_info), S_VAL)]], colWidths=[W])
    info.setStyle(TableStyle([
        ("BOX",           (0,0),(-1,-1), 0.3, C_BRD),
        ("TOPPADDING",    (0,0),(-1,-1), 3),
        ("BOTTOMPADDING", (0,0),(-1,-1), 3),
        ("LEFTPADDING",   (0,0),(-1,-1), 3),
    ]))
    story.append(info)

    # ── 12. RODAPÉ ────────────────────────────────────────────────────────────
    # Fica ancorado no pé da página, não logo após o conteúdo — por isso é
    # desenhado no callback de página, e não empilhado na story.
    def _pagina(canvas, documento):
        if d.get("cancelada"):
            _marca_dagua(canvas, documento)
        _rodape(canvas, d, W)

    doc.build(story, onFirstPage=_pagina, onLaterPages=_pagina)
    return buf.getvalue()


def gerar_pdf_bytes(xml_bytes: bytes, cancelada: bool | None = None) -> bytes:
    return gerar_danfse(xml_bytes, cancelada=cancelada)
