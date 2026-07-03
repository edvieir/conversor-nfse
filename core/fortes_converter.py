"""
core/fortes_converter.py — Conversor NFS-e XML → Fortes ACFiscal (.fs)
"""

import defusedxml.ElementTree as ET
from datetime import date

_NS = "http://www.sped.fazenda.gov.br/nfse"


def _t(el, tag: str) -> str:
    found = el.find(f".//{{{_NS}}}{tag}")
    return found.text.strip() if found is not None and found.text else ""


_IBGE_UF = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE",
    "27": "AL", "28": "SE", "29": "BA",
    "31": "MG", "32": "ES", "33": "RJ", "35": "SP",
    "41": "PR", "42": "SC", "43": "RS",
    "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}


def _uf_from_cmun(cmun: str) -> str:
    """Deriva a sigla UF a partir do código IBGE de 7 dígitos do município."""
    digits = ''.join(c for c in cmun if c.isdigit())
    return _IBGE_UF.get(digits[:2], "")


_CSTAT_CANCELADO = {
    "101",  # NFS-e Cancelada (emitente regular)
    "108",  # NFS-e do MEI Cancelada
}


def _nota_cancelada(root) -> bool:
    """
    Dois filtros independentes — basta um ser verdadeiro para classificar como cancelada.

    Filtro 1 (estrutural): presença do elemento <nfseCanc> no XML.
    Filtro 2 (cStat):      valor em {101, 108} — códigos de cancelamento NFS-e Nacional.
                           cStat=107 = NFS-e do MEI Gerada = AUTORIZADA (não é cancelamento).
    """
    if any(e.tag.split("}")[-1] == "nfseCanc" for e in root.iter()):
        return True
    el_cstat = next((e for e in root.iter() if e.tag.split("}")[-1] == "cStat"), None)
    if el_cstat is not None and el_cstat.text and el_cstat.text.strip() in _CSTAT_CANCELADO:
        return True
    return False


def parse_nfse_xml(xml_bytes: bytes) -> dict:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValueError(f"XML inválido: {exc}") from exc

    cancelada = _nota_cancelada(root)

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
    toma_cnpj   = (_t(toma, "CNPJ") or _t(toma, "CPF")) if toma is not None else ""
    toma_is_cpf = bool(_t(toma, "CPF")) if toma is not None else False
    toma_nome   = _t(toma, "xNome")   if toma is not None else ""
    toma_lgr    = _t(toma, "xLgr")   if toma is not None else ""
    toma_nro    = _t(toma, "nro")     if toma is not None else ""
    toma_bairro = _t(toma, "xBairro") if toma is not None else ""
    toma_cep    = _t(toma, "CEP")     if toma is not None else ""
    toma_cmun   = _t(toma, "cMun")   if toma is not None else ""
    # UF pode estar ausente no <toma> do NFSe Nacional; deriva do prefixo IBGE
    toma_uf     = _t(toma, "UF") if toma is not None else ""
    if not toma_uf and toma_cmun:
        toma_uf = _uf_from_cmun(toma_cmun)

    vals_nfse = inf.find(f"{{{_NS}}}valores")
    v_bc   = (_t(vals_nfse, "vBC")        if vals_nfse is not None else "") or "0.00"
    v_iss  = (_t(vals_nfse, "vISSQN")     if vals_nfse is not None else "") or "0.00"
    v_liq  = (_t(vals_nfse, "vLiq")       if vals_nfse is not None else "") or v_bc
    p_aliq = (_t(vals_nfse, "pAliqAplic") if vals_nfse is not None else "") or ""

    v_ret_cofins = v_ret_pis = v_ret_csl = v_ret_irrf = v_ret_inss = ""
    if inf_dps is not None:
        v_ret_cofins = _t(inf_dps, "vRetCofins") or _t(inf_dps, "vCofins")
        v_ret_pis    = _t(inf_dps, "vRetPis")    or _t(inf_dps, "vPis")
        v_ret_csl    = _t(inf_dps, "vRetCSLL")   or _t(inf_dps, "vCSLL") or _t(inf_dps, "vRetCsll") or _t(inf_dps, "vCsll")
        v_ret_irrf   = _t(inf_dps, "vRetIRRF")   or _t(inf_dps, "vIRRF")
        v_ret_inss   = _t(inf_dps, "vRetInss")   or _t(inf_dps, "vInss")

    cnae = _t(inf_dps, "CNAE") if inf_dps is not None else ""

    # código e descrição do serviço (dentro de <cServ> no DPS)
    c_serv       = inf_dps.find(f".//{{{_NS}}}cServ") if inf_dps is not None else None
    cod_trib_mun = _t(c_serv, "cTribMun") if c_serv is not None else ""
    cod_trib_nac = _t(c_serv, "cTribNac") if c_serv is not None else ""
    desc_serv    = _t(c_serv, "xDescServ") if c_serv is not None else ""
    # cTribNac tem 6 dígitos no padrão LLSSDD (lista LC116 + sub-item + desdobramento).
    # Fortes cadastra o código ISS como str(int(LL)) + SS preenchido com zeros à esquerda até 6
    # dígitos. Ex: "070101" → LL=07→7, SS=01 → "701" → zfill(6) → "000701".
    if len(cod_trib_nac) >= 4:
        ll = str(int(cod_trib_nac[0:2])) if cod_trib_nac[0:2].isdigit() else cod_trib_nac[0:2]
        ss = cod_trib_nac[2:4]
        cod_lc116 = ll + ss  # ex: "070101" -> "7"+"01" = "701"
    else:
        cod_lc116 = cod_trib_nac

    dh_emi_raw = _tv("dhEmi") or _tv("dEmi") or ""
    d_emi = dh_emi_raw[:10] if dh_emi_raw else ""  # YYYY-MM-DD

    d_compet = _tv("dCompet")
    if not d_compet:
        d_compet = d_emi or date.today().isoformat()
    if not d_emi:
        d_emi = d_compet

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
        "cancelada": cancelada,
        "n_nfse": n_nfse, "d_compet": d_compet, "d_emi": d_emi,
        "emit_cnpj": emit_cnpj, "emit_nome": emit_nome,
        "emit_im": emit_im, "emit_uf": emit_uf or "CE",
        "emit_lgr": emit_lgr, "emit_nro": emit_nro,
        "emit_cpl": emit_cpl, "emit_bairro": emit_bairro,
        "emit_cmun": emit_cmun, "emit_cep": emit_cep, "emit_fone": emit_fone,
        "toma_cnpj": toma_cnpj, "toma_is_cpf": toma_is_cpf, "toma_nome": toma_nome,
        "toma_uf": toma_uf, "toma_lgr": toma_lgr, "toma_nro": toma_nro,
        "toma_bairro": toma_bairro, "toma_cep": toma_cep, "toma_cmun": toma_cmun,
        "v_bc": v_bc, "v_iss": v_iss, "v_liq": v_liq, "p_aliq": p_aliq,
        "tp_ret_iss": tp_ret_iss, "chave_acesso": chave_acesso, "cnae": cnae,
        "v_ret_cofins": v_ret_cofins, "v_ret_pis": v_ret_pis,
        "v_ret_csl": v_ret_csl, "v_ret_irrf": v_ret_irrf, "v_ret_inss": v_ret_inss,
        "cod_trib_mun": cod_trib_mun, "cod_trib_nac": cod_trib_nac,
        "cod_lc116": cod_lc116, "desc_serv": desc_serv,
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


def _par_line_prestado(par_id, nome, uf, doc, is_cpf=False,
                       lgr="", nro="", cpl="", bairro="", cep="", cmun="", fone=""):
    """PAR line para arquivo de serviços Prestados (v200)."""
    # Campo 18 exige numérico; CMun deve ser só dígitos
    nro_num  = ''.join(c for c in (nro or "") if c.isdigit())
    cmun_dig = ''.join(c for c in (cmun or "") if c.isdigit())
    cmun_cod = cmun_dig[-5:] if len(cmun_dig) >= 5 else cmun_dig

    f = [""] * 43
    f[0]  = "PAR"
    f[1]  = str(par_id)
    f[2]  = nome.upper()[:60]
    f[3]  = "" if is_cpf else uf
    f[4]  = doc
    f[7]  = "N"
    f[11] = "N"
    f[13] = "N"
    f[14] = "N"
    if not is_cpf and (lgr or bairro or cep or cmun):
        f[15] = "35"  # tipo logradouro padrão
        f[16] = lgr
        f[17] = nro_num   # somente dígitos
        f[18] = cpl
        f[19] = "1" if bairro else ""
        f[20] = bairro
        f[21] = cep.replace("-", "").replace(".", "")
        f[22] = cmun_cod  # campo 23: código município Fortes (5 dígitos)
        ddd, tel = (fone[:2], fone[2:]) if len(fone) > 2 else ("", fone)
        f[23] = ddd
        f[24] = tel
        f[29] = "1058"
    else:
        f[20] = "0"
    f[26] = "N"
    f[30] = "N"
    f[31] = "3" if is_cpf else "1"
    f[33] = "N"
    f[34] = "N"
    f[36] = "N"
    f[37] = "0"
    f[38] = "N"
    return "|".join(f)


def _dss_line(par_id, data_emi, num_nota, v_total, chave, d_compet_yyyymm01, iss_retido,
              v_cofins="", v_pis="", v_csl="", v_irrf="", v_inss=""):
    """DSS line — documento de serviço prestado (57 campos, layout v200)."""
    f = [""] * 57
    f[0]  = "DSS"
    f[1]  = "0001"
    f[2]  = data_emi            # YYYYMMDD (data emissão)
    f[3]  = "50"                # NFS-e Nacional
    f[4]  = "N"
    f[5]  = num_nota            # número nota, 15 dígitos
    f[6]  = ""
    f[7]  = "N"
    f[8]  = v_total
    f[9]  = str(par_id)
    f[10] = "S" if iss_retido else "N"
    # Retido na Fonte: campos 21-26 (f[20]-f[25])
    # campos 12-20 = Receita Tributável (COFINS/PIS/CSL/IRPJ) — deixar vazios
    f[20] = v_cofins or ""      # campo 21: COFINS retido
    f[21] = v_pis    or ""      # campo 22: PIS retido
    f[22] = v_csl    or ""      # campo 23: CSL retido
    # f[23]                     # campo 24: IRPJ retido (n/a)
    f[24] = v_inss   or ""      # campo 25: INSS retido
    f[25] = v_irrf   or ""      # campo 26: IRRF retido
    f[30] = chave[:44] if chave else ""   # campo 31: chave
    f[31] = d_compet_yyyymm01            # campo 32: data de prestação AAAAMMDD
    f[32] = "N"                          # campo 33: Pago pelo SUS
    # f[33-34] = vazios
    f[35] = v_total                      # campo 36: valor
    # f[36] = vazio (campo 37: Código Contábil — deixar em branco)
    f[37] = "0"                          # campo 38
    # f[38-41] = vazios (campo 39: CNO — deve ficar vazio)
    f[42] = "0"                          # campo 43
    f[43] = "0"                          # campo 44
    f[44] = "0"                          # campo 45
    # f[45-54] = vazios
    f[55] = "N"                          # campo 56: Pagamento Antecipado
    return "|".join(f)


def _its_line(v_total, cod_atividade, v_bc, aliq, uf, cmun, cod_servico):
    """ITS line — item de serviço prestado (50 campos, layout v200).

    campo 3  (f[2])  = Código de Atividade ISS (código configurado no Fortes)
    campo 10 (f[9])  = Código do Serviço ISS
    campo 15 (f[14]) = Código de Atividade ISS (secundário, mesmo valor)
    """
    # Código do serviço: remove zeros à esquerda (Fortes usa ex: "701" não "0701")
    cod_serv_clean = str(int(cod_servico)) if cod_servico and cod_servico.isdigit() else (cod_servico or "")

    f = [""] * 50
    f[0]  = "ITS"
    f[1]  = v_total
    f[2]  = str(cod_atividade) if cod_atividade else ""  # campo 3: Código de Atividade
    f[3]  = v_bc
    try:
        f[4] = f"{float(aliq):.5f}" if aliq else ""
    except (ValueError, TypeError):
        f[4] = aliq or ""
    f[5]  = "1"
    f[6]  = uf
    f[7]  = cmun
    f[9]  = cod_serv_clean                               # campo 10: Código do Serviço
    f[14] = str(cod_atividade) if cod_atividade else ""  # campo 15: Código de Atividade (2º)
    f[19] = v_total
    return "|".join(f)


def gerar_fortes_prestados(notas, nome_empresa, observacao=""):
    """Gera arquivo .fs para serviços PRESTADOS (formato DSS/ITS, versão 200)."""
    if not notas:
        return ""

    hoje = date.today().strftime("%Y%m%d")
    datas_raw = [n["d_compet"].replace("-", "")[:8] for n in notas if n.get("d_compet")]
    periodo_ini = (min(datas_raw)[:6] + "01") if datas_raw else hoje[:6] + "01"
    periodo_fim = (max(datas_raw)[:6] + "01") if datas_raw else hoje[:6] + "01"
    # Ajusta período_fim para o último dia do mês
    import calendar
    try:
        ano_f, mes_f = int(periodo_fim[:4]), int(periodo_fim[4:6])
        ultimo_dia = calendar.monthrange(ano_f, mes_f)[1]
        periodo_fim = f"{ano_f}{mes_f:02d}{ultimo_dia:02d}"
    except Exception:
        pass

    linhas = [f"CAB|200|ACFiscal|{hoje}|{nome_empresa}|{periodo_ini}|{periodo_fim}|1|N"]

    # Constrói índice de tomadores (parceiros)
    tomadores = {}
    par_id_next = 1
    for n in notas:
        if n.get("cancelada"):
            continue
        doc = n.get("toma_cnpj") or ""
        if doc and doc not in tomadores:
            tomadores[doc] = {
                "id": par_id_next,
                "nome": n.get("toma_nome", "") or doc,
                "uf": n.get("toma_uf", ""),
                "lgr": n.get("toma_lgr", ""),
                "nro": n.get("toma_nro", ""),
                "bairro": n.get("toma_bairro", ""),
                "cep": n.get("toma_cep", ""),
                "cmun": n.get("toma_cmun", ""),
                "is_cpf": n.get("toma_is_cpf", False),
            }
            par_id_next += 1

    for doc, p in tomadores.items():
        linhas.append(_par_line_prestado(
            p["id"], p["nome"], p["uf"], doc, is_cpf=p["is_cpf"],
            lgr=p["lgr"], nro=p["nro"], bairro=p["bairro"],
            cep=p["cep"], cmun=p["cmun"],
        ))

    for n in sorted(notas, key=lambda n: (n["d_compet"], n["n_nfse"].zfill(15))):
        if n.get("cancelada"):
            continue
        doc = n.get("toma_cnpj") or ""
        if not doc or doc not in tomadores:
            continue

        par_id  = tomadores[doc]["id"]
        d_emi_raw = (n.get("d_emi") or n["d_compet"]).replace("-", "")[:8]
        d_comp_raw = n["d_compet"].replace("-", "")[:8]
        d_compet_yyyymm01 = d_comp_raw[:6] + "01"

        num_nota  = n["n_nfse"].zfill(15)
        v_total   = n["v_liq"] or n["v_bc"]
        iss_retido = n.get("tp_ret_iss") == "2"
        tributacao = "4" if iss_retido else "3"
        aliq_iss   = n.get("p_aliq", "")
        chave      = n.get("chave_acesso", "")

        linhas.append(_dss_line(
            par_id, d_emi_raw, num_nota, v_total,
            chave, d_compet_yyyymm01, iss_retido,
            v_cofins=n.get("v_ret_cofins", ""),
            v_pis   =n.get("v_ret_pis",    ""),
            v_csl   =n.get("v_ret_csl",    ""),
            v_irrf  =n.get("v_ret_irrf",   ""),
            v_inss  =n.get("v_ret_inss",   ""),
        ))

        uf           = n.get("emit_uf", "CE")
        # Código do município: últimos 5 dígitos do IBGE (coluna MUN_Codigo aceita só 5)
        mun_raw  = ''.join(c for c in (n.get("emit_cmun") or "") if c.isdigit())
        mun_code = mun_raw[-5:] if len(mun_raw) >= 5 else mun_raw
        cod_atividade = n.get("cod_lc116") or n.get("cod_trib_mun") or ""

        linhas.append(_its_line(v_total, cod_atividade, n["v_bc"],
                                aliq_iss, uf, mun_code, cod_atividade))

    linhas.append(f"TRA|{len(linhas) + 1}")
    return "\r\n".join(linhas) + "\r\n"


def gerar_fortes(notas, nome_empresa, observacao="NFS-e Importacao"):
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
        if n.get("cancelada"):
            continue
        cnpj = n["emit_cnpj"]
        if not cnpj or cnpj not in prestadores:
            continue
        par_id     = prestadores[cnpj]["id"]
        data_emi   = n["d_compet"].replace("-", "")
        num_nota   = n["n_nfse"].zfill(15)
        v_total    = n["v_liq"]
        # tpRetISSQN=2 → ISS retido pelo tomador; qualquer outro → não retido
        iss_retido = n.get("tp_ret_iss") == "2"
        tributacao = "4" if iss_retido else "3"
        aliq_iss   = n["p_aliq"] if iss_retido else ""

        linhas.append(_esi_line(
            par_id, data_emi, num_nota, v_total, n.get("chave_acesso",""),
            v_cofins=n.get("v_ret_cofins",""), v_pis=n.get("v_ret_pis",""),
            v_csl=n.get("v_ret_csl",""), v_irrf=n.get("v_ret_irrf",""),
            v_inss=n.get("v_ret_inss",""),
        ))
        # LC 116 derivado do cTribNac tem prioridade; fallback para cTribMun
        _cod = n.get("cod_lc116") or n.get("cod_trib_mun") or ""
        linhas.append(_ies_line(v_total, tributacao, aliq_iss, _cod,
                                n["v_bc"], cnae=n.get("cnae","")))

    linhas.append(f"TRA|{len(linhas) + 1}")
    return "\r\n".join(linhas) + "\r\n"
