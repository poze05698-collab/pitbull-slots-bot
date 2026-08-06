from database import cursor, conn
from utils import data_atual


# ==========================================
# REGISTRAR FRAUDE
# ==========================================

def registrar_fraude(usuario_id, indicador_id, motivo):

    cursor.execute(
        """
        INSERT INTO fraudes
        (
            usuario_id,
            indicador_id,
            motivo,
            data
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            usuario_id,
            indicador_id,
            motivo,
            data_atual()
        )
    )

    conn.commit()


# ==========================================
# USUÁRIO JÁ FOI INDICADO
# ==========================================

def usuario_ja_indicado(user_id):

    cursor.execute(
        """
        SELECT id
        FROM indicacoes
        WHERE indicado_id=?
        """,
        (user_id,)
    )

    return cursor.fetchone() is not None


# ==========================================
# AUTO INDICAÇÃO
# ==========================================

def auto_indicacao(indicador, indicado):

    return int(indicador) == int(indicado)


# ==========================================
# USUÁRIO BANIDO
# ==========================================

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


# ==========================================
# INDICAÇÃO DUPLICADA
# ==========================================

def indicacao_existente(indicador, indicado):

    cursor.execute(
        """
        SELECT id
        FROM indicacoes
        WHERE indicador_id=?
        AND indicado_id=?
        """,
        (indicador, indicado)
    )

    return cursor.fetchone() is not None


# ==========================================
# VALIDAÇÃO
# ==========================================

def validar_indicacao(indicador, indicado):

    if auto_indicacao(indicador, indicado):

        registrar_fraude(
            indicado,
            indicador,
            "Auto indicação"
        )

        return False, "Você não pode indicar a si mesmo."


    if usuario_banido(indicador):

        registrar_fraude(
            indicado,
            indicador,
            "Indicador banido"
        )

        return False, "Conta do indicador banida."


    if usuario_banido(indicado):

        registrar_fraude(
            indicado,
            indicador,
            "Indicado banido"
        )

        return False, "Conta do indicado banida."


    if usuario_ja_indicado(indicado):

        registrar_fraude(
            indicado,
            indicador,
            "Usuário já indicado"
        )

        return False, "Este usuário já foi indicado."


    if indicacao_existente(indicador, indicado):

        registrar_fraude(
            indicado,
            indicador,
            "Indicação duplicada"
        )

        return False, "Esta indicação já existe."


    return True, "OK"
