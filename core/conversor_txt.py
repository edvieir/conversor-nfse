"""
core/conversor_txt.py — Conversão XML → TXT (ISS Fortaleza)
Lógica copiada integralmente de app_web.py — NENHUMA linha de conversão alterada.
"""

import sys
import io
import os
import tempfile
import contextlib
from pathlib import Path

# Garante que nfse_xml_to_txt (raiz do projeto) seja encontrado
sys.path.insert(0, str(Path(__file__).parent.parent))

_CONVERSOR_OK  = False
_CONVERSOR_ERR = ""
try:
    import nfse_xml_to_txt as C
    _CONVERSOR_OK = True
except Exception as _e:
    _CONVERSOR_ERR = str(_e)


def conversor_disponivel() -> tuple[bool, str]:
    return _CONVERSOR_OK, _CONVERSOR_ERR


# ── CACHE MEI (persiste durante todo o processo Streamlit) ────────────────────
# Evita consultar o mesmo CNPJ mais de uma vez por sessão do servidor.
_cnpj_mei_cache: dict = {}


def _consulta_cnpj_mei(cnpj: str):
    """
    Consulta BrasilAPI para verificar se um CNPJ é MEI.
    Retorna True (é MEI), False (não é MEI) ou None (erro / sem resposta).
    Usa cache em memória — o mesmo CNPJ nunca é consultado duas vezes.
    """
    import urllib.request as _ureq
    import json as _json

    cnpj_limpo = "".join(c for c in (cnpj or "") if c.isdigit())
    if len(cnpj_limpo) != 14:
        return None

    if cnpj_limpo in _cnpj_mei_cache:
        return _cnpj_mei_cache[cnpj_limpo]

    try:
        url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"
        req = _ureq.Request(url, headers={"User-Agent": "ConversorNFSe/2.0"})
        with _ureq.urlopen(req, timeout=5) as resp:
            data = _json.loads(resp.read())
        porte   = str(data.get("porte") or "").upper()
        is_mei  = (porte == "MEI") or (data.get("opcao_pelo_mei") is True)
        _cnpj_mei_cache[cnpj_limpo] = is_mei
        return is_mei
    except Exception:
        return None   # API indisponível — resultado inconclusivo


# ── PROCESSAMENTO TXT ─────────────────────────────────────────────────────────

def processar_uploads(uploaded_files, im: str, modo: str, competencia_filtro: str = ""):
    """
    Converte arquivos XML para TXT (ISS Fortaleza) ou XLSX (SPED GOV via nfse_xml_to_txt).
    Todo o pós-processamento de correção de campos é feito aqui via _fix_linha().
    NÃO modifica nfse_xml_to_txt.py.
    """
    import xml.etree.ElementTree as _ET
    import unicodedata as _ud
    import re as _re

    def _comp_bytes(b):
        """Extrai competência MM/AAAA do conteúdo do XML."""
        try:
            root = _ET.fromstring(b)
            el = next((e for e in root.iter() if e.tag.endswith("dCompet")), None)
            if el is not None and el.text:
                p = el.text.strip()[:7].split("-")
                return f"{p[1]}/{p[0]}"
        except Exception:
            pass
        return ""

    def _emit_pj_nao_mei(content: bytes) -> bool:
        """
        Retorna True quando o emitente é PJ de Fortaleza e NÃO é MEI.
        Nesse caso o XML é ignorado no TXT ISS Fortaleza.

        Lógica: para Fortaleza PJ, só inclui se MEI for CONFIRMADO.
        Inconclusivo → filtrar (o oposto da cautela geral):
          - Pessoa Física (CPF)    → incluir sempre
          - PJ de outro município  → incluir sempre
          - MEI de Fortaleza       → incluir (qualquer camada confirma)
          - PJ Fortaleza inconclusivo → filtrar (seguro para ISS Fortaleza)

        Camadas de confirmação MEI:
          1. opSimpNac=2 ou regEspTrib=5 no XML
          2. Nome termina com 11 dígitos (padrão MEI: "NOME SOBRENOME CPF")
          3. BrasilAPI / Receita Federal (com cache por sessão)
        """
        try:
            root = _ET.fromstring(content)
            emit = next((e for e in root.iter() if e.tag.endswith("emit")), None)
            if emit is None:
                return False

            # ── Município: filtra apenas emitentes de Fortaleza ───────────────
            loc_emi = next((e.text or "" for e in root.iter()
                           if e.tag.endswith("cLocEmi")), "")
            if loc_emi.strip() != "2304400":
                return False  # Emitente de outro município → incluir sempre

            # ── A partir daqui: emitente de Fortaleza ────────────────────────
            # Regra: só inclui se MEI CONFIRMADO (usa CNPJ). Inconclusivo → filtrar.
            # CPF de Fortaleza também é filtrado: cartório/PF não é MEI.

            # Camada 0: CPF de Fortaleza → filtrar (PF não é MEI)
            cpf = next((c.text or "" for c in emit if c.tag.endswith("CPF")), "")
            if cpf.strip():
                return True

            # Sem CNPJ e sem CPF → não conseguimos identificar → incluir
            cnpj = next((c.text or "" for c in emit if c.tag.endswith("CNPJ")), "")
            if not cnpj.strip():
                return False

            # ── Camada 1: Campos XML (opSimpNac / regEspTrib) ────────────────
            prest = next((e for e in root.iter() if e.tag.endswith("prest")), None)
            if prest is not None:
                op_simp = next((e.text or "0" for e in prest.iter()
                               if e.tag.endswith("opSimpNac")), "0")
                reg_esp = next((e.text or "0" for e in prest.iter()
                               if e.tag.endswith("regEspTrib")), "0")
                if op_simp.strip() == "2" or reg_esp.strip() == "5":
                    return False  # MEI confirmado pelo XML → incluir
                # opSimpNac 1=Simples ou 3=Regime Normal → definitivamente não-MEI
                if op_simp.strip() in ("1", "3"):
                    return True

            # ── Camada 2: Razão social com CPF embutido (padrão de nome MEI) ─
            nome = next((c.text or "" for c in emit if c.tag.endswith("xNome")), "")
            if _re.search(r"\s\d{11}$", nome.strip()):
                return False  # MEI confirmado pelo nome → incluir

            # ── Camada 3: BrasilAPI — consulta Receita Federal ───────────────
            api_mei = _consulta_cnpj_mei(cnpj.strip())
            if api_mei is True:
                return False  # API confirma MEI → incluir
            if api_mei is False:
                return True   # API confirma não-MEI → filtrar

            # BrasilAPI indisponível e MEI não confirmado por nenhuma camada:
            # filtrar por segurança (PJ Fortaleza só entra se MEI confirmado)
            return True
        except Exception:
            return False

    # ── Pré-leitura: monta lookup de retenção a partir dos XMLs originais ──────
    # Necessário porque nfse_xml_to_txt.py tem dois bugs que precisamos corrigir:
    #   BUG 1 – Campo 21 (tpRetISSQN): o script passa o valor da NFS-e nacional
    #           diretamente, mas os significados são invertidos:
    #           NFS-e tpRetISSQN=2 = "retido pelo tomador"
    #           ISS Fortaleza campo 21=1 = "retido" (campo 21=2 = "a recolher")
    #           → notas com tpRetISSQN=2 ficam com campo 21=2 ("a recolher") — ERRADO.
    #   BUG 2 – Campos 39/40 (PIS/COFINS): o script busca tags 'vPIS'/'vCOFINS'
    #           (maiúsculas), mas o XML usa 'vPis'/'vCofins' (misto). Case-sensitive
    #           no ElementTree → valores nunca são encontrados → ficam vazios.
    _ret_lookup = {}   # {numero_nota: {tpRet, vPis, vCofins, vCSLL}}
    if modo == "txt":
        for _uf in uploaded_files:
            try:
                _uf.seek(0)
                _root = _ET.fromstring(_uf.read())
                # Número da nota: replica a mesma lógica do nfse_xml_to_txt.py,
                # que busca nDFSe (depois nNFSe) nos filhos DIRETOS do infNFSe.
                _infNFSe = next((e for e in _root.iter()
                                 if e.tag.endswith("infNFSe")), _root)
                # nNFSe = número oficial da nota (exibido no DANFSe e usado pelo portal)
                _nNFSe_val = next((c.text.strip() for c in _infNFSe
                                   if c.tag.endswith("nNFSe") and c.text), "")
                # chave do lookup = mesma lógica do nfse_xml_to_txt.py:
                # nDFSe primeiro (filho direto de infNFSe), depois nNFSe
                _nota_num = (
                    next((c.text.strip() for c in _infNFSe
                          if c.tag.endswith("nDFSe") and c.text), "")
                    or _nNFSe_val
                )
                # Tipo retenção ISS (1=não retido, 2=retido pelo tomador)
                _tpRet = next((e.text or "1" for e in _root.iter()
                               if e.tag.endswith("tpRetISSQN")), "1")
                # Retenções federais (tags explícitas de retenção, não valores calculados)
                _vPis    = next((e.text or "" for e in _root.iter()
                                 if e.tag.lower().endswith("vretpis")), "")
                _vCofins = next((e.text or "" for e in _root.iter()
                                 if e.tag.lower().endswith("vretcofins")), "")
                _vCSLL   = next((e.text or "" for e in _root.iter()
                                 if e.tag.lower().endswith("vretcsll")), "")
                # INSS retido: campo vRetCP no NFS-e Nacional (Contribuição Previdenciária)
                _vINSS   = next((e.text or "" for e in _root.iter()
                                 if e.tag.lower().endswith("vretcp")), "")
                # IR retido na fonte
                _vIRRF   = next((e.text or "" for e in _root.iter()
                                 if e.tag.lower().endswith("vretirrf")), "")
                # Alíquota ISS: busca pAliqAplic (nível NFSe) ou pAliq (nível DPS/tribMun)
                _aliq = (next((e.text or "" for e in _root.iter()
                                if e.tag.endswith("pAliqAplic")), "")
                         or next((e.text or "" for e in _root.iter()
                                  if e.tag.endswith("pAliq")), ""))
                # Valor ISS retido (vISSQN)
                _vISS = next((e.text or "" for e in _root.iter()
                              if e.tag.endswith("vISSQN")), "")
                # Valor bruto (base de cálculo do ISS, antes de deduções)
                _vBC  = next((e.text or "" for e in _root.iter()
                              if e.tag.endswith("vBC")), "")
                # CPF do emitente (quando prestador é Pessoa Física)
                _emit_el2 = next((e for e in _root.iter() if e.tag.endswith("emit")), None)
                _cpf_emit = ""
                if _emit_el2 is not None:
                    _cpf_emit = next(
                        (e.text.strip() for e in _emit_el2 if e.tag.endswith("CPF") and e.text),
                        ""
                    )
                # Competência (dCompet): mês e ano corretos da prestação do serviço.
                # nfse_xml_to_txt.py usa dhEmi (emissão), o que quebra quando a nota
                # é emitida em mês diferente da competência (ex: emitida 01/07, dCompet 06/2026).
                _comp_mes = ""
                _comp_ano = ""
                _dCompet_el = next((e for e in _root.iter() if e.tag.endswith("dCompet")), None)
                if _dCompet_el is not None and _dCompet_el.text:
                    _dc = _dCompet_el.text.strip()  # formato: YYYY-MM-DD
                    if len(_dc) >= 7:
                        _comp_ano = _dc[:4]
                        _comp_mes = _dc[5:7]
                _rinfo = {
                    "tpRet":    _tpRet,
                    "aliq":     _aliq,
                    "vISS":     _vISS,
                    "vBC":      _vBC,
                    "nNFSe":    _nNFSe_val,   # número oficial (DANFSe)
                    "vPis":     _vPis,        # PIS retido na fonte (vRetPis)
                    "vCofins":  _vCofins,     # COFINS retido na fonte (vRetCofins)
                    "vCSLL":    _vCSLL,       # CSLL retido na fonte
                    "vINSS":    _vINSS,       # INSS retido (vRetCP)
                    "vIRRF":    _vIRRF,       # IR retido na fonte
                    "cpf_emit": _cpf_emit,    # CPF do prestador PF (vazio se CNPJ)
                    "comp_mes": _comp_mes,    # mês da competência (dCompet)
                    "comp_ano": _comp_ano,    # ano da competência (dCompet)
                }
                if _nota_num:
                    _ret_lookup[_nota_num] = _rinfo
            except Exception:
                pass
            finally:
                try:
                    _uf.seek(0)
                except Exception:
                    pass

    def _sanitize_semicolons_xml(data: bytes) -> bytes:
        """Substitui ';' dentro de nós de texto XML por espaço.
        Evita que campos como xCpl com ';' quebrem o delimitador do TXT."""
        def _rep(m):
            return m.group(0).replace(b";", b" ")
        return _re.sub(rb">([^<]+)<", _rep, data)

    _CSTAT_CANCELADO_TXT = {"101", "108"}

    def _is_cancelada_bytes(content: bytes) -> bool:
        """
        Filtro 1: elemento <nfseCanc> presente.
        Filtro 2: cStat em {101, 108} (cancelamento NFS-e Nacional).
        cStat=107 = NFS-e do MEI Gerada = AUTORIZADA.
        """
        try:
            root = _ET.fromstring(content)
            if any(e.tag.split("}")[-1] == "nfseCanc" for e in root.iter()):
                return True
            el_cstat = next((e for e in root.iter() if e.tag.split("}")[-1] == "cStat"), None)
            if el_cstat is not None and el_cstat.text and el_cstat.text.strip() in _CSTAT_CANCELADO_TXT:
                return True
        except Exception:
            pass
        return False

    with tempfile.TemporaryDirectory() as tmp:
        ignorados    = 0
        pj_ignorados = 0
        canc_ignorados = 0
        for uf in uploaded_files:
            uf.seek(0)
            content = uf.read()
            if competencia_filtro:
                comp = _comp_bytes(content)
                if comp and comp != competencia_filtro:
                    ignorados += 1
                    continue
            if _is_cancelada_bytes(content):
                canc_ignorados += 1
                continue
            # TXT Fortaleza: ignora emitentes PJ que não sejam MEI ou Pessoa Física
            if modo == "txt" and _emit_pj_nao_mei(content):
                pj_ignorados += 1
                continue
            with open(os.path.join(tmp, uf.name), "wb") as fh:
                fh.write(_sanitize_semicolons_xml(content) if modo == "txt" else content)
        ext   = "txt" if modo == "txt" else "xlsx"
        saida = os.path.join(tmp, f"resultado.{ext}")
        buf   = io.StringIO()
        if ignorados:
            buf.write(f"  FILTRO  {ignorados} arquivo(s) ignorado(s) — competência ≠ {competencia_filtro}\n\n")
        if canc_ignorados:
            buf.write(f"  CANCELADAS  {canc_ignorados} nota(s) cancelada(s) ignorada(s)\n\n")
        if pj_ignorados:
            buf.write(
                f"  FILTRO  {pj_ignorados} arquivo(s) ignorado(s) "
                f"— emitente PJ de Fortaleza não-MEI (TXT: só CPF e MEI de Fortaleza)\n\n"
            )
        with contextlib.redirect_stdout(buf):
            try:
                if modo == "txt":
                    C.processar(tmp, saida, im_padrao=im)
                else:
                    C.processar_sped(tmp, saida, im_padrao=im)
            except Exception as exc:
                print(f"\nERRO FATAL: {exc}")
        log  = buf.getvalue()
        data = b""
        if os.path.exists(saida):
            with open(saida, "rb") as fh:
                data = fh.read()

            if modo == "txt" and data:
                def _fix_linha(linha: str) -> str:
                    cs = linha.split(";")
                    if len(cs) != 46:
                        return linha

                    # Campo 3 (índice 2) – tipo de pessoa: 1=Física, 2=Jurídica
                    # Campo 4 (índice 3) – CNPJ do prestador (vazio quando é CPF/PF)
                    # Lookup pelo número da nota para obter o CPF quando o campo está vazio
                    _rinfo_pf = _ret_lookup.get(cs[17].strip(), {})
                    if not cs[3].strip():
                        cs[2] = "1"
                        if _rinfo_pf.get("cpf_emit"):
                            cs[3] = _rinfo_pf["cpf_emit"]

                    # Campo 5 (índice 4) – nome do prestador: remove caracteres especiais
                    # Cobre casos como "RUBEM GARCIA-05CP-CNPJ:60.048.261/0001-03"
                    _nome = "".join(
                        c for c in _ud.normalize("NFD", cs[4]) if ord(c) < 128
                    )
                    _nome = _re.sub(r"[^A-Za-z0-9 ]", " ", _nome)
                    cs[4] = _re.sub(r" {2,}", " ", _nome).strip()

                    # Campo 26 (índice 25) – descrição: remove acentos E pontuações
                    _desc = "".join(
                        c for c in _ud.normalize("NFD", cs[25]) if ord(c) < 128
                    )
                    _desc = _re.sub(r"[^A-Za-z0-9 ]", " ", _desc)
                    cs[25] = _re.sub(r" {2,}", " ", _desc).strip()

                    # Campo 30 (índice 29) – natureza: prestação em Fortaleza → "1"
                    if cs[28] == "2304400":
                        cs[29] = "1"

                    # Lookup pelo número da nota (campo 18 = índice 17)
                    _rinfo = _ret_lookup.get(cs[17].strip(), {})

                    # Campo 18 (índice 17) – número da nota
                    # nfse_xml_to_txt.py pode usar nDFSe (número interno),
                    # mas o número oficial exibido no DANFSe e reconhecido
                    # pelo portal é sempre o nNFSe. Substitui sempre por ele.
                    if _rinfo.get("nNFSe"):
                        cs[17] = _rinfo["nNFSe"]

                    # Campos 22/23 (índices 21/22) – mês e ano de competência
                    # nfse_xml_to_txt.py usa dhEmi; corrige pelo dCompet do XML
                    if _rinfo.get("comp_mes"):
                        cs[21] = _rinfo["comp_mes"]
                    if _rinfo.get("comp_ano"):
                        cs[22] = _rinfo["comp_ano"]

                    # Campo 21 (índice 20) – tipo recolhimento
                    # tpRetISSQN=2 → ISS retido pelo tomador
                    # ISS Fortaleza: campo 21=1 significa "retido" (não "2"!)
                    _iss_retido = _rinfo.get("tpRet") == "2"
                    if _iss_retido and cs[20] == "2":
                        cs[20] = "1"

                    if _iss_retido:
                        # Campo 25 (índice 24) – alíquota ISS em centésimos
                        # Fica logo após o CNAE. Ex.: pAliqAplic="2.00" → "200"
                        if not cs[24].strip() and _rinfo.get("aliq"):
                            try:
                                cs[24] = str(int(round(float(_rinfo["aliq"]) * 100)))
                            except Exception:
                                pass

                        # Campo 31 (índice 30) – valor ISS retido em centavos
                        # Ex.: vISSQN="6.84" → "684"
                        if not cs[30].strip() and _rinfo.get("vISS"):
                            try:
                                cs[30] = str(int(round(float(_rinfo["vISS"]) * 100)))
                            except Exception:
                                pass

                        # Campo 33 (índice 32) – valor do serviço em centavos
                        # nfse_xml_to_txt.py usa vLiq (líquido, já descontado o ISS);
                        # o portal exige o valor bruto (vBC) para calcular ISS corretamente.
                        if _rinfo.get("vBC"):
                            try:
                                cs[32] = str(int(round(float(_rinfo["vBC"]) * 100)))
                            except Exception:
                                pass

                        # Campo 44 (índice 43) – indicador de retenção ISS
                        # 0 = não retido (padrão)  |  1 = retido pelo tomador
                        cs[43] = "1"

                    # Campo 39 (índice 38) – PIS retido na fonte
                    if _rinfo.get("vPis") and not cs[38].strip():
                        try:
                            cs[38] = str(int(round(float(_rinfo["vPis"]) * 100)))
                        except Exception:
                            pass

                    # Campo 40 (índice 39) – COFINS retido na fonte
                    if _rinfo.get("vCofins") and not cs[39].strip():
                        try:
                            cs[39] = str(int(round(float(_rinfo["vCofins"]) * 100)))
                        except Exception:
                            pass

                    # Campo 41 (índice 40) – INSS retido (vRetCP no NFS-e Nacional)
                    if _rinfo.get("vINSS") and not cs[40].strip():
                        try:
                            cs[40] = str(int(round(float(_rinfo["vINSS"]) * 100)))
                        except Exception:
                            pass

                    # Campo 42 (índice 41) – CSLL retido na fonte
                    if _rinfo.get("vCSLL") and not cs[41].strip():
                        try:
                            cs[41] = str(int(round(float(_rinfo["vCSLL"]) * 100)))
                        except Exception:
                            pass

                    # Campo 43 (índice 42) – IRRF retido na fonte
                    if _rinfo.get("vIRRF") and not cs[42].strip():
                        try:
                            cs[42] = str(int(round(float(_rinfo["vIRRF"]) * 100)))
                        except Exception:
                            pass

                    return ";".join(cs)

                texto  = data.decode("utf-8")
                linhas = texto.split("\n")
                data   = "\n".join(
                    _fix_linha(l) if ";" in l else l
                    for l in linhas
                ).encode("utf-8")
    return data, log
