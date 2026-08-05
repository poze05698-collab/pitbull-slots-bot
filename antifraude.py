from database import cursor


# ==========================================
# USUÁRIO JÁ FOI INDICADO?
# ==========================================

def usuario_ja_indicado(user_id):

    cursor.execute(
        """
        SELECT id
        FROM indicacoes
        WHERE indicado_id = ?
        """,
        (user_id,)
    )

    return cursor.fetchone() is not None


# ==========================================
# NÃO PODE INDICAR A SI MESMO
# ==========================================

def auto_indicacao(indicador, indicado):

    return int(indicador) == int(indicado)


# ==========================================
# USUÁRIO ESTÁ BANIDO?
# ==========================================

def usuario_banido(user_id):

    cursor.execute(
        """
        SELECT banido
        FROM usuarios
        WHERE id = ?
        """,
        (user_id,)
    )

    resultado = cursor.fetchone()

    if resultado:
        return resultado[0] == 1

    return False


# ==========================================
# INDICAÇÃO JÁ EXISTE?
# ==========================================

def indicacao_existente(indicador, indicado):

    cursor.execute(
        """
        SELECT id
        FROM indicacoes
        WHERE indicador_id = ?
        AND indicado_id = ?
        """,
        (indicador, indicado)
    )

    return cursor.fetchone() is not None


# ==========================================
# VALIDAÇÃO GERAL
# ==========================================

def validar_indicacao(indicador, indicado):

    if auto_indicacao(indicador, indicado):
        return False, "Você não pode indicar a si mesmo."

    if usuario_banido(indicador):
        return False, "Sua conta está banida."

    if usuario_banido(indicado):
        return False, "O usuário convidado está banido."

    if usuario_ja_indicado(indicado):
        return False, "Este usuário já foi indicado anteriormente."

    if indicacao_existente(indicador, indicado):
        return False, "Esta indicação já foi registrada."

    return True, "Indicação válida."
