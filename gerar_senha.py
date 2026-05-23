#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuração de Usuários — Conversor NFSe Web
=============================================
Execute UMA VEZ (ou sempre que quiser adicionar/remover usuários):

    python gerar_senha.py

O script cria/atualiza o arquivo config.yaml com as credenciais.
Depois disso, basta rodar:

    streamlit run app_web.py
"""

import sys
import yaml
import getpass
from pathlib import Path

CONFIG = Path(__file__).parent / "config.yaml"


def gerar_hash(senha: str) -> str:
    """Gera hash bcrypt da senha."""
    try:
        import bcrypt
        return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
    except ImportError:
        pass

    try:
        import streamlit_authenticator as stauth
        # API 0.3.x
        return stauth.utilities.hasher.Hasher([senha]).generate()[0]
    except Exception:
        pass

    try:
        import streamlit_authenticator as stauth
        # API 0.2.x
        return stauth.Hasher([senha]).generate()[0]
    except Exception:
        pass

    raise RuntimeError(
        "Não foi possível gerar o hash da senha.\n"
        "Instale as dependências:  pip install -r requirements.txt"
    )


def carregar_config():
    """Carrega config.yaml existente ou cria estrutura padrão."""
    if CONFIG.exists():
        with open(CONFIG, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        # Garantir estrutura mínima
        cfg.setdefault("credentials", {}).setdefault("usernames", {})
        cfg.setdefault("cookie", {})
        cfg["cookie"].setdefault("expiry_days", 30)
        cfg["cookie"].setdefault("key", "conversor_nfse_chave_secreta_2026")
        cfg["cookie"].setdefault("name", "conversor_nfse_cookie")
        return cfg
    else:
        return {
            "credentials": {"usernames": {}},
            "cookie": {
                "expiry_days": 30,
                "key": "conversor_nfse_chave_secreta_2026",
                "name": "conversor_nfse_cookie",
            },
        }


def salvar_config(cfg):
    with open(CONFIG, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def listar_usuarios(cfg):
    usuarios = cfg["credentials"]["usernames"]
    if not usuarios:
        print("  (nenhum usuário cadastrado)")
    else:
        for u, d in usuarios.items():
            print(f"  • {u:<15}  {d.get('name',''):<25}  {d.get('email','')}")


def menu():
    print()
    print("═" * 52)
    print("  CONVERSOR NFSe — Gerenciador de Usuários")
    print("═" * 52)

    cfg = carregar_config()

    while True:
        print()
        print("Usuários cadastrados:")
        listar_usuarios(cfg)
        print()
        print("Opções:")
        print("  [1] Adicionar / atualizar usuário")
        print("  [2] Remover usuário")
        print("  [3] Sair")
        print()

        op = input("Escolha: ").strip()

        if op == "1":
            print()
            username = input("  Nome de usuário (login): ").strip()
            if not username:
                print("  ❌  Nome de usuário não pode ser vazio.")
                continue

            name  = input("  Nome completo:            ").strip() or username
            email = input("  E-mail:                   ").strip() or f"{username}@exemplo.com"

            print("  Senha: ", end="", flush=True)
            try:
                senha = getpass.getpass("")
            except Exception:
                senha = input("")

            if len(senha) < 6:
                print("  ❌  Senha deve ter pelo menos 6 caracteres.")
                continue

            print("  Gerando hash da senha…", end=" ", flush=True)
            try:
                hashed = gerar_hash(senha)
            except RuntimeError as e:
                print(f"\n  ❌  {e}")
                continue
            print("OK")

            cfg["credentials"]["usernames"][username] = {
                "name": name,
                "email": email,
                "password": hashed,
                "failed_login_attempts": 0,
                "logged_in": False,
            }
            salvar_config(cfg)
            print(f"  ✅  Usuário '{username}' salvo com sucesso em config.yaml")

        elif op == "2":
            username = input("  Nome de usuário a remover: ").strip()
            if username in cfg["credentials"]["usernames"]:
                del cfg["credentials"]["usernames"][username]
                salvar_config(cfg)
                print(f"  ✅  Usuário '{username}' removido.")
            else:
                print(f"  ❌  Usuário '{username}' não encontrado.")

        elif op == "3":
            print()
            print("  Para iniciar o sistema web, execute:")
            print("    streamlit run app_web.py")
            print()
            break
        else:
            print("  Opção inválida.")


if __name__ == "__main__":
    try:
        menu()
    except KeyboardInterrupt:
        print("\n\n  Cancelado pelo usuário.")
        sys.exit(0)
