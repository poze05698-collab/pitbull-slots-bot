from database import conn, cursor
from config import (
    BOT_USERNAME,
    STATUS_PENDENTE,
    STATUS_APROVADO,
    STATUS_REJEITADO
)

from utils import (
    data_atual,
    adicionar_saldo,
    adicionar_saldo_pendente,
    remover_saldo_pendente,
    registrar_historico,
    valor_indicacao_atual,
    criar_notificacao,
    registrar_movimentacao
)

from antifraude import validar_indicacao


def preparar_coluna_valor_pago():
    cursor.execute("PRAGMA table_info(indicacoes)")
    colunas = {linha[1] for linha in cursor.fetchall()}
    if "valor_pago" not in colunas:
        cursor.execute("ALTER TABLE indicacoes ADD COLUMN valor_pago REAL")
        conn.commit()


preparar_coluna_valor_pago()


# ==========================================================
# GERAR LINK DE INDICAÇÃO
# ==========================================================

def gerar_link(usuario_id):
    """
    Gera o link de indicação do usuário.
    """

    return f"https://t.me/{BOT_USERNAME}?start=ref_{usuario_id}"


# ==========================================================
# REGISTRAR INDICAÇÃO
# ==========================================================

def registrar_indicacao(indicador_id, indicado_id):

    valor_indicacao = valor_indicacao_atual()

    # Não pode indicar a si mesmo
    if indicador_id == indicado_id:
        return False, "Você não pode indicar a si mesmo."

    # Verifica se o usuário já foi indicado
    cursor.execute(
        """
        SELECT id
        FROM indicacoes
        WHERE indicado_id=?
        """,
        (indicado_id,)
    )

    if cursor.fetchone():
        return False, "Este usuário já foi indicado."

    # Anti fraude
    if not validar_indicacao(indicador_id, indicado_id):
        return False, "Indicação bloqueada pelo sistema antifraude."

    # Cadastra indicação
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
        VALUES
        (?, ?, ?, ?, ?, ?)
        """,
        (
            indicador_id,
            indicado_id,
            valor_indicacao,
            STATUS_PENDENTE,
            0,
            data_atual()
        )
    )

    adicionar_saldo_pendente(
        indicador_id,
        valor_indicacao
    )

    conn.commit()

    registrar_historico(
        indicador_id,
        "INDICACAO",
        f"Nova indicação: {indicado_id}",
        valor_indicacao
    )

    return True, "Indicação registrada com sucesso."# ==========================================================
# CONFIRMAR ENTRADA NO GRUPO
# ==========================================================

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


# ==========================================================
# BUSCAR INDICAÇÕES PENDENTES
# ==========================================================

def listar_indicacoes_pendentes():

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
        ORDER BY id ASC
        """,
        (
            STATUS_PENDENTE,
        )
    )

    return cursor.fetchall()


# ==========================================================
# BUSCAR INDICAÇÃO
# ==========================================================

def buscar_indicacao(indicacao_id):

    cursor.execute(
        """
        SELECT
            id,
            indicador_id,
            indicado_id,
            valor,
            status,
            grupo_confirmado
        FROM indicacoes
        WHERE id=?
        """,
        (
            indicacao_id,
        )
    )

    return cursor.fetchone()


# ==========================================================
# VERIFICAR SE O USUÁRIO JÁ POSSUI INDICAÇÃO
# ==========================================================

def usuario_possui_indicacao(usuario_id):

    cursor.execute(
        """
        SELECT id
        FROM indicacoes
        WHERE indicado_id=?
        LIMIT 1
        """,
        (
            usuario_id,
        )
    )

    return cursor.fetchone() is not None# ==========================================================
# APROVAR INDICAÇÃO
# ==========================================================

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

    if indicacao is None:
        return False, "Indicação não encontrada."

    indicador_id = indicacao[0]
    indicado_id = indicacao[1]
    valor = indicacao[2]
    status = indicacao[3]
    grupo_confirmado = indicacao[4]

    if status != STATUS_PENDENTE:
        return False, "Esta indicação já foi processada."

    if grupo_confirmado != 1:
        return False, "O usuário ainda não entrou no grupo."

    # O valor pendente é o valor base. O valor pago pode receber bônus de evento.
    from gamificacao import recompensa_dinamica, recalcular_confianca, verificar_conquistas
    from avancado import add_coins, dar_vip_xp
    valor_pago, nome_evento = recompensa_dinamica(valor)

    remover_saldo_pendente(
        indicador_id,
        valor
    )

    adicionar_saldo(
        indicador_id,
        valor_pago
    )

    cursor.execute(
        """
        UPDATE indicacoes
        SET
            status=?,
            admin_id=?,
            data_aprovacao=?,
            valor_pago=?
        WHERE id=?
        """,
        (
            STATUS_APROVADO,
            admin_id,
            data_atual(),
            valor_pago,
            indicacao_id
        )
    )

    conn.commit()

    descricao_evento = f" | Evento: {nome_evento}" if nome_evento else ""

    registrar_historico(
        indicador_id,
        "INDICACAO_APROVADA",
        f"Indicação aprovada: {indicado_id}{descricao_evento}",
        valor_pago
    )

    registrar_movimentacao(
        indicador_id,
        "INDICACAO",
        valor_pago,
        f"Recompensa da indicação #{indicacao_id}"
    )

    criar_notificacao(
        indicador_id,
        "🎉 Indicação aprovada",
        f"Sua indicação foi aprovada. R$ {valor_pago:.2f} foi liberado no seu saldo." + (f" Evento ativo: {nome_evento}." if nome_evento else "")
    )

    criar_notificacao(
        indicado_id,
        "🎉 Entrada aprovada",
        "Sua entrada foi confirmada e a indicação foi aprovada pelo administrador."
    )

    try:
        add_coins(indicador_id, 5)
        dar_vip_xp(indicador_id, 10)
        recalcular_confianca(indicador_id)
        verificar_conquistas(indicador_id)
    except Exception as erro:
        print(f"Erro ao atualizar gamificação: {erro}")

    return True, indicador_id


# ==========================================================
# REJEITAR INDICAÇÃO
# ==========================================================

def rejeitar_indicacao(indicacao_id, admin_id, motivo=None):

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

    if indicacao is None:
        return False, "Indicação não encontrada."

    indicador_id = indicacao[0]
    indicado_id = indicacao[1]
    valor = indicacao[2]
    status = indicacao[3]

    if status != STATUS_PENDENTE:
        return False, "Esta indicação já foi processada."

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

    criar_notificacao(
        indicador_id,
        "❌ Indicação rejeitada",
        f"Sua indicação foi rejeitada. Motivo: {motivo or 'Não informado'}"
    )

    criar_notificacao(
        indicado_id,
        "❌ Indicação reprovada",
        f"Sua indicação foi reprovada. Motivo: {motivo or 'Não informado'}"
    )

    return True, indicador_id# ==========================================================
# INDICAÇÕES DO USUÁRIO
# ==========================================================

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
        (
            usuario_id,
        )
    )

    return cursor.fetchall()


# ==========================================================
# ESTATÍSTICAS
# ==========================================================

def total_indicacoes():

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM indicacoes
        """
    )

    return cursor.fetchone()[0]


def total_pendentes():

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM indicacoes
        WHERE status=?
        """,
        (
            STATUS_PENDENTE,
        )
    )

    return cursor.fetchone()[0]


def total_aprovadas():

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM indicacoes
        WHERE status=?
        """,
        (
            STATUS_APROVADO,
        )
    )

    return cursor.fetchone()[0]


def total_rejeitadas():

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM indicacoes
        WHERE status=?
        """,
        (
            STATUS_REJEITADO,
        )
    )

    return cursor.fetchone()[0]


# ==========================================================
# BUSCAR INDICAÇÃO PELO INDICADO
# ==========================================================

def buscar_por_indicado(indicado_id):

    cursor.execute(
        """
        SELECT *
        FROM indicacoes
        WHERE indicado_id=?
        LIMIT 1
        """,
        (
            indicado_id,
        )
    )

    return cursor.fetchone()

# ==========================================================
# SALVAR LINK DE CONVITE
# ==========================================================

def salvar_link_convite(usuario_id, invite_link, invite_name):

    cursor.execute(
        """
        INSERT INTO links_convite
        (
            usuario_id,
            invite_link,
            invite_name,
            data_criacao
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            usuario_id,
            invite_link,
            invite_name,
            data_atual()
        )
    )

    conn.commit()


# ==========================================================
# DESATIVAR CONVITES ANTIGOS
# ==========================================================

def desativar_convites(usuario_id):

    cursor.execute(
        """
        UPDATE links_convite
        SET ativo=0
        WHERE usuario_id=?
        """,
        (
            usuario_id,
        )
    )

    conn.commit()

# ==========================================================
# BUSCAR DONO DO LINK
# ==========================================================

def buscar_dono_convite(invite_link):

    cursor.execute(
        """
        SELECT usuario_id
        FROM links_convite
        WHERE invite_link=?
        AND ativo=1
        LIMIT 1
        """,
        (
            invite_link,
        )
    )

    resultado = cursor.fetchone()

    if resultado:
        return resultado[0]

    return None
        
# ==========================================================
# BUSCAR INDICAÇÃO PELO INDICADOR
# ==========================================================

def buscar_por_indicador(indicador_id):

    cursor.execute(
        """
        SELECT *
        FROM indicacoes
        WHERE indicador_id=?
        ORDER BY id DESC
        """
        ,
        (
            indicador_id,
        )
    )

    return cursor.fetchall()
