"""
core/nfse_status.py — Utilitário portátil de classificação de NFS-e Nacional

Pode ser copiado para qualquer sistema que precise determinar se uma
NFS-e do padrão NFS-e Nacional (sped.fazenda.gov.br) está autorizada
ou cancelada a partir do conteúdo do XML.

Dependências: apenas a biblioteca padrão do Python (xml.etree.ElementTree).

──────────────────────────────────────────────────────────────────────────────
TABELA DE STATUS (cStat) — NFS-e Nacional
──────────────────────────────────────────────────────────────────────────────
  100  NFS-e Autorizada          (emitente regular — prefeitura/emissor web)
  101  NFS-e Cancelada           (emitente regular)
  107  NFS-e do MEI Gerada       (MEI NFS-e Nacional — AUTORIZADA, não cancelada)
  108  NFS-e do MEI Cancelada    (MEI NFS-e Nacional — cancelada)
──────────────────────────────────────────────────────────────────────────────

ATENÇÃO: cStat=107 significa AUTORIZADA (nota do MEI), NÃO cancelada.
         Tratá-la como cancelamento é um erro comum.

──────────────────────────────────────────────────────────────────────────────
LIMITE IMPORTANTE DESTA VERIFICAÇÃO
──────────────────────────────────────────────────────────────────────────────
O XML da NFS-e NÃO é reescrito quando a nota é cancelada: ela permanece com
cStat=100 para sempre. Na distribuição de DFe o cancelamento chega como um
DOCUMENTO SEPARADO, com raiz <evento>, que aponta a nota em <chNFSe> e traz o
código do evento como nome do elemento (ex: <e101101>).

Ou seja: olhando só o XML da nota é IMPOSSÍVEL saber que ela foi cancelada.
Quem baixa da API deve cruzar os eventos — é o que core/api_nfse.py faz.

Para XMLs já baixados e soltos, o único sinal disponível é o nome do arquivo:
o downloader grava as canceladas com o sufixo _CANC. Daí `nome_indica_cancelada`.
"""

import xml.etree.ElementTree as ET

# Sufixo que core/api_nfse.py aplica ao nome dos arquivos na pasta cancelados/
SUFIXO_ARQUIVO_CANCELADO = "_CANC"

# Códigos que indicam nota AUTORIZADA
CSTAT_AUTORIZADO = {
    "100",  # NFS-e Autorizada (emitente regular)
    "107",  # NFS-e do MEI Gerada (MEI NFS-e Nacional — também autorizada)
}

# Códigos que indicam nota CANCELADA
CSTAT_CANCELADO = {
    "101",  # NFS-e Cancelada (emitente regular)
    "108",  # NFS-e do MEI Cancelada
}


def is_cancelada(root: ET.Element) -> bool:
    """
    Recebe o elemento raiz de um XML NFS-e Nacional já parseado e retorna
    True se a nota estiver cancelada.

    Dois filtros independentes — basta um ser verdadeiro:

      Filtro 1 (estrutural): presença do elemento <nfseCanc> no XML.
                             A API envia esse elemento em eventos de cancelamento.

      Filtro 2 (cStat):      valor em CSTAT_CANCELADO {101, 108}.

    Notas com cStat=107 (NFS-e do MEI Gerada) são tratadas como AUTORIZADAS.
    """
    # Filtro 1 — elemento de cancelamento explícito
    if any(e.tag.split("}")[-1] == "nfseCanc" for e in root.iter()):
        return True

    # Filtro 2 — cStat com código de cancelamento conhecido
    el_cstat = next(
        (e for e in root.iter() if e.tag.split("}")[-1] == "cStat"),
        None,
    )
    if el_cstat is not None and el_cstat.text:
        if el_cstat.text.strip() in CSTAT_CANCELADO:
            return True

    return False


def is_cancelada_bytes(xml_bytes: bytes) -> bool:
    """
    Versão que recebe o conteúdo bruto do arquivo XML em bytes.
    Retorna False em caso de erro de parse (nota é mantida como autorizada).
    """
    try:
        root = ET.fromstring(xml_bytes)
        return is_cancelada(root)
    except ET.ParseError:
        return False


def nome_indica_cancelada(nome_arquivo: str) -> bool:
    """
    True se o NOME do arquivo marcar a nota como cancelada (sufixo _CANC).

    É o único sinal que sobrevive quando o XML sai do ZIP e passa a circular
    solto, já que o conteúdo da nota nunca registra o cancelamento.
    Aceita caminho completo ou apenas o nome.
    """
    if not nome_arquivo:
        return False
    base = nome_arquivo.replace("\\", "/").rsplit("/", 1)[-1]
    raiz = base.rsplit(".", 1)[0]
    return raiz.upper().endswith(SUFIXO_ARQUIVO_CANCELADO)


def is_cancelada_arquivo(xml_path: str) -> bool:
    """
    Versão que recebe o caminho do arquivo XML no disco.
    Considera tanto o conteúdo quanto o sufixo _CANC no nome.
    Retorna False em caso de erro de leitura ou parse.
    """
    if nome_indica_cancelada(xml_path):
        return True
    try:
        root = ET.parse(xml_path).getroot()
        return is_cancelada(root)
    except Exception:
        return False


def status_nota(root: ET.Element) -> str:
    """
    Retorna uma string descritiva do status da nota:
      'cancelada'  — nota cancelada (cStat 101/108 ou elemento nfseCanc)
      'autorizada' — nota autorizada (cStat 100 ou 107)
      'desconhecido' — cStat não reconhecido (tratar como autorizada por segurança)
    """
    if is_cancelada(root):
        return "cancelada"

    el_cstat = next(
        (e for e in root.iter() if e.tag.split("}")[-1] == "cStat"),
        None,
    )
    if el_cstat is not None and el_cstat.text:
        cstat = el_cstat.text.strip()
        if cstat in CSTAT_AUTORIZADO:
            return "autorizada"
        return "desconhecido"

    return "autorizada"


# ──────────────────────────────────────────────────────────────────────────────
# Uso como script standalone (python nfse_status.py arquivo.xml ...)
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso: python nfse_status.py arquivo1.xml [arquivo2.xml ...]")
        sys.exit(1)

    for path in sys.argv[1:]:
        try:
            root = ET.parse(path).getroot()
            el_cstat = next(
                (e for e in root.iter() if e.tag.split("}")[-1] == "cStat"), None
            )
            cstat_val = el_cstat.text.strip() if el_cstat is not None and el_cstat.text else "?"
            resultado = status_nota(root)
            print(f"{path}  |  cStat={cstat_val}  |  {resultado.upper()}")
        except Exception as e:
            print(f"{path}  |  ERRO: {e}")
