"""
core/fortes_converter.py — Conversor NFS-e XML → Fortes ACFiscal (.fs)
"""

from xml.etree import ElementTree as ET
from datetime import date

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

    inf = root.find(f"{{{_NS}}}infNFSe")
    if inf is None:
        inf = root.find(f".//{{{_NS}}}infNFSe")
    if inf is None:
        raise ValueError("Elemento <infNFSe> não encontrado no XML")

    inf_dps = inf.find(f".//{{{_NS}}}infDPS")

    def _tv(tag: str) -> str:
        v = _t(inf, tag)
        if not v and inf_dps is not None:
            v = _t(inf_dps, tag)
        return v

    emit = inf.find(f"{{{_NS}}}emit")
    emit_cnpj = _t(emit, "CNPJ") if emit is not None else ""
    emit_nome = _t(emit, "xNome") if emit is not None else ""
    emit_im   = _t(emit, "IM") if emit is not None else ""
    emit_uf   = _t(emit, "UF") if emit is not None else "CE"

    toma = inf_dps.find(f"{{{_NS}}}toma") if inf_dps is not None else None
    toma_cnpj = (_t(toma, "CNPJ") or _t(toma, "CPF")) if toma is not None else ""
    toma_nome = _t(toma, "xNome") if toma is not None else ""

    vals_nfse = inf.find(f"{{{_NS}}}valores")
    v_bc   = (_t(vals_nfse, "vBC")        if vals_nfse is not None else "") or "0.00"
    v_iss  = (_t(vals_nfse, "vISSQN")     if vals_nfse is not None else "") or "0.00"
    v_liq  = (_t(vals_nfse, "vLiq")       if vals_nfse is not None else "") or v_bc
    p_aliq = (_t(vals_nfse, "pAliqAplic") if vals_nfse is not None else "") or ""

    d_compet = _tv("dCompet")
    if not d_compet:
        dh = _tv("dhEmi")
        d_compet = dh[:10] if dh else date.today().isoformat()

    n_nfse = _t(inf, "nNFSe") or _tv("nDPS") or "0"

    tp_ret_iss = ""
    if inf_dps is not None:
        trib_mun = inf_dps.find(f".//{{{_NS}}}tribMun")
        tp_ret_iss = _t(trib_mun, "tpRetISSQN") if trib_mun is not None else ""

    # Chave eletrônica (44 chars) — extraída do Id do infNFSe sem o prefixo "NFS"
    chave_acesso = ""
    inf_id = inf.get("Id", "")
    if inf_id.startswith("NFS"):
        chave_acesso = inf_id[3:47]   # 44 chars após "NFS"
    elif len(inf_id) >= 44:
        chave_acesso = inf_id[:44]

    return {
        "n_nfse":       n_nfse,
        "d_compet":     d_compet,
        "emit_cnpj":    emit_cnpj,
        "emit_nome":    emit_nome,
        "emit_im":      emit_im,
        "emit_uf":      emit_uf or "CE",
        "toma_cnpj":    toma_cnpj,
        "toma_nome":    toma_nome,
        "v_bc":         v_bc,
        "v_iss":        v_iss,
        "v_liq":        v_liq,
        "p_aliq":       p_aliq,
        "tp_ret_iss":   tp_ret_iss,
        "chave_acesso": chave_acesso,
    }


def _par_line(par_id: int, nome: str, uf: str, cnpj: str, im: str) -> str:
    f = [""] * 43
    f[0]  = "PAR"
    f[1]  = str(par_id)
    f[2]  = nome.upper()[:60]
    f[3]  = uf
    f[4]  = cnpj
    f[5]  = im       # IM
    f[6]  = ""       # inscricao estadual
    f[7]  = "N"      # contribuinte ISS
    f[11] = "N"
    f[13] = "N"
    f[14] = "N"
    f[19] = "0"
    f[26] = "N"
    f[30] = "N"
    f[31] = "3"
    f[33] = "N"
    f[34] = "N"
    f[36] = "N"
    f[37] = "0"
    f[38] = "N"
    return "|".join(f)


def _esi_line(par_id: int, data_emi: str, num_nota: str, v_total: str, chave: str = "") -> str:
    f = [""] * 44
    f[0]  = "ESI"
    f[1]  = "0001"
    f[2]  = str(par_id)
    f[3]  = data_emi
    f[4]  = "S"
    f[5]  = "50"
    f[6]  = "N"
    f[7]  = num_nota
    f[8]  = v_total
    # f[9]  = data retencao (blank)
    # f[10] = servico Fortaleza (blank)
    # f[11] = COFINS retido (blank)
    # f[12] = PIS retido (blank)
    # f[13] = CSL retido (blank)
    # f[14] = IRRF retido (blank)
    # f[15] = INSS retido (blank)
    # f[16] = serie (blank)
    # f[17] = fatura (blank)
    # f[18] = observacao (blank)
    f[19] = chave[:44] if chave else ""  # chave eletronica (44 chars)
    f[23] = v_total
    f[25] = "0"
    f[28] = data_emi
    f[31] = "0"
    f[42] = "N"
    f[43] = ""   # trailing pipe
    return "|".join(f)


def _ies_line(v_total: str, tributacao: str, aliq: str, cod_servico: str, v_bc: str) -> str:
    f = [""] * 59
    f[0]  = "IES"
    f[1]  = v_total
    f[2]  = "N"
    f[3]  = tributacao
    f[4]  = v_total
    f[5]  = aliq
    f[6]  = cod_servico
    f[7]  = ""
    f[8]  = "98"
    f[13] = v_bc
    return "|".join(f)


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
    linhas.append(
        f"CAB|200|ACFiscal|{hoje}|{nome_empresa}|{periodo_ini}|{periodo_fim}|{observacao}|N"
    )

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

    for cnpj, p in prestadores.items():
        linhas.append(_par_line(p["id"], p["nome"], p["uf"], cnpj, p["im"]))

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
        tributacao = "4" if n.get("tp_ret_iss") == "1" else "3"

        linhas.append(_esi_line(par_id, data_emi, num_nota, v_total, n.get("chave_acesso", "")))
        linhas.append(_ies_line(v_total, tributacao, aliq, cod_servico, v_bc))

    return "\r\n".join(linhas) + "\r\n"
