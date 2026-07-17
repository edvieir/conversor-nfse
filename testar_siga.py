"""
Script manual para testar o login e download via core/siga_sefaz.py
contra o SIGA real, usando um certificado ja cadastrado no banco do app.

Uso:
    python testar_siga.py <usuario> <cnpj>

Ex.: python testar_siga.py ednaldo 37787770000136
"""
import sys

from db.database import carregar_certificado
from core import siga_sefaz


def main():
    if len(sys.argv) != 3:
        print("Uso: python testar_siga.py <usuario> <cnpj>")
        sys.exit(1)

    usuario, cnpj = sys.argv[1], sys.argv[2]
    cert = carregar_certificado(usuario, cnpj)
    if not cert:
        print(f"Nenhum certificado encontrado para usuario={usuario} cnpj={cnpj}")
        sys.exit(1)

    pfx_bytes, senha = cert
    sessao = siga_sefaz._sessao(pfx_bytes, senha)

    print("Tentando login (OIDC + certificado)...")
    try:
        token_resp = siga_sefaz.login(sessao)
    except Exception as e:
        print(f"FALHOU no login: {e}")
        sys.exit(1)

    token = token_resp["access_token"]
    print(f"Login OK. access_token (primeiros 30 chars): {token[:30]}...")

    print("\nSolicitando download de NF-e do último mês...")
    solicitacao_id = siga_sefaz.solicitar_download(
        sessao, token, cnpj, "NF_E",
        dat_referencia=["2026-06"],
    )
    print(f"Solicitação criada: {solicitacao_id}")

    print("Aguardando conclusão...")
    conteudo = siga_sefaz.aguardar_e_baixar(sessao, token, solicitacao_id)
    out_path = f"siga_nfe_{cnpj}.xlsx"
    with open(out_path, "wb") as f:
        f.write(conteudo)
    print(f"Arquivo salvo em {out_path} ({len(conteudo)} bytes)")


if __name__ == "__main__":
    main()
