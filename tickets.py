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
    respostas = {}
    
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

            markup = types.InlineKeyboardMarkup()

            markup.row(

                types.InlineKeyboardButton(
                    "✉️ Responder",
                    callback_data=f"ticket_resp_{user_id}"
                ),

                types.InlineKeyboardButton(
                    "❌ Fechar",
                    callback_data=f"ticket_close_{user_id}"
                )

            )

            bot.send_message(

                ADMIN_ID,

                f"""
🎫 <b>NOVO TICKET</b>

👤 Usuário:
<code>{user_id}</code>

📝 Mensagem:

{mensagem}
""",

                parse_mode="HTML",
                reply_markup=markup

            )

        except Exception as erro:

            print(f"Erro ao enviar ticket para o admin: {erro}")

except:
    pass

    # ==========================================
    # RESPONDER TICKET
    # ==========================================

    @bot.callback_query_handler(func=lambda c: c.data.startswith("ticket_resp_"))
    def responder_ticket(call):

        user_id = int(call.data.split("_")[-1])

        respostas[call.from_user.id] = user_id

        bot.answer_callback_query(call.id)

        bot.send_message(

            call.message.chat.id,

            f"""
✍️ Digite a resposta para o usuário.

ID:
<code>{user_id}</code>
""",

            parse_mode="HTML"

        )

    # ==========================================
    # RECEBER RESPOSTA
    # ==========================================

    @bot.message_handler(
        func=lambda m: m.from_user.id in respostas
    )
    def receber_resposta(message):

        admin_id = message.from_user.id

        if admin_id != ADMIN_ID:
            return

        usuario_id = respostas.pop(admin_id)

        resposta = message.text.strip()

        cursor.execute(
            """
            UPDATE tickets
            SET
                resposta=?,
                status='RESPONDIDO',
                admin_id=?,
                data_resposta=?
            WHERE usuario_id=?
            AND status=?
            """,
            (
                resposta,
                admin_id,
                data_atual(),
                usuario_id,
                STATUS_ABERTO
            )
        )

        conn.commit()

        bot.send_message(

            usuario_id,

            f"""
📩 <b>Resposta do Suporte</b>

{resposta}
""",

            parse_mode="HTML"

        )

        bot.send_message(

            admin_id,

            "✅ Resposta enviada ao usuário."

        )

    # ==========================================
    # FECHAR TICKET
    # ==========================================

    @bot.callback_query_handler(func=lambda c: c.data.startswith("ticket_close_"))
    def fechar_ticket(call):

        if call.from_user.id != ADMIN_ID:

            bot.answer_callback_query(
                call.id,
                "Sem permissão."
            )

            return

        usuario_id = int(
            call.data.split("_")[-1]
        )

        cursor.execute(
            """
            UPDATE tickets
            SET
                status='FECHADO',
                admin_id=?,
                fechado_em=?
            WHERE usuario_id=?
            AND status IN ('ABERTO','RESPONDIDO')
            """,
            (
                ADMIN_ID,
                data_atual(),
                usuario_id
            )
        )

        conn.commit()

        bot.answer_callback_query(
            call.id,
            "✅ Ticket fechado."
        )

        try:

            bot.send_message(

                usuario_id,

                """
📩 Seu atendimento foi finalizado.

Caso precise de ajuda novamente,
basta abrir um novo ticket.
"""

            )

        except:
            pass

        try:

            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=None
            )

        except:
            pass

            
