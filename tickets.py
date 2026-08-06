from telebot import types

from database import cursor, conn
from utils import data_atual, registrar_historico


def registrar(bot):

    estados = {}

    @bot.message_handler(func=lambda m: m.text == "🎫 Suporte")
    def abrir_suporte(message):

        estados[message.from_user.id] = "AGUARDANDO_MENSAGEM"

        bot.send_message(

            message.chat.id,

            "✍️ Escreva sua mensagem para o suporte."

        )


    @bot.message_handler(func=lambda m: m.from_user.id in estados)
    def receber_ticket(message):

        if estados[message.from_user.id] != "AGUARDANDO_MENSAGEM":
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
            (?, ?, ?, '', 'ABERTO', NULL, ?, NULL, NULL)

            """,

            (

                message.from_user.id,

                "Suporte",

                message.text,

                data_atual()

            )

        )

        conn.commit()

        registrar_historico(

            message.from_user.id,

            "TICKET",

            "Ticket aberto"

        )

        estados.pop(message.from_user.id)

        bot.send_message(

            message.chat.id,

            "✅ Seu ticket foi enviado para o administrador."

        )
