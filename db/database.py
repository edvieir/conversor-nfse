"""
db/database.py — Persistência SQLite
Tabelas: users (usuários), conversions (histórico de conversões)

Na primeira execução migra automaticamente o config.yaml existente.
Em produção (Render), use a variável de ambiente ADMIN_BOOTSTRAP=login:senha
para garantir que o admin exista após cada redeploy.
"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime, date

# Caminho do banco — pasta data/ na raiz do projeto
DB_PATH = Path(__file__).parent.parent / "data" / "conversor.db"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


# ── INICIALIZAÇÃO ────────────────────────────────────────────────────────────────

def init_db():
    """Cria as tabelas, migra config.yaml e garante o admin bootstrap."""
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT UNIQUE NOT NULL,
                name          TEXT NOT NULL,
                email         TEXT DEFAULT '',
                password_hash TEXT NOT NULL,
                role          TEXT DEFAULT 'user',
                created_at    TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS conversions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ts           TEXT NOT NULL,
                usuario      TEXT NOT NULL,
                modo         TEXT NOT NULL,
                qtd_arquivos INTEGER DEFAULT 0,
                sucesso      INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS certificados (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario       TEXT NOT NULL,
                cnpj          TEXT NOT NULL,
                razao_social  TEXT DEFAULT '',
                pfx_enc       BLOB NOT NULL,
                senha_enc     TEXT NOT NULL,
                criado_em     TEXT DEFAULT (datetime('now','localtime')),
                UNIQUE(usuario, cnpj)
            );
        """)
    _migrate_from_yaml()
    _bootstrap_admin()
    _bootstrap_users()


def _migrate_from_yaml():
    """Importa usuários do config.yaml se a tabela users estiver vazia."""
    cfg_path = Path(__file__).parent.parent / "config.yaml"
    if not cfg_path.exists():
        return
    with _conn() as con:
        count = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count > 0:
            return
    try:
        import yaml
        with open(cfg_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        usuarios = cfg.get("credentials", {}).get("usernames", {})
        with _conn() as con:
            for username, dados in usuarios.items():
                role = "admin" if username == "admin" else "user"
                con.execute(
                    "INSERT OR IGNORE INTO users "
                    "(username, name, email, password_hash, role) VALUES (?,?,?,?,?)",
                    (
                        username,
                        dados.get("name", username.title()),
                        dados.get("email", ""),
                        dados.get("password", ""),
                        role,
                    ),
                )
        print(f"[db] Migrados {len(usuarios)} usuário(s) do config.yaml")
    except Exception as exc:
        print(f"[db] Migração config.yaml falhou: {exc}")


def _bootstrap_admin():
    """
    Garante que existe ao menos um admin.
    Variável de ambiente: ADMIN_BOOTSTRAP=login:senha
    Útil no Render onde o filesystem é efêmero.
    """
    raw = os.environ.get("ADMIN_BOOTSTRAP", "").strip()
    if not raw or ":" not in raw:
        return
    with _conn() as con:
        count = con.execute(
            "SELECT COUNT(*) FROM users WHERE role='admin'"
        ).fetchone()[0]
        if count > 0:
            return
    import bcrypt
    username, senha = raw.split(":", 1)
    pw_hash = bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")
    with _conn() as con:
        con.execute(
            "INSERT OR IGNORE INTO users (username, name, email, password_hash, role) "
            "VALUES (?,?,?,?,?)",
            (username, username.title(), f"{username}@empresa.com", pw_hash, "admin"),
        )
    print(f"[db] Admin bootstrap: usuário '{username}' criado.")


def _bootstrap_users():
    """
    Garante que os usuários padrão existam a cada inicialização.
    Usa INSERT OR IGNORE — não sobrescreve senhas já alteradas pelo admin.
    Variável opcional USERS_BOOTSTRAP=login:senha:nome[:email] (separados por '|')
    permite adicionar usuários extras via painel do Render.
    """
    import bcrypt

    # ── Usuários fixos — criados automaticamente se não existirem ────────────
    _FIXOS = [
        # (username,  senha_inicial,  nome,               email)
        ("p&p",    "123456",    "P&P Contabilidade", "pp@empresa.com"),
        ("calebe", "calebe123", "Calebe",             "calebe@exemplo.com"),
    ]

    for username, senha, nome, email in _FIXOS:
        pw_hash = bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")
        with _conn() as con:
            con.execute(
                "INSERT OR IGNORE INTO users "
                "(username, name, email, password_hash, role) VALUES (?,?,?,?,?)",
                (username, nome, email, pw_hash, "user"),
            )
        print(f"[db] Bootstrap: '{username}' verificado/criado.")

    # ── Usuários extras via variável de ambiente (opcional) ──────────────────
    # Formato: USERS_BOOTSTRAP=login:senha:nome[:email]|login2:senha2:nome2
    raw = os.environ.get("USERS_BOOTSTRAP", "").strip()
    if not raw:
        return
    for entrada in raw.split("|"):
        partes = entrada.strip().split(":", 3)
        if len(partes) < 3:
            continue
        username = partes[0].strip()
        senha    = partes[1].strip()
        nome     = partes[2].strip()
        email    = partes[3].strip() if len(partes) == 4 else f"{username}@empresa.com"
        if not username or not senha:
            continue
        pw_hash = bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")
        with _conn() as con:
            con.execute(
                "INSERT OR IGNORE INTO users "
                "(username, name, email, password_hash, role) VALUES (?,?,?,?,?)",
                (username, nome, email, pw_hash, "user"),
            )
        print(f"[db] Bootstrap extra: '{username}' verificado/criado.")


# ── CRUD — USUÁRIOS ──────────────────────────────────────────────────────────────

def get_user(username: str) -> dict | None:
    with _conn() as con:
        row = con.execute(
            "SELECT username, name, email, password_hash, role "
            "FROM users WHERE username = ?",
            (username.strip().lower(),),
        ).fetchone()
    return dict(row) if row else None


def list_users() -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT username, name, email, role, created_at "
            "FROM users ORDER BY role DESC, created_at"
        ).fetchall()
    return [dict(r) for r in rows]


def create_user(username: str, name: str, email: str,
                password_hash: str, role: str = "user") -> bool:
    try:
        with _conn() as con:
            con.execute(
                "INSERT INTO users (username, name, email, password_hash, role) "
                "VALUES (?,?,?,?,?)",
                (username.strip().lower(), name.strip(), email.strip(), password_hash, role),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def delete_user(username: str):
    with _conn() as con:
        con.execute("DELETE FROM users WHERE username = ?", (username,))


def update_password(username: str, new_hash: str):
    with _conn() as con:
        con.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (new_hash, username),
        )


# ── CRUD — CONVERSÕES ────────────────────────────────────────────────────────────

def log_conversion(usuario: str, modo: str, qtd: int, sucesso: bool):
    ts = datetime.now().isoformat()
    with _conn() as con:
        con.execute(
            "INSERT INTO conversions (ts, usuario, modo, qtd_arquivos, sucesso) "
            "VALUES (?,?,?,?,?)",
            (ts, usuario, modo.upper(), qtd, int(sucesso)),
        )


def get_conversions(limit: int = 500) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT ts, usuario, modo, qtd_arquivos AS arquivos, sucesso "
            "FROM conversions ORDER BY ts DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── CRUD — CERTIFICADOS ──────────────────────────────────────────────────────────

def salvar_certificado(usuario: str, cnpj: str, razao_social: str,
                       pfx_bytes: bytes, senha: str) -> bool:
    from core.crypto import encrypt_bytes, encrypt_str
    pfx_enc   = encrypt_bytes(pfx_bytes)
    senha_enc = encrypt_str(senha)
    try:
        with _conn() as con:
            con.execute(
                """INSERT INTO certificados (usuario, cnpj, razao_social, pfx_enc, senha_enc)
                   VALUES (?,?,?,?,?)
                   ON CONFLICT(usuario, cnpj) DO UPDATE SET
                     razao_social=excluded.razao_social,
                     pfx_enc=excluded.pfx_enc,
                     senha_enc=excluded.senha_enc,
                     criado_em=datetime('now','localtime')""",
                (usuario, cnpj, razao_social, pfx_enc, senha_enc),
            )
        return True
    except Exception as e:
        print(f"[db] salvar_certificado erro: {e}")
        return False


def listar_certificados(usuario: str) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT id, cnpj, razao_social, criado_em FROM certificados "
            "WHERE usuario = ? ORDER BY razao_social",
            (usuario,),
        ).fetchall()
    return [dict(r) for r in rows]


def carregar_certificado(usuario: str, cnpj: str) -> tuple[bytes, str] | None:
    """Retorna (pfx_bytes, senha) descriptografados, ou None se não encontrado."""
    from core.crypto import decrypt_bytes, decrypt_str
    with _conn() as con:
        row = con.execute(
            "SELECT pfx_enc, senha_enc FROM certificados WHERE usuario=? AND cnpj=?",
            (usuario, cnpj),
        ).fetchone()
    if not row:
        return None
    try:
        pfx   = decrypt_bytes(bytes(row["pfx_enc"]))
        senha = decrypt_str(row["senha_enc"])
        return pfx, senha
    except Exception as e:
        print(f"[db] carregar_certificado erro: {e}")
        return None


def remover_certificado(usuario: str, cnpj: str):
    with _conn() as con:
        con.execute(
            "DELETE FROM certificados WHERE usuario=? AND cnpj=?",
            (usuario, cnpj),
        )


def get_stats() -> dict:
    hoje = str(date.today())
    mes  = hoje[:7]
    with _conn() as con:
        total  = con.execute("SELECT COUNT(*) FROM conversions").fetchone()[0]
        d_hoje = con.execute(
            "SELECT COUNT(*) FROM conversions WHERE ts LIKE ?", (f"{hoje}%",)
        ).fetchone()[0]
        d_mes  = con.execute(
            "SELECT COUNT(*) FROM conversions WHERE ts LIKE ?", (f"{mes}%",)
        ).fetchone()[0]
        xmls   = con.execute(
            "SELECT COALESCE(SUM(qtd_arquivos),0) FROM conversions WHERE sucesso=1"
        ).fetchone()[0]
        txt_c  = con.execute(
            "SELECT COUNT(*) FROM conversions WHERE modo='TXT' AND sucesso=1"
        ).fetchone()[0]
        xlsx_c = con.execute(
            "SELECT COUNT(*) FROM conversions WHERE modo='XLSX' AND sucesso=1"
        ).fetchone()[0]
        by_usr = con.execute(
            "SELECT usuario, COUNT(*) FROM conversions GROUP BY usuario ORDER BY 2 DESC"
        ).fetchall()
        by_day = con.execute(
            "SELECT DATE(ts) AS d, COUNT(*) FROM conversions "
            "WHERE ts >= date('now','-14 days') GROUP BY d ORDER BY d"
        ).fetchall()
    return {
        "total":       total,
        "hoje":        d_hoje,
        "mes":         d_mes,
        "xmls":        xmls,
        "txt":         txt_c,
        "xlsx":        xlsx_c,
        "por_usuario": {r[0]: r[1] for r in by_usr},
        "por_dia":     {r[0]: r[1] for r in by_day},
    }
