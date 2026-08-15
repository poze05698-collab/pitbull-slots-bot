import sqlite3
import threading
from pathlib import Path

# =====================================================
# SQLITE THREAD-SAFE
# =====================================================
# O bot usa TeleBot com várias threads. Um único cursor SQLite compartilhado
# entre threads causa:
#   sqlite3.ProgrammingError: Recursive use of cursors not allowed
#
# Cada thread passa a ter sua própria conexão e seu próprio cursor.
# O banco continua sendo o mesmo database.db e nenhum dado é apagado.

DB_PATH = Path("database.db")
_local = threading.local()


def _nova_conexao():
    conexao = sqlite3.connect(
        str(DB_PATH),
        check_same_thread=True,
        timeout=30
    )
    conexao.execute("PRAGMA busy_timeout=30000")
    conexao.execute("PRAGMA journal_mode=WAL")
    conexao.execute("PRAGMA synchronous=NORMAL")
    conexao.execute("PRAGMA foreign_keys=ON")
    return conexao


def _get_conn():
    if not hasattr(_local, "conn"):
        _local.conn = _nova_conexao()
    return _local.conn


def _get_cursor():
    if not hasattr(_local, "cursor"):
        _local.cursor = _get_conn().cursor()
    return _local.cursor


class _ConnectionProxy:
    def __getattr__(self, nome):
        return getattr(_get_conn(), nome)

    def commit(self):
        return _get_conn().commit()

    def rollback(self):
        return _get_conn().rollback()

    def close(self):
        # Não fecha a conexão compartilhada do processo.
        # Ela é mantida por thread e será reutilizada.
        return None


class _CursorProxy:
    def __getattr__(self, nome):
        return getattr(_get_cursor(), nome)

    def execute(self, *args, **kwargs):
        return _get_cursor().execute(*args, **kwargs)

    def executemany(self, *args, **kwargs):
        return _get_cursor().executemany(*args, **kwargs)

    def executescript(self, *args, **kwargs):
        return _get_cursor().executescript(*args, **kwargs)

    def fetchone(self):
        return _get_cursor().fetchone()

    def fetchmany(self, *args, **kwargs):
        return _get_cursor().fetchmany(*args, **kwargs)

    def fetchall(self):
        return _get_cursor().fetchall()

    @property
    def lastrowid(self):
        return _get_cursor().lastrowid

    @property
    def rowcount(self):
        return _get_cursor().rowcount


conn = _ConnectionProxy()
cursor = _CursorProxy()

# =====================================================
# INICIALIZAÇÃO DO BANCO
# =====================================================
# A criação/migração das tabelas é feita numa conexão própria de inicialização,
# antes de o bot começar a atender mensagens.
_bootstrap = _nova_conexao()
_bootstrap_cursor = _bootstrap.cursor()

# ==========================================
# USUÁRIOS
# ==========================================

_bootstrap_cursor.execute("""
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

_bootstrap_cursor.execute("""
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

_bootstrap_cursor.execute("""
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

_bootstrap_cursor.execute("""
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

_bootstrap_cursor.execute("""
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

_bootstrap_cursor.execute("""
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

_bootstrap_cursor.execute("""
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

    _bootstrap_cursor.execute(

        """
        INSERT OR IGNORE INTO configuracoes
        (chave, valor)
        VALUES (?, ?)
        """,

        (chave, valor)

    )

_bootstrap.commit()

# =====================================================
# LINKS DE CONVITE
# =====================================================

_bootstrap_cursor.execute("""
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


# =====================================================
# MOVIMENTAÇÕES FINANCEIRAS
# =====================================================

_bootstrap_cursor.execute("""
CREATE TABLE IF NOT EXISTS movimentacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL,
    tipo TEXT NOT NULL,
    valor REAL NOT NULL DEFAULT 0,
    descricao TEXT NOT NULL,
    admin_id INTEGER,
    data TEXT NOT NULL,
    FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
)
""")

# =====================================================
# NOTIFICAÇÕES
# =====================================================

_bootstrap_cursor.execute("""
CREATE TABLE IF NOT EXISTS notificacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL,
    titulo TEXT NOT NULL,
    mensagem TEXT NOT NULL,
    lida INTEGER DEFAULT 0,
    data TEXT NOT NULL,
    FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
)
""")

# =====================================================
# CAMPANHAS
# =====================================================

_bootstrap_cursor.execute("""
CREATE TABLE IF NOT EXISTS campanhas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    meta INTEGER NOT NULL DEFAULT 0,
    bonus REAL NOT NULL DEFAULT 0,
    ativa INTEGER DEFAULT 0,
    data_criacao TEXT
)
""")

_bootstrap.commit()



# =====================================================
# PERFORMANCE / INTEGRIDADE
# =====================================================
try:
    _bootstrap_cursor.execute("PRAGMA journal_mode=WAL")
    _bootstrap_cursor.execute("PRAGMA synchronous=NORMAL")
    _bootstrap_cursor.execute("PRAGMA busy_timeout=5000")
except Exception:
    pass
_bootstrap.commit()

_bootstrap.commit()
_bootstrap.close()
del _bootstrap_cursor
del _bootstrap

# As conexões das threads usam WAL + busy_timeout, reduzindo colisões entre
# handlers simultâneos.
