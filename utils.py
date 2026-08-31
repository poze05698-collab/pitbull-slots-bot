from datetime import datetime

from database import conn, cursor
from config import ADMIN_ID


# =====================================================
# DATA E HORA
# =====================================================

def data_atual():
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


# =====================================================
# DINHEIRO
# =====================================================

def dinheiro(valor):
    return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# =====================================================
# ADMINISTRADORES / CARGOS
# =====================================================

CARGOS_ADMIN = {
    "gerente": {
        "nome": "👑 Gerente",
        "permissoes": {"dashboard", "indicacoes", "saques", "usuarios", "ranking", "anuncio", "gamificacao", "evento", "vip", "manutencao", "tickets", "codigos", "parceiros", "banimentos", "configuracoes", "saldo"}
    },
    "financeiro": {
        "nome": "💰 Financeiro",
        "permissoes": {"dashboard", "indicacoes", "saques", "saldo", "ranking", "usuarios"}
    },
    "suporte": {
        "nome": "🎧 Suporte",
        "permissoes": {"dashboard", "tickets", "usuarios", "ranking"}
    },
    "moderador": {
        "nome": "🛡️ Moderador",
        "permissoes": {"dashboard", "usuarios", "banimentos", "tickets", "indicacoes", "ranking"}
    },
}

def eh_admin(user_id):
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return False
    if uid == int(ADMIN_ID):
        return True
    try:
        cursor.execute("SELECT 1 FROM administradores WHERE id=? AND ativo=1", (uid,))
        return cursor.fetchone() is not None
    except Exception:
        return False

def cargo_admin(user_id):
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return None
    if uid == int(ADMIN_ID):
        return "master"
    try:
        cursor.execute("SELECT cargo FROM administradores WHERE id=? AND ativo=1", (uid,))
        row = cursor.fetchone()
        return row[0] if row else None
    except Exception:
        return None

def nome_cargo_admin(cargo):
    if cargo == "master":
        return "👑 Master"
    return CARGOS_ADMIN.get(cargo, {}).get("nome", "🎧 Suporte")

def tem_permissao_admin(user_id, permissao):
    cargo = cargo_admin(user_id)
    if cargo == "master":
        return True
    return permissao in CARGOS_ADMIN.get(cargo, {}).get("permissoes", set())


# =====================================================
# USUÁRIO
# =====================================================

def usuario_existe(user_id):

    cursor.execute(
        "SELECT id FROM usuarios WHERE id=?",
        (user_id,)
    )

    return cursor.fetchone() is not None


def buscar_usuario(user_id):

    cursor.execute(
        "SELECT * FROM usuarios WHERE id=?",
        (user_id,)
    )

    return cursor.fetchone()


# =====================================================
# PIX
# =====================================================

def buscar_pix(user_id):

    cursor.execute(
        "SELECT pix FROM usuarios WHERE id=?",
        (user_id,)
    )

    resultado = cursor.fetchone()

    if resultado:
        return resultado[0]

    return ""


# =====================================================
# SALDOS
# =====================================================

def saldo_usuario(user_id):

    cursor.execute(
        "SELECT saldo FROM usuarios WHERE id=?",
        (user_id,)
    )

    resultado = cursor.fetchone()

    return float(resultado[0]) if resultado else 0.0


def saldo_pendente(user_id):

    cursor.execute(
        "SELECT saldo_pendente FROM usuarios WHERE id=?",
        (user_id,)
    )

    resultado = cursor.fetchone()

    return float(resultado[0]) if resultado else 0.0


def saque_pendente(user_id):

    cursor.execute(
        "SELECT saque_pendente FROM usuarios WHERE id=?",
        (user_id,)
    )

    resultado = cursor.fetchone()

    return float(resultado[0]) if resultado else 0.0


# =====================================================
# ATUALIZAR SALDOS
# =====================================================

def adicionar_saldo(user_id, valor):

    cursor.execute(
        "UPDATE usuarios SET saldo = saldo + ? WHERE id=?",
        (valor, user_id)
    )

    conn.commit()


def remover_saldo(user_id, valor):

    cursor.execute(
        "UPDATE usuarios SET saldo = saldo - ? WHERE id=?",
        (valor, user_id)
    )

    conn.commit()


def adicionar_saldo_pendente(user_id, valor):

    cursor.execute(
        "UPDATE usuarios SET saldo_pendente = saldo_pendente + ? WHERE id=?",
        (valor, user_id)
    )

    conn.commit()


def remover_saldo_pendente(user_id, valor):

    cursor.execute(
        "UPDATE usuarios SET saldo_pendente = saldo_pendente - ? WHERE id=?",
        (valor, user_id)
    )

    conn.commit()


def adicionar_saque_pendente(user_id, valor):

    cursor.execute(
        "UPDATE usuarios SET saque_pendente = saque_pendente + ? WHERE id=?",
        (valor, user_id)
    )

    conn.commit()


def remover_saque_pendente(user_id, valor):

    cursor.execute(
        "UPDATE usuarios SET saque_pendente = saque_pendente - ? WHERE id=?",
        (valor, user_id)
    )

    conn.commit()


# =====================================================
# BANIMENTO
# =====================================================

def usuario_banido(user_id):

    cursor.execute(
        "SELECT banido FROM usuarios WHERE id=?",
        (user_id,)
    )

    resultado = cursor.fetchone()

    if resultado:
        return resultado[0] == 1

    return False


def banir_usuario(user_id):

    cursor.execute(
        "UPDATE usuarios SET banido=1 WHERE id=?",
        (user_id,)
    )

    conn.commit()


def desbanir_usuario(user_id):

    cursor.execute(
        "UPDATE usuarios SET banido=0 WHERE id=?",
        (user_id,)
    )

    conn.commit()


# =====================================================
# HISTÓRICO
# =====================================================

def registrar_historico(usuario_id, tipo, descricao, valor=0):

    cursor.execute(
        """
        INSERT INTO historico
        (
            usuario_id,
            tipo,
            descricao,
            valor,
            data
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            usuario_id,
            tipo,
            descricao,
            valor,
            data_atual()
        )
    )

    conn.commit()


# =====================================================
# MOVIMENTAÇÃO FINANCEIRA
# =====================================================

def registrar_movimentacao(usuario_id, tipo, valor, descricao, admin_id=None):

    cursor.execute(
        """
        INSERT INTO movimentacoes
        (usuario_id, tipo, valor, descricao, admin_id, data)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            usuario_id,
            tipo,
            float(valor),
            descricao,
            admin_id,
            data_atual()
        )
    )

    conn.commit()


# =====================================================
# NOTIFICAÇÕES
# =====================================================

def criar_notificacao(usuario_id, titulo, mensagem):

    cursor.execute(
        """
        INSERT INTO notificacoes
        (usuario_id, titulo, mensagem, data)
        VALUES (?, ?, ?, ?)
        """,
        (
            usuario_id,
            titulo,
            mensagem,
            data_atual()
        )
    )

    conn.commit()


def notificacoes_usuario(usuario_id, limite=15):

    cursor.execute(
        """
        SELECT id, titulo, mensagem, lida, data
        FROM notificacoes
        WHERE usuario_id=?
        ORDER BY id DESC
        LIMIT ?
        """,
        (usuario_id, limite)
    )

    return cursor.fetchall()


def marcar_notificacoes_lidas(usuario_id):

    cursor.execute(
        """
        UPDATE notificacoes
        SET lida=1
        WHERE usuario_id=?
        """,
        (usuario_id,)
    )

    conn.commit()


# =====================================================
# CONFIGURAÇÕES DINÂMICAS
# =====================================================

def configuracao(chave, padrao=None):

    cursor.execute(
        "SELECT valor FROM configuracoes WHERE chave=?",
        (chave,)
    )

    resultado = cursor.fetchone()

    if not resultado:
        return padrao

    return resultado[0]


def valor_indicacao_atual():

    try:
        return float(
            configuracao("valor_indicacao", "1.00")
        )
    except (TypeError, ValueError):
        return 1.0


def valor_minimo_saque_atual():

    try:
        return float(
            configuracao("valor_minimo_saque", "20")
        )
    except (TypeError, ValueError):
        return 20.0
