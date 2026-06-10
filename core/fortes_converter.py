"""
core/fortes_converter.py — Conversor NFS-e XML → Fortes ACFiscal (.fs)
"""

from xml.etree import ElementTree as ET
from datetime import date
from typing import Optional

_NS = "http://www.sped.fazenda.gov.br/nfse"


def _t(el, tag: str) -> str:
    """Return text of first matching descendant, empty string if absent."""
    found = el.find(f".//{{{_NS}}}{tag}")
    return found.text.strip() if found is not None and found.text else ""


def parse_nfse_xml(xml_bytes: bytes) -> dict:
    """
    Parse NFS-e XML (formato nacional sped.fazenda.gov.br).
    Returns dict with all fields needed for Fortes .fs generation.
    Raises ValueError on malformed XML.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValueError(f"XML inválido: {exc}") from exc

    # Support root = <NFSe> or <nfseProc> wrapper
    inf = root.find(f"{{{_NS}}}infNFSe")
    if inf is None:
        inf = root.find(f".//{{{_NS}}}infNFSe")
    if inf is None:
        raise ValueError("Elemento <infNFSe> não encontrado no XML")

    # DPS (inner document)
    inf_dps = inf.find(f".//{{{_NS}}}infDPS")

    def _tv(tag: str) -> str:
        """Look in infNFSe first, then infDPS."""
        v = _t(inf, tag)
        if not v and inf_dps is not None:
            v = _t(inf_dps, tag)
        return v

    # ── Emitente (prestador) ───────────────────────────────────────────────
    emit = inf.find(f"{{{_NS}}}emit")
    emit_cnpj = _t(emit, "CNPJ") if emit is not None else ""
    emit_nome = _t(emit, "xNome") if emit is not None else ""
    emit_im   = _t(emit, "IM") if emit is not None else ""
    emit_uf   = _t(emit, "UF") if emit is not None else "CE"

    # ── Tomador ────────────────────────────────────────────────────────────
    toma = inf_dps.find(f"{{{_NS}}}toma") if inf_dps is not None else None
    toma_cnpj = (_t(toma, "CNPJ") or _t(toma, "CPF")) if toma is not None else ""
    toma_nome = _t(toma, "xNome") if toma is not None else ""

    # ── Valores NFSe ───────────────────────────────────────────────────────
    vals_nfse = inf.find(f"{{{_NS}}}valores")
    v_bc   = (_t(vals_nfse, "vBC")        if vals_nfse is not None else "") or "0.00"
    v_iss  = (_t(vals_nfse, "vISSQN")     if vals_nfse is not None else "") or "0.00"
    v_liq  = (_t(vals_nfse, "vLiq")       if vals_nfse is not None else "") or v_bc
    p_aliq = (_t(vals_nfse, "pAliqAplic") if vals_nfse is not None else "") or ""

    # ── Competência ────────────────────────────────────────────────────────
    d_compet = _tv("dCompet")  # YYYY-MM-DD
    if not d_compet:
        # fallback: dhEmi
        dh = _tv("dhEmi")
        d_compet = dh[:10] if dh else date.today().isoformat()

    # ── Número nota ────────────────────────────────────────────────────────
    n_nfse = _t(inf, "nNFSe") or _tv("nDPS") or "0"

    # ── Retenção ISS ───────────────────────────────────────────────────────
    tp_ret_iss = ""
    if inf_dps is not None:
        trib_mun = inf_dps.find(f".//{{{_NS}}}tribMun")
        tp_ret_iss = _t(trib_mun, "tpRetISSQN") if trib_mun is not None else ""

    return {
        "n_nfse":    n_nfse,
        "d_compet":  d_compet,
        "emit_cnpj": emit_cnpj,
        "emit_nome": emit_nome,
        "emit_im":   emit_im,
        "emit_uf":   emit_uf or "CE",
        "toma_cnpj": toma_cnpj,
        "toma_nome": toma_nome,
        "v_bc":      v_bc,
        "v_iss":     v_iss,
        "v_liq":     v_liq,
        "p_aliq":    p_aliq,
        "tp_ret_iss": tp_ret_iss,  # "1"=retido tomador, "2"=normal
    }


# ── Record builders ────────────────────────────────────────────────────────────

def _par_line(par_id: int, nome: str, uf: str, cnpj: str, im: str) -> str:
    """PAR record: parceiro/prestador."""
    f = [""] * 49
    f[0]  = "PAR"
    f[1]  = str(par_id)
    f[2]  = nome.upper()[:60]
    f[3]  = uf
    f[4]  = cnpj
    f[5]  = im
    f[6]  = ""       # inscrição estadual
    f[7]  = "N"      # contribuinte ISS
    f[12] = "N"
    f[14] = "N"
    f[15] = "N"
    f[21] = "0"
    f[29] = "N"
    f[34] = "N"
    f[35] = "3"
    f[38] = "N"
    f[39] = "N"
    f[42] = "N"
    f[43] = "0"
    f[44] = "N"
    return "|".join(f)


def _esi_line(par_id: int, data_emi: str, num_nota: str, v_total: str) -> str:
    """ESI record: entrada de serviço ISS."""
    f = [""] * 45
    f[0]  = "ESI"
    f[1]  = "0001"       # codEmpresa
    f[2]  = str(par_id)
    f[3]  = data_emi     # YYYYMMDD
    f[4]  = "S"
    f[5]  = "50"         # natureza operação
    f[6]  = "N"          # cancelado
    f[7]  = num_nota     # 15 dígitos
    f[8]  = v_total
    # f[11..14] = IRRF, CSLL, PIS, COFINS (empty — sem retenção federal no XML simples)
    # f[17] = "V" quando há retenção (empty aqui)
    f[23] = v_total      # valorServicos
    f[25] = "0"
    f[28] = data_emi     # dataLancto
    f[31] = "0"
    f[43] = "N"
    f[44] = ""           # trailing pipe
    return "|".join(f)


def _ies_line(
    v_total: str,
    tributacao: str,
    aliq: str,
    cod_servico: str,
    v_bc: str,
) -> str:
    """IES record: detalhe ISS entrada."""
    f = [""] * 59
    f[0]  = "IES"
    f[1]  = v_total
    f[2]  = "N"          # construção civil
    f[3]  = tributacao   # "3"=normal, "4"=retido
    f[4]  = v_total      # valorServicos
    f[5]  = aliq         # alíquota ISS
    f[6]  = cod_servico  # código serviço Fortes
    f[7]  = ""           # natureza crédito
    f[8]  = "98"         # CST COFINS/PIS (98=não incide)
    # f[9..12] = bases COFINS/PIS (empty)
    f[13] = v_bc         # base cálculo ISS
    return "|".join(f)


# ── Public API ─────────────────────────────────────────────────────────────────

def gerar_fortes(
    notas: list,
    nome_empresa: str,
    observacao: str = "NFS-e Importacao",
    cod_servico: str = "",
) -> str:
    """
    Generates Fortes ACFiscal .fs file from a list of parsed NFS-e dicts.
    Returns file content as a string (CRLF line endings).
    """
    if not notas:
        return ""

    hoje = date.today().strftime("%Y%m%d")

    datas = [n["d_compet"].replace("-", "") for n in notas if n.get("d_compet")]
    periodo_ini = min(datas) if datas else hoje
    periodo_fim = max(datas) if datas else hoje

    linhas = []

    # CAB
    linhas.append(
        f"CAB|200|ACFiscal|{hoje}|{nome_empresa}|{periodo_ini}|{periodo_fim}|{observacao}|S"
    )

    # Collect unique prestadores (by CNPJ)
    prestadores: dict = {}
    par_id_next = 10000
    for n in notas:
        cnpj = n["emit_cnpj"]
        if cnpj and cnpj not in prestadores:
            prestadores[cnpj] = {
                "id":   par_id_next,
                "nome": n["emit_nome"],
                "uf":   n["emit_uf"],
                "im":   n["emit_im"],
            }
            par_id_next += 1

    # PAR records
    for cnpj, p in prestadores.items():
        linhas.append(_par_line(p["id"], p["nome"], p["uf"], cnpj, p["im"]))

    # ESI + IES records (one pair per nota, sorted by competência then número)
    notas_ord = sorted(notas, key=lambda n: (n["d_compet"], n["n_nfse"].zfill(15)))
    for n in notas_ord:
        cnpj = n["emit_cnpj"]
        if not cnpj or cnpj not in prestadores:
            continue

        par_id   = prestadores[cnpj]["id"]
        data_emi = n["d_compet"].replace("-", "")
        num_nota = n["n_nfse"].zfill(15)
        v_total  = n["v_liq"]
        aliq     = n["p_aliq"]
        v_bc     = n["v_bc"]
        # tributação: 4=ISS retido pelo tomador, 3=demais
        tributacao = "4" if n.get("tp_ret_iss") == "1" else "3"

        linhas.append(_esi_line(par_id, data_emi, num_nota, v_total))
        linhas.append(_ies_line(v_total, tributacao, aliq, cod_servico, v_bc))

    return "\r\n".join(linhas) + "\r\n"
