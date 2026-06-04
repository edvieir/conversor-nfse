"""
core/crypto.py — Criptografia simétrica para armazenar certificados .pfx
Usa Fernet (AES-128-CBC + HMAC-SHA256).
Chave lida da variável de ambiente CERT_ENCRYPTION_KEY (base64url 32 bytes).
Se não definida, gera uma chave estável baseada no SECRET_KEY do Render.
"""

import os
import base64
import hashlib
from cryptography.fernet import Fernet


def _get_fernet() -> Fernet:
    raw = os.environ.get("CERT_ENCRYPTION_KEY", "").strip()
    if raw:
        # Aceita chave Fernet direta (44 chars base64url) ou qualquer string >= 32 chars
        try:
            return Fernet(raw.encode() if isinstance(raw, str) else raw)
        except Exception:
            pass
    # Deriva chave de SECRET_KEY ou fallback fixo
    secret = os.environ.get("SECRET_KEY", "conversor-nfse-default-key-change-me")
    key32  = hashlib.sha256(secret.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key32)
    return Fernet(fernet_key)


def encrypt_bytes(data: bytes) -> bytes:
    return _get_fernet().encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    return _get_fernet().decrypt(token)


def encrypt_str(s: str) -> str:
    return encrypt_bytes(s.encode("utf-8")).decode("ascii")


def decrypt_str(token: str) -> str:
    return decrypt_bytes(token.encode("ascii")).decode("utf-8")
