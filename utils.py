from datetime import datetime

from database import cursor, conn
from config import ADMIN_ID


# ==========================================
# DATA E HORA
# ==========================================

def data_atual():
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


# ==========================================
# FORMATAR DINHEIRO
# ==========================================

def dinheiro(valor):
    return f"R$ {valor:.2f}".replace(".", ",")


# ==========================================
# VERIFICA SE É ADMIN
# ==========================================

def eh_admin(user_id):
    return int(user_id) == int(ADMIN_ID)


# ==========================================
# VERIFICA SE O USUÁRIO EXISTE
# ==========================================

def usuario_existe(user_id):

    cursor.execute(
        "SELECT id FROM usuarios WHERE id=?",
        (user_id,)
    )

    return cursor.fetchone() is not None


# ==========================================
# BUSCAR USUÁRIO
# ==========================================

def buscar_usuario(user_id):

    cursor.execute(
        "SELECT * FROM usuarios WHERE id=?",
        (user_id,)
    )

    return cursor.fetchone()


# ==========================================
# SALDO
# ==========================================

def saldo_usuario(user_id):

    cursor.execute(
        "SELECT saldo FROM usuarios WHERE id=?",
        (user_id,)
    )

    resultado = cursor.fetchone()

    if resultado:
        return resultado[0]

    return 0


# ==========================================
# SALDO PENDENTE
# ==========================================

def saldo_pendente(user_id):

    cursor.execute(
        "SELECT saldo_pendente FROM usuarios WHERE id=?",
        (user_id,)
    )

    resultado = cursor.fetchone()

    if resultado:
        return resultado[0]

    return 0


# ==========================================
# REGISTRAR HISTÓRICO
# ==========================================

def registrar_historico(user_id, tipo, descricao, valor=0):

    cursor.execute(
        """
        INSERT INTO historico
        (usuario_id, tipo, descricao, valor, data)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            user_id,
            tipo,
            descricao,
            valor,
            data_atual()
        )
    )

    conn.commit()


# ==========================================
# USUÁRIO BANIDO
# ==========================================

def usuario_banido(user_id):

    cursor.execute(
        "SELECT banido FROM usuarios WHERE id=?",
        (user_id,)
    )

    resultado = cursor.fetchone()

    if resultado:
        return resultado[0] == 1

    return False
