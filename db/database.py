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
            CREATE TABLE IF NOT EXISTS nfe_nsu (
                cnpj              TEXT PRIMARY KEY,
                ultimo_nsu        TEXT NOT NULL DEFAULT '000000000000000',
                atualizado_em     TEXT,
                proxima_consulta  TEXT
            )
        """)
        cur.execute("ALTER TABLE nfe_nsu ADD COLUMN IF NOT EXISTS proxima_consulta TEXT")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS nfe_auto_sync (
                cnpj     TEXT NOT NULL,
                username TEXT NOT NULL,
                ativo    INTEGER DEFAULT 0,
                PRIMARY KEY (cnpj, username)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS nfe_resultados (
                id           SERIAL PRIMARY KEY,
                cnpj         TEXT NOT NULL,
                chave        TEXT NOT NULL,
                modelo       TEXT DEFAULT 'NF-e',
                papel        TEXT DEFAULT 'Recebida',
                numero       TEXT DEFAULT '',
                serie        TEXT DEFAULT '',
                data_emissao TEXT DEFAULT '',
                cnpj_emit    TEXT DEFAULT '',
                nome_emit    TEXT DEFAULT '',
                cnpj_dest    TEXT DEFAULT '',
                nome_dest    TEXT DEFAULT '',
                valor_total  REAL DEFAULT 0,
                nat_operacao TEXT DEFAULT '',
                xml_conteudo TEXT NOT NULL,
                baixado_por  TEXT DEFAULT 'auto',
                criado_em    TEXT NOT NULL,
                UNIQUE(cnpj, chave)
            )
        """)
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
            CREATE TABLE IF NOT EXISTS nfe_nsu (
                cnpj             TEXT PRIMARY KEY,
                ultimo_nsu       TEXT NOT NULL DEFAULT '000000000000000',
                atualizado_em    TEXT,
                proxima_consulta TEXT
            );
            CREATE TABLE IF NOT EXISTS nfe_auto_sync (
                cnpj     TEXT NOT NULL,
                username TEXT NOT NULL,
                ativo    INTEGER DEFAULT 0,
                PRIMARY KEY (cnpj, username)
            );
            CREATE TABLE IF NOT EXISTS nfe_resultados (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                cnpj         TEXT NOT NULL,
                chave        TEXT NOT NULL,
                modelo       TEXT DEFAULT 'NF-e',
                papel        TEXT DEFAULT 'Recebida',
                numero       TEXT DEFAULT '',
                serie        TEXT DEFAULT '',
                data_emissao TEXT DEFAULT '',
                cnpj_emit    TEXT DEFAULT '',
                nome_emit    TEXT DEFAULT '',
                cnpj_dest    TEXT DEFAULT '',
                nome_dest    TEXT DEFAULT '',
                valor_total  REAL DEFAULT 0,
                nat_operacao TEXT DEFAULT '',
                xml_conteudo TEXT NOT NULL,
                baixado_por  TEXT DEFAULT 'auto',
                criado_em    TEXT NOT NULL,
                UNIQUE(cnpj, chave)
            );
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
    try:
        _exec("ALTER TABLE nfe_nsu ADD COLUMN proxima_consulta TEXT")
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


def get_conversions(limit: int = 500, usuario: str | None = None) -> list[dict]:
    ph = "%s" if _PG else "?"
    if usuario:
        rows = _exec(
            f"SELECT ts, usuario, modo, qtd_arquivos AS arquivos, sucesso FROM conversions WHERE usuario={ph} ORDER BY ts DESC LIMIT {ph}",
            (usuario, limit),
            fetch_all=True,
        )
    else:
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


def get_stats(usuario: str | None = None) -> dict:
    hoje = str(date.today())
    mes  = hoje[:7]

    # filtro extra se não for admin
    if usuario:
        f_pg  = " AND usuario=%s"
        f_sq  = " AND usuario=?"
        u_arg = (usuario,)
    else:
        f_pg = f_sq = ""
        u_arg = ()

    if _PG:
        total  = (_exec(f"SELECT COUNT(*) AS n FROM conversions WHERE sucesso=1{f_pg}", u_arg, fetch_one=True) or {}).get("n", 0)
        d_hoje = (_exec(f"SELECT COUNT(*) AS n FROM conversions WHERE sucesso=1 AND ts LIKE %s{f_pg}", (f"{hoje}%", *u_arg), fetch_one=True) or {}).get("n", 0)
        d_mes  = (_exec(f"SELECT COUNT(*) AS n FROM conversions WHERE sucesso=1 AND ts LIKE %s{f_pg}", (f"{mes}%",  *u_arg), fetch_one=True) or {}).get("n", 0)
        xmls   = (_exec(f"SELECT COALESCE(SUM(qtd_arquivos),0) AS n FROM conversions WHERE sucesso=1{f_pg}", u_arg, fetch_one=True) or {}).get("n", 0)
        txt_c  = (_exec(f"SELECT COUNT(*) AS n FROM conversions WHERE modo IN ('TXT','MILHAO_TXT') AND sucesso=1{f_pg}", u_arg, fetch_one=True) or {}).get("n", 0)
        xlsx_c = (_exec(f"SELECT COUNT(*) AS n FROM conversions WHERE modo IN ('XLSX','MILHAO_XLSX') AND sucesso=1{f_pg}", u_arg, fetch_one=True) or {}).get("n", 0)
        fs_c   = (_exec(f"SELECT COALESCE(SUM(qtd_arquivos),0) AS n FROM conversions WHERE modo='FS' AND sucesso=1{f_pg}", u_arg, fetch_one=True) or {}).get("n", 0)
        xml_api= (_exec(f"SELECT COALESCE(SUM(qtd_arquivos),0) AS n FROM conversions WHERE modo IN ('XML','AMBOS') AND sucesso=1{f_pg}", u_arg, fetch_one=True) or {}).get("n", 0)
        pdf_api= (_exec(f"SELECT COALESCE(SUM(qtd_arquivos),0) AS n FROM conversions WHERE modo IN ('PDF','AMBOS') AND sucesso=1{f_pg}", u_arg, fetch_one=True) or {}).get("n", 0)
        by_usr = _exec(f"SELECT usuario, COUNT(*) AS cnt FROM conversions WHERE 1=1{f_pg} GROUP BY usuario ORDER BY 2 DESC", u_arg, fetch_all=True) or []
        by_day = _exec(
            f"SELECT DATE(ts::date) AS d, COUNT(*) AS cnt FROM conversions "
            f"WHERE ts::date >= CURRENT_DATE - INTERVAL '14 days'{f_pg} GROUP BY d ORDER BY d",
            u_arg, fetch_all=True,
        ) or []
    else:
        total  = (_exec(f"SELECT COUNT(*) AS n FROM conversions WHERE sucesso=1{f_sq}", u_arg, fetch_one=True) or {}).get("n", 0)
        d_hoje = (_exec(f"SELECT COUNT(*) AS n FROM conversions WHERE sucesso=1 AND ts LIKE ?{f_sq}", (f"{hoje}%", *u_arg), fetch_one=True) or {}).get("n", 0)
        d_mes  = (_exec(f"SELECT COUNT(*) AS n FROM conversions WHERE sucesso=1 AND ts LIKE ?{f_sq}", (f"{mes}%",  *u_arg), fetch_one=True) or {}).get("n", 0)
        xmls   = (_exec(f"SELECT COALESCE(SUM(qtd_arquivos),0) AS n FROM conversions WHERE sucesso=1{f_sq}", u_arg, fetch_one=True) or {}).get("n", 0)
        txt_c  = (_exec(f"SELECT COUNT(*) AS n FROM conversions WHERE modo IN ('TXT','MILHAO_TXT') AND sucesso=1{f_sq}", u_arg, fetch_one=True) or {}).get("n", 0)
        xlsx_c = (_exec(f"SELECT COUNT(*) AS n FROM conversions WHERE modo IN ('XLSX','MILHAO_XLSX') AND sucesso=1{f_sq}", u_arg, fetch_one=True) or {}).get("n", 0)
        fs_c   = (_exec(f"SELECT COALESCE(SUM(qtd_arquivos),0) AS n FROM conversions WHERE modo='FS' AND sucesso=1{f_sq}", u_arg, fetch_one=True) or {}).get("n", 0)
        xml_api= (_exec(f"SELECT COALESCE(SUM(qtd_arquivos),0) AS n FROM conversions WHERE modo IN ('XML','AMBOS') AND sucesso=1{f_sq}", u_arg, fetch_one=True) or {}).get("n", 0)
        pdf_api= (_exec(f"SELECT COALESCE(SUM(qtd_arquivos),0) AS n FROM conversions WHERE modo IN ('PDF','AMBOS') AND sucesso=1{f_sq}", u_arg, fetch_one=True) or {}).get("n", 0)
        by_usr = _exec(f"SELECT usuario, COUNT(*) AS cnt FROM conversions WHERE 1=1{f_sq} GROUP BY usuario ORDER BY 2 DESC", u_arg, fetch_all=True) or []
        by_day = _exec(
            f"SELECT DATE(ts) AS d, COUNT(*) AS cnt FROM conversions "
            f"WHERE ts >= date('now','-14 days'){f_sq} GROUP BY d ORDER BY d",
            u_arg, fetch_all=True,
        ) or []

    return {
        "total":       total,
        "hoje":        d_hoje,
        "mes":         d_mes,
        "xmls":        xmls,
        "txt":         txt_c,
        "xlsx":        xlsx_c,
        "fs":          fs_c,
        "xml_api":     xml_api,
        "pdf_api":     pdf_api,
        "por_usuario": {r["usuario"]: r["cnt"] for r in by_usr},
        "por_dia":     {str(r["d"]): r["cnt"] for r in by_day},
    }


# ── CRUD — NSU NF-e ───────────────────────────────────────────────────────────

def get_nsu_cnpj(cnpj: str) -> dict:
    """Retorna {'ultimo_nsu', 'atualizado_em', 'proxima_consulta'} para o CNPJ."""
    ph = "%s" if _PG else "?"
    row = _exec(
        f"SELECT ultimo_nsu, atualizado_em, proxima_consulta FROM nfe_nsu WHERE cnpj={ph}",
        (cnpj,), fetch_one=True,
    )
    return row or {"ultimo_nsu": "000000000000000", "atualizado_em": None, "proxima_consulta": None}


def set_nsu_cnpj(cnpj: str, nsu: str):
    """Persiste o último NSU consultado para o CNPJ."""
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    if _PG:
        _exec(
            """INSERT INTO nfe_nsu (cnpj, ultimo_nsu, atualizado_em)
               VALUES (%s,%s,%s)
               ON CONFLICT (cnpj) DO UPDATE SET
                 ultimo_nsu=EXCLUDED.ultimo_nsu,
                 atualizado_em=EXCLUDED.atualizado_em""",
            (cnpj, nsu, agora),
        )
    else:
        _exec(
            """INSERT INTO nfe_nsu (cnpj, ultimo_nsu, atualizado_em) VALUES (?,?,?)
               ON CONFLICT(cnpj) DO UPDATE SET
                 ultimo_nsu=excluded.ultimo_nsu,
                 atualizado_em=excluded.atualizado_em""",
            (cnpj, nsu, agora),
        )


def set_proxima_consulta(cnpj: str, dt_iso: str):
    """Define o datetime ISO em que a próxima consulta estará liberada."""
    ph = "%s" if _PG else "?"
    if _PG:
        _exec(
            """INSERT INTO nfe_nsu (cnpj, ultimo_nsu, proxima_consulta)
               VALUES (%s,'000000000000000',%s)
               ON CONFLICT (cnpj) DO UPDATE SET proxima_consulta=EXCLUDED.proxima_consulta""",
            (cnpj, dt_iso),
        )
    else:
        _exec(
            """INSERT INTO nfe_nsu (cnpj, ultimo_nsu, proxima_consulta) VALUES (?,?,?)
               ON CONFLICT(cnpj) DO UPDATE SET proxima_consulta=excluded.proxima_consulta""",
            (cnpj, "000000000000000", dt_iso),
        )


def reset_nsu_cnpj(cnpj: str):
    """Reseta o NSU para zero e libera a próxima consulta imediatamente."""
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    if _PG:
        _exec(
            """INSERT INTO nfe_nsu (cnpj, ultimo_nsu, atualizado_em, proxima_consulta)
               VALUES (%s,'000000000000000',%s,NULL)
               ON CONFLICT (cnpj) DO UPDATE SET
                 ultimo_nsu='000000000000000',
                 atualizado_em=EXCLUDED.atualizado_em,
                 proxima_consulta=NULL""",
            (cnpj, agora),
        )
    else:
        _exec(
            """INSERT INTO nfe_nsu (cnpj, ultimo_nsu, atualizado_em, proxima_consulta) VALUES (?,?,?,NULL)
               ON CONFLICT(cnpj) DO UPDATE SET
                 ultimo_nsu='000000000000000',
                 atualizado_em=excluded.atualizado_em,
                 proxima_consulta=NULL""",
            (cnpj, "000000000000000", agora),
        )


# ── CRUD — Auto-Sync NF-e ─────────────────────────────────────────────────────

def set_auto_sync(cnpj: str, username: str, ativo: bool):
    """Ativa ou desativa a sincronização automática para um CNPJ."""
    ph = "%s" if _PG else "?"
    if _PG:
        _exec(
            """INSERT INTO nfe_auto_sync (cnpj, username, ativo) VALUES (%s,%s,%s)
               ON CONFLICT (cnpj, username) DO UPDATE SET ativo=EXCLUDED.ativo""",
            (cnpj, username, int(ativo)),
        )
    else:
        _exec(
            """INSERT INTO nfe_auto_sync (cnpj, username, ativo) VALUES (?,?,?)
               ON CONFLICT(cnpj, username) DO UPDATE SET ativo=excluded.ativo""",
            (cnpj, username, int(ativo)),
        )


def get_auto_sync(cnpj: str, username: str) -> bool:
    ph = "%s" if _PG else "?"
    row = _exec(
        f"SELECT ativo FROM nfe_auto_sync WHERE cnpj={ph} AND username={ph}",
        (cnpj, username), fetch_one=True,
    )
    return bool(row["ativo"]) if row else False


def listar_auto_sync_ativos() -> list[dict]:
    """Retorna todos os CNPJs com auto-sync ativo para uso pelo scheduler."""
    return _exec(
        "SELECT cnpj, username FROM nfe_auto_sync WHERE ativo=1",
        fetch_all=True,
    ) or []


# ── CRUD — Resultados NF-e (auto-sync) ───────────────────────────────────────

def salvar_resultados_nfe(docs: list[dict], baixado_por: str = "auto"):
    """Insere NF-es baixadas no banco. Ignora duplicatas (por chave+cnpj)."""
    agora = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    for d in docs:
        chave = d.get("chave", "")
        cnpj  = d.get("cnpj_empresa", "")
        if not chave or not cnpj:
            continue
        params = (
            cnpj, chave,
            d.get("modelo", "NF-e"),
            d.get("papel", "Recebida"),
            d.get("numero", ""),
            d.get("serie", ""),
            d.get("data_emissao", ""),
            d.get("cnpj_emitente", ""),
            d.get("nome_emitente", ""),
            d.get("cnpj_dest_doc", ""),
            d.get("nome_dest_doc", ""),
            float(d.get("valor_total", 0)),
            d.get("nat_operacao", ""),
            d.get("xml", ""),
            baixado_por,
            agora,
        )
        try:
            if _PG:
                _exec(
                    """INSERT INTO nfe_resultados
                       (cnpj,chave,modelo,papel,numero,serie,data_emissao,cnpj_emit,nome_emit,
                        cnpj_dest,nome_dest,valor_total,nat_operacao,xml_conteudo,baixado_por,criado_em)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (cnpj, chave) DO NOTHING""",
                    params,
                )
            else:
                _exec(
                    """INSERT OR IGNORE INTO nfe_resultados
                       (cnpj,chave,modelo,papel,numero,serie,data_emissao,cnpj_emit,nome_emit,
                        cnpj_dest,nome_dest,valor_total,nat_operacao,xml_conteudo,baixado_por,criado_em)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    params,
                )
        except Exception as e:
            print(f"[db] salvar_resultados_nfe erro: {e}")


def listar_resultados_nfe(cnpj: str, limit: int = 1000) -> list[dict]:
    ph = "%s" if _PG else "?"
    lim = "%s" if _PG else "?"
    return _exec(
        f"SELECT id,chave,modelo,papel,numero,serie,data_emissao,cnpj_emit,nome_emit,"
        f"valor_total,criado_em FROM nfe_resultados WHERE cnpj={ph} ORDER BY criado_em DESC LIMIT {lim}",
        (cnpj, limit), fetch_all=True,
    ) or []


def contar_resultados_nfe(cnpj: str) -> int:
    ph = "%s" if _PG else "?"
    row = _exec(
        f"SELECT COUNT(*) AS n FROM nfe_resultados WHERE cnpj={ph}",
        (cnpj,), fetch_one=True,
    )
    return int((row or {}).get("n", 0))


def carregar_xml_resultado(cnpj: str, chave: str) -> str | None:
    ph = "%s" if _PG else "?"
    row = _exec(
        f"SELECT xml_conteudo FROM nfe_resultados WHERE cnpj={ph} AND chave={ph}",
        (cnpj, chave), fetch_one=True,
    )
    return row["xml_conteudo"] if row else None


def listar_resultados_por_periodo(
    cnpj: str, data_ini: str, data_fim: str,
    modelo: str | None = None, papel: str | None = None,
) -> list[dict]:
    """Retorna NF-es/NFC-es de um CNPJ filtradas por período e tipo.
    modelo: '55' → NF-e, '65' → NFC-e, None → todos.
    papel:  'Recebida' | 'Emitida' | None → todos.
    data_ini/data_fim: formato YYYY-MM-DD.
    """
    ph = "%s" if _PG else "?"
    conditions = [f"cnpj={ph}"]
    params: list = [cnpj]

    if data_ini:
        conditions.append(f"data_emissao >= {ph}")
        params.append(data_ini)
    if data_fim:
        conditions.append(f"data_emissao <= {ph}")
        params.append(data_fim + "T23:59:59")
    if modelo == "55":
        conditions.append(f"modelo = {ph}")
        params.append("NF-e")
    elif modelo == "65":
        conditions.append(f"modelo = {ph}")
        params.append("NFC-e")
    if papel:
        conditions.append(f"papel = {ph}")
        params.append(papel)

    where = " AND ".join(conditions)
    return _exec(
        f"SELECT chave,modelo,papel,numero,serie,data_emissao,cnpj_emit,nome_emit,"
        f"cnpj_dest,nome_dest,valor_total,nat_operacao FROM nfe_resultados "
        f"WHERE {where} ORDER BY data_emissao DESC",
        tuple(params), fetch_all=True,
    ) or []


def listar_xmls_resultados(cnpj: str) -> list[dict]:
    """Retorna (chave, xml_conteudo) de todos os resultados para gerar ZIP."""
    ph = "%s" if _PG else "?"
    return _exec(
        f"SELECT chave, modelo, papel, xml_conteudo FROM nfe_resultados WHERE cnpj={ph} ORDER BY data_emissao",
        (cnpj,), fetch_all=True,
    ) or []
