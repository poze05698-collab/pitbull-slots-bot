from telebot import types

from database import conn, cursor

from config import (
    BOT_USERNAME,
    VALOR_INDICACAO,
    STATUS_PENDENTE
)

from utils import (
    dinheiro,
    registrar_historico,
    adicionar_saldo_pendente,
    data_atual
)

from antifraude import validar_indicacao


# ==========================================
# REGISTRAR
# ==========================================

def registrar(bot):

    # ==========================================
    # MEU LINK
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "🔗 Meu Link")
    def meu_link(message):

        user_id = message.from_user.id

        link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"

        cursor.execute(
            """
            SELECT COUNT(*)

            FROM indicacoes

            WHERE indicador_id=?

            AND status='APROVADO'
            """,
            (user_id,)
        )

        aprovadas = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*)

            FROM indicacoes

            WHERE indicador_id=?

            AND status='PENDENTE'
            """,
            (user_id,)
        )

        pendentes = cursor.fetchone()[0]

        bot.send_message(

            message.chat.id,

            f"""
🔗 <b>SEU LINK</b>

{link}

━━━━━━━━━━━━━━

✅ Aprovadas:

{aprovadas}

⏳ Pendentes:

{pendentes}

💰 Total recebido:

{dinheiro(aprovadas * VALOR_INDICACAO)}

Compartilhe este link com seus amigos.
""",

            parse_mode="HTML"

        )

    # ==========================================
    # REGISTRAR INDICAÇÃO
    # ==========================================

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

        adicionar_saldo_pendente(
            indicador_id,
            VALOR_INDICACAO
        )

        registrar_historico(
            indicador_id,
            "INDICACAO",
            "Nova indicação pendente",
            VALOR_INDICACAO
        )

        return True, "Indicação registrada."


    # ==========================================
    # CONFIRMAR ENTRADA NO GRUPO
    # ==========================================

    def confirmar_grupo(indicado_id):

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


    # ==========================================
    # BUSCAR INDICAÇÕES PENDENTES
    # ==========================================

    def listar_pendentes():

        cursor.execute(
            """
            SELECT
                id,
                indicador_id,
                indicado_id,
                valor,
                data

            FROM indicacoes

            WHERE status=?

            ORDER BY id
            """,
            (STATUS_PENDENTE,)
        )

        return cursor.fetchall()


    # ==========================================
    # BUSCAR INDICAÇÕES DO USUÁRIO
    # ==========================================

    def minhas_indicacoes(user_id):

        cursor.execute(
            """
            SELECT
                indicado_id,
                valor,
                status,
                data

            FROM indicacoes

            WHERE indicador_id=?

            ORDER BY id DESC
            """,
            (user_id,)
        )

        return cursor.fetchall()
