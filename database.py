import sqlite3

# ==========================================
# CONEXÃO COM O BANCO
# ==========================================

conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

# ==========================================
# TABELA DE USUÁRIOS
# ==========================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS usuarios (

    id INTEGER PRIMARY KEY,
    nome TEXT,
    username TEXT,

    saldo REAL DEFAULT 0,
    saldo_pendente REAL DEFAULT 0,

    pix TEXT DEFAULT "",

    indicados INTEGER DEFAULT 0,

    banido INTEGER DEFAULT 0,

    data_cadastro TEXT

)
""")

# ==========================================
# TABELA DE INDICAÇÕES
# ==========================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS indicacoes (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    indicador_id INTEGER,

    indicado_id INTEGER,

    valor REAL,

    status TEXT,

    data TEXT

)
""")

# ==========================================
# TABELA DE SAQUES
# ==========================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS saques (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    usuario_id INTEGER,

    valor REAL,

    pix TEXT,

    status TEXT,

    data TEXT

)
""")

# ==========================================
# TABELA DE TICKETS
# ==========================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS tickets (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    usuario_id INTEGER,

    mensagem TEXT,

    resposta TEXT,

    status TEXT,

    data TEXT

)
""")

# ==========================================
# TABELA DE HISTÓRICO
# ==========================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS historico (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    usuario_id INTEGER,

    tipo TEXT,

    descricao TEXT,

    valor REAL,

    data TEXT

)
""")

conn.commit()
