import sqlite3

# ==========================================
# CONEXÃO COM O BANCO
# ==========================================

conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

# ==========================================
# USUÁRIOS
# ==========================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS usuarios(

    id INTEGER PRIMARY KEY,

    nome TEXT NOT NULL,

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
# INDICAÇÕES
# ==========================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS indicacoes(

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    indicador_id INTEGER,

    indicado_id INTEGER,

    valor REAL,

    status TEXT,

    admin_id INTEGER,

    data TEXT,

    data_aprovacao TEXT

)
""")

# ==========================================
# SAQUES
# ==========================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS saques(

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    usuario_id INTEGER,

    valor REAL,

    pix TEXT,

    status TEXT,

    admin_id INTEGER,

    data TEXT,

    data_aprovacao TEXT

)
""")

# ==========================================
# TICKETS
# ==========================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS tickets(

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    usuario_id INTEGER,

    mensagem TEXT,

    resposta TEXT,

    status TEXT,

    admin_id INTEGER,

    data TEXT,

    data_resposta TEXT

)
""")

# ==========================================
# HISTÓRICO
# ==========================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS historico(

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    usuario_id INTEGER,

    tipo TEXT,

    descricao TEXT,

    valor REAL,

    data TEXT

)
""")

conn.commit()
