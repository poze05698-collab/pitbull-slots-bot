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

