"""Cria conversor.db (SQLite) a partir dos JSONs exportados do Supabase."""
import json, sqlite3, os, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
EXPORT = ROOT / "data" / "supabase_export"
DB_PATH = ROOT / "data" / "conversor.db"

if DB_PATH.exists():
    DB_PATH.unlink()
    print(f"Removido DB antigo: {DB_PATH}")

DB_PATH.parent.mkdir(parents=True, exist_ok=True)
con = sqlite3.connect(str(DB_PATH))
cur = con.cursor()

# ── Criar tabelas ──
cur.executescript("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    name TEXT,
    email TEXT,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'user',
    validade TEXT,
    permissoes TEXT
);
CREATE TABLE IF NOT EXISTS conversions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    file_name TEXT,
    conversion_type TEXT,
    records_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS certificados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    cnpj TEXT NOT NULL,
    razao_social TEXT,
    pfx_enc BLOB,
    senha TEXT,
    validade TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(username, cnpj)
);
CREATE TABLE IF NOT EXISTS nfe_nsu (
    cnpj TEXT PRIMARY KEY,
    ultimo_nsu TEXT DEFAULT '0',
    max_nsu TEXT DEFAULT '0',
    updated_at TEXT,
    proxima_consulta TEXT
);
CREATE TABLE IF NOT EXISTS nfe_auto_sync (
    cnpj TEXT NOT NULL,
    username TEXT NOT NULL,
    ativo INTEGER DEFAULT 1,
    intervalo_min INTEGER DEFAULT 60,
    PRIMARY KEY (cnpj, username)
);
CREATE TABLE IF NOT EXISTS nfe_resultados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cnpj TEXT,
    nsu TEXT,
    tipo_schema TEXT,
    chave TEXT,
    xml_conteudo TEXT,
    resumo TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS siga_xml_fila (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    cnpj TEXT NOT NULL,
    chave TEXT NOT NULL UNIQUE,
    status TEXT DEFAULT 'pendente',
    tentativas INTEGER DEFAULT 0,
    erro TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS siga_documentos_fiscais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cnpj TEXT NOT NULL,
    tipo TEXT,
    numero TEXT,
    serie TEXT,
    chave TEXT,
    data_emissao TEXT,
    valor REAL,
    prestador_cnpj TEXT,
    prestador_nome TEXT,
    tomador_cnpj TEXT,
    tomador_nome TEXT,
    situacao TEXT,
    competencia TEXT,
    username TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(cnpj, chave)
);
CREATE TABLE IF NOT EXISTS siga_indicadores_malha (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cnpj TEXT NOT NULL,
    competencia TEXT NOT NULL,
    status TEXT,
    valor_declarado REAL,
    valor_apurado REAL,
    diferenca REAL,
    username TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(cnpj, competencia)
);
CREATE TABLE IF NOT EXISTS siga_indicadores_malha_detalhe (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cnpj TEXT NOT NULL,
    competencia TEXT NOT NULL,
    prestador_cnpj TEXT,
    prestador_nome TEXT,
    valor_nfse REAL,
    valor_declarado REAL,
    diferenca REAL,
    username TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS filiais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cnpj_matriz TEXT NOT NULL,
    cnpj_filial TEXT NOT NULL UNIQUE,
    razao_social TEXT,
    username TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
""")
con.commit()

def load_json(name):
    path = EXPORT / name
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def import_table(table, json_file, columns, conflict="IGNORE"):
    data = load_json(json_file)
    if not data:
        print(f"  {table}: 0 records (skip)")
        return
    placeholders = ",".join(["?"] * len(columns))
    col_names = ",".join(columns)
    sql = f"INSERT OR {conflict} INTO {table} ({col_names}) VALUES ({placeholders})"

    batch = []
    for row in data:
        values = []
        for col in columns:
            val = row.get(col)
            if col == "pfx_enc" and val is not None:
                if isinstance(val, str):
                    val = val.encode("utf-8")
            values.append(val)
        batch.append(tuple(values))

    cur.executemany(sql, batch)
    con.commit()
    print(f"  {table}: {len(batch)} records imported")

print("Importing users...")
import_table("users", "users.json",
    ["username", "name", "email", "password_hash", "role", "validade", "permissoes"])

print("Importing certificados...")
import_table("certificados", "certificados.json",
    ["username", "cnpj", "razao_social", "pfx_enc", "senha", "validade", "created_at"])

print("Importing conversions...")
import_table("conversions", "conversions.json",
    ["username", "file_name", "conversion_type", "records_count", "created_at"])

print("Importing nfe_nsu...")
import_table("nfe_nsu", "nfe_nsu.json",
    ["cnpj", "ultimo_nsu", "max_nsu", "updated_at", "proxima_consulta"])

print("Importing nfe_auto_sync...")
import_table("nfe_auto_sync", "nfe_auto_sync.json",
    ["cnpj", "username", "ativo", "intervalo_min"])

print("Importing nfe_resultados...")
import_table("nfe_resultados", "nfe_resultados.json",
    ["cnpj", "nsu", "tipo_schema", "chave", "xml_conteudo", "resumo", "created_at"])

print("Importing siga_xml_fila...")
import_table("siga_xml_fila", "siga_xml_fila.json",
    ["username", "cnpj", "chave", "status", "tentativas", "erro", "created_at", "updated_at"])

print("Importing siga_documentos_fiscais...")
import_table("siga_documentos_fiscais", "siga_documentos_fiscais.json",
    ["cnpj", "tipo", "numero", "serie", "chave", "data_emissao", "valor",
     "prestador_cnpj", "prestador_nome", "tomador_cnpj", "tomador_nome",
     "situacao", "competencia", "username", "created_at"])

print("Importing siga_indicadores_malha...")
import_table("siga_indicadores_malha", "siga_indicadores_malha.json",
    ["cnpj", "competencia", "status", "valor_declarado", "valor_apurado",
     "diferenca", "username", "created_at"])

print("Importing siga_indicadores_malha_detalhe...")
import_table("siga_indicadores_malha_detalhe", "siga_indicadores_malha_detalhe.json",
    ["cnpj", "competencia", "prestador_cnpj", "prestador_nome",
     "valor_nfse", "valor_declarado", "diferenca", "username", "created_at"])

# Criar admin com bcrypt
import bcrypt
pw_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt(12)).decode()
cur.execute("INSERT OR REPLACE INTO users (username, name, email, password_hash, role) VALUES (?,?,?,?,?)",
    ("admin", "Admin", "admin@empresa.com", pw_hash, "admin"))
con.commit()
print("\nAdmin user created (admin/admin123)")

con.close()
size_mb = DB_PATH.stat().st_size / (1024*1024)
print(f"\nDone! {DB_PATH} = {size_mb:.1f} MB")
