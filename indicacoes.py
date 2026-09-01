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

    if indicador_id == indicado_id:
        return False, "Você não pode indicar a si mesmo."

    valido, _ = validar_indicacao(indicador_id, indicado_id)
    if not valido:
        return False, "Indicação bloqueada pelo sistema antifraude."

    try:
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            """
            INSERT INTO indicacoes
            (indicador_id, indicado_id, valor, status, grupo_confirmado, data)
            VALUES (?, ?, ?, ?, 0, ?)
            """,
            (indicador_id, indicado_id, valor_indicacao, STATUS_PENDENTE, data_atual())
        )
        cursor.execute(
            """
            UPDATE usuarios
            SET saldo_pendente = COALESCE(saldo_pendente, 0) + ?
            WHERE id=?
            """,
            (valor_indicacao, indicador_id)
        )
        conn.commit()
    except Exception as erro:
        try:
            conn.rollback()
        except Exception:
            pass
        if "unique" in str(erro).lower():
            return False, "Este usuário já foi indicado."
        raise

    registrar_historico(
        indicador_id,
        "INDICACAO",
        f"Nova indicação: {indicado_id}",
        valor_indicacao
    )
    return True, "Indicação registrada com sucesso."

# CONFIRMAR ENTRADA NO GRUPO
# ==========================================================

def aprovar_indicacao_automatica(indicado_id):
    """
    Aprova automaticamente uma indicação depois que o Telegram
    confirma a entrada real do indicado no grupo.

    A decisão de segurança é determinística (entrada confirmada +
    indicação pendente), e não depende de uma resposta de LLM.
    Isso evita que uma IA possa liberar recompensa por engano.
    """
    indicacao = buscar_por_indicado(indicado_id)
    if not indicacao:
        return False, "Nenhuma indicação pendente encontrada."

    # Layout esperado: id, indicador_id, indicado_id, valor, status, grupo_confirmado, ...
    indicacao_id = indicacao[0]
    status = indicacao[4]
    grupo_confirmado = indicacao[5]

    if status != STATUS_PENDENTE:
        return False, "Indicação já processada."
    if grupo_confirmado != 1:
        return False, "Grupo ainda não confirmado."

    return aprovar_indicacao(indicacao_id, 0)


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
        "SELECT indicador_id, indicado_id, valor, status, grupo_confirmado FROM indicacoes WHERE id=?",
        (indicacao_id,)
    )
    indicacao = cursor.fetchone()
    if indicacao is None:
        return False, "Indicação não encontrada."

    indicador_id, indicado_id, valor, status, grupo_confirmado = indicacao
    if status != STATUS_PENDENTE:
        return False, "Esta indicação já foi processada."
    if grupo_confirmado != 1:
        return False, "O usuário ainda não entrou no grupo."

    from gamificacao import recompensa_dinamica, recalcular_confianca, verificar_conquistas
    from avancado import add_coins, dar_vip_xp
    valor_pago, nome_evento = recompensa_dinamica(valor)

    try:
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            """
            UPDATE indicacoes
            SET status=?, admin_id=?, data_aprovacao=?, valor_pago=?
            WHERE id=? AND status=? AND grupo_confirmado=1
            """,
            (STATUS_APROVADO, admin_id, data_atual(), valor_pago,
             indicacao_id, STATUS_PENDENTE)
        )
        if cursor.rowcount != 1:
            conn.rollback()
            return False, "Esta indicação já foi processada."

        cursor.execute(
            "UPDATE usuarios SET saldo_pendente=MAX(0,COALESCE(saldo_pendente,0)-?) WHERE id=?",
            (valor, indicador_id)
        )
        cursor.execute(
            "UPDATE usuarios SET saldo=COALESCE(saldo,0)+? WHERE id=?",
            (valor_pago, indicador_id)
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise

    descricao_evento = f" | Evento: {nome_evento}" if nome_evento else ""
    registrar_historico(
        indicador_id, "INDICACAO_APROVADA",
        f"Indicação aprovada: {indicado_id}{descricao_evento}", valor_pago
    )
    registrar_movimentacao(
        indicador_id, "INDICACAO", valor_pago,
        f"Recompensa da indicação #{indicacao_id}"
    )
    criar_notificacao(
        indicador_id, "🎉 Indicação aprovada",
        f"Sua indicação foi aprovada. R$ {valor_pago:.2f} foi liberado no seu saldo." +
        (f" Evento ativo: {nome_evento}." if nome_evento else "")
    )
    mensagem_indicado = (
        "Sua entrada no grupo foi confirmada automaticamente pelo sistema. "
        "Sua indicação também foi aprovada e a recompensa foi liberada."
        if admin_id == 0 else
        "Sua entrada foi confirmada e a indicação foi aprovada pelo administrador."
    )
    criar_notificacao(
        indicado_id, "🎉 Entrada aprovada", mensagem_indicado
    )

    try:
        add_coins(indicador_id, 5)
        dar_vip_xp(indicador_id, 10)
        recalcular_confianca(indicador_id)
        verificar_conquistas(indicador_id)
    except Exception as erro:
        print(f"Erro ao atualizar gamificação: {erro}")

    return True, indicador_id

# REJEITAR INDICAÇÃO
# ==========================================================

def rejeitar_indicacao(indicacao_id, admin_id, motivo=None):

    cursor.execute(
        "SELECT indicador_id, indicado_id, valor, status FROM indicacoes WHERE id=?",
        (indicacao_id,)
    )
    indicacao = cursor.fetchone()
    if indicacao is None:
        return False, "Indicação não encontrada."

    indicador_id, indicado_id, valor, status = indicacao
    if status != STATUS_PENDENTE:
        return False, "Esta indicação já foi processada."

    try:
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            """
            UPDATE indicacoes
            SET status=?, admin_id=?, data_aprovacao=?
            WHERE id=? AND status=?
            """,
            (STATUS_REJEITADO, admin_id, data_atual(), indicacao_id, STATUS_PENDENTE)
        )
        if cursor.rowcount != 1:
            conn.rollback()
            return False, "Esta indicação já foi processada."

        cursor.execute(
            "UPDATE usuarios SET saldo_pendente=MAX(0,COALESCE(saldo_pendente,0)-?) WHERE id=?",
            (valor, indicador_id)
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise

    registrar_historico(
        indicador_id, "INDICACAO_REJEITADA",
        f"Indicação rejeitada: {indicado_id}", valor
    )
    criar_notificacao(
        indicador_id, "❌ Indicação rejeitada",
        f"Sua indicação foi rejeitada. Motivo: {motivo or 'Não informado'}"
    )
    criar_notificacao(
        indicado_id, "❌ Indicação reprovada",
        f"Sua indicação foi reprovada. Motivo: {motivo or 'Não informado'}"
    )
    return True, indicador_id

# ==========================================================
# REABRIR / DESFAZER REJEIÇÃO DE INDICAÇÃO
# ==========================================================

def reaprovar_indicacao(indicacao_id, admin_id):
    """
    Permite ao administrador desfazer uma rejeição e aprovar novamente.

    Regras de segurança:
    - somente uma indicação REJEITADA pode ser reaberta;
    - o usuário indicado precisa ter a entrada no grupo confirmada;
    - a operação é atômica e só pode ser executada uma vez;
    - a recompensa é adicionada ao saldo somente após a mudança de status.
    """
    cursor.execute(
        "SELECT indicador_id, indicado_id, valor, status, grupo_confirmado FROM indicacoes WHERE id=?",
        (indicacao_id,)
    )
    indicacao = cursor.fetchone()
    if indicacao is None:
        return False, "Indicação não encontrada."

    indicador_id, indicado_id, valor, status, grupo_confirmado = indicacao

    if status != STATUS_REJEITADO:
        return False, "Somente indicações rejeitadas podem ser reaprovadas."

    if grupo_confirmado != 1:
        return False, "O usuário ainda não está confirmado no grupo."

    from gamificacao import recompensa_dinamica, recalcular_confianca, verificar_conquistas
    from avancado import add_coins, dar_vip_xp

    valor_pago, nome_evento = recompensa_dinamica(valor)

    try:
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            """
            UPDATE indicacoes
            SET status=?, admin_id=?, data_aprovacao=?, valor_pago=?
            WHERE id=? AND status=? AND grupo_confirmado=1
            """,
            (
                STATUS_APROVADO,
                admin_id,
                data_atual(),
                valor_pago,
                indicacao_id,
                STATUS_REJEITADO
            )
        )

        if cursor.rowcount != 1:
            conn.rollback()
            return False, "Esta indicação já foi processada por outro administrador."

        cursor.execute(
            "UPDATE usuarios SET saldo=COALESCE(saldo,0)+? WHERE id=?",
            (valor_pago, indicador_id)
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise

    descricao_evento = f" | Evento: {nome_evento}" if nome_evento else ""
    registrar_historico(
        indicador_id,
        "INDICACAO_REAPROVADA",
        f"Indicação #{indicacao_id} reaprovada: {indicado_id}{descricao_evento}",
        valor_pago
    )
    registrar_movimentacao(
        indicador_id,
        "INDICACAO",
        valor_pago,
        f"Recompensa da indicação #{indicacao_id} reaprovada"
    )
    criar_notificacao(
        indicador_id,
        "🎉 Indicação reaprovada",
        f"A indicação #{indicacao_id} foi reaprovada pelo administrador. "
        f"R$ {valor_pago:.2f} foi liberado no seu saldo."
        + (f" Evento ativo: {nome_evento}." if nome_evento else "")
    )
    criar_notificacao(
        indicado_id,
        "✅ Indicação reaprovada",
        "Sua indicação foi reavaliada e aprovada pelo administrador."
    )

    try:
        add_coins(indicador_id, 5)
        dar_vip_xp(indicador_id, 10)
        recalcular_confianca(indicador_id)
        verificar_conquistas(indicador_id)
    except Exception as erro:
        print(f"Erro ao atualizar gamificação na reaprovação: {erro}")

    return True, indicador_id


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
