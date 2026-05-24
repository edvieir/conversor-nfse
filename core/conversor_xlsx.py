"""
core/conversor_xlsx.py — Conversão XML → XLSX (SPED GOV)
Lógica copiada integralmente de app_web.py — NENHUMA linha de conversão alterada.
Adicionado: st.progress() no loop principal para feedback visual.
"""

import sys
import io
import os
import tempfile
import contextlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import nfse_xml_to_txt as C


def processar_xlsx_sped(uploaded_files, im: str, competencia_filtro: str = ""):
    """Gera XLSX no layout exato do SPED GOV — aba 'Serviços Tomados', 43 colunas."""
    import glob as _glob
    import openpyxl
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter
    import streamlit as st

    # Cabeçalhos e larguras exatas do SPED GOV
    COLUNAS = [
        ("Tipo Doc.",                       24.14),
        ("Número",                          10.28),
        ("Código de Verificação",           23.57),
        ("Competência",                     14.57),
        ("Data",                            11.42),
        ("Vencimento",                      13.42),
        ("Número RPS",                      18.42),
        ("Série RPS",                       11.14),
        ("Tipo RPS",                        10.28),
        ("Natureza da Operação",            27.71),
        ("Regime Especial Tributação",      52.14),
        ("Operação Simples Nacional",       29.28),
        ("Incentivador Cultural",           22.85),
        ("Item da Lista",                   14.57),
        ("CNAE",                           123.14),
        ("ART",                              5.28),
        ("Código Obra",                     13.85),
        ("Número Empenho",                  19.42),
        ("Discriminação dos Serviços",     141.14),
        ("Valor dos Serviços",              20.28),
        ("Deduções Permitidas em Lei",      30.42),
        ("Desconto Condicionado",           25.28),
        ("Desconto Incondicionado",         27.00),
        ("Retenções Federais",              21.28),
        ("Outras Retenções",               19.42),
        ("PIS",                              4.42),
        ("COFINS",                           8.85),
        ("IRRF",                             5.71),
        ("CSLL",                             6.14),
        ("INSS",                             5.85),
        ("Base de Cálculo",                 17.28),
        ("Alíquota",                         9.85),
        ("Local da Prestação",              22.14),
        ("ISS Retido",                      11.71),
        ("Valor do ISS",                    13.85),
        ("Valor Líquido",                   14.85),
        ("Status Doc.",                     13.00),
        ("Inscrição Prestador",             21.14),
        ("CPF/CNPJ Prestador",              21.42),
        ("Razão Social/Nome do Prestador",  58.57),
        ("Escrituração",                    13.85),
        ("Origem",                           9.71),
        ("Status Aceite",                   14.85),
    ]

    IBGE_FORTALEZA = "2304400"

    def _float(v):
        try:
            return float(v) if v else 0.0
        except Exception:
            return 0.0

    def _str(v):
        return str(v).strip() if v else ""

    def _data_fmt(iso, fmt):
        if not iso:
            return ""
        data_part = iso[:10]
        try:
            partes = data_part.split("-")
            if fmt == "mes":
                return f"{partes[1]}/{partes[0]}"
            else:
                return f"{partes[2]}/{partes[1]}/{partes[0]}"
        except Exception:
            return iso

    def _local_prestacao(d):
        uf   = _str(d.get("uf", ""))
        xLP  = _str(d.get("xLP", ""))
        cLP  = _str(d.get("cLP", ""))
        xMun = _str(d.get("xMun", ""))
        nome_mun = (
            xLP
            or getattr(C, "IBGE_TO_NOME", {}).get(cLP, "")
            or xMun
        )
        if nome_mun and uf:
            return f"{nome_mun.upper()} - {uf.upper()}"
        return nome_mun.upper() if nome_mun else ""

    def _cnae_desc(cnae9):
        desc = getattr(C, "CNAE9_TO_DESC", {}).get(cnae9, "")
        return f"{cnae9} - {desc}" if desc else cnae9

    def _extrair_fed(xml_path):
        """
        Extrai todas as retenções federais diretamente do XML.
        parse_nfse() não mapeia corretamente PIS/COFINS/IRRF/CSLL no modelo nacional.
        """
        import xml.etree.ElementTree as ET

        def _v(root, *tags):
            for tag in tags:
                el = next((e for e in root.iter() if e.tag.endswith(tag)), None)
                if el is not None and el.text:
                    try:
                        return float(el.text.strip())
                    except (ValueError, AttributeError):
                        pass
            return 0.0

        try:
            root = ET.parse(xml_path).getroot()
            return (
                _v(root, "vPis",    "vPIS"),
                _v(root, "vCofins", "vCOFINS"),
                _v(root, "vRetIRRF"),
                _v(root, "vRetCSLL"),
                _v(root, "vINSS"),
            )
        except Exception:
            return 0.0, 0.0, 0.0, 0.0, 0.0

    def _competencia_xml(xml_path):
        import xml.etree.ElementTree as ET
        try:
            root = ET.parse(xml_path).getroot()
            el = next((e for e in root.iter() if e.tag.endswith("dCompet")), None)
            if el is not None and el.text:
                p = el.text.strip()[:7].split("-")
                return f"{p[1]}/{p[0]}"
        except Exception:
            pass
        return ""

    with tempfile.TemporaryDirectory() as tmp:
        for uf_file in uploaded_files:
            uf_file.seek(0)
            with open(os.path.join(tmp, uf_file.name), "wb") as fh:
                fh.write(uf_file.read())

        arquivos = sorted(_glob.glob(os.path.join(tmp, "*.xml")))

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Serviços Tomados"

        header_fill = PatternFill(fill_type="solid", fgColor="C0C0C0")
        header_font = Font(bold=True, size=11)

        for col_idx, (titulo, largura) in enumerate(COLUNAS, 1):
            cell = ws.cell(row=1, column=col_idx, value=titulo)
            cell.font  = header_font
            cell.fill  = header_fill
            letra = get_column_letter(col_idx)
            ws.column_dimensions[letra].width = largura

        buf   = io.StringIO()
        total = 0
        erros = []
        n_arqs = max(len(arquivos), 1)

        # Barra de progresso no Streamlit
        _progress = st.progress(0, text="Iniciando processamento...")

        with contextlib.redirect_stdout(buf):
            for idx, xml_path in enumerate(arquivos):
                nome_arq = os.path.basename(xml_path)
                _progress.progress(
                    (idx + 1) / n_arqs,
                    text=f"Processando {idx + 1}/{len(arquivos)}: {nome_arq}",
                )
                try:
                    if competencia_filtro:
                        comp = _competencia_xml(xml_path)
                        if comp and comp != competencia_filtro:
                            print(f"  SKIP {nome_arq}: competência {comp} ≠ {competencia_filtro}")
                            continue

                    d = C.parse_nfse(xml_path)
                    if im:
                        d["im"] = im

                    cnae9, item, aliq_cnae = C.resolver_cnae9(d)
                    dhEmi = _str(d.get("dhEmi", ""))

                    vS   = _float(d.get("vS"))
                    vISS = _float(d.get("vISS"))
                    vPIS, vCOFINS, vIRRF, vCSLL, vINSS = _extrair_fed(xml_path)
                    aliq   = _float(d.get("aliq")) or float(aliq_cnae or 0)
                    tpRet  = _str(d.get("tpRet", "1"))
                    iss_retido = (tpRet == "2")

                    ret_federais  = vPIS + vCOFINS + vCSLL
                    valor_iss_col = vISS if iss_retido else 0

                    ws.append([
                        "NFS-e de Outro Município",
                        _str(d.get("nDFSe")),
                        None,
                        _data_fmt(dhEmi, "mes"),
                        _data_fmt(dhEmi, "dia"),
                        "",
                        "",
                        "",
                        "",
                        "Tributação Fora do Município",
                        "",
                        "Não",
                        None,
                        item,
                        _cnae_desc(cnae9),
                        "",
                        "",
                        "",
                        _str(d.get("desc")),
                        vS,
                        "",
                        "",
                        "",
                        ret_federais,
                        "",
                        vPIS    if vPIS    else "",
                        vCOFINS if vCOFINS else "",
                        vIRRF   if vIRRF   else "",
                        vCSLL   if vCSLL   else "",
                        vINSS   if vINSS   else "",
                        vS,
                        aliq,
                        _local_prestacao(d),
                        "Sim" if iss_retido else "Não",
                        valor_iss_col,
                        vS,
                        "NORMAL",
                        "",
                        _str(d.get("cnpj")),
                        _str(d.get("nome")),
                        "Atual",
                        "Prestador",
                        "Não informada",
                    ])

                    r = ws.max_row
                    for col_mon in [20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 35, 36]:
                        ws.cell(row=r, column=col_mon).number_format = '#,##0.00'
                    ws.cell(row=r, column=32).number_format = '0.00'

                    total += 1
                    print(f"  OK   {nome_arq}")
                    print(f"       NFSe {d.get('nDFSe','')} | {d.get('nome','')[:35]}")

                except Exception as exc:
                    erros.append((nome_arq, str(exc)))
                    print(f"  ERRO {nome_arq}: {exc}")

        _progress.empty()

        print(f"\n  Processadas: {total} nota(s)")
        if erros:
            print(f"  Com erro:    {len(erros)}")
            for n, e in erros:
                print(f"    - {n}: {e}")

        log   = buf.getvalue()
        saida = os.path.join(tmp, "resultado.xlsx")
        wb.save(saida)

        data = b""
        if os.path.exists(saida):
            with open(saida, "rb") as fh:
                data = fh.read()

    return data, log
