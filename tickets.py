from telebot import types

from database import cursor, conn

from config import (
    ADMIN_ID,
    STATUS_ABERTO
)

from utils import (
    data_atual,
    registrar_historico
)

from antifraude import usuario_banido


def registrar(bot):

    estados = {}

    # ==========================================
    # ABRIR SUPORTE
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "🎫 Suporte")
    def abrir_suporte(message):

        user_id = message.from_user.id

        if usuario_banido(user_id):

            bot.send_message(

                message.chat.id,

                "❌ Sua conta está bloqueada."

            )

            return

        cursor.execute(

            """
            SELECT id
            FROM tickets
            WHERE usuario_id=?
            AND status=?
            """,

            (

                user_id,

                STATUS_ABERTO

            )

        )

        if cursor.fetchone():

            bot.send_message(

                message.chat.id,

                "❌ Você já possui um ticket aberto."

            )

            return

        estados[user_id] = "AGUARDANDO_MENSAGEM"

        bot.send_message(

            message.chat.id,

            """
✍️ Escreva sua mensagem para o suporte.

Envie todos os detalhes para facilitar o atendimento.
"""

        )

    # ==========================================
    # RECEBER TICKET
    # ==========================================

    @bot.message_handler(func=lambda m: m.from_user.id in estados)
    def receber_ticket(message):

        user_id = message.from_user.id

        if estados.get(user_id) != "AGUARDANDO_MENSAGEM":
            return

        mensagem = message.text.strip()

        if len(mensagem) < 5:

            bot.send_message(

                message.chat.id,

                "❌ Escreva uma mensagem com pelo menos 5 caracteres."

            )

            return

        cursor.execute(

            """
            INSERT INTO tickets
            (
                usuario_id,
                assunto,
                mensagem,
                resposta,
                status,
                admin_id,
                data,
                data_resposta,
                fechado_em
            )

            VALUES
            (?, ?, ?, '', ?, NULL, ?, NULL, NULL)

            """,

            (

                user_id,

                "Suporte",

                mensagem,

                STATUS_ABERTO,

                data_atual()

            )

        )

        conn.commit()

        registrar_historico(

            user_id,

            "TICKET",

            "Ticket aberto"

        )

        estados.pop(user_id, None)

        bot.send_message(

            message.chat.id,

            "✅ Seu ticket foi enviado para o administrador."

        )

        try:

            bot.send_message(

                ADMIN_ID,

                f"""
🎫 <b>NOVO TICKET</b>

👤 Usuário:
<code>{user_id}</code>

📝 Mensagem:

{mensagem}
""",

                parse_mode="HTML"

            )

        except:
            pass
