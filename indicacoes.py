from database import conn, cursor

from config import (
    BOT_USERNAME,
    GRUPO_ID,
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

    """
    Compatibilidade com a versão atual.

    Esta função continuará existindo para não quebrar
    outras partes do projeto.

    A geração do convite do grupo será feita pelo
    usuario.py utilizando o objeto bot.

    Esta função passa apenas a retornar None quando
    não houver um convite criado.
    """

    cursor.execute(
        """
        SELECT invite_link
        FROM links_convite
        WHERE usuario_id=?
        AND ativo=1
        LIMIT 1
        """,
        (user_id,)
    )

    resultado = cursor.fetchone()

    if resultado:
        return resultado[0]

    return None


# =====================================================
# LINKS DE CONVITE
# =====================================================

def salvar_link_convite(
    usuario_id,
    invite_link,
    invite_name
):

    cursor.execute(
        """
        INSERT INTO links_convite
        (
            usuario_id,
            invite_link,
            invite_name,
            data_criacao
        )
        VALUES
        (?, ?, ?, ?)
        """,
        (
            usuario_id,
            invite_link,
            invite_name,
            data_atual()
        )
    )

    conn.commit()


def buscar_dono_convite(invite_link):

    cursor.execute(
        """
        SELECT usuario_id
        FROM links_convite
        WHERE invite_link=?
        AND ativo=1
        LIMIT 1
        """,
        (invite_link,)
    )

    resultado = cursor.fetchone()

    if resultado:
        return resultado[0]

    return None


def desativar_convites(usuario_id):

    cursor.execute(
        """
        UPDATE links_convite
        SET ativo=0
        WHERE usuario_id=?
        """,
        (usuario_id,)
    )

    conn.commit()

# =====================================================
# REGISTRAR INDICAÇÃO
# =====================================================

def registrar_indicacao(indicador_id, indicado_id):

    if indicador_id == indicado_id:
        return False

    cursor.execute(
        "SELECT id FROM indicacoes WHERE indicado_id=?",
        (indicado_id,)
    )

    if cursor.fetchone():
        return False

    if not validar_indicacao(indicador_id, indicado_id):
        return False

    cursor.execute(
        """
        INSERT INTO indicacoes
        (
            indicador_id,
            indicado_id,
            valor,
            status,
            grupo_confirmado,
            data
        )
        VALUES (?, ?, ?, ?, 0, ?)
        """,
        (
            indicador_id,
            indicado_id,
            VALOR_INDICACAO,
            STATUS_PENDENTE,
            data_atual()
        )
    )

    adicionar_saldo_pendente(
        indicador_id,
        VALOR_INDICACAO
    )

    conn.commit()

    registrar_historico(
        indicador_id,
        "INDICACAO",
        f"Nova indicação pendente: {indicado_id}",
        VALOR_INDICACAO
    )

    return True


# =====================================================
# CONFIRMAR ENTRADA NO GRUPO
# =====================================================

def confirmar_entrada_grupo(indicado_id):

    cursor.execute(
        """
        UPDATE indicacoes
        SET grupo_confirmado=1
        WHERE indicado_id=?
        AND status=?
        """,
        (
            indicado_id,
            STATUS_PENDENTE
        )
    )

    conn.commit()

    return cursor.rowcount > 0


# =====================================================
# APROVAR INDICAÇÃO
# =====================================================

def aprovar_indicacao(indicacao_id, admin_id):

    cursor.execute(
        """
        SELECT
            indicador_id,
            indicado_id,
            valor,
            status,
            grupo_confirmado
        FROM indicacoes
        WHERE id=?
        """,
        (indicacao_id,)
    )

    indicacao = cursor.fetchone()

    if not indicacao:
        return False

    indicador_id = indicacao[0]
    indicado_id = indicacao[1]
    valor = indicacao[2]
    status = indicacao[3]
    grupo_confirmado = indicacao[4]

    if status != STATUS_PENDENTE:
        return False

    if not grupo_confirmado:
        return False

    remover_saldo_pendente(
        indicador_id,
        valor
    )

    adicionar_saldo(
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
            STATUS_APROVADO,
            admin_id,
            data_atual(),
            indicacao_id
        )
    )

    conn.commit()

    registrar_historico(
        indicador_id,
        "INDICACAO_APROVADA",
        f"Indicação aprovada: {indicado_id}",
        valor
    )

    return True


# =====================================================
# REJEITAR INDICAÇÃO
# =====================================================

def rejeitar_indicacao(indicacao_id, admin_id):

    cursor.execute(
        """
        SELECT
            indicador_id,
            indicado_id,
            valor,
            status
        FROM indicacoes
        WHERE id=?
        """,
        (indicacao_id,)
    )

    indicacao = cursor.fetchone()

    if not indicacao:
        return False

    indicador_id = indicacao[0]
    indicado_id = indicacao[1]
    valor = indicacao[2]
    status = indicacao[3]

    if status != STATUS_PENDENTE:
        return False

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
        "INDICACAO_REJEITADA",
        f"Indicação rejeitada: {indicado_id}",
        valor
    )

    return True


# =====================================================
# INDICAÇÕES DO USUÁRIO
# =====================================================

def indicacoes_usuario(usuario_id):

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
        (usuario_id,)
    )

    return cursor.fetchall()
