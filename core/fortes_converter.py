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

    # Endereço do prestador
    emit_end = emit.find(f"{{{_NS}}}end") if emit is not None else None
    emit_cep    = _t(emit_end, "CEP")    if emit_end is not None else ""
    emit_lgr    = _t(emit_end, "xLgr")  if emit_end is not None else ""
    emit_nro    = _t(emit_end, "nro")   if emit_end is not None else ""
    emit_cpl    = _t(emit_end, "xCpl")  if emit_end is not None else ""
    emit_bairro = _t(emit_end, "xBairro") if emit_end is not None else ""
    emit_cmun   = _t(emit_end, "cMun")  if emit_end is not None else ""
    emit_xmun   = _t(emit_end, "xMun")  if emit_end is not None else ""
    emit_fone   = _t(emit, "fone")      if emit is not None else ""

    toma = inf_dps.find(f"{{{_NS}}}toma") if inf_dps is not None else None
    toma_cnpj = (_t(toma, "CNPJ") or _t(toma, "CPF")) if toma is not None else ""
    toma_nome = _t(toma, "xNome") if toma is not None else ""

    vals_nfse = inf.find(f"{{{_NS}}}valores")
    v_bc   = (_t(vals_nfse, "vBC")        if vals_nfse is not None else "") or "0.00"
    v_iss  = (_t(vals_nfse, "vISSQN")     if vals_nfse is not None else "") or "0.00"
    v_liq  = (_t(vals_nfse, "vLiq")       if vals_nfse is not None else "") or v_bc
    p_aliq = (_t(vals_nfse, "pAliqAplic") if vals_nfse is not None else "") or ""

    # Retenções federais
    ret_fed = inf_dps.find(f".//{{{_NS}}}retFed") if inf_dps is not None else None
    v_ret_cofins = (_t(ret_fed, "vRetCofins") or _t(ret_fed, "vCofins")) if ret_fed is not None else ""
    v_ret_pis    = (_t(ret_fed, "vRetPis")    or _t(ret_fed, "vPis"))    if ret_fed is not None else ""
    v_ret_csl    = (_t(ret_fed, "vRetCsll")   or _t(ret_fed, "vCsll"))   if ret_fed is not None else ""
    v_ret_irrf   = (_t(ret_fed, "vRetIRRF")   or _t(ret_fed, "vIRRF"))   if ret_fed is not None else ""
    v_ret_inss   = (_t(ret_fed, "vRetInss")   or _t(ret_fed, "vInss"))   if ret_fed is not None else ""

    # CNAE do serviço
    cnae = ""
    if inf_dps is not None:
        serv = inf_dps.find(f".//{{{_NS}}}serv")
        if serv is not None:
            cnae = _t(serv, "CNAE") or _t(serv, "cnae")

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
        "n_nfse":        n_nfse,
        "d_compet":      d_compet,
        "emit_cnpj":     emit_cnpj,
        "emit_nome":     emit_nome,
        "emit_im":       emit_im,
        "emit_uf":       emit_uf or "CE",
        "emit_cep":      emit_cep,
        "emit_lgr":      emit_lgr,
        "emit_nro":      emit_nro,
        "emit_cpl":      emit_cpl,
        "emit_bairro":   emit_bairro,
        "emit_cmun":     emit_cmun,
        "emit_xmun":     emit_xmun,
        "emit_fone":     emit_fone,
        "toma_cnpj":     toma_cnpj,
        "toma_nome":     toma_nome,
        "v_bc":          v_bc,
        "v_iss":         v_iss,
        "v_liq":         v_liq,
        "p_aliq":        p_aliq,
        "tp_ret_iss":    tp_ret_iss,
        "chave_acesso":  chave_acesso,
        "cnae":          cnae,
        "v_ret_cofins":  v_ret_cofins,
        "v_ret_pis":     v_ret_pis,
        "v_ret_csl":     v_ret_csl,
        "v_ret_irrf":    v_ret_irrf,
        "v_ret_inss":    v_ret_inss,
    }


def _par_line(par_id: int, nome: str, uf: str, cnpj: str, im: str,
              cep: str = "", lgr: str = "", nro: str = "", cpl: str = "",
              bairro: str = "", cmun: str = "", xmun: str = "", fone: str = "") -> str:
    # PAR tem exatamente 33 campos conforme manual v71
    f = [""] * 33
    f[0]  = "PAR"
    f[1]  = str(par_id)
    f[2]  = nome.upper()[:60]
    f[3]  = uf
    f[4]  = cnpj
    f[5]  = ""        # 6: Inscrição Estadual (não disponível no XML)
    f[6]  = im        # 7: Inscrição Municipal
    f[7]  = "N"       # 8: Informa ISS Digital
    f[8]  = "N"       # 9: Informa DIEF
    f[9]  = "N"       # 10: Informa DIC
    f[10] = "N"       # 11: Informa DEMMS
    f[11] = "N"       # 12: Órgão Público
    f[12] = "N"       # 13: Informa Livro Eletrônico
    f[13] = "N"       # 14: Fornecedor de Prod. Primário
    f[14] = "N"       # 15: Sociedade Simples
    f[15] = cep       # 16: CEP
    f[16] = lgr       # 17: Logradouro
    f[17] = nro       # 18: Número
    f[18] = cpl       # 19: Complemento
    f[19] = bairro    # 20: Bairro
    f[20] = cmun      # 21: Código Município (IBGE)
    f[21] = xmun      # 22: Nome Município
    f[22] = uf        # 23: UF endereço
    # f[23] DDD
    # f[24] Fone
    ddd, tel = (fone[:2], fone[2:]) if len(fone) > 2 else ("", fone)
    f[23] = ddd
    f[24] = tel
    f[26] = "N"       # 27: Substituto ISS
    f[29] = "1058"    # 30: País (Brasil)
    f[30] = "N"       # 31: Exterior
    f[31] = "N"       # 32: Isento do ICMS
    # f[32] e-mail (vazio)
    return "|".join(f)


def _esi_line(par_id: int, data_emi: str, num_nota: str, v_total: str, chave: str = "",
              v_cofins: str = "", v_pis: str = "", v_csl: str = "",
              v_irrf: str = "", v_inss: str = "") -> str:
    # ESI tem exatamente 21 campos conforme manual v71
    f = [""] * 21
    f[0]  = "ESI"
    f[1]  = "0001"
    f[2]  = str(par_id)
    f[3]  = data_emi
    f[4]  = "S"
    f[5]  = "50"
    f[6]  = "N"
    f[7]  = num_nota
    f[8]  = v_total
    # f[9]  = data retenção (blank)
    # f[10] = serviço Fortaleza (blank)
    f[11] = v_cofins  # COFINS retido
    f[12] = v_pis     # PIS retido
    f[13] = v_csl     # CSL retido
    f[14] = v_irrf    # IRRF retido
    f[15] = v_inss    # INSS retido
    # f[16] = série (blank)
    # f[17] = fatura (blank)
    # f[18] = observação (blank)
    f[19] = chave[:44] if chave else ""  # chave eletrônica
    # f[20] = campo reservado (blank)
    return "|".join(f)


def _ies_line(v_total: str, tributacao: str, aliq: str, cod_servico: str, v_bc: str,
              cnae: str = "") -> str:
    # IES tem exatamente 11 campos conforme manual v71
    f = [""] * 11
    f[0]  = "IES"
    f[1]  = v_total
    f[2]  = "N"
    f[3]  = tributacao
    f[4]  = v_total
    f[5]  = aliq
    f[6]  = cod_servico
    f[7]  = cnae      # CNAE do serviço
    f[8]  = "98"
    # f[9]  = blank
    f[10] = v_bc
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
        f"CAB|71|ACFiscal|{hoje}|{nome_empresa}|{periodo_ini}|{periodo_fim}|{observacao}|N"
    )

    prestadores: dict = {}
    par_id_next = 10000
    for n in notas:
        cnpj = n["emit_cnpj"]
        if cnpj and cnpj not in prestadores:
            prestadores[cnpj] = {
                "id":     par_id_next,
                "nome":   n["emit_nome"],
                "uf":     n["emit_uf"],
                "im":     n["emit_im"],
                "cep":    n.get("emit_cep", ""),
                "lgr":    n.get("emit_lgr", ""),
                "nro":    n.get("emit_nro", ""),
                "cpl":    n.get("emit_cpl", ""),
                "bairro": n.get("emit_bairro", ""),
                "cmun":   n.get("emit_cmun", ""),
                "xmun":   n.get("emit_xmun", ""),
                "fone":   n.get("emit_fone", ""),
            }
            par_id_next += 1

    for cnpj, p in prestadores.items():
        linhas.append(_par_line(
            p["id"], p["nome"], p["uf"], cnpj, p["im"],
            cep=p.get("cep",""), lgr=p.get("lgr",""), nro=p.get("nro",""),
            cpl=p.get("cpl",""), bairro=p.get("bairro",""),
            cmun=p.get("cmun",""), xmun=p.get("xmun",""), fone=p.get("fone",""),
        ))

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

        linhas.append(_esi_line(
            par_id, data_emi, num_nota, v_total, n.get("chave_acesso", ""),
            v_cofins=n.get("v_ret_cofins", ""),
            v_pis=n.get("v_ret_pis", ""),
            v_csl=n.get("v_ret_csl", ""),
            v_irrf=n.get("v_ret_irrf", ""),
            v_inss=n.get("v_ret_inss", ""),
        ))
        linhas.append(_ies_line(v_total, tributacao, aliq, cod_servico, v_bc,
                                cnae=n.get("cnae", "")))

    linhas.append(f"TRA|{len(linhas) + 1}")
    return "\r\n".join(linhas) + "\r\n"
