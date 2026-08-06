from database import conn, cursor

from config import (
    BOT_USERNAME,
    VALOR_INDICACAO,
    STATUS_PENDENTE,
    STATUS_APROVADO,
    STATUS_REJEITADO
)

from utils import (
    data_atual,
    adicionar_saldo,
    adicionar_saldo_pendente,
    remover_saldo_pendente,
    registrar_historico
)

from antifraude import validar_indicacao


# =====================================================
# LINK
# =====================================================

def gerar_link(user_id):

    return f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"


# =====================================================
# REGISTRAR INDICAÇÃO
# =====================================================

def registrar_indicacao(indicador_id, indicado_id):

    valido, motivo = validar_indicacao(
        indicador_id,
        indicado_id
    )

    if not valido:
        return False, motivo

    cursor.execute(
        """
        INSERT INTO indicacoes
        (
            indicador_id,
            indicado_id,
            valor,
            status,
            grupo_confirmado,
            admin_id,
            data,
            data_aprovacao
        )

        VALUES

        (?, ?, ?, ?, 0, NULL, ?, NULL)
        """,

        (
            indicador_id,
            indicado_id,
            VALOR_INDICACAO,
            STATUS_PENDENTE,
            data_atual()
        )

    )

    conn.commit()

    return True, "Indicação registrada."

# =====================================================
# CONFIRMAR ENTRADA NO GRUPO
# =====================================================

def confirmar_entrada_grupo(indicado_id):

    cursor.execute(
        """
        SELECT
            id,
            indicador_id,
            valor,
            grupo_confirmado
        FROM indicacoes
        WHERE indicado_id=?
        AND status=?
        """,
        (
            indicado_id,
            STATUS_PENDENTE
        )
    )

    indicacao = cursor.fetchone()

    if indicacao is None:
        return False, "Indicação não encontrada."

    indicacao_id, indicador_id, valor, grupo = indicacao

    if grupo == 1:
        return False, "Grupo já confirmado."

    cursor.execute(
        """
        UPDATE indicacoes
        SET grupo_confirmado=1
        WHERE id=?
        """,
        (indicacao_id,)
    )

    conn.commit()

    adicionar_saldo_pendente(
        indicador_id,
        valor
    )

    registrar_historico(
        indicador_id,
        "INDICACAO",
        "Usuário entrou no grupo",
        valor
    )

    return True, indicador_id


# =====================================================
# INDICAÇÕES DO USUÁRIO
# =====================================================

def indicacoes_usuario(user_id):

    cursor.execute(
        """
        SELECT
            indicado_id,
            valor,
            status,
            grupo_confirmado,
            data
        FROM indicacoes
        WHERE indicador_id=?
        ORDER BY id DESC
        """,
        (user_id,)
    )

    return cursor.fetchall()


# =====================================================
# LISTAR PENDENTES
# =====================================================

def listar_pendentes():

    cursor.execute(
        """
        SELECT
            id,
            indicador_id,
            indicado_id,
            valor,
            grupo_confirmado,
            data
        FROM indicacoes
        WHERE status=?
        ORDER BY id
        """,
        (STATUS_PENDENTE,)
    )

    return cursor.fetchall()

# =====================================================
# APROVAR INDICAÇÃO
# =====================================================

def aprovar_indicacao(indicacao_id, admin_id):

    cursor.execute(
        """
        SELECT
            indicador_id,
            valor,
            status,
            grupo_confirmado
        FROM indicacoes
        WHERE id=?
        """,
        (indicacao_id,)
    )

    indicacao = cursor.fetchone()

    if indicacao is None:
        return False, "Indicação não encontrada."

    indicador_id, valor, status, grupo = indicacao

    if status != STATUS_PENDENTE:
        return False, "Esta indicação já foi processada."

    if grupo != 1:
        return False, "O usuário ainda não foi confirmado no grupo."

    cursor.execute(
        """
        UPDATE indicacoes
        SET
            status=?,
            admin_id=?,
            data_aprovacao=?
        WHERE id=?
        """,
        (
            STATUS_APROVADO,
            admin_id,
            data_atual(),
            indicacao_id
        )
    )

    conn.commit()

    remover_saldo_pendente(
        indicador_id,
        valor
    )

    adicionar_saldo(
        indicador_id,
        valor
    )

    registrar_historico(
        indicador_id,
        "INDICACAO",
        "Indicação aprovada",
        valor
    )

    return True, indicador_id


# =====================================================
# REJEITAR INDICAÇÃO
# =====================================================

def rejeitar_indicacao(indicacao_id, admin_id, motivo):

    cursor.execute(
        """
        SELECT
            indicador_id,
            valor,
            status,
            grupo_confirmado
        FROM indicacoes
        WHERE id=?
        """,
        (indicacao_id,)
    )

    indicacao = cursor.fetchone()

    if indicacao is None:
        return False, "Indicação não encontrada."

    indicador_id, valor, status, grupo = indicacao

    if status != STATUS_PENDENTE:
        return False, "Esta indicação já foi processada."

    if grupo == 1:
        remover_saldo_pendente(
            indicador_id,
            valor
        )

    cursor.execute(
        """
        UPDATE indicacoes
        SET
            status=?,
            admin_id=?,
            data_aprovacao=?
        WHERE id=?
        """,
        (
            STATUS_REJEITADO,
            admin_id,
            data_atual(),
            indicacao_id
        )
    )

    conn.commit()

    registrar_historico(
        indicador_id,
        "INDICACAO",
        f"Indicação rejeitada: {motivo}",
        valor
    )

    return True, indicador_id
