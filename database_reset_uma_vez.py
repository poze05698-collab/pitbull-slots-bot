import sqlite3

# ==========================================
# CONEXÃO
# ==========================================

conn = sqlite3.connect(
    "database.db",
    check_same_thread=False
)

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

    saque_pendente REAL DEFAULT 0,

    pix TEXT DEFAULT "",

    banido INTEGER DEFAULT 0,

    data_cadastro TEXT,

    ultimo_acesso TEXT

)
""")

# ==========================================
# INDICAÇÕES
# ==========================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS indicacoes(

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    indicador_id INTEGER NOT NULL,

    indicado_id INTEGER NOT NULL UNIQUE,

    valor REAL NOT NULL,

    status TEXT NOT NULL,

    grupo_confirmado INTEGER DEFAULT 0,

    admin_id INTEGER,

    data TEXT,

    data_aprovacao TEXT,

    FOREIGN KEY(indicador_id)
        REFERENCES usuarios(id),

    FOREIGN KEY(indicado_id)
        REFERENCES usuarios(id)

)
""")

# ==========================================
# SAQUES
# ==========================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS saques(

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    usuario_id INTEGER NOT NULL,

    valor REAL NOT NULL,

    pix TEXT NOT NULL,

    status TEXT NOT NULL,

    motivo_rejeicao TEXT,

    admin_id INTEGER,

    data TEXT,

    data_aprovacao TEXT,

    FOREIGN KEY(usuario_id)
        REFERENCES usuarios(id)

)
""")

# ==========================================
# TICKETS
# ==========================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS tickets(

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    usuario_id INTEGER NOT NULL,

    assunto TEXT NOT NULL,

    mensagem TEXT NOT NULL,

    resposta TEXT,

    status TEXT NOT NULL,

    admin_id INTEGER,

    data TEXT,

    data_resposta TEXT,

    fechado_em TEXT,

    FOREIGN KEY(usuario_id)
        REFERENCES usuarios(id)

)
""")

# ==========================================
# HISTÓRICO
# ==========================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS historico(

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    usuario_id INTEGER NOT NULL,

    tipo TEXT NOT NULL,

    descricao TEXT NOT NULL,

    valor REAL DEFAULT 0,

    data TEXT,

    FOREIGN KEY(usuario_id)
        REFERENCES usuarios(id)

)
""")

# ==========================================
# FRAUDES
# ==========================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS fraudes(

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    usuario_id INTEGER,

    indicador_id INTEGER,

    motivo TEXT,

    acao TEXT,

    data TEXT

)
""")

# ==========================================
# CONFIGURAÇÕES
# ==========================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS configuracoes(

    chave TEXT PRIMARY KEY,

    valor TEXT NOT NULL

)
""")

# ==========================================
# CONFIGURAÇÕES PADRÃO
# ==========================================

configuracoes_padrao = {

    "valor_indicacao": "1.00",

    "valor_minimo_saque": "20",

    "grupo_obrigatorio": "1",

    "tickets_ativos": "1"

}

for chave, valor in configuracoes_padrao.items():

    cursor.execute(

        """
        INSERT OR IGNORE INTO configuracoes
        (chave, valor)
        VALUES (?, ?)
        """,

        (chave, valor)

    )

conn.commit()

# =====================================================
# LINKS DE CONVITE
# =====================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS links_convite (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    usuario_id INTEGER NOT NULL,

    invite_link TEXT UNIQUE,

    invite_name TEXT,

    ativo INTEGER DEFAULT 1,

    data_criacao TEXT,

    FOREIGN KEY(usuario_id)
        REFERENCES usuarios(id)

)
""")

conn.commit()


# =====================================================
# RESET ÚNICO DO BANCO - USO PARA TESTES
# =====================================================
# Esta parte limpa os dados somente na primeira execução.
# Depois cria um arquivo marcador para não apagar novamente.

RESET_MARKER = "database_reset_done.txt"

if not __import__("os").path.exists(RESET_MARKER):

    tabelas_reset = [
        "links_convite",
        "historico",
        "fraudes",
        "tickets",
        "saques",
        "indicacoes",
        "usuarios"
    ]

    for tabela in tabelas_reset:
        cursor.execute(f"DELETE FROM {tabela}")

    # Reinicia os IDs automáticos das tabelas.
    cursor.execute("DELETE FROM sqlite_sequence")

    conn.commit()

    with open(RESET_MARKER, "w", encoding="utf-8") as arquivo:
        arquivo.write("RESET REALIZADO - NAO APAGAR ESTE ARQUIVO DURANTE OS TESTES")


conn.commit()
