"""Cria conversor.db (SQLite) a partir dos JSONs exportados do Supabase.
Usa o schema exato de _init_sqlite() em db/database.py."""
import json, sqlite3, os, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
EXPORT = ROOT / "data" / "supabase_export"
DB_PATH = ROOT / "data" / "conversor.db"

if DB_PATH.exists():
    DB_PATH.unlink()

DB_PATH.parent.mkdir(parents=True, exist_ok=True)
con = sqlite3.connect(str(DB_PATH))
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
        xml_conteudo TEXT NOT NULL DEFAULT '',
        nsu          TEXT DEFAULT '',
        baixado_por  TEXT DEFAULT '',
        criado_em    TEXT DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        username      TEXT UNIQUE NOT NULL,
        name          TEXT NOT NULL,
        email         TEXT DEFAULT '',
        password_hash TEXT NOT NULL,
        role          TEXT DEFAULT 'user',
        permissoes    TEXT DEFAULT 'conversor,baixar_xmls,certificados,milhao,dashboard',
        created_at    TEXT DEFAULT (datetime('now','localtime')),
        validade      TEXT
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
    CREATE TABLE IF NOT EXISTS siga_xml_fila (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario       TEXT NOT NULL,
        cnpj          TEXT NOT NULL,
        chave         TEXT NOT NULL,
        status        TEXT DEFAULT 'PENDENTE',
        erro          TEXT DEFAULT '',
        criado_em     TEXT DEFAULT (datetime('now','localtime')),
        processado_em TEXT,
        UNIQUE(cnpj, chave)
    );
    CREATE TABLE IF NOT EXISTS siga_documentos_fiscais (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        cnpj             TEXT NOT NULL,
        tipo             TEXT NOT NULL,
        aba              TEXT NOT NULL,
        periodo          TEXT NOT NULL,
        chave            TEXT NOT NULL,
        numero           TEXT DEFAULT '',
        data_emissao     TEXT DEFAULT '',
        valor            REAL DEFAULT 0,
        uf               TEXT DEFAULT '',
        contraparte_cnpj TEXT DEFAULT '',
        contraparte_nome TEXT DEFAULT '',
        situacao         TEXT DEFAULT '',
        atualizado_em    TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(cnpj, tipo, aba, periodo, chave)
    );
    CREATE TABLE IF NOT EXISTS siga_indicadores_malha (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        cnpj          TEXT NOT NULL,
        indicador     TEXT NOT NULL,
        descricao     TEXT DEFAULT '',
        grupo_cfop    TEXT DEFAULT '',
        valor         REAL DEFAULT 0,
        unidade       TEXT DEFAULT '',
        qtd_indicios  INTEGER DEFAULT 0,
        atualizado_em TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(cnpj, indicador, grupo_cfop)
    );
    CREATE TABLE IF NOT EXISTS siga_indicadores_malha_detalhe (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        cnpj             TEXT NOT NULL,
        indicador        TEXT NOT NULL,
        chave            TEXT NOT NULL,
        numero           TEXT DEFAULT '',
        data_emissao     TEXT DEFAULT '',
        valor            REAL DEFAULT 0,
        contraparte_cnpj TEXT DEFAULT '',
        atualizado_em    TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(cnpj, indicador, chave)
    );
    CREATE TABLE IF NOT EXISTS filiais (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        cnpj_matriz  TEXT NOT NULL,
        cnpj_filial  TEXT NOT NULL,
        nome_filial  TEXT DEFAULT '',
        criado_em    TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(cnpj_matriz, cnpj_filial)
    );
""")
con.commit()

def load_json(name):
    path = EXPORT / name
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def import_table(table, json_file, columns):
    data = load_json(json_file)
    if not data:
        print(f"  {table}: 0 records (skip)")
        return
    placeholders = ",".join(["?"] * len(columns))
    col_names = ",".join(columns)
    sql = f"INSERT OR IGNORE INTO {table} ({col_names}) VALUES ({placeholders})"

    batch = []
    for row in data:
        values = []
        for col in columns:
            val = row.get(col)
            if col == "pfx_enc" and val is not None:
                if isinstance(val, str):
                    val = val.encode("utf-8")
            if col == "xml_conteudo" and val is None:
                val = ""
            values.append(val)
        batch.append(tuple(values))

    cur.executemany(sql, batch)
    con.commit()
    print(f"  {table}: {len(batch)} records")

print("Importing...")
import_table("users", "users.json",
    ["username", "name", "email", "password_hash", "role", "permissoes", "created_at", "validade"])

import_table("certificados", "certificados.json",
    ["usuario", "cnpj", "razao_social", "pfx_enc", "senha_enc", "criado_em"])

import_table("conversions", "conversions.json",
    ["ts", "usuario", "modo", "qtd_arquivos", "sucesso"])

import_table("nfe_nsu", "nfe_nsu.json",
    ["cnpj", "ultimo_nsu", "atualizado_em", "proxima_consulta"])

import_table("nfe_auto_sync", "nfe_auto_sync.json",
    ["cnpj", "username", "ativo"])

import_table("nfe_resultados", "nfe_resultados.json",
    ["cnpj", "chave", "modelo", "papel", "numero", "serie", "data_emissao",
     "cnpj_emit", "nome_emit", "cnpj_dest", "nome_dest", "valor_total",
     "nat_operacao", "baixado_por", "criado_em"])

import_table("siga_xml_fila", "siga_xml_fila.json",
    ["usuario", "cnpj", "chave", "status", "erro", "criado_em", "processado_em"])

import_table("siga_documentos_fiscais", "siga_documentos_fiscais.json",
    ["cnpj", "tipo", "aba", "periodo", "chave", "numero", "data_emissao",
     "valor", "uf", "contraparte_cnpj", "contraparte_nome", "situacao", "atualizado_em"])

import_table("siga_indicadores_malha", "siga_indicadores_malha.json",
    ["cnpj", "indicador", "descricao", "grupo_cfop", "valor", "unidade",
     "qtd_indicios", "atualizado_em"])

import_table("siga_indicadores_malha_detalhe", "siga_indicadores_malha_detalhe.json",
    ["cnpj", "indicador", "chave", "numero", "data_emissao", "valor",
     "contraparte_cnpj", "atualizado_em"])

# Criar admin
import bcrypt
pw_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt(12)).decode()
cur.execute("INSERT OR REPLACE INTO users (username, name, email, password_hash, role) VALUES (?,?,?,?,?)",
    ("admin", "Admin", "admin@empresa.com", pw_hash, "admin"))
con.commit()
print("\nAdmin criado (admin/admin123)")

con.close()
size_mb = DB_PATH.stat().st_size / (1024*1024)
print(f"Done! {DB_PATH.name} = {size_mb:.1f} MB")
