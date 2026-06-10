"""
core/fortes_converter.py — Conversor NFS-e XML → Fortes ACFiscal (.fs)
"""

from xml.etree import ElementTree as ET
from datetime import date

_NS = "http://www.sped.fazenda.gov.br/nfse"


def _t(el, tag: str) -> str:
    found = el.find(f".//{{{_NS}}}{tag}")
    return found.text.strip() if found is not None and found.text else ""


def parse_nfse_xml(xml_bytes: bytes) -> dict:
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

    def _tv(tag):
        v = _t(inf, tag)
        if not v and inf_dps is not None:
            v = _t(inf_dps, tag)
        return v

    emit = inf.find(f"{{{_NS}}}emit")
    emit_cnpj   = _t(emit, "CNPJ")    if emit is not None else ""
    emit_nome   = _t(emit, "xNome")   if emit is not None else ""
    emit_im     = _t(emit, "IM")      if emit is not None else ""
    emit_uf     = _t(emit, "UF")      if emit is not None else "CE"
    emit_lgr    = _t(emit, "xLgr")   if emit is not None else ""
    emit_nro    = _t(emit, "nro")     if emit is not None else ""
    emit_cpl    = _t(emit, "xCpl")   if emit is not None else ""
    emit_bairro = _t(emit, "xBairro") if emit is not None else ""
    emit_cmun   = _t(emit, "cMun")   if emit is not None else ""
    emit_cep    = _t(emit, "CEP")    if emit is not None else ""
    emit_fone   = _t(emit, "fone")   if emit is not None else ""

    toma = inf_dps.find(f"{{{_NS}}}toma") if inf_dps is not None else None
    toma_cnpj = (_t(toma, "CNPJ") or _t(toma, "CPF")) if toma is not None else ""
    toma_nome = _t(toma, "xNome") if toma is not None else ""

    vals_nfse = inf.find(f"{{{_NS}}}valores")
    v_bc   = (_t(vals_nfse, "vBC")        if vals_nfse is not None else "") or "0.00"
    v_iss  = (_t(vals_nfse, "vISSQN")     if vals_nfse is not None else "") or "0.00"
    v_liq  = (_t(vals_nfse, "vLiq")       if vals_nfse is not None else "") or v_bc
    p_aliq = (_t(vals_nfse, "pAliqAplic") if vals_nfse is not None else "") or ""

    v_ret_cofins = v_ret_pis = v_ret_csl = v_ret_irrf = v_ret_inss = ""
    if inf_dps is not None:
        v_ret_cofins = _t(inf_dps, "vRetCofins") or _t(inf_dps, "vCofins")
        v_ret_pis    = _t(inf_dps, "vRetPis")    or _t(inf_dps, "vPis")
        v_ret_csl    = _t(inf_dps, "vRetCSLL")   or _t(inf_dps, "vRetCsll") or _t(inf_dps, "vCsll")
        v_ret_irrf   = _t(inf_dps, "vRetIRRF")   or _t(inf_dps, "vIRRF")
        v_ret_inss   = _t(inf_dps, "vRetInss")   or _t(inf_dps, "vInss")

    cnae = _t(inf_dps, "CNAE") if inf_dps is not None else ""

    d_compet = _tv("dCompet")
    if not d_compet:
        dh = _tv("dhEmi")
        d_compet = dh[:10] if dh else date.today().isoformat()

    n_nfse = _t(inf, "nNFSe") or _tv("nDPS") or "0"

    tp_ret_iss = ""
    if inf_dps is not None:
        trib_mun = inf_dps.find(f".//{{{_NS}}}tribMun")
        tp_ret_iss = _t(trib_mun, "tpRetISSQN") if trib_mun is not None else ""

    chave_acesso = ""
    inf_id = inf.get("Id", "")
    if inf_id.startswith("NFS"):
        chave_acesso = inf_id[3:47]
    elif len(inf_id) >= 44:
        chave_acesso = inf_id[:44]

    return {
        "n_nfse": n_nfse, "d_compet": d_compet,
        "emit_cnpj": emit_cnpj, "emit_nome": emit_nome,
        "emit_im": emit_im, "emit_uf": emit_uf or "CE",
        "emit_lgr": emit_lgr, "emit_nro": emit_nro,
        "emit_cpl": emit_cpl, "emit_bairro": emit_bairro,
        "emit_cmun": emit_cmun, "emit_cep": emit_cep, "emit_fone": emit_fone,
        "toma_cnpj": toma_cnpj, "toma_nome": toma_nome,
        "v_bc": v_bc, "v_iss": v_iss, "v_liq": v_liq, "p_aliq": p_aliq,
        "tp_ret_iss": tp_ret_iss, "chave_acesso": chave_acesso, "cnae": cnae,
        "v_ret_cofins": v_ret_cofins, "v_ret_pis": v_ret_pis,
        "v_ret_csl": v_ret_csl, "v_ret_irrf": v_ret_irrf, "v_ret_inss": v_ret_inss,
    }


def _par_line(par_id, nome, uf, cnpj, im,
              lgr="", nro="", cpl="", bairro="", cep="", cmun="", fone=""):
    f = [""] * 33
    f[0]  = "PAR";  f[1]  = str(par_id); f[2]  = nome.upper()[:60]
    f[3]  = uf;     f[4]  = cnpj
    f[5]  = "";     f[6]  = im
    f[7]  = "N";    f[8]  = "N";  f[9]  = "N";  f[10] = "N"
    f[11] = "N";    f[12] = "N";  f[13] = "N";  f[14] = "N"
    f[15] = ""      # 16: Tipo Logradouro (código)
    f[16] = lgr     # 17: Logradouro
    f[17] = nro     # 18: Número
    f[18] = cpl     # 19: Complemento
    f[19] = ""      # 20: Tipo Bairro (código)
    f[20] = bairro  # 21: Bairro
    f[21] = cep.replace("-", "").replace(".", "")  # 22: CEP (numérico)
    f[22] = cmun[-5:] if len(cmun) >= 5 else cmun  # 23: Município IBGE 5 dig
    ddd, tel = (fone[:2], fone[2:]) if len(fone) > 2 else ("", fone)
    f[23] = ddd;    f[24] = tel
    f[26] = "N";    f[29] = "1058";  f[30] = "N";  f[31] = "N"
    return "|".join(f)


def _esi_line(par_id, data_emi, num_nota, v_total, chave="",
              v_cofins="", v_pis="", v_csl="", v_irrf="", v_inss=""):
    f = [""] * 21
    f[0]="ESI"; f[1]="0001"; f[2]=str(par_id); f[3]=data_emi
    f[4]="S";   f[5]="50";   f[6]="N";         f[7]=num_nota; f[8]=v_total
    f[11]=v_cofins; f[12]=v_pis; f[13]=v_csl; f[14]=v_irrf; f[15]=v_inss
    f[19]=chave[:44] if chave else ""
    return "|".join(f)


def _ies_line(v_total, tributacao, aliq, cod_servico, v_bc, cnae=""):
    f = [""] * 11
    f[0]="IES"; f[1]=v_total; f[2]="N"; f[3]=tributacao
    f[4]=v_total; f[5]=aliq; f[6]=cod_servico; f[7]=cnae; f[8]="98"; f[10]=v_bc
    return "|".join(f)


def gerar_fortes(notas, nome_empresa, observacao="NFS-e Importacao", cod_servico=""):
    if not notas:
        return ""

    hoje = date.today().strftime("%Y%m%d")
    datas = [n["d_compet"].replace("-", "") for n in notas if n.get("d_compet")]
    periodo_ini = min(datas) if datas else hoje
    periodo_fim = max(datas) if datas else hoje

    linhas = [f"CAB|71|ACFiscal|{hoje}|{nome_empresa}|{periodo_ini}|{periodo_fim}|{observacao}|N"]

    prestadores = {}
    par_id_next = 10000
    for n in notas:
        cnpj = n["emit_cnpj"]
        if cnpj and cnpj not in prestadores:
            prestadores[cnpj] = {
                "id": par_id_next, "nome": n["emit_nome"],
                "uf": n["emit_uf"], "im": n["emit_im"],
                "lgr": n.get("emit_lgr",""), "nro": n.get("emit_nro",""),
                "cpl": n.get("emit_cpl",""), "bairro": n.get("emit_bairro",""),
                "cep": n.get("emit_cep",""), "cmun": n.get("emit_cmun",""),
                "fone": n.get("emit_fone",""),
            }
            par_id_next += 1

    for cnpj, p in prestadores.items():
        linhas.append(_par_line(
            p["id"], p["nome"], p["uf"], cnpj, p["im"],
            lgr=p["lgr"], nro=p["nro"], cpl=p["cpl"], bairro=p["bairro"],
            cep=p["cep"], cmun=p["cmun"], fone=p["fone"],
        ))

    for n in sorted(notas, key=lambda n: (n["d_compet"], n["n_nfse"].zfill(15))):
        cnpj = n["emit_cnpj"]
        if not cnpj or cnpj not in prestadores:
            continue
        par_id     = prestadores[cnpj]["id"]
        data_emi   = n["d_compet"].replace("-", "")
        num_nota   = n["n_nfse"].zfill(15)
        v_total    = n["v_liq"]
        tributacao = "4" if n.get("tp_ret_iss") == "1" else "3"

        linhas.append(_esi_line(
            par_id, data_emi, num_nota, v_total, n.get("chave_acesso",""),
            v_cofins=n.get("v_ret_cofins",""), v_pis=n.get("v_ret_pis",""),
            v_csl=n.get("v_ret_csl",""), v_irrf=n.get("v_ret_irrf",""),
            v_inss=n.get("v_ret_inss",""),
        ))
        linhas.append(_ies_line(v_total, tributacao, n["p_aliq"], cod_servico,
                                n["v_bc"], cnae=n.get("cnae","")))

    linhas.append(f"TRA|{len(linhas) + 1}")
    return "\r\n".join(linhas) + "\r\n"
