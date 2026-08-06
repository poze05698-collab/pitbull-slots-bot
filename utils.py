from datetime import datetime

from database import cursor, conn
from config import ADMIN_ID


# ======================================================
# DATA E HORA
# ======================================================

def data_atual():
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


# ======================================================
# FORMATAR DINHEIRO
# ======================================================

def dinheiro(valor):
    return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ======================================================
# ADMIN
# ======================================================

def eh_admin(user_id):
    return int(user_id) == int(ADMIN_ID)


# ======================================================
# USUÁRIO
# ======================================================

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


# ======================================================
# SALDOS
# ======================================================

def saldo_usuario(user_id):

    cursor.execute(
        "SELECT saldo FROM usuarios WHERE id=?",
        (user_id,)
    )

    resultado = cursor.fetchone()

    if resultado:
        return float(resultado[0])

    return 0.0


def saldo_pendente(user_id):

    cursor.execute(
        "SELECT saldo_pendente FROM usuarios WHERE id=?",
        (user_id,)
    )

    resultado = cursor.fetchone()

    if resultado:
        return float(resultado[0])

    return 0.0


def saque_pendente(user_id):

    cursor.execute(
        "SELECT saque_pendente FROM usuarios WHERE id=?",
        (user_id,)
    )

    resultado = cursor.fetchone()

    if resultado:
        return float(resultado[0])

    return 0.0


# ======================================================
# PIX
# ======================================================

def buscar_pix(user_id):

    cursor.execute(
        "SELECT pix FROM usuarios WHERE id=?",
        (user_id,)
    )

    resultado = cursor.fetchone()

    if resultado:
        return resultado[0]

    return ""


# ======================================================
# ATUALIZAR SALDO
# ======================================================

def adicionar_saldo(user_id, valor):

    cursor.execute(
        """
        UPDATE usuarios
        SET saldo = saldo + ?
        WHERE id=?
        """,
        (
            valor,
            user_id
        )
    )

    conn.commit()


def remover_saldo(user_id, valor):

    cursor.execute(
        """
        UPDATE usuarios
        SET saldo = saldo - ?
        WHERE id=?
        """,
        (
            valor,
            user_id
        )
    )

    conn.commit()


def adicionar_saldo_pendente(user_id, valor):

    cursor.execute(
        """
        UPDATE usuarios
        SET saldo_pendente = saldo_pendente + ?
        WHERE id=?
        """,
        (
            valor,
            user_id
        )
    )

    conn.commit()


def remover_saldo_pendente(user_id, valor):

    cursor.execute(
        """
        UPDATE usuarios
        SET saldo_pendente = saldo_pendente - ?
        WHERE id=?
        """,
        (
            valor,
            user_id
        )
    )

    conn.commit()


def adicionar_saque_pendente(user_id, valor):

    cursor.execute(
        """
        UPDATE usuarios
        SET saque_pendente = saque_pendente + ?
        WHERE id=?
        """,
        (
            valor,
            user_id
        )
    )

    conn.commit()


def remover_saque_pendente(user_id, valor):

    cursor.execute(
        """
        UPDATE usuarios
        SET saque_pendente = saque_pendente - ?
        WHERE id=?
        """,
        (
            valor,
            user_id
        )
    )

    conn.commit()


# ======================================================
# HISTÓRICO
# ======================================================

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


# ======================================================
# BANIMENTO
# ======================================================

def usuario_banido(user_id):

    cursor.execute(
        """
        SELECT banido
        FROM usuarios
        WHERE id=?
        """,
        (user_id,)
    )

    resultado = cursor.fetchone()

    if resultado:
        return resultado[0] == 1

    return False
