"""
db/database.py — Persistência PostgreSQL (Supabase)
Tabelas: users, conversions, certificados

Variável de ambiente obrigatória em produção:
  DATABASE_URL=postgresql://postgres:SENHA@db.XXX.supabase.co:5432/postgres

Em desenvolvimento local, se DATABASE_URL não estiver definida, usa SQLite como fallback.
"""

import os
from datetime import datetime, date
from contextlib import contextmanager

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# ── Backend: PostgreSQL ou SQLite (fallback local) ───────────────────────────

if DATABASE_URL:
    import psycopg2
    import psycopg2.extras

    @contextmanager
    def _conn():
        con = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    _PG = True
else:
    import sqlite3
    from pathlib import Path

    _DB_PATH = Path(__file__).parent.parent / "data" / "conversor.db"

    @contextmanager
    def _conn():
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    _PG = False


def _exec(sql: str, params=(), fetch_one=False, fetch_all=False):
    """Execute a single statement and optionally fetch results."""
    with _conn() as con:
        cur = con.cursor()
        cur.execute(sql, params)
        if fetch_one:
            row = cur.fetchone()
            return dict(row) if row else None
        if fetch_all:
            rows = cur.fetchall()
            return [dict(r) for r in rows]
        return cur.rowcount


# ── INICIALIZAÇÃO ─────────────────────────────────────────────────────────────

def init_db():
    """Cria as tabelas e garante os usuários bootstrap."""
    if _PG:
        _init_pg()
    else:
        _init_sqlite()
    _bootstrap_admin()
    _bootstrap_users()


def _init_pg():
    with _conn() as con:
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            SERIAL PRIMARY KEY,
                username      TEXT UNIQUE NOT NULL,
                name          TEXT NOT NULL,
                email         TEXT DEFAULT '',
                password_hash TEXT NOT NULL,
                role          TEXT DEFAULT 'user',
                permissoes    TEXT DEFAULT 'conversor,baixar_xmls,certificados,milhao,dashboard',
                created_at    TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS conversions (
                id           SERIAL PRIMARY KEY,
                ts           TEXT NOT NULL,
                usuario      TEXT NOT NULL,
                modo         TEXT NOT NULL,
                qtd_arquivos INTEGER DEFAULT 0,
                sucesso      INTEGER DEFAULT 1
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS certificados (
                id            SERIAL PRIMARY KEY,
                usuario       TEXT NOT NULL,
                cnpj          TEXT NOT NULL,
                razao_social  TEXT DEFAULT '',
                pfx_enc       BYTEA NOT NULL,
                senha_enc     TEXT NOT NULL,
                criado_em     TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(usuario, cnpj)
            )
        """)
        cur.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS
            permissoes TEXT DEFAULT 'conversor,baixar_xmls,certificados,milhao,dashboard'
        """)
        cur.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS
            validade DATE DEFAULT NULL
        """)


def _init_sqlite():
    with _conn() as con:
        cur = con.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT UNIQUE NOT NULL,
                name          TEXT NOT NULL,
                email         TEXT DEFAULT '',
                password_hash TEXT NOT NULL,
                role          TEXT DEFAULT 'user',
                permissoes    TEXT DEFAULT 'conversor,baixar_xmls,certificados,milhao,dashboard',
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
    try:
        _exec("ALTER TABLE users ADD COLUMN permissoes TEXT DEFAULT 'conversor,baixar_xmls,certificados,milhao,dashboard'")
    except Exception:
        pass
    try:
        _exec("ALTER TABLE users ADD COLUMN validade DATE DEFAULT NULL")
    except Exception:
        pass


def _bootstrap_admin():
    raw = os.environ.get("ADMIN_BOOTSTRAP", "").strip()
    if not raw or ":" not in raw:
        return
    count = _exec("SELECT COUNT(*) AS n FROM users WHERE role='admin'", fetch_one=True)
    if count and count.get("n", count.get("count(*)", 0)) > 0:
        return
    import bcrypt
    username, senha = raw.split(":", 1)
    pw_hash = bcrypt.hashpw(senha.encode(), bcrypt.gensalt(12)).decode()
    ph = "%s" if _PG else "?"
    try:
        _exec(
            f"INSERT INTO users (username, name, email, password_hash, role) VALUES ({ph},{ph},{ph},{ph},{ph})",
            (username, username.title(), f"{username}@empresa.com", pw_hash, "admin"),
        )
        print(f"[db] Admin bootstrap: '{username}' criado.")
    except Exception:
        pass


def _bootstrap_users():
    import bcrypt

    _FIXOS = [
        ("p&p",    "123456",    "P&P Contabilidade", "pp@empresa.com"),
        ("calebe", "calebe123", "Calebe",             "calebe@exemplo.com"),
    ]

    for username, senha, nome, email in _FIXOS:
        pw_hash = bcrypt.hashpw(senha.encode(), bcrypt.gensalt(12)).decode()
        if _PG:
            sql = (
                "INSERT INTO users (username, name, email, password_hash, role) "
                "VALUES (%s,%s,%s,%s,%s) ON CONFLICT (username) DO NOTHING"
            )
        else:
            sql = (
                "INSERT OR IGNORE INTO users "
                "(username, name, email, password_hash, role) VALUES (?,?,?,?,?)"
            )
        try:
            _exec(sql, (username, nome, email, pw_hash, "user"))
        except Exception:
            pass
        print(f"[db] Bootstrap: '{username}' verificado/criado.")

    raw = os.environ.get("USERS_BOOTSTRAP", "").strip()
    if not raw:
        return
    for entrada in raw.split("|"):
        partes = entrada.strip().split(":", 3)
        if len(partes) < 3:
            continue
        u = partes[0].strip()
        s = partes[1].strip()
        n = partes[2].strip()
        e = partes[3].strip() if len(partes) == 4 else f"{u}@empresa.com"
        if not u or not s:
            continue
        pw_hash = bcrypt.hashpw(s.encode(), bcrypt.gensalt(12)).decode()
        if _PG:
            sql = (
                "INSERT INTO users (username, name, email, password_hash, role) "
                "VALUES (%s,%s,%s,%s,%s) ON CONFLICT (username) DO NOTHING"
            )
        else:
            sql = (
                "INSERT OR IGNORE INTO users "
                "(username, name, email, password_hash, role) VALUES (?,?,?,?,?)"
            )
        try:
            _exec(sql, (u, n, e, pw_hash, "user"))
        except Exception:
            pass
        print(f"[db] Bootstrap extra: '{u}' verificado/criado.")


# ── CRUD — USUÁRIOS ───────────────────────────────────────────────────────────

def get_user(username: str) -> dict | None:
    ph = "%s" if _PG else "?"
    return _exec(
        f"SELECT username, name, email, password_hash, role, validade FROM users WHERE username = {ph}",
        (username.strip().lower(),),
        fetch_one=True,
    )


def list_users() -> list[dict]:
    return _exec(
        "SELECT username, name, email, role, created_at, validade FROM users ORDER BY role DESC, created_at",
        fetch_all=True,
    )


def create_user(username: str, name: str, email: str,
                password_hash: str, role: str = "user",
                validade=None) -> bool:
    ph = "%s" if _PG else "?"
    try:
        _exec(
            f"INSERT INTO users (username, name, email, password_hash, role, validade) VALUES ({ph},{ph},{ph},{ph},{ph},{ph})",
            (username.strip().lower(), name.strip(), email.strip(), password_hash, role, validade),
        )
        return True
    except Exception:
        return False


def update_validade(username: str, validade):
    ph = "%s" if _PG else "?"
    _exec(f"UPDATE users SET validade = {ph} WHERE username = {ph}", (validade, username))


def delete_user(username: str):
    ph = "%s" if _PG else "?"
    _exec(f"DELETE FROM users WHERE username = {ph}", (username,))


def get_user_permissions(username: str) -> list[str]:
    ph = "%s" if _PG else "?"
    row = _exec(f"SELECT permissoes, role FROM users WHERE username={ph}", (username,), fetch_one=True)
    if not row:
        return []
    if row.get("role") == "admin":
        return []
    perms = row.get("permissoes") or "conversor,baixar_xmls,certificados,milhao,dashboard"
    return [p.strip() for p in perms.split(",") if p.strip()]


def set_user_permissions(username: str, permissoes: list[str]):
    ph = "%s" if _PG else "?"
    _exec(f"UPDATE users SET permissoes={ph} WHERE username={ph}", (",".join(permissoes), username))


def update_password(username: str, new_hash: str):
    ph = "%s" if _PG else "?"
    _exec(f"UPDATE users SET password_hash = {ph} WHERE username = {ph}", (new_hash, username))


# ── CRUD — CONVERSÕES ─────────────────────────────────────────────────────────

def log_conversion(usuario: str, modo: str, qtd: int, sucesso: bool):
    ts = datetime.now().isoformat()
    ph = "%s" if _PG else "?"
    _exec(
        f"INSERT INTO conversions (ts, usuario, modo, qtd_arquivos, sucesso) VALUES ({ph},{ph},{ph},{ph},{ph})",
        (ts, usuario, modo.upper(), qtd, int(sucesso)),
    )


def get_conversions(limit: int = 500) -> list[dict]:
    ph = "%s" if _PG else "?"
    rows = _exec(
        f"SELECT ts, usuario, modo, qtd_arquivos AS arquivos, sucesso FROM conversions ORDER BY ts DESC LIMIT {ph}",
        (limit,),
        fetch_all=True,
    )
    return rows or []


# ── CRUD — CERTIFICADOS ───────────────────────────────────────────────────────

def salvar_certificado(usuario: str, cnpj: str, razao_social: str,
                       pfx_bytes: bytes, senha: str) -> bool:
    from core.crypto import encrypt_bytes, encrypt_str
    pfx_enc   = encrypt_bytes(pfx_bytes)
    senha_enc = encrypt_str(senha)
    try:
        if _PG:
            _exec(
                """INSERT INTO certificados (usuario, cnpj, razao_social, pfx_enc, senha_enc)
                   VALUES (%s,%s,%s,%s,%s)
                   ON CONFLICT (usuario, cnpj) DO UPDATE SET
                     razao_social=EXCLUDED.razao_social,
                     pfx_enc=EXCLUDED.pfx_enc,
                     senha_enc=EXCLUDED.senha_enc,
                     criado_em=NOW()""",
                (usuario, cnpj, razao_social, psycopg2.Binary(pfx_enc), senha_enc),
            )
        else:
            _exec(
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
    ph = "%s" if _PG else "?"
    rows = _exec(
        f"SELECT id, cnpj, razao_social, criado_em FROM certificados WHERE usuario = {ph} ORDER BY razao_social",
        (usuario,),
        fetch_all=True,
    )
    return rows or []


def carregar_certificado(usuario: str, cnpj: str) -> tuple[bytes, str] | None:
    from core.crypto import decrypt_bytes, decrypt_str
    ph = "%s" if _PG else "?"
    row = _exec(
        f"SELECT pfx_enc, senha_enc FROM certificados WHERE usuario={ph} AND cnpj={ph}",
        (usuario, cnpj),
        fetch_one=True,
    )
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
    ph = "%s" if _PG else "?"
    _exec(f"DELETE FROM certificados WHERE usuario={ph} AND cnpj={ph}", (usuario, cnpj))


def get_stats() -> dict:
    hoje = str(date.today())
    mes  = hoje[:7]

    if _PG:
        total  = (_exec("SELECT COUNT(*) AS n FROM conversions", fetch_one=True) or {}).get("n", 0)
        d_hoje = (_exec("SELECT COUNT(*) AS n FROM conversions WHERE ts LIKE %s", (f"{hoje}%",), fetch_one=True) or {}).get("n", 0)
        d_mes  = (_exec("SELECT COUNT(*) AS n FROM conversions WHERE ts LIKE %s", (f"{mes}%",), fetch_one=True) or {}).get("n", 0)
        xmls   = (_exec("SELECT COALESCE(SUM(qtd_arquivos),0) AS n FROM conversions WHERE sucesso=1", fetch_one=True) or {}).get("n", 0)
        txt_c  = (_exec("SELECT COUNT(*) AS n FROM conversions WHERE modo='TXT' AND sucesso=1", fetch_one=True) or {}).get("n", 0)
        xlsx_c = (_exec("SELECT COUNT(*) AS n FROM conversions WHERE modo='XLSX' AND sucesso=1", fetch_one=True) or {}).get("n", 0)
        by_usr = _exec("SELECT usuario, COUNT(*) AS cnt FROM conversions GROUP BY usuario ORDER BY 2 DESC", fetch_all=True) or []
        by_day = _exec(
            "SELECT DATE(ts::date) AS d, COUNT(*) AS cnt FROM conversions "
            "WHERE ts::date >= CURRENT_DATE - INTERVAL '14 days' GROUP BY d ORDER BY d",
            fetch_all=True,
        ) or []
    else:
        total  = (_exec("SELECT COUNT(*) AS n FROM conversions", fetch_one=True) or {}).get("n", 0)
        d_hoje = (_exec("SELECT COUNT(*) AS n FROM conversions WHERE ts LIKE ?", (f"{hoje}%",), fetch_one=True) or {}).get("n", 0)
        d_mes  = (_exec("SELECT COUNT(*) AS n FROM conversions WHERE ts LIKE ?", (f"{mes}%",), fetch_one=True) or {}).get("n", 0)
        xmls   = (_exec("SELECT COALESCE(SUM(qtd_arquivos),0) AS n FROM conversions WHERE sucesso=1", fetch_one=True) or {}).get("n", 0)
        txt_c  = (_exec("SELECT COUNT(*) AS n FROM conversions WHERE modo='TXT' AND sucesso=1", fetch_one=True) or {}).get("n", 0)
        xlsx_c = (_exec("SELECT COUNT(*) AS n FROM conversions WHERE modo='XLSX' AND sucesso=1", fetch_one=True) or {}).get("n", 0)
        by_usr = _exec("SELECT usuario, COUNT(*) AS cnt FROM conversions GROUP BY usuario ORDER BY 2 DESC", fetch_all=True) or []
        by_day = _exec(
            "SELECT DATE(ts) AS d, COUNT(*) AS cnt FROM conversions "
            "WHERE ts >= date('now','-14 days') GROUP BY d ORDER BY d",
            fetch_all=True,
        ) or []

    return {
        "total":       total,
        "hoje":        d_hoje,
        "mes":         d_mes,
        "xmls":        xmls,
        "txt":         txt_c,
        "xlsx":        xlsx_c,
        "por_usuario": {r["usuario"]: r["cnt"] for r in by_usr},
        "por_dia":     {str(r["d"]): r["cnt"] for r in by_day},
    }
